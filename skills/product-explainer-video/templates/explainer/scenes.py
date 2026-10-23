"""<Company> product explainer (16:9, 1920x1080). Scenes come from edit/vo_lines{_lang}.json: each scene's "type" picks a
built-in look from toolkit/explainer_kit.py and its "show" block holds the on-screen content; anchor words are timed to
the ElevenLabs word timestamps in work/vo{_lang}/timeline.json. Write a custom scene function (below) for anything the
built-ins don't cover - real products usually need 2-4 bespoke scenes (a product-specific flow, a before/after, a device).

Language/region: TV_LANG (render.py --lang). Brand colours, logos, url: edit/config.json -> <brand>/brand.json.
Design space 1920x1080; c.w("word") = time that word starts; K.fx(name, t, db) schedules a sound effect.
"""
import os, sys
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("STUDIO_ROOT") or os.path.dirname(os.path.dirname(P))
sys.path.insert(0, f"{ROOT}/toolkit")
import explainer_kit as K
K.load(P)                                   # colours the engine first, so the imports below see the brand colours
import explainer as X
from explainer import (place, reveal, pop, text, pill, bubble, card, browser, phone_screen, image, cursor_tap,
                       life, prog, out_cubic, out_back, inout, lerp, clip, px, TVA, TVB, INK, MUTE, RED, GRN, WHITE)
from explainer_kit import fx, H, label_card, badge, stat_card, logo_lockup, shot, title

SFX = K.SFX; SC = K.SC; DUR = K.DUR; TT = K.TT; WEB = K.WEB


# ---------------------------------------------------------------- custom scenes (examples; delete or adapt)
def s_custom_example(im, t, c):
    """pattern for a bespoke scene: kinetic headline from VO line 0, a screenshot, a pill tapped on a spoken word"""
    (w0, h0), = c.head(0, [(c.hw(0), (1, 2))])
    H(im, c, t, w0, 170, 72, hi=h0)
    reveal(im, browser(shot("web_dashboard.png"), 1100), 960, 600, t, c.L(0) + 0.3, c.out)
    tw = c.w("click", default=c.frac(0.6))
    pop(im, pill("Click me", 34, "bold", icon="👆"), 960, 900, t, tw - 0.35, c.out)
    cursor_tap(im, 960, 900, t, tw, c.out); fx("ui_click", tw, 0)


ORDER = K.default_order({})   # e.g. {"feature2": s_custom_example} to replace a built-in scene by id
K.finish(ORDER)
_ids = [sid for sid, _ in ORDER]
_LOGO_FROM = SC[_ids[min(len(_ids) - 1, _ids.index("reveal") + 1 if "reveal" in _ids else 1)]].s
_LOGO_TO = SC[_ids[-1]].s + 0.3


def frame(t):
    return K.compose(t, ORDER, overlays=[lambda im, t: K.corner_logo(im, t, _LOGO_FROM, _LOGO_TO)])


def scene_starts():
    return [(sid, SC[sid].s) for sid in _ids]
