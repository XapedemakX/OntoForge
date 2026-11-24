# L52 : clôture (24/11/2026)

**Livré.** Les 20 défauts relevés par L51 sont corrigés : 13 côté backend (dont les 4 majeurs : traduction SPARQL → Cypher multi-labels, owlrl en processus fils tuable, inférence du triplestore local plafonnée, chargement du triplestore local passé par les gardes d'entrée en échec fermé) et 7 côté front (client réseau unique, messages traduits, test de parité i18n, Playwright épinglé en CI). Synthèse : `journal/L52/corrections.md` ; détail : `corrections-backend.md`, `corrections-front.md`.

**Relectures.** Front : secu, scout, mobile OK it1 (non-bloquants traités). Backend : query OK, devfront OK, secu KO it1 (garde XML qui laissait passer une entrée mal formée) puis OK it2. Documentaliste : `doc-ok.md`. Humaniseur : fait.

**Vérification sur la version fusionnée.** Suite backend 1648 réussis ; front `npm test` 19/19, `npm run build` OK ; recettes e2e_ui 30/30, mobile_l45, l48_import, l49_bonnes_pratiques vertes ; l40_partage verte 2 fois sur 2 après un premier passage tombé sur son délai instable connu (déjà relevé en L46).

**Reste ouvert.** DF-B12 (EXISTS / NOT EXISTS / MINUS réduits à un typage → Cypher invalide) et DF-B13 (somme des plafonds mémoire des fils au-delà des 2 Gio de Cloud Run), consignés dans `journal/L51/defauts.md` ; six choix pour Jerem dans `corrections.md`. Le job CI `recettes` avec Playwright 1.63.0 est à confirmer au premier passage sur GitHub.
