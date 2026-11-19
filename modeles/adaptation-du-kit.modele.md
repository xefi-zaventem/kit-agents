# Adaptation du kit au projet <nom>

> Modèle du kit (`methode/modeles.md` §8), à copier dans `docs/adaptation-du-kit.md` du projet.

- Version du kit : <étiquette, identique à `.kit-version`>
- Pile et dépendances autorisées (renvoi vers les ADR)
- Structure des modules et règles d'import
- Motifs interdits propres au projet
- Skills du projet
- Tranche exemplaire (chemin)
- Données de développement (origine, règles)
- Critères d'évaluation propres au projet
- Offre Claude utilisée et données que Claude lit

## Ce que les scripts du kit appellent dans le projet

| Appel | Par qui | Ce qu'il doit faire |
|---|---|---|
| `./init.sh` | Agent, au début de chaque session | Démarrer l'application |
| `./init.sh --controles <fichier>` | Hook `controles-rapides`, après chaque écriture | Lint et format du fichier (outils de la pile) ; code non nul si échec |
| `./init.sh --rapide` | Hook `fin-de-session` | Typage, règles d'import, tests rapides ; code non nul si échec |
| `./init.sh --ci` | CI (`.github/workflows/tests.yml`) | Préparer la machine de CI |
| `tests/acceptance/kit.json` | `marquer-valide`, `tout-verifier` | `{"image": "<image Docker, version figée>", "commande": ["<programme>", "...", "{test}"]}` : lance un test d'acceptation dans le conteneur, à la racine du dépôt (`/depot`, en lecture seule, sans réseau) |

`feature_list.json` : un champ par ligne (indentation de 2), pour que deux validations en parallèle ne
touchent jamais la même ligne.
