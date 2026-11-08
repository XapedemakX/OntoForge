# L25 : vérification documentaire (documentaliste)

Sections vérifiées contre le code : « Amorcer depuis un document » (docs/guide/utilisateur.md) et docs/CONTRACTS.md §9.

Écarts trouvés et corrigés :
- CONTRACTS §9 ne listait pas `GET /api/assistant/document/demo` (api/assistant.py) : ajouté.
- `document` de la réponse de `/document/draft` contient maintenant `lang` (docdraft.py) : ajouté, avec son usage.
- Confidentialité : le texte disait que `ollama` n'appelle que l'URL locale. Faux depuis la revue w3c : un Ollama dont l'URL n'est pas locale est hébergé (`is_hosted`, docdraft.py). Règle exacte ajoutée, avec la décoche de la case à chaque nouveau fichier ou fournisseur (DocImport.tsx).
- Code 501 (pypdf absent) manquait à la ligne de `/document/upload` (document.py) : ajouté.
- Guide : la proposition est groupée avec compteurs, filtre, « Tout accepter » par groupe, extrait au clic ; W07 est une information repliable ; lien de démo. Réécrit en conséquence, avec les captures régénérées par la recette.

Points confirmés sans changement : formats et limites (415/413/422, variables `ONTOFORGE_DOC_*`), extrait de 300 caractères retrouvé dans le document, 5 à 10 questions, moteur de repli et motifs, 409 sans `confirm_hosted`, annulation depuis l'éditeur.

Limite à signaler (revue w3c, non encore au guide) : un extrait à cheval sur deux pages n'est pas retrouvé et l'élément est écarté. À CONFIRMER avec l'humaniseur pour la formulation ; la passe de style reste à faire avant clôture.
