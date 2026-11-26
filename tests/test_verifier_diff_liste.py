"""Tests de verifier-diff-liste."""
import json
import tempfile
import unittest

from outils import creer_depot, ecrire, fonctionnalite, lancer, lire

SCRIPT = "bin/verifier-diff-liste"


class TestVerifierDiffListe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [fonctionnalite("F001", ["a/"]),
                                                 fonctionnalite("F002", ["b/"])])
        self.liste = json.loads(lire(self.depot, "feature_list.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def avec(self, modifier):
        liste = json.loads(json.dumps(self.liste))
        modifier(liste)
        ecrire(self.depot, "feature_list.json", json.dumps(liste))
        return lancer([SCRIPT, "origin/main", "feature_list.json"], cwd=self.depot)

    def test_seul_passes_change(self):
        self.assertEqual(self.avec(lambda l: None).returncode, 0)
        r = self.avec(lambda l: l["fonctionnalites"][0].update(passes=True))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_autres_changements_refuses(self):
        cas = [
            lambda l: l["fonctionnalites"][0].update(steps=["rien"]),
            lambda l: l["fonctionnalites"][1].update(touches=["a/", "b/"]),
            lambda l: l["fonctionnalites"].pop(),
            lambda l: l["fonctionnalites"].append(dict(l["fonctionnalites"][0], id="F009")),
            lambda l: l.update(projet="autre"),
            lambda l: l["fonctionnalites"].reverse(),
        ]
        for modifier in cas:
            with self.subTest():
                self.assertEqual(self.avec(modifier).returncode, 1)

    def test_echoue_ferme(self):
        self.assertEqual(lancer([SCRIPT], cwd=self.depot).returncode, 2)
        self.assertEqual(lancer([SCRIPT, "inexistante"], cwd=self.depot).returncode, 2)
        ecrire(self.depot, "feature_list.json", "{ cassé")
        self.assertEqual(lancer([SCRIPT, "origin/main"], cwd=self.depot).returncode, 2)


if __name__ == "__main__":
    unittest.main()
