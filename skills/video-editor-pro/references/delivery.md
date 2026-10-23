# Delivery specs and export

## 1. Platform table (2026 defaults)

| Platform | Resolution | Aspect | fps | Video | Audio | Loudness | Max |
|---|---|---|---|---|---|---|---|
| YouTube 1080p | 1920×1080 | 16:9 | source (24/25/30/60) | H.264 High, CRF 18 or 12–16 Mb/s; 4K: H.264 40 Mb/s or HEVC | AAC 48 kHz 320k (stereo) | −14 LUFS / −1 dBTP | 12 h |
| YouTube Shorts | 1080×1920 | 9:16 | 30/60 | H.264 CRF 18 | AAC 192k+ | −14 | 60 s (up to 3 min allowed) |
| Instagram Reels | 1080×1920 | 9:16 | 30 | H.264 CRF 19, ≤ 10 Mb/s | AAC 128–192k | −14 | 90 s (3 min allowed) |
| Instagram Feed | 1080×1350 (4:5) or 1080×1080 | 4:5 / 1:1 | 30 | H.264 | AAC | −14 | 60 s |
| TikTok | 1080×1920 | 9:16 | 30/60 | H.264 ≤ 10 Mb/s | AAC | −14 | 10 min |
| LinkedIn | 1920×1080 or 1080×1350 | 16:9 / 4:5 | 30 | H.264 ≤ 10 Mb/s | AAC | −14 | 10 min |
| X / Twitter | 1920×1080 | 16:9 | 30/60 | H.264 ≤ 25 Mb/s | AAC | −14 | 2:20 |
| Client review | source | source | source | H.264 CRF 20, `-movflags +faststart` | AAC 192k | −16 | — |
| Master / archive | source | source | source | ProRes 422 HQ (`prores_ks -profile:v 3`) or DNxHR | PCM 24-bit | −23 or untouched | — |
| Broadcast | 1920×1080 | 16:9 | 25 (EU) / 29.97 (US) | ProRes/XDCAM 50 per spec | PCM | −23 EBU / −24 ATSC | per spec |

Social platforms re-encode everything; deliver a *clean, slightly high-bitrate* H.264 so their encoder has good input. Keep `yuv420p`, BT.709, square pixels, constant frame rate.

## 2. Export commands

```bash
# Social / YouTube master (quality-first)
ffmpeg -i edit.mov -c:v libx264 -preset slow -crf 18 -profile:v high -level 4.2 \
  -pix_fmt yuv420p -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -g 60 -keyint_min 60 -sc_threshold 0 -bf 2 \
  -c:a aac -b:a 320k -ar 48000 -ac 2 -movflags +faststart out.mp4

# 4K
... -crf 17 -maxrate 60M -bufsize 120M ...

# Fast preview on Apple Silicon
ffmpeg -i edit.mov -c:v h264_videotoolbox -b:v 8M -c:a aac -b:a 160k -movflags +faststart preview.mp4

# ProRes master
ffmpeg -i edit.mov -c:v prores_ks -profile:v 3 -vendor apl0 -pix_fmt yuv422p10le -c:a pcm_s24le master.mov

# Vertical from a horizontal edit (centre crop)
-vf "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos"

# GIF (for previews/docs)
ffmpeg -i in.mp4 -vf "fps=15,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer" out.gif
```
`-g` = 2× fps keeps seeking responsive. `-movflags +faststart` is mandatory for web playback.

## 3. Thumbnails and stills

`ffmpeg -ss 00:00:12.5 -i out.mp4 -frames:v 1 -q:v 2 thumb.jpg` — pick a frame with a face/expression and strong colour; for YouTube render 1280×720 with the title text in ≥ 100 px bold.

## 4. QC before handoff

Run `python3 scripts/qc.py out.mp4 --platform youtube`. It checks resolution, aspect, fps, codec, pixel format, duration limits, integrated loudness, true peak, black frames (`blackdetect`), silence at head/tail, and faststart. Fix every flagged item.

Manual pass on the actual output:
1. Scrub the first and last 2 s — no black, no silence, no stray frame from the previous clip.
2. Watch on a phone-sized window — text legible?
3. Audio on headphones at the start, a transition, the loudest part, the end.
4. File size sane (1080p social ≈ 5–12 MB per minute at CRF 18–20).

## 5. Deliverable naming

`<project>_<cut>_<version>_<platform>.mp4` → `launch_teaser_v03_reels.mp4`. Keep `work/` intermediates; deliver only `out/`.

## 6. Handoff note (one paragraph the user can paste to a client)

What was delivered (formats, lengths), what was changed since the last version, what's not done / needs assets, and the loudness/spec it was mastered to.
