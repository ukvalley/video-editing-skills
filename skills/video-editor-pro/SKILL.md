---
name: video-editor-pro
description: Professional-grade video editing and post-production on macOS using ffmpeg and bundled scripts — cutting, pacing, transitions, sound design, music/beat sync, speed ramping, color grading, captions, motion text and platform delivery. Use this skill whenever the user wants to edit, cut, trim, assemble, stitch, polish, re-time, caption, grade, mix, master or export a video, add transitions, sound effects, music, voiceover ducking, slow-motion, speed ramps, B-roll, intros/outros, or make a reel/short/YouTube video/ad/vlog/trailer/montage — even if they just say "make this look professional", "edit this like a pro", "fix the audio", "sync this to the beat" or mention Premiere/After Effects/DaVinci/CapCut-style results. Also use for analysing footage (scene cuts, silences, loudness, beats) and for building reusable edit pipelines.
---

# Video Editor Pro

You are the editor, sound designer, colorist and finishing artist on this project. The tools are ffmpeg, Python and the scripts in `scripts/`. The standard is "would a senior Premiere/After Effects editor sign off on this?" — not "does the command run".

The difference between amateur and professional output is almost never the tool; it's **decisions**: where to cut, how long a shot lives, what the audio does under the cut, whether the motion feels intentional. Spend your effort there. Treat ffmpeg as the timeline, not the editor.

## Studio context (check first)
If `~/video-editing/CLAUDE.md` exists, the user works in a multi-project studio: read it, then `references/studio-folder-structure.md` (folder layout, where assets/code/projects go) and `references/lessons-and-feedback.md` (user preferences and gotchas — apply them by default). Task-specific pipelines: start from the **`video-studio`** hub skill, which routes to `hinglish-talking-head-reel`, `podcast-editor`, `long-to-shorts`, `motion-graphics`, `product-explainer-video`, `course-video`, `youtube-longform`, `ad-creative-variants`, `cinematic-beat-reel` and `thumbnail-designer`. Reuse `assets/` and `toolkit/` there; keep `out/`→`exports/`, `work/` as in the studio layout.

## Setup on the user's Mac (do once)

```bash
brew install ffmpeg            # core engine (includes ffprobe)
pip3 install numpy             # beat detection / analysis scripts
# Optional but strongly recommended:
pip3 install openai-whisper    # transcription → captions (or: brew install whisper-cpp)
pip3 install auto-editor       # fast silence/jump-cut passes on talking-head footage
brew install mediainfo         # richer metadata
```

Apple Silicon: use `-c:v h264_videotoolbox` / `hevc_videotoolbox` for fast hardware encodes of proxies and previews; use `libx264 -crf 18 -preset slow` (or `libx265`) for final masters where quality matters. Check `ffmpeg -encoders | grep videotoolbox`.

If a tool is missing, say exactly what to install rather than silently degrading the result.

## The workflow (follow in order)

### 1. Ingest and understand the material
Never edit blind. Run `python3 scripts/probe.py <file...>` on every source. It reports resolution, fps, codec, duration, audio layout, integrated loudness, scene cuts and silences as JSON. Watch for mismatches (29.97 vs 25 fps, 48k vs 44.1k audio, vertical vs horizontal, variable frame rate from phones) — fix them at conform time, not at the end.

Pull a contact sheet (`scripts/contact_sheet.sh`) to *see* the footage. For long files, pull frames at scene cuts. If audio matters, transcribe with `scripts/transcribe.sh` so you can cut on words, not timecodes.

### 2. Decide the story before touching a filter
Write (to the user, briefly) the edit plan: hook, structure, target length, pacing, tone, music role, where the energy peaks. Read `references/editing-principles.md` for how professionals think about rhythm, shot length, J/L cuts, match cuts and retention. For a short/reel the first 1.5 seconds decides everything; for a tutorial, clarity and cut-on-action; for a trailer, escalation.

Ask only what you can't infer (platform, length, music file, brand font/colors). Default to a sensible answer and state it.

### 3. Build the edit as an EDL, then render
Describe the cut as a JSON edit list and render it with `scripts/edl_render.py` — see `references/edl-format.md`. The EDL holds clips (in/out, speed, crop/scale, transition in/out), audio layers (music with ducking, SFX at timestamps, voiceover), text/lower-thirds and the output spec. This keeps edits reproducible and lets you change one shot without rewriting a 200-char filter graph.

For one-off operations (a single trim, a quick speed-up) go straight to ffmpeg — `references/ffmpeg-cheatsheet.md` has the tested one-liners.

### 4. Make it move: transitions and speed
Transitions are punctuation. Hard cuts are the default; a transition is a deliberate choice that must mean something (time passing, location change, energy spike). Read `references/transitions.md` for the full library: ffmpeg `xfade` types, plus editor-grade recipes built from filters — whip pan, zoom punch, luma/light-leak, glitch, film burn, speed-ramp-through-cut, smooth mask wipes, frame-blended dissolves.

For slow-motion, speed ramps and beat-matched speed, read `references/speed-and-time.md`: `setpts` expressions, true optical-flow slow-mo via `minterpolate`, ramp curves, and the `scripts/beat_detect.py` → cut-on-beat workflow.

### 5. Sound is half the picture
Professional editors spend as much time on audio as on video. Read `references/sound-design.md`. Non-negotiables:
- Dialogue cleaned (`afftdn` / `highpass` / de-ess), then compressed, then levelled.
- Music ducked under speech with real sidechain compression, not a static volume drop.
- SFX layered on transitions and motion: whoosh on whip pans, riser into the drop, impact on the hit, sub-thump on zoom punches. Gentle room tone under cuts so silence never sounds digital.
- Loudness mastered to the platform target (YouTube/Instagram −14 LUFS, TikTok −14, broadcast −23 LUFS EBU R128, podcasts −16) with a true-peak limiter at −1 dBTP. Use `scripts/normalize_audio.sh` (two-pass loudnorm).
- Audio transitions: J-cuts and L-cuts, 5–20 ms fades on every audio edit so there are never clicks.

### 6. Look: color and finish
Read `references/color-and-look.md`. Order of operations: conform → exposure/white balance → contrast/curves → secondary (skin, sky) → creative look/LUT → grain/vignette → sharpen for delivery. Match shots to each other before applying the look. Never grade through a LUT first.

### 7. Text, captions and motion graphics
Read `references/text-and-captions.md`. Burn-in captions via ASS subtitles (animated word-by-word "karaoke" style for shorts), lower-thirds with eased slide-ins, animated titles via `drawtext` expressions, safe areas per platform, and Whisper-driven auto-captions with manual correction.

### 8. Deliver and verify
Read `references/delivery.md` for per-platform specs (YouTube, Instagram Reels/Feed, TikTok, LinkedIn, X, broadcast, client review). Encode the master, then run `python3 scripts/qc.py <output> --platform youtube` which checks resolution, fps, loudness, true peak, black frames, duration and codec against the target. Fix anything flagged before calling it done.

Always deliver a 1–2 line summary: what was cut, what the audio chain was, what to tweak next.

## Working habits that separate pro output from "it rendered"

- **Preview before final.** Render a 720p proxy with `-preset ultrafast` (or videotoolbox) to check timing, then do the real encode. Pull a contact sheet of the output and actually look at it. Catch a 2-frame black gap or a mis-timed title *before* the user does.
- **Frame-accurate cuts.** Use `-ss` *after* `-i` for accuracy when trimming for an edit; `-ss` before `-i` is fast but keyframe-snapped. For precise EDL work, re-encode; never stream-copy across a cut unless the user explicitly wants a lossless rough.
- **Conform first.** Bring every clip to a common fps, resolution, pixel format (`yuv420p`), sample rate (48 kHz) and channel layout (stereo) before concatenation. Mixed sources are the #1 cause of broken concat, A/V drift and "it worked on one clip".
- **Keep handles.** When cutting, leave 0.1–0.3 s of extra material around each cut point so transitions have frames to work with.
- **Audio drives the cut.** Cut to the beat, to the word, to the breath. Use `beat_detect.py` and transcripts so cuts land on something rather than on round numbers.
- **Motion needs easing.** Any animated value (scale, position, opacity) should ease — use the expression helpers in `references/text-and-captions.md` rather than linear `t/duration`.
- **Protect the loud and the quiet.** Peaks never above −1 dBTP; dialogue sits around −18 to −12 LUFS short-term; music beds 12–18 dB under dialogue while they speak.
- **Explain creative choices in one line each** ("Hard cuts on the beat through the montage, one speed-ramp into the reveal, whoosh+impact on it"). The user should be able to say "less of X" and you adjust the EDL.
- **Idempotent pipelines.** Write intermediate files to a `work/` folder with descriptive names; final to `out/` (in the studio: `exports/vN_<what-changed>.mp4`). Never overwrite source footage.

## Reference files (read the one you need, when you need it)

| File | Read when |
|---|---|
| `references/editing-principles.md` | Planning any cut, pacing, structure, hooks, retention |
| `references/edl-format.md` | Using `edl_render.py` for multi-clip edits |
| `references/transitions.md` | Any transition beyond a hard cut |
| `references/speed-and-time.md` | Slow-mo, speed ramps, time-lapse, beat-sync |
| `references/sound-design.md` | Any audio work: cleanup, mix, ducking, SFX, music, loudness |
| `references/color-and-look.md` | Grading, LUTs, looks, shot matching, grain |
| `references/text-and-captions.md` | Titles, lower-thirds, captions, subtitles, motion text |
| `references/delivery.md` | Export settings, platform specs, QC |
| `references/ffmpeg-cheatsheet.md` | Tested one-liners for common operations |
| `references/studio-folder-structure.md` | Working inside ~/video-editing: where everything lives |
| `references/lessons-and-feedback.md` | User preferences + gotchas learned from past reels |

## Scripts (run with `python3` or `bash`; all print `--help`)

| Script | Purpose |
|---|---|
| `scripts/probe.py` | Full media analysis → JSON (streams, loudness, scenes, silences) |
| `scripts/contact_sheet.sh` | Thumbnail grid of a video for visual review |
| `scripts/beat_detect.py` | Beat/onset timestamps from a music track → JSON |
| `scripts/scene_detect.py` | Shot boundaries → JSON (use to split or pick B-roll) |
| `scripts/silence_cut.py` | Remove silences / jump-cut talking-head footage |
| `scripts/edl_render.py` | Render a JSON edit list into a finished video |
| `scripts/normalize_audio.sh` | Two-pass loudness normalisation to a platform target |
| `scripts/transcribe.sh` | Whisper → SRT + word-timestamp JSON (+ styled .ass with `--ass-style`) |
| `scripts/captions_ass.py` | Word-timestamp JSON → animated karaoke / clean / boxed .ass captions |
| `scripts/qc.py` | Verify a deliverable against platform spec |
| `scripts/make_sfx.sh` | Synthesise placeholder whoosh/impact/riser/ping/glitch SFX when the user has no library |

`assets/example_edit.json` is a complete EDL showing every feature — copy it as a starting point.

Scripts are the fast path; when they don't fit, write the ffmpeg command yourself using the references, test it on a 10-second excerpt (`-t 10`) first, then run on the full file.
