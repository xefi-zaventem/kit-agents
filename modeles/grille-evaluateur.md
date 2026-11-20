# Grille de l'évaluateur — gabarit NON CALIBRÉ

> À calibrer après la tranche exemplaire (`methode/modeles.md` §3) : l'évaluateur et l'humain notent
> les mêmes cas, les écarts corrigent le prompt, les cas notés par l'humain deviennent les exemples.
> Tant que ce n'est pas fait, les notes de l'évaluateur ne décident rien seules.

| Critère | Ce qu'on regarde | Seuil (sur 10) | Note | Preuve (capture, étape) |
|---|---|---|---|---|
| Fonctionnement | Chaque `steps` des fonctionnalités du jalon se reproduit dans le navigateur | 8 | | |
| Respect du système de design | Captures comparées aux écrans de référence ; aucun composant hors liste | 8 | | |
| Robustesse | Erreurs d'API simulées, champs vides, double clic, retour arrière | 6 | | |
| Conformité à l'architecture | Code comparé aux ADR et contrats (passe anti-dérive) | 7 | | |
| Sécurité (relecture avant production seulement) | Authentification, droits, validation humaine des écritures, secrets | 9 | | |

Un critère sous son seuil = jalon refusé.

## Corrections exploitables

Une ligne par correction : fonctionnalité, étape, ce qui est observé, ce qui est attendu.

## Exemples de calibration

(vide tant que la calibration n'est pas faite)
