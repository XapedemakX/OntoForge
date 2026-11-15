# L43 : changement de mot de passe pour tous les comptes : rapport

Décision : D-L43-01. Contrat : CONTRACTS §17. Pas de montée de version (D-L21-02).

## Livré
| Demande | Réalisation | Test |
|---|---|---|
| Compte de la configuration change son mot de passe | `config.<login>.hash` dans `accounts.json` (600) masque la configuration ; `gen` renouvelé (autres sessions coupées, courante renouvelée) | `test_config_account_changes_its_password_and_masks_the_config_one` ; recette |
| Masque persistant, prioritaire | relu au redémarrage ; `cfg_fp` signale l'écart (`cfg_changed`) | `test_mask_survives_a_restart_and_wins_over_a_changed_config_hash` |
| Réinitialisation et retour à la configuration | `reset-password` valable pour la configuration ; `POST …/revert-password` | `test_admin_resets_a_config_account_then_reverts_to_the_config_password` |
| Reste géré par la configuration | désactiver, rôle, supprimer : 409 | `test_other_attributes_of_config_accounts_stay_managed_by_the_config` |
| Droits | non-administrateur : 403 ; route de changement = session courante | `test_non_admin_cannot_touch_another_account`, `…without_csrf…` |
| Interface | menu du compte (formulaire, afficher, succès) ; panneau : étiquette, boutons, avertissement ; i18n fr / en ; aide Krakie | recette `l43_password.mjs` |
| L42-01 | hachage hors verrou ; relecture sous verrou ; `pwd:<login>` 5/min | `test_l42_01_*` (4 tests, dont concurrence) |
| L42-03 | rotation avec archives ; échec du journal = 500 et magasin rétabli | `test_l42_03_*` (4 tests) |
| L42-05 | champ `type=password` + afficher | recette |

## Vérifications
- `pytest -q` : 1301 verts (dont `test_l43_password.py` : 16 tests, `test_help_map`, `test_docs_bilingual`). `npm run build` : sans erreur.
- `l43_password.mjs` (8999/4999) : vert. Captures : `journal/L43/screens/` (menu et panneau en fr / en, clair / sombre) ; deux reprises dans le guide.

## Choix et points à confirmer par Jerem
1. Le limiteur `pwd:<login>` compte toutes les tentatives (pas seulement les réussites) : plus simple et plus strict ; 5 erreurs de saisie bloquent une minute.
2. Le masque reste prioritaire si le `.env` change : avertissement dans le panneau, remède « Revenir au mot de passe de la configuration ».
3. Un `accounts.json` perdu rend leur mot de passe de configuration aux comptes masqués.
4. Rotation du journal : 10 archives de 1 000 lignes par défaut ; seule la plus ancienne au-delà est supprimée.
