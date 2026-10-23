#!/usr/bin/env bash
# Synthesise placeholder SFX (whoosh, impact, riser, ping, glitch, click) so every transition can carry a sound
# even before the user supplies a real library. Replace with real samples (freesound.org, Mixkit, Zapsplat) when available.
#
# Usage: bash make_sfx.sh [out_dir]   (default: sfx/)
set -euo pipefail
OUT="${1:-sfx}"; mkdir -p "$OUT"
F="ffmpeg -hide_banner -loglevel error -y"
$F -f lavfi -i "anoisesrc=d=0.4:c=pink:a=0.6"  -af "lowpass=f=2500,afade=t=in:d=0.12:curve=exp,afade=t=out:st=0.18:d=0.22" "$OUT/whoosh.wav"
$F -f lavfi -i "sine=f=55:d=0.6" -af "afade=t=out:st=0.05:d=0.55,volume=0.9" "$OUT/impact.wav"
$F -f lavfi -i "anoisesrc=d=2:c=white:a=0.3" -af "lowpass=f=3000,afade=t=in:d=1.8:curve=exp" "$OUT/riser.wav"
$F -f lavfi -i "sine=f=1760:d=0.5" -af "afade=t=out:st=0.02:d=0.45,volume=0.35" "$OUT/ping.wav"
$F -f lavfi -i "anoisesrc=d=0.25:c=white:a=0.5" -af "acrusher=bits=4:mode=log:aa=0,tremolo=f=40:d=1,afade=t=out:st=0.1:d=0.15" "$OUT/glitch.wav"
$F -f lavfi -i "sine=f=2200:d=0.05" -af "afade=t=out:st=0.005:d=0.045,volume=0.4" "$OUT/click.wav"
# EDL snippet to paste:
cat <<EOF
"auto_sfx": {"whoosh": "$OUT/whoosh.wav", "impact": "$OUT/impact.wav", "flash": "$OUT/ping.wav", "glitch": "$OUT/glitch.wav"}
EOF
