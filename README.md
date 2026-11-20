# kit-agents

Couche **méthode** : un kit générique pour faire construire un logiciel par une équipe d'agents
Claude Code sans dérive (méthode, modèles, hooks, scripts, modèle de CI). Aucun détail de projet ni de machine.

| Référence dans les textes | Fichier qui fait foi |
|---|---|
| `06` | `methode/methode.md` : méthode anti-dérive, proportionnalité, rôles de l'équipe |
| `07` | `methode/architecture.md` : ce qu'Anthropic publie et les choix du kit (garde-fous, orchestration) |
| `08` | `methode/modeles.md` : modèles (`feature_list.json`, progression, grille, réglages, CI) |

Contenu : `hooks/` (garde-fous Claude Code), `bin/` (`installer`, `marquer-valide`, `orchestre`,
`verifier-diff-liste`, `tout-verifier`), `modeles/`, `tests/` (`python3 -m unittest discover -s tests`, Docker requis).
Installation : `bin/installer --depot <dépôt> --regles <règles de la machine> --organisation <org>`.

Version : `VERSION` ; changements : `CHANGELOG.md`. Chaque projet note la version suivie dans sa
`.kit-version`. Le point d'entrée d'un projet est son propre `docs/index.md`.
