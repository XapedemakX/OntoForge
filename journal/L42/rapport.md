# L42 : administration des comptes, langue par compte, administrateur sur tous les projets : rapport

Décision : D-L42-01 (réponses de Jerem à Q-L40-1, désormais fermée). Contrat : CONTRACTS §17. Pas de montée de version (D-L21-02).

## Ce qui est livré
| Demande | Réalisation | Test |
|---|---|---|
| Langue par compte | `PUT /api/auth/preferences`, `localize.REQUEST_LANG` lue par `ui_lang()` et `assistant_lang()` ; menu du compte ; défaut des nouveaux comptes = réglage global | `test_language_is_per_account`, `…survives_relogin…`, `…global_language_is_the_default…`, `…config_account_can_set_language` ; recette : carol en anglais, alice et bob en français |
| Pas de génération par le lecteur | `generate/{target}` et `/zip` classés `write` (action « generate ») ; CSRF exigé malgré le GET ; Exports et tableau de bord : boutons désactivés | `test_reader_cannot_generate_but_editor_can`, `test_generate_by_get_requires_csrf`, `test_l40_02_no_read_route_modifies_the_project_folder` (plus d'exception `generations.json`) |
| Magasin de comptes | `auth/accounts.py` : `accounts.json` 600, atomique, fusion avec la configuration | `test_create_account_hashes_password_and_file_is_600`, `…loosened_is_tightened…`, `…list_merges_config_and_store`, `…config_account_is_not_editable…` |
| Dernier administrateur | règle dans l'annuaire (409 `last_admin`) | `test_last_active_admin_is_protected` |
| Sessions coupées | jeton `gen` dans le cookie, compte relu à chaque requête | `test_disable_and_delete_cut_sessions_immediately`, `test_reset_password_cuts_sessions_and_forces_change` |
| Mot de passe provisoire | `must_change` : 403 `password_change_required` partout sauf `/api/auth` ; écran Krakie ; ancien mot de passe requis ; limiteur de connexion partagé | `test_provisional_password_must_be_changed_first`, `test_typed_password_is_also_provisional`, `test_password_change_is_rate_limited`, `test_change_own_password_needs_session_and_csrf` |
| Journal d'administration | `admin-audit.jsonl` 600 ; clés secrètes écartées | `test_admin_journal_never_holds_a_secret`, `test_audit_detail_drops_secret_looking_keys` |
| Réservé aux administrateurs | 403 `admin_only` sur tout `/api/admin` | `test_non_admin_is_refused_on_every_admin_route` (parcourt les routes de l'application), `test_new_admin_can_administer_and_demoted_admin_loses_access` |
| Administrateur sur tous les projets | `role_for` → propriétaire ; `via_admin` ; `as_admin` dans le journal d'activité ; suppression → journal d'administration | `test_admin_sees_and_acts_on_every_project_with_trace`, `test_admin_own_project_actions_are_not_marked_as_admin` |
| Suppression d'un compte | transfert obligatoire des projets ; accès aux projets des autres retiré | `test_delete_account_transfers_projects` |

Tests : 26 nouveaux dans `tests/test_l42_admin.py` ; `tests/test_collab.py` adapté (génération = écriture, route d'administration dans le test d'inventaire).

## Vérifications
- `pytest -q` : 1283 verts. `npm run build` : sans erreur.
- `l42_admin.mjs` (8997/4997) : vert (49 contrôles). `l40_partage.mjs` (8993/4993) : vert, son ouverture fixe la langue par l'API (la langue est maintenant celle du compte). `e2e_ui.mjs` (8995/4995) : 30/30. `english_scan.mjs` : 0 texte français suspect sur 80 vues.
- Captures : `journal/L42/screens/` (01 à 09 en français clair, 10 à 12 en fr / en, clair / sombre) ; trois reprises dans le guide (`admin-comptes`, `compte-langue`, `admin-liste-projets`, fr et en).

## Choix faits (D-L42-01) et points à arbitrer par Jerem
1. Le zip de génération est classé en écriture comme `generate/{target}` (il génère à la volée) : le lecteur n'a donc plus d'archive, seulement l'export de l'ontologie et des shapes. Pour le lui rendre, repasser `("GET", P + "/generate/{target}/zip")` en lecture dans `collab/routes.py`.
2. Un compte de la configuration ne change pas son mot de passe depuis l'interface (409 `managed_by_config`) : « tout compte peut changer son mot de passe » vaut pour les comptes créés dans l'interface.
3. Les lectures d'un administrateur sur le projet d'un autre ne sont pas journalisées (écritures et actions de propriétaire seulement).
4. La suppression d'un compte propriétaire de projets exige un compte destinataire ; aucun projet n'est jamais supprimé avec le compte.
5. Comme la configuration déclare toujours un administrateur, « il reste un administrateur actif » ne se déclenche en pratique que si l'on retire un jour cette obligation ; la règle est testée sur l'annuaire.

## Pour la relecture de sécurité
- Le magasin garde des hachages argon2 dans `accounts.json` (600) ; la déconnexion volontaire reste une liste de révocation en mémoire (inchangé), mais désactivation, suppression, réinitialisation et changement de mot de passe coupent les sessions par le jeton `gen`.
- `GET generate/*` exige désormais le jeton CSRF (écriture par GET).
- Le mot de passe provisoire généré n'existe qu'en clair dans la réponse qui le crée ; ni journal, ni fichier.
- Pas de limiteur propre aux routes d'administration (le plafond global par minute s'applique).
