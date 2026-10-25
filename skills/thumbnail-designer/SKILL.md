---
name: thumbnail-designer
description: Make YouTube thumbnails (1280x720, A/B variants), Instagram Reels covers (1080x1920 with the 3:4 grid crop safe) and square posts from a video frame or photo — sharpest-frame pick, face-aware layout (text on the side away from the face), punchy grade, bold Montserrat Black title with brand-colour highlight word, real logo. Use when the user asks for a thumbnail, cover, poster frame, "YouTube thumbnail", "reel cover", "thumbnail A/B test", and with every video export in the ~/video-editing studio.
---

# Thumbnails and covers

Script: `T=~/.claude/skills/thumbnail-designer/scripts/thumb.py` (`--help` for all options). Ship one with every export
(`exports/vN_thumb_youtube_1280x720.jpg`, `exports/vN_cover_reels_1080x1920.jpg`).

```
python3 $T --src raw/a.mp4 --title "3X MORE *CALLS* IN 30 DAYS" --logo assets/brand/<client>/logo.png --out exports/v1_thumb_youtube_1280x720.jpg --variants 3
python3 $T --src raw/a.mp4 --at 41.2 --title "STOP LOSING *LEADS*" --format cover --out exports/v1_cover_reels_1080x1920.jpg
```
- Without `--at` it picks the sharpest of 24 frames; better: choose a frame with a strong expression (surprise, pointing, smile) by looking
  at a contact sheet, or use a dedicated photo. `--focus` overrides the detected face position.
- `*word*` = highlight bar in `--accent` (default brand yellow `FFC700`; client colour from `assets/brand/<client>/brand.json`).
- `--variants 3` → `_a/_b/_c` (flipped side, smaller title) for YouTube "Test & compare".

## What makes a thumbnail work
- **3–5 words max**, not the video title — the curiosity or result the title doesn't say. Big face with emotion, high contrast, one accent colour.
- Readable at 160 px wide (check by downscaling). Nothing important in the bottom-right corner (YouTube timestamp).
- Covers: all text inside the centre 1080x1440 (Instagram grid crops 3:4); face never under the title.
- Consistent series look per channel/client (same font, accent, logo placement).
- Look at the output at full size and at 160 px before delivering. For a custom composition (product shots, before/after split, arrows,
  cut-out subject) extend the script per project in `edit/thumbnails.py` rather than changing the shared one.

## Podcast episode thumbnail (proven layout)
Guest close-up on the right with a strong expression (hand on head, pointing, laugh), a dark panel fading in from the left
with a 3–5 word hook in Anton/Montserrat Black (one gold word or a gold label box), a soft warm glow behind the text.
Never reuse the previous episode's hook wording. Build it per project in `edit/thumbnail.py` when the generic script's
layout doesn't fit.
