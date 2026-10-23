#!/usr/bin/env python3
"""Render a JSON edit decision list (see references/edl-format.md) into a finished video with ffmpeg.

Usage:
  python3 edl_render.py edit.json [--preview] [--dry-run] [--verbose] [--hw] [--no-cache] [--out path]

Pipeline: per-clip conformed intermediates (trim/speed/fit/zoom/filters/freeze/boundary FX + clip audio)
          -> join with concat / xfade + acrossfade (exact offsets measured from intermediates)
          -> overlays (look, LUT, images, lower-thirds, text, progress bar, captions, grain, vignette, letterbox)
          -> audio mix (timeline + voiceover + ducked music + SFX) -> loudnorm + limiter -> encode.
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys

from _common import (media_info, require, find_font, escape_drawtext, escape_path, hex_to_ffcolor,
                     LOUDNESS_TARGETS, sh_quote, is_mac)

LOOKS = {
    "teal_orange": "colorbalance=rs=-0.06:gs=0.02:bs=0.12:rh=0.10:gh=0.03:bh=-0.10,eq=saturation=1.05",
    "clean": "curves=master='0/0 0.5/0.52 1/1',eq=saturation=1.05:contrast=1.05",
    "moody": "eq=saturation=0.8,curves=master='0/0.03 0.3/0.25 1/0.97',colorbalance=bs=0.08",
    "warm_film": "eq=contrast=0.95:saturation=0.9,curves=r='0/0.02 1/0.98':b='0/0.05 1/0.93',colorbalance=rm=0.04:bm=-0.04",
    "bleach": "eq=saturation=0.4:contrast=1.3",
    "bright_social": "eq=brightness=0.04:contrast=1.02:saturation=1.15,curves=master='0/0.02 0.5/0.56 1/1'",
    "bw": "colorchannelmixer=.4:.4:.2:0:.4:.4:.2:0:.4:.4:.2,eq=contrast=1.15",
    "neon": "colorbalance=rs=-0.10:bs=0.20:rh=0.10:gh=-0.10:bh=0.10,eq=saturation=1.3,vibrance=intensity=0.3",
}

# transition name -> (xfade name, default duration, head_fx, tail_fx, sfx category)
TRANSITIONS = {
    "whip_left": ("slideleft", 0.3, "whip", "whip", "whoosh"),
    "whip_right": ("slideright", 0.3, "whip", "whip", "whoosh"),
    "whip_up": ("slideup", 0.3, "whip", "whip", "whoosh"),
    "whip_down": ("slidedown", 0.3, "whip", "whip", "whoosh"),
    "zoom_punch": ("fade", 0.12, "zoom_in", "zoom_out", "impact"),
    "flash": ("fadewhite", 0.16, None, None, "flash"),
    "flash_warm": ("fadewhite", 0.2, "warm", "warm", "flash"),
    "glitch": ("fade", 0.1, "glitch", "glitch", "glitch"),
    "film_burn": ("fadeblack", 0.3, "burn", "burn", None),
    "speed_ramp": ("hblur", 0.25, "mblur", "mblur", "whoosh"),
    "blur_dissolve": ("fade", 0.5, "gblur_in", "gblur", None),
    "match_dissolve": ("fade", 0.08, None, None, None),
}


def log(msg):
    print(msg, file=sys.stderr)


class Renderer:
    def __init__(self, edl, edl_path, preview=False, dry=False, verbose=False, hw=False, no_cache=False, out=None):
        self.edl = edl
        self.base = os.path.dirname(os.path.abspath(edl_path))
        self.preview, self.dry, self.verbose, self.hw, self.no_cache = preview, dry, verbose, hw, no_cache
        o = edl.get("output", {})
        self.W, self.H, self.fps = int(o.get("width", 1920)), int(o.get("height", 1080)), float(o.get("fps", 30))
        if preview:
            self.W, self.H = (self.W // 2) & ~1, (self.H // 2) & ~1
        self.crf = int(o.get("crf", 18))
        self.bitrate = o.get("bitrate")
        self.loud = o.get("loudness", "youtube")
        self.out_path = out or self.p(o.get("path", "out/final.mp4"))
        if preview and not out:
            r, e = os.path.splitext(self.out_path)
            self.out_path = r + "_preview" + e
        self.work = self.p(edl.get("work_dir", "work"))
        os.makedirs(self.work, exist_ok=True)
        os.makedirs(os.path.dirname(self.out_path) or ".", exist_ok=True)
        self.font = find_font(self.p(edl["font"]) if edl.get("font") else None)
        self.brand = edl.get("brand_color", "#FF6A00")
        self.auto_sfx_events = []  # (category, timeline_time)
        self.transition_times = []

    # ---------- helpers ----------
    def p(self, path):
        if path is None:
            return None
        path = os.path.expanduser(str(path))
        return path if os.path.isabs(path) else os.path.join(self.base, path)

    def run(self, cmd):
        if self.verbose or self.dry:
            log("+ " + " ".join(sh_quote(c) for c in cmd))
        if self.dry:
            return
        p = subprocess.run(cmd, text=True, stderr=subprocess.PIPE)
        if p.returncode != 0:
            lines = [l for l in p.stderr.strip().splitlines() if "Failed to set value" not in l]
            log("ffmpeg failed:")
            log("\n".join(lines[-12:]))
            if self.verbose:
                log("command: " + " ".join(sh_quote(c) for c in cmd))
            else:
                log("(re-run with --verbose to see the full command)")
            sys.exit(1)

    def venc(self, intermediate=False):
        if self.preview:
            if self.hw and is_mac():
                return ["-c:v", "h264_videotoolbox", "-b:v", "6M"]
            return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"]
        if intermediate:
            return ["-c:v", "libx264", "-preset", "fast", "-crf", "14"]
        enc = ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high"]
        enc += ["-b:v", str(self.bitrate)] if self.bitrate else ["-crf", str(self.crf)]
        return enc

    @staticmethod
    def atempo_chain(speed):
        if abs(speed - 1.0) < 1e-6:
            return []
        parts = []
        s = speed
        while s > 2.0:
            parts.append("atempo=2.0")
            s /= 2.0
        while s < 0.5:
            parts.append("atempo=0.5")
            s /= 0.5
        parts.append(f"atempo={s:.5f}")
        return parts

    def fit_chain(self, fit, focus):
        W, H = self.W, self.H
        if fit == "stretch":
            return [f"scale={W}:{H}"]
        if fit == "contain":
            return [f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos",
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
        x = {"left": "0", "right": "iw-ow", "center": "(iw-ow)/2", "top": "(iw-ow)/2", "bottom": "(iw-ow)/2"}.get(focus, "(iw-ow)/2")
        y = {"top": "0", "bottom": "ih-oh", "center": "(ih-oh)/2", "left": "(ih-oh)/2", "right": "(ih-oh)/2"}.get(focus, "(ih-oh)/2")
        return [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}:{x}:{y}"]

    @staticmethod
    def stepped(template, t0, d, steps, v0, v1):
        """Blur-type filters don't accept time expressions, so ramp them in `steps` enable-windows.
        template uses {v} for the value."""
        out = []
        for k in range(steps):
            a = t0 + d * k / steps
            b = t0 + d * (k + 1) / steps
            v = v0 + (v1 - v0) * (k + 1) / steps
            out.append(template.format(v=round(v, 2)) + f":enable='between(t,{a:.4f},{b:.4f})'")
        return out

    def boundary_fx(self, kind, t0, d):
        """Video filter(s) active between t0 and t0+d implementing a boundary effect."""
        W, H = self.W, self.H
        en = f"enable='between(t,{t0:.4f},{t0 + d:.4f})'"
        p = f"clip((t-{t0:.4f})/{d:.4f},0,1)"
        steps = max(3, int(d * self.fps / 2))
        if kind == "whip":      # blur ramps up to the cut
            return self.stepped("boxblur=luma_radius={v}:luma_power=1", t0, d, steps, 0, 40)
        if kind == "whip_in":   # blur ramps down from the cut
            return self.stepped("boxblur=luma_radius={v}:luma_power=1", t0, d, steps, 40, 0)
        if kind == "zoom_out":   # end of outgoing clip: zoom in fast
            return [f"scale='iw*(1+0.6*pow({p},2))':'ih*(1+0.6*pow({p},2))':eval=frame", f"crop={W}:{H}"]
        if kind == "zoom_in":    # start of incoming clip: settle from zoomed
            return [f"scale='iw*(1+0.6*pow(1-{p},2))':'ih*(1+0.6*pow(1-{p},2))':eval=frame", f"crop={W}:{H}"]
        if kind == "warm":
            return [f"colorbalance=rh=0.3:gh=0.1:bh=-0.2:{en}", f"eq=brightness=0.08:{en}"]
        if kind == "glitch":
            fx = [f"noise=alls=40:allf=t+u:{en}", f"hue=h='40*sin(t*70)':{en}"]
            n = max(3, int(d * self.fps))
            for k in range(n):   # RGB split jitter, alternating direction each frame
                a, b = t0 + d * k / n, t0 + d * (k + 1) / n
                s = 10 if k % 2 == 0 else -6
                fx.append(f"rgbashift=rh={s}:bh={-s}:enable='between(t,{a:.4f},{b:.4f})'")
            return fx
        if kind == "burn":
            return [f"noise=alls=45:allf=t+u:{en}", f"eq=brightness='0.25*{p}':saturation=0.7:{en}"]
        if kind == "mblur":
            return [f"tblend=all_mode=average:{en}", f"tblend=all_mode=average:{en}"]
        if kind == "gblur":
            return self.stepped("gblur=sigma={v}", t0, d, steps, 0, 24)
        if kind == "gblur_in":
            return self.stepped("gblur=sigma={v}", t0, d, steps, 24, 0)
        return []

    # ---------- stage 1: intermediates ----------
    def clip_duration(self, c, src_dur):
        i = float(c.get("in", 0))
        o = float(c["out"]) if c.get("out") is not None else src_dur
        raw = max(0.0, o - i)
        sp = c.get("speed", 1.0)
        if isinstance(sp, (int, float)):
            d = raw / float(sp)
        else:
            kf = sorted([[float(a), float(b)] for a, b in sp])
            d = 0.0
            times = [k[0] for k in kf] + [raw]
            for j, (t, s) in enumerate(kf):
                seg = max(0.0, min(raw, times[j + 1]) - t)
                d += seg / float(s)
            if kf and kf[0][0] > 0:
                d += kf[0][0]  # before first keyframe: speed 1
        if c.get("freeze"):
            d += float(c["freeze"].get("duration", 1.0))
        return d, raw

    def render_clip(self, idx, c, prev_tr, next_tr):
        src = self.p(c["src"])
        if not os.path.exists(src) and not self.dry:
            sys.exit(f"clip {idx}: source not found: {src}")
        info = media_info(src) if (os.path.exists(src)) else {"duration": 10.0, "has_audio": True, "fps": 30}
        D, raw = self.clip_duration(c, info["duration"])
        key = hashlib.md5(json.dumps([c, prev_tr, next_tr, self.W, self.H, self.fps, self.preview], sort_keys=True).encode()).hexdigest()[:10]
        out = os.path.join(self.work, f"clip_{idx:03d}_{key}.mp4")
        if os.path.exists(out) and not self.no_cache and not self.dry:
            try:
                return out, media_info(out)["duration"]
            except Exception:
                os.remove(out)  # broken leftover from an interrupted render
        i_t = float(c.get("in", 0))
        o_t = float(c["out"]) if c.get("out") is not None else None
        fps = self.fps
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y", "-i", src]
        if not info["has_audio"]:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            a_in = "1:a"
        else:
            a_in = "0:a"
        fc = []
        # --- video base: trim + speed
        sp = c.get("speed", 1.0)
        aoff = float(c.get("audio_offset", 0.0))
        vtrim = f"trim=start={i_t:.4f}" + (f":end={o_t:.4f}" if o_t is not None else "") + ",setpts=PTS-STARTPTS"
        ai_t, ao_t = max(0.0, i_t + aoff), (o_t + aoff) if o_t is not None else None
        atrim = f"atrim=start={ai_t:.4f}" + (f":end={ao_t:.4f}" if ao_t is not None else "") + ",asetpts=PTS-STARTPTS"
        if isinstance(sp, (int, float)):
            sp = float(sp)
            vchain = [vtrim] + ([f"setpts=PTS/{sp:.5f}"] if abs(sp - 1) > 1e-6 else [])
            achain = [atrim] + self.atempo_chain(sp)
            fc.append("[0:v]" + ",".join(vchain) + "[vbase]")
            fc.append(f"[{a_in}]" + ",".join(achain) + "[abase]")
        else:
            kf = sorted([[float(a), float(b)] for a, b in sp])
            if not kf or kf[0][0] > 0:
                kf = [[0.0, 1.0]] + kf
            fc.append("[0:v]" + vtrim + f",split={len(kf)}" + "".join(f"[vs{j}]" for j in range(len(kf))))
            fc.append(f"[{a_in}]" + atrim + f",asplit={len(kf)}" + "".join(f"[as{j}]" for j in range(len(kf))))
            labels = ""
            for j, (t, s) in enumerate(kf):
                end = kf[j + 1][0] if j + 1 < len(kf) else None
                seg = f"trim=start={t:.4f}" + (f":end={end:.4f}" if end else "") + f",setpts=(PTS-STARTPTS)/{s:.5f}"
                blur = ",tblend=all_mode=average" if s > 2.0 else ""
                fc.append(f"[vs{j}]{seg}{blur}[vseg{j}]")
                aseg = f"atrim=start={t:.4f}" + (f":end={end:.4f}" if end else "") + ",asetpts=PTS-STARTPTS"
                fc.append(f"[as{j}]" + ",".join([aseg] + self.atempo_chain(s)) + f"[aseg{j}]")
                labels += f"[vseg{j}][aseg{j}]"
            fc.append(labels + f"concat=n={len(kf)}:v=1:a=1[vbase][abase]")
        # --- fit, zoom, filters, conform
        chain = [f"fps={fps}"] + self.fit_chain(c.get("fit", "cover"), c.get("crop_focus", "center"))
        if c.get("zoom"):
            z0, z1 = [float(z) for z in c["zoom"]]
            chain += [f"scale='iw*({z0}+({z1}-{z0})*clip(t/{max(D, 0.01):.4f},0,1))':'ih*({z0}+({z1}-{z0})*clip(t/{max(D, 0.01):.4f},0,1))':eval=frame",
                      f"crop={self.W}:{self.H}"]
        if c.get("filters"):
            chain.append(c["filters"])
        # boundary effects
        if prev_tr:
            name, (xf, dd, head, tail, _) = prev_tr
            d_in = float(dd)
            if head == "whip":
                chain += self.boundary_fx("whip_in", 0.0, d_in)
            elif head:
                chain += self.boundary_fx(head, 0.0, d_in)
        if next_tr:
            name, (xf, dd, head, tail, _) = next_tr
            d_out = float(dd)
            if tail:
                chain += self.boundary_fx(tail, max(0.0, D - d_out), d_out)
        chain += ["format=yuv420p", "setsar=1"]
        vlabel = "vbase"
        alabel = "abase"
        if c.get("freeze"):
            fa = float(c["freeze"].get("at", 0.0))
            fd = float(c["freeze"].get("duration", 1.0))
            n = int(round(fd * fps))
            fc.append(f"[vbase]split=3[fa][ff][fb]")
            fc.append(f"[fa]trim=end={fa:.4f},setpts=PTS-STARTPTS[fa2]")
            fc.append(f"[ff]trim=start={fa:.4f}:end={fa + 1.5 / fps:.4f},setpts=PTS-STARTPTS,loop=loop={n}:size=1:start=0,setpts=N/{fps}/TB,trim=end={fd:.4f}[ff2]")
            fc.append(f"[fb]trim=start={fa:.4f},setpts=PTS-STARTPTS[fb2]")
            fc.append("[fa2][ff2][fb2]concat=n=3:v=1:a=0[vfrz]")
            fc.append(f"[abase]asplit=2[aa][ab]")
            fc.append(f"[aa]atrim=end={fa:.4f},asetpts=PTS-STARTPTS[aa2]")
            fc.append(f"[ab]atrim=start={fa:.4f},asetpts=PTS-STARTPTS[ab2]")
            cmd += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={fd:.4f}"]
            sil = f"{len(cmd) // 2 - 1}:a"  # index of the last -i
            sil = f"{cmd.count('-i') - 1}:a"
            fc.append(f"[{sil}]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[asil]")
            fc.append("[aa2][asil][ab2]concat=n=3:v=0:a=1[afrz]")
            vlabel, alabel = "vfrz", "afrz"
        fc.append(f"[{vlabel}]" + ",".join(chain) + "[vout]")
        # --- audio polish
        vol = -120.0 if c.get("mute") else float(c.get("volume_db", 0.0))
        achain = ["aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo", f"volume={vol}dB",
                  "afade=t=in:d=0.01", f"afade=t=out:st={max(0.0, D - 0.012):.4f}:d=0.012", f"apad=whole_dur={D:.4f}", f"atrim=end={D:.4f}"]
        fc.append(f"[{alabel}]" + ",".join(achain) + "[aout]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-shortest"]
        tmp = out + ".part.mp4"
        cmd += self.venc(intermediate=True) + ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", tmp]
        log(f"clip {idx}: {os.path.basename(src)} [{i_t:.2f}-{o_t if o_t is not None else 'end'}] -> {D:.2f}s"
            + (f" (in: {prev_tr[0]})" if prev_tr else ""))
        self.run(cmd)
        if not self.dry:
            os.replace(tmp, out)
            D = media_info(out)["duration"]
        return out, D

    def resolve_transition(self, c):
        name = c.get("transition", "cut")
        if not name or name == "cut":
            return None
        if name in TRANSITIONS:
            xf, dd, head, tail, sfx = TRANSITIONS[name]
        else:
            xf, dd, head, tail, sfx = name, 0.5, None, None, None
        dd = float(c.get("transition_duration", dd))
        return (name, (xf, dd, head, tail, sfx))

    # ---------- stage 2+3+4: join, overlays, audio ----------
    def render(self):
        clips = self.edl.get("clips", [])
        if not clips:
            sys.exit("EDL has no clips")
        trs = [self.resolve_transition(c) for c in clips]
        files, durs = [], []
        for i, c in enumerate(clips):
            prev_tr = trs[i] if i > 0 else None
            next_tr = trs[i + 1] if i + 1 < len(clips) else None
            f, d = self.render_clip(i, c, prev_tr, next_tr)
            files.append(f)
            durs.append(d)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-stats", "-y"]
        for f in files:
            cmd += ["-i", f]
        n_in = len(files)
        fc = []
        for i in range(n_in):
            fc.append(f"[{i}:v]settb=AVTB,fps={self.fps}[v{i}]")
            fc.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a{i}]")
        cur_v, cur_a, cur_d = "v0", "a0", durs[0]
        for i in range(1, n_in):
            tr = trs[i]
            if tr is None:
                fc.append(f"[{cur_v}][v{i}]concat=n=2:v=1:a=0,settb=AVTB,fps={self.fps}[vj{i}]")  # re-stamp rate: ffmpeg>=8 xfade rejects concat output
                fc.append(f"[{cur_a}][a{i}]concat=n=2:v=0:a=1[aj{i}]")
                self.transition_times.append(("cut", cur_d, None))
                cur_d += durs[i]
            else:
                name, (xf, dd, head, tail, sfx) = tr
                dd = min(dd, cur_d * 0.9, durs[i] * 0.9)
                off = max(0.0, cur_d - dd)
                fc.append(f"[{cur_v}][v{i}]xfade=transition={xf}:duration={dd:.4f}:offset={off:.4f},settb=AVTB,fps={self.fps}[vj{i}]")
                fc.append(f"[{cur_a}][a{i}]acrossfade=d={dd:.4f}:c1=tri:c2=tri[aj{i}]")
                self.transition_times.append((name, off, sfx))
                if sfx:
                    self.auto_sfx_events.append((sfx, off + (0.0 if sfx == "impact" else -0.12), name))
                cur_d += durs[i] - dd
            cur_v, cur_a = f"vj{i}", f"aj{i}"
        T = cur_d
        self.timeline_duration = T
        # ---- overlays
        v = cur_v
        vf = []
        look = self.edl.get("look", "")
        if look:
            vf.append(LOOKS.get(look, look))
        lut = self.edl.get("lut")
        if lut and lut.get("file"):
            strength = float(lut.get("strength", 1.0))
            lp = escape_path(self.p(lut["file"]))
            if strength >= 0.999:
                vf.append(f"lut3d=file='{lp}':interp=tetrahedral")
            else:
                fc.append(f"[{v}]" + (",".join(vf) if vf else "null") + "[vl0]")
                fc.append(f"[vl0]split[vla][vlb]")
                fc.append(f"[vlb]lut3d=file='{lp}':interp=tetrahedral[vlc]")
                fc.append(f"[vla][vlc]blend=all_mode=normal:all_opacity={strength}[vl1]")
                v, vf = "vl1", []
        # images
        for k, im in enumerate(self.edl.get("images", []) or []):
            path = self.p(im["file"])
            cmd += ["-loop", "1", "-i", path]
            idx = n_in + k
            at = float(im.get("at", 0.0))
            dur = float(im.get("duration", 0) or 0)
            end = at + dur if dur > 0 else T
            w = int(self.W * float(im.get("scale", 0.12)))
            op = float(im.get("opacity", 1.0))
            anim = im.get("anim", "fade")
            fi = 0.3 if anim == "fade" else 0.0
            fades = f",fade=t=in:st={at:.3f}:d={fi}:alpha=1,fade=t=out:st={max(at, end - fi):.3f}:d={fi}:alpha=1" if fi else ""
            fc.append(f"[{idx}:v]scale={w}:-1,format=rgba,colorchannelmixer=aa={op}{fades}[img{k}]")
            if vf:
                fc.append(f"[{v}]" + ",".join(vf) + f"[vi{k}]")
                v, vf = f"vi{k}", []
            x, y = im.get("x", "W-w-40"), im.get("y", "40")
            fc.append(f"[{v}][img{k}]overlay=x={x}:y={y}:enable='between(t,{at:.3f},{end:.3f})':eval=frame[vo{k}]")
            v = f"vo{k}"
        n_in += len(self.edl.get("images", []) or [])
        # lower thirds
        for lt in self.edl.get("lower_thirds", []) or []:
            vf += self.lower_third(lt)
        # text
        for tx in self.edl.get("text", []) or []:
            vf += self.text_filters(tx)
        pb = self.edl.get("progress_bar")
        if pb:
            h = int(pb.get("height", 8))
            y = "0" if pb.get("position") == "top" else f"ih-{h}"
            vf.append(f"drawbox=x=0:y={y}:w='iw*t/{T:.4f}':h={h}:color={hex_to_ffcolor(self.brand, 0.95)}:t=fill")
        caps = self.edl.get("captions")
        if caps:
            cp = escape_path(self.p(caps))
            vf.append(f"ass='{cp}'" if caps.lower().endswith(".ass") else f"subtitles='{cp}'")
        g = int(self.edl.get("grain", 0) or 0)
        if g:
            vf.append(f"noise=alls={g}:allf=t+u")
        vg = float(self.edl.get("vignette", 0) or 0)
        if vg:
            vf.append(f"vignette=angle={0.2 + 0.6 * vg:.3f}")
        lb = self.edl.get("letterbox")
        if lb:
            r = float(lb)
            bar = int((self.H - self.W / r) / 2)
            if bar > 0:
                vf += [f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill", f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill"]
        vf += ["format=yuv420p"]
        fc.append(f"[{v}]" + ",".join(vf) + "[vfinal]")
        # ---- audio
        a_layers = [cur_a]
        key_sources = [cur_a]
        vo = self.edl.get("voiceover")
        if vo and vo.get("file"):
            cmd += ["-i", self.p(vo["file"])]
            idx = n_in
            n_in += 1
            ch = ["aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"]
            if vo.get("clean", True):
                ch += ["highpass=f=80", "afftdn=nf=-25", "acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=3"]
            ch += [f"volume={float(vo.get('gain_db', 0)):.2f}dB", f"adelay={int(float(vo.get('at', 0)) * 1000)}|{int(float(vo.get('at', 0)) * 1000)}", f"apad=whole_dur={T:.4f}", f"atrim=end={T:.4f}"]
            fc.append(f"[{idx}:a]" + ",".join(ch) + ",asplit=2[avo][avokey]")
            a_layers.append("avo")
            key_sources = ["avokey"]
            fc.append(f"[{cur_a}]anull[atl]")
            a_layers[0] = "atl"
        music = self.edl.get("music")
        if music and music.get("file"):
            cmd += ["-ss", str(float(music.get("start", 0.0))), "-i", self.p(music["file"])]
            idx = n_in
            n_in += 1
            ch = ["aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo", f"volume={float(music.get('gain_db', -10)):.2f}dB"]
            fi, fo = float(music.get("fade_in", 0) or 0), float(music.get("fade_out", 1.0) or 0)
            if fi:
                ch.append(f"afade=t=in:d={fi:.3f}")
            ch += [f"apad=whole_dur={T:.4f}", f"atrim=end={T:.4f}"]
            if fo:
                ch.append(f"afade=t=out:st={max(0.0, T - fo):.3f}:d={fo:.3f}")
            fc.append(f"[{idx}:a]" + ",".join(ch) + "[amus0]")
            if music.get("duck", True):
                depth = float(music.get("duck_amount", 14))
                ratio = max(2.0, min(20.0, depth / 1.2))
                if len(key_sources) == 1 and key_sources[0] == cur_a:
                    fc.append(f"[{cur_a}]asplit=2[atl][akey]")
                    a_layers[0] = "atl"
                    key = "akey"
                else:
                    key = key_sources[0]
                fc.append(f"[amus0][{key}]sidechaincompress=threshold=0.02:ratio={ratio:.1f}:attack=20:release=450:makeup=1:level_sc=1[amus]")
            else:
                fc.append("[amus0]anull[amus]")
            a_layers.append("amus")
        sfx_list = list(self.edl.get("sfx", []) or [])
        auto = self.edl.get("auto_sfx") or {}
        for cat, at, name in self.auto_sfx_events:
            if auto.get(cat):
                sfx_list.append({"file": auto[cat], "at": max(0.0, at), "gain_db": {"whoosh": -6, "impact": -3, "flash": -10, "glitch": -8}.get(cat, -6),
                                 "pan": -0.5 if name.endswith("left") else 0.5 if name.endswith("right") else 0})
        for k, s in enumerate(sfx_list):
            cmd += ["-i", self.p(s["file"])]
            idx = n_in
            n_in += 1
            ms = int(float(s.get("at", 0)) * 1000)
            pan = float(s.get("pan", 0) or 0)
            L, R = min(1.0, 1 - pan), min(1.0, 1 + pan)
            ch = ["aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo", f"volume={float(s.get('gain_db', -6)):.2f}dB",
                  f"pan=stereo|c0={L:.3f}*c0|c1={R:.3f}*c1", f"adelay={ms}|{ms}", f"apad=whole_dur={T:.4f}", f"atrim=end={T:.4f}"]
            fc.append(f"[{idx}:a]" + ",".join(ch) + f"[asfx{k}]")
            a_layers.append(f"asfx{k}")
        mix = "".join(f"[{l}]" for l in a_layers) + (f"amix=inputs={len(a_layers)}:duration=first:dropout_transition=0:normalize=0" if len(a_layers) > 1 else "anull")
        post = []
        if self.loud and self.loud != "none":
            I, TP, LRA = LOUDNESS_TARGETS.get(self.loud, (-14.0, -1.0, 11.0))
            post += [f"loudnorm=I={I}:TP={TP}:LRA={LRA}:linear=true", f"alimiter=limit={10 ** (TP / 20):.3f}:attack=5:release=50:level=false"]
        fc.append(mix + "," + ",".join(post + [f"atrim=end={T:.4f}", "aresample=48000"]) + "[afinal]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "[vfinal]", "-map", "[afinal]"]
        cmd += self.venc() + ["-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                              "-g", str(int(self.fps * 2)), "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart",
                              "-t", f"{T:.4f}", self.out_path]
        log(f"timeline: {len(clips)} clips, {T:.2f}s, {len(self.transition_times)} joins -> {self.out_path}")
        self.run(cmd)
        return self.out_path, T

    # ---------- text ----------
    def font_opt(self, f=None):
        ff = self.p(f) if f else self.font
        return f"fontfile='{escape_path(ff)}':" if ff else ""

    def text_filters(self, tx):
        at = float(tx.get("at", 0))
        dur = float(tx.get("duration", 3))
        end = at + dur
        size = int(tx.get("size", int(self.H * 0.07)))
        if self.preview:
            size = max(12, size // 2)
        # drawtext never wraps: shrink to fit the widest line inside 90% of the frame (approx 0.6*size per char)
        longest = max(len(line) for line in str(tx["text"]).split("\n")) or 1
        max_size = int(0.9 * self.W / (0.6 * longest))
        if size > max_size:
            log(f"text '{tx['text'][:30]}' shrunk {size}->{max_size}px to fit the frame (add \\n to wrap)")
            size = max(16, max_size)
        color = tx.get("color", "white")
        anim = tx.get("anim", "fade")
        fi, fo = 0.4, 0.25
        p_in = f"clip((t-{at:.3f})/{fi},0,1)"
        ease_in = f"(1-pow(1-{p_in},3))"
        alpha = f"{p_in}*clip(({end:.3f}-t)/{fo},0,1)"
        pos = tx.get("position", "center")
        if isinstance(pos, dict):
            x, y = pos.get("x", "(w-text_w)/2"), pos.get("y", "(h-text_h)/2")
        else:
            x = "(w-text_w)/2"
            y = {"top": "h*0.18-text_h/2", "bottom": "h*0.78-text_h/2", "lower_third": "h*0.72"}.get(pos, "(h-text_h)/2")
        if anim == "slide_up":
            y = f"({y})+{int(self.H * 0.05)}*(1-{ease_in})"
        elif anim == "slide_left":
            x = f"({x})+{int(self.W * 0.08)}*(1-{ease_in})"
        elif anim == "none":
            alpha = "1"
        opts = [self.font_opt(tx.get("font")) + f"text='{escape_drawtext(tx['text'])}'", f"fontsize={size}", f"fontcolor={color}",
                f"x='{x}'", f"y='{y}'", f"alpha='{alpha}'", f"enable='between(t,{at:.3f},{end:.3f})'"]
        if tx.get("box"):
            opts += ["box=1", "boxcolor=black@0.55", f"boxborderw={max(8, size // 4)}"]
        if tx.get("shadow", True):
            opts += ["shadowcolor=black@0.5", "shadowx=0", f"shadowy={max(2, size // 18)}"]
        if tx.get("stroke"):
            opts += [f"borderw={int(tx['stroke'])}", "bordercolor=black"]
        filt = "drawtext=" + ":".join(opts)
        if anim == "pop":
            # pop = quick scale via two staggered draws is not possible in drawtext; emulate with fast fade + slight rise
            filt = filt.replace(f"alpha='{alpha}'", f"alpha='clip((t-{at:.3f})/0.12,0,1)*clip(({end:.3f}-t)/{fo},0,1)'")
        return [filt]

    def lower_third(self, lt):
        at, dur = float(lt.get("at", 1.0)), float(lt.get("duration", 4.0))
        end = at + dur
        H, W = self.H, self.W
        base_y = int(H * 0.74)
        name_size = int(H * 0.05)
        role_size = int(H * 0.032)
        if self.preview:
            name_size, role_size = max(10, name_size // 2), max(8, role_size // 2)
        p0 = f"clip((t-{at:.3f})/0.3,0,1)"
        e0 = f"(1-pow(1-{p0},3))"
        out_a = f"clip(({end:.3f}-t)/0.25,0,1)"
        x0 = int(W * 0.07)
        barh = name_size + role_size + int(H * 0.025)
        fl = [f"drawbox=x='{x0 - 14}-{int(W * 0.08)}*(1-{e0})':y={base_y - int(H * 0.012)}:w=8:h={barh}:color={hex_to_ffcolor(self.brand)}:t=fill:enable='between(t,{at:.3f},{end:.3f})'",
              "drawtext=" + self.font_opt(lt.get("font")) + f"text='{escape_drawtext(lt.get('name', ''))}':fontsize={name_size}:fontcolor=white:x='{x0}+{int(W * 0.03)}*(1-{e0})':y={base_y}:alpha='clip((t-{at + 0.08:.3f})/0.3,0,1)*{out_a}':shadowcolor=black@0.5:shadowy=2:enable='between(t,{at:.3f},{end:.3f})'",
              "drawtext=" + self.font_opt(lt.get("font")) + f"text='{escape_drawtext(lt.get('role', ''))}':fontsize={role_size}:fontcolor=white@0.85:x='{x0}+{int(W * 0.03)}*(1-clip((t-{at + 0.18:.3f})/0.3,0,1))':y={base_y + name_size + int(H * 0.01)}:alpha='clip((t-{at + 0.2:.3f})/0.3,0,1)*{out_a}':enable='between(t,{at:.3f},{end:.3f})'"]
        return fl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("--preview", action="store_true", help="fast half-res proxy")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--hw", action="store_true", help="use videotoolbox for previews on Mac")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    require("ffmpeg")
    with open(a.edl) as fh:
        edl = json.load(fh)
    r = Renderer(edl, a.edl, a.preview, a.dry_run, a.verbose, a.hw, a.no_cache, a.out)
    out, T = r.render()
    if not a.dry_run:
        log(f"done: {out} ({T:.2f}s). Next: python3 scripts/qc.py {sh_quote(out)} --platform <platform>")
        print(out)


if __name__ == "__main__":
    main()
