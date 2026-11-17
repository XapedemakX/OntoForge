# L47 : réponse à la revue curiosity it3 (non-bloquant)

Correction faite par le chef pendant la clôture.

| Rôle | Constat | Réponse |
|---|---|---|
| curiosity | `Guaranteed("au plus une valeur")` émis à tort sur un scalaire `max 0` / `exactly 0` | `targets/curiosity.py` : sur un scalaire texte ou date, `max 0` devient un contrôle de présence (`!string.IsNullOrWhiteSpace` / `!= default`) ; sur un numérique non nullable, `NotChecked` motivé (absent = 0). Test `test_scalar_max_zero_is_not_guaranteed`. |

Hors périmètre signalé par la revue : l'analyse de `samples/trap/trap-nondl.ttl` plante dans `detect_o18` (tri DatatypeProperty / ObjectProperty) ; à vérifier sur master, suivi hors L47.
