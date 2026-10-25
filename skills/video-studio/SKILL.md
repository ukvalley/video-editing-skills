---
name: video-studio
description: Hub for every video job in the ~/video-editing studio — picks the right specialist skill (talking-head reel, podcast, long-form → shorts, motion graphics, product explainer/ad, course video, YouTube long-form, ad creative variants, cinematic beat reel, thumbnails) and holds the shared rules and scripts (ElevenLabs TTS/Scribe/voice isolation, keep-segment renderer, face-follow 9:16 reframing, transcript tools). Use at the start of ANY video request, when unsure which video skill applies, or when the user asks "what video skills do you have / what can you edit".
---

# Video studio — router + shared toolbox

Studio: `~/video-editing` (read its `CLAUDE.md`). General craft (cutting, transitions, sound, grade, captions, delivery, QC
scripts) lives in **`video-editor-pro`** — every specialist below builds on it.

## 1. Pick the skill

| The user has / wants | Skill |
|---|---|
| Talking-head speech footage → 9:16 reel (your channel, clients), product-ad reel with presenter | `hinglish-talking-head-reel` |
| A podcast / interview / panel episode (1–3 cams or a split-screen) → clean 16:9 YouTube episode | `podcast-editor` |
| A long video (podcast, webinar, YouTube, live) → several 9:16 viral clips | `long-to-shorts` |
| Motion graphics with no footage: logo sting, kinetic typography, intro/outro, lower-third pack, animated stats/infographic, title sequence, overlay pack for footage | `motion-graphics` |
| SaaS / product explainer (2–3 min) or 30 s ad with VO, no presenter | `product-explainer-video` |
| Webpage / frontend project → cinematic product promo (Remotion, screenshots, 2.5D camera) | `video-shotcraft` |
| Slides / PDF / course notes → narrated long-form lesson | `course-video` |
| 16:9 YouTube video: talking head, tutorial, screen recording, vlog | `youtube-longform` |
| Footage → many paid-ad creatives (hooks × bodies × CTAs, 9:16 / 4:5 / 1:1) for Meta/YouTube | `ad-creative-variants` |
| Song + clips/photos, no speech (car delivery, wedding, festival, family, travel, aftermovie) | `cinematic-beat-reel` (studio pipeline) or `cinematic-reel` |
| Thumbnail, Reels cover, YouTube A/B thumbnails | `thumbnail-designer` |
| Anything else (trim, fix audio, re-time, convert, caption a file) | `video-editor-pro` directly |

A job can chain skills: podcast → `podcast-editor` → `long-to-shorts` → `thumbnail-designer`. Say which skills you'll use in one line, then go.

## 2. Studio rules (all skills)

- **Projects:** `./new-project.sh <slug>` → `projects/YYYY-MM-DD_<slug>/{raw,edit,work,exports,notes.md}`. `raw/` is never modified;
  `edit/` = small reproducible decision files + scripts; `work/` = deletable intermediates; exports `vN_<what-changed>.mp4`;
  append every version to `notes.md`. If `projects/_template` is missing, create the folders by hand.
- **Shared assets** in `assets/` (sfx, music, fonts, brand/<client>/, luts/looks.json, broll, overlays); reusable code in `toolkit/`.
  Never copy shared assets into a project. A new client gets `assets/brand/<client>/`.
- `export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH` before every ffmpeg call (drawtext/libass). ffmpeg 9: `-fps_mode`, not `-vsync`.
  pip is blocked (PEP 668) — brew only; numpy + Pillow are installed, OpenCV/scipy/requests are not (the scripts here avoid them).
- **Heavy renders:** `taskpolicy -b nice -n 19 <cmd>` with `run_in_background`, one job at a time — the laptop hangs otherwise.
- **Fast mode:** only when the user says the laptop is free (e.g. "not in use for 4 hours"): skip taskpolicy and render
  pieces in parallel for that session. Back to low priority by default next time.
- **A/V check:** every assembled base must have video duration == audio duration (keep_render.py checks and stops).
  Conform odd frame rates (29.97/59.94) with `fps=25` as the first filter and exact frame counts per piece.
- **Stage gates:** brief → script/cut plan → (paid VO / isolation) → low-res preview → user approval → full render → master → QC.
  Never spend ElevenLabs credits or do the full-res render before the user approves the stage before it, unless they waive the gates.
- **Look before you send:** stills/contact sheet of every deliverable at full res (clipped text, overlaps, safe zones, faces under titles).
- **Masters:** −14 LUFS (YouTube/Instagram; talking-head reels −11 for phone speakers), `--tp -1.5` to `-2.0` so AAC stays under −1 dBTP;
  `qc.py --platform …` must PASS. Thumbnails/covers ship with every export (`thumbnail-designer`).
- **User taste:** rich edits (graphics synced to words, SFX clearly audible, transitions only at section changes, premium grade),
  crisp full-res graphics (no blurry plates), real logos, Roman Hinglish captions, a fresh look per brand (don't reuse the lavender orb canvas).

## 3. Shared scripts (`~/.claude/skills/video-studio/scripts/`)

| Script | What it does |
|---|---|
| `eleven.py credits` | ElevenLabs balance (Starter = 40k credits/month — check before any paid job and tell the user the cost) |
| `eleven.py tts "text" out.mp3 --voice ID --speed 1.05 --words w.json` | VO line + word timings; cached, so unchanged lines are free |
| `eleven.py stt in.mp4 scribe.json --lang hin [--speakers 2]` | Scribe verbatim transcript (keeps fillers/stutters), diarized; ~18 credits/min |
| `eleven.py isolate in.mp4 iso.wav --yes` | Voice isolation (echo/room/noise), chunked + re-aligned sample-locked to the video; ~600 credits/min |
| `transcript_view.py words.json` | `[mm:ss–mm:ss] S0: sentence` lines — read this to pick clips, chapters, hooks, B-roll moments |
| `keep_render.py keeps.json out.mov --size WxH` | Render a cut list (in/out, per-segment crop/zoom/src, replacement audio) with click-free micro-fades |
| `face_track.py src.mp4 crops.json --aspect 9:16 --range a b --sheet s.jpg` | Apple-Vision face-follow reframing; locked "camera operator" framing, not jitter |
| `remap_words.py keeps.json words.json out.json` | Source-time words → output-time words (for captions/graphics after a cut) |

Voices (ElevenLabs): Ruhaan `siw1N9V8LmYeEWKyWBxv` (default, explainers), Prem `05QRrdNgiglhuYOaTQvw` (courses, speed 1.05),
Saavi `H8bdWZHK2OgZwTN7ponr` (Hinglish female, ads), Viraj `bajNon13EdhNMndG3z05`. Output format `mp3_44100_128` (Starter plan).
Free local transcription: `whisper-cli -m ~/.cache/whisper-cpp/ggml-medium.bin -l hi` (hides disfluencies; drifts — transcribe per speech region).

## 4. Publishing (YouTube / LinkedIn through the user's browser)
- Only with the user's explicit request, and **never click Publish / Post without their OK in chat** — fill everything, then stop.
- The browser tool can't attach files over 10 MB: open the upload dialog, reveal the export in Finder, and the user drags it in
  (one file per drag). Never press Escape in YouTube's upload dialog (it closes it).
- YouTube details: title (keyword first, #shorts for Shorts), description (links, chapters for long-form), tags, language,
  category, "not made for kids", AI disclosure (real footage of the person saying their own words + background music = No),
  thumbnail (long-form), then Visibility. Channels with memberships list "Members only" ABOVE "Public": click Public by
  position and confirm with a screenshot.
- Shorts: "Related video" only lists PUBLIC videos, so publish the full episode first, then link each Short to it.
  Daily release = upload all as Private with SEO done.
- Posting kit per video in `edit/posting_kit.md` (Instagram caption + hashtags + alt text + comment-to-DM keyword,
  YouTube title/description/tags, LinkedIn text). Links in Shorts descriptions aren't clickable: pin a comment.
