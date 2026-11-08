"""``python -m ontoforge.auth hash`` : produit le hachage d'un mot de passe pour ONTOFORGE_AUTH_USERS.

    python -m ontoforge.auth hash --user demo            # demande le mot de passe (sans écho), affiche demo:$argon2id$...
    python -m ontoforge.auth hash --bcrypt               # bcrypt au lieu d'argon2
    echo -n 'motdepasse' | python -m ontoforge.auth hash --stdin --user demo
    python -m ontoforge.auth secret                      # valeur pour ONTOFORGE_SECRET_KEY
"""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from .passwords import hash_password


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ontoforge.auth", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hash", help="hacher un mot de passe")
    h.add_argument("--user", help="affiche « utilisateur:hachage », prêt pour ONTOFORGE_AUTH_USERS")
    h.add_argument("--bcrypt", action="store_true", help="bcrypt au lieu d'argon2id")
    h.add_argument("--stdin", action="store_true", help="lit le mot de passe sur l'entrée standard (scripts)")
    sub.add_parser("secret", help="génère une valeur pour ONTOFORGE_SECRET_KEY")
    a = ap.parse_args(argv)
    if a.cmd == "secret":
        print(secrets.token_urlsafe(48))
        return 0
    if a.stdin:
        pw = sys.stdin.read().rstrip("\r\n")
    else:
        pw = getpass.getpass("Mot de passe : ")
        if getpass.getpass("Confirmer : ") != pw:
            print("Les deux saisies diffèrent.", file=sys.stderr)
            return 2
    if len(pw) < 10:
        print("Mot de passe trop court : 10 caractères au moins (une phrase de passe est préférable).", file=sys.stderr)
        return 2
    try:
        out = hash_password(pw, "bcrypt" if a.bcrypt else "argon2")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if a.user:
        if ":" in a.user or not a.user.strip():
            print("Nom d'utilisateur invalide (sans « : »).", file=sys.stderr)
            return 2
        out = f"{a.user.strip().lower()}:{out}"
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
