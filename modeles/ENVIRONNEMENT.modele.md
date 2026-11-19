# Environnement : <machine>

> Modèle du kit (`methode/modeles.md` §7). Ce fichier vit dans le dépôt d'infrastructure de la
> machine, jamais dans le kit. Les rubriques « Commandes interdites », « Chemins interdits » et
> « Ressources partagées » sont traduites dans le fichier de règles lu par `garde-commandes` et
> `verrou-ressources` (clés ci-dessous).

## Périodes et droits de l'agent

| Période | Machine | Droits | Garde-fous |
|---|---|---|---|

## Commandes interdites (lues par garde-commandes)

Clés du fichier de règles : `commandes` (`nom`, `raison`, et au besoin `si_args`, `sauf_args`,
`valeurs`), `motifs_texte` (`motif`, `raison`).

## Chemins interdits en lecture

Clés : `chemins_proteges` (expressions régulières), `lecture_seule` (commandes permises sur ces
chemins), `copie_depuis_protege`. Si le dossier du kit (`/opt/kit`) est protégé, mettre
`marquer-valide` dans `lecture_seule` : sinon l'agent ne peut pas le lancer (il n'écrit que
`feature_list.json` du dépôt, jamais un chemin protégé). Côté Claude Code : règles `Read(...)` en `deny` et
`sandbox.filesystem.denyRead`.

## Ressources partagées (verrous)

Clés : `dossier_verrous` (hors de portée de l'agent), `duree_verrou_minutes`, `ressources`
(`nom`, `motif` sur la commande).

## Fenêtres sans session agent

Clé : `verrou_donnees_reelles` (fichier dont la présence fait tout refuser).

## Portes d'accès de l'agent (pas de root) : jeton d'API et ses droits, actions root permises

## Risques acceptés, avec garde-fous de remplacement
