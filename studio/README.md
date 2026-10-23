# Video Editing Studio

One folder for every video you edit. Shared things (sounds, fonts, brand, music, B-roll) live in `assets/` and are reused by every project.

```
video-editing/
├── inbox/                  ← drop new raw footage here
├── new-project.sh          ← makes a project and moves inbox/ footage into it
├── assets/                 ← shared by ALL videos
│   ├── sfx/                  whoosh, swish, pop, tick, ding, impact, riser, buzz
│   ├── music/                background tracks
│   ├── fonts/                Montserrat Black / ExtraBold
│   ├── brand/brand.json      colours, caption style, title style, audio levels
│   ├── luts/looks.json       colour grades (warm_clean, …)
│   ├── broll/                reusable stock / own B-roll clips
│   └── overlays/             logos, stickers, light leaks
├── toolkit/                ← reusable code
│   ├── gfx.py                motion-graphics engine (cards, funnel, stat counter, checklist…)
│   └── make_sfx.py           regenerates the SFX library
└── projects/
    ├── _template/            copied for every new project
    └── 2026-10-06_pricing-objection-reel/
        ├── notes.md          brief + edit log
        ├── raw/              original footage (never modified)
        ├── edit/             edit decisions, captions, scripts (small files)
        ├── work/             renders, graphics, transcripts (big, safe to delete)
        └── exports/          finished videos (v1, v2, v3…)
```

## Editing a new video
1. Copy the footage into `inbox/`.
2. In Terminal: `cd ~/video-editing && ./new-project.sh pricing-objection-reel`, or just ask Claude: *"new project from inbox: pricing objection reel"*.
3. Optional: fill in `notes.md` in the new project (hook, key message, CTA, music).
4. Ask Claude to edit it. Finished videos land in that project's `exports/`.

## Upgrading the shared assets
- **Better sounds:** put a real sample in `assets/sfx/` with the same name (e.g. `whoosh.wav`). Every future video uses it.
- **Music:** add tracks to `assets/music/`.
- **B-roll:** add clips to `assets/broll/`, named by subject (`crm-dashboard_01.mp4`).
- **Logo:** add a transparent PNG to `assets/overlays/`.

## Freeing disk space
`work/` folders hold large intermediates (the first project's is about 2.4 GB). When a project is final, delete its `work/` folder. Keep `edit/` so the video can be re-rendered later.
