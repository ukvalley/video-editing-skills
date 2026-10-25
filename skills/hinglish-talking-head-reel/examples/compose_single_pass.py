#!/usr/bin/env python3
"""EXAMPLE (real project: the open-source skills launch reel, 41.7 s, approved first preview). Copy into a project's edit/.
Single-pass compositor: graded base + word-synced motion graphics (mg.py engine) + karaoke captions + SFX/music mix.

    python3 edit/compose.py --preview          # 540x960 -> work/mix_540.mov
    python3 edit/compose.py                    # 1080x1920 -> work/mix_1080.mov
    python3 edit/compose.py --stills 2,7,14    # full-res PNG checks -> work/stills/
"""
import argparse, glob, json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO = os.path.expanduser("~/video-editing")
sys.path.insert(0, os.path.expanduser("~/.claude/skills/motion-graphics/scripts"))
from mg import Ctx, text, pill, wipe, oc, ob, io, p, clamp, lerp, stagger, font  # noqa: E402

W0, H0, FPS = 1080, 1920, 25
Y = (255, 199, 0)          # brand yellow
CL = (217, 119, 87)        # Claude orange
INK = (14, 14, 18)
CARD = (20, 20, 26, 236)
WHITE = (255, 255, 255)
MUTE = (190, 190, 200)
RED = (235, 64, 52)
GRN = (46, 204, 113)
SFX = f"{STUDIO}/assets/sfx"
GRADE = ("colortemperature=temperature=6000:mix=0.45,curves=master='0/0 0.22/0.19 0.5/0.52 0.8/0.84 1/1',"
         "vibrance=intensity=0.18,eq=saturation=1.04,colorbalance=rm=0.015:bm=-0.015,unsharp=5:5:0.45:5:5:0,vignette=angle=0.5")

# ---------- output timeline ----------
K = json.load(open(f"{P}/edit/keeps.json"))
PH = {x["id"]: x for x in json.load(open(f"{P}/edit/phrases.json"))}
parts = sorted(glob.glob(f"{P}/work/keeps/k*.mov"))
dur = lambda f: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                     capture_output=True, text=True).stdout)
D = [dur(f) for f in parts]
OFF = list(np.cumsum([0] + D[:-1]))
TOTAL = float(sum(D))
SW = [w for w in json.load(open(f"{P}/work/scribe.json"))["words"] if w["type"] == "word"]
WORDS, SEG_T = [], {}
for k, s in enumerate(K["segments"]):
    SEG_T[s["id"]] = (OFF[k], OFF[k] + D[k])
    src = [w for w in SW if w["end"] > s["in"] + 0.05 and w["start"] < s["out"] - 0.02]
    toks = PH[s["id"]]["text"].split()
    if not toks:
        continue
    if len(src) != len(toks):
        print(f"! {s['id']}: {len(src)} spoken vs {len(toks)} caption words — spreading evenly")
        span = (s["out"] - s["in"]) / len(toks)
        src = [{"start": s["in"] + i * span, "end": s["in"] + (i + 0.9) * span} for i in range(len(toks))]
    for tok, w in zip(toks, src):
        a = OFF[k] + max(0.0, w["start"] - s["in"]); b = OFF[k] + min(s["out"], w["end"]) - s["in"]
        WORDS.append({"word": tok, "start": round(a, 3), "end": round(max(b, a + 0.08), 3)})


def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())


def w(word, n=1, after=0.0, end=False):
    """output time of the n-th spoken occurrence of `word` after `after`"""
    hits = [x for x in WORDS if norm(x["word"]) == norm(word) and x["start"] >= after - 1e-6]
    x = hits[n - 1]
    return x["end"] if end else x["start"]


def seg(i): return SEG_T[i]


# ---------- drawing helpers (design units = 1080x1920) ----------
def card(c, wd, ht, fill=CARD, r=34, border=None):
    L = Image.new("RGBA", (int(c.S(wd)) + 2, int(c.S(ht)) + 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    d.rounded_rectangle([1, 1, L.width - 2, L.height - 2], radius=int(c.S(r)), fill=fill,
                        outline=border, width=max(1, int(c.S(3))) if border else 0)
    return L


def shadowed(c, L, a=0.45):
    from PIL import ImageFilter
    sh = Image.new("RGBA", (L.width + int(c.S(60)), L.height + int(c.S(60))), (0, 0, 0, 0))
    m = Image.new("RGBA", L.size, (0, 0, 0, int(255 * a))); m.putalpha(L.getchannel("A").point(lambda v: int(v * a)))
    sh.alpha_composite(m, (int(c.S(30)), int(c.S(40))))
    sh = sh.filter(ImageFilter.GaussianBlur(c.S(16)))
    sh.alpha_composite(L, (int(c.S(30)), int(c.S(30))))
    return sh


def put(c, L, x, y, a=1.0, sc=1.0, anchor="mm"):
    """paste a layer at design coords with alpha and scale (scale about the anchor)"""
    if a <= 0.01 or sc <= 0.01:
        return
    if abs(sc - 1) > 0.01:
        L = L.resize((max(1, int(L.width * sc)), max(1, int(L.height * sc))), Image.BICUBIC)
    c.paste(L, c.S(x), c.S(y), clamp(a), anchor)


def env(t, t0, t1, fin=0.28, fout=0.22):
    """entrance/exit envelope: (alpha, pop-scale, slide 0..1)"""
    if t < t0 or t > t1 + fout:
        return 0, 0, 0
    k_in = p(t, t0, fin); k_out = p(t, t1, fout)
    return oc(k_in) * (1 - k_out), lerp(0.6, 1.0, ob(k_in)) * (1 - 0.15 * k_out), 1 - oc(k_in) + k_out


def tick(c, d, cx, cy, r, k, col=GRN):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    if k > 0:
        pts = [(cx - r * .45, cy + r * .02), (cx - r * .1, cy + r * .38), (cx + r * .5, cy - r * .35)]
        seg_k = min(1, k * 2)
        a, b = pts[0], pts[1]; d.line([a, (lerp(a[0], b[0], seg_k), lerp(a[1], b[1], seg_k))], fill=WHITE, width=int(r * .28))
        if k > .5:
            k2 = (k - .5) * 2; a, b = pts[1], pts[2]
            d.line([a, (lerp(a[0], b[0], k2), lerp(a[1], b[1], k2))], fill=WHITE, width=int(r * .28))


def chip(c, label, fill=CARD, col=WHITE, size=44, padx=34, h=92, border=None, fnt="black"):
    T = text(c, label, size, fnt, col)
    L = card(c, T.width / c.s + padx * 2, h, fill, r=h / 2, border=border)
    L.alpha_composite(T, ((L.width - T.width) // 2, (L.height - T.height) // 2 + int(c.S(2))))
    return L


BAND = 1400  # centre of the graphics band: chest, below the mic (~1000) and the captions (~1180)
SFXQ = []    # (t, file, dB) collected while defining scenes


def sfx(t, name, db): SFXQ.append((round(t, 3), name, db))


# ---------- scenes ----------
def s_hook(c, t):
    t0, t1 = seg("hook"); a1 = w("Claude"); a2 = w("studio")
    al, sc, _ = env(t, a1 - 0.1, t1 - 0.1)
    if al:
        put(c, shadowed(c, chip(c, "CLAUDE CODE", (CL[0], CL[1], CL[2], 255), WHITE, 58, h=118)), 540, BAND - 80, al, sc)
    al2, sc2, _ = env(t, a2 - 0.25, t1 - 0.1)
    if al2:
        put(c, text(c, "INTO A", 34, "black", WHITE, track=4, shadow=0.8), 540, BAND + 12, al2)
        put(c, shadowed(c, chip(c, "VIDEO EDITING STUDIO", (Y[0], Y[1], Y[2], 255), INK, 54, h=112)), 540, BAND + 100, al2, sc2)


def s_edited(c, t):
    t0 = w("watching") - 0.3; t1 = seg("was")[1]
    al, sc, _ = env(t, t0, t1)
    if not al:
        return
    L = card(c, 860, 310)
    d = ImageDraw.Draw(L); S = c.S
    T = text(c, "THIS VIDEO", 40, "black", MUTE, track=3); L.alpha_composite(T, (int(S(40)), int(S(26))))
    # timeline tracks with clips + moving playhead
    k = clamp((t - t0) / max(0.1, t1 - t0))
    for r, (yy, cols) in enumerate([(100, [(0, 180, CL), (190, 420, CL), (430, 560, CL), (570, 780, CL)]),
                                    (150, [(60, 300, Y), (330, 520, Y), (560, 760, Y)])]):
        for i, (x0, x1, col) in enumerate(cols):
            kk = oc(clamp(k * 3 - i * 0.25 - r * 0.2))
            if kk > 0:
                d.rounded_rectangle([S(40 + x0), S(yy), S(40 + x0 + (x1 - x0) * kk), S(yy + 36)], radius=int(S(8)),
                                    fill=col + (255,))
    px = S(40 + 780 * oc(k))
    d.rectangle([px - S(2), S(88), px + S(2), S(198)], fill=WHITE)
    ka = p(t, w("edited") - 0.05, 0.3)
    if ka > 0:
        B = chip(c, "EDITED BY CLAUDE CODE", (GRN[0], GRN[1], GRN[2], 255), WHITE, 34, h=64, padx=26)
        L.alpha_composite(B, (int(S(40)), int(S(222))))
    put(c, shadowed(c, L), 540, BAND + 20, al, sc)


def s_notjust(c, t):
    t0 = w("Not") - 0.1; t1 = seg("not")[1]
    al, _, _ = env(t, t0, t1)
    if not al:
        return
    for i, (word, lab, x) in enumerate([("prompts", "PROMPTS", 300), ("ideas", "IDEAS", 780)]):
        ta = w(word) - 0.15
        a, sc, _ = env(t, ta, t1)
        if a:
            L = chip(c, lab, CARD, WHITE, 48, h=104)
            ks = p(t, ta + 0.35, 0.25)
            if ks > 0:
                d = ImageDraw.Draw(L)
                d.line([(c.S(24), L.height / 2), (c.S(24) + (L.width - c.S(48)) * oc(ks), L.height / 2)], fill=RED, width=int(c.S(10)))
            put(c, shadowed(c, L), x, BAND - 90, a, sc)
            if ks > 0 and ks < 0.2:
                pass
    ta = w("production-level") - 0.1
    a, sc, _ = env(t, ta, t1)
    if a:
        L = chip(c, "PRODUCTION-LEVEL SKILLS", (Y[0], Y[1], Y[2], 255), INK, 50, h=116, padx=44)
        d = ImageDraw.Draw(L)
        put(c, shadowed(c, L), 540, BAND + 70, a, sc)


SKILLS = [("podcast", "Podcast\nclips"), ("reels", "Reels &\nShorts"), ("motion", "Motion\ngraphics"),
          ("product", "Product\nexplainers"), ("course", "Course\nvideos"), ("YouTube", "YouTube\nvideos"),
          ("ad", "Ad\ncreatives"), ("thumbnails", "Thumb-\nnails")]


def s_skills(c, t):
    t14 = w("14"); t1 = seg("course")[1] + 0.3
    al, sc, _ = env(t, t14 - 0.1, t1)
    if not al:
        return
    tg = w("podcast") - 0.2
    kg = io(p(t, tg, 0.35))  # counter moves up into a header when the grid starts
    num = str(int(round(14 * oc(p(t, t14 - 0.05, 0.5)))))
    N = text(c, num, lerp(230, 96, kg), "anton", Y)
    Lb = text(c, "SKILLS", lerp(64, 44, kg), "black", WHITE, track=4)
    cy = lerp(BAND - 10, BAND - 250, kg)
    gap = c.S(18); tw = N.width + gap + Lb.width
    put(c, N, 540 - tw / c.s / 2, cy, al, sc, "lm")
    put(c, Lb, 540 - tw / c.s / 2 + (N.width + gap) / c.s, cy + lerp(30, 10, kg), al, 1, "lm")
    if t < tg:
        return
    after = seg("built")[0]
    for i, (word, lab) in enumerate(SKILLS):
        ta = w(word, after=after) - 0.12
        a, sc2, _ = env(t, ta, t1, fin=0.24)
        if not a:
            continue
        col, row = i % 4, i // 4
        x = 147 + col * 262; y = BAND - 100 + row * 186
        L = card(c, 244, 168, (255, 255, 255, 245), r=26)
        d = ImageDraw.Draw(L)
        nT = text(c, f"{i + 1:02d}", 30, "anton", CL); L.alpha_composite(nT, (int(c.S(20)), int(c.S(14))))
        for j, ln in enumerate(lab.split("\n")):
            T = text(c, ln, 34, "black", INK); L.alpha_composite(T, (int(c.S(20)), int(c.S(58 + j * 44))))
        put(c, shadowed(c, L, 0.35), x, y + 30 * (1 - oc(p(t, ta, 0.3))), a, sc2)


def s_again(c, t):
    t0 = w("explaining") - 0.15; t1 = seg("now")[1]
    al, _, _ = env(t, t0, t1)
    if not al:
        return
    times = [t0, w("again") - 0.1, w("again", 2) - 0.1]
    for i, ta in enumerate(times):
        a, sc, _ = env(t, ta, t1, fin=0.2)
        if a:
            L = chip(c, "“Cut it like this… add SFX here…”", CARD, MUTE, 34, h=86, padx=30, fnt="xbold")
            put(c, shadowed(c, L), 540 + (i - 1) * 40, BAND - 70 + i * 64, a, sc)
    kx = p(t, w("again", 2, end=True) - 0.05, 0.25)
    if kx > 0:
        R = chip(c, "AGAIN & AGAIN", (RED[0], RED[1], RED[2], 255), WHITE, 44, h=100)
        put(c, shadowed(c, R), 540, BAND + 140, oc(kx) * al, ob(kx))


def s_give(c, t):
    t0 = w("give") - 0.15; t1 = seg("give")[1] + 0.1
    al, sc, _ = env(t, t0, t1)
    if not al:
        return
    L = card(c, 760, 230, (255, 255, 255, 248))
    d = ImageDraw.Draw(L); S = c.S
    d.rounded_rectangle([S(36), S(58), S(196), S(178)], radius=int(S(16)), fill=Y + (255,))
    d.rounded_rectangle([S(36), S(40), S(110), S(76)], radius=int(S(10)), fill=Y + (255,))
    T = text(c, "video-editing-skills", 46, "black", INK); L.alpha_composite(T, (int(S(226)), int(S(54))))
    k = p(t, w("complete") - 0.05, 0.3)
    if k > 0:
        T2 = text(c, "14 skills · ready to use", 36, "xbold", (90, 90, 100)); L.alpha_composite(wipe(T2, oc(k)), (int(S(226)), int(S(124))))
    put(c, shadowed(c, L), 540, BAND + 10, al, sc)


def s_prompt(c, t):
    t0 = w("say") - 0.2; t1 = seg("say")[1] + 0.15
    al, sc, _ = env(t, t0, t1)
    if not al:
        return
    L = card(c, 900, 230, (14, 14, 18, 245), border=(60, 60, 70))
    d = ImageDraw.Draw(L); S = c.S
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([S(34 + i * 34), S(28), S(56 + i * 34), S(50)], fill=col)
    lab = text(c, "claude", 28, "xbold", (140, 140, 150)); L.alpha_composite(lab, (int(S(150)), int(S(22))))
    msg = "Create this video in this style"
    a, b = w("Create") - 0.05, w("style", end=True)
    n = int(len(msg) * clamp((t - a) / max(0.1, b - a)))
    T = text(c, "> " + msg[:n], 44, "xbold", WHITE)
    L.alpha_composite(T, (int(S(34)), int(S(110))))
    if n < len(msg) or int(t * 3) % 2 == 0:
        d.rectangle([S(34) + T.width + S(6), S(118), S(34) + T.width + S(26), S(166)], fill=Y)
    put(c, shadowed(c, L), 540, BAND + 10, al, sc)


def s_checks(c, t):
    t0 = w("workflow") - 0.15; t1 = seg("and")[1] + 0.1
    al, _, _ = env(t, t0, t1)
    if not al:
        return
    items = [("workflow", "WORKFLOW"), ("structure", "STRUCTURE"), ("editing", "EDITING LOGIC"), ("output", "OUTPUT")]
    for i, (word, lab) in enumerate(items):
        ta = w(word, after=seg("and")[0]) - 0.1
        a, sc, _ = env(t, ta, t1, fin=0.22)
        if not a:
            continue
        col, row = i % 2, i // 2
        L = card(c, 450, 104, CARD, r=52)
        d = ImageDraw.Draw(L)
        tick(c, d, c.S(56), L.height / 2, c.S(30), oc(p(t, ta + 0.1, 0.3)))
        T = text(c, lab, 38, "black", WHITE); L.alpha_composite(T, (int(c.S(104)), (L.height - T.height) // 2 + int(c.S(2))))
        put(c, shadowed(c, L), 300 + col * 480, BAND - 50 + row * 130, a, sc)


def s_github(c, t):
    t0 = w("complete", after=seg("open")[0]) - 0.1; t1 = seg("open")[1] + 0.1
    al, sc, _ = env(t, t0, t1)
    if not al:
        return
    L = card(c, 900, 280, (255, 255, 255, 250))
    d = ImageDraw.Draw(L); S = c.S
    d.ellipse([S(36), S(40), S(136), S(140)], fill=INK)
    g = text(c, "GH", 40, "black", WHITE); L.alpha_composite(g, (int(S(86) - g.width / 2), int(S(90) - g.height / 2)))
    T = text(c, "ukvalley /", 36, "xbold", (100, 100, 110)); L.alpha_composite(T, (int(S(160)), int(S(42))))
    T = text(c, "video-editing-skills", 52, "black", INK); L.alpha_composite(T, (int(S(160)), int(S(84))))
    ko = p(t, w("open", after=seg("open")[0]) - 0.1, 0.3)
    if ko > 0:
        B = chip(c, "OPEN SOURCE · FREE", (GRN[0], GRN[1], GRN[2], 255), WHITE, 34, h=70, padx=26)
        L.alpha_composite(B, (int(S(36)), int(S(178))))
        st = chip(c, "     STAR", (Y[0], Y[1], Y[2], 255), INK, 34, h=70, padx=26)
        ds = ImageDraw.Draw(st); cx, cy, ro, ri = S(46), st.height / 2, S(18), S(7.5)
        ds.polygon([(cx + (ro if k % 2 == 0 else ri) * math.sin(k * math.pi / 5), cy - (ro if k % 2 == 0 else ri) * math.cos(k * math.pi / 5)) for k in range(10)], fill=INK)
        L.alpha_composite(st, (int(S(36) + B.width + S(18)), int(S(178))))
    put(c, shadowed(c, L), 540, BAND + 10, al, sc)


def s_comment(c, t):
    t0 = w("comment") - 0.2; t1 = seg("link")[1]
    al, sc, _ = env(t, t0, t1, fout=0.15)
    if not al:
        return
    L = card(c, 820, 210, (255, 255, 255, 250), r=44)
    d = ImageDraw.Draw(L); S = c.S
    d.polygon([(S(110), L.height - S(4)), (S(170), L.height - S(4)), (S(90), L.height + S(40))], fill=(255, 255, 255, 250))
    T = text(c, "Comment", 40, "xbold", (110, 110, 120)); L.alpha_composite(T, (int(S(44)), int(S(30))))
    kv = p(t, w("VIDEO") - 0.05, 0.25)
    if kv > 0:
        V = text(c, "“VIDEO”", 92, "black", INK)
        V = V.resize((int(V.width * ob(kv)), int(V.height * ob(kv))))
        L.alpha_composite(V, (int(S(44)), int(S(80))))
    put(c, shadowed(c, L), 540, BAND - 50, al, sc)
    kl = p(t, w("link") - 0.15, 0.3)
    if kl > 0:
        B = chip(c, "GET THE GITHUB LINK →", (Y[0], Y[1], Y[2], 255), INK, 42, h=100)
        put(c, shadowed(c, B), 540, BAND + 130, oc(kl) * al, ob(kl))


def s_end(c, t):
    t0 = seg("tail")[0] - 0.1
    k = oc(p(t, t0, 0.35))
    if k <= 0:
        return
    # lower panel end card
    pan = Image.new("RGBA", (int(c.S(1080)), int(c.S(900))), (12, 12, 16, int(235 * k)))
    c.paste(pan, 0, c.S(1020), 1, "lt")
    put(c, text(c, "COMMENT", 70, "black", WHITE, track=4), 540, 1150 + 40 * (1 - k), k)
    V = chip(c, "“VIDEO”", (Y[0], Y[1], Y[2], 255), INK, 110, h=180, padx=50)
    kv = p(t, t0 + 0.15, 0.35)
    put(c, V, 540, 1300, oc(kv), ob(kv))
    put(c, text(c, "github.com/ukvalley/video-editing-skills", 36, "xbold", MUTE), 540, 1450, oc(p(t, t0 + 0.35, 0.3)))
    put(c, text(c, "14 FREE CLAUDE CODE SKILLS", 40, "black", CL, track=3), 540, 1520, oc(p(t, t0 + 0.45, 0.3)))


SCENES = [s_hook, s_edited, s_notjust, s_skills, s_again, s_give, s_prompt, s_checks, s_github, s_comment, s_end]

# section punches (frame zoom pulse + whoosh/impact) and the CTA flash
PUNCH = [seg("built")[0], seg("now")[0], seg("open")[0], seg("comm")[0]]
FLASH = [seg("tail")[0]]


def build_sfx():
    SFXQ.clear()
    sfx(w("Claude") - 0.12, "pop", -4); sfx(w("studio") - 0.25, "whoosh_fast", -4); sfx(w("studio"), "impact", -6)
    sfx(w("watching") - 0.3, "swish", -6); sfx(w("edited"), "success", -6)
    sfx(w("prompts") - 0.15, "pop", -5); sfx(w("prompts") + 0.2, "buzz", -12)
    sfx(w("ideas") - 0.15, "pop", -5); sfx(w("ideas") + 0.2, "buzz", -12)
    sfx(w("production-level") - 0.1, "ding", -5)
    for tp in PUNCH:
        sfx(tp - 0.12, "whoosh", -3); sfx(tp, "sub_drop", -6)
    sfx(w("14"), "impact", -4)
    for k in range(6):
        sfx(w("14") + k * 0.07, "tick", -12)
    after = seg("built")[0]
    for word, _ in SKILLS:
        sfx(w(word, after=after) - 0.12, "pop", -5)
    sfx(w("explaining") - 0.15, "swish", -7); sfx(w("again") - 0.1, "swish", -7); sfx(w("again", 2) - 0.1, "swish", -7)
    sfx(w("again", 2, end=True), "glitch", -7)
    sfx(w("give") - 0.15, "whoosh_fast", -5); sfx(w("complete", after=seg("give")[0]), "ding", -6)
    sfx(w("say") - 0.2, "swipe_up", -6); sfx(w("Create") - 0.05, "typing", -9)
    for word in ["workflow", "structure", "editing", "output"]:
        sfx(w(word, after=seg("and")[0]), "ui_click", -4)
    sfx(w("repository") - 0.2, "pop", -5); sfx(w("open", after=seg("open")[0]), "success", -5)
    sfx(w("comment") - 0.2, "notification", -4); sfx(w("VIDEO"), "impact", -5)
    sfx(w("link") - 0.15, "swish", -6)
    sfx(FLASH[0], "boom_hit", -4); sfx(FLASH[0] + 0.15, "reverse_swell", -10)


def frame_fx(base, t, scale):
    """section zoom-punch pulse + white flash on the end card"""
    for tp in PUNCH:
        if tp - 0.02 <= t < tp + 0.3:
            k = (t - tp) / 0.3; z = 1 + 0.07 * (1 - oc(clamp(k)))
            wd, ht = base.size; nw, nh = int(wd / z), int(ht / z)
            base = base.crop(((wd - nw) // 2, (ht - nh) // 2, (wd - nw) // 2 + nw, (ht - nh) // 2 + nh)).resize((wd, ht), Image.BICUBIC)
    for tf in FLASH:
        if tf <= t < tf + 0.24:
            a = 1 - (t - tf) / 0.24
            base = Image.blend(base, Image.new("RGB", base.size, (255, 255, 255)), 0.85 * a)
    return base


def captions(scale):
    g0, g1 = w("podcast") - 0.2, seg("course")[1] + 0.3
    words = [x for x in WORDS if not (g0 <= x["start"] < g1)]
    json.dump({"words": words}, open(f"{P}/work/words_out.json", "w"), indent=1)
    subprocess.run(["python3", os.path.expanduser("~/.claude/skills/video-editor-pro/scripts/captions_ass.py"),
                    f"{P}/work/words_out.json", f"{P}/edit/captions.ass", "--style", "karaoke", "--font", "Montserrat Black",
                    "--size", "84", "--words-per-line", "3", "--position", "0.615", "--uppercase", "--playres", "1080x1920",
                    "--highlight", "&H0000C7FF"], check=True)


def render(scale, out):
    Wd, Hd = int(W0 * scale) // 2 * 2, int(H0 * scale) // 2 * 2
    captions(scale)
    fonts = f"{STUDIO}/assets/fonts"
    dec = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", f"{P}/work/base.mov", "-vf",
                            f"{GRADE},scale={Wd}:{Hd}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{Wd}x{Hd}",
                            "-r", str(FPS), "-i", "-", "-vf", f"ass={P}/edit/captions.ass:fontsdir={fonts}",
                            "-c:v", "libx264", "-crf", "16" if scale == 1 else "20", "-preset", "medium", "-pix_fmt", "yuv420p",
                            f"{P}/work/video_{Wd}.mp4"], stdin=subprocess.PIPE)
    n = int(round(TOTAL * FPS)); fb = Wd * Hd * 3
    for i in range(n):
        buf = dec.stdout.read(fb)
        if len(buf) < fb:
            break
        t = i / FPS
        base = frame_fx(Image.frombuffer("RGB", (Wd, Hd), buf), t, scale)
        c = Ctx(Wd, Hd, t, scale)
        for s in SCENES:
            s(c, t)
        base = base.convert("RGBA"); base.alpha_composite(c.im)
        enc.stdin.write(base.convert("RGB").tobytes())
        if i % 50 == 0:
            print(f"\r{t:.0f}/{TOTAL:.0f}s", end="", flush=True)
    enc.stdin.close(); enc.wait(); dec.wait()
    mix(f"{P}/work/video_{Wd}.mp4", out)
    print(f"\nwrote {out}")


def mix(video, out):
    build_sfx()
    music = f"{STUDIO}/assets/music/tech_underscore_105bpm_170s.wav"
    ins = ["-i", video, "-i", f"{P}/work/base.mov", "-i", music]
    flt = ["[1:a]highpass=f=90,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3000:t=q:w=1:g=4,equalizer=f=6500:t=q:w=1:g=1.5,"
           "acompressor=threshold=-26dB:ratio=4:attack=8:release=120:makeup=6,alimiter=limit=0.9,asplit=2[voice][sc]",
           f"[2:a]atrim=0:{TOTAL:.2f},volume=-19dB,afade=t=in:d=0.5,afade=t=out:st={TOTAL - 1.2:.2f}:d=1.2[mus]",
           "[mus][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[ducked]"]
    labels = []
    for j, (t, name, db) in enumerate(sorted(SFXQ)):
        ins += ["-i", f"{SFX}/{name}.wav"]
        idx = 3 + j
        flt.append(f"[{idx}:a]aformat=channel_layouts=stereo,volume={db + 6}dB,adelay={int(max(0, t) * 1000)}|{int(max(0, t) * 1000)}[s{j}]")
        labels.append(f"[s{j}]")
    flt.append(f"[voice][ducked]{''.join(labels)}amix=inputs={2 + len(labels)}:normalize=0:duration=first[a]")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *ins, "-filter_complex", ";".join(flt),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "pcm_s24le", "-t", f"{TOTAL:.3f}", out], check=True)


def stills(ts):
    os.makedirs(f"{P}/work/stills", exist_ok=True)
    for t in ts:
        i = int(t * FPS)
        raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", f"{P}/work/base.mov", "-frames:v", "1",
                              "-vf", GRADE, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        base = frame_fx(Image.frombuffer("RGB", (W0, H0), raw), t, 1.0)
        c = Ctx(W0, H0, t, 1.0)
        for s in SCENES:
            s(c, t)
        base = base.convert("RGBA"); base.alpha_composite(c.im)
        base.convert("RGB").save(f"{P}/work/stills/t{t:05.2f}.jpg", quality=90)
    print("stills ->", f"{P}/work/stills")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true"); ap.add_argument("--stills")
    a = ap.parse_args()
    if a.stills:
        stills([float(x) for x in a.stills.split(",")])
    else:
        render(0.5 if a.preview else 1.0, f"{P}/work/mix_{540 if a.preview else 1080}.mov")
