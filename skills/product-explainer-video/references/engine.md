# Engine cheat sheet

Design space is 1920x1080 (or 1080x1920 for 9:16), and every coordinate is a sprite *centre* in design px. `X.init(scale, w, h)` sets the
render scale (0.5 = preview), and `X.S` is that scale. Time `t` is absolute seconds, and scenes read times from `c` (the scene object).

## toolkit/explainer.py (`X`)
- Colours: `X.TVA`, `X.TVB` (brand gradient pair), `X.INK`, `X.MUTE`, `X.RED`, `X.GRN`, `X.AMB`, `X.WHITE`, `X.ACC3`.
  `X.brand(a, b, ink, mute, accent3, bg, orbs)` re-colours everything. Defaults are violet→blue.
- Easing: `prog(t, t0, d)`, `out_cubic`, `in_cubic`, `inout`, `out_back`, `out_expo`, `lerp`, `clip`,
  `life(t, t0, t1, din, dout)` → (k_in 0..1, alpha 0..1).
- Sprites (cached): `text(s, size, weight, color, track, grad)`. The weights are black/xbold (Montserrat) and
  heavy/bold/demi/med/reg (Avenir Next). Also `para(lines, …)`, `emoji(ch, size)`, `rrect(w, h, r, fill, outline, grad)`,
  `card(w, h, r)` (white + shadow), `circle(d, fill, grad)`, `bubble(emoji, d)` (icon in a white circle),
  `pill(label, size, weight, fg, grad|fill, padx, pady, icon)`, `image(path, w|h)`, `browser(path, w, crop, url)` (window
  chrome + `X.APP_URL` pill), `phone_screen(path, h)` (drawn bezel), `shadowed(spr)`, `grad_img(w, h, a, b)`.
- Draw: `place(im, spr, cx, cy, sc, a, rot, blur)`, `reveal(im, spr, cx, cy, t, t0, t1, dy, blur)` (blur + rise in, float,
  light sweep), `pop(im, spr, cx, cy, t, t0, t1)` (overshoot + breathe), `headline(im, [(word, t)], cx, cy, size, t, t_out,
  hi=(idx…))` (kinetic words + gradient underline), `cursor_tap(im, x, y, t, t_tap, t_out)`, `sheen(spr, k)`.
- `X.background(t)` gives the canvas with drifting orbs. `X.APP_URL` and `X.STRIP_BAR` control the browser frames.

## toolkit/explainer_fx.py (`M`): the decorative ~30 %
- `M.setup(spans, bpm, chapters, beat0, drums_from, cam, drift, out, in, streak, hud)`. The kit calls it in `K.finish()`.
- `M.back(im, t)` draws the dot grid (pulses on beats), network lines, dashed rings, shapes, far/mid particles and bar ring pulses.
- `M.camera(layer, t, idx, s, e)` adds a 3.5 % push (6 % for ads) and alternating drift. `M.composite_scene(...)` slides scenes in and out with a smear.
- `M.front(im, t, dur)` draws near particles, depth blobs, streaks + a light blob at every cut, the chapter label + progress bar (HUD) and grain.

## toolkit/explainer_kit.py (`K`)
- `K.load(P)` reads config.json, brand.json, the region urls, vo_lines{_lang}.json and work/vo{_lang}/timeline.json, and sets
  `K.SC` {id: Sc}, `K.DUR`, `K.TT` (titles), `K.WEB`, `K.B` (brand folder), `K.FAST` (ad pacing), `K.T_DROP`, `K.MUSIC_OFF`.
- `Sc`: `c.s`, `c.e`, `c.out`, `c.show`, `c.lines`, `c.w("word", n=1, after=0, default=None)`, `c.L(i)`, `c.LE(i)`, `c.at(f, i)`,
  `c.frac(f)`, `c.hw(i)` → [(word, t)], `c.head(i, default)` (the language file's headline groups, else default).
- Helpers: `K.fx(name, t, db)`, `K.H(im, c, t, words, cy, size, hi)`, `K.title(im, c, t, s)`, `K.slam(...)`, `K.shake(t, t0)`,
  `K.fit(s, size, maxw)`, `K.two_lines(s)`, `K.label_card(icon, title, w, h, sub)`, `K.badge("✕"|"✓"|"1", col)`,
  `K.stat_card(label, value_sprite)`, `K.wipe(...)`, `K.logo_lockup(im, t, t0, cx, cy, t_out, scale)`, `K.logo_full(h)`,
  `K.shot("web_x.png")` → brand path, `K.frame_shot(name, kind, size)`, `K.counter_val("92%", k)`, `K.white(a)`, `K.red_vignette()`.
- Built-in scenes: `K.TYPES` (hook, pains, statement, reveal, feature, steps, stats, cta), `K.default_order(custom)`.
- Frame: `K.finish(order)` then `K.compose(t, order, shakes, overlays)`. Overlays: `K.corner_logo`, `K.early_cta`,
  `K.captions(im, t, K.caption_chunks())`. `K.ad_shakes()` returns the default shakes for ads.

## Positions that worked
- 16:9 explainer: the headline at y 170–250 when content sits below, or y 540 alone. Card rows at y 440/660, three columns at x 390/960/1530.
  The corner logo is at (200, 62) and the HUD on y 1042.
- 16:9 ad: titles at y 150, content at y 330–870, the early-CTA bar at y 952 (inside title-safe x 192–1728, y 108–972).
- 9:16: the logo at y 300, titles at y 400, content at y 500–1100, captions at y 1190, and nothing important below y 1250.
