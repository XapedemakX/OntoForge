# L11 - Socle du front (itération 2)

## Livré
- **Design system « Abysse »** : `frontend/src/design/tokens.css` (clair, sombre via préférence système + bascule système/clair/sombre, `data-theme`), IBM Plex Sans/Mono via `@fontsource` (versions exactes), Font Awesome 7.3.1 (solid). Les anciens noms de variables (`--panel`, `--ink`, `--accent`, `--auto`…) restent des alias : les écrans existants sont thémés sans modification.
- **Kit** `frontend/src/kit/index.tsx` : Icon, Button, IconButton, Field, Select, Segmented, Tabs, Panel (rabattable), SeverityBadge (auto/review/lost/info, icône + libellé), Card (`tone`), Toolbar, EmptyState (Krakie), ToastHost/useToast, Krakie. Styles : `shell/kit.css`.
- **Shell** `shell/Shell.tsx` + `shell/shell.css` : barre latérale par projet (parcours 1 Concevoir, 2 Vérifier, 3 Transposer, 4 Générer, puis Outils), en-tête (cible Curiosity/Neo4j, périmètre via `GET/PUT /perimeters`, endpoint SPARQL actif lu dans `/api/settings` : `sparql_endpoint.url` ou `sparql_endpoints` + `active_sparql_endpoint`, placeholder sinon, thème), routes hash, responsive (< 900 px : tiroir, bandeau « consultation » sur les écrans `editing`).
- **i18n** `i18n/{fr,en}.json` + `useI18n()` / `useT()` ; langue lue dans `GET /api/settings` (`language.ui`), français par défaut ; clés `nav.*`, `step.*`, `sev.*`, `dash.*`, `head.*`, `settings.*`.
- **Krakie** `krakie/Krakie.tsx` : `<Krakie pose size title float />` ; tente `/krakie/<pose>.svg`, repli sur l'ébauche 20 px (`krakie-draft-20px.json`, copie dans src/krakie) rendue en SVG avec accessoires simples par pose ; flottement désactivé si `prefers-reduced-motion`.
- **Tableau de bord** `screens/Dashboard.tsx` : prochaine action de Krakie (règles : ontologie vide, écarts DL, aucune shape, perdus, à arbitrer, génération obsolète/absente, tout OK), 4 étapes avec état, constats par cible (barres), dernières générations (journal local `lib/generations.ts`, alimenté par l'écran Exports : pas d'historique backend), périmètres, raccourcis.
- Écrans existants rebranchés (Ontologie, Conformité, SHACL, Analyse, Modèle, Exports, Requêtes, Assistant en pleine page). Entrée « Shapes » = placeholder.
- Captures : `journal/L11/screens/` (tableau clair/sombre/mobile 390, analyse clair/mobile, ontologie sombre, projets). `npm run build` vert.

## Contrat : brancher un écran (L8, L9, L10, L15)
1. Créer `frontend/src/screens/MonEcran.tsx` exportant un composant qui reçoit `ScreenProps` (`import type { ScreenProps } from '../shell/types'` : `{p, setP, target, setTarget}`). Racine `<div className="page">` ; écran pleine page : `fullBleed: true` et gérer le scroll soi-même.
2. Ajouter (ou remplacer le placeholder) une entrée dans `frontend/src/shell/registry.tsx` : `{ key, labelKey, icon, step, render, editing?, fullBleed?, badge? }`. L'URL est `#/projet/<id>/<key>`. L'étape fixe le groupe de la barre latérale.
3. Ajouter les libellés dans `i18n/fr.json` ET `en.json` (préfixe de l'écran) ; jamais de texte en dur.
4. N'utiliser que `../kit` et les variables de `tokens.css` (aucune couleur en dur) ; sévérités via `SeverityBadge`, états vides via `EmptyState`, annonces via `useToast`.
5. Remplacements prévus : L8 -> `screens/Settings.tsx` (route globale `#/parametres`) ; L9 -> entrée `shapes` (ComingSoon) et éditeur graphique (remplacer ou compléter `ontologie`) ; L10 -> `screens/AssistantPage.tsx` ; L15 -> `requetes`. Les appels API passent par `api.ts` (ajouts L11 : `settings`, `perimeters`, `setActivePerimeter`).
6. Mobile : consultation, arbitrage et navigation graphe sans édition ; marquer `editing: true` pour afficher le bandeau.

## Points ouverts
- Les 8 SVG de pose `public/krakie/*.svg` n'existaient pas au moment du lot : repli ébauche actif (aucun fichier public écrit par L11).
- Historique de générations côté serveur absent : « obsolète / à jour » est local au navigateur.
- Écrans existants non refaits en profondeur (sélecteur de cible dupliqué dans Analyse/Modèle, boutons texte sans icône).
