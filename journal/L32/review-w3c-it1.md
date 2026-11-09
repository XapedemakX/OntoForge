# L32 : revue w3c, itération 1 (raisonneur HermiT)

verdict: OK (après corrections faites par le relecteur, détaillées ci-dessous)

Méthode : HermiT 1.3.8.1099 réel (Java 21, owlready2 0.47), 14 ontologies d'essai passées par `run_hermit`, sortie brute de la ligne de commande comparée à la réponse d'OntoForge. Les cas vérifiés sont figés dans `backend/tests/test_reason_hermit_w3c.py` (14 tests).

## Résultats vérifiés (justes)
| Cas | HermiT | OntoForge |
|---|---|---|
| Individu dans deux classes disjointes | incohérente | incohérente, piste exacte |
| Cardinalité max 1 + deux valeurs `differentFrom` | incohérente | incohérente, aucune piste (correct) |
| Domaine (ou portée) disjoint du type déclaré | incohérente | incohérente ; piste trouvée depuis le correctif ci-dessous |
| `hasKey` + même clé + `differentFrom` | incohérente (clé DL-safe) | incohérente, aucune piste |
| `someValuesFrom` vers une classe vide (≡ Nothing, ou sous deux disjointes) | C et E insatisfiables | idem |
| `allValuesFrom A` + `someValuesFrom B`, A disjointe de B | C insatisfiable | idem, aucune sous-classe proposée |
| `Driver ≡ Person ⊓ ∃p.Car`, `Trucker ⊑ Person ⊓ ∃p.Car` (en deux axiomes) | Trucker ⊑ Driver | proposé ; Driver ⊑ Person non proposé (conjoint déclaré) |
| `French ≡ ∃p.{Fr}` (hasValue), `x p Fr` | x : French | individu reclassé |
| `xsd:date` (hors carte OWL 2) | ignoré (`--ignoreUnsupportedDatatypes`) | avertissement « sort d'OWL 2 DL » en tête |
| Classe non déclarée | raisonne | avertissement W02 |
| Propriété transitive dans une cardinalité | refus (IllegalArgumentException) | `status: error` |

Entrées : `model_to_graph` émet déclarations, individus, `hasKey`, restrictions et datatypes ; tout passe à HermiT. Ce qui manquait est traité ci-dessous (imports).

bloquants (corrigés par le relecteur, `backend/ontoforge/conformance/hermit.py`) :
  - [hermit.py:run_hermit] les `owl:imports` du projet étaient passés à HermiT, qui (OWL API) va chercher l'IRI sur le réseau depuis le serveur : accès sortant non maîtrisé (SSRF via une IRI d'import), et sur une IRI injoignable `status: error` « Could not load imported ontology ». Les imports sont maintenant retirés de la copie envoyée à HermiT ; un avertissement les liste et le guide dit que le raisonnement porte sur le seul contenu du projet. Test `test_imports_are_not_fetched`.
  - [hermit.py:compare] HermiT n'écrit qu'un représentant arbitraire par groupe d'équivalence. Avec `C ⊑ B` déclaré et `A ≡ B` inféré, la carte proposait « C ⊑ A » (vrai mais redondant, et dépendant du représentant choisi). La comparaison se fait maintenant groupe à groupe. Test `test_equivalence_representative_does_not_produce_redundant_subclass`.
  - [hermit.py:MSG no_cand] « la cause passe par des restrictions ou des cardinalités » était faux pour une incohérence par domaine/portée ou par `hasKey`. Message réécrit (restrictions, cardinalités, fonctionnelles, clés, valeurs de données), sans désigner de cause.

non-bloquants :
  - Corrigé : les pistes ferment maintenant les types par `rdfs:domain` / `rdfs:range` des assertions et le disent (« type déduit du domaine ou de la portée de p »). Tests domaine et portée.
  - Corrigé : une classe inférée équivalente à `owl:Thing` donne un avertissement (souvent un domaine ou une définition trop large). Les arêtes vers `owl:Thing` et réflexives n'ont jamais été proposées : vérifié.
  - Corrigé : hors DL, quand HermiT refuse l'ontologie, `error` renvoie au profil (« l'échec vient probablement des points signalés »). Le guide disait seulement « HermiT est quand même lancé », il dit maintenant qu'il peut refuser.
  - « Ajouter au modèle » : seules les arêtes `SubClassOf` de HermiT, hors `owl:*`, hors classes insatisfiables, hors réflexives et hors fermeture déclarée, sont proposées : ce sont bien des subsomptions inférées. Quand l'ontologie sort d'OWL 2 DL, l'ajout reste possible ; je suggère de le désactiver (ou de demander confirmation) si `dl.conformant` est faux, car le résultat n'est qu'indicatif.
  - Les pistes d'incohérence sont honnêtes : `justification: false`, note explicite, renvoi à Protégé. Elles restent syntaxiques (pas de propagation par `subPropertyOf`, `inverseOf`, restrictions).
  - `counts.inferred_subclass` compte aussi les lignes `SubClassOf(X owl:Thing)` : chiffre gonflé, sans effet visible (non affiché).
  - L'intention Krakie était du code mort dans le commit L32 (collée après le `return` de `_prop`, et `agent.py` ne compilait plus depuis L28). La version d'`agent.py` livrée par L31 (e52011c) la place correctement dans `run()` ; le test `test_krakie_reasoning_hooked_in_agent_run` passe par `agent.run` pour que cela ne se reproduise pas.
  - `docs/CONTRACTS.md` §11 : précisions de comportement ajoutées (imports, groupes d'équivalence, `--ignoreUnsupportedDatatypes`, refus hors DL), sans changement de forme de la réponse. Le lead jugera s'il faut une ligne dans `journal/decisions.md`.

skill: section HermiT de `skills/w3c-ontology-conformance/SKILL.md` complétée (imports, représentant d'équivalence, refus hors DL, message « aucune piste », équivalence à owl:Thing).
