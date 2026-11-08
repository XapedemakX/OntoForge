---
name: technical-documentation
description: Méthode de documentation d'un logiciel construit par une équipe d'agents Claude. Couvre le guide utilisateur illustré, l'architecture, l'API générée depuis OpenAPI avec exemples réels, les règles métier expliquées par des exemples exécutés, le glossaire, la FAQ des limites, le journal des versions et le guide de contribution. À utiliser pour documenter ou relire la documentation d'un projet livré par lots, sans inventer ce que le code ne dit pas.
---

# Documenter un logiciel construit par une équipe d'agents

Méthode éprouvée sur OntoForge (documentaliste, agent `doc`, lot L12). Générique : remplacer les noms de lots, de dossiers et de livrables.

## 1. Principes

1. Le code et les tests font foi. Chaque affirmation est vérifiée contre un fichier source, un test ou une exécution ; on cite le fichier quand c'est utile. Une documentation plus ancienne que le code (README, catalogue, décisions) est une *source à contrôler*, pas une vérité : le jour où le code a changé (ex. un type ajouté après le README), la doc suit le code et l'écart est signalé.
2. Ne jamais deviner. Ce que le code ne tranche pas devient une question (fichier `journal/doc/questions.md` : identifiant, destinataire, question, contexte, pages concernées, réponse) adressée à l'expert concerné ; le lead relaie. Dans le texte : `À CONFIRMER`, ou l'état observé du code, daté.
3. Exemples réels, pas rédigés de tête. Les réponses d'API viennent d'un vrai appel (client de test de l'application, données dans un dossier temporaire), abrégées mécaniquement (`…`). Les exemples de règles métier sont exécutés : chaque extrait est passé dans le moteur et l'on vérifie qu'il produit bien la règle annoncée. Un extrait qui ne déclenche pas sa règle est faux, même s'il est plausible (cas vécu : un datatype défini doit s'écrire en `owl:equivalentClass [ a rdfs:Datatype … ]`, pas en propriétés directes).
4. Générer ce qui peut l'être. Référence d'API depuis `app.openapi()` ; fiches de règles depuis le catalogue normatif (source unique) + une table d'exemples et de pertes écrite à la main. Le générateur reste hors du dépôt (ou dans un script de lot) ; seul le résultat est versionné. Regénérer à chaque lot.
5. Une page par question du lecteur. « Comment l'utiliser ? » (utilisateur), « Comment c'est fait ? » (architecture), « Comment l'appeler ? » (API), « Pourquoi ce résultat ? » (règles), « Qu'est-ce que ce mot ? » (glossaire), « Qu'est-ce qui ne marche pas ? » (limites), « Qu'est-ce qui a changé ? » (changelog), « Comment travailler ici ? » (contribuer).
6. Dire ce qui n'est pas vérifié. La FAQ des limites est le livrable le plus lu : elle liste ce qui n'a pas été exécuté (compilation, base réelle, Docker), les marques `À VÉRIFIER` du code, les écarts doc/code, l'absence d'authentification, avec la source de chacun.
7. Le code bouge pendant qu'on écrit. Dater les chiffres (« état du 3 novembre »), éviter les nombres qui évoluent avec le moteur (nombre de constats), relire l'arborescence juste avant de livrer, ne documenter une route ou un écran en cours de livraison qu'en le signalant « non stabilisé ».

## 2. Livrables et sources

| Livrable | Source principale | Vérification |
|---|---|---|
| Guide utilisateur illustré | écrans du front, captures de revue de lot (références relatives) | parcourir le parcours de bout en bout par l'API ; compter les violations / résultats annoncés |
| Architecture | arborescence du code, modèles de données (pydantic / types), fonctions de service, schéma Mermaid | `grep` des signatures ; ne décrire que des fichiers qui existent |
| API | `app.openapi()` + client de test | une requête et une réponse réelles par route ; erreurs (404, 422…) rejouées |
| Règles métier | catalogue normatif + oracle de tests | harnais : chaque exemple déclenche sa règle ; mêmes pour les deux cibles |
| Glossaire | vocabulaire des specs, des modèles, du domaine | chaque terme apparaît dans le guide ou le code |
| FAQ des limites | rapports de lot, revues, marques `À VÉRIFIER`, décisions | chaque entrée cite sa source ; écarts doc/code → question |
| Journal des versions | rapports et revues par lot, décisions | verdicts de revue recopiés tels quels (y compris KO) |
| Guide de contribution | protocole d'équipe, contrats de lot, fiches d'agents | recoupé avec le protocole normatif |

## 3. Méthode pas à pas

1. Lire ciblé : fiche de rôle, protocole d'équipe, contrats d'interface, catalogue, rapports et revues (en-têtes « limites », « À VÉRIFIER », « points ouverts »), arborescence du code. Économiser les appels : un `grep` d'en-têtes avant de lire un rapport en entier.
2. Mesurer le réel : lancer l'application avec un fournisseur simulé, sur un dossier de données jetable ; récupérer la spécification OpenAPI ; lister les routes ; noter les écarts avec le contrat écrit.
3. Écrire le harnais d'exemples (hors dépôt) : table `règle → extrait`, complétion automatique des déclarations indispensables, exécution du moteur, échec bruyant si la règle n'apparaît pas. Corriger les extraits, pas le moteur.
4. Générer les pages dérivées (API, règles), écrire les pages narratives (utilisateur, architecture, limites, contribuer), dater les chiffres.
5. Relire contre le code : pour chaque nombre, nom de fichier, option d'interface, port, variable d'environnement, route : un `grep` ou une exécution. Supprimer ce qui ne se vérifie pas.
6. Poser les questions (une par écart non résolu), renvoyer à elles depuis la page concernée.
7. Événements : publier `start` et `done` dans la salle de suivi de l'équipe (format du protocole).
8. Clôture d'un lot : `journal/<lot>/doc-ok.md` seulement si la doc reflète le lot *et* si les questions bloquantes sont tranchées ; sinon liste explicite de ce qui manque. Sans ce fichier, le lot n'est pas clos.

## 4. Pièges rencontrés

- README en retard sur le code (type ajouté, port, dossier cité qui n'existe pas) : vérifier chaque affirmation du README avant de la recopier.
- Captures périmées : elles montrent un état passé (module « bientôt disponible », nombres différents). Les légender avec leur origine et ne pas en tirer de chiffres.
- Générateur d'exemples qui masque l'erreur : tronquer un JSON n'est pas le réécrire ; abréger par profondeur (`{…}`, `[…]`) plutôt que par réécriture.
- Deux sources pour une règle (catalogue et sa copie rendue) : citer la source unique, signaler la copie comme rendu.
- Questions déguisées en affirmations : « il semble que… » dans un guide = une question non posée.
- Parallélisme : d'autres agents modifient code et décisions pendant la rédaction ; reprendre la liste des routes / fichiers juste avant de finir.

## 5. Gabarits

Question : `| ID | Destinataire | Question | Contexte (source) | Pages concernées | Réponse |`.

Fiche de règle : identifiant, construct, détection, sévérité ; exemple (extrait exécutable) ; transposition par cible (option recommandée, raison, alternatives) ; ce qui se perd ; compensation.

Entrée de FAQ : question en gras, réponse en deux ou trois phrases, source entre parenthèses, renvoi vers la question ouverte s'il y a un écart.
