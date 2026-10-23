"""Project glue + reusable scenes for explainer.py videos (product explainers and 30 s ads for any brand).

A project's edit/scenes.py does:

    import explainer_kit as K
    K.load(P)                       # edit/config.json -> brand.json colours/logos/region urls, VO timeline, on-screen data
    ORDER = K.default_order()       # or [(scene_id, fn), ...] with your own scene functions
    K.finish(ORDER)                 # momentum layer + scene-change whooshes
    def frame(t): return K.compose(t, ORDER)

Data (all per language, in edit/vo_lines{_lang}.json):
  scenes[i].type   which built-in scene draws it: hook | pains | statement | reveal | feature | steps | stats | cta
  scenes[i].show   that scene's on-screen content (see each s_<type> below); words named as anchors are timed to the VO
  scenes[i].chapter  optional HUD chapter label (explainers)
  titles           free-form strings for hand-written scenes (K.TT)
Language/region comes from TV_LANG (en | hi | ca | ...): VO timeline work/vo{_lang}/timeline.json, url from brand.json regions.
Layout: canvas size comes from X.W / X.H, so the same scene functions lay out 16:9 and 9:16 (portrait branches inside).
"""
import json, math, os, re
import numpy as np
from PIL import Image, ImageDraw
import explainer as X
import explainer_fx as M
from explainer import (place, reveal, pop, text, pill, bubble, card, browser, phone_screen, image, headline, cursor_tap,
                       life, prog, out_cubic, out_back, in_cubic, inout, lerp, clip, px)

ROOT = X.ROOT
RED = X.RED; GRN = X.GRN; AMB = X.AMB; WHITE = X.WHITE
SFX = {}
CFG = {}; BRAND = {}; VO = {}; TT = {}; SC = {}; TL = {}
LANG = "en"; LSUF = ""; WEB = ""; DUR = 0.0; B = ""; FAST = False; T_DROP = 0.0; MUSIC_OFF = None
LOGO = {}


def fx(name, t, db=0.0):
    """schedule a sound effect (assets/sfx/<name>.wav) at time t, gain in dB"""
    SFX[(name, round(t, 2))] = db


def norm(w): return re.sub(r"[^a-z0-9%]", "", w.lower())


def portrait(): return X.H > X.W
def CX(): return X.W / 2


# ---------------------------------------------------------------- scene timing
class Sc:
    """one VO scene: s/e = span, lines[i] = {text, s, e, words:[{w,s,e}], head?}, show = on-screen data"""

    def __init__(self, d, src):
        self.id, self.s, self.e, self.lines = d["id"], d["s"], d["e"], d["lines"]
        self.type = src.get("type"); self.show = src.get("show", {}); self.chapter = src.get("chapter", "")
        self.words = [w for ln in self.lines for w in ln["words"]]
        self.out = self.e + (0.06 if FAST else 0.12)  # elements fade out just after the scene ends

    def w(self, word, n=1, after=0.0, default=None):
        """start time of the n-th on-screen word starting with `word` (tuple = alternatives per language, e.g. ("one", "ek")).
        Missing word: `default` if given, else KeyError (so a script edit that drops an anchor word is caught)."""
        if isinstance(word, (int, float)): return float(word)
        for alt in (word if isinstance(word, (tuple, list)) else (word,)):
            k = 0
            for x in self.words:
                if x["s"] >= after and norm(x["w"]).startswith(norm(alt)):
                    k += 1
                    if k == n: return x["s"]
        if default is not None: return default
        raise KeyError(f"{self.id}: word {word!r} #{n}")

    def L(self, i=0): return self.lines[i]["s"]
    def LE(self, i=0): return self.lines[i]["e"]
    def at(self, f, i=0): return lerp(self.L(i), self.LE(i), f)  # time at fraction f through line i
    def frac(self, f): return lerp(self.s, self.e, f)

    def hw(self, i, a=0, b=None):
        """(word, time) list for line i, words a..b"""
        return [(x["w"], x["s"]) for x in self.lines[i]["words"][a:b]]

    def head(self, i, default):
        """headline groups [(words, hi)] for line i: the language file's "head" if given, else default (list or callable)"""
        h = self.lines[i].get("head")
        if h: return [([(x["w"], x["s"]) for x in ws], tuple(hi)) for ws, hi in h]
        return default(self.hw(i)) if callable(default) else default

    def anchor(self, a, i, n, default=None):
        """time for item i of n: an anchor word if given, else line i (when the scene has one line per item), else spread"""
        if a:
            try: return self.w(a)
            except KeyError: pass
        if len(self.lines) >= n: return self.L(i) - (0.05 if FAST else 0)
        return default if default is not None else lerp(self.s + 0.2, self.e - 0.8, i / max(1, n - 1)) if n > 1 else self.s + 0.2


# ---------------------------------------------------------------- loading
def load(P, lang=None):
    """read edit/config.json + brand.json + the VO timeline; colour the engine. Call at the top of scenes.py.
    config.brand = brand folder (relative to the studio root, or absolute) holding brand.json, logos and screenshots."""
    global CFG, BRAND, VO, TT, SC, TL, LANG, LSUF, WEB, DUR, B, FAST, T_DROP, MUSIC_OFF
    CFG = json.load(open(f"{P}/edit/config.json"))
    bdir = CFG["brand"].rstrip("/"); B = bdir + "/"
    BRAND = json.load(open(os.path.join(ROOT, bdir, "brand.json")))
    c = BRAND.get("colors", {})
    X.brand(a=c.get("a"), b=c.get("b"), ink=c.get("ink"), mute=c.get("mute"), accent3=c.get("accent3"),
            bg=(c["bg_top"], c["bg_bottom"]) if c.get("bg_top") else None)
    LANG = lang or os.environ.get("TV_LANG", "en"); LSUF = "" if LANG == "en" else f"_{LANG}"
    regs = BRAND.get("regions", {}); r = regs.get(LANG) or regs.get("en") or {}
    WEB = r.get("web", "www.example.com")
    X.APP_URL = r.get("app_url") or ("app." + re.sub(r"^www\.", "", WEB))
    X.STRIP_BAR = bool(r.get("strip_bar", False))
    for k, f in BRAND.get("logos", {}).items():
        LOGO[k] = B + f if f and os.path.exists(os.path.join(ROOT, B + f)) else None
    VO = json.load(open(f"{P}/edit/vo_lines{LSUF}.json")); TT = VO.get("titles", {})
    TL = json.load(open(f"{P}/work/vo{LSUF}/timeline.json"))
    FAST = CFG.get("kind", "explainer") == "ad"
    src = {s["id"]: s for s in VO["scenes"]}
    SC = {d["id"]: Sc(d, src.get(d["id"], {})) for d in TL["scenes"]}
    DUR = TL["duration"]
    if FAST and "reveal" in SC:  # ads: the music drop lands on the logo slam, on the beat grid
        beat = CFG.get("beat", 0.5)
        T_DROP = math.ceil((SC["reveal"].s + 0.1) / beat) * beat
        MUSIC_OFF = CFG.get("music_drop", 16.0) - T_DROP
    return SC


def shot(name):
    """brand screenshot path: names without a folder are looked up in the brand folder"""
    return name if "/" in name else B + name


# ---------------------------------------------------------------- small pieces
def H(im, c, t, words, cy, size, hi=(), t_out=None, cx=None, maxw=None, weight="black", color=None):
    headline(im, words, CX() if cx is None else cx, cy, size, t, t_out or c.out, weight=weight, color=color or X.INK, hi=hi,
             maxw=maxw or (X.W * 0.82 if portrait() else 1500))


def fit(s, size, maxw, weight="black", color=None, grad=None):
    """largest text sprite <= maxw design px, shrinking from size"""
    color = color or X.INK
    while size > 20:
        sp = text(s, size, weight, color, grad=grad)
        if sp.width / X.S <= maxw: return sp
        size -= 4
    return text(s, size, weight, color, grad=grad)


def two_lines(s):
    w = s.split()
    if len(w) == 1: return [s]
    best = min(range(1, len(w)), key=lambda i: abs(len(" ".join(w[:i])) - len(" ".join(w[i:]))))
    return [" ".join(w[:best]), " ".join(w[best:])]


def tint(): return X._mix(X.TVA, WHITE, 0.9)


def label_card(icon, title, w=500, h=150, sub=None, size=34, bub=None):
    """white card: icon bubble on the left, bold title (and optional sub line); grows to fit long (Hinglish) titles"""
    def mk():
        tt = text(title, size, "bold", X.INK); st = text(sub, size * 0.7, "med", X.MUTE) if sub else None
        need = (px(27) + px(h - 54) + px(24) + max(tt.width, st.width if st else 0) + px(36)) / X.S
        im = X.rrect(max(w, need), h, 26)
        b = X.circle(h - 54, bub or tint()); e = X.emoji(icon, (h - 54) * 0.52)
        b.alpha_composite(e, ((b.width - e.width) // 2, (b.height - e.height) // 2))
        im.alpha_composite(b, (px(27), px(27)))
        x0 = px(27) + b.width + px(24)
        if st:
            y = (im.height - tt.height - st.height - px(8)) // 2
            im.alpha_composite(tt, (x0, y)); im.alpha_composite(st, (x0, y + tt.height + px(8)))
        else:
            im.alpha_composite(tt, (x0, (im.height - tt.height) // 2))
        return X.shadowed(im)
    return X.cached(("KLC", icon, title, w, h, sub, size, bub), mk)


def badge(ch, col, d=56):
    """round ✕ / ✓ / text badge"""
    def mk():
        c = X.circle(d, col); dr = ImageDraw.Draw(c); w = c.width; lw = max(2, px(d * 0.1))
        if ch == "✕":
            m = w * 0.32; dr.line([m, m, w - m, w - m], fill=WHITE, width=lw); dr.line([m, w - m, w - m, m], fill=WHITE, width=lw)
        elif ch == "✓":
            dr.line([(w * 0.28, w * 0.52), (w * 0.44, w * 0.68), (w * 0.73, w * 0.36)], fill=WHITE, width=lw, joint="curve")
        else:
            s = text(ch, d * 0.5, "black", WHITE); c.alpha_composite(s, ((c.width - s.width) // 2, (c.height - s.height) // 2))
        return X.shadowed(c, 10, 6, 0.25)
    return X.cached(("KBADGE", ch, col, d), mk)


def stat_card(label, value_sprite, w=420, h=250):
    im = card(w, h, 30).copy()
    l = text(label, 26, "demi", X.MUTE, track=3); cx = im.width // 2
    im.alpha_composite(l, (cx - l.width // 2, im.height // 2 - px(h / 2) + px(40)))
    im.alpha_composite(value_sprite, (cx - value_sprite.width // 2, im.height // 2 - px(10) - value_sprite.height // 2 + px(30)))
    return im


def wipe(im, spr, x_left, cy, k, a=1.0):
    """reveal sprite left->right (k 0..1)"""
    if k <= 0 or a <= 0: return
    w = max(1, int(spr.width * k)); s = spr.crop((0, 0, w, spr.height))
    place(im, s, x_left + w / X.S / 2, cy, a=a)


def _text_mark(h):
    """fallback logo mark when the brand has no mark image: gradient disc with the initial"""
    def mk():
        c = X.circle(h, grad=(X.TVA, X.TVB)); s = text(BRAND.get("name", "?")[0].upper(), h * 0.55, "black", WHITE)
        c.alpha_composite(s, ((c.width - s.width) // 2, (c.height - s.height) // 2)); return c
    return X.cached(("TMARK", h), mk)


def logo_parts(scale=1.0, mark_h=220, word_h=104):
    mark = image(LOGO["mark"], h=mark_h * scale) if LOGO.get("mark") else _text_mark(mark_h * scale)
    word = image(LOGO["word"], h=word_h * scale) if LOGO.get("word") else text(BRAND.get("name", ""), word_h * 1.15 * scale, "black", X.INK)
    return mark, word


def logo_full(h=54):
    if LOGO.get("full"): return image(LOGO["full"], h=h)
    def mk():
        m, w = logo_parts(h / 220, 220, 104 * 1.1); g = px(h * 0.22)
        im = Image.new("RGBA", (m.width + g + w.width, max(m.height, w.height)))
        im.alpha_composite(m, (0, (im.height - m.height) // 2)); im.alpha_composite(w, (m.width + g, (im.height - w.height) // 2)); return im
    return X.cached(("KLOGOFULL", h), mk)


def logo_lockup(im, t, t0, cx=None, cy=430, t_out=None, scale=1.0, sfx=True, slam=None):
    """mark pops (explainer) or slams (ad) at centre, slides left as the wordmark wipes in"""
    slam = FAST if slam is None else slam; cx = CX() if cx is None else cx
    mark, word = logo_parts(scale, 230 if slam else 220, 110 if slam else 104)
    mw, ww, gap = mark.width / X.S, word.width / X.S, 46 * scale
    mx_end = cx - (mw + gap + ww) / 2 + mw / 2; wx_left = mx_end + mw / 2 + gap
    if slam:
        k1, a = life(t, t0, t_out, 0.25, 0.2)
        if a <= 0: return
        k2 = inout(prog(t, t0 + 0.28, 0.35))
        place(im, mark, lerp(cx, mx_end, k2), cy, lerp(1.7, 1, out_cubic(k1)), a, blur=12 * (1 - k1))
        wipe(im, word, wx_left, cy + 6 * scale, out_cubic(prog(t, t0 + 0.4, 0.35)), a)
        if sfx: fx("riser", t0 - 1.6, -6); fx("boom_hit", t0, 0); fx("impact", t0, -3); fx("whoosh", t0 + 0.3, -4)
    else:
        k1, a = life(t, t0, t_out, 0.55, 0.4)
        if a <= 0: return
        k2 = inout(prog(t, t0 + 0.55, 0.6))
        place(im, mark, lerp(cx, mx_end, k2), cy, max(0.02, out_back(k1, 1.3)), a, rot=-25 * (1 - out_cubic(k1)))
        wipe(im, word, wx_left, cy + 6 * scale, out_cubic(prog(t, t0 + 0.75, 0.6)), a)
        if sfx: fx("whoosh", t0 - 0.1, 0); fx("boom_hit", t0 + 0.05, -4); fx("swish", t0 + 0.6, -2); fx("ding", t0 + 1.3, -6)


def title(im, c, t, s, y=None, size=None, t0=None, grad=False, maxw=None):
    """scene title that drops in with blur (ad pace) at the top of the content area"""
    y = y if y is not None else (400 if portrait() else 150); size = size or (66 if portrait() else 70)
    t0 = c.s + 0.05 if t0 is None else t0
    k, a = life(t, t0, c.out, 0.28 if FAST else 0.42, 0.15 if FAST else 0.3)
    if a <= 0: return
    e = out_cubic(k)
    spr = fit(s, size, maxw or X.W * 0.88, grad=(X.TVA, X.TVB) if grad else None)
    place(im, spr, CX(), y + 24 * (1 - e), lerp(1.12, 1, e), a, blur=10 * (1 - e))


def slam(im, spr, x, y, t, t0, t1, s0=1.45, rot=0.0):
    """fast scale-down slam with blur (0.22 s)"""
    k, a = life(t, t0, t1, 0.22, 0.15)
    if a <= 0: return
    e = out_cubic(k)
    place(im, spr, x, y, lerp(s0, 1, e), min(1, a * 2), rot=rot, blur=14 * (1 - e))


def shake(t, t0, amp=14, d=0.18):
    k = prog(t, t0, d)
    if not 0 < k < 1: return 0.0, 0.0
    f = (1 - k) * amp
    return f * math.sin(t * 95), f * math.cos(t * 77)


def white(a):
    w = X.cached(("KWHITE",), lambda: Image.new("RGBA", (X.RW, X.RH), (255, 255, 255, 255)))
    w = w.copy(); w.putalpha(int(255 * a)); return w


def red_vignette():
    def mk():
        y = np.linspace(-1, 1, X.RH, dtype=np.float32)[:, None]; x = np.linspace(-1, 1, X.RW, dtype=np.float32)[None, :]
        a = np.clip(np.sqrt(x ** 2 * 0.8 + y ** 2) - 0.45, 0, 1) ** 1.2
        im = Image.new("RGBA", (X.RW, X.RH), RED + (0,)); im.putalpha(Image.fromarray((a * 255).astype(np.uint8), "L")); return im
    return X.cached(("KREDV",), mk)


def frame_shot(name, kind="browser", size=None):
    """screenshot sprite: browser window, phone bezel (raw screen), or a ready-made mockup image"""
    p = shot(name)
    if kind == "phone": return phone_screen(p, size or 640)
    if kind == "image": return image(p, h=size or 560)
    return browser(p, size or 1120)


def counter_val(spec, k):
    """'3x' / '92%' / '500+' / '1,248' animated to fraction k"""
    m = re.match(r"^([^\d]*)([\d,\.]+)(.*)$", spec)
    if not m: return spec
    pre, num, post = m.groups(); v = float(num.replace(",", "")) * k
    s = f"{v:,.0f}" if "," in num else (f"{v:.1f}" if "." in num else f"{int(v)}")
    return pre + s + post


# ---------------------------------------------------------------- built-in scenes
# Each takes (im, t, c); c.show holds its on-screen data. Explainers (FAST False) ease in slowly and use the kinetic
# headline from the VO line; ads (FAST True) slam titles in and keep each beat short.

def s_hook(im, t, c):
    """show: {icon: "📞", title?: "MISSED FOLLOW-UPS", sub?: "= LOST DEALS", hi?: [word idx], pill?: "BUSY ≠ PRODUCTIVE"}
    Without title the first VO line becomes the kinetic headline."""
    sh = c.show; icon = sh.get("icon", "📞"); P = portrait(); cx = CX()
    spots = ([(170, 420), (910, 420), (170, 1030), (910, 1030)] if P else
             [(330, 250), (1590, 250), (330, 820), (1590, 820)] if FAST else
             [(150, 190), (1770, 210), (190, 900), (1730, 890), (640, 1000), (1290, 1000)])
    for i, (x, y) in enumerate(spots):
        ti = c.s + 0.12 + (0.08 if FAST else 0.15) * i
        k, a = life(t, ti, c.out, 0.3 if FAST else 0.45, 0.15 if FAST else 0.35)
        if a > 0:
            wig = 10 * math.sin((t - ti) * 30) * math.exp(-((t - ti) % 1.4) * 3)
            place(im, bubble(icon, 130 if P else 140), x, y + (0 if FAST else 8 * math.sin(t * 1.7 + i)), max(0.02, out_back(k)), a, rot=wig)
            if sh.get("title") and k > 0.5: place(im, badge("✕", RED, 50), x + 50, y - 50, out_back(prog(t, ti + 0.2, 0.3)), a)
        fx("pop", ti, -4)
    if sh.get("title"):
        t0 = c.s + 0.12
        lines = two_lines(sh["title"]) if P else [sh["title"]]
        for li, ln in enumerate(lines):
            slam(im, fit(ln, 150 if P else 128, X.W * 0.88), cx, (600 + li * 150) if P else 470, t, t0 + 0.06 * li, c.out)
        if sh.get("sub"):
            ts = c.at(0.5)
            st = pill(sh["sub"], 54 if P else 60, "black", fg=WHITE, grad=(RED, (255, 110, 90)), padx=46, pady=22)
            slam(im, st, cx, 900 if P else 650, t, ts, c.out, s0=1.8, rot=-4); fx("boom_hit", ts, -2)
        fx("impact", t0, 0); fx("buzz", t0 + 0.2, -10)
    else:
        (w0, h0), = c.head(0, [(c.hw(0), tuple(sh.get("hi", ())))])
        H(im, c, t, w0, 820 if P else 540, 80, hi=h0, maxw=X.W * 0.88 if P else 1750)
        fx("notification", c.L(0) + 0.1, -6)
    if sh.get("pill"):
        tb = c.LE(len(c.lines) - 1) - 0.3
        pop(im, pill(sh["pill"], 40, "black", fill=X.INK, padx=44, pady=22), cx, 1080 if P else 880, t, tb, c.out); fx("impact", tb, -2)


def s_pains(im, t, c):
    """show: {label?: "SOUND FAMILIAR?", items: [[icon, text, anchor_word?], ...]} - pain cards with red ✕ badges.
    Ads: cards slide in from the right with a shake and a red alarm pulse (one VO line per card)."""
    items = c.show["items"]; n = len(items); P = portrait(); cx = CX()
    if c.show.get("label"): reveal(im, text(c.show["label"], 30, "xbold", X.TVA, track=8), cx, 380 if P else 190, t, c.s + 0.1, c.out)
    for i, it in enumerate(items):
        ic, lab = it[0], it[1]; t0 = c.anchor(it[2] if len(it) > 2 else None, i, n)
        if FAST or P:
            y = (520 if P else 330) + i * (200 if n <= 3 else 150) if P or n <= 3 else 300 + i * 150
            lc = label_card(ic, lab, 700 if P else 760, 150, size=40 if P else 44, bub=(255, 236, 238))
            k, a = life(t, t0, c.out, 0.24 if FAST else 0.45, 0.15)
            if a > 0:
                e = out_cubic(k); place(im, lc, cx + 700 * (1 - e), y, a=a, blur=16 * (1 - e))
            cw = lc.width / X.S - 140
            pop(im, badge("✕", RED, 60), cx + cw / 2 - 18, y - 56, t, t0 + 0.25, c.out, din=0.3)
            fx("whoosh_fast", t0 - 0.05, -2); fx("impact", t0 + 0.22, -6)
        else:
            cols = 3 if n > 4 else 2; x = [[660, 1260], [390, 960, 1530]][cols - 2][i % cols]
            rows = math.ceil(n / cols); y = 550 + (i // cols - (rows - 1) / 2) * 220
            reveal(im, label_card(ic, lab, 540, 160), x, y, t, t0, c.out)
            pop(im, badge("✕", RED), x + 255, y - 66, t, t0 + 0.45, c.out)
            fx("swish", t0, -4); fx("buzz", t0 + 0.45, -12)
    if FAST:
        k = prog(t, c.L(len(c.lines) - 1), c.e - c.L(len(c.lines) - 1))
        if k > 0: place(im, red_vignette(), cx, X.H / 2, a=0.35 * k * (0.7 + 0.3 * math.sin(t * 20)))


def pains_shake(t, c):
    return tuple(map(sum, zip(*[shake(t, c.anchor(it[2] if len(it) > 2 else None, i, len(c.show["items"])) + 0.22)
                                for i, it in enumerate(c.show["items"])]))) if FAST else (0.0, 0.0)


def s_statement(im, t, c):
    """show: {hi: [[idx...], [idx...]]} - each VO line as a stacked kinetic headline; last line big with highlights.
    The language file's per-line "head" overrides the split."""
    n = len(c.lines); P = portrait(); his = c.show.get("hi", [])
    groups = []
    for i in range(n):
        groups += c.head(i, [(c.hw(i), tuple(his[i]) if i < len(his) else ())])
    m = len(groups); y0 = (760 if P else 540) - (m - 1) * (75 if P else 70)
    for j, (ws, hi) in enumerate(groups):
        last = j == m - 1
        size = (96 if P else 112) if last else (56 if P else 62)
        H(im, c, t, ws, y0 + j * (150 if P else 140), size, hi=hi, color=X.INK if last else X.MUTE, weight="black" if last else "xbold",
          maxw=X.W * 0.9 if P else 1800)
    fx("whoosh_long", c.L(0) - 0.2, -4); fx("impact", c.L(n - 1) + 0.3, -2)


def s_reveal(im, t, c):
    """show: {sub: "tagline", icons?: [[icon, label, anchor?], ...], pill?: "ALL IN ONE PLACE"} - logo lockup
    (on the music drop for ads, with a white flash from compose())"""
    sh = c.show; P = portrait(); cx = CX()
    t0 = T_DROP if FAST else c.s + 0.15
    logo_lockup(im, t, t0, cy=600 if P else (410 if FAST else 400), t_out=c.out, scale=0.72 if P else 1.0)
    if not FAST: fx("riser", c.s - 1.4, -6)
    if sh.get("sub"):
        ts = c.L(min(1, len(c.lines) - 1)) if not FAST else t0 + 0.6
        k, a = life(t, ts - 0.1, c.out, 0.3 if FAST else 0.45, 0.15)
        if a > 0:
            e = out_cubic(k)
            place(im, fit(sh["sub"], 64 if P else (66 if FAST else 56), X.W * 0.88, grad=(X.TVA, X.TVB)), cx, (800 if P else 650 if FAST else 640) + 20 * (1 - e), a=a, blur=8 * (1 - e))
        fx("swish", ts - 0.1, -4)
    ics = sh.get("icons", [])
    for i, it in enumerate(ics):
        x = cx + (i - (len(ics) - 1) / 2) * (240 if P else 260); y = 1000 if P else 790
        ti = c.anchor(it[2] if len(it) > 2 else None, 99, 99, default=c.frac(0.45 + 0.08 * i))
        pop(im, bubble(it[0], 120), x, y, t, ti, c.out); reveal(im, text(it[1], 30, "bold", X.INK), x, y + 100, t, ti + 0.1, c.out, dy=14)
        fx("pop", ti, -3)
    if sh.get("pill"):
        tp = c.frac(0.8)
        pop(im, pill(sh["pill"], 34, "black", padx=40), cx, 1180 if P else 940, t, tp, c.out); fx("success", tp, -6)


def s_feature(im, t, c):
    """show: {title, shot: "web_x.png", frame: browser|phone|image, size?, side?: left|right,
              sub?: "...", pills?: [[icon, label, anchor?], ...], tap?: anchor word}
    Screenshot on one side with a slow push-in; title on top; pills pop on the other side, timed to their anchor words."""
    sh = c.show; P = portrait(); cx = CX(); kind = sh.get("frame", "browser")
    t0 = c.s + 0.05
    if sh.get("title"): title(im, c, t, sh["title"], size=66 if P else 68)
    right = sh.get("side", "right") == "right"
    if P:
        sx_, sy_ = cx, 780; size = sh.get("size_916") or {"browser": 900, "phone": 560, "image": 520}[kind]
    else:
        sx_, sy_ = (1180 if right else 740), 590; size = sh.get("size") or {"browser": 1040, "phone": 680, "image": 600}[kind]
    k, a = life(t, t0, c.out, 0.3 if FAST else 0.5, 0.15 if FAST else 0.35)
    if a > 0:
        z = 1 + 0.05 * inout(prog(t, t0, c.e - t0))
        place(im, frame_shot(sh["shot"], kind, size), sx_, sy_ + 50 * (1 - out_cubic(k)), z * lerp(0.94, 1, out_cubic(k)), a, blur=10 * (1 - k))
    pills = sh.get("pills", [])
    for i, it in enumerate(pills):
        ti = c.anchor(it[2] if len(it) > 2 else None, 99, 99, default=t0 + (0.25 if FAST else 0.6) + (0.2 if FAST else 0.5) * i)
        if P: x, y = (cx, 1050) if len(pills) == 1 else (cx + (-230 if i % 2 == 0 else 230), 1030 + (i // 2) * 100)
        else: x, y = (430 if right else 1490), 380 + i * 130 * (4 / max(4, len(pills)))
        pop(im, pill(it[1], 34 if not P else 32, "bold", fg=X.INK, fill=WHITE, icon=it[0], padx=30, pady=16), x, y, t, ti, c.out,
            din=0.3 if FAST else 0.45)
        fx("pop", ti, -4)
    if sh.get("sub"):
        reveal(im, fit(sh["sub"], 38, X.W * 0.8, "bold", X.MUTE), cx, 1110 if P else 990, t, t0 + 0.3, c.out, dy=10, din=0.3)
    if sh.get("tap"):
        tt = c.w(sh["tap"], default=c.frac(0.6))
        cursor_tap(im, sx_ + (0 if P else 120), sy_ + 60, t, tt, c.out); fx("ui_click", tt, 0)
    fx("whoosh_fast" if FAST else "swish", t0, -4)


def s_steps(im, t, c):
    """show: {title?, items: [[icon, label, sub, anchor?], ...]} - numbered steps joined by a drawing line"""
    sh = c.show; its = sh["items"]; n = len(its); P = portrait(); cx = CX()
    if sh.get("title"): title(im, c, t, sh["title"])
    pos = [(cx, 560 + i * (560 / max(1, n - 1)) - 0) for i in range(n)] if P else \
          [(cx + (i - (n - 1) / 2) * min(340, 1600 / n), 560) for i in range(n)]
    times = [c.anchor(it[3] if len(it) > 3 else None, i, n) for i, it in enumerate(its)]
    _, a = life(t, times[0], c.out)
    if a > 0 and n > 1:
        dr = ImageDraw.Draw(im); kk = clip((t - times[0]) / max(0.3, times[-1] - times[0]))
        (x0, y0), (x1, y1) = pos[0], pos[-1]
        dr.line([px(x0), px(y0), px(lerp(x0, x1, kk)), px(lerp(y0, y1, kk))], fill=X.TVA + (int(110 * a),), width=max(2, px(5)))
    for i, it in enumerate(its):
        x, y = pos[i]; ti = times[i]
        pop(im, bubble(it[0], 120 if P else 140), x if not P else x - 330, y, t, ti, c.out)
        pop(im, badge(str(i + 1), X.TVA, 46), (x if not P else x - 330) + 50, y - 50, t, ti + 0.15, c.out)
        if P:
            reveal(im, text(it[1], 40, "black", X.INK), x + 80, y - 18, t, ti + 0.1, c.out, dy=12)
            reveal(im, text(it[2], 28, "med", X.MUTE), x + 80, y + 30, t, ti + 0.2, c.out, dy=10)
        else:
            reveal(im, text(it[1], 34, "black", X.INK), x, y + 120, t, ti + 0.1, c.out, dy=12)
            reveal(im, text(it[2], 25, "med", X.MUTE), x, y + 168, t, ti + 0.2, c.out, dy=10)
        fx("pop", ti, -3)


def s_stats(im, t, c):
    """show: {title?, items: [["3x", "more calls", anchor?], ["92%", "follow-ups on time"], ...]} - counting stat cards"""
    sh = c.show; its = sh["items"]; n = len(its); P = portrait(); cx = CX()
    if sh.get("title"): title(im, c, t, sh["title"])
    for i, it in enumerate(its):
        ti = c.anchor(it[2] if len(it) > 2 else None, i, n)
        if P: x, y = cx + (-235 if i % 2 == 0 else 235), 640 + (i // 2) * 300
        else: x, y = cx + (i - (n - 1) / 2) * min(520, 1700 / n), 600
        k, a = life(t, ti, c.out, 0.3 if FAST else 0.5, 0.15 if FAST else 0.35)
        if a > 0:
            v = text(counter_val(it[0], out_cubic(prog(t, ti, 0.8))), 100 if n > 2 or P else 120, "black", grad=(X.TVA, X.TVB))
            cw = 420 if P else min(460, 1700 / n - 70)
            place(im, stat_card(it[1].upper(), v, cw, 260), x, y + 40 * (1 - out_cubic(k)), a=a, blur=8 * (1 - k))
        fx("swish", ti, -4); [fx("tick", ti + 0.1 * j, -12) for j in range(6)]


def s_cta(im, t, c):
    """show: {button: "Book a Free Demo", tap?: anchor word, head_hi?: [idx]} - logo, glowing button + cursor tap, url"""
    sh = c.show; P = portrait(); cx = CX()
    if not FAST and len(c.lines) > 1:  # explainer: line 0 as a headline first, then the end card
        (w0, h0), = c.head(0, [(c.hw(0), tuple(sh.get("head_hi", ())))])
        H(im, c, t, w0, 540, 84, hi=h0, t_out=c.L(1) + 0.1, maxw=1800)
        t0 = c.L(1) - 0.1
    else:
        t0 = c.s + 0.05
    logo_lockup(im, t, t0, cy=560 if P else 330, t_out=None, scale=0.72 if P else 0.92)
    tb = t0 + (0.35 if FAST else 0.8)
    k, a = life(t, tb, None, 0.35 if FAST else 0.5)
    by = 800 if P else 620
    if a > 0:
        glow = 1 + 0.035 * math.sin(max(0, t - tb) * 5)
        place(im, pill(sh.get("button", "Book a Free Demo"), 56 if P else 60, "black", padx=70, pady=32), cx, by, out_back(k) * glow, a)
    ttap = c.w(sh["tap"], after=t0, default=tb + 0.8) + 0.2 if sh.get("tap") else tb + 0.8
    cursor_tap(im, cx + 50, by, t, ttap, None)
    reveal(im, fit(WEB, 58 if FAST else 48, X.W * 0.86, "black" if FAST else "bold", X.INK), cx, by + (160 if P else 165), t, tb + 0.3, None, dy=14, din=0.35)
    fx("whoosh", t0, -2); fx("impact", tb, -3); fx("ui_click", ttap, 0); fx("success", ttap + 0.1, -4)
    if not FAST: fx("reverse_swell", c.e - 2.6, -8)


TYPES = {"hook": s_hook, "pains": s_pains, "statement": s_statement, "reveal": s_reveal, "feature": s_feature,
         "steps": s_steps, "stats": s_stats, "cta": s_cta}


def default_order(custom=None):
    """[(id, fn)] in timeline order: custom[id] if given, else the built-in scene for that scene's type"""
    custom = custom or {}
    out = []
    for d in TL["scenes"]:
        c = SC[d["id"]]; fn = custom.get(c.id) or TYPES.get(c.type)
        if fn is None: raise SystemExit(f"scene {c.id!r}: no custom function and unknown type {c.type!r}")
        out.append((c.id, fn))
    return out


# ---------------------------------------------------------------- overlays
def corner_logo(im, t, t0, t1, h=54, x=200, y=62):
    k, a = life(t, t0, t1, 0.6, 0.4)
    if a > 0: place(im, logo_full(h), x, y, a=a * 0.95)


def early_cta(im, t, t0, t1, label):
    """persistent lower bar (ads): the action is on screen long before the end card"""
    k, a = life(t, t0, t1, 0.35, 0.25)
    if a <= 0: return
    bar = X.cached(("KECTA", label), lambda: pill(label, 30, "black", fg=X.INK, fill=WHITE, padx=34, pady=14, icon="📅"))
    place(im, bar, CX(), X.H - 128 + 30 * (1 - out_cubic(k)), a=a)


def caption_chunks(maxw=4, src=None):
    """VO words grouped into short caption chunks: (start, end, words)"""
    out = []
    for sc in (src or TL)["scenes"]:
        for ln in sc["lines"]:
            cur = []
            for w in ln["words"]:
                cur.append(w)
                if len(cur) >= maxw or w["w"][-1] in ".,?!:।": out.append(cur); cur = []
            if cur: out.append(cur)
    res = []
    for i, ch in enumerate(out):
        end = out[i + 1][0]["s"] if i + 1 < len(out) and out[i + 1][0]["s"] - ch[-1]["e"] < 0.6 else ch[-1]["e"] + 0.3
        res.append((ch[0]["s"], end, ch))
    return res


FUT = (150, 152, 182)


def captions(im, t, chunks, y=1190, size=52):
    """burned-in word-by-word captions on a white pill (9:16, sound-off feeds); current word in the brand gradient"""
    for s, e, ch in chunks:
        if not (s - 0.04 <= t < e): continue
        sps = []
        for w in ch:
            st = "now" if w["s"] <= t < w["e"] + 0.05 else ("past" if t >= w["s"] else "fut")
            sps.append(text(w["w"], size, "black", X.INK if st == "past" else FUT, grad=(X.TVA, X.TVB) if st == "now" else None))
        gap = px(16); tw = sum(s_.width for s_ in sps) + gap * (len(sps) - 1)
        scale = min(1.0, px(X.W * 0.89) / (tw + px(70)))
        bg = X.cached(("KCAPBG", int(tw)), lambda: X.shadowed(X.rrect((tw + px(70)) / X.S, size * 1.92, 30, fill=(255, 255, 255)), 18, 10, 0.18))
        k = out_cubic(prog(t, s - 0.04, 0.12))
        place(im, bg, CX(), y, scale * lerp(0.92, 1, k), 0.94 * k)
        x = px(CX()) - tw * scale / 2
        for sp in sps:
            place(im, sp, (x + sp.width * scale / 2) / X.S, y, scale, k)
            x += (sp.width + gap) * scale
        break


# ---------------------------------------------------------------- frame assembly
def finish(order, bpm=None):
    """momentum layer + a whoosh at every scene change. Explainer pace by default; ads get fast cuts and no HUD."""
    spans = [(SC[sid].s, SC[sid].e) for sid, _ in order]
    chapters = [SC[sid].chapter for sid, _ in order]
    bpm = bpm or CFG.get("bpm", 120 if FAST else 105)
    if FAST:
        M.setup(spans, bpm=bpm, chapters=[""] * len(order), beat0=0.0, drums_from=T_DROP,
                cam=0.06, drift=32, out=(0.14, 0.2, -480), **{"in": (0.24, 360)}, streak=0.4, hud=False)
    else:
        M.setup(spans, bpm=bpm, chapters=chapters, drums_from=CFG.get("drums_from", 4.6), hud=any(chapters))
    for sid, _ in order[:-1]:
        fx("whoosh_fast", SC[sid].e - (0.12 if FAST else 0.22), -6 if FAST else -7)


def compose(t, order, shakes=None, overlays=(), pre=None):
    """one frame: background, momentum back layer, each live scene on its own layer (camera push + slide/smear
    transitions + optional shake), then overlays (fn(im, t)), momentum front layer and (ads) the white flash on the drop."""
    im = X.background(t)
    M.back(im, t)
    pre = pre if pre is not None else (1.0 if FAST else 1.5)
    for idx, (sid, fn) in enumerate(order):
        c = SC[sid]
        if c.s - pre <= t <= c.out + 0.05:
            layer = Image.new("RGBA", im.size)
            fn(layer, t, c)
            dx, dy = (shakes or {}).get(sid, lambda t, c: (0.0, 0.0))(t, c)
            layer = M.camera(layer, t, idx, c.s, c.e)
            if dx or dy:
                layer = layer.transform(layer.size, Image.AFFINE, (1, 0, -px(dx), 0, 1, -px(dy)), resample=Image.BILINEAR)
            M.composite_scene(im, layer, t, c.s, c.e, first=idx == 0, last=idx == len(order) - 1)
    for ov in overlays: ov(im, t)
    M.front(im, t, DUR)
    if FAST and T_DROP:
        k = prog(t, T_DROP, 0.4)
        if 0 < k < 1: im.alpha_composite(white(0.9 * (1 - out_cubic(k))))
    return im


def ad_shakes():
    """default shakes for ads: the hook title slam and each pain card"""
    return {sid: (lambda t, c: shake(t, c.s + 0.3, 18)) if SC[sid].type == "hook" and SC[sid].show.get("title") else pains_shake
            for sid in SC if SC[sid].type in ("hook", "pains")}
