# L30 : correctif sprite « carré teal », centrage et « DONEBY »

## Reproduction
Build de production servi par un serveur statique qui imite nginx (MIME `image/svg+xml`, 404 sous `/krakie/` et `/assets/`), Chromium, 1850×1270, avec et sans `prefers-reduced-motion`. Firefox n'est pas installé dans Playwright ici : non testé. Avec les fichiers du dépôt à jour, le sprite s'affiche et la zone est centrée (marges 375/375) : le défaut n'apparaît que quand une image de pose échoue.

## Causes
1. Sprite : `loadKrakieSprites` abandonnait **toute la pose** si une seule image échouait, sans message, et le moteur dessinait alors un carré `lagL` 20×20. Les URLs dépendaient du manifeste : un `manifest.json` périmé (copie en cache navigateur d'avant L30, sans `nage*`) faisait viser `/krakie/nage.svg`, inexistant ; `try_files $uri /index.html` répondait 200 en HTML, donc `img.onerror` et carré. Cause probable chez Jerem (non vérifiable à distance).
2. Centrage : non reproduit (la capture montre un en-tête sans boutons : la fenêtre réelle est sans doute plus large que la capture, la zone étant centrée à x≈1270). CSS durci quand même (largeur 100 %, `min-width: 0`, marges auto, écoute de `resize`).
3. « DONEBY » : `norm()` mettait en majuscules sans couper le camelCase.

## Correction
- `sprites.ts` : manifeste en `no-cache` et facultatif (6 images par convention, durées de `game_poses.py`), préchargement attendu (bouton Jouer désactivé jusqu'au chargement), retry avec contournement de cache, rejet des images vides, silhouette pixel art de repli, `console.warn` nommant la pose manquante.
- `engine.ts`/`GameOverlay.tsx` : plus de carré ; `font.ts` : `doneBy` devient « DONE BY ».
- `nginx.conf` : 404 pour un fichier manquant sous `/krakie/` et `/assets/`, `no-cache` sur index et `/krakie/`.
- Recette `tools/recette/l30_game.mjs` (ports 8934/4934, serveur statique type nginx) : pixels autour de Krakie, centrage à 1850 px et de 390 à 2560 px, manifeste périmé, pose manquante, DONE BY. Captures dans `journal/L30/fix-sprite/`.
