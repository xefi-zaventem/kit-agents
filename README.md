# kit-agents

Couche **méthode** : un kit générique pour faire construire un logiciel par une équipe d'agents
Claude Code sans dérive (méthode, modèles, hooks, modèle de CI). Aucun détail de projet ni de machine.

Fichiers qui font foi :

- `methode/methode.md` : la méthode anti-dérive, la proportionnalité, les rôles de l'équipe ;
- `methode/architecture.md` : ce qu'Anthropic publie et les choix du kit (garde-fous, orchestration) ;
- `methode/modeles.md` : les modèles (`feature_list.json`, progression, grille de l'évaluateur, réglages).

Version du kit : `VERSION` ; changements : `CHANGELOG.md`. Chaque projet qui utilise le kit note la
version suivie dans sa `.kit-version`. Le point d'entrée d'un projet est son propre `docs/index.md` :
c'est lui qu'on joint en tête de chaque session.
