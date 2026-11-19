"""Tests de controles-rapides (appelle « init.sh --controles <fichier> »)."""
import os
import tempfile
import unittest

from outils import INIT_SH, ecrire, git, lancer

HOOK = "hooks/controles-rapides"


class TestControlesRapides(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = os.path.join(self.tmp.name, "depot")
        git(self.tmp.name, "init", "-q", "-b", "main", self.depot)
        ecrire(self.depot, "init.sh", INIT_SH, executable=True)

    def tearDown(self):
        self.tmp.cleanup()

    def code(self, chemin, cwd=None, brut=None):
        donnees = {"tool_name": "Write", "tool_input": {"file_path": chemin},
                   "cwd": cwd or self.depot}
        return lancer([HOOK], entree=brut if brut is not None else donnees)

    def test_fichier_correct(self):
        ecrire(self.depot, "app/bon.py", "x = 1\n")
        self.assertEqual(self.code(os.path.join(self.depot, "app/bon.py")).returncode, 0)

    def test_echec_renvoye_a_l_agent(self):
        ecrire(self.depot, "app/mauvais.py", "x = 1  # MAUVAIS\n")
        r = self.code(os.path.join(self.depot, "app/mauvais.py"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("init.sh --controles", r.stderr)

    def test_chemin_relatif_resolu_depuis_cwd(self):
        ecrire(self.depot, "app/mauvais.py", "MAUVAIS\n")
        self.assertEqual(self.code("app/mauvais.py").returncode, 2)

    def test_fichier_hors_du_depot_ignore(self):
        ecrire(self.tmp.name, "dehors.py", "MAUVAIS\n")
        self.assertEqual(self.code(os.path.join(self.tmp.name, "dehors.py")).returncode, 0)

    def test_init_absent_echoue_ferme(self):
        os.remove(os.path.join(self.depot, "init.sh"))
        ecrire(self.depot, "app/bon.py", "x = 1\n")
        r = self.code(os.path.join(self.depot, "app/bon.py"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("init.sh absent", r.stderr)

    def test_echoue_ferme(self):
        self.assertEqual(self.code("", brut="pas du json").returncode, 2)
        self.assertEqual(self.code("").returncode, 2)  # chemin absent
        self.assertEqual(self.code("x.py", cwd=self.tmp.name).returncode, 2)  # pas de dépôt

    def test_le_hook_plante(self):
        r = lancer([HOOK], entree={"tool_name": "Write", "tool_input": ["x"], "cwd": self.depot})
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
