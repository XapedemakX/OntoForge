# L17 - Vue liste de l'ontologie (refonte)

Livré : `frontend/src/screens/ontology-list/` (index, ListPane, ClassSheet, PropSheets, Header, parts, QuickPanel, model.ts, ctx.ts, css) ; ancien `screens/Ontology.tsx` supprimé ; entrée `ontologie-liste` du registre pointe sur le nouvel écran (fullBleed). Clés i18n `ol.*` en fr et en.

- Colonne gauche : recherche, 4 onglets avec compteurs, arbre des classes (icônes, compteurs propriétés / sous-classes, multi-parents), listes à plat avec domaine → portée, création rapide.
- Fiche classe en cartes : en-tête (icône éditable, IRI compacte copiable et renommable, badges, « Demander à Krakie » + suggestions), identité fr/en côte à côte, hiérarchie (combobox à recherche), tableau des propriétés (type/cible, cardinalité lisible, obligatoire, clé, origine propre/héritée, ajout en ligne donnée ou relation), restrictions en langage naturel (+ ajout), disjonctions/équivalences, clés, utilisation (domaine, portée, restrictions, shapes).
- Fiches propriété objet (domaine, portée, inverse, 7 caractéristiques en interrupteurs expliqués), propriété de données, individu (types, faits).
- Krakie : `useAssistantContext({screen:'ontology-list', selection:{kind,id,label}, suggestions})` ; boutons `openAssistant({prompt, context})` ; état vide avec Krakie. Saisie rapide repliable (fermée par défaut).
- Écritures par POST /ops (libellés, hiérarchie, propriétés, restrictions, clés, icône, inverse, rename, delete). Repli PUT /onto pour ce qui n'a pas d'opération : individus (création, types) et « une seule valeur » des propriétés de données.
- Mobile < 900 px : liste ou fiche, bouton retour.

Vérifié avec Playwright sur automaint (classe Opération de service, Garage héritée, propriété, donnée, individu, combobox, ajout de propriété, panneau Krakie) : captures `journal/L17/screens/liste-*.png`. Corrigés après revue : onglets tronqués (retour à la ligne), icône de compteur manquante, placeholder de clé tronqué, suggestions d'individu. `npm run build` vert.

Limites : faits d'individus en lecture seule ; équivalences et expressions complexes en lecture seule ; badge « abstraite » lu depuis /graph ; pas de test automatisé du front.
