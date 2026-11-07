# L10 - Assistant plein écran (front)

## Livré
- `frontend/src/screens/assistant/` (index.tsx, aapi.ts, MiniGraph.tsx, assistant.css) ; ancien panneau et `AssistantPage.tsx` supprimés ; entrée `assistant` du registre rebranchée ; clés `asst.*` fr/en.
- Conversation par projet (localStorage `ontoforge.assistant.<id>`), Krakie en avatar (réfléchit pendant l'appel, contente à la proposition, inquiète sur erreur), sélecteur de fournisseur (`/assistant/status`, défaut = `default_provider_id`), note + lien Paramètres si seul le mock est configuré.
- Dépôt de fichiers (glisser-déposer + bouton) CSV/SQL/TXT/MD via `/upload`, aperçu (colonnes, tables, premières lignes), retrait.
- Actions rapides : brouillon depuis le fichier (`/chat` + pièces jointes), shapes (`/shapes`, carte « Appliquer » -> PUT shapes fusionné), expliquer un constat (liste des constats non auto, `/explain`), alignements SKOS/schema.org (message `/chat`).
- Proposition à droite : mini-graphe (vert ajout, orange modification, pointillé existant), liste avec ✓/✕, Tout accepter/rejeter, « Voir dans l'éditeur ». Mobile : onglets Conversation / Proposition.
- `frontend/src/lib/proposal.ts` : `setProposal`, `useProposal`, `acceptItem`, `rejectItem`, `acceptAll`, `rejectAll`, `clear`, plus `buildItems(cur, prop, lang)` et `bindProjectSetter(fn)`. Item : `{id, kind: add|modify, entity_iri, label, ops, type, detail?, source?, target?, needs?}`. L'acceptation POST `/ops` (tout ou rien), accepte d'abord les classes dont l'élément dépend (`needs`), retire les éléments traités, appelle `onProject(project)` (fourni à setProposal ou via bindProjectSetter) et émet l'évènement `window` « ontoforge:project ». L'état est persisté dans localStorage `ontoforge.proposal`.

## Pour L9 (éditeur)
Consommer `useProposal()` (filtrer sur `projectId`), surligner `items` par `entity_iri` / `source`-`target`, appeler `acceptItem/rejectItem`. Pour rafraîchir le projet : `bindProjectSetter(setP)` ou écouter « ontoforge:project ». À la date du lot, l'éditeur n'affiche pas encore la proposition (capture 05).

## Vérification
Playwright sur automaint (backend mock) : dépôt de `vehicules.csv` (aperçu colonnes), brouillon mock (6 éléments), acceptation de 2 éléments via /ops (6 -> 4, aucune erreur), navigation vers `#/ontologie`, mobile 390 px. Captures `journal/L10/screens/` 01 à 08 ; correction faite après examen (étiquettes d'attributs du mini-graphe débordantes -> compteur « n attr. »). `npm run build` vert.

## Limites
- Le mock ne renvoie qu'un squelette ; pas testé avec un vrai fournisseur.
- Shapes : application par fusion, pas élément par élément.
- Mini-graphe en grille simple (pas de dagre) ; étiquettes d'arêtes parfois superposées.
- Historique de conversation limité au navigateur (80 messages).
