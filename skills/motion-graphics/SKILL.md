---
name: motion-graphics
description: Design and render standalone motion graphics with code (Pillow frame engine or Remotion) in the ~/video-editing studio — logo animations/stings, kinetic typography reels, animated infographics and data (counters, bars, charts, maps), lower-third and title packs, intros/outros, transitions packs, social quote/announcement posts, and transparent overlay packs (ProRes 4444) to drop over footage. Use when the user asks for "motion graphics", "animate my logo", "logo reveal/intro", "kinetic text/typography video", "animated infographic/stats", "lower thirds pack", "title animation", "intro/outro", "animated post", or After-Effects-style animation without a presenter. For a full SaaS explainer/ad with VO use product-explainer-video instead.
---

# Motion graphics

Read `video-studio` first. Engine for this skill: `~/.claude/skills/motion-graphics/scripts/mg.py` (copy into the project's `edit/`).
Bigger existing engines to reuse when they fit: `toolkit/explainer.py` + `explainer_kit.py` (SaaS scenes, sprites, kinetic type),
`toolkit/gfx*.py` (reel/podcast graphics). Remotion (`npx create-video@latest`,
node 22 is installed) when the user asks for it or the piece is HTML/CSS-native (web UI, SVG, Lottie); then render in resumable chunks.

## Workflow
1. **Brief:** purpose + where it plays (16:9 YouTube intro, 9:16 reel, overlay on footage, TV), duration, brand (logo files, colours, fonts
   from `assets/brand/<client>/brand.json` or the brand kit), copy text, music/song, reference (link or "like X"). Ask once for the gaps.
2. **Style frames first:** design 3–4 key frames as stills (`render(..., still=t)`), show them as one contact sheet, get a yes on the look
   before animating. Cheap to change here, expensive later.
3. **Animatic:** timing on the music — `video-editor-pro/scripts/beat_detect.py` for the beat grid; list beats (t → what happens).
   Big moves on downbeats, small accents on off-beats, a breath (0.3–0.6 s of hold) after every reveal so it can be read.
4. **Build** scene functions `def s(c)` that draw from `c.t` only (pure function of time → any frame renders alone, previews/stills/chunks work).
5. **Preview** at `--scale 0.5` → look → full res → mux audio + SFX → master/QC.

## Craft rules (what makes it look After-Effects, not PowerPoint)
- **Easing on everything:** `oc` for entrances, `ob` overshoot for pops/slams, `io` for camera/position moves, `spring` for playful bounce.
  Never linear except constant drift/rotation.
- **Stagger** related elements 40–120 ms apart (`stagger()`); exit faster than you enter (≈ 60 %); overlap motion — the next thing starts
  before the last settles.
- **Hierarchy:** one hero element per moment; max 2 typefaces (Montserrat Black/ExtraBold, Anton for numbers, Caveat for handwritten notes,
  Noto Sans Devanagari for Hindi); 1 accent colour per frame (e.g. brand yellow `#FFC700`).
- **Readable time:** on-screen text stays ≥ (words × 0.3 s + 0.5 s). Text inside the title-safe 90 % (16:9) or y 260–1100 (9:16 with UI).
- **Layout from measured widths** (`text().width`), and shrink to fit — never fixed x steps (words overlap at other lengths/languages).
- **Depth & life:** subtle background drift/parallax, grain 2–4 %, light sweep across logos, motion-blur-like smear on fast moves
  (draw 3–5 ghost copies at decreasing alpha), shadows only if the brand allows (a flat paper look: no shadows/gradients).
- **Crisp:** render at full output resolution (no upscaled plates, no blurred backgrounds — the user rejects them); logos from real
  vector/PNG files (`toolkit/upscale_logo.py` for tiny ones). Look at full-res stills for clipped glyphs (Caveat "?" got cut once).
- **Sound sells motion:** whoosh on moves, pop on appears, impact/sub-drop on slams, riser into reveals, tick on counters, sheen
  on logo shine (`assets/sfx/`, clearly audible: −6 to −2 dB hits, −12 ticks).

## Recipes
- **Logo sting (3–6 s):** mark scales in with `ob` + rotation settle → wordmark wipes in (`wipe()`) → light sweep → tagline fades up →
  hold 1 s → (optional) exit. Split mark and wordmark files first. Variants: particles converge, line-draw (stroke reveal), glitch-in, 3D flip (shear+scale).
- **Kinetic typography:** one phrase per beat; key word in accent colour and 1.3–2× size; alternate motions (slide up, scale punch,
  mask wipe, letter stagger); camera push between phrases. Sync words to VO timings (`eleven.py tts --words`) or to beats.
- **Animated data:** counters (`counter()` with `oc`), bars grow from a baseline with stagger, line charts draw along the path, pie arcs
  sweep; always label units and source; real numbers only.
- **Lower-third pack:** bar wipes in → name → role (stagger 80 ms) → hold → reverse out; export each as ProRes 4444 alpha (`--alpha`)
  in 16:9 and 9:16 variants, plus a PNG still.
- **Intro/outro (YouTube):** 3–5 s intro max (retention); outro 10–20 s with space for end-screen elements (leave the YouTube end-screen
  zones empty: two video boxes + subscribe circle).
- **Overlay pack for footage:** transparent `.mov` (ProRes 4444) per element + a `pack.json` listing durations and anchor positions;
  to burn onto footage use ffmpeg `overlay` with `format=auto` and `tpad` padding (see video-editor-pro lessons).

## Delivery
H.264 CRF 14 master + platform encode via `video-editor-pro/references/delivery.md`; overlays as ProRes 4444; stills as PNG.
Audio at −14 LUFS when there's music. Name `vN_<what>.mp4`; log in notes.md.
