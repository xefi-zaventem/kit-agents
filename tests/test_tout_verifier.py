"""Tests de tout-verifier (Docker obligatoire)."""
import json
import os
import tempfile
import unittest

from outils import avec_docker, creer_depot, ecrire, fonctionnalite, lancer, lire, test_qui_importe

SCRIPT = "bin/tout-verifier"


class TestToutVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [
            fonctionnalite("F001", ["app/"], passes=True),
            fonctionnalite("F002", ["app/"])],
            tests={"tests/acceptance/test_f001.py": test_qui_importe("f001", "f001", 1),
                   "tests/acceptance/test_f002.py": test_qui_importe("f002", "f002", 2)},
            fichiers={"app/__init__.py": "", "app/f001.py": "def f001():\n    return 1\n"})

    def tearDown(self):
        self.tmp.cleanup()

    def verifier(self):
        return lancer([SCRIPT], cwd=self.depot)

    @avec_docker
    def test_valide_et_vert(self):
        r = self.verifier()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 test(s) d'acceptation verts", r.stdout)

    @avec_docker
    def test_regression_sur_une_fonctionnalite_validee(self):
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 0\n")
        r = self.verifier()
        self.assertEqual(r.returncode, 1)
        self.assertIn("ÉCHEC F001", r.stdout)

    @avec_docker
    def test_passes_force_sans_code(self):
        liste = json.loads(lire(self.depot, "feature_list.json"))
        liste["fonctionnalites"][1]["passes"] = True  # F002 forcée, pas de code
        ecrire(self.depot, "feature_list.json", json.dumps(liste, indent=2))
        self.assertEqual(self.verifier().returncode, 1)

    def test_test_absent(self):
        os.remove(os.path.join(self.depot, "tests/acceptance/test_f001.py"))
        self.assertEqual(self.verifier().returncode, 1)

    def test_rien_de_valide(self):
        liste = json.loads(lire(self.depot, "feature_list.json"))
        liste["fonctionnalites"][0]["passes"] = False
        ecrire(self.depot, "feature_list.json", json.dumps(liste, indent=2))
        self.assertEqual(self.verifier().returncode, 0)

    def test_echoue_ferme(self):
        self.assertEqual(lancer([SCRIPT, "x"], cwd=self.depot).returncode, 2)
        liste = json.loads(lire(self.depot, "feature_list.json"))
        liste["fonctionnalites"][0]["category"] = "inconnue"
        ecrire(self.depot, "feature_list.json", json.dumps(liste))
        self.assertEqual(self.verifier().returncode, 2)
        liste["fonctionnalites"][0]["category"] = "fonctionnel"
        ecrire(self.depot, "feature_list.json", json.dumps(liste))
        os.remove(os.path.join(self.depot, "tests/acceptance/kit.json"))
        self.assertEqual(self.verifier().returncode, 2)


if __name__ == "__main__":
    unittest.main()
