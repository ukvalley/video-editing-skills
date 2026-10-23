#!/usr/bin/env bash
# Transcribe speech to SRT (+ word-level JSON) with Whisper, and optionally build animated ASS captions.
#
# Usage: bash transcribe.sh in.mp4 [--model medium] [--lang en] [--words] [--ass-style karaoke|clean] [--out-dir .]
#        [--font Montserrat] [--size 64] [--color &H00FFFFFF] [--highlight &H0000A5FF] [--words-per-line 4] [--playres 1080x1920]
#
# Requires one of:  pip3 install openai-whisper   (python module 'whisper')
#                   brew install whisper-cpp       (binary 'whisper-cli' / 'whisper-cpp', needs a model .bin)
# Outputs: <name>.srt, <name>.words.json (if --words or --ass-style), <name>.ass (if --ass-style)
set -euo pipefail
IN="${1:?input}"; shift
MODEL="medium"; LANG=""; WORDS=0; ASS=""; OUTDIR="."; FONT="Montserrat"; SIZE=64; COLOR="&H00FFFFFF"; HL="&H0000A5FF"; WPL=4; PLAYRES="1080x1920"
while [[ $# -gt 0 ]]; do case "$1" in
  --model) MODEL="$2"; shift 2;; --lang) LANG="$2"; shift 2;; --words) WORDS=1; shift;;
  --ass-style) ASS="$2"; WORDS=1; shift 2;; --out-dir) OUTDIR="$2"; shift 2;;
  --font) FONT="$2"; shift 2;; --size) SIZE="$2"; shift 2;; --color) COLOR="$2"; shift 2;;
  --highlight) HL="$2"; shift 2;; --words-per-line) WPL="$2"; shift 2;; --playres) PLAYRES="$2"; shift 2;;
  *) echo "unknown arg $1" >&2; exit 1;; esac; done
mkdir -p "$OUTDIR"
BASE="$OUTDIR/$(basename "${IN%.*}")"
WAV="$BASE.16k.wav"
ffmpeg -hide_banner -loglevel error -y -i "$IN" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$WAV"

if python3 -c "import whisper" 2>/dev/null; then
  echo "transcribing with openai-whisper ($MODEL)..." >&2
  python3 - "$WAV" "$BASE" "$MODEL" "$LANG" "$WORDS" <<'EOF'
import sys, json, whisper
wav, base, model, lang, words = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1"
m = whisper.load_model(model)
r = m.transcribe(wav, language=lang or None, word_timestamps=words, verbose=False)
def ts(t):
    h=int(t//3600); m_=int(t%3600//60); s=t%60
    return f"{h:02d}:{m_:02d}:{int(s):02d},{int((s-int(s))*1000):03d}"
with open(base+".srt","w") as f:
    for i,seg in enumerate(r["segments"],1):
        f.write(f"{i}\n{ts(seg['start'])} --> {ts(seg['end'])}\n{seg['text'].strip()}\n\n")
if words:
    out=[]
    for seg in r["segments"]:
        for w in seg.get("words",[]):
            out.append({"word":w["word"].strip(),"start":round(w["start"],3),"end":round(w["end"],3)})
    json.dump({"language":r.get("language"),"words":out},open(base+".words.json","w"),indent=1)
print(base+".srt")
EOF
elif command -v whisper-cli >/dev/null || command -v whisper-cpp >/dev/null; then
  BIN=$(command -v whisper-cli || command -v whisper-cpp)
  MODELFILE="${WHISPER_MODEL:-$HOME/.cache/whisper-cpp/ggml-$MODEL.bin}"
  [[ -f "$MODELFILE" ]] || { echo "whisper.cpp model not found at $MODELFILE. Download a ggml model and set WHISPER_MODEL=/path/ggml-$MODEL.bin" >&2; exit 1; }
  echo "transcribing with whisper.cpp..." >&2
  "$BIN" -m "$MODELFILE" -f "$WAV" -osrt -of "$BASE" ${LANG:+-l $LANG} >/dev/null
  if [[ $WORDS -eq 1 ]]; then
    "$BIN" -m "$MODELFILE" -f "$WAV" -ojf -of "$BASE.raw" -ml 1 ${LANG:+-l $LANG} >/dev/null
    python3 - "$BASE" <<'EOF'
import sys, json
base=sys.argv[1]; j=json.load(open(base+".raw.json"))
words=[]
for s in j.get("transcription",[]):
    t=s["text"].strip()
    if not t: continue
    words.append({"word":t,"start":s["offsets"]["from"]/1000,"end":s["offsets"]["to"]/1000})
json.dump({"words":words},open(base+".words.json","w"),indent=1)
EOF
  fi
else
  echo "No Whisper found. Install: pip3 install openai-whisper   (or: brew install whisper-cpp)" >&2; exit 1
fi
rm -f "$WAV"

if [[ -n "$ASS" ]]; then
  python3 "$(dirname "$0")/captions_ass.py" "$BASE.words.json" "$BASE.ass" --style "$ASS" --font "$FONT" --size "$SIZE" \
    --color "$COLOR" --highlight "$HL" --words-per-line "$WPL" --playres "$PLAYRES"
fi
