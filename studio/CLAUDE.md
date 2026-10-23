# Video editing studio — instructions for Claude

Multi-project video editing (Hinglish talking-head reels, podcasts, explainers, courses, ads). Start every video job with the `video-studio` hub skill: it picks the specialist skill (talking-head reel, podcast, long-to-shorts, motion graphics, product explainer, course, YouTube long-form, ad variants, beat reel, thumbnails) and holds the shared scripts. `video-editor-pro` covers the general craft.
For motion-graphics product explainers / 30 s ads for any company (no presenter), use the `product-explainer-video` skill (`~/.claude/skills/product-explainer-video/`; start with its `scripts/init_project.sh <company> explainer|ad30`).

## Layout rules
- New footage arrives in `inbox/`. Create a project with `./new-project.sh <short-name>` (projects/YYYY-MM-DD_<slug>/).
- Per project: `raw/` is never modified · `edit/` holds small, reproducible decision files + scripts · `work/` holds intermediates (deletable) · `exports/` holds deliverables named `vN_<what-changed>.mp4` · `notes.md` holds the brief + edit log (append each version).
- Shared, reusable things go in `assets/` (sfx, music, fonts, brand, luts, broll, overlays) and `toolkit/` (code). Never copy shared assets into a project; reference them.
- Read `assets/brand/brand.json` for colours, fonts, caption/title style, audio levels and zoom alternation, and `assets/luts/looks.json` for the grade. Keep new videos consistent with them unless the user asks otherwise.

## Environment gotchas
- Use `export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH` for every ffmpeg call: the default Homebrew ffmpeg lacks drawtext/libass (titles, captions).
- ffmpeg is v9: use `-fps_mode`, not `-vsync`.
- pip is blocked (PEP 668). Install Python packages with brew (numpy, pillow are installed).
- Transcription: `whisper-cli -m ~/.cache/whisper-cpp/ggml-medium.bin -l hi` (Hindi mode transcribes Hinglish correctly; `-l en` translates instead). Its word timestamps drift, so find speech regions with silencedetect, transcribe each phrase separately, then romanise the captions by hand (English words in English spelling).
- Watch for retakes (the speaker often repeats a line 2-3 times). Keep the last clean take.

## Proven talking-head pipeline
1. probe + contact sheet → silencedetect speech regions → per-region Whisper → pick takes (`clips.json`).
2. Phrase split (`phrases.json`) + Roman captions (`roman.json`) → `build_segments.py` tightens pauses to ~0.1 s, drops fillers, and adds whip/zoom-punch only at section changes.
3. `edl_render.py edit_v2.json` → graded base (warm_clean + vignette 0.25, alternating zooms).
4. `compose.py`: `toolkit/gfx.py` motion graphics anchored to spoken words, drawtext titles, karaoke ASS captions, SFX schedule (+6 dB boost, transitions +9 dB) → composite.
5. `normalize_audio.sh --target instagram` → AAC export → `qc.py --platform reels`. Check frames visually before delivering.

User preferences so far: likes rich edits (B-roll graphics, SFX, transitions, grade); wants SFX clearly audible; noticed and disliked a soft/blurry background, so keep graphics crisp at full resolution.
