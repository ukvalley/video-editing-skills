#!/usr/bin/env bash
# Start a product explainer / 30 s ad project for any company, from inbox/.
#
#   init_project.sh <company-slug> explainer|ad30 [short-name]
#     init_project.sh acme explainer              -> projects/<today>_acme-explainer/
#     init_project.sh acme ad30                   -> projects/<today>_acme-30s-ad/
#
# 1. ./new-project.sh (moves everything in inbox/ into the new project's raw/)
# 2. copies the skill templates into edit/ (make_vo.py, render.py, scenes.py[, scenes_916.py], vo_lines.json, config.json)
# 3. points edit/config.json at assets/brand/<company-slug>/ and creates that folder + brand.json from the template if new
#    (a second video for the same company reuses the brand folder as is)
# 4. writes the explainer brief skeleton into notes.md
set -euo pipefail
STUDIO="${VIDEO_STUDIO:-${STUDIO_ROOT:-$HOME/video-editing}}"
SK="$(cd "$(dirname "$0")/.." && pwd)"
CO="${1:?company slug, e.g. acme}"; KIND="${2:?explainer|ad30}"
CO=$(echo "$CO" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
case "$KIND" in explainer) DEF="$CO-explainer";; ad30) DEF="$CO-30s-ad";; *) echo "kind must be explainer|ad30" >&2; exit 1;; esac
NAME="${3:-$DEF}"
cd "$STUDIO"
OUT=$(./new-project.sh "$NAME"); echo "$OUT"
DEST=$(echo "$OUT" | sed -n 's/^created \([^ ]*\).*/\1/p')
[[ -d "$DEST" ]] || { echo "could not find the new project folder" >&2; exit 1; }
cp "$SK"/templates/common/*.py "$SK/templates/$KIND"/* "$DEST/edit/"
sed -i '' "s#\"assets/brand/acme\"#\"assets/brand/$CO\"#" "$DEST/edit/config.json"
BR="assets/brand/$CO"
if [[ ! -f "$BR/brand.json" ]]; then
  mkdir -p "$BR"; sed "s/\"Acme\"/\"$CO\"/" "$SK/templates/brand/brand.json" > "$BR/brand.json"
  echo "new brand folder $BR (fill brand.json: name, colours from the logo, regions/urls; add logos + screenshots)"
else
  echo "reusing brand folder $BR"
fi
cat > "$DEST/notes.md" <<EOF
# Project brief — $CO $([[ $KIND == ad30 ]] && echo "30 s ad" || echo "product explainer") (motion graphics, no presenter)

- **Platform:** $([[ $KIND == ad30 ]] && echo "16:9 1920x1080 30 fps, exactly 30.00 s (YouTube -14 LUFS; TV 1080p25 ProRes -24 LKFS if asked); 9:16 1080x1920 for Shorts/Reels" || echo "16:9 1920x1080, 30 fps (website / YouTube / sales demo)")
- **Target length:** $([[ $KIND == ad30 ]] && echo "30.00 s" || echo "2–3 min")
- **Language(s) / regions:** (en; hi = Hinglish; other regions = vo_lines_<code>.json + brand.json regions)
- **Voice:** ElevenLabs (default Ruhaan siw1N9V8LmYeEWKyWBxv, mp3_44100_128)
- **Source (raw/):**
- **Brand folder:** \`$BR/\` (brand.json, logos, screenshots)
- **Audience:**
- **Problem:**
- **Product / tagline:**
- **Features (in order):**
- **Proof (numbers, logos, customers):**
- **CTA / domain:**
- **Style reference:**
- **Music:** \`$(python3 -c "import json;print(json.load(open('$DEST/edit/config.json'))['music'])")\`

## Edit log
- v0 — project created with the product-explainer-video skill ($KIND template).
EOF
echo "next: fill $DEST/notes.md + $BR/brand.json, then write the script in $DEST/edit/vo_lines.json (see SKILL.md)"
