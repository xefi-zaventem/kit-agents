"""Tests d'orchestre. Un faux « claude » imite le flux stream-json d'une session
(aucun appel réel, aucun coût) ; marquer-valide et tout-verifier sont les vrais
(Docker obligatoire)."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest

from outils import (chemin, creer_depot, ecrire, fonctionnalite, git, lancer, liste,
                    test_qui_importe)

FAUX_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
mode = os.environ.get("FAUX_MODE", "")
with open(os.environ["FAUX_APPELS"], "a") as f:
    f.write(json.dumps(args) + "\n")
def emettre(e):
    print(json.dumps(e), flush=True)
if prompt.startswith("/code-review"):
    assert os.environ.get("KIT_SESSION") == "relecture"
    if "sans-verdict" in mode:
        texte = "app/un/f.py:1 : un constat"
    elif "verdict" in mode:
        texte = "Rien de bloquant.\nVERDICT : AUCUN BLOQUANT"
    else:
        texte = "(none)"
    print(json.dumps({"type": "result", "result": texte, "total_cost_usd": 0.01}))
    sys.exit(0)
fid = args[args.index("--worktree") + 1]
wt = os.path.join(os.getcwd(), ".claude", "worktrees", fid)
subprocess.run(["git", "worktree", "add", "-q", "-b", "worktree-" + fid, wt, "origin/main"],
               check=True)
emettre({"type": "system", "subtype": "init", "cwd": wt,
         "claude_code_version": os.environ.get("FAUX_VERSION", "2.1.328")})
if "sans-hook" not in mode:
    emettre({"type": "system", "subtype": "hook_started", "hook_event": "PreToolUse"})
emettre({"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}})
travail = json.loads(os.environ["FAUX_TRAVAIL"])[fid]
for relatif, contenu in travail["fichiers"].items():
    p = os.path.join(wt, relatif)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(contenu)
r = subprocess.run([os.environ["FAUX_MARQUER"], fid], cwd=wt, capture_output=True, text=True)
etat = "validée" if r.returncode == 0 else "bloquée"
with open(os.path.join(wt, "claude-progress.txt"), "a") as f:
    f.write("=== essai | %s ===\nÉTAT : %s\nTEST CONTESTÉ : %s\nTROP GROS : non\n"
            % (fid, etat, travail.get("conteste", "aucun")))
subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
subprocess.run(["git", "commit", "-q", "-m", fid], cwd=wt, check=True)
emettre({"type": "system", "subtype": "hook_started", "hook_event": "Stop"})
emettre({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.02})
'''


def charger_orchestre():
    chargeur = importlib.machinery.SourceFileLoader("orchestre", chemin("bin", "orchestre"))
    spec = importlib.util.spec_from_loader("orchestre", chargeur)
    module = importlib.util.module_from_spec(spec)
    chargeur.exec_module(module)
    return module


class TestFormerLot(unittest.TestCase):
    def setUp(self):
        self.o = charger_orchestre()

    def lot(self, fonctions):
        return [f["id"] for f in self.o.former_lot(json.loads(liste(fonctions)))]

    def test_tranche_exemplaire_seule(self):
        self.assertEqual(self.lot([fonctionnalite("F001", ["a/"], priorite=2),
                                   fonctionnalite("F002", ["b/"], priorite=1)]), ["F002"])

    def test_au_plus_trois_et_par_priorite(self):
        fonctions = [fonctionnalite("F000", ["z/"], passes=True)] + [
            fonctionnalite("F00%d" % i, ["d%d/" % i], priorite=10 - i) for i in range(1, 6)]
        self.assertEqual(self.lot(fonctions), ["F005", "F004", "F003"])

    def test_touches_et_dependances(self):
        self.assertEqual(self.lot([
            fonctionnalite("F000", ["z/"], passes=True),
            fonctionnalite("F001", ["app/clients/"], priorite=1),
            fonctionnalite("F002", ["app/"], priorite=2),            # chevauche F001
            fonctionnalite("F003", ["autre/"], depends_on=["F001"]),  # pas prête
            fonctionnalite("F004", ["./ecrans"], priorite=4),
        ]), ["F001", "F004"])

    def test_fichier_partage_seul(self):
        base = [fonctionnalite("F000", ["z/"], passes=True)]
        self.assertEqual(self.lot(base + [fonctionnalite("F001", ["migrations/"], priorite=1),
                                          fonctionnalite("F002", ["b/"], priorite=2)]), ["F001"])
        self.assertEqual(self.lot(base + [fonctionnalite("F001", ["b/"], priorite=1),
                                          fonctionnalite("F002", ["docs/contrats/"], priorite=2),
                                          fonctionnalite("F003", ["CLAUDE.md"], priorite=3),
                                          fonctionnalite("F004", ["c/"], priorite=4)]),
                         ["F001", "F004"])


class TestOrchestre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.depot = creer_depot(self.tmp.name, [
            fonctionnalite("F000", ["base/"], passes=True),
            fonctionnalite("F001", ["app/un/"], priorite=1),
            fonctionnalite("F002", ["app/deux/"], priorite=2),
            fonctionnalite("F003", ["app/trois/"], priorite=3),
        ], tests={
            "tests/acceptance/test_f000.py": "print('ok')\n",
            "tests/acceptance/test_f001.py": test_qui_importe("un.f", "f001", 1),
            "tests/acceptance/test_f002.py": test_qui_importe("deux.f", "f002", 2),
            "tests/acceptance/test_f003.py": test_qui_importe("trois.f", "f003", 3),
        }, fichiers={"app/__init__.py": "", ".claude/settings.json": "{}\n"})
        self.faux = os.path.join(self.tmp.name, "faux-bin")
        ecrire(self.faux, "claude", FAUX_CLAUDE.replace("#!/usr/bin/env python3",
                                                        "#!" + sys.executable), executable=True)
        self.appels = os.path.join(self.tmp.name, "appels.jsonl")
        self.travail = {
            "F001": {"fichiers": {"app/un/__init__.py": "", "app/un/f.py": "def f001():\n    return 1\n"}},
            "F002": {"fichiers": {"app/deux/__init__.py": "", "app/deux/f.py": "def f002():\n    return 2\n"}},
            "F003": {"fichiers": {"app/trois/__init__.py": "", "app/trois/f.py": "def f003():\n    return 4\n"},
                     "conteste": "test_f003 attend 3"},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def orchestre(self, *args, mode=""):
        env = {"PATH": self.faux + os.pathsep + os.environ["PATH"], "FAUX_MODE": mode,
               "FAUX_APPELS": self.appels, "FAUX_TRAVAIL": json.dumps(self.travail),
               "FAUX_MARQUER": chemin("bin", "marquer-valide")}
        return lancer(["bin/orchestre", "--depot", self.depot, "--ci", "locale"] + list(args),
                      env=env)

    def passes_sur_origin(self):
        texte = git(self.depot, "show", "origin/main:feature_list.json")
        return {f["id"]: f["passes"] for f in json.loads(texte)["fonctionnalites"]}

    def appels_claude(self):
        with open(self.appels, encoding="utf-8") as f:
            return [json.loads(l) for l in f]

    def test_deux_en_parallele_fusionnees_la_troisieme_jamais(self):
        r = self.orchestre()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.passes_sur_origin(),
                         {"F000": True, "F001": True, "F002": True, "F003": False})
        self.assertIn("| F001 | fusionnée", r.stdout)
        self.assertIn("| F002 | fusionnée", r.stdout)
        self.assertIn("| F003 | non validée", r.stdout)
        self.assertIn("TEST CONTESTÉ : test_f003 attend 3", r.stdout)
        self.assertIn("Coût total : 0.0800 $", r.stdout)  # 3 sessions + 2 relectures
        sessions = [a for a in self.appels_claude() if "--worktree" in a]
        self.assertEqual(len(sessions), 3)
        for a in sessions:
            self.assertNotIn("--bare", a)
            self.assertNotIn("--max-budget-usd", a)  # surveillé : pas de plafond
            self.assertIn("--include-hook-events", a)
            self.assertEqual(a[a.index("--permission-mode") + 1], "acceptEdits")
            self.assertIn("--settings", a)
        relectures = [a for a in self.appels_claude() if a[a.index("-p") + 1].startswith("/code-review")]
        self.assertEqual(len(relectures), 2)
        git(self.depot, "fetch", "-q", "origin")
        self.assertIn("agent/F003", git(self.depot, "branch", "--list", "agent/*"))

    def test_verdict_ecrit_accepte(self):
        r = self.orchestre(mode="verdict")
        self.assertIn("| F001 | fusionnée", r.stdout)

    def test_plafond_seulement_sans_surveillance(self):
        self.orchestre("--sans-surveillance", "0.5")
        for a in [a for a in self.appels_claude() if "--worktree" in a]:
            self.assertEqual(a[a.index("--max-budget-usd") + 1], "0.5")

    def test_hooks_non_charges_arrete_la_session(self):
        r = self.orchestre(mode="sans-hook")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hooks non chargés", r.stdout)
        self.assertNotIn("fusionnée", r.stdout)
        self.assertEqual(self.passes_sur_origin()["F001"], False)

    def test_version_trop_ancienne(self):
        r = lancer(["bin/orchestre", "--depot", self.depot, "--ci", "locale"],
                   env={"PATH": self.faux + os.pathsep + os.environ["PATH"],
                        "FAUX_APPELS": self.appels, "FAUX_TRAVAIL": json.dumps(self.travail),
                        "FAUX_MARQUER": chemin("bin", "marquer-valide"), "FAUX_VERSION": "2.1.200"})
        self.assertIn("2.1.200 < 2.1.295", r.stdout)
        self.assertNotIn("fusionnée", r.stdout)

    def test_relecture_sans_verdict_point_de_rendez_vous(self):
        r = self.orchestre(mode="sans-verdict")
        self.assertIn("/code-review sans verdict lisible", r.stdout)
        self.assertIn("Points de rendez-vous", r.stdout)
        self.assertIn("- agent/F001", r.stdout)
        self.assertEqual(self.passes_sur_origin()["F001"], False)

    def test_refus_si_checkout_principal_sale(self):
        ecrire(self.depot, "feature_list.json", "{}")
        r = self.orchestre()
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(self.appels))


if __name__ == "__main__":
    unittest.main()
