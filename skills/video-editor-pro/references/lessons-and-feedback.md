# Lessons & user feedback (learned on real client reels)

## User preferences (explicit feedback)
- Wants "world's best editor" output: premium cinematic grade, rich B-roll-style motion graphics, transitions at section changes. Default to the FULL treatment unprompted.
- SFX must be clearly audible: after v2 they asked for louder → SFX +6 dB, transition SFX +9 dB, layered (whoosh + impact + sub, tick + pop...).
- Soft/blurry graphic backgrounds were rejected → graphics rendered crisp at full 1080x1920, no blurred plate behind them.
- Titles that are too faint get rejected (car reel v1→v2): bold, strong gradient/contrast.
- Titles must sit inside safe margins (car reel v3) – check frames at the edges/UI zones.
- Liked: Roman-script Hinglish karaoke captions, alternating punch-in framing, animated data graphics synced to spoken words, real logo end card with sheen + CTA tap.
- Logos must be real brand assets, crisp (rebuild low-res logos with upscale_logo.py).
- PREVIEW FIRST : send a small 540x960 preview (`compose.py --preview`, mastered like the final) to `exports/vN_preview_<what>.mp4`; the full-quality render + export happens only after the user approves it.
- VOICE TOO QUIET on phone speakers : voice must clearly lead. Dialogue chain: highpass 90, -2 dB @250 Hz, +4 dB @3 kHz, +1.5 dB @6.5 kHz, acompressor -26 dB 4:1 makeup 6, alimiter 0.9; music bed -19 dB (was -15); SFX trimmed -2 dB; master -11 LUFS / -1.5 dBTP (was -14).

## Footage rules
- Speaker retakes lines 2–3×: transcribe EVERY speech region, build a take table, keep the LAST clean take, drop false starts, stumbles and stray "accha".
- Run a filler/stutter check on the final cut (silence-gated chunks re-transcribed) – found "ek ek ek ek" after v2.
- Room light colour casts (magenta/purple LEDs): neutralise with colorbalance BEFORE the studio grade.

## Technical gotchas
- `export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH` — default ffmpeg lacks drawtext/libass.
- ffmpeg 9: `-fps_mode`, not `-vsync`. Wrap in `ff.sh` (`exec ffmpeg -nostdin "$@"`): backgrounded ffmpeg stalls on stdin.
- Whisper: `-l hi` for Hinglish (`-l en` translates). Word timestamps drift → silencedetect regions, transcribe each phrase separately, hand-romanise.
- Keep big filter graphs split: bloom/grade pass separate from the overlay pass (one giant graph hung).
- Normalize with `--tp -1.5` for Instagram: default −1 dBTP came out −0.8 after AAC encode. Target −14 LUFS; QC `--platform reels` must PASS.
- Phone footage 60 fps → 0.5× gives true slow-mo; other speeds are only "ease".
- Only re-render what changed (e.g. `compose.py --gfx` cached graphics; re-render only the `cta` graphic).
- pip blocked (PEP 668): brew install packages. numpy, pillow present.
- Final export: `ffmpeg -c:v copy -c:a aac -b:a 320k -movflags +faststart`, CRF 16 master.
- Always look at frames (contact sheet / stills) before delivering.
- Mixing JPEG photos (decode as full-range yuvj420p) with video shots in one concat → force every shot to `scale=out_range=tv,format=yuv420p` (+ `-color_range tv`); a mid-stream pixel-format flip re-inits the compose filter graph, resets `setpts=N` and collapses the timeline. Also pass `-reinit_filter 0` on the base input.
- Short overlay clips placed late with `-itsoffset` (or `setpts=PTS+X/TB`) were silently dropped by overlay framesync → pad overlays from t=0 with `tpad=start=<frames>:color=black@0` and rebase all streams with `settb=1/30,setpts=N`.
- Seek-sample (`-ss`) for contact sheets of concatenated bases; `select=eq(n,..)` / `fps=1` sheets were unreliable on them.
- Music-only aftermovies: original track via `toolkit/make_hype_track.py` (build + drops, markers JSON); crowd ambience via `toolkit/make_sfx_crowd.py`.
