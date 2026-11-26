# Architecture du harness — ce qu'Anthropic publie et ce que le kit en fait

> **Couche : `kit-agents`.** Aucun détail de projet ni de machine ici.
> Les sections 1 à 3 résument **uniquement** ce qu'Anthropic a publié (vérifié le 18 novembre 2026).
> Les sections 4 à 6 sont **nos choix**, marqués comme tels. Les modèles concrets sont dans `08`.
> Version 4 (18/11/2026) : pas de root sur une machine d'infrastructure (§4.3), `marquer-valide`
> dans un bac à sable (§4.2), CI et `/code-review` avant fusion, `orchestre` réduit (§5), limite de
> `onFailure` sur `Stop` (§4.4), budget de l'abonnement (§5.2).
> Version 5 (19/11/2026) : `orchestre` ne fusionne jamais seul (D29, §5.1), résultat du hook `Stop`
> lu par `orchestre`, `system/init` sans les hooks, réponse `(none)` de `/code-review`.

---

## 1. Harness à deux agents (Anthropic, 26 novembre 2025)

Article : *Effective harnesses for long-running agents*, Justin Young.
But : faire avancer un agent sur plusieurs fenêtres de contexte sans qu'il oublie sa progression,
refasse le travail ou déclare avoir fini trop tôt.

| Agent | Quand | Ce qu'il fait |
|---|---|---|
| **Initialisateur** | Une fois | Crée `init.sh`, `claude-progress.txt`, la liste des fonctionnalités en JSON, un premier commit |
| **Agent de code** | Ensuite | Une fonctionnalité à la fois, laisse une trace claire |

Faits notables de l'article :

- Format d'une entrée : `category`, `description`, `steps` (étapes de vérification), `passes` (`false` au départ).
- L'agent ne doit changer que `passes`. **Anthropic l'obtient par des consignes fermement formulées dans
  le prompt, pas par des hooks** ; le JSON est choisi parce que le modèle le modifie moins volontiers.
- Rituel : `pwd`, lire git log et progression, choisir la fonctionnalité prioritaire, démarrer le serveur
  par `init.sh`, lancer un test de bout en bout de base avant tout nouveau travail.
- Les tests de bout en bout **dans un navigateur** (Puppeteer MCP dans l'article) attrapent ce que les
  tests unitaires et `curl` laissent passer. Limite citée : les boîtes d'alerte natives du navigateur
  sont invisibles pour l'agent.
- Initialisateur et agent de code ne diffèrent que par leur prompt initial ; construit sur le Claude Agent SDK.

## 2. Harness à trois agents (Anthropic, 24 mars 2026)

Article : *Harness design for long-running application development*, Prithvi Rajasekaran (Anthropic Labs).

### 2.1 Les rôles

| Agent | Rôle |
|---|---|
| **Planificateur** | Transforme une demande de 1 à 4 phrases en spec produit ; reste général sur la technique pour qu'une erreur de spec ne se propage pas |
| **Générateur** | Construit, fonctionnalité par fonctionnalité, s'auto-évalue en fin de sprint avant de passer la main |
| **Évaluateur** | Utilise l'application via Playwright MCP (interface, API, base) et note selon des critères à **seuils durs** : un critère sous son seuil = sprint refusé |

- **Contrat de sprint** : avant chaque sprint, le générateur propose quoi construire et comment le
  vérifier ; l'évaluateur relit ; ils itèrent jusqu'à accord, par fichiers.
- **Critères** de l'évaluateur full-stack : profondeur produit, fonctionnement, design visuel, qualité du code.
- **Calibration** : exemples notés (few-shot) avec le détail des notes, puis relecture des journaux de
  l'évaluateur et ajustement du prompt là où son jugement divergeait de celui de l'auteur.

### 2.2 Ce qui a été retiré au fil des modèles

| Modèle | Changement |
|---|---|
| Sonnet 4.5 | « Anxiété de contexte » : **réinitialisations de contexte** indispensables |
| Opus 4.5 | Réinitialisations **abandonnées** ; compaction automatique du SDK ; sprints conservés |
| Opus 4.6 | **Sprints supprimés** ; planificateur et évaluateur gardés ; évaluateur en **une passe en fin d'exécution** |

Ordres de grandeur rapportés : harnais complet sous Opus 4.5, 6 h pour 200 $ ; harnais v2 sous Opus 4.6
(application audio dans le navigateur), 3 h 50 pour 124,70 $, dont environ 11 $ pour trois passes d'évaluation.

### 2.3 Le principe à retenir

Chaque composant d'un harnais encode une hypothèse sur ce que le modèle ne sait pas faire seul ; ces
hypothèses vieillissent. Anthropic recommande la solution la plus simple possible, et de réexaminer le
harnais à chaque nouveau modèle en retirant ce qui ne porte plus. L'évaluateur vaut son coût **quand la
tâche dépasse ce que le modèle fait seul de façon fiable**.

## 3. Pratiques des équipes d'Anthropic

- `CLAUDE.md` versionné dans git, enrichi des erreurs rencontrées ; la doc vise moins de 200 lignes par fichier.
- Sessions parallèles sur des worktrees git distincts (`claude --worktree <nom>`).
- Sous-agents pour explorer sans encombrer le contexte principal.
- Bonnes pratiques officielles de Claude Code (vérifiées le 18/11/2026) : ce qui doit arriver
  **à chaque fois** va dans un hook, une règle `deny` ou un réglage géré ; le reste reste dans
  `CLAUDE.md`. Garder peu de règles imposées : chacune se déclenche parfois à tort et doit être
  entretenue. Pour la sécurité, règles **et** sandbox. Relecture par une session neuve
  (`/code-review`) en demandant d'ignorer le style ; `/verify` fait tourner l'application.

---

## 4. Nos choix pour le kit

### 4.1 Vue d'ensemble

```
Cadrage (conversations, humain + planificateur)
   └─► spec, ADR, contrats, feature_list.json (steps), système de design verrouillé

Construction (Claude Code, dans la machine de dev du projet)
   ├─ Initialisateur : init.sh, squelette, contrôles, tests e2e de base, hooks, premier commit
   ├─ Tranche exemplaire : SEULE, relue à fond par l'humain, sert à calibrer l'évaluateur
   ├─ Générateurs : UNE fonctionnalité par session, en parallèle si §2.10 de 06 le permet
   │     rituel → code → contrôles → marquer-valide <id> → progression → commit
   └─ Jalon : évaluateur (navigateur + passe anti-dérive) → corrections → démo humaine
```

### 4.2 Ce que nous reprenons, ajustons, ajoutons

| Élément | Choix | Raison |
|---|---|---|
| Initialisateur, `init.sh`, progression, git | Repris tel quel | — |
| Rituel de début de session, test e2e de base | Repris tel quel | — |
| Une fonctionnalité par session | Gardé, **sans** prétendre qu'Anthropic l'exige encore | Économie, traçabilité, `revert` par fonctionnalité |
| Planificateur | = conversation de cadrage avec l'humain | Le périmètre est tranché par le commanditaire |
| Contrat de sprint | Remplacé par les `steps` validés par l'humain + contrats d'architecture | Le périmètre est figé avant ; moins de tokens |
| Évaluateur | Après la tranche exemplaire, puis par jalon | Hypothèse : nos fonctionnalités sont à la portée du modèle seul ; à revoir si les jalons échouent |
| `passes` | Modifié **uniquement** par `marquer-valide`, qui prend le test dans la branche de référence et le lance dans un bac à sable jetable (`08` §5) | Plus robuste qu'une consigne ou un hook ; le code de l'agent ne tourne jamais avec le droit d'écrire `passes` |
| Contrôle final | CI (GitHub Actions) sur chaque envoi ; fusion seulement si verte, revérifiée juste avant | Hors de la machine de l'agent ; compense l'absence de protection de `main` |
| Relecture | `/code-review` (fonction native) par fonctionnalité, « skip style » | Regard neuf à faible coût, sans outil maison |
| Garde-fous | Sandbox + permissions + hooks (§4.3) ; jamais de root sur une machine d'infrastructure | Anthropic n'en utilise pas ; nos agents tournent sans surveillance |
| Orchestration | `orchestre` réduit : `claude -p` en worktrees, classement « prête » / « à relire » ; la fusion, une par une, est lancée par le pilote (`orchestre fusionner`, D29, §5) | Plus simple qu'un orchestrateur SDK ; on s'appuie sur les fonctions natives (worktrees, sous-agents) ; un humain décide de chaque entrée dans `main` |

### 4.3 Garde-fous : trois couches

La documentation de Claude Code est explicite : un hook qui plante, sort en code 1 ou expire **laisse
passer** l'action par défaut ; seul le code 2 bloque ; pour les refus stricts, il faut le **système de
permissions**, pas les hooks. Le kit applique donc :

| Couche | Ce qu'elle fait | Limite connue |
|---|---|---|
| **1. Sandbox** (`sandbox.enabled`, `allowUnsandboxedCommands: false`, `failIfUnavailable: true`) | Les commandes shell tournent dans un espace réseau séparé, avec une liste de domaines autorisés ; écriture limitée au dépôt ; `.claude/settings*.json` et `.claude/hooks` toujours protégés en écriture | Ne couvre pas les outils Read/Edit/Write (couche 2). À ne pas utiliser seule face à une commande malveillante |
| **2. Permissions `deny`** | `Edit` interdit sur `tests/acceptance/**`, `feature_list.json`, `init.sh`, `.github/**`, la configuration du lanceur de tests à tout niveau (`**/conftest.py`, `**/pytest.ini`, `**/.pytest.ini`, `**/pytest.toml`, `**/tox.ini`, `**/setup.cfg`, `**/pyproject.toml`, `**/sitecustomize.py`, `**/usercustomize.py`), `.claude/**`, `~/.claude/**` ; `Read` interdit sur les fichiers de secrets. `sandbox.filesystem.denyWrite` reprend ces chemins à la racine et dans `tests/` (les fichiers plus profonds : `Edit`, `fin-de-session`, `marquer-valide` et la CI). Pas de règle `Write(...)` : la doc précise que les outils de fichiers ne lisent que `Edit` et `Read` | Les règles portent sur des chemins, pas sur le contenu |
| **3. Hooks** (avec `onFailure: "block"`) | Contrôles de **contenu** : secret dans un texte écrit, commande interdite propre à la machine, lint après écriture, conditions de fin de session | Contournables seuls ; utiles en complément |
| **Contrôle après coup** (hook `Stop`, CI) | `git diff` vide sur `tests/acceptance/` et `init.sh` ; diff de `feature_list.json` limité au champ `passes` ; `init.sh` toujours lancé dans sa version de la référence (`08` §10) | Détecte, n'empêche pas : sert de filet |

**Machine d'infrastructure** (hyperviseur, hôte de conteneurs) : l'agent n'y a **pas** le root.
Il tourne sous un utilisateur dédié, **avec** le sandbox, et passe par deux portes sudo sans mot de
passe, autorisées sans question dans les réglages gérés :

1. **Le jeton d'API de l'outil** (ex. celui de l'hyperviseur), à privilèges séparés, limité par les droits de l'outil
   lui-même (rôles, pool, ponts réseau permis). Un script le lit sous un utilisateur technique : l'agent
   ne voit jamais le jeton.
2. **Une liste fermée d'actions root** : un script appelé par sudo, qui vérifie les arguments et
   construit lui-même chaque commande, sans shell. Tout ce qui n'est pas prévu est refusé.

Raison : une liste noire de commandes (le hook) se contourne en deux étapes par un root (écrire un
script, puis le lancer), et la doc précise que les règles `Edit` ne s'appliquent pas à un script qui
ouvre lui-même les fichiers. Les droits Linux, sudo et les ACL de l'outil, eux, ne se contournent pas
depuis le compte de l'agent. Le hook reste comme filet contre l'erreur.

### 4.4 Hooks fournis par le kit

| Hook | Événement | Effet |
|---|---|---|
| `garde-commandes` | `PreToolUse` sur `Bash` | Refuse (code 2) les commandes listées par `ENVIRONNEMENT.md`. En mode `-p`, « demander » vaut refus : on refuse directement, avec un message qui dit à l'agent de noter la demande dans `claude-progress.txt` sous `DEMANDE HUMAINE` |
| `garde-secrets` | `PreToolUse` sur `Write`, `Edit`, `Bash` | Refuse un texte qui contient un secret (motifs + outil type gitleaks) |
| `controles-rapides` | `PostToolUse` sur `Write`, `Edit` | Lint et format du fichier modifié ; l'échec est renvoyé à l'agent (le hook ne peut pas annuler) |
| `fin-de-session` | `Stop` | Bloque la fin si : typage, imports ou tests rapides échouent ; progression non mise à jour ; diff interdit (§4.3). **Au plus 3 blocages par session**, ensuite il laisse finir en écrivant `ÉCHEC FIN DE SESSION` dans la progression (contre les boucles infinies). **Limite** : la doc précise que `onFailure` n'a aucun effet sur `Stop` ; si ce hook plante, la session se termine quand même. Le filet est alors `orchestre`, qui lit le **résultat** du hook (événement `hook_response` : code de sortie et sortie) : hook sauté, sans résultat ou terminé autrement qu'en code 0 = branche « à relire » ; puis la CI. Sans aucun diff (ex. la relecture, dans un checkout propre de la référence), il n'y a rien à contrôler et la fin passe. Claude Code arrête de lui-même après 8 blocages consécutifs |
| `verrou-ressources` | `PreToolUse` sur `Bash` | Refuse une commande qui touche une ressource partagée verrouillée par une autre session (06, §2.10) |

### 4.5 Skills

Le kit fournit le **gabarit** d'un skill (`SKILL.md` court + fichiers de référence chargés à la demande).
Les skills de contenu (API métier, système de design, conventions) appartiennent au projet.

### 4.6 Plusieurs dépôts

Un projet utilise le kit **par version** : son dépôt contient `.kit-version` (une étiquette git de
`kit-agents`). L'installateur du kit copie les hooks et les scripts (`marquer-valide`…) dans
`/opt/kit/`, **hors du dépôt** et en lecture seule pour l'utilisateur qui fait tourner Claude, et les
réglages dans `.claude/settings.json`. Il accepte une destination (`--destination <dossier>`) pour ses
propres tests, sans droit administrateur. La CI, elle, récupère le kit à l'étiquette de `.kit-version`
(`08` §9). Une erreur de méthode
découverte dans un projet devient une modification de `kit-agents`, une nouvelle étiquette, puis une mise
à jour volontaire dans chaque projet.

---

## 5. Orchestration (nos choix)

### 5.1 Le script `orchestre` (version réduite, v1.0)

> **Bloqué avant le point de contrôle (D31)** : sans `--essai-du-kit` (réservé aux tests du kit),
> `orchestre` refuse de tourner. Constats ouverts : `CHANGELOG.md`, « Limites connues ».

Livré par le kit, lancé par l'humain. Il ne fait que ce qui suit ; tout ajout passe par un incident
réel (06, §2.12). Pour chaque dépôt déclaré :

1. Lire `feature_list.json`, choisir les fonctionnalités prêtes (non validées, dépendances validées).
2. Former les lots parallèles selon 06, §2.10 (au plus 3).
3. Pour chacune : lancer
   `claude -p "<prompt court : id + rituel>" --worktree <id> --output-format stream-json --include-hook-events`
   (`--max-budget-usd <plafond>` seulement sans surveillance) avec les réglages du dépôt (**pas** de
   `--bare`, qui ignore hooks et `CLAUDE.md` et deviendra le défaut de `-p` : le script passe
   `--settings` explicitement). L'environnement de la session est nettoyé de toute variable `KIT_*`
   sauf celles qu'`orchestre` pose lui-même (`KIT_FONCTIONNALITE`).
   **`system/init` ne liste pas les hooks** (vérifié par un essai) : `orchestre` y vérifie la version
   et le worktree, et contrôle les hooks par `--include-hook-events` : un outil qui tourne avant tout
   hook `PreToolUse` arrête la session ; le hook `Stop` doit avoir tourné et son dernier résultat
   (`hook_response`) doit être un code 0.
4. Mode de permission : `acceptEdits` + liste `--allowedTools` explicite. **Jamais** `bypassPermissions`.
5. Classer chaque branche (règle de fusion **D29**) : **« prête »** seulement si la CI est verte, si le
   verdict de `/code-review` (lancé dans un checkout propre de `origin/main`) est **exactement la
   dernière ligne non vide** de la réponse et vaut `(none)` ou `VERDICT : AUCUN BLOQUANT`, et si le
   diff reste dans les `touches` (plus les conditions de la session : validée, hook `Stop` en code 0,
   pas d'`ÉCHEC FIN DE SESSION`, taille du diff). Tout le reste est **« à relire »**. En `-p`,
   `/code-review` répond `(none)` quand il ne trouve rien, et ignore souvent la consigne de verdict ;
   essai du 19/11/2026 : il ajoute parfois un paragraphe après `(none)`, et la branche reste alors à
   relire (coût : une relecture humaine, pas un risque). Un verdict cité plus haut dans la réponse
   (par exemple recopié d'un commentaire du diff) ne compte pas.
6. Écrire un récapitulatif : prêtes, à relire (avec la raison), contestées, `TROP GROS`, demandes
   humaines, coût et taille du diff de chaque fonctionnalité (06, §2.12), coût total.

`orchestre` ne fusionne **jamais** seul dans `main` (D29). Le pilote lit le récapitulatif, puis lance
`orchestre fusionner --recapitulatif <empreinte>` (empreinte sha256 affichée par `orchestre`, jamais
« le dernier fichier de `.kit/` », que du code de l'agent pourrait déposer) : les branches « prêtes »
de ce récapitulatif sont fusionnées une par une,
dans l'ordre de priorité, si la branche n'a pas bougé depuis et si la CI, revérifiée juste avant, est
verte ; tests complets après chaque fusion ; conflit ou rouge → pas de fusion, file d'attente. Avant
chaque push, contrôle D28 (auteur et committer = pilote, sans `Co-Authored-By`, `anthropic.com`,
« Generated with Claude Code » ni lien de session) ;
push refusé → retour à `ORIG_HEAD`, branche non fusionnée.

Ce que `orchestre` ne fait **pas** : choisir le modèle, réessayer en boucle, résoudre un conflit,
modifier `feature_list.json` autrement que par `marquer-valide`. Sans `orchestre`, la même chose se
fait à la main avec `claude --worktree <nom>` (fonction native), une session par fonctionnalité.

### 5.2 Budget

- Coût de chaque session toujours consigné (gratuit).
- Plafond par session **seulement** dans la boucle sans surveillance (garde-fou), réglé par le projet.
- Le choix de l'offre Claude (abonnement ou API) appartient au projet, qui vérifie que les conditions
  de l'offre couvrent les données que Claude lira (voir les règles du projet).
- Vérifié le 18/11/2026 : avec un abonnement, `claude -p` puise encore dans les limites de
  l'abonnement (le passage à un crédit séparé, annoncé pour le 15 juin 2026, a été suspendu). La doc
  précise que les limites Pro et Max supposent un usage individuel ordinaire. Trois agents en boucle
  s'en approchent : on mesure le coût réel après la tranche exemplaire avant de lancer le parallélisme.
- `--bare` deviendra le défaut de `-p` (doc) et n'utilise pas la connexion de l'abonnement :
  `orchestre` ne le passe jamais, et vérifie à chaque lancement que les hooks tournent (événements
  de hooks : `system/init` ne les liste pas).

---

## 6. Réexamen à chaque modèle

À chaque changement de modèle, une session de réexamen répond, composant par composant : « porte-t-il
encore quelque chose ? ». Candidats au retrait dans l'ordre : passe anti-dérive, évaluateur par jalon
(→ une seule passe finale, comme Anthropic avec Opus 4.6), découpage strict une fonctionnalité par session.

---

## Sources

- Anthropic, *Effective harnesses for long-running agents* :
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, *Harness design for long-running application development* :
  https://www.anthropic.com/engineering/harness-design-long-running-apps
- Claude Code, hooks : https://code.claude.com/docs/en/hooks
- Claude Code, sandbox : https://code.claude.com/docs/en/sandboxing
- Claude Code, mode non interactif : https://code.claude.com/docs/en/headless
- Claude Code, mémoire : https://code.claude.com/docs/en/memory
- Claude Code, worktrees : https://code.claude.com/docs/en/common-workflows
- Claude Code, bonnes pratiques : https://code.claude.com/docs/en/best-practices
- Claude Code, permissions (limites des règles `Edit` face aux scripts) : https://code.claude.com/docs/en/permissions
- Claude Code, cadre juridique (usage individuel ordinaire des offres Pro et Max) :
  https://code.claude.com/docs/en/legal-and-compliance
- Utiliser l'Agent SDK avec une offre Claude : https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
