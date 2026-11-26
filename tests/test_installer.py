"""Tests de l'installateur, dans un dossier temporaire (sans droit administrateur)."""
import json
import os
import stat
import subprocess
import tempfile
import unittest

from outils import KIT, chemin, creer_depot, ecrire, fonctionnalite, git, lancer, lire

SCRIPT = "bin/installer"


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = os.path.join(self.tmp.name, "depot")
        git(self.tmp.name, "init", "-q", "-b", "main", self.depot)
        self.dest = os.path.join(self.tmp.name, "kit")
        self.regles = os.path.join(self.tmp.name, "regles.json")
        with open(self.regles, "w", encoding="utf-8") as f:
            json.dump({"commandes": []}, f)

    def tearDown(self):
        for racine, dossiers, _ in os.walk(self.tmp.name):
            for d in dossiers:
                os.chmod(os.path.join(racine, d), 0o755)
        self.tmp.cleanup()

    def installer(self, *extra, dest=None, regles=None):
        return lancer([SCRIPT, "--depot", self.depot, "--regles", regles or self.regles,
                       "--organisation", "org-essai", "--destination", dest or self.dest] + list(extra))

    def test_installation(self):
        r = self.installer()
        self.assertEqual(r.returncode, 0, r.stderr)
        for relatif in ["hooks/garde-commandes", "hooks/garde-secrets", "hooks/controles-rapides",
                        "hooks/fin-de-session", "hooks/verrou-ressources", "bin/marquer-valide",
                        "bin/orchestre", "bin/tout-verifier", "bin/verifier-diff-liste",
                        "bin/kit_commun.py", "modeles/prompts/agent-de-code.md"]:
            p = os.path.join(self.dest, relatif)
            self.assertTrue(os.path.isfile(p), relatif)
            self.assertFalse(os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH),
                             relatif + " doit être en lecture seule")
        self.assertTrue(os.access(os.path.join(self.dest, "bin/marquer-valide"), os.X_OK))
        self.assertFalse(os.stat(os.path.join(self.dest, "hooks")).st_mode & stat.S_IWUSR)

        texte = lire(self.depot, ".claude/settings.json")
        self.assertNotIn("/opt/kit", texte)
        self.assertNotIn("/etc/kit", texte)
        reglages = json.loads(texte)
        self.assertEqual(reglages["attribution"], {"commit": "", "pr": "", "sessionUrl": False})
        self.assertIn("Edit(feature_list.json)", reglages["permissions"]["deny"])
        self.assertIn("Edit(tests/acceptance/**)", reglages["permissions"]["deny"])
        self.assertTrue(reglages["sandbox"]["enabled"] and reglages["sandbox"]["failIfUnavailable"])
        self.assertEqual(reglages["sandbox"]["excludedCommands"],
                         [os.path.join(os.path.realpath(self.dest), "bin/marquer-valide") + " *"])
        commandes = []
        for evenement, groupes in reglages["hooks"].items():
            for g in groupes:
                for h in g["hooks"]:
                    commandes.append(h["command"])
                    self.assertTrue(os.access(h["command"].split()[0], os.X_OK), h["command"])
                    if evenement != "Stop":  # onFailure n'a pas d'effet sur Stop (doc)
                        self.assertEqual(h.get("onFailure"), "block", h["command"])
        self.assertIn(os.path.realpath(self.regles), " ".join(commandes))

        self.assertEqual(lire(self.depot, ".kit-version").strip(), "v1.0")
        ci = lire(self.depot, ".github/workflows/tests.yml")
        self.assertIn('repository: "org-essai/kit-agents", ref: "v1.0"', ci)
        self.assertNotIn("<", ci)
        self.assertIn(".kit/", lire(self.depot, ".gitignore").splitlines())
        self.assertIn("claude-progress.txt merge=union", lire(self.depot, ".gitattributes"))

    def test_reinstallation(self):
        self.assertEqual(self.installer().returncode, 0)
        r = self.installer("--version", "v1.1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(lire(self.depot, ".kit-version").strip(), "v1.1")
        self.assertEqual(lire(self.depot, ".gitignore").count(".kit/"), 1)

    def test_echoue_ferme(self):
        r = self.installer(dest=os.path.join(self.depot, "kit"))
        self.assertEqual(r.returncode, 2)  # destination dans le dépôt
        r = self.installer(regles=os.path.join(self.tmp.name, "absentes.json"))
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.depot, ".claude")))
        self.assertFalse(os.path.exists(self.dest))
        r = lancer([SCRIPT, "--depot", self.tmp.name, "--regles", self.regles,
                    "--organisation", "o", "--destination", self.dest])
        self.assertEqual(r.returncode, 2)  # pas un dépôt git
        self.assertNotEqual(lancer([SCRIPT]).returncode, 0)

    def test_modele_de_reglages_du_kit(self):
        reglages = json.loads(lire(chemin("modeles"), "settings-produit.json"))
        self.assertEqual(reglages["permissions"]["disableBypassPermissionsMode"], "disable")
        self.assertFalse(reglages["sandbox"]["allowUnsandboxedCommands"])

    def test_init_sh_et_reglages_proteges(self):
        reglages = json.loads(lire(chemin("modeles"), "settings-produit.json"))
        deny = reglages["permissions"]["deny"]
        for regle in ("Edit(init.sh)", "Edit(.claude/**)", "Edit(~/.claude/**)"):
            self.assertIn(regle, deny)
        self.assertFalse([r for r in deny if r.startswith("Write(")])  # sans effet (doc)
        for chemin_protege in ("init.sh", ".claude", "~/.claude"):
            self.assertIn(chemin_protege, reglages["sandbox"]["filesystem"]["denyWrite"])

    def etape_ci(self, ci, nom):
        """Corps du « run: | » de l'étape <nom> du modèle de CI (sans dépendre de PyYAML)."""
        lignes = ci.splitlines()
        debut = next(i for i, l in enumerate(lignes) if nom in l) + 2
        corps = []
        for l in lignes[debut:]:
            if not l.startswith(" " * 10):
                break
            corps.append(l[10:])
        return "\n".join(corps) + "\n"

    def test_ci_rouge_si_init_sh_differe_de_la_reference(self):
        self.assertEqual(self.installer().returncode, 0)
        script = self.etape_ci(lire(self.depot, ".github/workflows/tests.yml"),
                               "Tests d'acceptation")
        projet = os.path.join(self.tmp.name, "projet-ci")
        os.makedirs(projet)
        depot = creer_depot(projet, [fonctionnalite("F001", ["app/"])])
        os.symlink(KIT, os.path.join(depot, "kit"))
        env = dict(os.environ, GITHUB_REF="refs/heads/agent/F001", TETE="HEAD",
                   PILOTE_NOM="essai", PILOTE_COURRIEL="essai@exemple.invalid")
        ci = lambda: subprocess.run(["bash", "-e", "-c", script], cwd=depot, env=env,
                                    capture_output=True, text=True)
        self.assertEqual(ci().returncode, 0, ci().stderr)
        ecrire(depot, "init.sh", "#!/bin/sh\nexit 0\n", executable=True)
        self.assertNotEqual(ci().returncode, 0)

    def projet_ci(self, ref="refs/heads/agent/F001", nom="projet-ci"):
        """Étape « Tests d'acceptation… D28 » du modèle installé, sur un projet d'essai."""
        if not os.path.exists(os.path.join(self.depot, ".github/workflows/tests.yml")):
            self.assertEqual(self.installer().returncode, 0)
        script = self.etape_ci(lire(self.depot, ".github/workflows/tests.yml"),
                               "Tests d'acceptation")
        projet = os.path.join(self.tmp.name, nom)
        os.makedirs(projet)
        depot = creer_depot(projet, [fonctionnalite("F001", ["app/"])])
        os.symlink(KIT, os.path.join(depot, "kit"))
        nom, courriel = git(depot, "var", "GIT_AUTHOR_IDENT").rsplit(">", 1)[0].split(" <")
        env = dict(os.environ, GITHUB_REF=ref, TETE="HEAD", PILOTE_NOM=nom,
                   PILOTE_COURRIEL=courriel)
        ci = lambda: subprocess.run(["bash", "-e", "-c", script], cwd=depot, env=env,
                                    capture_output=True, text=True)
        return depot, ci, env

    def test_ci_etiquette_origin_main_ne_trompe_pas(self):
        """Relecture du 26/11 (constat 1) : une étiquette « origin/main » posée par l'agent sur
        son commit ne remplace pas la référence (nom complet refs/remotes/origin/main)."""
        depot, ci, _ = self.projet_ci()
        ecrire(depot, "tests/acceptance/test_f001.py", "pass  # truqué\n")
        git(depot, "add", "tests")
        git(depot, "commit", "-q", "-m", "a")
        git(depot, "tag", "origin/main")
        r = ci()
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ci_rouge_si_github_ou_configuration_des_tests_changent(self):
        """Relecture du 26/11 (constats 2 et 3) : sur une branche, .github/ et la configuration
        du lanceur de tests ne changent pas, commités ou non."""
        depot, ci, _ = self.projet_ci()
        self.assertEqual(ci().returncode, 0, ci().stdout + ci().stderr)
        for relatif, commit in ((".github/workflows/tests.yml", True), ("conftest.py", False),
                                ("app/conftest.py", True), ("pyproject.toml", True)):
            ecrire(depot, relatif, "# agent\n")
            if commit:
                git(depot, "add", relatif)
                git(depot, "commit", "-q", "-m", "config")
            self.assertNotEqual(ci().returncode, 0, relatif)
            git(depot, "reset", "-q", "--hard", "refs/remotes/origin/main")
            git(depot, "clean", "-q", "-fd", "-e", "kit")

    def test_ci_de_main_admet_la_fusion_faite_sur_github(self):
        """Relecture du 26/11 (constat 6) : sur main, le commit de fusion de GitHub (auteur =
        pilote, committer « GitHub <noreply@github.com> ») passe D28 ; ailleurs, non."""
        for ref, attendu in (("refs/heads/main", 0), ("refs/heads/agent/F001", 1)):
            depot, ci, env = self.projet_ci(ref, nom="projet-" + ref.split("/")[-1])
            ecrire(depot, "app/a.py", "a = 1\n")
            git(depot, "add", "app")
            subprocess.run(["git", "commit", "-q", "-m", "Fusion (#1)"], cwd=depot, check=True,
                           env=dict(env, GIT_COMMITTER_NAME="GitHub",
                                    GIT_COMMITTER_EMAIL="noreply@github.com"))
            r = ci()
            self.assertEqual(r.returncode != 0, bool(attendu), ref + r.stdout + r.stderr)
            if attendu:
                self.assertIn("D28", r.stdout)

    def test_ci_rouge_si_commit_hors_d28(self):
        """Constat 3 : le modèle de CI refuse un co-auteur, anthropic.com ou un autre auteur."""
        self.assertEqual(self.installer().returncode, 0)
        script = self.etape_ci(lire(self.depot, ".github/workflows/tests.yml"),
                               "Tests d'acceptation")
        projet = os.path.join(self.tmp.name, "projet-ci")
        os.makedirs(projet)
        depot = creer_depot(projet, [fonctionnalite("F001", ["app/"])])
        os.symlink(KIT, os.path.join(depot, "kit"))
        env = dict(os.environ, GITHUB_REF="refs/heads/agent/F001", TETE="HEAD",
                   PILOTE_NOM="essai", PILOTE_COURRIEL="essai@exemple.invalid")
        ci = lambda: subprocess.run(["bash", "-e", "-c", script], cwd=depot, env=env,
                                    capture_output=True, text=True)
        ecrire(depot, "app/a.py", "a = 1\n")
        git(depot, "add", "app")  # pas le lien « kit »
        git(depot, "commit", "-q", "-m", "a")
        self.assertEqual(ci().returncode, 0, ci().stdout + ci().stderr)
        for message, auteur in (("b\n\nCo-Authored-By: Claude <noreply@anthropic.com>", None),
                                ("c (voir anthropic.com)", None),
                                ("e\n\nGenerated with Claude Code", None),
                                ("f\n\nhttps://claude.ai/code/session_0123", None),
                                ("d", "Autre <autre@exemple.invalid>")):
            git(depot, "reset", "-q", "--hard", "origin/main")
            ecrire(depot, "app/b.py", "b = 1\n")
            git(depot, "add", "app")
            git(depot, "commit", "-q", "-m", message, *(["--author", auteur] if auteur else []))
            r = ci()
            self.assertNotEqual(r.returncode, 0, message)
            self.assertIn("D28", r.stdout, message + r.stderr)
        self.assertNotEqual(subprocess.run(
            ["bash", "-e", "-c", script], cwd=depot, capture_output=True, text=True,
            env=dict(env, PILOTE_NOM="")).returncode, 0)  # pilote non configuré = rouge


if __name__ == "__main__":
    unittest.main()
