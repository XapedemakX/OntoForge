verdict: OK
vérifié :
  - Vérifié le 17/11 sur master (3ab285f) : test_docs_bilingual, test_help_map et test_english verts (55 réussis) ; ancres {#id} et parité fr/en des guides (test) ; captures citées présentes dans docs/guide/img/fr et img/en (script).
  - deploy/cloudrun/README.md §8 relu contre cloudbuild-trigger.yaml et trigger-main.yaml : trois étapes (docker build, docker push, gcloud run services update --image), image ontoforge:auto-$SHORT_SHA, substitutions _REGION _REPO _SERVICE, CLOUD_LOGGING_ONLY, approvalRequired true, motif ^main$, quatre rôles du compte ontoforge-build : tout concorde. Variables $PROJECT, $REGION, $SA définies à l'étape 0. Les points « À VÉRIFIER » restent marqués. La puce mount-options du §3 est bien au niveau de la puce env.yaml.
  - Légendes des captures « téléphone » (fr et en) sans repères numérotés ; titres d'images bien formés ; CHANGELOG fr/en entrée L50 conforme au rapport.
  - Aucune clé i18n ajoutée : libellé « Mock (démonstration) » du CHANGELOG conforme à l'interface.
corrections faites : aucune propre au lot (la légende de mobile-accueil a été recalée au titre de L47, voir L47/doc-ok.md).
humaniseur : fait (deploy/cloudrun/README.md §8 : gras décoratif retiré, phrases coupées ; docs/guide/CHANGELOG.md et CHANGELOG.en.md : entrée L50 ; légendes mobiles de utilisateur.md et utilisateur.en.md relues, déjà sans tic). Le gras sur le périmètre de confiance (8.2) est gardé : c'est un avertissement de sécurité.
