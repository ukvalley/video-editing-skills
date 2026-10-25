---
name: podcast-editor
description: Edit podcasts, interviews and panel talks (Hindi/Hinglish/English, 1–3 cameras or a baked split-screen) into a premium 16:9 YouTube episode — ElevenLabs voice isolation for bad mics/echo, Scribe verbatim transcript, automatic filler/stutter/false-start/long-pause removal with a reviewable cut report, auto multicam (speaker close-ups, punch-ins hiding jump cuts), cold-open teaser, chapter cards, lower thirds, keyword pops, B-roll cards (toolkit/gfx_podcast.py), music bed, −14/−16 LUFS master, chapters + thumbnail. Use when the user gives a podcast/interview/conversation recording, says "edit this podcast", "Ranveer/BeerBiceps-style edit", "recut this episode", "remove fillers/umm", "fix the podcast audio".
---

# Podcast editor (16:9 episode)

Read `video-studio` (router + shared rules/scripts) and `video-editor-pro/references/sound-design.md`. Shared scripts:
`V=~/.claude/skills/video-studio/scripts`, this skill's: `P=~/.claude/skills/podcast-editor/scripts`.
Proven on a 16:9 two-person Hindi podcast recut (split-screen source, bad mics) that the client approved.

## Source is someone else's edited master?
Most client episodes arrive as a freelancer's finished cut (baked split-screen, their hook, burned-in captions, name tags,
often 29.97 fps). Read `references/recut-edited-master.md` FIRST: shot map (`scripts/classify_shots.py`), burned-in text
(`scripts/detect_baked.py`), 25 fps conform, framing rules, content edit, cold open, card timing, Shorts and publishing.

## Pipeline
1. **Ingest.** `new-project.sh <show>-ep<N>`. `probe.py` every file; contact sheet. Note: cameras (count, which is wide/CU),
   baked-in name tags or split-screen (never widen to a layout with a freelancer's baked graphics), audio (lav per person? one mix?),
   sync offsets between cams (clap or `eleven.py`'s `lag()` cross-correlation on the audio tracks).
2. **Brief (one message):** target length (full episode vs tightened), cold open yes/no, guest name/title spellings, show branding,
   chapter list if they have one, how aggressive the cleanup should be. Default: keep the conversation natural, remove only noise.
3. **Transcript.** `python3 $V/eleven.py stt raw/ep.mp4 work/scribe.json --lang hin --speakers 2` (Scribe keeps अअअ/umm/stutters,
   which the cut pass needs; ~18 credits/min — state the cost). `transcript_view.py work/scribe.json --out work/transcript.md` and READ it:
   find the cold-open line, chapter boundaries, the 3–6 strongest moments, off-topic tangents, retakes ("let me say that again").
4. **Voice (if mics are bad/echoey).** Ask first: `eleven.py isolate` costs ~600 credits/min (a 40-min episode ≈ 24k of the 40k/month).
   `python3 $V/eleven.py isolate raw/ep.mp4 work/iso.wav --yes` → sample-locked to the video. Then a light chain on top:
   `highpass=f=80, equalizer=f=250:g=-2, equalizer=f=3000:g=3, acompressor=threshold=-24dB:ratio=3:attack=10:release=150, alimiter=0.9`.
   Cheap fallback (no credits): `afftdn=nf=-25, highpass, deesser` + the same chain. Blend 85 % isolated + 15 % original if it sounds hollow.
5. **Framing map.** `edit/speaker_crops.json` in source pixels: `{"speaker_0": [x,y,w,h], "speaker_1": [...], "wide": [...]}`.
   From a split-screen, each half is a close-up (crop to 16:9 inside the half — `keep_render` fits the aspect). Check Scribe's speaker ids
   against the picture (who is speaker_0?) on 2–3 lines before trusting them. For true multicam, use per-segment `"src"`.
6. **Cut list.**
   ```
   python3 $P/podcast_cuts.py work/scribe.json edit/keeps.json --src raw/ep.mp4 --audio work/iso.wav \
       --crops edit/speaker_crops.json --min-shot 2.5 --punch 1.12 --report edit/cuts_report.md
   ```
   Removes fillers, stutters (keeps the last "ek"), immediate false starts (keeps the LAST take), host backchannels that sit in pauses,
   and tightens pauses > 0.7 s to 0.32 s. Never cuts a word that overlaps the other speaker. Read `cuts_report.md`; hand-edit
   `keeps.json` for content cuts (tangents, retakes, sensitive bits the guest asked to drop) and anything that cut meaning.
   Options: `--extra-fillers "matlab,basically"` only if the user asks; `--no-repeats` for a rhetorical-repetition speaker; `--range` to test 3 min first.
7. **Base render (test 2–3 min first, then all):**
   `taskpolicy -b nice -n 19 python3 $V/keep_render.py edit/keeps.json work/base.mov --size 1920x1080 --fps 25 [--preview]`.
   Listen to 10 random cuts: no clipped consonants, no breath chopped in half, no double-words left. Jump cuts inside a speaker
   must change framing (punch 1.0 ↔ 1.12) — that's what hides them.
8. **Graphics** (`toolkit/gfx_podcast.py`, charcoal + gold, 1920x1080 25 fps; plan list `{name, kind, dur, data}` → `work/gfx/<name>.mov`
   alpha): `lower_third` (guest name/title at their first close-up, again after ~10 min), `keyword` pops on punchlines (max one per ~45 s),
   `chapter` cards at topic changes, full-screen B-roll cards `steps/compare/flow/stat/quote/title/tasks` when the guest lists or explains,
   `sub_cta` once around the 1/3 mark. Anchor every graphic to a spoken word: `remap_words.py edit/keeps.json work/scribe.json work/words_out.json`
   gives output times. Overlay with `tpad` padding (see video-editor-pro lessons: late overlays get dropped otherwise).
9. **Cold open (optional, recommended):** 20–40 s of the 2–3 strongest lines (their keeps from the transcript) + whoosh/riser,
   then a 2–3 s show title card, then the episode. Same keep_render, then concat.
10. **Mix:** voice leads; music bed only under the cold open, title and chapter cards (−18 to −20 dB, ducked), not under the whole talk.
   Soft SFX on graphics (whoosh/pop −10 to −6 dB). Captions are optional on 16:9 (`captions_ass.py --style boxed --position 0.9`).
11. **Preview → approval → master.** 960px preview of the first 3–5 min + one middle chapter → `exports/v1_preview_….mp4`; after approval
   full render, `normalize_audio.sh --target -14 --tp -2.0` (or `podcast` −16 for audio-only platforms), `qc.py --platform youtube`.
   Also export `exports/vN_audio_podcast.mp3` (−16 LUFS, 192k) when the show is on Spotify/Apple.
12. **Package:** YouTube chapters from the chapter cards (`00:00 Intro` first, ≥ 3 chapters, ≥ 10 s each), title + description draft,
   thumbnail via `thumbnail-designer` (guest face + 3–5 word promise), and hand off to `long-to-shorts` for clips.

## Style (what "Ranveer-level" meant to this user)
Tight but natural pacing, clean warm voices, close-ups that follow the talker, punch-ins on emphasis, a cold open, bold gold-on-charcoal
graphics that explain lists and numbers, chapter cards, and no dead air. Not: constant zooms, SFX on every sentence, meme inserts.

## Gotchas
- A/V drift: conform 29.97 sources with `fps=25` first and exact frame counts per piece (keep_render does; it also
  refuses a render whose video and audio lengths differ). 27 s of drift over 14 min happened before this rule.
- Content-edit mode: when the user finds the episode weak, keep only the clearest sentence per point (9 → 5 min, 30 → 14 min).
- Full-screen cards: start at the first spoken item, end ~5 s after the last; > ~35 s of card hides faces too long.
- Read the host intro: editors reuse a previous episode's intro (wrong topic) — keep only the greeting.
- Render fast (parallel pieces, no taskpolicy) only when the user says the laptop is free; low priority otherwise.
- Isolation chunks come back shifted by a few ms; `eleven.py isolate` re-aligns them — never just concatenate the returned mp3s.
- Scribe hyphen stutters (`ता-ताकत`) are kept as the full word; captions still need hand-romanising for Hinglish.
- Overlapping speech (both talking) can't be micro-cut; leave it or cut the whole exchange.
- Long jobs: build and render the cut per chapter (`podcast_cuts.py --range a b` → one keeps file each) so a killed job only redoes one chapter; keep `work/keeps/` until the master is approved.
