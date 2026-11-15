# L36b : carte métier, rapport du lead front

## Livré
- Écran `carte-metier` (étape Concevoir, `frontend/src/screens/bmap/`), raccourci depuis le Modèle cible, sélecteur Ontologie / Modèle cible.
- Rendu SVG en chaîne (`render.ts`, partagé écran et export) : zones teintées à bordure pointillée, nœuds par rôle avec volume abrégé, courbes fléchées rognées aux cercles, libellés orientés placés au premier endroit libre, cadres pointillés bleus avec une flèche unique, styles de scénario, estompés, légende générée et notes en colonne de droite. Palettes claire et sombre (`palette.ts`).
- Interaction : zoom et déplacement, survol, inspecteur, glisser pour épingler, panneaux Zones et Scénarios, rôle, estompé, aperçu puis application des propositions de zones et de cadres, Réorganiser, Annuler (Ctrl+Z), bandeau « carte proposée automatiquement ».
- Export SVG, PNG ×2 et ×4 (`svgToPng` accepte un rapport, défaut inchangé).
- Krakie (`business-map`, deux suggestions), étape de visite « bmap » (21 étapes, borne de `tour.mjs` relevée), entrée `business-map` dans `help_map.json`, section `{#carte-metier}` fr/en, captures fr/en, CHANGELOG fr/en.
- Recette `tools/recette/l36_business_map.mjs` : 27/27 contre le vrai backend. Captures dans `journal/L36/screens/`.

## Écarts et points à relire
- Le contrat réel (CONTRACTS §13) diffère de la description initiale : `normalizeMap` accepte les deux formes. Le PUT n'envoie que zones (sans rectangle), rôles, estompés, épinglés, positions, cadres, scénarios.
- Le serveur ne renvoie pas les zones vides : le front garde localement celles qu'on vient d'ajouter jusqu'à ce qu'un type y soit rangé. À arbitrer côté backend (renvoyer un rectangle minimal ?).
- Les rôles intégrés du backend (`issue`, `detail`, `key`, `classifier`, `context`, `catalogue`, `knowledge`, `config`) reprennent les catégories de la légende du workspace confidentiel à oublier. Mots génériques, mais à vérifier par le lead.
- Le dessin rogne la toile du serveur au contenu (zones, cadres, nœuds) pour rester lisible une fois ajusté.
- Réorganiser applique directement (annulable) ; seules les propositions de zones et de cadres passent par un aperçu.
- Non couvert : redimensionner une zone à la main (Réorganiser recalcule), pincer pour zoomer sur mobile (boutons + et −).

## Relectures demandées
- scout : parcours UX (aperçu des propositions, épinglage, lecture mobile).
- doc : exactitude de la section `{#carte-metier}` et des légendes de styles.
- humain : dernière passe de rédaction sur la section du guide, le CHANGELOG et les textes `bm.*`.
