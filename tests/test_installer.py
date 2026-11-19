"""Tests de l'installateur, dans un dossier temporaire (sans droit administrateur)."""
import json
import os
import stat
import tempfile
import unittest

from outils import chemin, git, lancer, lire

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


if __name__ == "__main__":
    unittest.main()
