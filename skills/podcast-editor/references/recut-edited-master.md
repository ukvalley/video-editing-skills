# Recutting an already-edited podcast master (freelancer/agency cut)

Most client podcasts arrive as someone else's finished master: 1920x1080, a baked split-screen with a divider, single
close-ups, the editor's hook with stock clips, burned-in captions and name tags, a sting and a disclaimer. There are no
raw camera files or separate mics. Proven on four recuts (10–30 min, Hindi/Hinglish, 2-person shows). Each project keeps
its decisions in `edit/` (build_edl.py, cleanup.py, overlays, render.py, reels/) so a later episode starts from a copy.

## 1. Map the master before cutting
- `ffprobe` fps first. **29.97/59.94 masters must be conformed to 25 with `fps=25` as the FIRST filter of every piece and an
  exact `-frames:v n` per piece.** Without it each piece gained 1–3 frames and the picture ended 27 s behind the audio over
  14 min. `keep_render.py` now does this and refuses a render whose video and audio lengths differ. If you write your own
  renderer, check `base` video duration == audio duration before anything else.
- `scripts/classify_shots.py raw/ep.mp4 work/shot_runs.json --sheet work/shots.jpg` → runs of S (split), C0/C1 (singles,
  clustered: name them guest/host from the sheet) and X (graphics/black, never cut to these). It also finds the divider x.
- `scripts/detect_baked.py raw/ep.mp4 work/baked.json --sheet work/baked.jpg` → spans with burned-in captions (yellow
  text, or any colour sitting on a darkened bottom gradient). Name tags ("Host …", "Mr. … Sir") show up here too.
- Read the transcript (`transcript_view.py`) start to end. Watch for: the editor's hook (stock/AI clips, B&W, burned subtitles,
  usually the first 60–90 s): drop it and build your own cold open. **A host intro copied from a different episode** (wrong
  topic, baked title from the earlier show): keep only the neutral greeting. Mid-answer jumps the editor left in.
  A host's mid-episode wrap-up before a last question. Disclaimers: move them to the end.

## 2. Framing rules
- Close-ups come from the split's halves: per-show crop boxes, e.g. `cuL [x, y, w]`, `cuR [x, y, w]`, about 880 px wide at 16:9.
  Tune them on stills (headroom, no divider, no shelf props cutting in).
- Paint the divider charcoal (a 10–16 px `drawbox` over the divider x ± margin) whenever the full split is shown.
- **Never show a frame with the editor's baked text.** Reframe those pieces to a close-up from the split, or use a
  top-anchored ~1.36× punch-in that crops the caption band off, or cover the span with your own full-screen card.
  For a split frame under a caption, test the divider on the top 600 px only (the editor darkens the bottom under captions).
- Never widen to a layout whose baked name tags or captions you can't remove.
- Jump cuts from micro-cuts are hidden by a framing change (close-up ↔ two-shot ↔ punch-in), not by transitions.
- Re-run `detect_baked.py` on your final render. A v1 recut still showed white/green captions at 3 spots that only the
  gradient mode caught.

## 3. Content edit (when the episode is weak or long)
When the user says the content "isn't effective", keep only the clearest sentence of each point: KEEP word ranges in
`build_edl.py` (Scribe word indices), with cuts snapped to the quietest 20 ms within ±0.35 s plus 40/60 ms padding.
Typical results: 9:14 → 5:03, 29:33 → 13:58. Then remove fillers, repeats and stutters (`podcast_cuts.py` or a hand DROP list)
and cap pauses at about 0.3 s.

## 4. Package of a premium recut
- Cold open 25–35 s: 4–5 strongest lines (claim → pain → number → contrarian → payoff), flash cuts with whoosh/impact,
  a drone + underscore bed, a riser into the title card (boom), the show sting, then the host greeting.
  **Title cards must differ between episodes of the same show** (don't reuse last week's hook line).
- Chapter cards (6–9), lower thirds exactly as the user words them (if they say "don't add anything" under a name, add no title).
- Full-screen B-roll cards for lists, numbers, flows, myths vs reality and quotes, anchored to Scribe word times: start at
  the first spoken item and end about 5 s after the last. Over ~35 s of card hides faces too long. Keyword pops at most one per 45 s.
- Voice: free chain by default (HPF, de-mud, presence, air, de-ess, 2-stage compression). ElevenLabs isolation only when the
  user opts in (~600 credits/min). Master −14 LUFS; an `alimiter` at −3 dB after loudnorm gives about −2.7 dBTP after AAC.
- Grade per show (`edit/grade.txt`: highlight roll-off, warm skin, contrast, vignette), the same across episodes.
- Thumbnail: guest close-up on the right with emotion (hand on head, pointing), a dark panel on the left with a 3–5 word
  hook in Anton/Montserrat Black and a gold label. Different wording from earlier episodes.
- Shared show assets (sting, disclaimer, logo) cut once from a master, then reused from `assets/brand/<show>/`.

## 5. Shorts from the same episode
`edit/reels/spans.json` (Scribe word-index ranges; the first span is the hook), plus `removals.json` fillers, the isolated
or processed voice, `shot_runs.json` to pick framings, and `baked.json` to avoid caption zones. 7 reels of 25–50 s,
1080x1920, Roman Hinglish captions, −13/−14 LUFS. When the editor's infographics dominate a candidate (e.g. a framework
explained over stills), pick another moment.

## 6. Publishing (YouTube Studio via the browser)
- The browser tool can't attach files over 10 MB: the user drags each file into the upload dialog (one per drag) or
  uploads drafts, and Claude fills in the title, description with chapters, tags, language, category, thumbnail, audience
  and AI disclosure. Never press Escape in the upload dialog (it closes it).
- Channels with memberships list "Members only" ABOVE "Public": a text search for "Public" picked Members for 5 Shorts.
  Click Public by position and confirm with a screenshot before Publish.
- A Short's "Related video" picker lists only PUBLIC videos: make the full episode public first, then link every Short to it.
- If the user wants to release one Short per day, upload them all as Private with SEO done, and they publish daily.
- Never click Publish/Post without the user's explicit OK in chat.
