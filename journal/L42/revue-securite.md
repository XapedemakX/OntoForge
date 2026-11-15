# L42 : revue sécurité

Relecture de l'agent secu (15/11/2026) du commit a27c029 : comptes et sessions, mots de passe, magasin, droits d'administrateur, langue par compte, génération réservée aux éditeurs. Tests d'attaque locaux sur une instance à trois comptes ; `pytest -q` : 1283 verts ; `npm run build` : sans erreur. Détail de reproduction : `journal/securite/revue-L42-2026-11-15.md` (non publié).

**Verdict : OK pour publication, sans constat bloquant.** Un constat moyen et quatre faibles à corriger dans un lot dédié (la correction du moyen est recommandée avant l'ouverture à de nombreux comptes).

| Id | Sévérité | CWE | Composant | Constat |
|---|---|---|---|---|
| L42-01 | Moyenne | CWE-400 / CWE-833 | `auth/accounts.py` (changement de mot de passe) | Le verrou de l'annuaire est tenu pendant le calcul du hachage : des changements de mot de passe répétés ralentissent toute l'instance. |
| L42-02 | Faible | CWE-755 | `auth/accounts.py` (magasin) | Après un échec d'écriture du magasin, l'état en mémoire diffère du fichier jusqu'au prochain changement du fichier. |
| L42-03 | Faible | CWE-778 | `auth/accounts.py` (journal d'administration) | Le journal est borné sans archivage, et une erreur d'écriture du journal n'interrompt pas l'action. |
| L42-04 | Faible | CWE-209 | `main.py` (erreurs de validation) | Une erreur de validation renvoie la valeur saisie, y compris un mot de passe, à l'émetteur. |
| L42-05 | Info | CWE-549 / CWE-538 | front, dépôt | Saisie du mot de passe provisoire en clair ; ignorés et détecteur de secrets incomplets pour les fichiers du magasin. |

Contrôles vérifiés sans défaut : accès aux routes d'administration refusé à tout non-administrateur (méthodes et chemins déformés), pas d'auto-promotion ni de modification des comptes de la configuration, pas d'injection de champs, mot de passe provisoire non journalisé, sessions coupées par désactivation, suppression, réinitialisation et changement de mot de passe, rétrogradation immédiate, langue sans fuite entre requêtes concurrentes, génération refusée au lecteur, jeton CSRF effectif sur les écritures par GET, fichiers du magasin en 600.
