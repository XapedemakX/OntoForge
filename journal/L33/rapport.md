# L33 : documentation en anglais

## Livré
- `utilisateur.en.md`, `limites.en.md`, `contribuer.en.md`, `api.en.md`, `CHANGELOG.en.md` (changelog traduit en entier). `deploiement.md` n'existe pas : rien à traduire.
- Traduction rédigée en anglais technique (voix active, phrases courtes, pas de tirets longs dans les listes, gras rare). Blocs de code, commandes, chemins, noms d'API et JSON d'exemple intacts. `api.en.md` est produit en remplaçant uniquement les lignes de prose du fichier français.
- Libellés d'interface alignés sur `frontend/src/i18n/en.json` (Dashboard, Quick input, Analysis & decisions, Check again, Reason with HermiT, Start from a document...).
- Les formulations françaises que l'utilisateur tape (intentions de Krakie, exemples de questions), les marqueurs `À VÉRIFIER` et les noms de sections cités sont en code inline, donc non traduits et ignorés par le scan anglais.

## Ancres
- Mécanisme : identifiant explicite `{#id}` en fin de titre, géré dans `frontend/src/lib/docs.ts` (retiré du texte affiché et du sommaire). Sans `{#id}`, l'ancre reste dérivée du titre.
- `tools/doc_ids.py` a posé les `{#id}` sur les cinq fichiers français, avec exactement les ancres calculées avant (aucun texte de titre modifié, `help_map.json` inchangé).
- Les fichiers `.en.md` reprennent les mêmes identifiants ; on traduit le titre, jamais l'id.
- Tests (`backend/tests/test_help_map.py`) : chaque ancre de help_map existe dans le fichier français et dans `.en.md` ; la liste des ancres fr et en est identique pour les cinq fichiers.

## Application
- Mode en : pas de bandeau « French only » sur les cinq pages traduites ; il reste sur architecture, règles, glossaire (fallback français marqué `data-doc-fallback`).
- Légende des images : « Screenshot: » en anglais, « Capture : » en français.
- `english_scan.mjs` : commentaire de l'exception mis à jour (seuls les fichiers non traduits sont exemptés), nom propre Protégé neutralisé, pages `documentation/{limites,contribuer,api,changelog,architecture}` ajoutées au scan.
- `l28_docs.mjs` adapté (page traduite sans bandeau, bandeau sur architecture). Nouvelle recette `tools/recette/l33_docs_en.mjs` : les 17 ancres de help_map s'ouvrent en anglais, bouton « ? » en anglais, captures dans `journal/L33/screens/`.

## Vérifications
- pytest : 959 passés. `npm run build` : OK.
- english_scan : 0 suspect (73 vues). l28_docs : 49/49. tour : 47/47. e2e_ui : 30/30. l33_docs_en : 3/3.
- Captures regardées : éditeur avec « ? » (section 5 en anglais), API, non traduit avec bandeau.

## À noter
- Le CHANGELOG français a une section « L30 » en tête ; si l'autre agent ajoute un titre (au lieu d'une puce), il faut lui poser un `{#id}` et le même titre traduit dans `CHANGELOG.en.md`, sinon le test d'ancres échoue.
- Les recettes ont régénéré des captures sous `journal/L14`, `L18`, `L28` : non commitées.
- Passe de l'humaniseur et `doc-ok.md` restent à faire (matrice de relecture).
