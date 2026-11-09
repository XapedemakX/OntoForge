# L32 : passage du documentaliste (doc-ok)

Vérifié contre le code après les corrections de la revue w3c it1 (`backend/ontoforge/conformance/hermit.py`, `api/analysis.py`, `assistant/reasoning.py`, `assistant/agent.py` à e52011c, `screens/Conformance.tsx`).

| Document | Affirmation vérifiée | Source |
|---|---|---|
| `docs/guide/utilisateur.md`, « Raisonner avec HermiT » | 30 s et 1 Go par défaut, variables `ONTOFORGE_HERMIT_TIMEOUT` / `_MAX_MB` | `DEFAULT_TIMEOUT`, `DEFAULT_MAX_MB` |
| idem | pistes : deux classes disjointes (y compris par domaine/portée), sameAs contre differentFrom ; pas de piste pour cardinalité, fonctionnelle, `hasKey` | `explain_inconsistency`, tests `test_reason_hermit_w3c.py` |
| idem | « Ajouter au modèle » = `add_subclass` par `/ops`, annulable ; équivalences non ajoutables | `ReasonerCard.add`, `rz.equiv.noop` |
| idem | sous-classe découlant d'une équivalence inférée non reproposée ; avertissement pour ≡ owl:Thing | `compare` |
| idem | hors DL : avertissement, HermiT lancé, refus possible ; `owl:imports` non suivis | `run_hermit` |
| idem | 501 sans Java ou owlready2 | `api/analysis.py:reason`, tests 501 |
| idem | Krakie : « raisonne », « vérifie la cohérence », « run the reasoner », « check consistency » | `reasoning._FR/_EN`, `test_krakie_intent_matches`, `test_krakie_reasoning_hooked_in_agent_run` |
| `docs/CONTRACTS.md` §11 | forme de la réponse 200, 422 / 501 / 503, `explanation`, `hierarchy`, ligne de commande Java (avec `--ignoreUnsupportedDatatypes`), variables d'environnement, Krakie avant le LLM | `run_hermit`, `agent.run` (appel avant `if real`) |
| `docs/guide/limites.md` | pas de justification, monde ouvert, DL seulement, imports non suivis, équivalences non ajoutables, Docker non vérifié | `hermit.py`, `journal/L32/rapport.md` |
| `docs/guide/CHANGELOG.md`, ligne L32 | contenu exact | commit 9b4dec4 |

Corrections faites dans la doc (en même temps que la revue w3c) : guide (pistes, équivalences, imports, refus hors DL, accord « correctes et complètes »), CONTRACTS §11 (domaine/portée, groupes d'équivalence, imports, `--ignoreUnsupportedDatatypes`), limites (imports).

À signaler, hors L32 : `docs/guide/CHANGELOG.md` porte dans l'arbre de travail une modification non commitée d'un autre agent qui supprime la section « L29 : Krakie forgeronne » et déplace les lignes L28 et L32. Je n'y ai pas touché ; à vérifier par son auteur avant commit.

Reste pour clore L32 : passage de l'humaniseur sur la section du guide et le CHANGELOG, puis contrôle du sens par le documentaliste.

Humaniseur : humanisé, sens vérifié (relecture du diff par le documentaliste, aucun fait, nombre, code ni lien modifié).
