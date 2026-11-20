"""Tests de verrou-ressources, avec des ressources d'exemple inventées."""
import json
import os
import tempfile
import time
import unittest

from outils import lancer

HOOK = "hooks/verrou-ressources"


def bash(cmd, session):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": session}


class TestVerrouRessources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.verrous = os.path.join(self.tmp.name, "verrous")
        self.regles = self.ecrire_regles(60)

    def tearDown(self):
        self.tmp.cleanup()

    def ecrire_regles(self, minutes, nom="regles.json"):
        chemin = os.path.join(self.tmp.name, nom)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump({"dossier_verrous": self.verrous, "duree_verrou_minutes": minutes,
                       "ressources": [{"nom": "machine-essai", "motif": r"\bmachine-essai\b"},
                                      {"nom": "base-partagee", "motif": r"\bbase-partagee\b"}]}, f)
        return chemin

    def code(self, donnees, regles=None, brut=None, args=None):
        args = args if args is not None else [regles or self.regles]
        return lancer([HOOK] + args, entree=brut if brut is not None else donnees).returncode

    def test_deux_sessions_sur_la_meme_ressource(self):
        self.assertEqual(self.code(bash("ssh machine-essai reboot", "A")), 0)
        self.assertTrue(os.path.exists(os.path.join(self.verrous, "machine-essai.verrou")))
        self.assertEqual(self.code(bash("ssh machine-essai uptime", "B")), 2)
        self.assertEqual(self.code(bash("ssh machine-essai uptime", "A")), 0)
        self.assertEqual(self.code(bash("psql base-partagee", "B")), 0)
        self.assertEqual(self.code(bash("psql base-partagee", "A")), 2)
        self.assertEqual(self.code(bash("ls -la", "B")), 0)

    def test_verrou_expire(self):
        regles = self.ecrire_regles(0.001, "courtes.json")
        self.assertEqual(self.code(bash("ssh machine-essai", "A"), regles), 0)
        time.sleep(0.2)
        self.assertEqual(self.code(bash("ssh machine-essai", "B"), regles), 0)
        time.sleep(0.2)
        self.assertEqual(self.code(bash("ssh machine-essai", "A"), regles), 0)  # expiré pour B aussi

    def test_hors_bash_et_sans_ressource(self):
        self.assertEqual(self.code({"tool_name": "Read", "tool_input": {"file_path": "/x"}}), 0)
        vide = os.path.join(self.tmp.name, "vide.json")
        with open(vide, "w", encoding="utf-8") as f:
            json.dump({}, f)
        self.assertEqual(self.code(bash("ssh machine-essai", "A"), vide), 0)

    def test_echoue_ferme(self):
        self.assertEqual(self.code(None, brut="pas du json"), 2)
        self.assertEqual(self.code(bash("ls", "A"), args=[]), 2)
        self.assertEqual(self.code(bash("ls", "A"), regles="/inexistant.json"), 2)
        self.assertEqual(self.code(bash("ssh machine-essai", None)), 2)  # session inconnue
        sans_dossier = os.path.join(self.tmp.name, "sans-dossier.json")
        with open(sans_dossier, "w", encoding="utf-8") as f:
            json.dump({"ressources": [{"nom": "x", "motif": "x"}]}, f)
        self.assertEqual(self.code(bash("x", "A"), sans_dossier), 2)

    def test_le_hook_plante(self):
        os.makedirs(self.verrous)
        with open(os.path.join(self.verrous, "machine-essai.verrou"), "w") as f:
            f.write("{ cassé")
        self.assertEqual(self.code(bash("ssh machine-essai", "A")), 2)


if __name__ == "__main__":
    unittest.main()
