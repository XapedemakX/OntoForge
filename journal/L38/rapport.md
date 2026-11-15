# L38 : Krakie dans les Paramètres

Demande de Jerem : « je veux que Krakie soit également disponible dans les paramètres pour aider à configurer ». Décision : D-L38-01. Contrat : `docs/CONTRACTS.md` §14. Lot : `lots/L38.md`.

## Fait
- **Front** : l'aquarium et le panneau sont montés sur `#/parametres` sans projet (`Shell.tsx`, `AssistantDock` avec `p = null`). Mode « paramètres » : conversation propre (`__settings`), pas d'actions de modèle, pas d'import de document, pas de plein écran, aucun contexte projet envoyé. Le contexte est l'onglet affiché (ligne « Paramètres · Fournisseurs LLM »), publié par `Settings.tsx` ; deux suggestions par onglet. Correction au passage : le panneau lit le contexte déjà publié à son abonnement (il le ratait au premier chargement).
- **Backend** : `POST /api/assistant/chat` accepte `project_id` absent pour `context.screen = settings` (422 sinon ; chemin projet inchangé). Nouveau `assistant/settings_help.py` : instantané non sensible, sujet de la question (six onglets), réponses déterministes fr / en (état, puis pas à pas Anthropic, compatible OpenAI, Ollama avec le piège « localhost dans Docker », endpoint SPARQL, versions, langues, valeurs par défaut, affichage), intentions aide, test, diagnostic, « montre-moi ma clé ». Avec un fournisseur réel : prompt `[TASK:settings]`, actions revalidées ; en cas d'échec du LLM, réponse intégrée avec avertissement.
- **Cartes** : `settings_goto` (onglet + défilement + contour de mise en évidence), `settings_test` (réutilise `POST /api/settings/providers/{id}/test` et `/endpoints/{id}/test`, résultat dans la carte ; jamais pour `mock` ni pour un fournisseur non configuré), `help` (`settings-<onglet>` dans `help_map.json`).
- **Aide** : « ? » sur les Paramètres et carte d'aide ouvrent la section de l'onglet ; le guide s'ouvre sans projet (`#/aide/<page>/<ancre>`, `Documentation` accepte `p` absent). Le guide décrit chaque onglet dans une sous-section à ancre (`parametres-fournisseurs-llm`, `-langues`, `-valeurs-par-defaut`, `-endpoints-sparql`, `-affichage`) + « Krakie dans les Paramètres » ; fr et en.
- **Docs** : guide utilisateur fr/en, API fr/en, limites fr/en, CHANGELOG fr/en, CONTRACTS §14, decisions. Captures `krakie-parametres` fr et en (`tools/docs/captures-list.mjs`).
- **Recettes** : `tools/recette/l38_settings_krakie.mjs` (nouveau) ; `english_scan.mjs` scanne aussi Krakie sur les Paramètres et ouvre le panneau par Ctrl+K (le clic sur `button.ag-fab` expirait depuis L37b : le bouton ne capte plus que Krakie et le récif, le scan du panneau de projet ne s'exécutait donc plus).

## Confidentialité (le point dur)
- Le contexte envoyé au LLM est `snapshot()` : par fournisseur id, nom, type, modèle, URL nettoyée (sans `user:pass@`, sans `?token=`, sans fragment), `configured`, `has_key` oui/non ; par endpoint URL nettoyée, type d'authentification, `has_secret` oui/non. Jamais la clé, ses 4 derniers caractères, un nom d'utilisateur, `extra`.
- `redact` masque les secrets enregistrés et les formes usuelles (`sk-ant-`, `sk-`, `Bearer`, GitHub, JWT, `password=`) dans les messages, dans le message système final, dans la réponse et dans les cartes.
- Tests (`tests/test_settings_assistant.py`) : l'instantané ne contient aucun secret ; un faux LLM enregistreur ne reçoit aucun secret (historique piégé compris) ; sa réponse piégée est nettoyée avant retour ; « quelle est ma clé ? » est refusée ; les mots ordinaires ne sont pas masqués ; les réglages sont identiques avant et après. La recette vérifie, dans le navigateur, qu'aucune requête ni réponse `/api/assistant` ne contient la fausse clé enregistrée par l'interface.

## Vérifié
- `pytest -q` : 1050 réussis (1018 avant, 32 nouveaux). `npm run build` OK.
- Recette L38 : 37/37 (ports 8983 / 4983) : sans projet, aquarium visible, contexte dès le chargement, pas à pas en mode mock, cartes, « Aller à cette section » (onglet + contour), « Ouvrir l'aide », « ? » sur trois onglets, test de connexion, aucune clé dans le trafic (20 échanges), réglages inchangés, aucun projet créé, anglais, aquarium sans recouvrement sur les six onglets (desktop) et en mobile.
- `e2e_ui.mjs` 30/30 ; `test_help_map` et `test_docs_bilingual` verts ; `english_scan` : 80 vues, 0 texte suspect (dont Krakie sur les Paramètres) ; `tour` : 49/49.
- Captures dans `journal/L38/screens/` : clair / sombre, desktop / mobile, panneau fermé et ouvert, section mise en évidence, guide ouvert, anglais.

## Aquarium
Sur les Paramètres le récif ne couvre rien : le contenu s'arrête bien au-dessus (la page garde 72 px de marge basse, `.set-page`). Pas besoin de `data-ag-floor`. Le contrôle de la recette compare, à chaque onglet et en haut comme en bas de page, les boîtes des contrôles et des textes avec celle du bouton flottant.

## Points d'attention
- Prompt `[TASK:settings]` non éprouvé sur un vrai fournisseur (pas de réseau en test), comme `[TASK:agent]`.
- `GET /api/settings` renvoie les URL telles que saisies : un identifiant collé dans une URL (`https://user:mdp@hote`) est visible dans l'écran Paramètres lui-même. Krakie, elle, ne les voit pas. À traiter dans un lot à part (nettoyage à la saisie ou refus des URL à identifiants).
- Le contexte de Krakie sur les Paramètres n'inclut pas l'état « Affichage » (bandeau) : il est stocké dans le navigateur, pas sur le serveur.
- Régénérer les captures du guide avec `tools/docs/captures.mjs` réécrit toutes les images (le script d'optimisation repasse sur tout le dossier, sans pngquant) : les deux nouvelles captures ont été optimisées à part pour ne pas bruiter le dépôt.
- Les recettes `e2e_ui` réécrivent `journal/L14/screens/` : commit à part « recettes : captures régénérées ».
