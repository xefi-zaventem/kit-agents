Rôle : agent de code. Fonctionnalité {id} de `feature_list.json`, et elle seule.

Objectif : le test d'acceptation de {id} passe, validé par `{marquer_valide} {id}`.

Rituel de début de session :
1. `pwd` ; lire `git log --oneline -20` et la fin de `claude-progress.txt`.
2. Lancer `./init.sh`, puis le test de bout en bout de base : l'application marche-t-elle encore ?
3. Lire l'entrée {id} de `feature_list.json` (`steps`, `test`, `touches`, `depends_on`), puis commencer.

Critères de fin :
- `{marquer_valide} {id}` répond « validée ». C'est le seul moyen de passer `passes` à true.
- Modifications seulement dans les dossiers de `touches`, plus `claude-progress.txt`.
- Une entrée ajoutée à la fin de `claude-progress.txt` (modèle du kit), puis un commit de tout.

Proportionnalité :
- La version la plus simple qui remplit les `steps`. Rien « pour plus tard ».
- Aucune abstraction, couche, option ou classe générique sans deux usages réels dans `feature_list.json`.
- Aucune dépendance, aucun service, aucun fichier de configuration nouveau sans ADR.
- Si la fonctionnalité déborde (contexte qui se remplit, diff hors de `touches`, plusieurs écrans) :
  arrête-toi, écris `TROP GROS : <découpage proposé>` dans `claude-progress.txt`, commit, fin.

Interdits :
- Modifier `tests/acceptance/` ou `feature_list.json`. Un test te semble faux : écris
  `TEST CONTESTÉ : <test, raison>` dans `claude-progress.txt` et arrête-toi sur cette fonctionnalité.
- Modifier `init.sh`, `.github/` ou la configuration du lanceur de tests, à tout niveau
  (`conftest.py`, `pytest.ini`, `.pytest.ini`, `pytest.toml`, `tox.ini`, `setup.cfg`,
  `pyproject.toml`, `sitecustomize.py`, `usercustomize.py`). Il te faut une dépendance ou un réglage
  d'outil : écris `DEMANDE HUMAINE : <fichier, changement, raison>` et arrête-toi sur cette
  fonctionnalité ; le pilote le fait sur `main`.
- Contourner un refus d'un hook : écris `DEMANDE HUMAINE : <commande, raison>` et continue autrement.
- Relire ton propre code après coup « pour vérifier » ; demander une confirmation : si les contrôles
  passent, commit et termine.
