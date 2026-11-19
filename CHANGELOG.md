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
| `permissions.deny` | **Les règles `Write(...)` ne s'appliquent pas** : seules `Edit(...)` et `Read(...)` comptent pour les outils de fichiers | Règles `Write(...)` retirées de `modeles/settings-produit.json` et de `08` §4 |
| Chemins des règles | `chemin` = relatif au dossier courant, `/chemin` = relatif aux réglages, `//chemin` = absolu | Inchangé (le dossier courant est la racine du worktree) |
| `sandbox.*` | `enabled`, `allowUnsandboxedCommands`, `failIfUnavailable`, `filesystem.denyWrite/denyRead`, `network.allowedDomains`, `excludedCommands` existent. Linux : `bubblewrap` **et** `socat`. Les hooks tournent hors sandbox | Essai : sans `socat`, `claude` refuse bien de démarrer (« Refusing to start without a working sandbox ») |
| `excludedCommands` | Comparé au **texte** de l'appel ; motif avec ` *` pour les arguments | `"/opt/kit/bin/marquer-valide *"` au lieu du chemin seul |
| `attribution` | Objet `commit`, `pr`, `sessionUrl` ; `includeCoAuthoredBy` obsolète | Inchangé |
| `disableBypassPermissionsMode` | Valeur `"disable"` | Inchangé |
| `allowManagedHooksOnly` | Réglage **géré** seulement : bloque les hooks utilisateur, projet, local et plugins | Non utilisé par le kit. Sur une machine qui l'active, les hooks du kit doivent être dans les réglages gérés, sinon ils ne tournent pas |
| `claude -p` | Sans `--bare`, charge hooks et `CLAUDE.md` ; `--bare` deviendra le défaut et ignore les hooks même passés par `--settings` | `orchestre` ne passe jamais `--bare` |
| `system/init` | Liste modèle, outils, MCP, plugins, `claude_code_version`, `cwd`, `permissionMode` : **pas les hooks** (vérifié par un essai) | `orchestre` vérifie version et worktree dans `system/init`, puis les hooks par `--include-hook-events` : un outil qui tourne avant tout `hook_started` PreToolUse arrête la session ; le hook Stop doit avoir un `hook_response` en `exit_code` 0, `outcome` `success` (format vérifié par une sonde : un Stop en code 1 laisse la session finir en `success`) |
| `--max-budget-usd` | Print seulement ; estimation côté client, peut être dépassée | Seulement avec `orchestre --sans-surveillance` |
| `--worktree` | `.claude/worktrees/<nom>`, branche `worktree-<nom>`, part de la branche par défaut d'origin ; en `-p`, pas de nettoyage | `orchestre` renomme la branche en `agent/<id>` et retire le worktree après fusion |
| `/code-review` | Prend une branche, une plage (`main...branche`), un numéro de PR ; en `-p`, tourne au premier plan et rend le texte. **Essai** : `/code-review low origin/main...agent/F001` marche en `-p` ; sans constat il rend exactement `(none)` et ignore une consigne ajoutée au prompt système | `orchestre` l'appelle sur chaque branche candidate, dans un checkout propre de `origin/main` ; « prête » seulement si la **dernière ligne non vide** vaut exactement `(none)` ou `VERDICT : AUCUN BLOQUANT` ; tout autre texte = branche à relire |

### Essai de bout en bout (local, 19/11/2026, modèle haiku)

`tests/essai-bout-en-bout` : dépôt jetable et `origin` nu locaux, kit installé avec `--destination`,
`orchestre --ci locale`. Quatre passages ; les trois premiers ont trouvé des défauts, corrigés :

1. `garde-commandes` refusait `marquer-valide` (dossier du kit protégé par les règles) → note dans
   `modeles/ENVIRONNEMENT.modele.md` : mettre `marquer-valide` dans `lecture_seule`. Et `__pycache__`
   non ignoré dans le projet d'essai.
2. et 3. La relecture `/code-review` tournait avec les réglages du projet : `fin-de-session` la
   bloquait (voir plus bas : elle tourne désormais dans un checkout propre de la référence), et sa
   réponse `(none)` est reconnue.
4. **Réussi** : F001 et F002 en parallèle, validées, relues, fusionnées une par une sans conflit,
   `tout-verifier` vert sur `main` ; F003 (test volontairement rouge) contestée par l'agent, jamais
   `passes: true`. Coût : 0,040 $. Coût total des quatre passages et des sondes : environ 0,24 $
   (estimations `total_cost_usd`).

Écart de l'essai : sandbox désactivé dans le dépôt jetable (`--sans-sandbox`), car `socat` manque sur
le poste et sudo est exclu pendant cette phase. Permissions et hooks restaient actifs.

### Corrigé après la relecture de la PR #1

- **D29** : `orchestre` ne fusionne plus jamais seul dans `main`. Il classe chaque branche « prête »
  (CI verte, verdict de relecture valable, diff dans `touches`) ou « à relire », dans son
  récapitulatif (`.kit/recapitulatif-*.md` et `.json`). Nouvelle commande `orchestre fusionner`,
  lancée par le pilote : fusionne une par une les branches « prêtes » du dernier récapitulatif, si
  elles n'ont pas bougé, en revérifiant la CI juste avant.
- Exemption de relecture supprimée : `fin-de-session` ne lit plus aucune variable de session ; la
  relecture tourne dans un checkout propre de `origin/main` et, sans diff, `fin-de-session` n'a rien
  à contrôler. Test : `test_kit_session_n_exempte_plus_rien`.
- `orchestre` lance chaque session avec un environnement sans aucune variable `KIT_*` de l'hôte, sauf
  `KIT_FONCTIONNALITE` qu'il pose. Test : `test_environnement_sans_variables_kit_de_l_hote`.
- `init.sh` appartient à la référence : `controles-rapides`, `fin-de-session` et la CI locale
  d'`orchestre` lancent la version de `origin/main` (`git show`) ; `fin-de-session` refuse un diff
  sur `init.sh` ; la CI échoue si `init.sh` diffère de `origin/main` ; règles `Edit(init.sh)`,
  `Edit(.claude/**)`, `Edit(~/.claude/**)` et mêmes chemins dans `sandbox.filesystem.denyWrite`.
  (`marquer-valide` et `tout-verifier` ne lancent pas `init.sh`.) Tests :
  `test_init_modifie_par_l_agent_non_execute` (deux hooks),
  `test_ci_rouge_si_init_sh_differe_de_la_reference`, `test_init_sh_et_reglages_proteges`.
- `orchestre` lit le résultat du hook Stop (`hook_response`) : sauté, sans résultat ou code ≠ 0 =
  « à relire ». Tests : `test_hook_stop_saute_a_relire`, `test_hook_stop_en_echec_a_relire`.
- Verdict de relecture : seule la dernière ligne non vide compte. Test :
  `test_verdict_cite_plus_haut_et_commentaire_piege_a_relire`.
- Essai de bout en bout refait (haiku, `--sans-sandbox`) : hook Stop lu en `exit_code` 0 / `success`
  pour les trois sessions ; F002 « prête » puis fusionnée par `orchestre fusionner` ; F001 validée
  mais « à relire », car la relecture a répondu `(none)` suivi d'un paragraphe ; F003 jamais
  validée ; `orchestre` seul n'a rien fusionné. Coût : 0,045 $. L'essai vérifie désormais que les
  branches fusionnées sont exactement les « prêtes ».
- Faux `claude` des tests : `git worktree add --no-track` (trois créations simultanées se
  disputaient `.git/config` : échec intermittent d'un test sur huit environ).
- Méthode : `08` §4 sans règles `Write(...)` ni `onFailure` sur `Stop` ; `08` §10 décrit les
  mécanismes gardés (`init.sh --controles/--rapide/--ci`, `tests/acceptance/kit.json`,
  `claude-progress.txt merge=union`) ; `07` §5 : `system/init` ne liste pas les hooks, `(none)` de
  `/code-review -p`, règle de fusion D29 ; `06` §2.2 et §2.10 alignés.

## 0.0.0-pre

- Mise en place du dépôt : méthode, modèles et hook `garde-commandes` (dossier v4).
