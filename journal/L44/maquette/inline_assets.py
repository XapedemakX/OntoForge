"""L44 : embarque dans index.html les polices de l'appli (IBM Plex, @fontsource), les icônes Font Awesome utilisées (data-i)
et les sprites de Krakie (frontend/public/krakie). Relançable : remplace le contenu entre les marqueurs."""
import base64, json, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NM = ROOT / 'frontend/node_modules'
html = (HERE / 'index.html').read_text()
b64 = lambda p: base64.b64encode(p.read_bytes()).decode()
fonts = []
for fam, pkg, weights in [('IBM Plex Sans', 'ibm-plex-sans', (400, 500, 600, 700)), ('IBM Plex Mono', 'ibm-plex-mono', (400, 500))]:
    for w in weights:
        f = NM / f'@fontsource/{pkg}/files/{pkg}-latin-{w}-normal.woff2'
        fonts.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;font-display:block;src:url(data:font/woff2;base64,{b64(f)}) format('woff2')}}")
html = re.sub(r'/\*FONTS:start\*/.*?/\*FONTS:end\*/', lambda m: '/*FONTS:start*/' + ''.join(fonts) + '/*FONTS:end*/', html, flags=re.S)
names = sorted(set(re.findall(r'<i data-i="([\w-]+)"', html)))
syms = []
for n in names:
    s = (NM / f'@fortawesome/fontawesome-free/svgs/solid/{n}.svg').read_text()
    vb = re.search(r'viewBox="([^"]+)"', s).group(1)
    paths = ''.join(re.findall(r'<path[^>]*/>', s))
    syms.append(f'<symbol id="i-{n}" viewBox="{vb}">{paths}</symbol>')
html = re.sub(r'<!--ICONS:start-->.*?<!--ICONS:end-->', lambda m: '<!--ICONS:start-->' + ''.join(syms) + '<!--ICONS:end-->', html, flags=re.S)
kr = {k: 'data:image/svg+xml;base64,' + b64(ROOT / f'frontend/public/krakie/{f}.svg') for k, f in
      [('KRAKIE_ACCUEIL', 'accueil'), ('KRAKIE_CONTENTE', 'contente'), ('KRAKIE_REFLECHIT', 'reflechit')]}
block = '<script id="krakie-sprites">/*KRAKIE:start*/window.KRAKIE=' + json.dumps(kr) + ';document.querySelectorAll("img[src^=KRAKIE_]").forEach(i=>{i.src=window.KRAKIE[i.getAttribute("src")]})/*KRAKIE:end*/</script>'
if 'id="krakie-sprites"' in html:
    html = re.sub(r'<script id="krakie-sprites">.*?</script>', lambda m: block, html, flags=re.S)
else:
    html = html.replace('</body>', block + '\n</body>')
(HERE / 'index.html').write_text(html)
print(len(names), 'icônes,', len(fonts), 'polices,', len(html) // 1024, 'Ko')
