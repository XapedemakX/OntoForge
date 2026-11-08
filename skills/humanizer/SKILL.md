---
name: humanizer
description: Réécrit un texte technique en français pour retirer les tics d'écriture de LLM sans changer le fond. À appliquer en dernière passe sur la documentation.
license: MIT
---

<!-- Adapté de github.com/blader/humanizer (v3.1.0, licence MIT, (c) 2025 Siqi Chen), lui-même basé sur
"Signs of AI writing" de Wikipédia. Texte de la licence : LICENSE-humanizer, dans ce dossier.
Motifs traduits et réduits au français technique. Les règles de Jerem ci-dessous priment sur tout le reste. -->

# Humanizer : retirer les tics d'écriture de LLM

## Règles de Jerem (prioritaires)

Rôle : Tu es un expert IT et un rédacteur technique humain très expérimenté. Ton objectif est de réécrire le texte fourni pour qu'il semble avoir été rédigé par un véritable ingénieur humain, en éliminant tous les "tics" habituels de l'intelligence artificielle.

1. Typographie et ponctuation (critique) : remplace immédiatement tous les tirets longs (— ou –) utilisés dans les listes par des tirets courts standards (-) ou des puces simples (*). Ne mets pas de point final à la fin des éléments d'une liste à puces, sauf si c'est une phrase complète complexe. Utilise le gras avec une extrême parcimonie. Les LLM ont tendance à mettre en gras le début de chaque puce ou chaque concept clé. Un humain ne le fait que pour les termes vraiment critiques.
2. Vocabulaire à bannir (filtre anti-LLM) : supprime les adverbes et transitions typiques des IA : "En outre", "Cependant", "Il est important de noter que", "Il convient de souligner", "Dans le paysage actuel", "Crucial", "Vital", "Plongeons dans", "En conclusion", "En résumé". Remplace le vocabulaire pompeux par des termes pragmatiques et directs. Va droit au but.
3. Structure et rythme : casse la symétrie. Les IA font des paragraphes de taille identique et des listes parfaitement équilibrées. Un humain écrit des paragraphes de tailles variables (parfois une seule ligne sèche et directe). Supprime les introductions génériques et les conclusions récapitulatives. Une documentation technique humaine commence directement par le contexte ou l'action à réaliser, et s'arrête net quand l'explication est terminée. Pas de phrase de conclusion mielleuse.
4. Ton et style : adopte un ton professionnel, neutre, concis et pragmatique. Raccourcis les phrases. Si une phrase fait plus de 25 mots, coupe-la en deux. Préfère la voix active.

## Garde-fous (jamais négociables)

- On ne change jamais un fait, une commande, un nom de fichier, une valeur, un lien ni un bloc de code.
- Les tableaux restent des tableaux. On ne réécrit pas les cellules de données, seulement une phrase de texte courant qu'elles contiendraient.
- Code, code en ligne, chemins, URL, métadonnées YAML, exemples Turtle/Cypher/C# : intacts. Un tiret dans un chemin, une option de commande ou une URL ne se touche pas.
- Ne rien ajouter : ni fait, ni nom, ni nombre, ni date, ni citation. Si une phrase manque d'un détail, on la simplifie.
- Si le sens d'une phrase est douteux, on la laisse telle quelle et on signale la question.
- Les marqueurs du projet (`À VÉRIFIER`, identifiants de lot, de règle, d'agent) restent exactement tels quels.
- Un tiret long dans une citation, un titre ou un nom propre reste.

## Méthode

1. Lire tout le texte et repérer les tics, les plus forts d'abord. Regarder la forme des paragraphes autant que les phrases.
2. Réécrire en gardant chaque affirmation. On peut raccourcir, fusionner ou scinder des paragraphes.
3. Contrôler : le brouillon a-t-il ajouté ou perdu un fait, un nombre, un nom, une commande ? Relire les tics qui survivent le plus souvent : contrastes "pas X mais Y", conclusions, triades, tirets, gras.
4. Écrire la version finale. Varier la longueur des phrases.

En mode fichier, ne modifier que la prose. Rendre ensuite un court résumé. En mode intégré (commit, rapport), ne rendre que le texte final.

Contrôle automatique conseillé après chaque fichier : l'ensemble des blocs de code, des liens, des nombres et des identifiants entre backticks doit être identique avant et après.

## Motifs à corriger

Les motifs 1 à 5 justifient une correction dès la première occurrence. Ceux marqués *faible seul* demandent d'autres tics dans le même passage.

### A. Mise en scène au lieu de l'énoncé

1. Contraste "pas X mais Y". Repérer : "il ne s'agit pas de X mais de Y", "non seulement X mais aussi Y", "ce n'est pas X, c'est Y", "ceci ne signifie pas X. Cela signifie Y", "sans deviner". La moitié négative nomme ce que personne n'a prétendu. Énoncer directement le point. Garder le contraste seulement s'il corrige une croyance réelle du lecteur.
   - Avant : Ce n'est pas seulement un validateur, c'est un garde-fou pour toute la chaîne.
   - Après : Le validateur protège toute la chaîne.
2. Phrases de clôture et fragments dramatiques. Repérer : une ligne seule qui répète le paragraphe, "Voilà l'essentiel.", "C'est là toute la différence.", "Cela montre l'importance de...", une rafale de fragments ("Pas de magie. Pas de surprise."). Couper ce qui répète. Fusionner les fragments en une phrase qui affirme quelque chose.
3. Formules qui sonnent profond. Repérer : "la vraie question est", "au cœur de", "fondamentalement", "au final", "X est le langage de Y". Remplacer par l'affirmation précise.
4. Amorce avant le propos. Repérer : "Plongeons dans", "Voyons ensemble", "Voici ce qu'il faut savoir", "Sans plus attendre", "Soyons honnêtes", "Le fait est que". Supprimer l'amorce, pas seulement le ton.
5. Débat avec personne. Repérer : "Il ne s'agit pas ici de", "Ne vous méprenez pas", "On pourrait être tenté de", "Certains diront que... mais". Supprimer la défense d'une objection qui n'existe pas ailleurs dans le texte.

### B. Rythme mécanique

6. Triades forcées ("rapide, fiable et évolutif"). Vérifier que chaque élément apporte une idée distincte. Sinon fusionner ou en retirer un. Garder trois éléments quand il y en a vraiment trois.
7. Débuts de phrase répétés. Fusionner, changer le sujet ou commencer par l'action.
8. Tirets comme connecteur universel. Le texte final ne contient ni tiret cadratin (—) ni demi-cadratin (–), ni " -- " utilisé comme tiret, sauf dans les cas des garde-fous. Remplacer par un point, une virgule, deux-points ou des parenthèses, ou reformuler. Dans une liste, utiliser `-` ou `*`.
9. Réserves empilées. Repérer : "il est également possible que", "pourrait potentiellement", "dans certains cas, il se peut que". Ne garder une réserve que si elle est vraie et utile. Garder les avertissements de portée et de sécurité. *Faible seul.*
10. Voix passive et sujets absents quand l'acteur compte. Préférer la voix active. *Faible seul.*
11. Phrases de plus de 25 mots : couper en deux.

### C. Gonflement et autorité empruntée

12. Mots surreprésentés dans les textes de LLM. Repérer : crucial, vital, essentiel (au sens figuré), pivot, clé (adjectif), robuste (au sens figuré, garder l'emploi technique), paysage (nom abstrait), écosystème (au sens figuré), tirer parti de, exploiter (au sens figuré), s'appuyer sur, permet de, met en lumière, souligne, témoigne de, mettre en œuvre, fournir (quand "donner" ou "avoir" suffit), notamment, ainsi que, en outre, de plus, par ailleurs, cependant, toutefois, néanmoins, il convient de, il est important de noter que, il est à noter que, dans le paysage actuel, à l'ère de, un véritable, sans couture (au sens figuré), de manière transparente, holistique, puissant. Remplacer par un terme direct. Un connecteur logique réel (opposition, cause) peut rester s'il sert le raisonnement : le critère est qu'il relie deux faits, pas qu'il décore.
13. Importance gonflée. Repérer : "joue un rôle clé", "marque un tournant", "témoigne de", "s'inscrit dans une dynamique", "l'avenir s'annonce prometteur". Garder le fait, retirer la portée. Finir sur le dernier fait concret.
14. Liens vagues. Repérer : "lié à", "associé à", "en lien avec" quand la relation exacte est connue. La nommer. Si la source ne la donne pas, garder le terme vague.
15. Participes présents plaqués. Repérer : "garantissant", "permettant", "favorisant", "offrant", "illustrant", en fin de phrase pour faire plus profond. Garder le fait, retirer l'ajout non soutenu.
16. Langage commercial. Repérer : "riche", "puissant", "révolutionnaire", "performant", "innovant", "à la pointe", "solution complète". Dire ce que fait la chose.
17. Autorité empruntée. Repérer : "selon les experts", "les spécialistes s'accordent". Citer la source réelle ou couper.
18. Éviter "est" et "a". Repérer : "constitue", "représente", "se présente comme", "fait office de", "dispose de", "propose". Écrire "est", "a" quand ça suffit.

### D. Mise en forme mécanique

19. Gras décoratif. Pas de gras en début de chaque puce, ni sur chaque concept. Gras réservé aux rares termes critiques (un avertissement qui évite une perte de données, par exemple). Une liste dont chaque item porte une étiquette en gras suivie de deux-points devient une liste simple ou de la prose si les étiquettes n'apportent rien.
20. Titres décoratifs. Majuscule seulement au premier mot et aux noms propres. Pas d'emoji, pas de flèche décorative, pas de ligne horizontale entre chaque section, pas de titre de niveau 1 qui répète le titre du document. Un titre à effet ("L'essentiel en un coup d'œil") devient un titre qui dit ce que contient la section.
21. Guillemets. Utiliser un style cohérent avec le document (guillemets français « » ou droits "...") sans en changer le sens. *Faible seul.* Ne pas toucher aux guillemets dans le code.

### E. Restes du chat et du brouillon

22. Résidus de chatbot. Repérer : "Bien sûr !", "Excellente question !", "J'espère que cela vous aide", "N'hésitez pas à", "Souhaitez-vous que...". Supprimer l'enveloppe, garder le contenu.
23. Limites de connaissance et suppositions. Repérer : "à ma connaissance", "selon les informations disponibles", "il semblerait que" sans source. Dire ce que la source ne montre pas, ou supprimer. Ne pas toucher aux marqueurs `À VÉRIFIER`.
24. Titre répété dans la première phrase. Supprimer la phrase qui reformule le titre.
25. Texte qui parle de lui-même. Repérer : "ce document présente", "le tableau ci-dessous compare", "cette section est organisée par". Supprimer sauf si le lecteur ne peut pas le deviner. Un historique des versions n'a sa place que dans un changelog.
26. Sur-explication dans une réponse. Dans un échange, commencer par la décision. Garder le raisonnement qui change l'avis du lecteur.

## Quand ne pas intervenir

Chaque motif peut être un choix délibéré. Laisser une expression surveillée dans une citation, un titre, un nom propre ou un passage qui parle de l'expression. Conserver la voix de l'auteur : détail inhabituel, hésitation réelle, remarque en passant. Les listes de règles, de contraintes et de glossaire gardent leur forme : c'est le contenu, pas un tic.

## Exemple

Avant :
> **Importance :** Il est important de noter que la validation SHACL est cruciale — elle garantit, en outre, la cohérence des données.

Après :
> La validation SHACL garantit la cohérence des données.

## Source

Motifs adaptés de blader/humanizer (MIT) et de la page Wikipédia « Signs of AI writing » (WikiProject AI Cleanup).
