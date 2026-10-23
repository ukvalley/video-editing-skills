---
name: ad-creative-variants
description: Produce many performance-ad creatives from one shoot or edit for Meta (Facebook/Instagram) and YouTube ads — modular hooks × bodies × CTAs matrix, 9:16 / 4:5 / 1:1 / 16:9 versions with platform safe zones, UGC/talking-head and product-demo styles, burned captions for sound-off, offer/price supers, consistent naming for testing, and a creative test plan. Use when the user says "ad variants", "make 5/10 ad creatives", "hook variations", "test different hooks", "Meta ad creatives from this video", "resize this ad for all placements", or works on paid campaigns for clients.
---

# Ad creative variants

Read `video-studio` first. Single polished ads come from `hinglish-talking-head-reel` (presenter) or `product-explainer-video` (motion graphics);
this skill multiplies them for testing. Never invent claims, numbers, prices or guarantees — use only what the client approved
(e.g. a refund promise only with its conditions caption; no invented numbers).

## 1. Plan the matrix (show it before rendering)
`edit/ads/matrix.json`:
```json
{"hooks":  [{"id":"H1","src":"raw/a.mp4","in":12.1,"out":15.0,"title":"STOP WASTING AD SPEND"}, ...],
 "bodies": [{"id":"B1","segments":[[40.2,52.8],[60.0,71.4]]}, ...],
 "ctas":   [{"id":"C1","src":"raw/a.mp4","in":90.0,"out":94.5,"button":"Book a Strategy Call"}],
 "combos": [["H1","B1","C1"], ["H2","B1","C1"], ["H3","B1","C1"]],
 "formats": ["9x16", "4x5", "1x1"]}
```
- **Test one variable at a time:** 3–5 hooks on the same body/CTA first (hooks move results most); then bodies; then CTA/offer.
- Hook types to draw from: bold claim, number/result, pain question, pattern interrupt (visual surprise), testimonial line, "POV:"/"If you…",
  before→after, objection call-out. First frame must work as a still (no fade-in, text on frame 1).
- Length targets: 15 s, 30 s, (45–60 s for UGC story). Captions always (85 % watch muted).

## 2. Build
- Cut each combo as one keep list (`keep_render.py` segments, hook → body → CTA, `"src"` per segment) at 1080x1920 master; pauses tight (~0.1 s).
- Formats from the 9:16 master: **4:5** 1080x1350 and **1:1** 1080x1080 by re-cropping the source (`face_track.py --aspect 4:5`), not by
  squashing; **16:9** for YouTube in-stream from wide source. Re-place supers/captions per format.
- **Safe zones:** 9:16 Reels/Stories — keep text and logo in y 250–1340 and x 60–1020 (top 14 % and bottom ~35 % are covered by UI);
  4:5 feed — 50 px margins; captions above the CTA button area.
- Supers: hook title on frame 1 (3–6 words), offer/price super when spoken, brand logo small top, CTA end card 2–3 s with the exact
  button wording ("Tap Learn More", "Book a Strategy Call") + domain. Music bed −16 dB, SFX on supers.
- Master each: −14 LUFS `--tp -1.5`, H.264 high, AAC 320k, faststart; `qc.py --platform reels|feed|youtube`.

## 3. Name and hand off
Name: `<client>_<campaign>_<H#>-<B#>-<C#>_<len>s_<format>_v<N>.mp4` (e.g. `acme_leads_H2-B1-C1_30s_9x16_v1.mp4`) in `exports/ads/`.
Give the user a table (file, hook text, length, format) and a test plan: which ad set gets which combos, run ≥ 3–5 days or ~50 conversions
per variant before calling a winner, judge hooks on thumb-stop (3-s view rate) and hold rate, bodies on CTR/CPA. Covers/thumbnails for
YouTube via `thumbnail-designer`.
