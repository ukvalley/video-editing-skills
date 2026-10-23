"""<Company> 30 s ad (16:9 1920x1080 for YouTube / TV). Problem -> Agitation -> Solution in the first ~7 s (hook title
slam, 3 pain cards with shakes + red alarm pulse, logo slam on the music drop with a white flash), a fast feature burst,
then the CTA end card. A persistent "book a demo -> url" bar is on screen from ~8 s. Exactly 30.00 s (vo_lines "total").

Scenes come from edit/vo_lines{_lang}.json (type + show, see toolkit/explainer_kit.py); write custom scene functions
for product-specific beats. Music: config.music started at MUSIC_OFF so its drop (config.music_drop) lands on the logo
slam (K.T_DROP, on the beat grid). Keep key content inside the 10% title-safe area (x 192-1728, y 108-972).
"""
import os, sys
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("STUDIO_ROOT") or os.path.dirname(os.path.dirname(P))
sys.path.insert(0, f"{ROOT}/toolkit")
import explainer_kit as K
K.load(P)
import explainer as X
from explainer import (place, reveal, pop, text, pill, bubble, card, browser, phone_screen, image, cursor_tap,
                       life, prog, out_cubic, out_back, inout, lerp, clip, px, TVA, TVB, INK, MUTE, RED, GRN, WHITE)
from explainer_kit import fx, title, slam, badge, label_card, shot

SFX = K.SFX; SC = K.SC; DUR = K.DUR; TT = K.TT; WEB = K.WEB
T_DROP = K.T_DROP; MUSIC_OFF = K.MUSIC_OFF

# custom scenes go here (see templates/explainer/scenes.py for the pattern); register them in ORDER by scene id
ORDER = K.default_order({})
K.finish(ORDER)
_END = SC[ORDER[-1][0]].s + 0.1
_BAR = TT.get("early_cta") or f"{K.SC[ORDER[-1][0]].show.get('button', 'Book a free demo')}  →  {WEB.replace('www.', '')}"
SHAKES = K.ad_shakes()


def overlays(im, t):
    K.corner_logo(im, t, T_DROP + 2.5, _END, h=50, x=1570, y=952)
    K.early_cta(im, t, T_DROP + 1.6, _END, _BAR)


def frame(t):
    return K.compose(t, ORDER, shakes=SHAKES, overlays=[overlays])
