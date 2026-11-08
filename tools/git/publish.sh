#!/usr/bin/env bash
# Publication d'OntoForge vers le clone léger (agent « git », lot L24).
#
# Copie l'état COMMITTÉ du dépôt de travail (git archive HEAD) dans le clone de publication,
# sans ref/, journal/L18/video/ ni *.whl, recherche des secrets, puis committe.
# Ne pousse que si --push est passé. Voir docs/guide/contribuer.md §Publication.
#
# Usage : tools/git/publish.sh "Lot L22 : éditeur de fichiers" [--push]
# Variables : ONTOFORGE_SRC (dépôt de travail), ONTOFORGE_PUB (clone de publication), PUBLISH_BRANCH (main)
set -euo pipefail

SRC="${ONTOFORGE_SRC:-/home/claude/OntoForge}"
PUB="${ONTOFORGE_PUB:-/home/claude/ontoforge-pub}"
BRANCH="${PUBLISH_BRANCH:-main}"
TRAILERS=$'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01UouNN3yxpAQp9R4L3qaZWh'

MESSAGE=""
PUSH=0
for arg in "$@"; do
  case "$arg" in
    --push) PUSH=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) if [ -z "$MESSAGE" ]; then MESSAGE="$arg"; else echo "Argument inattendu : $arg" >&2; exit 2; fi ;;
  esac
done
[ -n "$MESSAGE" ] || { echo "Usage : $0 \"message de commit\" [--push]" >&2; exit 2; }

git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1 || { echo "Dépôt de travail introuvable : $SRC" >&2; exit 1; }
git -C "$PUB" rev-parse --git-dir >/dev/null 2>&1 || { echo "Clone de publication introuvable : $PUB" >&2; exit 1; }
[ "$(git -C "$PUB" rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || { echo "Le clone de publication doit être sur la branche $BRANCH." >&2; exit 1; }
[ -z "$(git -C "$PUB" status --porcelain --untracked-files=no)" ] || { echo "Le clone de publication a des modifications non commitées : $PUB" >&2; exit 1; }

if [ -n "$(git -C "$SRC" status --porcelain --untracked-files=no)" ]; then
  echo "Attention : le dépôt de travail a des modifications non commitées ; seul HEAD est publié." >&2
fi

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# 1. État committé, hors exclusions
git -C "$SRC" archive HEAD | tar -x -C "$STAGE"
rm -rf "$STAGE/ref" "$STAGE/journal/L18/video"
find "$STAGE" -type f -name '*.whl' -delete

# 2. Recherche de secrets sur ce qui sera publié
# Clés d'exemple connues des tests (littéraux exacts, jamais de motif large).
KNOWN_EXAMPLES=(
  'sk-ant-SECRET-1234567890abcd'   # backend/tests/test_settings_api.py
)
fail=0
PATTERN='sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|AQ\.Ab[0-9A-Za-z_.-]{20,}|ghp_[A-Za-z0-9]{30,}|nvapi-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*(PRIVATE KEY|CERTIFICATE|PGP)'
hits="$(grep -rIEno "$PATTERN" "$STAGE" 2>/dev/null || true)"
while IFS= read -r line; do
  [ -n "$line" ] || continue
  match="${line#*:*:}"
  known=0
  for ex in "${KNOWN_EXAMPLES[@]}"; do
    # sans « -E » : comparaison littérale du début de la clé trouvée
    case "$match" in "$ex"*) known=1 ;; esac
  done
  if [ "$known" -eq 0 ]; then echo "SECRET ? ${line#"$STAGE"/}" >&2; fail=1; fi
done <<< "$hits"

# Fichiers .env (hors modèles) et settings.json contenant api_key
while IFS= read -r f; do
  echo "SECRET ? fichier interdit : ${f#"$STAGE"/}" >&2; fail=1
done < <(find "$STAGE" -type f \( -name '.env' -o -name '.env.*' \) ! -name '.env.example' ! -name '.env.sample' ! -name '.env.template')
while IFS= read -r f; do
  if grep -Eq '"?api_key"?[[:space:]]*[:=]' "$f"; then echo "SECRET ? api_key dans ${f#"$STAGE"/}" >&2; fail=1; fi
done < <(find "$STAGE" -type f -name 'settings.json')

if [ "$fail" -ne 0 ]; then
  echo "Recherche de secrets : ECHEC, aucun commit." >&2
  exit 1
fi
echo "Recherche de secrets : OK."

# 3. Synchronisation dans le clone (tout sauf .git)
find "$PUB" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -a "$STAGE"/. "$PUB"/

# 4. Commit
git -C "$PUB" add -A
if git -C "$PUB" diff --cached --quiet; then
  echo "Rien à publier : le clone est déjà à jour."
  exit 0
fi
git -C "$PUB" commit -q -m "$MESSAGE" -m "$TRAILERS"
echo "Commit local : $(git -C "$PUB" log --oneline -1)"

# 5. Push uniquement sur demande
if [ "$PUSH" -eq 1 ]; then
  git -C "$PUB" push origin "$BRANCH"
else
  echo "Pas de push (ajouter --push pour publier)."
fi
