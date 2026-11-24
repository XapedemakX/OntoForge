# L53 : passe de l'humaniseur

Fichiers repris, sans changer un chiffre, un nom, un symbole ni une ancre :

- `journal/L53/corrections.md` : gras retiré (sauf code), une phrase recollée (majuscule après un point), quelques tournures raccourcies.
- `docs/guide/CHANGELOG.md` : doublon de la ligne « Développeurs » supprimé (la version complète est gardée), puce Cloud Run coupée en phrases, deux « avant / après » plus directs.
- `docs/guide/CHANGELOG.en.md` : mêmes retouches que le français (pas de doublon dans cette version).
- `deploy/cloudrun/README.md` : §7 (explication des secrets avec `--env-vars-file`), §8 (À VÉRIFIER sur `roles/run.admin`), plafond disque (phrase scindée).
- `docs/guide/utilisateur.md` et `.en.md`, `docs/dev` 09 et 10 : relus, déjà lisibles, non modifiés (le chapitre 09 contient un très long paragraphe DF-B17, laissé tel quel : le découper demanderait des choix de sens).

Question pour le documentaliste : rien. Tests : 252 réussis (test_dev_docs, test_docs_bilingual, test_help_map, test_l53_b13).
