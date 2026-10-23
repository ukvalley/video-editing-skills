---
name: product-explainer-video
description: Make motion-graphics product videos for any company in the ~/video-editing studio, with no presenter or footage. Covers a 2–3 min 16:9 SaaS/product explainer and a 30 s ad (16:9 YouTube, 16:9 TV ProRes 25p, 9:16 Shorts/Reels), voiced with ElevenLabs and its word timestamps, built on toolkit/explainer.py, with multi-language/region cuts. Use when the user says "explainer video for <company>", "product video", "motion graphics video", "SaaS explainer", "30 second ad", "YouTube/TV ad", "make the same kind of video as our last explainer", or drops a company's logo/deck/screenshots in inbox/ and asks for a product video or ad.
---

# Product explainer + ad videos (motion graphics, no presenter)

This is a proven workflow for SaaS explainers and ads. One brief yields an approved script, ElevenLabs VO, word-synced
motion graphics, a 960px preview, and after approval the full render, mastering and QC. It works for any company:
brand colours, logos, screenshots and domains come from config, not code.

Reference projects: once you've made one, keep it as working code to copy from (proven so far: a 2:27 explainer with 15 bespoke
scenes in EN / Hinglish / a Canada cut, and a 30 s ad in 16:9, 9:16 and TV 25p).

Engine: `toolkit/explainer.py` (canvas, sprites, kinetic type, `X.brand()` colours) + `toolkit/explainer_fx.py`
(momentum layer) + `toolkit/explainer_kit.py` (project loading, built-in scene types, captions, frame assembly).
API cheat sheet: `references/engine.md`. Always `export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH`.

## Start a new company's video from the inbox (the short version)

The user only needs to say something like: *"New product video for Acme, files are in the inbox: explainer + 30 s ad,
English and Hinglish."* Then:

1. **Intake.** Look at everything in `inbox/` (deck/manual PDFs, logo, screenshots, reference video link). Ask for
   whatever is still missing from the intake checklist below, in a single message.
2. **Create the project(s):**
   `bash ~/.claude/skills/product-explainer-video/scripts/init_project.sh <company> explainer` (and/or `ad30`).
   This moves inbox/ into `raw/`, copies the templates into `edit/`, creates `assets/brand/<company>/brand.json`
   (reused by the company's later videos), and writes the brief skeleton into `notes.md`. Fill in the brief.
3. **Brand folder.** Put the logos and screenshots in `assets/brand/<company>/` (recipes below) and fill `brand.json`.
4. **Script → approval.** Write the script in `edit/vo_lines.json` and show it to the user as plain text grouped by
   scene. Wait for approval before you spend ElevenLabs credits.
5. **VO → scenes → preview.** `make_vo.py eleven` → choose scene types and `show` data, add custom scenes → check
   `--stills` → `render.py --scale 0.5` → master → `exports/v1_preview_….mp4`. Wait for feedback.
6. **Final.** After approval: `render.py --scale 1` → `deliver.sh` (YouTube / Reels / TV) → QC → log in notes.md.

## Intake checklist

Ask only for what the files don't already answer:
- **Logo** (PNG/SVG, ideally mark and wordmark separately; otherwise crop them from the deck), brand colours (or take the gradient pair from the logo).
- **Deck / manual / website.** Product story, feature names and real UI screenshots (web + mobile). Real screens beat mock-ups.
- **Reference video.** Style to match (e.g. a SaaS explainer with a light canvas, gradient orbs, floating UI cards, kinetic type).
- **Audience** (who buys, which industry, which country) and **the problem** in their words.
- **Features** to show, in priority order (an explainer covers 6–8, an ad 4–6).
- **Proof.** Numbers (3x calls, 92 %…), customer count, industries, logos. Use only real numbers from the client.
- **CTA + domain** ("Book a Free Demo" + www…), per region if they differ.
- **Regions / languages** (e.g. India EN + Hinglish, Canada EN with a .ca domain).
- **Voice.** Default ElevenLabs "Ruhaan" (`siw1N9V8LmYeEWKyWBxv`, `eleven_multilingual_v2`); offer an audition if they want a different one.
- **Deliverables.** Explainer and/or 30 s ad; 16:9 YouTube, TV (which channel spec?), 9:16 Shorts/Reels.

## Brand folder recipes (`assets/brand/<company>/`)

- `brand.json`: `name`, `tagline`, `colors` {`a`,`b` = gradient pair, `ink` text, `mute` secondary text, `accent3`,
  optional `bg_top`/`bg_bottom`}, `logos` {`mark`,`word`,`full`} (file names in this folder), `regions` {`en`: {`web`},
  `ca`: {`web`, `app_url`, `strip_bar`}}. `X.brand()` re-colours the gradients, canvas tint, orbs, shadows, grid,
  particles and rings from `a`/`b`/`accent3`. If a logo file is missing, the kit draws a gradient disc and a text wordmark.
- PDF pages → PNG: `pdftoppm -r 200 -png raw/deck.pdf work/deck/p`; embedded images: `pdfimages -png raw/deck.pdf work/deck/img`.
  Crop the screens with PIL and save them in the brand folder (`web_*.png` ~1600 px wide, `phone_*.png` raw phone screens).
- Small logos: `python3 toolkit/upscale_logo.py src.png out.png --scale 6` keeps the edges crisp. Split mark and wordmark so
  the lockup can animate (the mark pops or slams, then the wordmark wipes in).
- Browser frames show `X.APP_URL` (default `app.<domain>`). If the screenshots captured their own address bar for
  another region, set `"strip_bar": true` for that region.

## Pipeline (commands run from the project folder)

```
export PATH=/opt/homebrew/opt/ffmpeg-full/bin:$PATH
python3 edit/make_vo.py say                  # free scratch VO + estimated word times (only to test layout early)
python3 edit/make_vo.py eleven [lang]        # ElevenLabs with exact word timestamps -> work/vo[_lang]/{vo.wav,timeline.json}
python3 edit/render.py --stills 3,9.5,21 [--lang hi] [--layout 916]   # PNG checks -> work/stills/ ; LOOK at them
python3 edit/render.py --scale 0.5 [--lang hi] [--layout 916]          # 960px preview -> work/mix_960*.mov
python3 edit/render.py --scale 1 [--fps 25]                            # full 1080p (25p = TV)
bash ~/.claude/skills/product-explainer-video/scripts/deliver.sh . work/mix_1920.mov v3_final-en_1080p youtube   # | reels | tv
```

- **make_vo.py** synthesises each line on its own (cached by text, voice and settings in `work/vo/<backend>/`, so edits only pay
  for changed lines), trims it, and lays out the scenes with `pre`/`post`/`gap` pads. The timeline is fully determined by
  `vo_lines.json`. Use output format `mp3_44100_128`: the user's plan is Starter, and 192k needs Creator. The API key is
  `ELEVENLABS_API_KEY` in `~/video-editing/.env`. Use `pronounce` (`{"Acme": "Ack me"}`) or a line's `say` to fix brand names.
- **Previews:** render at `--scale 0.5`, master with `deliver.sh … youtube` (it writes to exports/, so name it `vN_preview_…`),
  then send the file. Always show a preview and get approval before a full-resolution render, which takes ~10× longer.
- **Check frames yourself** before sending anything: render `--stills` at each scene's busiest moment (times from
  `timeline.json`), make a contact sheet with PIL, and look for overlaps, clipped text, empty frames and safe-zone violations.
- After every version, append to the project's `notes.md` edit log what changed, the export names, loudness and the QC result.

## Writing the script

**Explainer (2–3 min, ~330–380 words at speed 1.0):** hook (busy but not productive) → problem (4–6 pains in the customer's
words) → pivot ("it's not your team, it's the system") → reveal (logo + one-line positioning + 3 pillars) → 5–8 feature
scenes, each one claim + one real screen → how it works (3–5 steps) → impact numbers → (before/after, industries, customer
count) → CTA. Short spoken sentences, one idea per line. Every line should carry a word the visuals can anchor to.

**30 s ad (~70–80 words, ElevenLabs speed 1.10–1.12, `"total": 30.0`):**
- **0–2.5 s PROBLEM:** a title slam in caps ("MISSED FOLLOW-UPS") plus a red sub-pill ("= LOST DEALS").
- **2.5–6.5 s AGITATION:** 3 pain cards, one per short VO line. They slam in with a shake, a ✕ badge and a red alarm pulse.
- **~7 s SOLUTION on the music drop:** white flash and logo slam. `T_DROP` snaps the reveal start to the beat grid, and
  `MUSIC_OFF = music_drop − T_DROP` starts the track so its drop lands there. Add a positioning line.
- **From ~8.5 s:** a persistent "Book a free demo → domain" bar (`titles.early_cta`) and a corner logo.
- **~9.5–24 s FEATURE BURST:** 5–7 one-line features, ~1.8–3 s each, each with a title, a real screen and 1–3 pills.
- **Last ~5 s CTA:** logo, a glowing button with a cursor tap, and the domain. Exactly 30.00 s: `make_vo.py` pads the end
  card and fails if the VO runs over, in which case trim words or raise the speed.

## Scenes

Each scene in `vo_lines.json` has `id`, `type`, `show`, optional `chapter` (explainer HUD label), `pre`/`post`, and `lines`.
Built-in types (`toolkit/explainer_kit.py`; each has a 16:9 and a 9:16 layout, and explainer or ad pacing from `config.kind`):

| type | show |
|---|---|
| `hook` | `icon`, and either `title` + `sub` (ad slam) or `hi` (highlighted word indices of line 0), optional `pill` |
| `pains` | `label`, `items` [[icon, text, anchor?]] → cards with ✕ (ads: one VO line per card, shakes + red pulse) |
| `statement` | `hi` per line → stacked kinetic headlines, last one big |
| `reveal` | `sub` (positioning), `icons` [[icon, label, anchor?]], `pill` → logo lockup (slam on the drop for ads) |
| `feature` | `title`, `shot`, `frame` browser\|phone\|image, `side`, `pills` [[icon, label, anchor?]], `sub`, `tap` |
| `steps` | `title`, `items` [[icon, label, sub, anchor?]] → numbered steps joined by a drawing line |
| `stats` | `title`, `items` [["3x", "more calls", anchor?]] → counting stat cards |
| `cta` | `button`, `tap` (anchor word), `head_hi` → logo, glowing button + cursor tap, region domain |

An **anchor** is a spoken word; that element appears when the word is said. A missing anchor falls back to line timing.
The built-ins get the template running fast. A good video also needs **2–4 bespoke scenes per product**: its signature
flow (e.g. for a calling app: SIM → app → CRM with flowing call packets), a lead pipeline, before/after, a device moment. Write those as
`def s_x(im, t, c)` in `scenes.py` and register them with `K.default_order({"scene_id": s_x})`. Copy patterns from your
earlier projects' `scenes.py` files. Every beat should key off `c.w("word")`, `c.L(i)` or `c.at(f, i)`, never fixed seconds.

**Momentum (the user's checklist):** ~70 % meaningful motion (reveals, taps, counters, flows tied to the words) and
~30 % decorative (grid, network lines, rings, shapes, 3-depth particles, depth blobs, light sweeps, camera push + drift,
slide/smear transitions with streaks, beat-synced ring pulses, grain, chapter label + progress bar). Something should
change every 1–2 s, and nothing may sit static. `explainer_fx` provides the decorative layer automatically through
`K.finish()` + `K.compose()`.

**SFX:** call `fx(name, t, db)` on every entrance (pop/swish/whoosh_fast), tap (ui_click), success, impact and number tick.
`K.finish` adds a whoosh at each scene change, and render.py collects the whole schedule. Keep SFX clearly audible (around −2 to −6 dB
for hits, −10 to −12 for ticks and buzz). The files are in `assets/sfx/`.

**Music:** explainers loop a generated underscore (`toolkit/make_music.py <secs> <bpm> <name>`) at −17 dB with sidechain
ducking. Ads use a hype track with a known drop (`toolkit/make_hype_track.py` writes the track plus a `.json` of drop times)
at −13 dB. Both are set in `edit/config.json`.

## 9:16 (Shorts / Reels) rules

`scenes_916.py` reuses the 16:9 timing, VO, music and SFX on a 1080x1920 canvas (`CANVAS`). Built-in scenes re-lay
themselves out. Custom scenes need a portrait twin.
- Key content stays in **y 260–1100** (Reels keeps ~14 % at the top and ~35 % at the bottom for UI, and Shorts covers the bottom too).
- **Burned-in word-by-word captions at y ~1190**, with the current word in the brand gradient (`K.captions`), for sound-off feeds.
- **Brand logo at the top** (y ~300) instead of the landscape lower bar. Text uses `K.fit()` so long Hinglish lines shrink to the width.
- QC with `--platform reels`.

## Languages and regions

- `edit/vo_lines_<lang>.json` is a full copy per language/region. `say` holds what the voice reads; `text` holds the on-screen words
  and anchors; `head` holds optional headline groups `[[text, [hi idx]], …]`; `titles` holds on-screen strings for custom scenes; `show` holds the per-language labels.
- **Hinglish (`hi`):** write `say` in Devanagari Hindi with the English terms in Latin script (ElevenLabs Ruhaan reads this
  naturally), and `text`/`head` in Roman Hinglish. Product labels and UI cards stay English. On-screen words are timed by
  matching them to spoken words, interpolating where they differ. Anchors can take alternatives: `c.w(("one", "ek"))`.
- **Region cut (e.g. `ca`):** English with region wording, `brand.json` `regions.ca` {`web`, `app_url`, `strip_bar`}. Only
  the changed lines cost new VO.
- `render.py --lang <code>` sets `TV_LANG` (the env var name is historical), reads
  `work/vo_<code>/`, and adds a `_<code>` suffix to the outputs. `make_vo.py eleven <code>` makes that language's VO.

## Deliverable specs (`scripts/deliver.sh`)

- **YouTube 16:9:** 1920x1080 30 fps, −14 LUFS with `--tp -2.0` (AAC overshoots: −1.5 measured −0.6 after encoding).
  Master `exports/<name>.mp4` (CRF 14 from the render) plus `<name>_upload.mp4` (H.264 CRF 18, maxrate 16M). QC `--platform youtube`.
- **Shorts / Reels 9:16:** 1080x1920, same audio. QC `--platform reels`.
- **TV:** render `--fps 25` (frames are time-based, so it's native 25p with no conversion). Deliver ProRes 422 HQ 10-bit with
  BT.709 tags, PCM 24-bit 48 kHz stereo, −24 LKFS / −2 dBTP, exactly 30.000 s, no black frames. Channels that want
  1080i50 XDCAM, −23 LUFS EBU R128, a slate/clock or a 2-pop need a re-wrap from this master: ask for the channel spec.
- Name exports `vN_<what>.mp4` (e.g. `v2_final_30s-ad_en_youtube_1080p30.mp4`). Delete superseded previews once a final
  is approved. Never overwrite an approved export.

## Style defaults

- **No people.** Use pure motion graphics and real product UI, and skip the reference's stock-person shots.
- **Continuous momentum**, ~70/30 meaningful/decorative. A frame that sits still reads as broken.
- **Preview before full render**, and the script approved before the paid VO.
- **Crisp graphics**: render sprites at full resolution, use no soft or blurry backgrounds, and use real screenshots at good resolution.
- **Clearly audible SFX** on every entrance, tap and hit.
- They like a premium voice (ElevenLabs Ruhaan, not macOS `say`, except as a scratch track).

## Gotchas

- Run ffmpeg from `ffmpeg-full` (drawtext/libass). ffmpeg 9 uses `-fps_mode`, not `-vsync`. pip is blocked: use brew for Python packages.
- Call `K.load(P)` before `from explainer import TVA, …`, so the names bind to the brand colours. Projects that don't call `brand()` keep the default violet→blue.
- The sprite cache is keyed per scale. `X.init()` clears it, and `X.brand()` clears it too.
- If ElevenLabs returns 401/402 for a library voice, the account is on the Free tier (library voices need Starter+).
- `say` VO only estimates word times. Never judge sync from it, and always re-check stills after the ElevenLabs VO.
- Keep the scenes' visual data in `vo_lines` (`show`/`titles`), so that a language variant is a JSON copy rather than a code change.
