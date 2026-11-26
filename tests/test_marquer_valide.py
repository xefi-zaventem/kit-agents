"""Tests de marquer-valide (Docker obligatoire : le test tourne dans un conteneur jetable)."""
import json
import os
import tempfile
import unittest

from outils import (avec_docker, creer_depot, ecrire, fonctionnalite, git, lancer, lire,
                    test_qui_importe)

MARQUER = "bin/marquer-valide"

CODE_PIRATE = '''def f004():
    for cible in ("feature_list.json", "tests/acceptance/test_f004.py"):
        try:
            with open(cible, "w") as f:
                f.write("pirate")
        except OSError:
            pass
    return 4
'''


class TestMarquerValide(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [
            fonctionnalite("F001", ["app/"]),
            fonctionnalite("F002", ["app/"]),
            fonctionnalite("F003", ["app/"], depends_on=["F002"]),
            fonctionnalite("F004", ["app/"]),
            fonctionnalite("F005", ["app/"]),
        ], tests={
            "tests/acceptance/test_f001.py": test_qui_importe("f001", "f001", 1),
            "tests/acceptance/test_f002.py": test_qui_importe("f002", "f002", 2),
            "tests/acceptance/test_f003.py": test_qui_importe("f003", "f003", 3),
            "tests/acceptance/test_f004.py": test_qui_importe("f004", "f004", 4),
            "tests/acceptance/test_f005.py": test_qui_importe("f005", "f005", 5),
        }, fichiers={"app/__init__.py": ""})
        git(self.depot, "switch", "-q", "-c", "agent/essai")
        self.liste_depart = lire(self.depot, "feature_list.json")

    def tearDown(self):
        self.tmp.cleanup()

    def marquer(self, *args, env=None):
        return lancer([MARQUER] + list(args), cwd=self.depot, env=env)

    def passes(self):
        return {f["id"]: f["passes"] for f in
                json.loads(lire(self.depot, "feature_list.json"))["fonctionnalites"]}

    @avec_docker
    def test_test_vert_ecrit_seulement_passes(self):
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 1\n")
        r = self.marquer("F001")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.passes(), {"F001": True, "F002": False, "F003": False,
                                         "F004": False, "F005": False})
        diff = git(self.depot, "diff", "-U0", "--", "feature_list.json")
        changees = [l for l in diff.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        self.assertEqual(changees, ['-      "passes": false', '+      "passes": true'])
        journal = lire(self.depot, ".kit/journal-validations.log")
        self.assertIn("F001\tvalidee", journal)

    @avec_docker
    def test_test_rouge_n_ecrit_rien(self):
        ecrire(self.depot, "app/f002.py", "def f002():\n    return 3\n")
        r = self.marquer("F002")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NON validée", r.stdout)
        self.assertEqual(lire(self.depot, "feature_list.json"), self.liste_depart)
        self.assertIn("F002\trouge", lire(self.depot, ".kit/journal-validations.log"))

    @avec_docker
    def test_test_modifie_dans_la_copie_de_travail_ignore(self):
        ecrire(self.depot, "app/f002.py", "def f002():\n    return 3\n")
        ecrire(self.depot, "tests/acceptance/test_f002.py", "print('toujours vert')\n")
        ecrire(self.depot, "tests/acceptance/kit.json", json.dumps(
            {"image": "python:3.13-slim", "commande": ["true"]}))
        r = self.marquer("F002")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertFalse(self.passes()["F002"])

    @avec_docker
    def test_code_d_agent_qui_ecrit_pendant_le_test(self):
        ecrire(self.depot, "app/f004.py", CODE_PIRATE)
        r = self.marquer("F004")
        # L'écriture échoue (lecture seule) ; le test passe quand même ici, donc seul
        # marquer-valide écrit, et seulement passes de F004.
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("pirate", lire(self.depot, "feature_list.json"))
        self.assertNotIn("pirate", lire(self.depot, "tests/acceptance/test_f004.py"))
        self.assertTrue(self.passes()["F004"])

    @avec_docker
    def test_code_d_agent_qui_ecrit_sans_se_proteger(self):
        ecrire(self.depot, "app/f005.py",
               "def f005():\n    open('feature_list.json', 'w').write('pirate')\n    return 5\n")
        r = self.marquer("F005")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Read-only file system", r.stdout)
        self.assertEqual(lire(self.depot, "feature_list.json"), self.liste_depart)

    def test_dependances_non_validees(self):
        ecrire(self.depot, "app/f003.py", "def f003():\n    return 3\n")
        r = self.marquer("F003")
        self.assertEqual(r.returncode, 2)
        self.assertIn("F002", r.stderr)

    def test_liste_falsifiee_dans_la_copie_de_travail(self):
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 1\n")
        liste = json.loads(self.liste_depart)
        liste["fonctionnalites"][0]["steps"] = ["rien"]
        ecrire(self.depot, "feature_list.json", json.dumps(liste, indent=2))
        self.assertEqual(self.marquer("F001").returncode, 2)
        liste = json.loads(self.liste_depart)
        liste["fonctionnalites"][1]["passes"] = True  # F002 forcée à la main
        ecrire(self.depot, "feature_list.json", json.dumps(liste, indent=2))
        r = self.marquer("F001")
        self.assertEqual(r.returncode, 2)
        self.assertIn("F002", r.stderr)

    def test_configuration_des_tests_modifiee_refusee(self):
        """Relecture du 26/11 (constat 3) : un conftest.py ou une option de pytest ajoutés par
        l'agent pourraient rendre le test vert sans ses assertions : refus avant le test."""
        exclure = os.path.join(self.depot, ".git", "info", "exclude")
        for relatif, commit in (("conftest.py", False), ("app/conftest.py", False),
                                ("pyproject.toml", True), ("pytest.ini", False),
                                ("tests/pytest.ini", False), (".pytest.ini", False),
                                ("tests/pyproject.toml", True), ("tests/conftest.py", "ignoré"),
                                ("pytest.ini", "ignoré")):
            if commit == "ignoré":  # ignoré par git, mais vu par le conteneur de test
                with open(exclure, "a", encoding="utf-8") as f:
                    f.write(relatif + chr(10))
                commit = False
            ecrire(self.depot, relatif, "# agent\n")
            if commit:
                git(self.depot, "add", relatif)
                git(self.depot, "commit", "-q", "-m", "config")
            r = self.marquer("F001")
            self.assertNotEqual(r.returncode, 0, relatif)
            self.assertIn("configuration des tests", r.stderr, relatif)
            self.assertIn(relatif, r.stderr)
            self.assertFalse(self.passes()["F001"])
            git(self.depot, "reset", "-q", "--hard", "main")
            git(self.depot, "clean", "-q", "-fdx")

    def test_configuration_ignoree_hors_des_dossiers_du_test_admise(self):
        """Non-régression : un conftest.py livré par un paquet dans un dossier ignoré (.venv/)
        n'est pas lu pour tests/acceptance/ et ne fait pas refuser marquer-valide."""
        ecrire(self.depot, ".git/info/exclude", ".venv/" + chr(10))
        ecrire(self.depot, ".venv/lib/paquet/conftest.py", "# paquet\n")
        ecrire(self.depot, ".venv/lib/paquet/pyproject.toml", "# paquet\n")
        r = self.marquer("F001")
        self.assertNotIn("configuration des tests", r.stderr)

    def test_reference_autre_que_origin_main_refusee(self):
        """Constat 2 : la référence reste origin/main (D25) ; une valeur en « - » n'est
        jamais passée à git comme option."""
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 1\n")
        sortie = os.path.join(self.tmp.name, "ecrit-par-git")
        for reference in ("HEAD", "agent/essai", "main", "--output=" + sortie, "-h"):
            r = self.marquer("F001", "--reference", reference)
            self.assertEqual(r.returncode, 2, reference)
            self.assertIn("référence refusée", r.stderr, reference)
        self.assertFalse(os.path.exists(sortie + ":feature_list.json"))
        self.assertEqual(lire(self.depot, "feature_list.json"), self.liste_depart)
        r = self.marquer("F001", "--reference", "origin/main", env={"PATH": "/nulle-part"})
        self.assertNotIn("référence refusée", r.stderr)  # origin/main reste admise

    def test_echoue_ferme(self):
        self.assertEqual(self.marquer().returncode, 2)
        self.assertEqual(self.marquer("F9").returncode, 2)
        self.assertEqual(self.marquer("F999").returncode, 2)
        self.assertEqual(self.marquer("F001", "--reference", "inexistante").returncode, 2)
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 1\n")
        r = self.marquer("F001", env={"PATH": "/nulle-part"})  # pas de Docker
        self.assertEqual(r.returncode, 2)
        self.assertEqual(lire(self.depot, "feature_list.json"), self.liste_depart)

    @avec_docker
    def test_deux_validations_paralleles_fusionnent_sans_conflit(self):
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 1\n")
        self.assertEqual(self.marquer("F001").returncode, 0)
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-q", "-m", "F001")
        git(self.depot, "switch", "-q", "-c", "agent/autre", "origin/main")
        ecrire(self.depot, "app/f004.py", "def f004():\n    return 4\n")
        self.assertEqual(self.marquer("F004").returncode, 0)
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-q", "-m", "F004")
        git(self.depot, "switch", "-q", "main")
        git(self.depot, "merge", "-q", "--no-ff", "-m", "F001", "agent/essai")
        git(self.depot, "merge", "-q", "--no-ff", "-m", "F004", "agent/autre")
        p = self.passes()
        self.assertTrue(p["F001"] and p["F004"])


if __name__ == "__main__":
    unittest.main()
