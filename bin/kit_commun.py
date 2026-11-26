"""Fonctions communes aux scripts du kit (bin/) et aux hooks qui lancent init.sh.

Bibliothèque standard seulement. Toute erreur lève une exception : chaque script
appelant la transforme en refus (échouer fermé).
"""
import json
import os
import re
import subprocess
import tempfile

# Nom complet : une branche locale nommée « origin/main » (refs/heads/origin/main) passerait
# avant refs/remotes/origin/main avec le nom court.
REFERENCE = "refs/remotes/origin/main"
# D28 : motifs refusés dans le message de chaque commit (comparés en minuscules).
MOTIFS_D28 = (("co-authored-by", "Co-Authored-By"),
              ("anthropic.com", "mention anthropic.com"),
              ("generated with claude code", "mention « Generated with Claude Code »"),
              ("generated with [claude code]", "mention « Generated with Claude Code »"),
              ("claude.com/claude-code", "lien claude.com/claude-code"),
              ("claude.ai/code", "lien de session claude.ai/code"))
LISTE = "feature_list.json"
DOSSIER_TESTS = "tests/acceptance"
LANCEUR = DOSSIER_TESTS + "/kit.json"
CATEGORIES = {"fonctionnel", "interface", "securite", "donnees", "infra"}
CHAMPS = {"id", "besoin", "jalon", "priorite", "category", "description", "steps",
          "test", "touches", "depends_on", "attribue_a", "passes"}
OBLIGATOIRES = CHAMPS - {"attribue_a"}


class Erreur(Exception):
    """Erreur qui doit faire refuser l'action."""


def git(args, cwd, entree=None, binaire=False):
    r = subprocess.run(["git"] + args, cwd=cwd, input=entree, capture_output=True,
                       text=not binaire)
    if r.returncode != 0:
        err = r.stderr if not binaire else r.stderr.decode("utf-8", "replace")
        raise Erreur("git " + " ".join(args) + " : " + err.strip())
    return r.stdout


def racine_depot(cwd):
    return git(["rev-parse", "--show-toplevel"], cwd).strip()


def lire_a_la_reference(depot, reference, chemin):
    return git(["show", reference + ":" + chemin], depot)


def pilote(depot):
    """(nom, courriel) du pilote : l'identité git configurée là où orchestre tourne."""
    ident = git(["var", "GIT_AUTHOR_IDENT"], depot).strip()
    m = re.fullmatch(r"(.*) <(.*)> \d+ [+-]\d{4}", ident)
    if not m or not m.group(1) or not m.group(2):
        raise Erreur("identité git du pilote illisible : " + ident)
    return m.group(1), m.group(2)


def ecarts_d28(depot, plage, nom, courriel):
    """D28 : chaque commit de <plage> est au seul nom du pilote, sans Co-Authored-By,
    anthropic.com, « Generated with Claude Code » ni lien de session (MOTIFS_D28).
    Renvoie la liste des écarts (vide si tout est conforme)."""
    if not nom or not courriel:
        return ["pilote non configuré (nom et courriel obligatoires)"]
    sortie = git(["log", "--format=%H%n%an%n%ae%n%cn%n%ce%n%B%x00", plage, "--"], depot)
    ecarts = []
    for bloc in sortie.split("\x00"):
        lignes = bloc.strip("\n").split("\n")
        if len(lignes) < 5:
            continue
        sha, texte = lignes[0][:12], "\n".join(lignes[1:]).lower()
        if lignes[1:5] != [nom, courriel, nom, courriel]:
            ecarts.append(sha + " : auteur ou committer autre que le pilote (%s / %s)"
                          % (lignes[1] + " <" + lignes[2] + ">", lignes[3] + " <" + lignes[4] + ">"))
        vus = []
        for motif, libelle in MOTIFS_D28:
            if motif in texte and libelle not in vus:
                vus.append(libelle)
                ecarts.append(sha + " : " + libelle)
    return ecarts


def nom_court(reference):
    """Nom lisible d'une référence dans les messages (refs/remotes/origin/main → origin/main)."""
    return reference[len("refs/remotes/"):] if reference.startswith("refs/remotes/") else reference


def lancer_init(depot, args, delai, reference=REFERENCE):
    """Lance init.sh tel qu'il est à la référence (git show), jamais la copie de travail :
    init.sh appartient à la référence, comme tests/acceptance/. Copié dans un fichier
    temporaire hors du dépôt, exécuté avec le dépôt comme dossier courant.
    Lève Erreur s'il est absent de la référence ; subprocess.TimeoutExpired au délai."""
    try:
        contenu = git(["show", reference + ":init.sh"], depot, binaire=True)
    except Erreur:
        raise Erreur("init.sh absent de " + nom_court(reference))
    with tempfile.TemporaryDirectory(prefix="kit-init-") as tmp:
        script = os.path.join(tmp, "init.sh")
        with open(script, "wb") as f:
            f.write(contenu)
        os.chmod(script, 0o700)
        return subprocess.run([script] + list(args), cwd=depot, capture_output=True,
                              text=True, timeout=delai)


def valider_liste(donnees):
    """Vérifie le schéma de feature_list.json (modeles/feature_list.schema.json).
    Renvoie la liste des erreurs (vide si la liste est valide)."""
    erreurs = []
    if not isinstance(donnees, dict):
        return ["la racine doit être un objet"]
    for cle in ("projet", "version_kit", "fonctionnalites"):
        if cle not in donnees:
            erreurs.append("clé manquante : " + cle)
    if erreurs:
        return erreurs
    if not isinstance(donnees["projet"], str) or not isinstance(donnees["version_kit"], str):
        erreurs.append("projet et version_kit doivent être des chaînes")
    fonctions = donnees["fonctionnalites"]
    if not isinstance(fonctions, list):
        return erreurs + ["fonctionnalites doit être une liste"]
    ids = set()
    for i, f in enumerate(fonctions):
        nom = "fonctionnalité %d" % i
        if not isinstance(f, dict):
            erreurs.append(nom + " : doit être un objet")
            continue
        manquants = OBLIGATOIRES - set(f)
        en_trop = set(f) - CHAMPS
        if manquants:
            erreurs.append(nom + " : champs manquants " + ", ".join(sorted(manquants)))
        if en_trop:
            erreurs.append(nom + " : champs inconnus " + ", ".join(sorted(en_trop)))
        if manquants:
            continue
        fid = f["id"]
        if not isinstance(fid, str) or not re.fullmatch(r"F[0-9]{3}", fid):
            erreurs.append(nom + " : id invalide")
        elif fid in ids:
            erreurs.append(nom + " : id en double " + fid)
        ids.add(fid)
        if not (isinstance(f["besoin"], list) and all(type(b) is int for b in f["besoin"])):
            erreurs.append(nom + " : besoin doit être une liste d'entiers")
        if not isinstance(f["jalon"], str):
            erreurs.append(nom + " : jalon doit être une chaîne")
        if type(f["priorite"]) is not int or f["priorite"] < 1:
            erreurs.append(nom + " : priorite doit être un entier >= 1")
        if f["category"] not in CATEGORIES:
            erreurs.append(nom + " : category inconnue")
        if not isinstance(f["description"], str) or len(f["description"]) > 200:
            erreurs.append(nom + " : description absente ou > 200 caractères")
        for cle, minimum in (("steps", 1), ("touches", 0), ("depends_on", 0)):
            v = f[cle]
            if not (isinstance(v, list) and len(v) >= minimum
                    and all(isinstance(x, str) for x in v)):
                erreurs.append(nom + " : " + cle + " doit être une liste de chaînes")
        if not isinstance(f["test"], str):
            erreurs.append(nom + " : test doit être une chaîne")
        if f.get("attribue_a") is not None and not isinstance(f["attribue_a"], str):
            erreurs.append(nom + " : attribue_a doit être une chaîne ou null")
        if type(f["passes"]) is not bool:
            erreurs.append(nom + " : passes doit être un booléen")
    for f in fonctions:
        if isinstance(f, dict) and isinstance(f.get("depends_on"), list):
            for d in f["depends_on"]:
                if d not in ids:
                    erreurs.append(str(f.get("id")) + " : dépendance inconnue " + str(d))
    return erreurs


def charger_liste(texte):
    donnees = json.loads(texte)
    erreurs = valider_liste(donnees)
    if erreurs:
        raise Erreur("feature_list.json invalide : " + " ; ".join(erreurs))
    return donnees


def par_id(liste):
    return {f["id"]: f for f in liste["fonctionnalites"]}


def ecarts_hors_passes(avant, apres):
    """Différences entre deux listes, en dehors du champ « passes »."""
    def sans_passes(liste):
        copie = json.loads(json.dumps(liste))
        for f in copie.get("fonctionnalites", []):
            if isinstance(f, dict):
                f.pop("passes", None)
        return copie
    a, b = sans_passes(avant), sans_passes(apres)
    if a == b:
        return []
    ecarts = []
    for cle in sorted(set(a) | set(b)):
        if cle != "fonctionnalites" and a.get(cle) != b.get(cle):
            ecarts.append("clé « " + cle + " » modifiée")
    fa = {f.get("id"): f for f in a.get("fonctionnalites", [])}
    fb = {f.get("id"): f for f in b.get("fonctionnalites", [])}
    for fid in sorted(set(fa) | set(fb), key=str):
        if fid not in fb:
            ecarts.append(str(fid) + " supprimée")
        elif fid not in fa:
            ecarts.append(str(fid) + " ajoutée")
        elif fa[fid] != fb[fid]:
            champs = sorted(k for k in set(fa[fid]) | set(fb[fid])
                            if fa[fid].get(k) != fb[fid].get(k))
            ecarts.append(str(fid) + " : " + ", ".join(champs) + " modifié(s)")
    if not ecarts:
        ecarts.append("ordre des fonctionnalités modifié")
    return ecarts


def charger_lanceur(texte):
    """tests/acceptance/kit.json : {"image": "...", "commande": ["...", "{test}"]}."""
    lanceur = json.loads(texte)
    image, commande = lanceur.get("image"), lanceur.get("commande")
    if not (isinstance(image, str) and image and isinstance(commande, list) and commande
            and all(isinstance(x, str) for x in commande)):
        raise Erreur(LANCEUR + " invalide : il faut « image » (chaîne) et « commande » (liste)")
    return image, commande


def lancer_test(lanceur, test, depot, tests_reference=None, liste_reference=None,
                delai=900):
    """Lance un test d'acceptation dans un conteneur Docker jetable.

    La copie de travail est montée en lecture seule sur /depot ; si on les donne,
    le dossier des tests et la liste de la référence remplacent ceux de la copie
    de travail (montés en lecture seule eux aussi). Pas de réseau, pas de variable
    d'environnement de l'hôte, aucun droit ajouté. Renvoie (code, sortie)."""
    image, commande = lanceur
    if not re.fullmatch(re.escape(DOSSIER_TESTS) + r"/[A-Za-z0-9_./-]+", test) or ".." in test:
        raise Erreur("chemin de test refusé : " + test)
    nom = "kit-test-%d" % os.getpid()
    cmd = ["docker", "run", "--rm", "--name", nom, "--network", "none",
           "--read-only", "--tmpfs", "/tmp", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges",
           "--user", "%d:%d" % (os.getuid(), os.getgid()),
           "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
           "-v", os.path.abspath(depot) + ":/depot:ro"]
    if tests_reference:
        cmd += ["-v", os.path.abspath(tests_reference) + ":/depot/" + DOSSIER_TESTS + ":ro"]
    if liste_reference:
        cmd += ["-v", os.path.abspath(liste_reference) + ":/depot/" + LISTE + ":ro"]
    cmd += ["-w", "/depot", "--entrypoint", commande[0], image]
    cmd += [x.replace("{test}", test) for x in commande[1:]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=delai)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", nom], capture_output=True)
        return 124, "délai dépassé (%d s)" % delai
    return r.returncode, (r.stdout + r.stderr)
