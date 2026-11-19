"""Tests de fin-de-session (hook Stop)."""
import json
import os
import tempfile
import unittest

from outils import creer_depot, ecrire, fonctionnalite, git, lancer, lire

HOOK = "hooks/fin-de-session"
ENTREE_PROGRES = "=== 2026-01-01 10:00 | F001 | session s | modèle m ===\nFAIT : essai\n"


class TestFinDeSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [
            fonctionnalite("F001", ["app/"]), fonctionnalite("F002", ["autre/"])],
            tests={"tests/acceptance/test_f001.py": "print('ok')\n"})
        git(self.depot, "switch", "-q", "-c", "agent/F001")
        self.etat = os.path.join(self.tmp.name, "etat")

    def tearDown(self):
        self.tmp.cleanup()

    def stop(self, session="s1", cwd=None, env=None, brut=None):
        donnees = {"hook_event_name": "Stop", "session_id": session, "cwd": cwd or self.depot,
                   "stop_hook_active": False}
        environnement = {"KIT_ETAT": self.etat, "KIT_FONCTIONNALITE": ""}
        environnement.update(env or {})
        return lancer([HOOK], entree=brut if brut is not None else donnees, env=environnement)

    def travail_correct(self):
        ecrire(self.depot, "app/f001.py", "def f001():\n    return 1\n")
        with open(os.path.join(self.depot, "claude-progress.txt"), "a", encoding="utf-8") as f:
            f.write(ENTREE_PROGRES)

    def test_session_correcte(self):
        self.travail_correct()
        self.assertEqual(self.stop().returncode, 0)
        git(self.depot, "add", "-A")
        git(self.depot, "commit", "-q", "-m", "F001")
        self.assertEqual(self.stop().returncode, 0)  # commité : pareil

    def test_progression_non_mise_a_jour(self):
        ecrire(self.depot, "app/f001.py", "x = 1\n")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("claude-progress.txt", r.stderr)

    def test_tests_acceptance_modifies(self):
        self.travail_correct()
        ecrire(self.depot, "tests/acceptance/test_f001.py", "pass\n")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("tests/acceptance", r.stderr)
        git(self.depot, "checkout", "--", "tests/acceptance/")
        ecrire(self.depot, "tests/acceptance/nouveau.py", "pass\n")  # fichier ajouté
        self.assertEqual(self.stop(session="s2").returncode, 2)

    def test_liste_modifiee_hors_passes(self):
        self.travail_correct()
        chemin = os.path.join(self.depot, "feature_list.json")
        liste = json.loads(lire(self.depot, "feature_list.json"))
        liste["fonctionnalites"][0]["passes"] = True
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(liste, f, indent=2)
        self.assertEqual(self.stop().returncode, 0)  # seul passes a changé
        liste["fonctionnalites"][0]["steps"] = ["plus rien à vérifier"]
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(liste, f, indent=2)
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("hors du champ passes", r.stderr)

    def test_respect_de_touches(self):
        self.travail_correct()
        ecrire(self.depot, "autre/intrus.py", "x = 1\n")
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("hors des touches de F001", r.stderr)
        self.assertIn("autre/intrus.py", r.stderr)

    def test_fonctionnalite_par_variable(self):
        self.travail_correct()
        r = self.stop(env={"KIT_FONCTIONNALITE": "F002"})  # app/ n'est pas dans F002
        self.assertEqual(r.returncode, 2)
        self.assertIn("F002", r.stderr)

    def test_controles_rapides_rouges(self):
        self.travail_correct()
        ecrire(self.depot, "RAPIDE_KO", "")
        git(self.depot, "add", "RAPIDE_KO")  # hors touches aussi, mais on vérifie init.sh
        r = self.stop()
        self.assertEqual(r.returncode, 2)
        self.assertIn("init.sh --rapide", r.stderr)

    def test_au_plus_trois_blocages(self):
        ecrire(self.depot, "app/f001.py", "x = 1\n")  # progression jamais mise à jour
        for n in (1, 2, 3):
            r = self.stop(session="boucle")
            self.assertEqual(r.returncode, 2, "blocage %d" % n)
            self.assertIn("blocage %d sur 3" % n, r.stderr)
        r = self.stop(session="boucle")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ÉCHEC FIN DE SESSION", lire(self.depot, "claude-progress.txt"))
        git(self.depot, "checkout", "--", "claude-progress.txt")
        r = self.stop(session="autre")  # compteur propre à chaque session
        self.assertEqual(r.returncode, 2)
        self.assertIn("blocage 1 sur 3", r.stderr)

    def test_relecture_lancee_par_orchestre(self):
        self.assertEqual(self.stop().returncode, 2)  # rien de fait : bloque
        self.assertEqual(self.stop(env={"KIT_SESSION": "relecture"}).returncode, 0)

    def test_le_hook_plante(self):
        # Pas de dépôt git : erreur interne, la fin est bloquée (code 2).
        r = self.stop(cwd=self.tmp.name)
        self.assertEqual(r.returncode, 2)
        self.assertIn("erreur interne", r.stderr)
        # Erreur pendant les contrôles (référence absente) : bloque et compte.
        git(self.depot, "remote", "remove", "origin")
        self.travail_correct()
        r = self.stop(session="sans-reference")
        self.assertEqual(r.returncode, 2)
        self.assertIn("blocage 1 sur 3", r.stderr)


if __name__ == "__main__":
    unittest.main()
