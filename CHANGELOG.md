# Journal des changements

## 1.0.0

Kit réduit à l'essentiel (`06` §2.12). Python 3, bibliothèque standard seulement ; chaque script
échoue fermé.

### Ajouté

- Hooks : `garde-secrets` (PreToolUse), `controles-rapides` (PostToolUse), `fin-de-session` (Stop :
  au plus 3 blocages par session, puis `ÉCHEC FIN DE SESSION`), `verrou-ressources` (PreToolUse).
- Scripts : `marquer-valide` (référence `origin/main`, conteneur Docker jetable, copie de travail en
  lecture seule), `installer`, `verifier-diff-liste`, `tout-verifier`, `orchestre` réduit ;
  `bin/kit_commun.py` (schéma de la liste et lancement d'un test, partagés par ces scripts).
- Modèles : `feature_list.schema.json`, `claude-progress.modele.txt`, `grille-evaluateur.md` (non
  calibrée), `ENVIRONNEMENT.modele.md`, `adaptation-du-kit.modele.md`, `ci/tests.yml`, prompts
  `initialisateur.md`, `agent-de-code.md`, `evaluateur.md`.
- Tests : un fichier par hook et par script (`tests/`), test générique de `garde-commandes` avec des
  règles inventées ; `tests/essai-bout-en-bout` (vrai Claude Code, lancé à la main) ; CI du kit
  (`.github/workflows/tests.yml`).
- README : table des références `06`, `07`, `08`.

### Corrigé

- `garde-commandes` : un chemin protégé **relatif** passait (`cd /etc && rm exemple-kit/x`, ou
  `rm exemple-kit/x` avec `cwd` = `/etc`). Les arguments, redirections et cibles de copie sont
  maintenant résolus depuis le dossier courant suivi. Test : `test_chemin_relatif_apres_cd`
  (rouge avec l'ancien moteur) ; les 84 + 15 cas d'une machine réelle restent verts.

### Contrat entre le kit et le projet (à lire avant d'installer)

- `init.sh` accepte `--controles <fichier>` (hook `controles-rapides`), `--rapide` (hook
  `fin-de-session`) et `--ci` (CI).
- `tests/acceptance/kit.json` : `{"image": "...", "commande": [..., "{test}"]}`. Il est lu **à la
  référence** par `marquer-valide`, donc protégé comme les tests.
- L'installateur ajoute `claude-progress.txt merge=union` à `.gitattributes` (pilote natif de git) :
  deux branches parallèles ajoutent chacune leur entrée sans conflit ; et `.kit/`,
  `.claude/worktrees/` à `.gitignore`.

### Vérifié dans la documentation (code.claude.com/docs, 19/11/2026) contre Claude Code 2.1.328

| Clé ou option | Constat | Effet sur le kit |
|---|---|---|
| `onFailure` | `"continue"` ou `"block"`, v2.1.295 ou plus ; **sans effet sur `Stop`** (ni `SubagentStop`) | Posé sur tous les hooks sauf `Stop` ; `orchestre` refuse une version < 2.1.295 |
| Codes de sortie | 2 bloque en PreToolUse et Stop ; en PostToolUse il montre seulement la sortie à l'agent ; 1 ne bloque jamais | Tous les refus sont en code 2 |
| `Stop` | Champs `stop_hook_active`, `last_assistant_message` ; plafond de **8** relances consécutives (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`) | Notre plafond de 3 par session reste plus strict |
| `permissions.deny` | **Les règles `Write(...)` ne s'appliquent pas** : seules `Edit(...)` et `Read(...)` comptent pour les outils de fichiers | Règles `Write(...)` retirées de `modeles/settings-produit.json` (écart avec `08` §4) |
| Chemins des règles | `chemin` = relatif au dossier courant, `/chemin` = relatif aux réglages, `//chemin` = absolu | Inchangé (le dossier courant est la racine du worktree) |
| `sandbox.*` | `enabled`, `allowUnsandboxedCommands`, `failIfUnavailable`, `filesystem.denyWrite/denyRead`, `network.allowedDomains`, `excludedCommands` existent. Linux : `bubblewrap` **et** `socat`. Les hooks tournent hors sandbox | Essai : sans `socat`, `claude` refuse bien de démarrer (« Refusing to start without a working sandbox ») |
| `excludedCommands` | Comparé au **texte** de l'appel ; motif avec ` *` pour les arguments | `"/opt/kit/bin/marquer-valide *"` au lieu du chemin seul |
| `attribution` | Objet `commit`, `pr`, `sessionUrl` ; `includeCoAuthoredBy` obsolète | Inchangé |
| `disableBypassPermissionsMode` | Valeur `"disable"` | Inchangé |
| `allowManagedHooksOnly` | Réglage **géré** seulement : bloque les hooks utilisateur, projet, local et plugins | Non utilisé par le kit. Sur une machine qui l'active, les hooks du kit doivent être dans les réglages gérés, sinon ils ne tournent pas |
| `claude -p` | Sans `--bare`, charge hooks et `CLAUDE.md` ; `--bare` deviendra le défaut et ignore les hooks même passés par `--settings` | `orchestre` ne passe jamais `--bare` |
| `system/init` | Liste modèle, outils, MCP, plugins, `claude_code_version`, `cwd`, `permissionMode` : **pas les hooks** (vérifié par un essai) | `orchestre` vérifie version et worktree dans `system/init`, puis les hooks par `--include-hook-events` (événements `hook_started` PreToolUse et Stop) ; un outil qui tourne sans hook arrête la session |
| `--max-budget-usd` | Print seulement ; estimation côté client, peut être dépassée | Seulement avec `orchestre --sans-surveillance` |
| `--worktree` | `.claude/worktrees/<nom>`, branche `worktree-<nom>`, part de la branche par défaut d'origin ; en `-p`, pas de nettoyage | `orchestre` renomme la branche en `agent/<id>` et retire le worktree après fusion |
| `/code-review` | Prend une branche, une plage (`main...branche`), un numéro de PR ; en `-p`, tourne au premier plan et rend le texte. **Essai** : `/code-review low origin/main...agent/F001` marche en `-p` ; sans constat il rend exactement `(none)` et ignore une consigne ajoutée au prompt système | `orchestre` l'appelle avant chaque fusion ; il fusionne seulement sur `(none)` ou `VERDICT : AUCUN BLOQUANT` ; tout autre texte = branche à relire (point de rendez-vous) |

### Essai de bout en bout (local, 19/11/2026, modèle haiku)

`tests/essai-bout-en-bout` : dépôt jetable et `origin` nu locaux, kit installé avec `--destination`,
`orchestre --ci locale`. Quatre passages ; les trois premiers ont trouvé des défauts, corrigés :

1. `garde-commandes` refusait `marquer-valide` (dossier du kit protégé par les règles) → note dans
   `modeles/ENVIRONNEMENT.modele.md` : mettre `marquer-valide` dans `lecture_seule`. Et `__pycache__`
   non ignoré dans le projet d'essai.
2. et 3. La relecture `/code-review` tournait avec les réglages du projet : `fin-de-session` la
   bloquait → `orchestre` pose `KIT_SESSION=relecture` pour elle seule, et sa réponse `(none)` est
   reconnue.
4. **Réussi** : F001 et F002 en parallèle, validées, relues, fusionnées une par une sans conflit,
   `tout-verifier` vert sur `main` ; F003 (test volontairement rouge) contestée par l'agent, jamais
   `passes: true`. Coût : 0,040 $. Coût total des quatre passages et des sondes : environ 0,24 $
   (estimations `total_cost_usd`).

Écart de l'essai : sandbox désactivé dans le dépôt jetable (`--sans-sandbox`), car `socat` manque sur
le poste et sudo est exclu pendant cette phase. Permissions et hooks restaient actifs.

## 0.0.0-pre

- Mise en place du dépôt : méthode, modèles et hook `garde-commandes` (dossier v4).
