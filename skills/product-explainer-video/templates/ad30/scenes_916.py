"""9:16 (1080x1920) cut of the 30 s ad for YouTube Shorts / Instagram Reels ads: same VO, music, timing and SFX as
scenes.py. The built-in scenes re-lay themselves out for portrait (they branch on X.H > X.W):
  - key content in y 260-1100 (Reels keeps ~14% top / ~35% bottom for UI; Shorts covers the bottom too),
  - burned-in word-by-word captions at y ~1190 (current word in the brand gradient) for sound-off feeds,
  - brand logo at the top (y 300) instead of the landscape lower bar.
Custom 16:9 scene functions need a portrait twin here: ORDER_916 = [(sid, s_mine_916 if sid == "x" else fn) ...].
Render: python3 edit/render.py --layout 916 [--lang hi]
"""
from scenes import K, X, SC, DUR, SFX, MUSIC_OFF, T_DROP, ORDER, SHAKES
from explainer import life, place

CANVAS = (1080, 1920)
CHUNKS = K.caption_chunks()
_END = SC[ORDER[-1][0]].s + 0.1


def brand_top(im, t):
    k, a = life(t, T_DROP + 2.2, _END, 0.4, 0.25)
    if a > 0: place(im, K.logo_full(46), K.CX(), 300, a=a)


def frame(t):
    return K.compose(t, ORDER, shakes=SHAKES, overlays=[brand_top, lambda im, t: K.captions(im, t, CHUNKS)])
