# Studio folder structure (~/video-editing)

All of the user's videos live in ONE studio. Shared things are reused, never copied into a project.

```
~/video-editing/
├── CLAUDE.md               studio rules (read first)
├── README.md               human-facing overview
├── new-project.sh          ./new-project.sh <short-name> [date] → creates project, moves inbox/* into raw/
├── inbox/                  drop new footage here (moved into raw/ by new-project.sh)
├── assets/                 SHARED by every video
│   ├── brand/
│   │   ├── brand.json        colours, fonts, caption/title style, audio levels, zoom alternation, logo
│   │   ├── logo_*.png        your logo (rebuild crisp with toolkit/upscale_logo.py)
│   │   └── <client>/         client brand kit: logo_full/mark/word/white/stacked, phone_*/laptop mockups, scr_*/web_* screenshots
│   ├── fonts/                Montserrat-Black / ExtraBold (+ system Optima used for cinematic titles)
│   ├── luts/
│   │   ├── looks.json        named grades: warm_clean, premium_cinematic (+ "finish" recipe)
│   │   └── depth_mask_1080x1920.png   edge-blur mask used by the finish pass
│   ├── music/                underscore_100bpm.wav, tech_underscore_105bpm.wav (generated; README lists BPM)
│   ├── sfx/                  ~22 wavs: whoosh/_fast/_long, swish, swipe_up, pop, tick, ding, success, coins, impact,
│   │                         boom_hit, sub_drop, riser, reverse_swell, tension_drone, glitch, buzz, notification,
│   │                         ui_click, typing, shutter (README has levels). Same filename = drop-in upgrade.
│   ├── broll/  overlays/     reusable clips, logos, light leaks (READMEs inside)
├── toolkit/                reusable CODE
│   ├── gfx.py                base motion-graphics engine + easing helpers (g_deals, g_chips, g_funnel, g_stat, g_compare)
│   ├── gfx_pro.py            10 data-driven "pro" graphics (marketing/ecosystem style)
│   ├── gfx_product.py        product-ad graphics on a LIGHT canvas: pains, timepie, counter, boost, logo_reveal,
│   │                         features, workflow, noskip, learnmore, tagchip, endcard_light
│   ├── timeline.py           source-time → output-time mapping for anchoring graphics to spoken words
│   ├── make_sfx.py / make_sfx_pro.py / make_music.py   regenerate the SFX + music libraries
│   └── upscale_logo.py       crisp upscale of a tiny logo
└── projects/
    ├── _template/            copied by new-project.sh
    └── YYYY-MM-DD_<slug>/
        ├── notes.md          brief + take-selection table + edit log (APPEND every version) + re-render commands
        ├── raw/              originals — NEVER modified
        ├── edit/             small reproducible decisions + scripts:
        │                       talking-head: clips.json, phrases.json (+Roman captions), build_segments.py → segments.json/edit.json,
        │                                     compose.py, captions.ass, gfx_plan.json, anchors/timeline
        │                       beat reel:    plan.py (beat grid + SHOTS), build_shots.py, compose.py, ff.sh
        ├── work/             intermediates (deletable; can reach GBs) — delete when the project is final
        └── exports/          deliverables named vN_<what-changed>.mp4
```

Rules
- New client/brand → `assets/brand/<client>/`, never inside a project.
- Reusable graphic → add to `toolkit/`; project-specific wiring → project `edit/compose.py`.
- Every version: append to `notes.md` edit log, export as `vN_<what-changed>.mp4`, run `qc.py`.
- Re-render from `edit/` alone must be possible; keep commands in notes.md.
