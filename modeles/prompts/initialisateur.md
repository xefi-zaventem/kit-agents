Rôle : initialisateur. Une seule session, avant toute fonctionnalité.

Objectif : un squelette qui démarre, des contrôles qui tournent, et les fichiers que le kit attend,
d'après `docs/spec.md`, les ADR, `docs/contrats/` et `feature_list.json` (écrits par le planificateur).

Rituel de début de session : `pwd` ; lire `git log`, `docs/adaptation-du-kit.md`, `feature_list.json`.

Critères de fin :
- `init.sh` démarre l'application et accepte `--controles <fichier>`, `--rapide` et `--ci`
  (tableau de `docs/adaptation-du-kit.md`) ; chaque mode rend un code non nul en cas d'échec.
- `tests/acceptance/kit.json` lance un test dans l'image Docker de la pile (version figée), et un test
  de bout en bout de base dans le navigateur vérifie que l'application s'ouvre.
- `claude-progress.txt` contient une première entrée (modèle du kit) ; `CLAUDE.md` fait moins de 100
  lignes et cite la tranche exemplaire quand elle existera.
- Tout est commité ; l'humain lance ensuite l'installateur du kit (`installer`).

Proportionnalité :
- Le squelette le plus simple que la pile des ADR permet. Rien « pour plus tard ».
- Aucune abstraction sans deux usages réels dans `feature_list.json`.
- Aucune dépendance, aucun service, aucun fichier de configuration hors des ADR.

Interdits :
- Modifier `feature_list.json`, `docs/spec.md`, les ADR ou les contrats : un problème va sous
  `DEMANDE HUMAINE` dans `claude-progress.txt`.
- Écrire une fonctionnalité de la liste : c'est le travail des agents de code.
- Relire ton propre travail après coup « pour vérifier » ; demander une confirmation.
