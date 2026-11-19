"""Tests de garde-secrets. Les faux secrets sont assemblés à l'exécution, pour ne
jamais apparaître en clair dans le dépôt."""
import unittest

from outils import lancer

GARDE = "hooks/garde-secrets"
JETON_GITHUB = "gh" + "p_" + "A1b2C3d4" * 5
CLE_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
CLE_ANTHROPIC = "sk-" + "ant-" + "api03-" + "x7Y8z9" * 6
CLE_PRIVEE = "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk=\n"


def appel(outil, **entree):
    return {"tool_name": outil, "tool_input": entree, "cwd": "/tmp"}


def code(donnees, brut=None):
    return lancer([GARDE], entree=brut if brut is not None else donnees).returncode


class TestGardeSecrets(unittest.TestCase):
    def test_refuse_les_secrets(self):
        cas = [
            appel("Write", file_path="/tmp/id", content=CLE_PRIVEE),
            appel("Bash", command="export AWS_ACCESS_KEY_ID=" + CLE_AWS),
            appel("Edit", file_path="/tmp/a.py", old_string="x", new_string="T = '%s'" % JETON_GITHUB),
            appel("Write", file_path="/tmp/c.env", content="CLE=" + CLE_ANTHROPIC),
            appel("Write", file_path="/tmp/r.py", content='password = "S3cr3t-Valeur-42"\n'),
            appel("Write", file_path="/tmp/c.yml", content="db: postgres://appli:Tr0pFacile@hote/base\n"),
            appel("MultiEdit", file_path="/tmp/m.py", edits=[
                {"old_string": "a", "new_string": "ok"},
                {"old_string": "b", "new_string": "api_key: 'Zq81-reelle-valeur'"}]),
            appel("NotebookEdit", notebook_path="/tmp/n.ipynb", new_source="token = 'Abcdefgh12345678'"),
            appel("Bash", command="git commit -m 'ajout %s'" % JETON_GITHUB),
        ]
        for donnees in cas:
            with self.subTest(donnees=str(donnees)[:80]):
                self.assertEqual(code(donnees), 2)

    def test_laisse_passer_le_reste(self):
        cas = [
            appel("Write", file_path="/tmp/r.py", content="password = os.environ['MOT_DE_PASSE']\n"),
            appel("Write", file_path="/tmp/e.env.exemple", content='password = "<a-remplacer>"\n'),
            appel("Write", file_path="/tmp/e.yml", content='token: "changeme-plus-tard"\n'),
            appel("Write", file_path="/tmp/doc.md", content="Le jeton se lit dans $JETON.\n"),
            appel("Bash", command="ls -la && git status"),
            appel("Edit", file_path="/tmp/a.py", old_string="x", new_string="def f():\n    return 1\n"),
            appel("Read", file_path="/tmp/secrets/cle"),
        ]
        for donnees in cas:
            with self.subTest(donnees=str(donnees)[:80]):
                self.assertEqual(code(donnees), 0)

    def test_echoue_ferme(self):
        self.assertEqual(code(None, brut="pas du json"), 2)
        self.assertEqual(code(None, brut=""), 2)
        self.assertEqual(code(appel("Write", file_path="/tmp/x", content=None)), 2)

    def test_le_hook_plante(self):
        # tool_input inattendu : exception interne, le hook doit refuser
        self.assertEqual(code({"tool_name": "Bash", "tool_input": ["ls"]}), 2)
        self.assertEqual(code({"tool_name": "MultiEdit", "tool_input": {"edits": ["x"]}}), 2)


if __name__ == "__main__":
    unittest.main()
