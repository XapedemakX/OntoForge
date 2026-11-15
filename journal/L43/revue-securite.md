# L43 : revue de sécurité

Auteur : agent secu, 15/11/2026. Commit relu : d4b6d1b. **Verdict : OK** (aucun bloquant ; 4 remarques faibles ou informatives, aucune à corriger avant publication).

Vérifications : `pytest -q` 1301 verts ; `npm run build` sans erreur ; tests d'attaque locaux hors dépôt (comptes fictifs, mots de passe assemblés à l'exécution).

## Résultats par point demandé
| Point | Résultat |
|---|---|
| Un compte change le mot de passe d'un autre (y compris compte de la configuration, champ d'identifiant injecté dans le corps, la requête ou les en-têtes) | Impossible : seul l'identifiant de la session est utilisé ; l'ancien mot de passe d'un autre compte est refusé (403). |
| CSRF, origine, absence de session sur le changement et sur `revert-password` | 403 / 401 comme attendu. |
| Masque posé ou retiré par un non-administrateur | Impossible : 403 `admin_only` (réinitialisation et retour à la configuration). |
| `revert-password` sur compte inexistant, d'interface, nom réservé, casse, caractères de contrôle, très long | 404 / 409 propres, aucune erreur 500, aucune traversée. |
| Course entre deux changements simultanés | Un seul gagne ; les autres 409 `password_changed_meanwhile` ou 429. Un seul mot de passe valable ensuite. |
| Course changement / réinitialisation administrateur (15 essais) | Aucune incohérence : le mot de passe de l'administrateur n'est jamais écrasé par un changement antérieur. |
| Sessions | Autres sessions coupées (401), ancien cookie rejeté, nouvelle session avec nouveaux identifiant et jeton CSRF (pas de fixation), cookie `__Host-`, HttpOnly, Secure, SameSite. Cookie forgé refusé. |
| Limiteur | Voir avis ci-dessous. |
| Rotation du journal | Archives en 600 (même si le courant était en 644) ; `ONTOFORGE_AUDIT_ARCHIVES` n'est lu que comme entier borné de 1 à 100 (toute autre valeur : défaut) : aucune traversée possible ; aucun mot de passe, hachage ni secret dans le journal. |
| Échec d'écriture du journal | 500 `audit_write_failed`, ancien mot de passe toujours valable, nouveau refusé, droits d'administration inchangés (changement, réinitialisation, compte de la configuration). |
| `accounts.json` | 600, hachages argon2 seulement, aucun mot de passe en clair. |
| Docs publiques (guide, API, limites, CHANGELOG, CONTRACTS, décision) | Rien d'exploitable : comportements et valeurs de limite documentés, pas de procédure d'attaque. |
| Front (menu du compte) | Champs `type=password` avec autocomplete adapté, saisies non conservées après fermeture, pas de rendu HTML des erreurs. |

## Avis pour Jerem sur le limiteur (déni de service par 5 essais)
Le limiteur `pwd:<compte>` ne peut être déclenché que depuis une session valide de ce compte : un tiers, même connecté avec un autre compte, ne peut pas bloquer le changement de mot de passe d'autrui (vérifié : les essais d'un compte n'affectent pas l'autre). Le pire cas est un voleur de session qui bloque la fonction une minute, ce qui est négligeable face à son accès déjà acquis. En revanche, la limite de 5 par minute freine bien le devinage de l'ancien mot de passe depuis une session volée. Recommandation : conserver le réglage actuel (5 par minute, toutes tentatives comptées). Le blocage de la connexion reste lui par adresse IP et non par compte : personne ne peut verrouiller le compte d'un autre à distance.

## Remarques (aucune bloquante)
- **L43-01 (Info, CWE-755)** : la rotation d'archives déplace plusieurs fichiers ; une panne au milieu (rare, disque) fait échouer l'action (500, rétablie) mais peut laisser les archives décalées, et la reprise écraserait alors une archive. Perte d'anciennes traces seulement. Correction possible plus tard : renommer d'abord le courant, ou tolérer.
- **L43-02 (Info, CWE-613)** : si `accounts.json` est perdu ou si l'administrateur « revient à la configuration », l'ancien mot de passe de la configuration redevient valable (déjà documenté, D-L43-01 point 3). Si ce mot de passe a fuité, le changer aussi dans la configuration avant de revenir.
- **L43-03 (Info, CWE-307, existant avant L43)** : la limite de connexion est par IP, pas par compte ; un devinage réparti sur plusieurs IP n'est pas freiné au niveau du compte. Hors lot.
- **L43-04 (Info)** : la suppression des archives en trop après réduction du réglage ne couvre que les 19 rangs suivants.

Détail de reproduction : `journal/securite/revue-L43-2026-11-15.md` (non publié).
