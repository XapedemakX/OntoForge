verdict: OK (corrections faites)

Corrigé (frontend/src/i18n/fr.json et en.json, écriture par fichier temporaire + os.replace, ancres et clés intactes) :
  - Pluriels « constat(s) » et « écart(s) » sur l'accueil mobile : `dash.next.lost.t` « Constats perdus sur {target} : {n} », `dash.next.review.t` « Constats à arbitrer sur {target} : {n} », `dash.next.dl.t` « Conformité OWL 2 DL, écarts : {n} », `dash.step.verifier.notdl` « OWL 2 DL, écarts : {n} ». Anglais en miroir (« Lost findings on {target}: {n} », etc.). Plus de « 1 constat(s) perdus ».
  - Sous-titres de « Plus » coupés par la carte : `mob.more.sub.carte-metier` « Zones et relations » / « Zones and relations » ; `mob.more.sub.fichiers` « Turtle et fichiers » / « Turtle and files ».
  - Registre : `mob.link.copied` « ouvrez-le sur votre ordinateur » passé au tutoiement de l'appli (« ouvre-le sur ton ordinateur »).
  - Guide fr/en : références internes (« Depuis L44 ») retirées (voir revue-doc).
Restent, hors périmètre mobile (écrans bureau), des « (s) » : `ol.tree.props`, `ol.tree.subs`, `an.count`, `an.nfind`, `an.nodecision`, `mo.pending`, `ex.files`, etc., et la phrase du rapport backend (`targets/report.py:140`). Une vraie gestion des pluriels dans `i18n/index.tsx` serait le bon lot.
À la discrétion de Jerem : « Arbitrer » (fr) / « Decide » (en) pour le même onglet ; garder.
Sens des docs non modifié hormis les trois corrections d'exactitude listées par la doc.
