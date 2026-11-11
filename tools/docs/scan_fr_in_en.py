"""Cherche du texte français dans les captures anglaises (docs/guide/img/en/*.png) par reconnaissance de caractères (tesseract).
Usage : python tools/docs/scan_fr_in_en.py [dossier] [--verbose]
Signale les lignes qui contiennent des lettres accentuées françaises ou des mots-outils français. À relire à la main : les données de
l'ontologie automaint en @fr (libellés sans équivalent anglais) et les noms de propriété sont attendus. Code retour 0 même s'il y a des signalements."""
import re, subprocess, sys
from pathlib import Path

root = Path(next((a for a in sys.argv[1:] if not a.startswith("--")), "docs/guide/img/en"))
verbose = "--verbose" in sys.argv
ACCENT = re.compile(r"[éèêëàâçùûôîï]")
WORDS = re.compile(r"\b(le|la|les|des|du|une|est|pour|dans|sur|avec|aucun|aucune|ou|et un|qui|sont|pas|ne)\b", re.I)
# mots anglais qui ressemblent à des mots-outils français : on ne les compte pas seuls
total = 0
for f in sorted(root.glob("*.png")):
    r = subprocess.run(["tesseract", str(f), "-", "-l", "eng", "--psm", "11"], capture_output=True, text=True)
    hits = []
    for line in r.stdout.splitlines():
        t = line.strip()
        if len(t) < 4: continue
        if ACCENT.search(t) or len(WORDS.findall(t)) >= 2: hits.append(t)
    if hits:
        total += len(hits); print(f"{f.name}: {len(hits)} ligne(s) suspecte(s)")
        for h in hits[:8]: print("    " + h[:110])
    elif verbose: print(f"{f.name}: rien")
print(f"=== {total} ligne(s) suspecte(s) dans {len(list(root.glob('*.png')))} captures")
