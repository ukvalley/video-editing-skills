---
name: hinglish-talking-head-reel
description: End-to-end pipeline for editing Hinglish talking-head reels and product-ad reels (1080x1920, Instagram/Shorts) in the ~/video-editing studio — retake removal, tightened pauses, Roman karaoke captions, word-synced motion graphics, layered SFX, music bed, premium grade, -14 LUFS export. Use when the user gives talking-head/speech footage (your channel or any client), says "edit this reel", "new project from inbox", "make a product ad", or asks to re-render/tweak a version of an existing speech reel.
---

# Hinglish talking-head / product-ad reel

Companion to `video-editor-pro` (read its `references/studio-folder-structure.md` and `lessons-and-feedback.md` first). Working dir: the studio (`$VIDEO_STUDIO`, default `~/video-editing`). Keep your own best project as the reference implementation and note its path in the studio CLAUDE.md.

## Folder structure (per project)
```
projects/YYYY-MM-DD_<slug>/
  notes.md   raw/   edit/   work/   exports/
  edit/: clips.json  phrases.json  build_segments.py  segments.json  edit.json  compose.py  captions.ass  gfx_plan.json
```
Create: `./new-project.sh <name>` (moves inbox/* to raw/). Fill notes.md brief (platform, message, CTA, look, music).

## Pipeline
1. **Probe + contact sheet** of raw (`video-editor-pro/scripts/probe.py`, `contact_sheet.sh`). Set `export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH`.
2. **Find speech**: silencedetect → regions; run `whisper-cli -m ~/.cache/whisper-cpp/ggml-medium.bin -l hi` on EACH region.
3. **Take table** in notes.md (line → takes → kept). Keep the LAST clean take; drop false starts, stumbles, stray "accha". → `clips.json`.
4. **Phrases**: `phrases.json` with source in/out + hand-romanised caption text (English words in English spelling). Fix captions here only.
5. **build_segments.py**: tighten pauses to ~0.1 s, cut on breath midpoints, drop fillers; alternate framing zooms from `brand.json` (`[1.0,1.04]` ↔ `[1.13,1.16]`); transitions ONLY at section changes (whip, zoom-punch, glitch, flash on CTA). Writes `segments.json` + `edit.json`.
6. **Base render**: `python3 ~/.claude/skills/video-editor-pro/scripts/edl_render.py edit/edit.json` with the look from `assets/luts/looks.json` (`warm_clean`+vignette 0.25 for plain office; `premium_cinematic` grade + finish for premium; neutralise colour casts first).
7. **compose.py**: graphics from `toolkit/gfx*.py` anchored to spoken words (via `toolkit/timeline.py`), drawtext titles (brand.json), karaoke ASS captions (Montserrat Black 100, 3 words/line, y=0.7, uppercase, highlight yellow), SFX schedule (+6 dB, transitions +9 dB, layered), music bed ducked under voice. Flags: `--preview` fast, `--gfx` re-render graphics, `--stills` graphic stills.
8. **Preview → approval → Master**: first `compose.py --preview` + normalize → `exports/vN_preview_<what>.mp4` and WAIT for the user to approve; then full render, `normalize_audio.sh work/mix.mov work/norm.mov --target -11 --tp -1.5` → `ffmpeg -c:v copy -c:a aac -b:a 320k -movflags +faststart exports/vN_<what>.mp4` → `qc.py --platform reels` must PASS.
9. **Filler/stutter check** (re-transcribe silence-gated chunks), look at frames, then append to notes.md edit log.

## Faster path with the shared scripts (proven on an English launch reel, approved at first preview)
- Transcript: `video-studio/scripts/eleven.py stt` (Scribe, ~18 credits/min, exact verbatim word times in any language)
  when words drive graphics; whisper-cpp per region stays the free option.
- Cut: `edit/keeps.json` (one segment per kept phrase) → `keep_render.py`; punch-in crop on alternate segments from
  `face_track.py --zoom 1.12` hides every jump cut. Retakes: keep the last clean take, find a stutter's clean onset in a
  long Scribe word from the 10 ms RMS envelope (burst → silence → word).
- Compose in ONE pass: decode the graded base as raw frames → draw word-anchored graphics with `motion-graphics/scripts/mg.py`
  → encode with the ASS captions burned in → mix voice chain + SFX + ducked music. Template: `examples/compose_single_pass.py`
  (scenes, SFX schedule, section zoom-punches, end card, `--stills` for checks).
- **Handheld mic / mic at the mouth:** the mouth+mic sit around y 900–1050 in 1080x1920. Put graphics in a band centred
  around y≈1400 (chest) and captions between them (position ≈0.615). Hide captions while a graphic shows the same words
  (e.g. a list grid). Check stills: nothing may cover the mouth.
- Master −11 LUFS with `--tp -2.2` (→ about −1.9 dBTP after AAC 320k); QC with `qc.py --platform reels --lufs -11`.

## Style defaults (user-approved)
Full treatment unasked: premium grade, B-roll-style data graphics synced to words, transitions at section changes, loud layered SFX, crisp full-res graphics (never blurred plate), real logo end card (sheen + CTA tap), karaoke Roman captions. Product ads: client brand colours on a light canvas (e.g. a violet→blue gradient #683CEC→#185CE8), brand kit in `assets/brand/<client>/`, CTA matching the ad button ("Tap Learn More"). Add new reusable graphics to `toolkit/`, not the project.

## Thumbnails (always)
With every export (and alongside every preview) make `exports/vN_cover_reels_1080x1920.jpg` (all text inside the centre 1080x1440 = Instagram 3:4 grid crop) and `exports/vN_thumb_youtube_1280x720.jpg` from the sharpest full-res photo/frame, graded like the video, bold Montserrat Black title + brand-yellow highlight + real logo. Use the `thumbnail-designer` skill.
