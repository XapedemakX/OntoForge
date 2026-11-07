"""``python -m ontoforge.settings rotate`` — ONTOFORGE_SECRET_KEY_OLD (ancienne clé ; vide = fichier .secret) et
ONTOFORGE_SECRET_KEY (nouvelle) doivent être définies."""
import os
import sys

from . import crypto, store


def main() -> int:
    if sys.argv[1:] != ["rotate"]:
        print(__doc__)
        return 2
    new = os.environ.get("ONTOFORGE_SECRET_KEY", "").strip()
    old = os.environ.get("ONTOFORGE_SECRET_KEY_OLD", "").strip()
    if not new:
        print("ONTOFORGE_SECRET_KEY (nouvelle clé) doit être définie.")
        return 2
    if not old:
        f = crypto.data_dir() / ".secret"
        if not f.exists():
            print("ONTOFORGE_SECRET_KEY_OLD absente et pas de fichier .secret.")
            return 2
        old = f.read_text(encoding="utf-8").strip()
    try:
        n = store.rotate(old, new)
    except crypto.SecretError as exc:
        print(exc)
        return 1
    print(f"{n} secret(s) rechiffré(s). Redémarrez le backend avec la nouvelle ONTOFORGE_SECRET_KEY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
