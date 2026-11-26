# Méthode anti-dérive

> **Couche : `kit-agents`** (méthode réutilisable, indépendante de tout projet).
> Statut : référence de méthode. En cas de conflit entre ce document et une consigne donnée dans un
> chat, **ce document gagne** jusqu'à ce qu'il soit modifié et commité.
> Ce fichier ne contient **aucun** détail de projet ni de machine. Ce qui est propre à un projet vit dans
> le dépôt du projet (`docs/adaptation-du-kit.md`, `CLAUDE.md`, ADR) ; ce qui est propre à une machine vit
> dans son dépôt d'infrastructure (`ENVIRONNEMENT.md`).
> Version 4 (18/11/2026) : rôles de l'équipe (§7), proportionnalité (§2.12), `marquer-valide` qui
> n'exécute plus le code de l'agent hors sandbox (§2.2), relecture et intégration continue (§3).

---

## 1. Le problème à éviter

La dérive de spécification : le résultat commence bien, puis s'éloigne du cadrage au fil des sessions.

| Cause | Mécanisme |
|---|---|
| Conversation longue | Chaque nouvelle consigne fait passer les précédentes au second plan. |
| Copie de l'existant | L'agent reproduit les motifs déjà présents dans le code, y compris les mauvais. |
| Spec en prose | Un texte se relit mais ne s'exécute pas. Rien ne prouve que le code le respecte. |
| Règles d'architecture | C'est ce que les modèles tiennent le moins bien sur la durée. |
| Décisions de goût | Sans référence imposée, le modèle revient à la moyenne (style, structure, bibliothèques). |

**Principe directeur : le cadrage n'est pas un texte que l'agent lit, c'est une contrainte que des
outils font respecter.**

**Principe de sobriété** (repris d'Anthropic) : chaque mécanisme ci-dessous encode une hypothèse sur ce
que le modèle ne sait pas faire seul. À chaque changement de modèle, on revoit la liste et on retire ce
qui ne sert plus (voir `07`, §2.3).

---

## 2. Les douze mécanismes

### 2.1 La vérité est dans des fichiers versionnés, jamais dans le chat

| Fichier | Rôle | Qui le modifie |
|---|---|---|
| `docs/spec.md` | Ce que fait l'application, par module | Planificateur, après validation humaine |
| `docs/decisions/NNNN-titre.md` | Une décision structurante par fichier (ADR) | Planificateur, après validation humaine |
| `docs/contrats/` | Modèles de données, formats d'échange, qui appelle qui | Planificateur, figés avant tout agent |
| `feature_list.json` | Fonctionnalités, critères, champ `passes` (schéma : `08`, §1) | Planificateur crée ; **seul le script `marquer-valide`** change `passes` |
| `tests/acceptance/` | Tests d'acceptation de bout en bout | Planificateur ; lecture seule pour les agents de code |
| `CLAUDE.md` | Règles courtes du projet, erreurs déjà rencontrées | Humain ou planificateur, < 100 lignes |
| `claude-progress.txt` | Journal de chaque session (modèle : `08`, §2) | Agent de code, en fin de session |

Une conversation **produit** ces fichiers. Elle n'est jamais la source de vérité.

### 2.2 Une spec exécutable, écrite avant le code

- Chaque fonctionnalité a des étapes de vérification (`steps`) : entrée, action, résultat attendu.
- Les critères sont écrits **avant** le code (phase de cadrage). Ils deviennent des tests exécutables
  **de bout en bout dans un navigateur** dès que le squelette existe (initialisation et tranche exemplaire).
  Anthropic a constaté que les tests unitaires et `curl` seuls laissent passer les échecs de bout en bout.
- L'agent de code ne peut ni écrire dans `tests/acceptance/`, ni modifier `feature_list.json`
  directement : c'est imposé par le sandbox et les permissions, pas seulement par un hook (`07`, §4.3).
- `init.sh`, `.github/` et la configuration du lanceur de tests (`conftest.py`, réglages de pytest,
  `pyproject.toml`, `setup.cfg`, `sitecustomize.py`…, à tout niveau) appartiennent aussi à la
  référence : une dépendance ou un réglage d'outil passe par une `DEMANDE HUMAINE`, et le pilote le
  change sur `main`.
- `passes` ne passe à `true` que par `marquer-valide <id>`, qui lance le test de la fonctionnalité et
  n'écrit que si le test passe. L'agent ne peut pas « réussir » en changeant la règle.
- `marquer-valide` prend le test et `feature_list.json` **dans la branche de référence** (pas dans
  la copie de travail de l'agent) et lance le test **dans un bac à sable jetable**, sans droit
  d'écriture sur le dépôt. Raison : le test exécute le code de l'agent ; s'il tournait avec les droits
  de `marquer-valide`, ce code pourrait écrire `passes` lui-même (`08`, §5).
- L'intégration continue (CI) relance tous les tests d'acceptation à chaque envoi : c'est le contrôle
  final, hors de la machine de l'agent. Une fusion n'a lieu que si la CI est verte, et seulement à
  l'initiative du pilote (`orchestre fusionner`, D29).
- `init.sh` appartient à la référence, comme `tests/acceptance/` et `tests/acceptance/kit.json` :
  les hooks lancent toujours la version de `origin/main`, l'agent ne peut pas l'écrire, et la CI
  échoue s'il diffère (`08`, §10).
- La liste est en JSON, pas en Markdown : les modèles réécrivent plus volontiers le Markdown.

**Test contesté.** Si un agent pense qu'un test d'acceptation est faux (URL, sélecteur, attente
erronée) : il l'écrit dans `claude-progress.txt` sous `TEST CONTESTÉ`, passe à une autre fonctionnalité
et ne touche pas au test. Seul l'humain (ou le planificateur validé par l'humain) le corrige.

### 2.3 L'architecture vérifiée par des outils

L'agent peut oublier une consigne, pas un échec de contrôle. Le kit fournit les mécanismes ; le projet
fournit ses règles (dans son `docs/adaptation-du-kit.md`).

- **Lint et format** (`ruff` ou équivalent) : à chaque modification.
- **Règles d'import** : peu nombreuses, celles qui protègent les frontières importantes du projet.
- **Motifs interdits** : script qui cherche secrets en clair, appels réseau hors du module prévu, etc.
- **Interface** : script qui refuse tout style hors du système de design verrouillé (§2.11).

Ces contrôles sont des scripts : déterministes, en quelques secondes, sans consommer de raisonnement.

### 2.4 Une première tranche exemplaire

L'agent copie l'existant : la première fonctionnalité complète (source de données → service → écran)
sert de modèle à toutes les autres.

- Construite en premier, **seule**, relue à fond par un humain, une seule fois.
- Citée dans `CLAUDE.md` comme référence.
- Sert aussi à **calibrer l'évaluateur** (`08`, §3).

### 2.5 Des contextes courts

- **Une fonctionnalité par session**, puis contexte neuf. Raison : économie de tokens, traçabilité, et
  un `git revert` possible par fonctionnalité. (Anthropic n'impose plus les réinitialisations de contexte
  depuis Opus 4.5 ; nous les gardons pour ces raisons-là, pas par obligation.)
- La continuité passe par les fichiers (progression, liste, git log), pas par la mémoire du chat.
- **Rituel de début de session** : `pwd` ; lire `git log` et `claude-progress.txt` ; lancer `init.sh`
  et un test de bout en bout de base (l'application marche-t-elle encore ?) ; choisir la fonctionnalité
  non validée la plus prioritaire **qui m'est attribuée** ; commencer.
- Les conversations de cadrage suivent la même règle : **une conversation neuve par phase**, dans l'ordre
  de la feuille de route du projet, ouverte avec les fichiers listés pour cette phase.

### 2.6 Un nettoyage régulier de la dérive

Une fois par jalon (pas à chaque étape) : l'évaluateur compare le code aux ADR et à la spec, produit une
courte liste de refactorisations ; le générateur les applique dans une session dédiée.

### 2.7 On corrige le système, pas seulement le résultat

1. Corriger le code.
2. Transformer la correction en **règle**, **test** ou **contrôle**.
3. Si c'est une règle, l'ajouter à « Erreurs déjà rencontrées » dans `CLAUDE.md`.
4. Si c'est une erreur de **méthode**, l'ouvrir aussi dans `kit-agents` (nouvelle version du kit).

### 2.8 L'agent exécute la spec, il ne l'écrit pas

| Qui | Décide |
|---|---|
| Humain + planificateur | **Quoi** : périmètre, critères d'acceptation, **contrats** entre les parties, **style** |
| Agent de code | **Comment** : la façon technique d'y arriver, à l'intérieur des contrats et des ADR |

Les contrats sont figés avant tout lancement d'agent.

### 2.9 Ce qu'on retire à l'agent, et ce qu'on lui laisse

- **On retire** les décisions de périmètre, de dépendances (bibliothèques) et de goût : elles sont dans
  la spec, les ADR et le système de design. Ajouter une dépendance non listée dans une ADR est interdit.
- **On laisse** la réflexion technique. Sinon on retombe dans la sur-spécification.
- Un bon prompt d'agent est **court** : un objectif et ses critères. Le reste est dans des fichiers
  (skills, ADR, contrats) que l'agent ouvre quand il en a besoin.

### 2.10 Le parallélisme a des conditions

Plusieurs agents en même temps **si et seulement si** l'orchestrateur le vérifie mécaniquement :

1. **Dépôts différents** (ex. infrastructure et produit) : autorisé, sauf sur une ressource partagée
   déclarée dans `ENVIRONNEMENT.md` (une session qui redémarre une machine utilisée par une autre est
   interdite pendant que l'autre tourne : verrou).
2. **Même dépôt** : deux fonctionnalités en parallèle seulement si
   - aucune ne figure dans le `depends_on` de l'autre ;
   - leurs champs `touches` (dossiers modifiés) sont disjoints ;
   - aucune ne touche les fichiers partagés déclarés (`contrats/`, migrations, réglages, `CLAUDE.md`) ;
   - chacune a sa branche, son worktree et sa propre base de données de test.
3. **Jamais** en parallèle : la tranche exemplaire, une migration de schéma, une modification de contrat.
4. Au plus **3 agents** à la fois (au-delà, la relecture humaine décroche).
5. Fusion **une par une**, lancée par le pilote (`orchestre fusionner`) sur les branches qu'`orchestre`
   a classées « prêtes » (D29) ; CI revérifiée juste avant ; tests complets après chaque fusion ; un
   conflit renvoie la fonctionnalité en file d'attente, il n'est pas résolu par un agent.

### 2.11 Le style est décidé par l'humain et verrouillé par des outils

- Le système de design part d'un **kit d'interface existant**, choisi par l'humain parmi des candidats
  vérifiés (grille de vérification : `08`, §6). L'agent propose et vérifie ; il ne choisit jamais.
- Une fois choisi : ADR, **liste fermée** des composants autorisés, tokens (couleurs, typographie,
  espacements, rayons), **écrans de référence** validés, liste d'anti-motifs.
- Contrôle automatique (script) : pas de style en ligne, pas de couleur hors tokens, pas de classe ni de
  composant hors liste, pas de nouveau fichier CSS, pas de nouvelle dépendance front.
- L'évaluateur compare des captures d'écran aux écrans de référence.

### 2.12 Proportionnalité : ni surarchitecture, ni surcadrage

Le cadrage protège la qualité tant qu'il reste petit. Trop de règles, de couches et de documents la
dégradent : l'agent suit la forme au lieu du but, et le produit devient lourd à reprendre.

**Pour le code (règles données à chaque agent de code) :**

- Construire la version la plus simple qui remplit les `steps`. Rien « pour plus tard ».
- Aucune abstraction, couche, option de configuration ou classe générique sans **deux usages réels**
  dans `feature_list.json`. Au premier usage, on écrit le code directement.
- Aucune dépendance, aucun service, aucun fichier de configuration nouveau sans ADR.
- Une fonctionnalité qui dépasse sa session (contexte qui se remplit, diff qui dépasse nettement
  `touches`, plusieurs écrans) s'arrête : l'agent écrit `TROP GROS : <découpage proposé>` dans
  `claude-progress.txt` et le planificateur la découpe. Il ne la termine pas « en forçant ».

**Pour le cadrage (règles pour l'humain et le planificateur) :**

- Un document ne contient que ce que l'agent ne peut pas trouver dans le dépôt.
- Un prompt d'agent : un objectif, ses critères, les interdits. Pas de plan imposé.
- Un garde-fou (hook, règle, contrôle) n'est ajouté qu'**après** un incident réel ou pour une règle
  sans aucune exception, et il cite sa raison (§2.7). Une préférence reste dans `CLAUDE.md`.
- Une relecture cherche ce qui touche le fonctionnement, la sécurité et les contrats, **pas le style**
  (« skip style ») : un relecteur à qui on demande des problèmes en trouve toujours, et tout corriger
  ajoute des couches inutiles.

**Signal de dérive vers le lourd** : le récapitulatif de l'orchestrateur donne, par fonctionnalité,
le coût et la taille du diff. Une fonctionnalité deux fois plus grosse que les autres du même jalon
est relue par le responsable technique avant fusion.

---

## 3. Économie de tokens : ni surverification, ni sous-agents inutiles

### Vérification

| Ce qui vérifie | Quand | Coût |
|---|---|---|
| Lint, format, motifs interdits | À chaque modification, par hook | Quasi nul |
| Typage, règles d'import, tests rapides | En fin de session (hook `Stop`) | Faible |
| Test d'acceptation de la fonctionnalité | Par `marquer-valide`, avant `passes = true` | Faible |
| Tous les tests, hors de la machine de l'agent | CI à chaque envoi ; condition de fusion | Nul en tokens |
| Relecture du diff par un regard neuf | `/code-review` de Claude Code, une fois par fonctionnalité, avant fusion, « skip style » | Faible |
| Évaluateur (navigateur, sceptique) | Après la tranche exemplaire (calibration), puis à chaque jalon | Modéré |
| Relecture de sécurité | Une fois, avant la production | Modéré |
| Humain | Démo de jalon | Son temps |

Interdits :

- L'agent ne relit pas son propre code après coup « pour vérifier ».
- L'agent ne demande pas de confirmation : si les contrôles passent, il commit et continue.
- L'évaluateur ne relit pas le code ligne à ligne : il utilise l'application comme un utilisateur
  (sauf pendant la relecture de sécurité).

### Sous-agents

| Rôle | Agent séparé ? | Raison |
|---|---|---|
| Planificateur | La conversation de cadrage de chaque phase | Il fixe le cadre avec l'humain |
| Générateur | Une session neuve par fonctionnalité | Contexte court |
| Évaluateur | Oui, par jalon | Regard neuf et sceptique |
| Tâches simples (renommer, formater, chercher) | **Non** | Le coût de contexte dépasse le gain |

### Budget

Le coût de chaque session (`total_cost_usd` de `claude -p --output-format json`) est **toujours**
consigné dans `claude-progress.txt` : c'est gratuit. Un plafond (`--max-budget-usd`) n'est posé que là
où il est **nécessaire** : dans la boucle sans surveillance, comme garde-fou contre une session qui
tourne en rond (`07`, §5).

---

## 4. Contrôle des changements

1. Le changement passe par le planificateur, **jamais** par une consigne rapide dans le chat d'un agent.
2. Le planificateur met à jour `spec.md`, l'ADR concernée, `feature_list.json` et les tests d'acceptation.
3. Les fonctionnalités touchées repassent à `passes: false`.
4. Les agents reprennent à partir des fichiers mis à jour.

Les demandes nouvelles du commanditaire vont dans le backlog du projet, arbitrées à chaque démo.

---

## 5. Règles d'environnement

Le kit ne connaît aucune machine. Chaque dépôt d'infrastructure fournit un `ENVIRONNEMENT.md` qui déclare :
droits de l'agent par période, commandes et chemins interdits (paramètres du hook de protection),
ressources partagées (pour le verrou du §2.10), fenêtres pendant lesquelles aucune session ne doit tourner.

Règle du kit : **l'agent n'a jamais le root d'une machine qui en héberge d'autres.** Ce dont il a
besoin passe par deux portes, sans mot de passe et sans question : les droits de l'outil de la
machine (un jeton d'API limité, que l'agent ne lit pas) et une **liste fermée d'actions root**
(un script appelé par sudo, qui construit lui-même chaque commande). Une capacité qui manque devient
une nouvelle action, testée, relue et installée par l'opérateur.

---

## 6. Répartition de l'effort humain

| Moment | Effort humain |
|---|---|
| Besoins, spec, critères, choix du kit d'interface | Élevé : c'est là que tout se joue |
| Tranche exemplaire (et calibration de l'évaluateur) | Élevé, une seule fois |
| Jalons suivants | Faible : une démo par jalon |
| Changement d'avis | Modifier spec et tests via le planificateur |

---

## 7. L'équipe : rôles humains et rôles d'IA

On travaille comme une équipe d'ingénieurs. Chaque conversation ou session a **un** rôle d'IA, et
l'humain y tient **un** rôle, annoncé au début (« Rôle : … »). Une même personne peut tenir plusieurs
rôles humains, mais un seul à la fois par conversation.

### Rôles humains

| Rôle | Décide ou fait | Ne fait pas |
|---|---|---|
| **Décideur produit** | Le quoi : périmètre, priorités, critères d'acceptation, choix du style ; valide les démos | Choisir une technique |
| **Responsable technique** | Valide spec, contrats, ADR ; tranche les tests contestés et les `TROP GROS` ; accepte ou refuse une fusion signalée | Écrire le code |
| **Opérateur** | Tape les commandes sur les machines, fait le réseau, ouvre et ferme les fenêtres données réelles, installe les garde-fous | Laisser un agent toucher au réseau |
| **Recette** | Joue les parcours réels, compare aux `steps`, note les écarts | Corriger soi-même |
| **Relecteur externe** (si possible une autre personne) | Relit la tranche exemplaire et la sécurité avec un œil technique | — |

### Rôles d'IA

| Rôle | Où | Sous quel contrôle |
|---|---|---|
| **Planificateur** | Conversation de cadrage | Le décideur produit et le responsable technique valident |
| **Guide d'installation** | Conversation ; n'exécute rien | L'opérateur tape et colle les résultats |
| **Agent d'infrastructure** | Claude Code sur la machine d'infrastructure, sans root (droits de `ENVIRONNEMENT.md`) | Garde-fous du §5 ; demandes humaines |
| **Générateur** | Claude Code, une fonctionnalité par session | Contrôles, `marquer-valide`, CI |
| **Relecteur** | `/code-review` dans une session neuve | Le responsable technique lit le résumé |
| **Évaluateur** | Session séparée, par jalon | Seuils durs ; la recette confirme |

### Travailler en parallèle

- Quand un rôle d'IA tourne **sans surveillance** (générateur, agent d'infrastructure, évaluateur),
  l'humain prend un autre rôle dans une autre conversation : par exemple décideur produit pour la
  revue des besoins pendant que l'agent d'infrastructure prépare les LXC.
- Avant de changer de rôle, on note où on en est dans le fichier de la phase (une ligne suffit).
- Les **points de rendez-vous** (l'humain revient au rôle qui attend) : une `DEMANDE HUMAINE`, un
  `TEST CONTESTÉ`, un `TROP GROS`, une fusion signalée, une démo de jalon. On les traite au plus tard
  à la fin de la demi-journée.
- Jamais deux rôles d'IA sur la même ressource (§2.10) ; jamais l'opérateur et l'agent
  d'infrastructure sur la même machine en même temps.

---

## Sources

- Anthropic, *Effective harnesses for long-running agents* (26 novembre 2025) :
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, *Harness design for long-running application development* (24 mars 2026) :
  https://www.anthropic.com/engineering/harness-design-long-running-apps
- Claude Code, mémoire et `CLAUDE.md` : https://code.claude.com/docs/en/memory
- Claude Code, worktrees et sessions parallèles : https://code.claude.com/docs/en/common-workflows
- Claude Code, bonnes pratiques (règles imposées en petit nombre, relecture « skip style »,
  `/code-review`, `/verify`, hook `Stop`) : https://code.claude.com/docs/en/best-practices
