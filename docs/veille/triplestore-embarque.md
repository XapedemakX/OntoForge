# Triplestore embarqué pour tester l'ontologie et les individus (L19)

Jerem a demandé d'évaluer un petit triplestore embarqué, pour tester sans endpoint externe. Verdict : c'est faisable proprement avec pyoxigraph (retenu, prototype livré, CONTRACTS §6.1). rdflib reste utile pour la validation SHACL et l'inférence (owlrl), pas pour interroger.

Mesures faites le 7/11/2026 sur la machine de développement (2 cœurs, Python 3.13, pyoxigraph 0.5.13, rdflib 7.1.1, owlrl 7.1.2). Jeu : `automaint.ttl` (583 triplets) + `automaint-demo-data.ttl` (4 136 triplets, 150 Ko) = 4 719 triplets ; jeu ×50 généré en suffixant les sujets de la démo (206 800 triplets de données, 8,2 Mo Turtle, 207 383 au total). Scripts de mesure : non conservés dans le dépôt (reproductibles : chargement puis 3 exécutions, meilleur temps).
Non mesuré : Fuseki (Maven Central et archives Apache refusés par le proxy du bac à sable, 403) et toute taille d'image Docker (le démon Docker n'a accès à aucun registre). Les chiffres correspondants ci-dessous viennent de la documentation et sont marqués À VÉRIFIER.

## Comparaison

| Critère | rdflib en mémoire | pyoxigraph (Oxigraph) | Jena Fuseki en conteneur |
|---|---|---|---|
| SPARQL 1.1 Query | 30 / 33 sondes OK (échecs : RDF-star, SPARQL 1.2) | 32 / 33 (la sonde en échec est une fonction SPARQL-star) | complet (documentation) À VÉRIFIER |
| SPARQL 1.1 Update | oui (sondé : INSERT DATA, DELETE/INSERT WHERE, CLEAR, WITH) | oui (mêmes sondes) | oui À VÉRIFIER |
| Chargement ×1 (Turtle) | 0,10 s | 0,01 s mémoire, 0,04 s disque | non mesuré |
| Chargement ×50 | 5,3 s | 0,42 s mémoire, 0,79 s disque | non mesuré |
| Mémoire ×50 (RSS ajouté) | 237 Mo | 104 Mo (mémoire), 144 Mo (disque) | JVM : plusieurs centaines de Mo À VÉRIFIER |
| Disque ×50 | — (pas de persistance) | 17,6 Mo (base brute) ; 34,6 Mo avec TBox et métadonnées | TDB2, non mesuré |
| Persistance par projet | à réécrire (sérialiser / relire) | native, dossier `triplestore/` du projet | volume du conteneur, une base par projet à configurer |
| Licence | BSD-3 | MIT ou Apache-2.0 | Apache-2.0 |
| Taille ajoutée à l'image | déjà présent | 8,2 Mo (roue cp312), 21 Mo installés | image à part (JRE + Fuseki, plus de 100 Mo) À VÉRIFIER ; la JRE est déjà dans l'image du raisonneur |
| Isolement réseau | `SERVICE` : refusé par le garde-fou existant ; JSON-LD : télécharge les contextes distants (mesuré) | `SERVICE` exécuté (mesuré : une requête part vers l'URL) donc à filtrer ; JSON-LD : contextes distants refusés | à restreindre (réseau Docker interne, pas d'endpoint d'écriture) |
| Effort d'intégration | nul, mais lent | faible (réalisé : ~600 lignes avec isolement et inférence) | élevé : service compose, ports, auth, un dataset par projet |

### Performances de 5 requêtes types (milliseconde, meilleur de 3, moteur seul)

| Requête | rdflib ×1 | Oxigraph disque ×1 | rdflib ×50 | Oxigraph disque ×50 |
|---|---|---|---|---|
| Q1 guidée Diesel (Vehicle, moteur, carburant, `IN (am:Diesel)`, LIMIT 10 : 10 lignes) | 57 | 0,8 | 42 396 | 1,0 |
| Q2 `COUNT … GROUP BY` classe | 12 | 0,3 | 283 | 9,7 |
| Q3 ordre de réparation, véhicule, garage, OPTIONAL, FILTER, ORDER BY | 21 | 2,1 | 715 | 98 |
| Q4 `a/rdfs:subClassOf*` | 2,9 | 0,1 | 24 | 1,2 |
| Q5 chemin à 3 sauts avec agrégat | 8,7 | 1,5 | 231 | 75 |

rdflib est correct sur la démo mais s'effondre sur la requête guidée à grand volume (ordre des jointures non optimisé : 42 s contre 1 ms). Oxigraph reste sous 100 ms partout. Mesure de bout en bout du prototype (API, processus fils par requête, démarrage compris) : 55 à 70 ms sur la démo, 65 à 185 ms sur le ×50 ; chargement ×50 par l'API 2,8 s (analyse, écriture disque, TBox, statistiques).

### Autres pistes (une ligne chacune)
- QLever : très rapide, mais le paquet pip `qlever` n'est qu'un pilote en ligne de commande qui lance des conteneurs ; pas de mode embarqué Python, pas d'Update. Écarté.
- Comunica (JS, MIT) : moteur de requêtes sur fichiers sans stockage ni persistance, ajouterait Node au backend. Écarté.

## Inférence : RDFS, OWL RL avec owlrl, que matérialiser

owlrl est déjà dans le projet (pyshacl l'utilise). Calcul fait dans un processus fils (tuable), sur ontologie + individus + données :

| Entrée | RDFS | OWL RL |
|---|---|---|
| 4 719 triplets | 1,6 s | 2,9 s |
| 21 263 triplets (×5) | 6,3 s | 12,2 s |
| 41 943 triplets (×10) | 9,9 s | 23,6 s |

Linéaire en pratique, d'où le plafond de 30 000 triplets sources. Piège mesuré : sur l'ontologie AutoMaint complète, OWL RL ne se termine pas (plus de 10 min, arrêté) ; la cause est `owl:hasKey` (6 axiomes) : sans lui, 3,7 s. Les restrictions de cardinalité ne posent pas de problème. Le prototype retire donc `owl:hasKey` avant calcul et le signale (prp-key déduirait des `owl:sameAs`, pas une contrainte d'unicité ; les doublons de clé se cherchent par SPARQL, GROUP BY et HAVING).

Que matérialiser. owlrl brut ajoute environ autant de triplets qu'il y en a (+5 718 pour RDFS sur 4 719) dont l'essentiel est du bruit : 2 349 `rdf:type rdfs:Resource/owl:Thing`, 902 triplets à sujet littéral ou anonyme, 2 187 fermetures du vocabulaire (schéma). Seuls ~215 faits servent à interroger les individus : 130 types de classes du domaine (sous-classe retrouvée par sa super-classe, domaines et portées) et 85 valeurs de propriétés (sous-propriétés, inverses). Le prototype ne garde que ces faits-là (types de classes du domaine, valeurs de propriétés, `sameAs`) dans un graphe séparé jetable ; la démo AutoMaint n'y gagne que 130 types car elle porte déjà ses super-types explicitement : le test d'inférence utilise donc un individu typé seulement par une sous-classe.

## Isolement (mesuré et appliqué)
- SSRF : `SERVICE` est exécuté par pyoxigraph (la requête de test a atteint un serveur de boucle locale) : refusé avant exécution (algèbre rdflib + filet lexical hors chaînes et IRI). `LOAD` n'existe qu'en UPDATE, refusé. JSON-LD : lu par pyoxigraph, contexte distant refusé ; rdflib l'aurait téléchargé (mesuré), donc on ne l'utilise pas pour les fichiers de l'utilisateur.
- Lecture seule : double garde (UPDATE refusé par l'analyse, puis `Store.read_only` dans le processus fils).
- Délai : pyoxigraph n'offre aucun délai ; un agrégat sur 9 millions de combinaisons dure 0,8 s mais un produit cartésien à 4 motifs ne se termine pas. D'où un processus fils par requête, tué à l'échéance (testé : 504 à 2 s, service intact), avec mémoire (3 Go), CPU et écriture de fichiers plafonnés.
- Quota : 25 Mo par fichier, 1 000 000 triplets, inférence 30 000 triplets, validation 60 000 triplets ; réglables par `ONTOFORGE_LOCAL_STORE_*`.

## Limites assumées

Union du graphe par défaut (décision D-L19-01) : Oxigraph la sert en multi-ensemble. Elle est donc matérialisée dans le magasin et reconstruite à chaque écriture, sous le verrou d'écriture : les lecteurs attendent et ne voient jamais d'union partielle. Mesuré sur 186 000 triplets : environ 4 s par écriture, base +60 % sur disque. Les lectures sont plus rapides qu'avant (COUNT 35 ms contre 68 ms). Les mesures du tableau ci-dessus précèdent ce choix. Un chargement qui échoue (inférence) est annulé en entier.
Un seul processus serveur (verrou en mémoire) ; pas d'UPDATE ni de graphes nommés écrits par l'utilisateur ; données du triplestore non versionnées avec le projet ; RocksDB ne se referme qu'à la destruction de l'objet (voir `_with_store`, piège corrigé pendant le lot). Fuseki reste la bonne réponse si un jour il faut du SPARQL Update, du raisonnement natif ou de gros volumes : à rouvrir alors.
