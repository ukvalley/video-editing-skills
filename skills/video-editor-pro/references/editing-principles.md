# Editing principles — how world-class editors think

Read this before planning any cut. The tools execute; these are the decisions.

## 1. Structure first

Every edit has a shape. Decide it before choosing shots.

| Format | Shape | Target length | Shot length |
|---|---|---|---|
| Short / Reel / TikTok | Hook (0–1.5 s) → promise → payoff loop | 7–45 s | 0.5–2 s, faster toward the end |
| YouTube explainer | Hook → context → body (chapters) → payoff → CTA | 6–15 min | 3–8 s talking, 1–3 s B-roll |
| Trailer / sizzle | Tease → build → drop → escalation → button | 30–90 s | 0.3–1.5 s; cut rate rises with music |
| Ad | Problem → agitation → product → proof → CTA | 15/30/60 s exactly | 1–3 s |
| Vlog / travel | Scene-setting → moments → reflection | 5–12 min | Mixed; rhythm follows music |
| Tutorial | Result-first → steps → recap | As short as clarity allows | Cut on every action |
| Interview / doc | Thesis → evidence → turn → resolution | varies | Dictated by the speech |

Write the beat sheet in 5–8 lines before editing: what the viewer feels at 0 s, 3 s, 10 s, the middle, the end.

## 2. The hook (first 1.5 seconds on social; first 10 s on YouTube)

- Start in motion or mid-sentence. Never start on a logo, a fade-in from black, or "hey guys".
- Open on the most visually striking frame, or on the result ("here's the finished thing").
- Text on screen at 0 s that states the promise ("3 mistakes killing your edits").
- Audio starts instantly — no silence, no slow music intro. Trim the music so the first downbeat lands by 0.5 s.

## 3. Pacing and rhythm

- **Shot length follows energy.** Calm = long takes. Excitement = short. Pacing should *change* across the piece; constant pace is boring at any speed.
- **Cut rate accelerates toward a climax**, then one long shot to let it land.
- **Rule of three**: a pattern of three similar shots, then break it.
- **Breathe.** After a fast montage, hold 2–3 s on one shot with the music resolving.
- **Cut on the beat for montage, on the word for speech, on the action for continuity.** Use `scripts/beat_detect.py` for music, `scripts/transcribe.sh` for words.
- **Not every beat is a cut.** Cutting every beat is amateur. Cut on 1 and 3, or on the kick, or every bar — then break the pattern at the drop.

## 4. Types of cut and when to use them

- **Hard cut** — 90% of edits. Invisible when motivated.
- **Cut on action** — cut mid-movement (hand reaching, head turning, door opening); the motion carries the eye across the cut. The single biggest "pro" signal in continuity editing.
- **Match cut** — shape, motion or color matches across the cut (circle → wheel, hand down → hand down). Great for transitions between sections.
- **J-cut** — audio of the next shot starts before its picture. Makes dialogue/scene changes feel natural. Default for interviews.
- **L-cut** — audio of the current shot continues under the next picture. Use to show reaction or B-roll while someone talks.
- **Jump cut** — same framing, time removed. Standard in vlogs/talking-head; make it intentional with a slight punch-in (3–5% scale) so it reads as a choice.
- **Smash cut** — loud/quiet or calm/chaos contrast for comedy or shock.
- **Cutaway / B-roll insert** — covers a jump, illustrates a word. Insert B-roll on the exact word it illustrates, not a second later.
- **Whip pan / speed transition** — energetic scene change, see `transitions.md`.
- **Dissolve** — time passing, dream, softness. Rare in modern fast content; 8–20 frames when used.

## 5. B-roll discipline

- Every B-roll shot must earn its place: illustrate, contrast, or cover.
- Cut B-roll in on the noun ("...our **factory** in Pune" → factory shot lands on "factory").
- Keep A-roll audio under B-roll (L-cut); add subtle ambience from the B-roll underneath at −20 dB.
- Punch-in on B-roll (slow 100→105% Ken Burns) only when the shot is static and needs life.

## 6. Composition and framing fixes

- Reframe phone footage: crop to rule of thirds, stabilise (`deshake` or `vidstabdetect/vidstabtransform`), fix horizon with `rotate`.
- Vertical from horizontal: don't just centre-crop — track the subject (`crop` with expressions on `t`), or use a blurred-background pillarbox for talking heads.
- Alternate shot sizes between consecutive shots (wide → medium → close). Two similar-size shots in a row of the same subject feel like a jump.

## 7. Audio-led editing

- Lay the music first for montages. Mark beats. Cut picture to them.
- For speech-led edits, cut the audio first (remove ums, long pauses, false starts), then fix picture with jump cuts or B-roll.
- Decide the sound *of each cut*: silent, whoosh, impact, music hit, ambience swell. See `sound-design.md`.

## 8. Retention mechanics (YouTube/shorts)

- Change something on screen every 2–4 s: cut, zoom, text, graphic, B-roll.
- Visual payoff every 20–30 s.
- "Open loops": tease the later payoff in text or VO early.
- End with a loop-back for shorts (last frame flows into first) or a direct next-video CTA for long-form.

## 9. Common amateur tells (eliminate all of them)

- Fade from black at the start.
- Cross-dissolves between every shot.
- Music at constant volume under speech.
- Cuts landing on nothing (not beat, not word, not action).
- Titles with linear motion and no easing.
- Audio clicks at edits (no micro-fades).
- Inconsistent color between shots.
- Letterboxed vertical footage in a horizontal video (or vice versa).
- A 3-second lingering shot after the content is over.
- Default fonts (Arial, Impact-with-stroke) for titles.

## 10. Editor's review checklist (watch the full output once, actively)

1. Does the first 1.5 s / 10 s make you stay?
2. Is there a moment of silence or dead air? Kill it.
3. Does each cut land on something (beat / word / action)?
4. Are the loudest and quietest moments intentional?
5. Is every transition motivated?
6. Do shots match in color and exposure?
7. Is text readable on a phone at arm's length (≥ 4% of frame height for body text, ≥ 7% for titles)?
8. Does it end on the strongest possible frame?
