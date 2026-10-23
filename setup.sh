#!/usr/bin/env bash
# One-time setup: tools, skills, studio folder, fonts and the generated SFX/music library.
#   ./setup.sh                      studio at ~/video-editing
#   VIDEO_STUDIO=/path ./setup.sh   studio somewhere else
#   ./setup.sh --skills-only        just (re)link the skills into ~/.claude/skills
# Safe to re-run: existing studio files are never overwritten, existing non-linked skills are backed up.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
STUDIO="${VIDEO_STUDIO:-$HOME/video-editing}"
SKILLS_DIR="$HOME/.claude/skills"
say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }

# 1. skills → ~/.claude/skills (symlinks, so `git pull` updates them)
mkdir -p "$SKILLS_DIR"
for s in "$REPO"/skills/*/; do
  name="$(basename "$s")"; dest="$SKILLS_DIR/$name"
  if [[ -e "$dest" && ! -L "$dest" ]]; then
    mv "$dest" "$dest.backup.$(date +%Y%m%d%H%M%S)"; say "backed up existing $name"
  fi
  ln -sfn "${s%/}" "$dest"
done
say "linked $(ls -d "$REPO"/skills/*/ | wc -l | tr -d ' ') skills into $SKILLS_DIR"
[[ "${1:-}" == "--skills-only" ]] && exit 0

# 2. tools (Homebrew)
if ! command -v brew >/dev/null; then
  echo "Homebrew is required: https://brew.sh" >&2; exit 1
fi
for f in ffmpeg-full numpy pillow whisper-cpp; do
  brew list "$f" >/dev/null 2>&1 || { say "brew install $f"; brew install "$f"; }
done
command -v swiftc >/dev/null || say "optional: xcode-select --install (swiftc, for face-follow reframing)"

# 3. studio folder (never overwrites your files)
say "studio: $STUDIO"
mkdir -p "$STUDIO"
rsync -a --ignore-existing "$REPO/studio/" "$STUDIO/"
chmod +x "$STUDIO/new-project.sh"

# 4. open-source fonts (SIL OFL 1.1)
F="$STUDIO/assets/fonts"; mkdir -p "$F"
fetch() { [[ -s "$F/$1" ]] || { say "font $1"; curl -fsSL "$2" -o "$F/$1"; }; }
fetch Montserrat-Black.ttf     https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-Black.ttf
fetch Montserrat-ExtraBold.ttf https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-ExtraBold.ttf
fetch Montserrat-VF.ttf        "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf"
fetch Anton-Regular.ttf        https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf
fetch Caveat-VF.ttf            "https://raw.githubusercontent.com/google/fonts/main/ofl/caveat/Caveat%5Bwght%5D.ttf"
fetch NotoSansDevanagari-VF.ttf "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth,wght%5D.ttf"

# 5. generated, royalty-free SFX + music (skipped if already there)
cd "$STUDIO"
mkdir -p assets/sfx assets/music
[[ -s assets/sfx/whoosh.wav ]] || { say "generating SFX library"; python3 toolkit/make_sfx.py; python3 toolkit/make_sfx_pro.py; python3 toolkit/make_sfx_crowd.py; }
[[ -s assets/music/underscore_100bpm.wav ]] || { say "generating music beds"; python3 toolkit/make_music.py 150 100 underscore_100bpm; python3 toolkit/make_hype_track.py hype_120bpm; }

cat <<EOF

Done. Next steps:
  - Free local transcription model (1.5 GB):
      mkdir -p ~/.cache/whisper-cpp && curl -L -o ~/.cache/whisper-cpp/ggml-medium.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin
  - Optional ElevenLabs (voice-over, Scribe, voice isolation): echo 'ELEVENLABS_API_KEY=...' >> "$STUDIO/.env"
  - Put your logo + colours in $STUDIO/assets/brand/ (brand.json)
  - cd "$STUDIO" && claude     then: "new project from inbox: ..."
EOF
