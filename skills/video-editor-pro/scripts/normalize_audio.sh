#!/usr/bin/env bash
# Two-pass loudness normalisation (EBU R128 loudnorm) + true-peak limiter, keeps video stream untouched.
#
# Usage: bash normalize_audio.sh in.mp4 [out.mp4] [--target youtube|podcast|broadcast|atsc|-14] [--tp -1] [--lra 11]
# Targets: youtube/social -14 LUFS, podcast -16, broadcast(EBU) -23, atsc -24. Default youtube.
set -euo pipefail
IN="${1:?input file}"; shift || true
OUT=""
TARGET="youtube"; TP="-1"; LRA="11"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2;;
    --tp) TP="$2"; shift 2;;
    --lra) LRA="$2"; shift 2;;
    *) OUT="$1"; shift;;
  esac
done
case "$TARGET" in
  youtube|social|instagram|tiktok|linkedin) I="-14";;
  podcast|spotify|review) I="-16";;
  broadcast|ebu) I="-23"; LRA="15";;
  atsc) I="-24"; TP="-2"; LRA="15";;
  *) I="$TARGET";;
esac
[[ -z "$OUT" ]] && OUT="${IN%.*}_norm.${IN##*.}"

echo "pass 1: measuring..." >&2
STATS=$(ffmpeg -hide_banner -nostats -i "$IN" -af "loudnorm=I=$I:TP=$TP:LRA=$LRA:print_format=json" -vn -f null - 2>&1 | sed -n '/^{/,/^}/p')
get() { echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['$1'])"; }
MI=$(get input_i); MTP=$(get input_tp); MLRA=$(get input_lra); MTH=$(get input_thresh); OFF=$(get target_offset)
echo "measured: I=$MI LUFS  TP=$MTP dBTP  LRA=$MLRA  -> target I=$I TP=$TP" >&2

LIMIT=$(python3 -c "print(round(10**($TP/20),4))")
AF="loudnorm=I=$I:TP=$TP:LRA=$LRA:measured_I=$MI:measured_TP=$MTP:measured_LRA=$MLRA:measured_thresh=$MTH:offset=$OFF:linear=true:print_format=summary,alimiter=limit=$LIMIT:attack=5:release=50:level=false"

echo "pass 2: rendering $OUT" >&2
HASV=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "$IN" || true)
if [[ -n "$HASV" ]]; then
  ffmpeg -hide_banner -loglevel error -stats -y -i "$IN" -af "$AF" -ar 48000 -c:v copy -c:a aac -b:a 320k -movflags +faststart "$OUT"
else
  ffmpeg -hide_banner -loglevel error -stats -y -i "$IN" -af "$AF" -ar 48000 "$OUT"
fi
echo "verify:" >&2
ffmpeg -hide_banner -nostats -i "$OUT" -af ebur128=peak=true -vn -f null - 2>&1 | grep -E "I:|LRA:|Peak:" | tail -3 >&2
echo "$OUT"
