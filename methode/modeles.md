# Modèles du kit

> **Couche : `kit-agents`.** Gabarits à copier dans chaque projet. Les noms de clés des réglages
> Claude Code sont ceux de la documentation au 17 novembre 2026 : **à revérifier en phase 0** contre
> la version installée (`claude --version`), car l'outil évolue chaque semaine.
> Version 4 (18/11/2026) : `marquer-valide` dans un bac à sable (§5), modèle de CI (§9), ligne
> `TROP GROS` (§2), portes d'accès dans `ENVIRONNEMENT.md` (§7).

---

## 1. `feature_list.json`

### Schéma

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["projet", "version_kit", "fonctionnalites"],
  "properties": {
    "projet": { "type": "string" },
    "version_kit": { "type": "string" },
    "fonctionnalites": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "besoin", "jalon", "priorite", "category", "description",
                     "steps", "test", "touches", "depends_on", "passes"],
        "additionalProperties": false,
        "properties": {
          "id":          { "type": "string", "pattern": "^F[0-9]{3}$" },
          "besoin":      { "type": "array", "items": { "type": "integer" },
                           "description": "N° des besoins du projet couverts" },
          "jalon":       { "type": "string", "description": "S1, S2… ou équivalent" },
          "priorite":    { "type": "integer", "minimum": 1 },
          "category":    { "enum": ["fonctionnel", "interface", "securite", "donnees", "infra"] },
          "description": { "type": "string", "maxLength": 200 },
          "steps":       { "type": "array", "minItems": 1, "items": { "type": "string" },
                           "description": "Étapes de vérification : entrée, action, résultat attendu" },
          "test":        { "type": "string", "description": "Chemin du test d'acceptation e2e" },
          "touches":     { "type": "array", "items": { "type": "string" },
                           "description": "Dossiers que la fonctionnalité a le droit de modifier" },
          "depends_on":  { "type": "array", "items": { "type": "string" } },
          "attribue_a":  { "type": ["string", "null"], "description": "Rempli par l'orchestrateur" },
          "passes":      { "type": "boolean" }
        }
      }
    }
  }
}
```

### Règles

- **Taille** : une fonctionnalité tient dans une session (repère : un écran ou un service, moins d'une
  demi-journée humaine). Un besoin peut donner plusieurs fonctionnalités. Si elle déborde, l'agent
  s'arrête et écrit `TROP GROS` (06, §2.12) au lieu de forcer.
- `passes` démarre à `false` et n'est modifié que par `marquer-valide` (§5).
- `touches` sert au parallélisme (06, §2.10) : le hook `fin-de-session` refuse un diff hors de `touches`.

### Exemple

```json
{
  "id": "F004",
  "besoin": [1],
  "jalon": "S1",
  "priorite": 4,
  "category": "fonctionnel",
  "description": "La fiche client affiche les contrats en cours de la société",
  "steps": [
    "Ouvrir la fiche de la société de test « Société A »",
    "La section Contrats liste les 2 contrats actifs du jeu de données, avec date de fin",
    "Un contrat expiré n'apparaît pas"
  ],
  "test": "tests/acceptance/test_f004_contrats.py",
  "touches": ["clients/", "templates/clients/"],
  "depends_on": ["F001", "F002"],
  "attribue_a": null,
  "passes": false
}
```

---

## 2. `claude-progress.txt`

Une entrée par session, ajoutée en fin de fichier :

```
=== 2026-12-03 14:10 | F004 | session abc123 | modèle <nom> ===
FAIT : <2 à 5 lignes>
ÉTAT : validée | en cours | bloquée
TEST CONTESTÉ : <id du test, raison> (sinon : aucun)
DEMANDE HUMAINE : <ce qui a été refusé et pourquoi c'était nécessaire> (sinon : aucune)
TROP GROS : <découpage proposé> (sinon : non)
PROCHAINE ÉTAPE : <1 ligne>
COÛT : <total_cost_usd> $
```

---

## 3. Grille de l'évaluateur

### Gabarit (livré en phase 0, **non calibré**)

| Critère | Ce qu'on regarde | Seuil (sur 10) |
|---|---|---|
| Fonctionnement | Chaque `steps` des fonctionnalités du jalon se reproduit dans le navigateur | 8 |
| Respect du système de design | Captures comparées aux écrans de référence ; aucun composant hors liste | 8 |
| Robustesse | Erreurs d'API simulées, champs vides, double clic, retour arrière | 6 |
| Conformité à l'architecture | Code comparé aux ADR et contrats (passe anti-dérive) | 7 |
| Sécurité (relecture avant production seulement) | Authentification, droits, validation humaine des écritures, secrets | 9 |

Un critère sous son seuil = jalon refusé, avec une liste de corrections exploitables.

### Calibration (après la tranche exemplaire)

1. L'évaluateur note la tranche exemplaire et 3 à 5 variantes volontairement dégradées.
2. L'humain note les mêmes cas.
3. Les écarts sont corrigés dans le prompt ; les cas notés par l'humain deviennent les exemples (few-shot).
4. On recommence au premier jalon si l'évaluateur diverge encore.

---

## 4. Réglages Claude Code (`.claude/settings.json` d'un dépôt de produit)

```json
{
  "attribution": { "commit": "", "pr": "", "sessionUrl": false },
  "permissions": {
    "deny": [
      "Edit(tests/acceptance/**)", "Write(tests/acceptance/**)",
      "Edit(feature_list.json)",   "Write(feature_list.json)",
      "Edit(.claude/**)",          "Write(.claude/**)",
      "Read(.env*)", "Read(**/secrets/**)"
    ]
  },
  "sandbox": {
    "enabled": true,
    "allowUnsandboxedCommands": false,
    "failIfUnavailable": true,
    "filesystem": {
      "denyWrite": ["tests/acceptance", "feature_list.json"],
      "denyRead": ["**/secrets"]
    },
    "network": {
      "allowedDomains": ["pypi.org", "files.pythonhosted.org", "github.com",
                         "objects.githubusercontent.com", "registry.npmjs.org"]
    },
    "excludedCommands": ["/opt/kit/bin/marquer-valide"]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [ { "type": "command", "command": "/opt/kit/hooks/garde-commandes", "onFailure": "block" },
                   { "type": "command", "command": "/opt/kit/hooks/verrou-ressources", "onFailure": "block" } ] },
      { "matcher": "Write|Edit|Bash",
        "hooks": [ { "type": "command", "command": "/opt/kit/hooks/garde-secrets", "onFailure": "block" } ] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [ { "type": "command", "command": "/opt/kit/hooks/controles-rapides" } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "/opt/kit/hooks/fin-de-session", "onFailure": "block" } ] }
    ]
  }
}
```

Points d'attention (phase 0) :

- `attribution` vide : aucun co-auteur Claude ni lien de session dans les commits et les demandes de
  fusion (D28). Forme objet plutôt que `"attribution": false` : `false` exige Claude Code v2.1.281 ou
  plus, et une version plus ancienne ignorerait alors **tout** le fichier de réglages.
- Hooks et `marquer-valide` vivent dans `/opt/kit/`, **hors du dépôt**, en lecture seule pour
  l'utilisateur qui fait tourner Claude. La doc prévient : exclure du sandbox un script situé dans le
  répertoire de travail permet à l'agent de le réécrire puis de le lancer hors sandbox.
- `onFailure: "block"` exige une version récente de Claude Code (v2.1.295 ou plus selon la doc).
- Chaque hook est testé volontairement : il doit bloquer ce qu'il doit bloquer, **et** bloquer quand on
  le fait planter exprès.

---

## 5. `marquer-valide <id>`

Seul chemin pour passer `passes` à `true`. Il est exclu du sandbox (il doit écrire
`feature_list.json`), donc **il n'exécute jamais lui-même le code de l'agent**.

1. Vérifie que `<id>` existe et que ses `depends_on` sont validés.
2. Prend `feature_list.json` et le dossier `tests/acceptance/` **dans la branche de référence**
   (`git show <référence>:…`), jamais dans la copie de travail de l'agent.
3. Lance le test dans un **bac à sable jetable** : conteneur (Docker ou Podman) détruit à la fin,
   copie de travail montée en **lecture seule**, tests de la référence copiés dedans, réseau limité
   aux faux serveurs, aucune variable de secret. À défaut de conteneur : un utilisateur dédié sans
   droit d'écriture sur le dépôt.
4. Si le test passe : écrit `"passes": true` pour cet `id` uniquement, et rien d'autre.
5. Sinon : n'écrit rien, renvoie la sortie du test (code 1).
6. Journalise l'appel (date, id, résultat, empreinte du commit) dans `.kit/journal-validations.log`.

Tests obligatoires (phase 0) : un test rouge ne valide pas ; un code d'agent qui essaie d'écrire
`feature_list.json` ou `tests/acceptance/` pendant le test échoue (lecture seule) ; un test modifié
dans la copie de travail est ignoré (c'est celui de la référence qui tourne).

Une fonctionnalité repasse à `false` seulement par le planificateur (changement de spec, 06 §4).

---

## 6. Grille de vérification d'un kit d'interface existant

L'agent prépare **2 à 3 candidats** ; l'humain choisit. Chaque candidat est noté sur :

| Critère | Vérification |
|---|---|
| Licence | Compatible avec un usage commercial interne ; texte de licence lu et cité |
| Vie du projet | Dernière version de moins de 6 mois ; corrections de sécurité récentes ; nombre de mainteneurs |
| Compatibilité | Fonctionne avec la pile du projet sans chaîne de construction lourde |
| Composants | Couvre les écrans de référence sans composant maison (formulaire, tableau, onglets, modale, alertes, badges) |
| Accessibilité | Contrastes, clavier, attributs ARIA documentés |
| Langues | Pas de texte figé en anglais dans les composants ; formats de date FR/NL |
| Thème | Tokens modifiables en un seul endroit |
| Poids et dépendances | Taille livrée ; aucune dépendance non maintenue |
| Démonstration | Les écrans de référence montés avec ce kit, en captures |

Le choix de l'humain devient une ADR. À partir de là, le kit d'interface, sa version et la liste des
composants autorisés sont figés ; en changer passe par le contrôle des changements (06, §4).

---

## 7. Modèle de `ENVIRONNEMENT.md` (dans chaque dépôt d'infrastructure)

```
# Environnement : <machine>
## Périodes et droits de l'agent
| Période | Machine | Droits | Garde-fous |
## Commandes interdites (lues par garde-commandes)
## Chemins interdits en lecture
## Ressources partagées (verrous)
## Fenêtres sans session agent
## Portes d'accès de l'agent (pas de root) : jeton d'API et ses droits, actions root permises
## Risques acceptés, avec garde-fous de remplacement
```

## 8. Modèle de `docs/adaptation-du-kit.md` (dans chaque dépôt de produit)

```
# Adaptation du kit au projet <nom>
- Version du kit : <étiquette>
- Pile et dépendances autorisées (renvoi vers les ADR)
- Structure des modules et règles d'import
- Motifs interdits propres au projet
- Skills du projet
- Tranche exemplaire (chemin)
- Données de développement (origine, règles)
- Critères d'évaluation propres au projet
- Offre Claude utilisée et données que Claude lit
```

## 9. Modèle d'intégration continue (`.github/workflows/tests.yml`)

Contrôle final, hors de la machine de l'agent. Gratuit sur GitHub pour un usage modéré ; à vérifier
dans les quotas de l'offre de l'organisation.

```yaml
name: tests
on: [push, pull_request]
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Kit à la version du projet (.kit-version)
        uses: actions/checkout@v4
        with: { repository: "<organisation>/kit-agents", ref: "<étiquette de .kit-version>", path: kit }
      - name: Tests d'acceptation et liste inchangés (sauf « passes »)
        run: |
          git diff --exit-code origin/main -- tests/acceptance/
          python3 kit/bin/verifier-diff-liste origin/main feature_list.json
      - name: Tous les contrôles
        run: ./init.sh --ci && ./kit/bin/tout-verifier
```

`verifier-diff-liste` et `tout-verifier` sont fournis par le kit (phase 0). L'installateur remplace les
deux valeurs entre chevrons. Le dépôt du kit étant public, la CI le lit sans clé. Sur `main` elle-même,
la première étape compare au commit précédent.

