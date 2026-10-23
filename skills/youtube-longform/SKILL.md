---
name: youtube-longform
description: Edit 16:9 long-form YouTube videos (5–30 min) from talking-head A-roll, screen recordings, tutorials, vlogs and B-roll — retake/filler removal, pacing for retention (hook in 30 s, pattern interrupts every 20–40 s), punch-in framing, screen-recording zoom/pan to the cursor, callouts and step titles, B-roll and graphics on spoken words, chapter cards, music beds, end screen, chapters/description/thumbnail. Use when the user says "edit my YouTube video", "tutorial/screen recording video", "vlog edit", "long video", "16:9 video for YouTube", or gives A-roll + screen capture.
---

# YouTube long-form edit

Read `video-studio` and `video-editor-pro` (editing-principles, transitions, sound-design, text-and-captions). Talking-head cleanup is
the same as `hinglish-talking-head-reel` (takes table, last clean take, pauses tightened) but paced for 16:9 long-form.

## Structure (agree it with the user before cutting)
- **0–30 s hook:** the promise / result first (show the end result, the number, the before/after), then "in this video…". No logo intro >3 s.
- **Body:** sections with a chapter card each; every 20–40 s something changes — framing (punch 1.0 ↔ 1.15), B-roll, screen, graphic,
  on-screen text, angle. Open loops ("the third one surprised me") carry viewers between sections.
- **End:** recap → one CTA → end screen 10–20 s (leave the end-screen element zones empty, music up).

## Pipeline
1. Ingest + probe + contact sheets; sync A-roll and screen recording (clap/audio cross-correlation) if recorded separately.
2. Transcript: whisper-cpp per speech region (free) or Scribe (`eleven.py stt`, verbatim, best for filler cuts). `transcript_view.py` → read,
   mark retakes, sections, B-roll moments, places for graphics.
3. Cut list: `podcast-editor/scripts/podcast_cuts.py` with `--max-gap 0.45 --keep-gap 0.18` (tighter than podcasts) then hand-fix;
   render with `keep_render.py` (`--size 1920x1080 --fps 30`), punch-in on every jump cut (`"zoom": 1.12`).
4. **Screen recordings:** never show a full desktop for long — zoom (1.5–2.5×) to the area being used, with `io`-eased pans between areas;
   follow the cursor/click (keyframes from the transcript cue + where the UI element is); highlight boxes/arrows on clicks; blur
   private data (emails, keys, phone numbers) with `boxblur` regions; speed up waiting/loading 4–8× with a "⏩" badge or cut it.
   Picture-in-picture face cam (circle/rounded, bottom-right, 22 % width) during screen segments.
5. Graphics: step titles ("STEP 2 — Connect WhatsApp"), keyword callouts, lists, stats (`motion-graphics` / `toolkit/gfx*.py`),
   lower third for the presenter once. Captions optional (`--style boxed --position 0.9`).
6. Sound: dialogue chain, music bed −20 dB ducked (change the track per section or at chapter cards), SFX on graphics and zooms
   (subtle — long-form fatigues fast), room tone under cuts.
7. Grade per `assets/luts/looks.json`; match A-roll angles; neutralise colour casts first.
8. Preview the first 2 min (hook!) + one section at 960px → approval → full → `normalize_audio.sh --target -14 --tp -2.0` →
   `qc.py --platform youtube`.
9. Package: chapters (`00:00` first, ≥ 3, ≥ 10 s), title options (3), description with timestamps and links, tags, thumbnail A/B set
   (`thumbnail-designer --variants 3`), and 3–5 Shorts candidates handed to `long-to-shorts`.
