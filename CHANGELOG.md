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
- Consigne de relecture d'`orchestre` : la dernière ligne de la réponse est le verdict seul, sans
  rien d'autre sur la ligne ni après. La règle de lecture ne change pas (dernière ligne non vide ;
  tout doute = « à relire »). Test : assertion sur la consigne dans
  `test_deux_en_parallele_pretes_puis_fusionnees_par_le_pilote`.
- Essai de bout en bout sur cet état, lancé par le pilote le 20/11/2026, **avec le sandbox** (sans
  `--sans-sandbox`), modèle haiku : « ESSAI DE BOUT EN BOUT : RÉUSSI ». Détail F001/F002/F003 et
  coût non relevés.

### Corrigé après la relecture neuve de la PR #1 (20/11/2026, verdict BLOQUANT)

- **Faux récapitulatif** : `orchestre fusionner` ne prend plus « le dernier fichier de `.kit/` ».
  `orchestre` affiche l'empreinte sha256 du récapitulatif JSON qu'il écrit ; le pilote la donne à
  `orchestre fusionner --recapitulatif <empreinte>`, qui ne lit que le fichier de même empreinte. Un
  fichier déposé par du code de l'agent (test, `init.sh` lancé sur l'hôte) ne porte pas l'empreinte
  affichée au pilote ; un récapitulatif retouché ne correspond plus. Test :
  `test_faux_recapitulatif_depose_par_l_agent_non_fusionne`.
- **`marquer-valide --reference`** : seule une valeur qui se résout en `refs/remotes/origin/main`
  (`git rev-parse --symbolic-full-name --end-of-options`) est admise (D25) ; une valeur en `-` est
  refusée avant tout appel à git. Test : `test_reference_autre_que_origin_main_refusee`.
- **D28 avant chaque push** : `kit_commun.ecarts_d28` parcourt `git log origin/main..<sha>` (auteur,
  committer, message) et refuse un `Co-Authored-By`, `anthropic.com` ou un auteur autre que le pilote
  (identité git configurée là où tourne `orchestre`). Appelé par `ci_github` (pas de push),
  `fusionner_branche` (fusion annulée) et `ci_locale`. Même contrôle dans le modèle de CI par le
  nouveau `bin/verifier-auteurs` (variables `vars.KIT_PILOTE_NOM`, `vars.KIT_PILOTE_COURRIEL`,
  absentes = rouge). Tests : `test_d28_refuse_le_push_d_un_commit_co_signe`,
  `test_ci_rouge_si_commit_hors_d28`.
- **Erreur sur une branche** (branche `agent/<id>` déjà présente, HEAD détaché) : la branche est « à
  relire » avec la raison, les autres sont évaluées et le récapitulatif est écrit. Test :
  `test_erreur_sur_une_branche_n_arrete_pas_le_lot`.
- **CI locale** : `init.sh` absent de la référence = rouge (n'était pas vérifié) ; `init.sh --ci` hors
  délai = rouge (arrêtait `orchestre`). Tests : `test_ci_locale_rouge_sans_init_sh`,
  `test_ci_locale_rouge_au_delai`.
- Preuve que les hooks sont chargés : un `hook_response` PreToolUse qui porte la marque
  « garde-commandes : autorisé » (que `garde-commandes` écrit maintenant sur sa sortie quand il
  laisse passer), et non n'importe quel hook PreToolUse. Test :
  `test_hook_pre_tool_use_autre_que_garde_commandes_arrete`.
- Tout signal non vide de `claude-progress.txt` (`TEST CONTESTÉ`, `DEMANDE HUMAINE`, `TROP GROS`,
  `ÉCHEC FIN DE SESSION`) rend la branche « à relire ». Test : `test_signal_non_vide_a_relire`.
- Push `HEAD:main` refusé après la fusion locale : retour à `ORIG_HEAD`, branche signalée non
  fusionnée. Test : `test_push_refuse_annule_la_fusion_locale`.
- Tests qui demandent Docker : sautés (`skipUnless`) là où Docker manque ; la CI du kit les lance.
- `tests/essai-bout-en-bout` passe l'empreinte affichée par `orchestre` à `orchestre fusionner`.

### Corrigé après la 3e relecture neuve de la PR #1 (26/11/2026, verdict BLOQUANT)

Périmètre choisi par le pilote : corriger ce qui sert avant le point de contrôle ; bloquer
`orchestre`, qui ne sert pas avant (D31) ; ses constats ouverts sont listés plus bas.

- **D28** : `kit_commun.ecarts_d28` refuse aussi « Generated with Claude Code » et les liens
  `claude.com/claude-code` et `claude.ai/code` (liens de session), en plus de `Co-Authored-By` et
  `anthropic.com` (`MOTIFS_D28`). Même contrôle pour `orchestre`, `bin/verifier-auteurs` et le modèle
  de CI. Tests : `test_d28_refuse_le_push_d_un_commit_co_signe`, `test_ci_rouge_si_commit_hors_d28`.
- **Référence en nom complet** : `REFERENCE = "refs/remotes/origin/main"` partout (`orchestre`,
  `fin-de-session`, `controles-rapides`, `lancer_init`, `marquer-valide`). Une branche locale nommée
  `origin/main` ne la remplace plus. Test : `test_reference_en_nom_complet`.
- **`orchestre` bloqué avant le point de contrôle (D31)** : sans `--essai-du-kit`, le lot comme
  `orchestre fusionner` refusent (code 2). L'option est réservée aux tests du kit et à
  `tests/essai-bout-en-bout`. Test : `test_bloque_avant_le_point_de_controle`.

### Corrigé après la 4e relecture neuve de la PR #1 (26/11/2026, verdict BLOQUANT)

Périmètre choisi par le pilote : constats 1, 2, 3 et 6, mineurs « test du nom complet » et
« abréviation » ; constats 4 et 5 vérifiés ou listés ci-dessous.

- **Référence en nom complet dans le modèle de CI** : `BASE=refs/remotes/origin/main`. Une
  étiquette `origin/main` posée par l'agent ne la remplace plus. Test :
  `test_ci_etiquette_origin_main_ne_trompe_pas`.
- **`.github/` protégé** : règles `Edit` et `denyWrite` du modèle de réglages, `fin-de-session`,
  CI du modèle sur les branches. Tests : `test_github_et_configuration_des_tests_proteges`,
  `test_ci_rouge_si_github_ou_configuration_des_tests_changent`.
- **Configuration du lanceur de tests protégée** (`conftest.py` à tout niveau, `pytest.ini`,
  `tox.ini`, `setup.cfg`, `pyproject.toml`, `sitecustomize.py`, `usercustomize.py` ;
  `kit_commun.CONFIG_TESTS`) : mêmes protections, et `marquer-valide` refuse de lancer le test si
  elle diffère de la référence. Seul le pilote la change, sur `main`. Test :
  `test_configuration_des_tests_modifiee_refusee`.
- **Fusion faite sur GitHub** : sur `main`, `verifier-auteurs --fusion-github` admet le committer
  « GitHub <noreply@github.com> » si l'auteur est le pilote. Test :
  `test_ci_de_main_admet_la_fusion_faite_sur_github`.
- `orchestre` : `allow_abbrev=False` (« --essai » ne débloque plus).
- Constat 4 (commande composée après `marquer-valide` hors sandbox) : **fermé par la doc**.
  code.claude.com/docs/en/sandboxing (lu le 26/11/2026) : « Every command in the call has to
  match: `npm ci && docker compose build` stays sandboxed unless another entry covers `npm ci` » ;
  une redirection, un `cd` ou un `$(...)` gardent aussi l'appel dans le sandbox.

### Corrigé après la 5e relecture neuve de la PR #1 (26/11/2026, verdict BLOQUANT)

Règle du pilote : la relecture juge seulement si les corrections ferment leur constat et si elles
cassent quelque chose. 2e et dernière correction permise sur les constats 2 et 3.

- **Configuration du lanceur de tests à tout niveau** (`kit_commun.NOMS_CONFIG_TESTS` : ajout de
  `.pytest.ini` et `pytest.toml` ; `**/` pour tous) ; `marquer-valide` compte aussi, à la racine et
  dans `tests/` (les dossiers que pytest lit pour un test d'acceptation), les fichiers
  ignorés par git (le conteneur de test reçoit toute la copie de travail). Tests :
  `test_configuration_des_tests_modifiee_refusee`, `test_github_et_configuration_des_tests_proteges`,
  `test_ci_rouge_si_la_configuration_des_tests_change`.
- **CI de branche** : la configuration des tests est comparée au point de départ de la branche
  (`merge-base`), plus au `main` actuel. Test : `test_ci_de_branche_ignore_les_changements_de_main`.
- **`.github/` dans la CI** : contrôle retiré, il ne pouvait rien prouver (GitHub lance le workflow
  de la branche). Limite décrite dans `methode/modeles.md` §9 et dans « Limites connues ».
- **Consigne de l'agent** (`modeles/prompts/agent-de-code.md`, `methode/methode.md`) : `init.sh`,
  `.github/` et la configuration des tests sont interdits ; une dépendance passe par une
  `DEMANDE HUMAINE`.
- Réglages : `denyWrite` aligné (racine et `tests/`), texte de `architecture.md` corrigé ; tests des
  nouvelles règles et de `--essai` refusé.

### Corrigé après la 6e relecture neuve de la PR #1 (26/11/2026, 3e correction autorisée par le pilote)

- `test_ci_de_branche_ignore_les_changements_de_main` prouve maintenant la correction : branche en
  retard sur `main`, sans fusion (verte), puis branche qui change `pyproject.toml` après avoir
  fusionné `main` (rouge). Il échoue sur le code d'avant `be5f6c8`.
- La limite de `.github/` est dite de la même façon partout (`kit_commun.py`, `methode/modeles.md`
  §9, « Limites connues ») : seul filet sûr, la relecture neuve. CODEOWNERS n'est plus proposé.

### Limites connues : constats ouverts sur `orchestre` (à corriger avant le point de contrôle)

Relevés par la relecture du 26/11/2026 ; `orchestre` reste bloqué tant qu'ils sont ouverts.

1. Signal de `claude-progress.txt` ignoré quand sa valeur commence par « aucun », « aucune » ou
   « non » (seul le premier mot est lu, `bin/orchestre`, signaux).
2. Signal invisible si l'en-tête n'est pas écrit exactement (espaces, puce, gras, minuscules, accent
   absent ou décomposé).
3. Après chaque fusion, seuls les tests d'acceptation (`tout-verifier`) repassent : ni
   `init.sh --ci` ni les contrôles de la CI sur le résultat fusionné.
4. Avec `--ci github`, la CI « revérifiée » avant fusion est l'ancien run du même sha, calculé contre
   l'ancien `main`.
5. Une erreur dans la CI ou la relecture d'une branche arrête encore tout le lot (et, dans
   `fusionner`, saute les branches suivantes).
6. « (none) » en dernière ligne suffit, même quand la relecture liste des constats plus haut. La
   lecture du verdict a déjà eu deux corrections : à reprendre avec le pilote.
7. (mineur) Modèle de CI : sur `main`, `BASE=HEAD~1` au lieu de `github.event.before`.
8. (mineur) `fusionner` prend `--ci` de la ligne de commande au lieu du récapitulatif.

Autres limites connues (relecture du 26/11/2026, à traiter en v1.1 avant la phase 6) :

- **`.github/`** : la CI ne le protège pas (GitHub lance le workflow de la branche, qui peut retirer
  tous ses contrôles). Sur la machine de l'agent, `Edit`, `denyWrite` et `fin-de-session` le
  refusent, mais un commit construit sans écrire de fichier les passe. Seul filet sûr : la relecture
  neuve (D27). Pour une branche qui modifie `.github/`, aucun « filet : la CI » ci-dessous ne vaut.
  CODEOWNERS avec revue obligatoire ne convient pas sous D28 ; autre protection côté GitHub à
  étudier avec le pilote.

- Code de l'agent dans le même processus que le test : un module importé par le test peut encore
  fausser son résultat (par exemple `os._exit(0)`). Filet : la relecture neuve (D27) lit tout le
  diff.
- L'agent peut déplacer `refs/remotes/origin/main` sur sa machine (`git update-ref`) : les contrôles
  locaux lisent alors son commit. Filet : la CI, qui part d'un clone propre (sauf `.github/`).
- `MOTIFS_D28` cherche des sous-chaînes : un message qui cite la règle (comme celui de ces
  corrections) est refusé dans un projet ; « Generated by Claude Code » passe.
- `orchestre` (bloqué) : `ci_locale` ne vérifie pas encore la configuration des tests.
- `fin-de-session` ne compare que la copie de travail au point de départ : un commit construit sans
  écrire de fichier (`git update-index`, `commit-tree`) passe le hook. Filet : la CI pour
  `tests/acceptance/`, `init.sh` et la configuration des tests ; pour `.github/`, la relecture seule.
- `fin-de-session` ne contrôle les « touches » que si `KIT_FONCTIONNALITE` est posée ou si le nom de
  la branche contient `Fxxx` : nommer le worktree `F00x`.

## 0.0.0-pre

- Mise en place du dépôt : méthode, modèles et hook `garde-commandes` (dossier v4).
