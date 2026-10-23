---
name: cinematic-beat-reel
description: Build music-only cinematic reels (no speech) from phone clips and photos, cut on the song's beat grid with true slow-mo, bloom/vignette/grain grade, flash+boom on the drop, shutter SFX on photos and bold title cards — e.g. car delivery, wedding, travel, celebration, unboxing reels in ~/video-editing. Use when the user supplies a song plus clips/photos and wants a "cinematic reel", "beat-synced edit", or "delivery/celebration video".
---

# Cinematic beat-synced reel

Companion to `video-editor-pro` (read `references/studio-folder-structure.md`, `lessons-and-feedback.md`). Reference: `projects/2026-10-16_car-delivery-cinematic-reel` (22.7 s, 97 BPM, 19 shots, v1→v3).

## Folder structure
```
projects/YYYY-MM-DD_<slug>/
  raw/  (clips IMG_*.MOV, photos *.JPG, song .mp3)
  edit/ plan.py  build_shots.py  compose.py  ff.sh
  work/ base.mp4 → fx.mp4 → mix      exports/ vN_<what>.mp4     notes.md
```
`ff.sh`: `exec /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -nostdin "$@"` (backgrounded ffmpeg stalls without -nostdin).

## Pipeline
1. **Probe all clips** (fps, orientation, duration) + contact sheet; pick the hero, detail, ritual and wide shots. 60 fps phone clips enable 0.5× true slow-mo.
2. **Beat grid**: `video-editor-pro/scripts/beat_detect.py song` → BPM, beat length, first beat. In `plan.py`: `T(n)=FIRST+BEAT*n`, cut frames snapped to `round(T*FPS)`.
3. **SHOTS list** `(start_beat, clip, src_in, speed, ("in"|"out", amount), (fx,fy))`. Structure by bar: hero slow-mo opener → beauty details (slow) → the ritual at 1 beat/shot → build → DROP (wide shots, flash + boom at the drop beat) → slow side shots → emotional moment → photos at the end (shutter SFX, white flashes) → hero photo with title → fade out. Long shots on slow bars, 1-beat cuts for energy.
4. **build_shots.py** → `work/base.mp4` (eased push/pull, focus point per shot).
5. **FX pass (separate ffmpeg)**: cinematic grade (rolled highlights, teal shadows/warm highlights), bloom, vignette, grain → `work/fx.mp4`. Keep this separate from the overlay pass.
6. **compose.py**: titles, white/amber flashes (`FLASHES = (beat, colour, dur, alpha)`), SFX (boom_hit/sub_drop on drop, riser before it, shutter on photos), song master → composite.
7. **Deliver**: normalize `-14 LUFS`, `--tp -1.5`, AAC 320k, `qc.py --platform reels`. Contact-sheet the result.

## Title rules (learned from feedback)
Bold Optima-style titles with a strong gradient/shadow – faint titles were rejected (v1→v2). Keep text inside safe margins (v3). Put end-card text over plain areas (e.g. roof) so faces/number plates stay clear. Typical end card: WELCOME HOME / FAMILY NAME / DELIVERY DAY.

## Thumbnails (always, user request 2026-10-16)
With every export (and alongside every preview) make `exports/vN_cover_reels_1080x1920.jpg` (all text inside the centre 1080x1440 = Instagram 3:4 grid crop) and `exports/vN_thumb_youtube_1280x720.jpg` from the sharpest full-res photo/frame, graded like the video, bold Montserrat Black title + brand-yellow highlight + real logo. Use the `thumbnail-designer` skill.
