#!/usr/bin/env bash
# Master + export one render (work/mix_*.mov from render.py) to the deliverable specs proven on real client deliveries.
#
#   deliver.sh <project_dir> <work/mix_XXX.mov> <export_name> youtube|reels|tv
#
#   youtube : -14 LUFS, --tp -2.0 (AAC overshoots: -1.5 came out -0.6), 16:9 -> exports/<name>.mp4 (master, CRF 14 from render)
#             + exports/<name>_upload.mp4 (H.264 CRF 18, maxrate 16M), qc.py --platform youtube
#   reels   : same audio/video specs for 9:16 (Shorts / Reels), qc.py --platform reels
#   tv      : render with --fps 25 first. -24 LKFS / -2 dBTP, ProRes 422 HQ 10-bit, BT.709 tags, PCM 24-bit 48 kHz stereo
#             -> exports/<name>.mov; checks duration (an ad must be exactly 30.000 s) and loudness
# Intermediates go to work/norm_<name>.*; exports/ only ever gets the named deliverables.
set -euo pipefail
export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH
VEP="$HOME/.claude/skills/video-editor-pro/scripts"
P="${1:?project dir}"; MIX="${2:?work/mix_*.mov}"; NAME="${3:?export name, e.g. v2_final_30s-ad_en_youtube_1080p30}"; TARGET="${4:?youtube|reels|tv}"
cd "$P"; mkdir -p exports work
[[ -f "$MIX" ]] || { echo "no such mix: $MIX" >&2; exit 1; }

case "$TARGET" in
  youtube|reels)
    bash "$VEP/normalize_audio.sh" "$MIX" "work/norm_$NAME.mov" --target youtube --tp -2.0 >/dev/null
    ffmpeg -nostdin -y -v error -i "work/norm_$NAME.mov" -c copy -movflags +faststart "exports/$NAME.mp4"
    ffmpeg -nostdin -y -v error -i "work/norm_$NAME.mov" -c:v libx264 -preset slow -crf 18 -maxrate 16M -bufsize 32M \
      -pix_fmt yuv420p -c:a copy -movflags +faststart "exports/${NAME}_upload.mp4"
    PLAT=$([[ "$TARGET" == reels ]] && echo reels || echo youtube)
    python3 "$VEP/qc.py" "exports/$NAME.mp4" --platform "$PLAT"
    python3 "$VEP/qc.py" "exports/${NAME}_upload.mp4" --platform "$PLAT"
    ;;
  tv)
    ffmpeg -nostdin -y -v error -i "$MIX" -vn -c:a pcm_s24le -ar 48000 "work/norm_${NAME}_in.wav"
    bash "$VEP/normalize_audio.sh" "work/norm_${NAME}_in.wav" "work/norm_$NAME.wav" --target atsc >/dev/null
    ffmpeg -nostdin -y -v error -i "$MIX" -i "work/norm_$NAME.wav" -map 0:v -map 1:a \
      -c:v prores_ks -profile:v 3 -vendor apl0 -pix_fmt yuv422p10le \
      -color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv \
      -c:a pcm_s24le -ar 48000 -ac 2 -shortest "exports/$NAME.mov"
    ffprobe -v error -show_entries format=duration:stream=codec_name,profile,width,height,r_frame_rate,pix_fmt,sample_rate -of compact "exports/$NAME.mov"
    ffmpeg -hide_banner -nostats -i "exports/$NAME.mov" -af ebur128=peak=true -vn -f null - 2>&1 | grep -E "^\s+(I|LRA|Peak):" | tail -3
    echo "black segments: $(ffmpeg -hide_banner -nostats -i "exports/$NAME.mov" -vf blackdetect=d=0.08:pix_th=0.10 -an -f null - 2>&1 | grep -c black_start || true)"
    ;;
  *) echo "target must be youtube|reels|tv" >&2; exit 1;;
esac
ls -la exports | grep -F "$NAME"
