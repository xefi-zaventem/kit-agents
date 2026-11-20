"""Aides communes aux tests du kit : dépôts git jetables avec un origin nu local."""
import json
import os
import shutil
import stat
import subprocess
import sys
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE = "python:3.13-slim"  # image des tests d'exemple (choix des tests du kit seulement)
# Tests qui lancent un conteneur : sautés (pas en échec) là où Docker manque ; la CI en a.
avec_docker = unittest.skipUnless(shutil.which("docker"), "Docker absent")

for cle, valeur in {"GIT_AUTHOR_NAME": "essai", "GIT_AUTHOR_EMAIL": "essai@exemple.invalid",
                    "GIT_COMMITTER_NAME": "essai", "GIT_COMMITTER_EMAIL": "essai@exemple.invalid",
                    "GIT_CONFIG_NOSYSTEM": "1"}.items():
    os.environ[cle] = valeur


def chemin(*parties):
    return os.path.join(KIT, *parties)


def lancer(cmd, cwd=None, entree=None, env=None, timeout=600):
    if isinstance(entree, (dict, list)):
        entree = json.dumps(entree)
    if cmd and not os.path.isabs(cmd[0]) and os.path.exists(chemin(cmd[0])):
        cmd = [sys.executable, chemin(cmd[0])] + list(cmd[1:])
    return subprocess.run(cmd, cwd=cwd, input=entree, capture_output=True, text=True,
                          env=dict(os.environ, **(env or {})), timeout=timeout)


def git(cwd, *args):
    r = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("git %s : %s" % (" ".join(args), r.stderr))
    return r.stdout


def ecrire(racine, relatif, contenu, executable=False):
    p = os.path.join(racine, relatif)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(contenu)
    if executable:
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def lire(racine, relatif):
    with open(os.path.join(racine, relatif), encoding="utf-8") as f:
        return f.read()


def fonctionnalite(fid, touches, depends_on=(), passes=False, priorite=1, jalon="S1"):
    return {"id": fid, "besoin": [1], "jalon": jalon, "priorite": priorite,
            "category": "fonctionnel", "description": "Fonctionnalité d'essai " + fid,
            "steps": ["Appeler la fonction", "Le résultat attendu est renvoyé"],
            "test": "tests/acceptance/test_%s.py" % fid.lower(), "touches": list(touches),
            "depends_on": list(depends_on), "attribue_a": None, "passes": passes}


def liste(fonctions):
    return json.dumps({"projet": "essai", "version_kit": "v1.0", "fonctionnalites": fonctions},
                      indent=2, ensure_ascii=False) + "\n"


INIT_SH = """#!/bin/sh
# init.sh d'essai : --controles refuse un fichier qui contient MAUVAIS ; --rapide lit RAPIDE_KO.
case "$1" in
  --controles) ! grep -q MAUVAIS "$2" ;;
  --rapide) [ ! -e RAPIDE_KO ] ;;
  --ci) exit 0 ;;
  *) echo "application démarrée" ;;
esac
"""


def creer_depot(tmp, fonctions, tests=None, fichiers=None):
    """Crée <tmp>/origin.git (nu) et <tmp>/depot (clone de travail sur main, poussé)."""
    origine = os.path.join(tmp, "origin.git")
    depot = os.path.join(tmp, "depot")
    git(tmp, "init", "-q", "--bare", "-b", "main", origine)
    git(tmp, "init", "-q", "-b", "main", depot)
    ecrire(depot, "feature_list.json", liste(fonctions))
    ecrire(depot, "tests/acceptance/kit.json", json.dumps(
        {"image": IMAGE, "commande": ["python3", "-I", "{test}"]}) + "\n")
    ecrire(depot, "init.sh", INIT_SH, executable=True)
    ecrire(depot, "claude-progress.txt", "=== début du projet d'essai ===\n")
    ecrire(depot, ".gitattributes", "claude-progress.txt merge=union\n")
    ecrire(depot, ".gitignore", ".kit/\n.claude/worktrees/\n__pycache__/\n")
    for relatif, contenu in (tests or {}).items():
        ecrire(depot, relatif, contenu)
    for relatif, contenu in (fichiers or {}).items():
        ecrire(depot, relatif, contenu)
    git(depot, "add", "-A")
    git(depot, "commit", "-q", "-m", "départ")
    git(depot, "remote", "add", "origin", origine)
    git(depot, "push", "-q", "-u", "origin", "main")
    git(depot, "remote", "set-head", "origin", "main")
    return depot


def test_qui_importe(module, fonction, attendu):
    """Contenu d'un test d'acceptation d'essai : app/<module>.py doit renvoyer <attendu>."""
    return ("import sys\nsys.path.insert(0, '.')\nfrom app.%s import %s\n"
            "assert %s() == %r, %s()\nprint('ok')\n" % (module, fonction, fonction, attendu, fonction))
