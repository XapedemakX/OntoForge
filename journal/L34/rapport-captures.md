# L34c : captures d'écran de la documentation

## Régénérer (une commande)

```
cd frontend && npm run build && cd .. && node tools/docs/captures.mjs
```

Le générateur lance lui-même un backend jetable (fournisseur `mock`, données temporaires, ports 8971/4971) et `vite preview` sur `frontend/dist`, prend les captures en fr puis en en 1440×900 thème clair, puis optimise (`tools/docs/optimize.py`, Pillow, pas de pngquant ici). Sortie : `docs/guide/img/{fr,en}/<nom>.png` et `docs/guide/img/sizes.json`.

Options : `--lang fr|en|both`, `--only nom1,groupe`, `--no-optimize`, `--keep-servers`. Variables : `REUSE=1` (serveurs déjà lancés), `BACKEND_PORT`, `FRONT_PORT`, `PYTHON`. Les captures sont déclarées dans `tools/docs/captures-list.mjs` (`cap(groupe, nom, fn)`) ; les annotations (pastilles numérotées, cadres) sont injectées juste avant la prise puis retirées. Aucune vraie clé : fournisseur et endpoint factices (`sk-ant-FACTICE-demo-0000`, `sparql.example.org`).

Contrôle du français dans les captures en : `python -I tools/docs/scan_fr_in_en.py` (OCR tesseract, à relire à la main).

## Résultat

- 63 captures par langue, 126 images, 8,98 Mo au total, aucune au-dessus de 150 Ko (palette 128 couleurs, repli 64 puis 32).
- Front : images en fichiers séparés (`?no-inline`), chargées à la demande (`loading=lazy`, largeur/hauteur réservées via sizes.json). Bundle principal 486,8 ko (avant : environ 475 ko) ; les PNG pèsent 9,4 Mo dans `dist/assets` mais ne sont téléchargés qu'à l'affichage.
- `.dockerignore` (`docs/*` puis `!docs/guide/`) laisse passer `docs/guide/img` (vérifié par émulation, pas de démon Docker ici).
- Gardes : pytest 967 passés, e2e_ui 30/30, english_scan 0 suspect, l33 3/3, l28 70/70 (images fr et en, visionneuse, Échap, mobile).

## À signaler

1. Le texte généré côté serveur reste en français quand l'interface est en anglais : commentaires et rapport des exports (Connector.cs, rapport-transposition.md), document de démonstration et questions de compétence du mock (import de document). Les captures en correspondantes (exports-rapport, limites-a-verifier, fichiers-genere, assistant-document-extrait) montrent ce français ; c'est une limite du produit, pas des captures.
2. Les libellés `@fr` de l'ontologie automaint apparaissent en français dans les captures en (attendu).
3. La saisie rapide accepte `Vehicle < ElectricVehicle` (cycle de sous-classes) sans validation OWL, puis `/analyze` répond 500. Le geste de glisser, lui, est validé par le serveur.
4. `tools/recette/english_scan.mjs` utilise par défaut les ports 8951/4951 ; le générateur prend 8971/4971 pour éviter la collision.

## L34e : contrôle du français dans les captures anglaises
`python -I tools/docs/scan_fr_in_en.py` : 23 lignes signalées dans 63 captures, toutes des données de l'ontologie automaint ou du bruit de reconnaissance de caractères.
- Libellés et commentaires `@fr` de l'ontologie (« Ordre de réparation », « Propriétaire de voiture », `skos:definition "..."@fr`, « Document ouvert par un garage... », « Véhicule électrique »), visibles dans editeur-inspecteur, liste-classe, liste-propriete, hermit-resultats, fichiers-diagnostic, fichiers-diff, fichiers-editeur.
- IRI `https://w3id.org/ontoforge/automaint` lue « autonainté » par l'OCR (requetes-question, requetes-valeurs-possibles).
- Bruit OCR sur des libellés d'ontologie (editeur-filtres, editeur-vowl, editeur-vowl-proprietes, hermit-classe-rouge « Chimère »).
Aucun texte d'interface en français. Captures régénérées : documentation et krakie-aide (fr, en).
