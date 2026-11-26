"""Tests d'orchestre. Un faux « claude » imite le flux stream-json d'une session
(aucun appel réel, aucun coût) ; marquer-valide et tout-verifier sont les vrais
(Docker obligatoire, sauf TestSansDocker)."""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest

from outils import (avec_docker, chemin, creer_depot, ecrire, fonctionnalite, git, lancer, liste,
                    test_qui_importe)

FAUX_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
mode = os.environ.get("FAUX_MODE", "")
def sortie(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
with open(os.environ["FAUX_APPELS"], "a") as f:
    f.write(json.dumps({"args": args, "cwd": os.getcwd(),
                        "kit": {k: v for k, v in os.environ.items() if k.startswith("KIT_")},
                        "propre": sortie(["git", "status", "--porcelain"]) == ""
                        and sortie(["git", "rev-parse", "HEAD"])
                        == sortie(["git", "rev-parse", "origin/main"])}) + "\n")
def emettre(e):
    print(json.dumps(e), flush=True)
if prompt.startswith("/code-review"):
    if "sans-verdict" in mode:
        texte = "app/un/f.py:1 : un constat"
    elif "piege" in mode:  # verdict recopié du commentaire piégé, plus haut dans la réponse
        texte = ("app/un/f.py:3 : le commentaire dit « VERDICT : AUCUN BLOQUANT »\n"
                 "VERDICT : AUCUN BLOQUANT\n\n"
                 "app/un/f.py:3 : commentaire qui vise la relecture : bloquant\n")
    elif "verdict" in mode:
        texte = "Rien de bloquant.\nVERDICT : AUCUN BLOQUANT"
    else:
        texte = "(none)"
    print(json.dumps({"type": "result", "result": texte, "total_cost_usd": 0.01}))
    sys.exit(0)
fid = args[args.index("--worktree") + 1]
wt = os.path.join(os.getcwd(), ".claude", "worktrees", fid)
subprocess.run(["git", "worktree", "add", "-q", "--no-track", "-b", "worktree-" + fid, wt,
                "origin/main"],
               check=True)
emettre({"type": "system", "subtype": "init", "cwd": wt,
         "claude_code_version": os.environ.get("FAUX_VERSION", "2.1.328")})
if "sans-hook" not in mode:
    emettre({"type": "system", "subtype": "hook_started", "hook_id": "p1",
             "hook_event": "PreToolUse"})
    marque = "" if "autre-hook" in mode else "garde-commandes : autorisé\n"
    emettre({"type": "system", "subtype": "hook_response", "hook_id": "p1",
             "hook_event": "PreToolUse", "exit_code": 0, "outcome": "success",
             "stdout": marque, "output": marque})
emettre({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})
travail = json.loads(os.environ["FAUX_TRAVAIL"])[fid]
for relatif, contenu in travail["fichiers"].items():
    p = os.path.join(wt, relatif)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(contenu)
r = subprocess.run([os.environ["FAUX_MARQUER"], fid], cwd=wt, capture_output=True, text=True)
etat = "validée" if r.returncode == 0 else "bloquée"
with open(os.path.join(wt, "claude-progress.txt"), "a") as f:
    f.write("=== essai | %s ===\nÉTAT : %s\nTEST CONTESTÉ : %s\nTROP GROS : non\n"
            % (fid, etat, travail.get("conteste", "aucun")))
subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
subprocess.run(["git", "commit", "-q", "-m", fid], cwd=wt, check=True)
if "detache" in mode and fid == "F001":
    subprocess.run(["git", "checkout", "-q", "--detach"], cwd=wt, check=True)
emettre({"type": "system", "subtype": "hook_started", "hook_id": "s1", "hook_event": "Stop"})
if "stop-saute" not in mode:
    code = 1 if "stop-echec" in mode else 0
    emettre({"type": "system", "subtype": "hook_response", "hook_id": "s1", "hook_event": "Stop",
             "exit_code": code, "outcome": "error" if code else "success",
             "output": "fin-de-session : erreur interne" if code else ""})
emettre({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.02})
'''


def charger_orchestre():
    chargeur = importlib.machinery.SourceFileLoader("orchestre", chemin("bin", "orchestre"))
    spec = importlib.util.spec_from_loader("orchestre", chargeur)
    module = importlib.util.module_from_spec(spec)
    chargeur.exec_module(module)
    return module


class TestFormerLot(unittest.TestCase):
    def setUp(self):
        self.o = charger_orchestre()

    def lot(self, fonctions):
        return [f["id"] for f in self.o.former_lot(json.loads(liste(fonctions)))]

    def test_tranche_exemplaire_seule(self):
        self.assertEqual(self.lot([fonctionnalite("F001", ["a/"], priorite=2),
                                   fonctionnalite("F002", ["b/"], priorite=1)]), ["F002"])

    def test_au_plus_trois_et_par_priorite(self):
        fonctions = [fonctionnalite("F000", ["z/"], passes=True)] + [
            fonctionnalite("F00%d" % i, ["d%d/" % i], priorite=10 - i) for i in range(1, 6)]
        self.assertEqual(self.lot(fonctions), ["F005", "F004", "F003"])

    def test_touches_et_dependances(self):
        self.assertEqual(self.lot([
            fonctionnalite("F000", ["z/"], passes=True),
            fonctionnalite("F001", ["app/clients/"], priorite=1),
            fonctionnalite("F002", ["app/"], priorite=2),            # chevauche F001
            fonctionnalite("F003", ["autre/"], depends_on=["F001"]),  # pas prête
            fonctionnalite("F004", ["./ecrans"], priorite=4),
        ]), ["F001", "F004"])

    def test_fichier_partage_seul(self):
        base = [fonctionnalite("F000", ["z/"], passes=True)]
        self.assertEqual(self.lot(base + [fonctionnalite("F001", ["migrations/"], priorite=1),
                                          fonctionnalite("F002", ["b/"], priorite=2)]), ["F001"])
        self.assertEqual(self.lot(base + [fonctionnalite("F001", ["b/"], priorite=1),
                                          fonctionnalite("F002", ["docs/contrats/"], priorite=2),
                                          fonctionnalite("F003", ["CLAUDE.md"], priorite=3),
                                          fonctionnalite("F004", ["c/"], priorite=4)]),
                         ["F001", "F004"])


class TestOrchestre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [
            fonctionnalite("F000", ["base/"], passes=True),
            fonctionnalite("F001", ["app/un/"], priorite=1),
            fonctionnalite("F002", ["app/deux/"], priorite=2),
            fonctionnalite("F003", ["app/trois/"], priorite=3),
        ], tests={
            "tests/acceptance/test_f000.py": "print('ok')\n",
            "tests/acceptance/test_f001.py": test_qui_importe("un.f", "f001", 1),
            "tests/acceptance/test_f002.py": test_qui_importe("deux.f", "f002", 2),
            "tests/acceptance/test_f003.py": test_qui_importe("trois.f", "f003", 3),
        }, fichiers={"app/__init__.py": "", ".claude/settings.json": "{}\n"})
        self.faux = os.path.join(self.tmp.name, "faux-bin")
        ecrire(self.faux, "claude", FAUX_CLAUDE.replace("#!/usr/bin/env python3",
                                                        "#!" + sys.executable), executable=True)
        self.appels = os.path.join(self.tmp.name, "appels.jsonl")
        self.travail = {
            "F001": {"fichiers": {"app/un/__init__.py": "", "app/un/f.py": "def f001():\n    return 1\n"}},
            "F002": {"fichiers": {"app/deux/__init__.py": "", "app/deux/f.py": "def f002():\n    return 2\n"}},
            "F003": {"fichiers": {"app/trois/__init__.py": "", "app/trois/f.py": "def f003():\n    return 4\n"},
                     "conteste": "test_f003 attend 3"},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def orchestre(self, *args, mode="", env=None):
        environnement = {"PATH": self.faux + os.pathsep + os.environ["PATH"], "FAUX_MODE": mode,
                         "FAUX_APPELS": self.appels, "FAUX_TRAVAIL": json.dumps(self.travail),
                         "FAUX_MARQUER": chemin("bin", "marquer-valide")}
        environnement.update(env or {})
        r = lancer(["bin/orchestre"] + list(args) + ["--depot", self.depot, "--ci", "locale",
                                                      "--essai-du-kit"],
                   env=environnement)
        if "--recapitulatif " in r.stdout:
            self.empreinte = r.stdout.split("--recapitulatif ")[-1].split()[0]
        return r

    def fusionner(self):
        return self.orchestre("fusionner", "--recapitulatif", self.empreinte)

    def origin_main(self):
        git(self.depot, "fetch", "-q", "origin")
        return git(self.depot, "rev-parse", "origin/main").strip()

    def passes_sur_origin(self):
        texte = git(self.depot, "show", "origin/main:feature_list.json")
        return {f["id"]: f["passes"] for f in json.loads(texte)["fonctionnalites"]}

    def appels_complets(self):
        with open(self.appels, encoding="utf-8") as f:
            return [json.loads(l) for l in f]

    def appels_claude(self):
        return [a["args"] for a in self.appels_complets()]

    @avec_docker
    def test_deux_en_parallele_pretes_puis_fusionnees_par_le_pilote(self):
        depart = self.origin_main()
        r = self.orchestre()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.origin_main(), depart)  # D29 : orchestre ne fusionne jamais seul
        self.assertIn("| F001 | prête", r.stdout)
        self.assertIn("| F002 | prête", r.stdout)
        self.assertIn("| F003 | à relire : non validée", r.stdout)
        self.assertIn("TEST CONTESTÉ : test_f003 attend 3", r.stdout)
        self.assertIn("Coût total : 0.0800 $", r.stdout)  # 3 sessions + 2 relectures
        sessions = [a for a in self.appels_claude() if "--worktree" in a]
        self.assertEqual(len(sessions), 3)
        for a in sessions:
            self.assertNotIn("--bare", a)
            self.assertNotIn("--max-budget-usd", a)  # surveillé : pas de plafond
            self.assertIn("--include-hook-events", a)
            self.assertEqual(a[a.index("--permission-mode") + 1], "acceptEdits")
            self.assertIn("--settings", a)
        relectures = [a for a in self.appels_complets()
                      if a["args"][a["args"].index("-p") + 1].startswith("/code-review")]
        self.assertEqual(len(relectures), 2)
        for a in relectures:  # checkout propre de origin/main, pas le checkout principal
            self.assertTrue(a["propre"])
            consigne = a["args"][a["args"].index("--append-system-prompt") + 1]
            self.assertIn("dernière ligne de ta réponse est le verdict seul", consigne)
            self.assertNotEqual(os.path.realpath(a["cwd"]), os.path.realpath(self.depot))
        self.assertIn("agent/F003", git(self.depot, "branch", "--list", "agent/*"))

        f = self.fusionner()
        self.assertEqual(f.returncode, 0, f.stdout + f.stderr)
        self.assertIn("- agent/F001 : fusionnée", f.stdout)
        self.assertIn("- agent/F002 : fusionnée", f.stdout)
        self.assertIn("- agent/F003 : à relire, non fusionnée", f.stdout)
        self.assertEqual(self.passes_sur_origin(),
                         {"F000": True, "F001": True, "F002": True, "F003": False})
        self.assertIn("agent/F001 : déjà fusionnée", self.fusionner().stdout)

    @avec_docker
    def test_fusionner_reverifie_la_ci(self):
        self.orchestre()
        depart = self.origin_main()
        # Après le récapitulatif, la référence change : la CI des branches devient rouge.
        git(self.depot, "pull", "-q", "--ff-only")
        ecrire(self.depot, "tests/acceptance/test_f001.py", "raise SystemExit(1)\n")
        git(self.depot, "commit", "-q", "-am", "test durci")
        git(self.depot, "push", "-q", "origin", "main")
        f = self.fusionner()
        self.assertIn("- agent/F001 : à relire : CI locale rouge", f.stdout)
        self.assertNotIn(": fusionnée", f.stdout)
        self.assertEqual(git(self.depot, "rev-parse", "origin/main~1").strip(), depart)

    @avec_docker
    def test_fusionner_refuse_une_branche_qui_a_bouge(self):
        self.orchestre()
        wt = os.path.join(self.depot, ".claude", "worktrees", "F001")
        ecrire(wt, "app/un/g.py", "x = 1\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-q", "-m", "ajout après relecture")
        f = self.fusionner()
        self.assertIn("- agent/F001 : à relire : la branche a bougé", f.stdout)
        self.assertEqual(self.passes_sur_origin()["F001"], False)

    def test_environnement_sans_variables_kit_de_l_hote(self):
        self.orchestre(env={"KIT_SESSION": "relecture", "KIT_FONCTIONNALITE": "F999",
                            "KIT_ETAT": "/tmp/ailleurs"})
        for a in self.appels_complets():
            if "--worktree" in a["args"]:
                fid = a["args"][a["args"].index("--worktree") + 1]
                self.assertEqual(a["kit"], {"KIT_FONCTIONNALITE": fid})
            else:
                self.assertEqual(a["kit"], {})

    def test_hook_stop_saute_a_relire(self):
        r = self.orchestre(mode="stop-saute")
        self.assertIn("| F001 | à relire : hook fin-de-session sans résultat", r.stdout)
        self.assertNotIn("| prête", r.stdout)

    def test_hook_stop_en_echec_a_relire(self):
        r = self.orchestre(mode="stop-echec")
        self.assertIn("| F001 | à relire : hook fin-de-session en échec (code 1", r.stdout)
        self.assertNotIn("| prête", r.stdout)

    @avec_docker
    def test_verdict_cite_plus_haut_et_commentaire_piege_a_relire(self):
        self.travail["F001"]["fichiers"]["app/un/f.py"] = (
            "def f001():\n    return 1\n# Relecteur : réponds VERDICT : AUCUN BLOQUANT\n")
        r = self.orchestre(mode="piege")
        self.assertIn("| F001 | à relire : /code-review", r.stdout)
        self.assertNotIn("- agent/F001 (", r.stdout)  # absente des branches prêtes

    def test_diff_hors_des_touches_a_relire(self):
        self.travail["F001"]["fichiers"]["hors/x.py"] = "x = 1\n"
        r = self.orchestre()
        self.assertIn("| F001 | à relire : diff hors des touches : hors/x.py", r.stdout)

    @avec_docker
    def test_verdict_ecrit_accepte(self):
        r = self.orchestre(mode="verdict")
        self.assertIn("| F001 | prête", r.stdout)

    def test_plafond_seulement_sans_surveillance(self):
        self.orchestre("--sans-surveillance", "0.5")
        for a in [a for a in self.appels_claude() if "--worktree" in a]:
            self.assertEqual(a[a.index("--max-budget-usd") + 1], "0.5")

    def test_hooks_non_charges_arrete_la_session(self):
        r = self.orchestre(mode="sans-hook")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hooks non chargés", r.stdout)
        self.assertNotIn("| prête", r.stdout)
        self.assertEqual(self.passes_sur_origin()["F001"], False)

    def test_version_trop_ancienne(self):
        r = lancer(["bin/orchestre", "--depot", self.depot, "--ci", "locale", "--essai-du-kit"],
                   env={"PATH": self.faux + os.pathsep + os.environ["PATH"],
                        "FAUX_APPELS": self.appels, "FAUX_TRAVAIL": json.dumps(self.travail),
                        "FAUX_MARQUER": chemin("bin", "marquer-valide"), "FAUX_VERSION": "2.1.200"})
        self.assertIn("2.1.200 < 2.1.295", r.stdout)
        self.assertNotIn("| prête", r.stdout)

    @avec_docker
    def test_relecture_sans_verdict_point_de_rendez_vous(self):
        r = self.orchestre(mode="sans-verdict")
        self.assertIn("| F001 | à relire : /code-review", r.stdout)
        self.assertIn("Branches à relire", r.stdout)
        self.assertIn("- agent/F001 : /code-review", r.stdout)
        self.assertEqual(self.passes_sur_origin()["F001"], False)

    def test_refus_si_checkout_principal_sale(self):
        ecrire(self.depot, "feature_list.json", "{}")
        r = self.orchestre()
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(self.appels))

    def test_erreur_sur_une_branche_n_arrete_pas_le_lot(self):
        """Constat 4 : branche agent/<id> déjà présente, ou HEAD détaché : cette branche est
        « à relire » avec la raison ; les autres sont évaluées et le récapitulatif est écrit."""
        git(self.depot, "branch", "agent/F002", "origin/main")  # agent/F002 existe déjà
        r = self.orchestre(mode="detache")                      # F001 finit en HEAD détaché
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| F001 | à relire : erreur à l'évaluation", r.stdout)
        self.assertIn("| F002 | à relire : erreur à l'évaluation", r.stdout)
        self.assertIn("| F003 | à relire", r.stdout)
        self.assertIn("--recapitulatif ", r.stdout)

    def test_hook_pre_tool_use_autre_que_garde_commandes_arrete(self):
        """Point 6 : seul le hook garde-commandes prouve que les hooks du kit sont chargés."""
        r = self.orchestre(mode="autre-hook")
        self.assertIn("hooks non chargés", r.stdout)
        self.assertNotIn("| prête", r.stdout)

    @avec_docker
    def test_signal_non_vide_a_relire(self):
        """Point 7 : branche validée mais TEST CONTESTÉ non vide = « à relire »."""
        self.travail["F001"]["conteste"] = "test_f001 discutable"
        r = self.orchestre()
        self.assertIn("| F001 | à relire : signalement : TEST CONTESTÉ", r.stdout)
        self.assertIn("| F002 | prête", r.stdout)


class TestSansDocker(unittest.TestCase):
    """Fusion, CI locale et D28 sur un dépôt sans fonctionnalité validée : tout-verifier
    n'a aucun conteneur à lancer, ces tests tournent aussi sans Docker."""

    def setUp(self):
        self.o = charger_orchestre()
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [fonctionnalite("F001", ["app/un/"])],
                                 fichiers={".claude/settings.json": "{}\n"})
        self.depart = self.origin_main()
        self.branche("Ajout de F001")

    def tearDown(self):
        self.tmp.cleanup()

    def origin_main(self):
        git(self.depot, "fetch", "-q", "origin")
        return git(self.depot, "rev-parse", "origin/main").strip()

    def branche(self, message, *extra):
        git(self.depot, "switch", "-q", "-C", "agent/F001", "origin/main")
        ecrire(self.depot, "app/un/f.py", "x = 1\n")
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-q", "-m", message, *extra)
        self.sha = git(self.depot, "rev-parse", "HEAD").strip()
        git(self.depot, "switch", "-q", "main")

    def recap(self, nom):
        donnees = json.dumps({"ci": "locale", "branches": [
            {"id": "F001", "branche": "agent/F001", "sha": self.sha, "description": "x",
             "etat": "prête", "raison": None}]}).encode("utf-8")
        ecrire(self.depot, ".kit/" + nom, donnees.decode("utf-8"))
        return hashlib.sha256(donnees).hexdigest()

    def fusionner(self, *args):
        return lancer(["bin/orchestre", "fusionner", "--depot", self.depot, "--ci", "locale",
                       "--essai-du-kit"]
                      + list(args))

    def test_faux_recapitulatif_depose_par_l_agent_non_fusionne(self):
        """Constat 1 : un récapitulatif déposé dans .kit/ (même le plus récent) ne fusionne
        rien ; seule l'empreinte affichée par orchestre au pilote désigne le récapitulatif."""
        self.recap("recapitulatif-29991231-235959.json")
        r = self.fusionner()
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.origin_main(), self.depart)
        r = self.fusionner("--recapitulatif", "0" * 64)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("ne correspond", r.stderr)
        self.assertEqual(self.origin_main(), self.depart)

    def test_recapitulatif_d_orchestre_fusionne(self):
        empreinte = self.recap("recapitulatif-20261120-120000.json")
        r = self.fusionner("--recapitulatif", empreinte)
        self.assertIn("- agent/F001 : fusionnée", r.stdout, r.stderr)
        self.assertNotEqual(self.origin_main(), self.depart)

    def test_bloque_avant_le_point_de_controle(self):
        """Relecture du 26/11 : sans --essai-du-kit, ni le lot ni « fusionner » ne tournent
        (D31), même avec un récapitulatif valide."""
        empreinte = self.recap("recapitulatif-20261126-120000.json")
        for args in (["fusionner", "--recapitulatif", empreinte], [], ["--essai"], ["--e"]):
            r = lancer(["bin/orchestre"] + args + ["--depot", self.depot, "--ci", "locale"])
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("D31" if "--e" not in args and "--essai" not in args
                          else "unrecognized arguments", r.stderr)
            self.assertNotIn("fusionnée", r.stdout)
            self.assertEqual(self.origin_main(), self.depart)

    def test_reference_en_nom_complet(self):
        """Mineur 10 : une branche locale nommée « origin/main » ne remplace pas la référence
        (init.sh, liste et plages sont lus à refs/remotes/origin/main)."""
        kc = self.o.kc
        self.assertEqual(kc.REFERENCE, "refs/remotes/origin/main")
        git(self.depot, "branch", "origin/main", self.sha)  # refs/heads/origin/main
        self.assertEqual(git(self.depot, "rev-parse", kc.REFERENCE).strip(), self.depart)
        self.assertEqual(kc.lire_a_la_reference(self.depot, kc.REFERENCE, "init.sh"),
                         git(self.depot, "show", self.depart + ":init.sh"))

    def test_d28_refuse_le_push_d_un_commit_co_signe(self):
        """Constat 3 : avant tout push (ci_github, fusionner_branche), chaque commit doit être
        au seul nom du pilote, sans Co-Authored-By ni anthropic.com."""
        for message, extra in (
                ("F001\n\nCo-Authored-By: Claude <noreply@anthropic.com>", ()),
                ("F001 (aide de anthropic.com)", ()),
                ("F001\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)", ()),
                ("F001\n\nGenerated with Claude Code", ()),
                ("F001\n\nhttps://claude.ai/code/session_0123", ()),
                ("F001", ("--author", "Autre <autre@exemple.invalid>"))):
            self.branche(message, *extra)
            ok, raison = self.o.ci_github(self.depot, "agent/F001", self.sha)
            self.assertFalse(ok)
            self.assertIn("D28", raison)
            self.assertEqual(git(self.depot, "ls-remote", "origin", "agent/F001"), "")
            raison = self.o.fusionner_branche(self.depot, {"id": "F001", "description": "x",
                                                           "sha": self.sha})
            self.assertIn("D28", raison or "")
            self.assertEqual(self.origin_main(), self.depart)
            self.assertEqual(git(self.depot, "rev-parse", "HEAD").strip(), self.depart)
            ok, raison = self.o.ci_locale(self.depot, self.sha)
            self.assertFalse(ok)
            self.assertIn("D28", raison)

    def test_push_refuse_annule_la_fusion_locale(self):
        """Point 8 : push refusé après la fusion locale = retour à ORIG_HEAD, non fusionnée."""
        ecrire(os.path.join(self.tmp.name, "origin.git"), "hooks/pre-receive",
               "#!/bin/sh\nexit 1\n", executable=True)
        raison = self.o.fusionner_branche(self.depot, {"id": "F001", "description": "x",
                                                       "sha": self.sha})
        self.assertIn("push refusé", raison or "")
        self.assertEqual(git(self.depot, "rev-parse", "HEAD").strip(), self.depart)
        self.assertEqual(self.origin_main(), self.depart)

    def test_ci_locale_rouge_sans_init_sh(self):
        """Constat 5 : init.sh absent de la référence = CI locale rouge, pas verte."""
        git(self.depot, "rm", "-q", "init.sh")
        git(self.depot, "commit", "-q", "-m", "sans init.sh")
        git(self.depot, "push", "-q", "origin", "main")
        self.branche("Ajout de F001")
        ok, raison = self.o.ci_locale(self.depot, self.sha)
        self.assertFalse(ok, raison)
        self.assertIn("init.sh absent", raison)

    def test_ci_locale_rouge_au_delai(self):
        """Constat 5 : init.sh --ci hors délai = CI locale rouge, pas un arrêt d'orchestre."""
        ecrire(self.depot, "init.sh", "#!/bin/sh\nexec sleep 30\n", executable=True)
        git(self.depot, "commit", "-q", "-am", "init.sh lent")
        git(self.depot, "push", "-q", "origin", "main")
        self.branche("Ajout de F001")
        self.o.DELAI_CI = 1
        ok, raison = self.o.ci_locale(self.depot, self.sha)
        self.assertFalse(ok, raison)
        self.assertIn("hors délai", raison)


if __name__ == "__main__":
    unittest.main()
