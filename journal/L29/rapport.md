# L29, étape 1 : Krakie forgeronne (propositions)

Demande de Jerem : remplacer la pose « bolide » (génération) par Krakie forgeronne (marteau, enclume, forge) pour rappeler le nom OntoForge. À la fin de la génération, Krakie brandit un trophée en forme de graphe.

Il s'agit uniquement de propositions. Rien n'est intégré : `frontend/`, `krakie-32.json`, `krakie-32-anim.json` et `build.py` sont inchangés.

## Contenu

- Script : `design/krakie/forge_props.py`, dérivé de `build.py`. Il importe ses primitives (`draw_krakie`, `path`, `shade`, contour `K` automatique) et sa palette de base.
  - `--redraw` dessine les poses de façon procédurale et écrit le JSON.
  - Sans option, il construit les rendus à partir du JSON, qu'on peut donc retoucher à la main.
- Sources, une par proposition : `propositions/<prop>/krakie-<prop>.json`. Le format est celui de `krakie-32-anim.json` : `poses.forge` contient 8 images et `poses.trophee` en contient 4, chacune avec `ms` et `rows`.
- Rendus par proposition :
  - `planche-claire.png` et `planche-sombre.png` (×8) ;
  - `taille-reelle.png` (×1 et ×2, fonds clair et sombre) ;
  - `forge.gif`, `forge-sombre.gif`, `trophee.gif` et `sequence.gif` (3 boucles de forge puis 3 boucles de trophée), tous en ×6, faits avec Pillow ;
  - `svg/forge-N.svg` et `svg/trophee-N.svg`, qu'on pourra copier dans `frontend/public/krakie/anim/` si une proposition est retenue.
- Comparatif : `propositions/planche.png`. Il montre « contente » (pose actuelle) puis, pour chaque proposition, la forge marteau levé, la frappe et le trophée, en ×8, ×2 et ×1, sur fond clair et sur fond sombre.

## Palette de forge (ajoutée à la palette de base)

| clé | couleur | rôle |
|---|---|---|
| `Y` | #FFE27A | métal chauffé à blanc, cœur des étincelles, nœuds du trophée |
| `O` | #F5861F | orange de forge : barre rougeoyante, flammes, braises |
| `E` | #B8321F | rouge braise, étincelles qui refroidissent |
| `e` | #6E1E14 | braise sombre (fond du foyer) |
| `N` | #4B5A64 | acier sombre : ombre de l'enclume, flanc du marteau |
| `n` | #C4D0D8 | acier clair : table de l'enclume, face du marteau |
| `d` | #7A4A26 | bois du manche |
| `c` | #3A3F46 | pierre du foyer |

Les clés de la palette de base ne sont ni modifiées ni réutilisées pour un autre sens. Le trophée reprend les ors `A` et `a` de la lanterne et de la loupe, pour rester cohérent avec la pose « graphe ». La chaleur de la barre suit quatre paliers, `e/E` → `E/O` → `O/Y` → `Y/W`. Le blanc n'apparaît qu'à l'impact.

## Proposition 1 : Frappe frontale (`p1-frappe`)

- Intention : c'est la lecture la plus directe. Krakie est à gauche, l'enclume entière à droite. Le marteau est dans le tentacule droit et une pince dans le gauche tient la barre. L'animation compte 8 images (1 120 ms) : marteau levé, armé vers l'arrière, descente, impact (yeux fermés, étoile blanche, barre blanche), étincelles qui partent vers le haut et la droite en refroidissant, remontée, puis un clin d'œil content. Le souffle est rendu par des braises qui montent au-dessus de la barre et par la chaleur qui pulse.
- Trophée : une coupe dorée à anses, surmontée d'un graphe en losange : 4 nœuds incandescents, 5 arêtes, le nœud du bas posé dans la coupe. Krakie la soutient par le pied d'un tentacule. La brillance passe d'un nœud à l'autre et sur la coupe, avec un petit saut sur la 3e image.
- Limites :
  - Il n'y a pas de foyer visible : le souffle se réduit à quelques braises.
  - À l'impact, le manche horizontal se confond avec le tentacule qui le tient. On reconnaît la tête du marteau, mais pas le manche.
  - Le trophée mesure 21 px de haut. Il mord sur la tête et oblige à décaler Krakie vers la gauche.

## Proposition 2 : L'atelier (`p2-atelier`)

- Intention : c'est la proposition la plus « forge » et la plus narrative. Un foyer de pierre à gauche a des flammes animées et de la fumée, et des coups de soufflet le font monter et cracher des braises (images 1, 7 et 8). L'enclume est au centre, Krakie à droite frappe avec le tentacule gauche. Le cycle de frappe est le même que dans la proposition 1, sur 8 images (1 110 ms).
- Trophée : un graphe forgé de 5 nœuds (deux, un, deux) aux arêtes d'acier, monté sur un socle d'acier qui rappelle l'enclume. Krakie le brandit au-dessus du foyer, qui reste allumé. Les étoiles et le reflet circulent.
- Palette : c'est la seule proposition qui utilise `c`, `e` et la fumée `g`. C'est aussi celle où l'orange domine le plus, et elle se lit très bien sur fond sombre grâce au feu.
- Limites :
  - L'image est la plus chargée. À ×1, on voit surtout un feu, une enclume et une pieuvre, et le marteau devient un petit trait gris.
  - La silhouette de Krakie est réduite : rx 9,5, tentacules sans le T7.
  - Le trophée sur socle se reconnaît à ×2, mais à ×1 ce n'est plus qu'une tache de points dorés.

## Proposition 3 : Deux marteaux (`p3-deux-marteaux`)

- Intention : une variante emblème, symétrique et propre à une pieuvre : Krakie, derrière l'enclume, frappe en alternance avec deux marteaux, comme un batteur. Chaque marteau est levé, puis armé vers l'extérieur, puis frappe, avec un décalage d'une demi-mesure entre les deux. La longue barre s'échauffe à chaque coup, et les étincelles partent du côté du marteau qui frappe. Le souffle est rendu par la pulsation de la barre et des braises qui jaillissent à ses extrémités. Le rythme est le plus vif : 8 images en 920 ms, 2 impacts par boucle.
- Trophée : La coupe la plus large et la plus compacte : 3 nœuds et 1 nœud central dans la vasque, sur 17 px de haut. Krakie la lève à gauche en sautillant et agite l'autre tentacule, dans l'esprit de « contente ».
- Limites :
  - En position « armé » (45°), la tête du marteau devient un bloc peu lisible, et elle touche le bord à gauche.
  - Les marteaux levés sont à hauteur des yeux, ce qui donne un visage encadré, un peu chargé.
  - Il n'y a pas de foyer. Seuls les tentacules latéraux tiennent les marteaux.

## Lisibilité à taille réelle (vérifiée sur `taille-reelle.png` et `planche.png`)

- ×2 (64 px, la taille par défaut du composant `Krakie`) : L'enclume, le marteau en T, le feu (proposition 2) et les trophées se reconnaissent dans les trois propositions.
- ×1 (32 px) :
  - L'enclume se reconnaît toujours, grâce à sa silhouette et à la bigorne.
  - Le marteau levé se reconnaît, mais pas le marteau en diagonale.
  - On voit le trophée comme une coupe dorée surmontée de points, mais on ne distingue pas que c'est un graphe.
  - L'animation compense en partie : impact blanc et étincelles.
- Avis de designer : la proposition 1 se lit le mieux à ×1. La proposition 2 est la plus évocatrice à ×2. La proposition 3 a la meilleure personnalité.

## Pour l'étape 2 (si une proposition est retenue)

- Ajouter la pose (`forge`, plus `trophee` pour la fin de génération) dans `build.py` et `Pose`, puis remplacer `bolide` dans les appels.
- Ajouter `ms` au manifeste. Les animations de 8 images passent déjà par le chargeur, qui accepte N images.
- Prévoir un repli 20 px dans `Krakie.tsx` (`ACC`).
- Fusionner la palette de forge dans `PALETTE`.

# L29, étape 2 : P3 « deux marteaux » intégrée

Jerem a retenu P3. Krakie forgeronne remplace Krakie au volant dans l'interface ; le trophée marque la fin d'une génération réussie.

## Corrections de dessin (`design/krakie/forge_props.py`)
- Marteau incliné : il est maintenant dessiné à la main (`hammer_diag`) au lieu d'être une tête pivotée : manche d'un pixel en bois clair (nouvelle clé `w`, #D9A066) qui ressort sur le contour sombre, tête en bande d'acier perpendiculaire (arête claire `n`, flanc sombre `N`). Le manche est plus court et décalé vers l'intérieur : plus de contact avec le bord. Les marteaux levés et la frappe utilisent aussi le manche clair.
- Trophée : 3 nœuds en triangle (deux en haut, un dans la vasque) et 3 arêtes ; la coupe dorée est conservée (13 × 18 px). Les nœuds ont la même forme arrondie, sans bloc noir.
- Limite restante : à ×1 (32 px) l'inclinaison se lit comme un marteau penché plutôt que comme un geste, et le triangle du trophée se réduit à trois points dorés reliés. Aux tailles d'usage (×2 et au-dessus), manche, tête et graphe se distinguent.
- Planches et GIF : `journal/L29/final/` (`planche-x8-claire.png`, `planche-x8-sombre.png`, `planche-x1-x2.png`, `forge.gif`, `forge-sombre.gif`, `trophee.gif`, `sequence.gif`, source `krakie-forge-trophee.json`).

## Pipeline
- `python design/krakie/forge_props.py --integrate` dessine P3 et fusionne `forge` (8 images) et `trophee` (4 images) dans `krakie-32-anim.json` et `krakie-32.json` (image statique : première image), puis appelle `build.py` (SVG statiques, `anim/`, manifeste). `--final` ne rend que les planches. Ne pas lancer `build.py --redraw` ou `--redraw-anim` : ils effaceraient les deux poses.
- `build.py` : palette de forge fusionnée dans `PALETTE`, libellés ajoutés. La pose « bolide » reste dans les sources et les SVG.
- Front : `Pose` = `forge` | `trophee` (plus `bolide`), replis 20 px, attribut `data-pose` sur l'image, `<KrakieStatus>` et `useResultFlash` (trophée 2 s) dans `Krakie.tsx`, toast avec Krakie (`toast(msg, { pose: 'trophee' })`, 2,6 s).

## Usages
| Où | Pendant | À la fin |
|---|---|---|
| Exports | carte forge | carte trophée 2 s |
| Analyse | carte forge | carte trophée 2 s |
| Tableau de bord | Krakie forge (aussi pose d'invitation « générer ») | Krakie trophée 2 s + toast trophée |
| Shapes (génération) | carte forge | carte trophée 2 s |
| Assistant : shapes, brouillon depuis un CSV | pose forge | toast trophée à l'application des shapes |
| Brouillon depuis un document | carte forge | toast trophée |
| Visite guidée, étape Exports | pose forge | — |

Le raisonnement et le dialogue gardent « réfléchit » : ce n'est pas une génération. Mouvement réduit : images fixes (`/krakie/forge.svg`, `/krakie/trophee.svg`).

## Vérifications
- `tools/recette/l29_forge.mjs` : 16 OK / 0 KO (réponses ralenties de 1,8 s ; forge animée puis trophée puis retour à la normale sur exports, analyse et tableau de bord ; toast ; mouvement réduit ; mobile). Captures : `journal/L29/screens/`.
- `npm run build` OK ; `e2e_ui.mjs` 30/30 (un premier passage a donné 29/30, le second 30/30 sans changement : écran à surveiller) ; `english_scan.mjs` 0 suspect ; `grep -rn bolide frontend/src` : aucun résultat.
- Guide : `architecture.md` et `glossaire.md` mis à jour (les poses). `utilisateur.md` ne parle pas du bolide : non modifié (fichier en cours de modification par L31).

## Relectures (à lancer par le lead)
Je n'ai pas d'outil pour créer d'autres agents : les relectures scout (UX) puis doc restent à faire. Points à soumettre au scout : lisibilité du marteau et du trophée à 64 px, présence de la carte forge à côté du bouton « Régénérer », durée du trophée (2 s).
