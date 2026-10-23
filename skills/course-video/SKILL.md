---
name: course-video
description: Turn slides, a PDF deck, course notes or a webinar outline into a long-form narrated training/course video (10–60 min, 16:9) — script per slide, ElevenLabs narration with word timings (Prem / Indian-English voices), each slide built up part-by-part on spoken cues with an easing camera, push transitions, progress bar and chapter markers, ducked music bed, light SFX, YouTube chapters and lesson splits. Use when the user says "make a course video", "training video from this PDF/deck", "narrate these slides", "lesson/module video", or gives a deck and wants a long educational video ("normal editing, not heavy motion graphics").
---

# Course / training video from slides

Read `video-studio` first. Proven on a 22-min marketing course built from a PDF deck (the brief was "normal editing, not heavy motion graphics",
Indian-English male voice). Rebuild it with the structure below: `edit/course.py`, `render.py`, `mix.py`.

## Pipeline
1. **Slides → images:** `pdftoppm -r 200 -png raw/deck.pdf work/slides/p` (or export PPTX/Keynote to PDF first). Look at every page.
   For build-ups, find the boxes of each part (title, bullet 1..n, chart, image) — by eye from the image or with PIL row/column
   projections of non-background pixels — and store them per slide.
2. **Script (`edit/course.py`):** per slide: `vo` paragraphs + `reveals` [{box:[x,y,w,h], cue:"spoken word"}] + optional `zoom` box.
   Write to teach, not to read the slide: hook the lesson (why it matters), one idea per paragraph, examples, recap at the end of each
   module, ~140–150 words/min. Hinglish if the audience wants it. **Show the script and get approval before any VO** (it costs credits).
3. **Budget check:** `eleven.py credits`; a 22-min course ≈ 18k characters — Starter has 40k/month, so a full re-voice the same month may not fit.
   Tell the user the cost. Free scratch VO with macOS `say` only to test timing.
4. **VO:** per paragraph `eleven.py tts "<text>" work/vo/<slide>_<n>.mp3 --voice 05QRrdNgiglhuYOaTQvw --speed 1.05 --words work/vo/<slide>_<n>.json`
   (Prem, approved). Cached by text — editing one paragraph re-pays only that one. Fix pronunciations by respelling in the text.
   Concatenate with 0.35 s between paragraphs and 0.8 s between slides; build the timeline JSON (slide start/end, cue word times).
5. **Render (`edit/render.py`):** each slide starts clean (title only), and each part fades/slides in on its cue word; slow easing camera
   push (1.00 → 1.04) and a zoom into the part being discussed for dense slides; push/slide transitions between slides (0.4 s),
   chapter label top-left, thin progress bar, slide number. Crisp: render slides from the 200-dpi PNGs at 1920x1080, no blur.
   Low-priority, in chunks per module so a killed render resumes.
6. **Mix (`edit/mix.py`):** voice chain (highpass 80, light compression), music bed −20 dB with sidechain ducking (`assets/music/*underscore*`),
   soft SFX on reveals (pop/swish −14 dB) and transitions (whoosh −12 dB) — lighter than reels. Master −14 LUFS, `--tp -2.0`.
7. **Preview → approve → full:** first module at `--scale 0.5`, get feedback, then everything. `qc.py --platform youtube`.
8. **Package:** YouTube chapters (one per slide group/module), description with lesson outline, per-module files if it's a course platform
   (`exports/vN_module_<n>_<slug>.mp4`), thumbnail (`thumbnail-designer`), optional SRT (`captions_ass.py --style clean` or from the VO words).

## Rules
- Visuals follow speech: nothing appears before it's mentioned; nothing important appears without being mentioned.
- Keep the deck's own design (it's the client's brand); add only the camera, reveals, chapter label and progress bar.
- Numbers and claims only from the deck/user. Spell brand names right on screen even if respelled for the voice.
- If the user goes to sleep and waives approvals, still keep previews and notes so they can review in the morning.
