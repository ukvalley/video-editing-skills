#!/usr/bin/env bash
# Create a new video project from the template and move everything in inbox/ into its raw/ folder.
# Usage: ./new-project.sh <short-name> [YYYY-MM-DD]
#   ./new-project.sh pricing-objection-reel        -> projects/2026-10-16_pricing-objection-reel/
set -euo pipefail
cd "$(dirname "$0")"
NAME="${1:?usage: ./new-project.sh <short-name> [date]}"
DATE="${2:-$(date +%Y-%m-%d)}"
SLUG=$(echo "$NAME" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
DEST="projects/${DATE}_${SLUG}"
[[ -e "$DEST" ]] && { echo "already exists: $DEST" >&2; exit 1; }
cp -R projects/_template "$DEST"
find "$DEST" -name .keep -delete
shopt -s nullglob
moved=0
for f in inbox/*; do
  [[ "$(basename "$f")" == "README.md" ]] && continue
  mv "$f" "$DEST/raw/"; moved=$((moved+1))
done
echo "created $DEST  ($moved file(s) moved from inbox/ into raw/)"
echo "next: fill in $DEST/notes.md, then ask Claude to edit it"
