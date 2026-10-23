#!/usr/bin/env bash
# Thumbnail grid of a video so you can SEE the footage / verify an edit.
#
# Usage: bash contact_sheet.sh in.mp4 [out.jpg] [--every 2] [--cols 6] [--width 320] [--every-beat beats.json] [--scenes]
#   --every N        one frame every N seconds (default: auto, ~48 frames total)
#   --every-beat F   one frame per beat from beat_detect.py output (verify beat-synced cuts)
#   --scenes         one frame per detected scene cut (threshold 0.35)
# Each tile is stamped with its timestamp.
set -euo pipefail
IN="${1:?input}"; shift
OUT=""; EVERY=""; COLS=6; W=320; BEATS=""; SCENES=0
while [[ $# -gt 0 ]]; do case "$1" in
  --every) EVERY="$2"; shift 2;; --cols) COLS="$2"; shift 2;; --width) W="$2"; shift 2;;
  --every-beat) BEATS="$2"; shift 2;; --scenes) SCENES=1; shift;; *) OUT="$1"; shift;; esac; done
[[ -z "$OUT" ]] && OUT="${IN%.*}_sheet.jpg"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
FONT=$(python3 - <<'EOF'
import os
for c in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf","/System/Library/Fonts/Supplemental/Arial.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
    if os.path.exists(c): print(c); break
EOF
)
FONTOPT=""; [[ -n "$FONT" ]] && FONTOPT="fontfile='$FONT':"

if [[ -n "$BEATS" ]]; then
  SEL=$(python3 -c "import json;b=json.load(open('$BEATS'))['beats'];print('+'.join(f'between(t,{x:.3f},{x+0.02:.3f})' for x in b[:120]))")
  VF="select='$SEL'"
elif [[ $SCENES -eq 1 ]]; then
  VF="select='gt(scene,0.35)+eq(n,0)'"
else
  [[ -z "$EVERY" ]] && EVERY=$(python3 -c "print(max(0.5, round($DUR/48,2)))")
  VF="fps=1/$EVERY"
fi
N=$(python3 -c "print(int($DUR/${EVERY:-1})+2 if '$BEATS'=='' and $SCENES==0 else 200)")
ROWS=$(( (N + COLS - 1) / COLS )); [[ $ROWS -lt 1 ]] && ROWS=1; [[ $ROWS -gt 40 ]] && ROWS=40
ffmpeg -hide_banner -loglevel error -y -i "$IN" -vf "$VF,scale=$W:-2,drawtext=${FONTOPT}text='%{pts\:hms}':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6:x=6:y=6,tile=${COLS}x${ROWS}:padding=4:margin=4:color=0x202020" -frames:v 1 -q:v 3 -fps_mode vfr "$OUT"
echo "$OUT"
