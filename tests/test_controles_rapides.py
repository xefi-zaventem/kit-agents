"""Tests de controles-rapides (appelle « init.sh --controles <fichier> »)."""
import os
import tempfile
import unittest

from outils import creer_depot, ecrire, git, lancer

HOOK = "hooks/controles-rapides"


class TestControlesRapides(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [])  # init.sh d'essai poussé sur origin/main

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

    def test_init_absent_de_la_reference_echoue_ferme(self):
        git(self.depot, "rm", "-q", "init.sh")
        git(self.depot, "commit", "-q", "-m", "sans init.sh")
        git(self.depot, "push", "-q", "origin", "main")
        ecrire(self.depot, "init.sh", "#!/bin/sh\nexit 0\n", executable=True)  # copie locale
        ecrire(self.depot, "app/bon.py", "x = 1\n")
        r = self.code(os.path.join(self.depot, "app/bon.py"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("init.sh absent de origin/main", r.stderr)

    def test_init_modifie_par_l_agent_non_execute(self):
        ecrire(self.depot, "init.sh", "#!/bin/sh\ntouch EXECUTE_PAR_LE_HOOK\nexit 0\n",
               executable=True)
        ecrire(self.depot, "app/mauvais.py", "MAUVAIS\n")
        r = self.code(os.path.join(self.depot, "app/mauvais.py"))
        self.assertEqual(r.returncode, 2, r.stderr)  # init.sh de la référence : refuse MAUVAIS
        self.assertFalse(os.path.exists(os.path.join(self.depot, "EXECUTE_PAR_LE_HOOK")))

    def test_echoue_ferme(self):
        self.assertEqual(self.code("", brut="pas du json").returncode, 2)
        self.assertEqual(self.code("").returncode, 2)  # chemin absent
        self.assertEqual(self.code("x.py", cwd=self.tmp.name).returncode, 2)  # pas de dépôt

    def test_le_hook_plante(self):
        r = lancer([HOOK], entree={"tool_name": "Write", "tool_input": ["x"], "cwd": self.depot})
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
