# L47 : correctif it2 (revue curiosity KO)

Les deux bloquants révélaient un défaut du générateur Curiosity ; corrigés à la source, pas seulement dans le texte.

## Bloquant 1 : O09 (et D13 max / exactly)
- Cause : les validations en forme restriction portent `{kind, n}` ; `targets/curiosity.py` ne lisait que `min` / `max`, d'où `NotChecked("cardinality : ni min ni max")` pour les 10 constats O09 d'automaint (et « non transposé en code » pour les D13 `max` / `exactly`).
- Correction : helper `_bounds(v)` (exactly n = min n + max n ; max n ; min n ; some = min 1), utilisé pour les arêtes et pour les propriétés. Propriété liste : comparaison sur `Length`. Propriété scalaire : minimum >= 1 = contrôle de présence (chaîne, date) ; « au plus une valeur » = `Guaranteed` (un scalaire n'a qu'une valeur) ; minimum sur un numérique non nullable = `NotChecked` motivé (absent = 0).
- Classement Curiosity : `engine._tightens_curiosity` garde en `review` les O09 `exactly n >= 1` (minimum = renforcement bloquant, code 2) ; seuls `max` / fonctionnelle restent en `auto`. Sur automaint, les 10 O09 sont des `exactly 1` : tous repassent à arbitrer. Neo4j inchangé (détection non bloquante).
- Motifs (`auto_reason`) réécrits par cible, EN dans `localize/phrases.py`.

## Bloquant 2 : D09 range
Garde de présence dans le code généré : `if (n.X != 0 && (n.X < lo || n.X > hi))` (`0m` pour decimal). Une absence n'est pas une violation de plage, comme pour `pattern`. D09 reste `auto`, motif exact (Curiosity : garde de présence ; Neo4j : une valeur nulle ne ressort pas de la requête).

## Non-bloquants
- Captures `ko-*` supprimées de `journal/L47/screens/` et ignorées (`.gitignore`).
- Texte d'aide « par branche » sorti de la boucle des sections dans `Analysis.tsx` (affiché une seule fois).
- Markdown : `www.` et `a@b` neutralisés (`\.` / `\@`) en plus de `://`.
- Tests sur le C# généré : `backend/tests/test_l47_curiosity_validations.py` (4 + 1 fonctions : bornes, exactly / max / min dans le texte, garde de présence, propriété de données, autolinks).

## Mesure automaint (recalculée)
| Cible | Avant L47 | Après it2 (constats) | Groupes de décision |
|---|---|---|---|
| Neo4j | 48 | 19 | 8 |
| Curiosity | 42 | 41 | 9 (Engine, Party, Vehicle, C08, D13, K02, O06, O09, O10) |

La cible < 25 n'est tenue en constats que pour Neo4j ; en groupes, 8 et 9. Pour Curiosity, le gain réel en constats est faible parce que les O09 d'automaint sont des `exactly 1` : les auto-classer aurait caché un renforcement bloquant. Question en suspens pour Jerem dans D-L47-01 (constats ou groupes).

## Docs et oracle
Recalés : guide fr/en (section constats-sans-choix), CHANGELOG fr/en, RULES.md, CONTRACTS §18, D-L47-01 (point 6), rapport.md, captures `analyse-*` fr/en (images sans rapport restaurées, `sizes.json` mis à jour). Oracle trap inchangé : dans le piège, O09 est une fonctionnelle et un `max`, donc auto pour les deux cibles.

## Vérifications
- `cd backend && /home/claude/venv/bin/python -m pytest -q` : **1324 passed** (1319 + 5 tests de `test_l47_curiosity_validations.py`) ; oracle trap 173 passed.
- `npm run build` : OK.
- Recette `tools/recette/l47_justification.mjs` (9147/5147) : **10/10 OK** (A1 mis à jour : Curiosity reclasse seulement D09, 9 groupes au plus).
- Captures `analyse-*` régénérées (fr et en).
