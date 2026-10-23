"""Shared helpers for video-editor-pro scripts."""
import json
import os
import platform
import re
import shutil
import subprocess
import sys


def which(name):
    return shutil.which(name)


def require(name, hint=None):
    if not which(name):
        msg = f"'{name}' not found on PATH."
        if hint:
            msg += " " + hint
        elif name in ("ffmpeg", "ffprobe"):
            msg += " Install with: brew install ffmpeg"
        sys.exit(msg)


def run(cmd, verbose=False, check=True, capture=False):
    if verbose:
        print("+ " + " ".join(sh_quote(c) for c in cmd), file=sys.stderr)
    return subprocess.run(cmd, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def sh_quote(s):
    s = str(s)
    if re.fullmatch(r"[A-Za-z0-9_./:=,+@%-]+", s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def ffprobe_json(path):
    require("ffprobe")
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe cannot read {path}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else 'unknown error'}")
    return json.loads(p.stdout)


def media_info(path):
    """Return a compact dict: duration, width, height, fps, has_audio, sample_rate, channels, vcodec, acodec."""
    j = ffprobe_json(path)
    info = {"path": path, "duration": float(j.get("format", {}).get("duration") or 0),
            "width": None, "height": None, "fps": None, "has_video": False, "has_audio": False,
            "sample_rate": None, "channels": None, "vcodec": None, "acodec": None, "pix_fmt": None,
            "rotation": 0, "size_bytes": int(j.get("format", {}).get("size") or 0),
            "bitrate": int(j.get("format", {}).get("bit_rate") or 0)}
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and not info["has_video"]:
            info["has_video"] = True
            info["width"], info["height"] = s.get("width"), s.get("height")
            info["vcodec"] = s.get("codec_name")
            info["pix_fmt"] = s.get("pix_fmt")
            r = s.get("avg_frame_rate") or s.get("r_frame_rate") or "0/1"
            try:
                n, d = r.split("/")
                info["fps"] = float(n) / float(d) if float(d) else 0.0
            except ValueError:
                info["fps"] = float(r)
            rot = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = int(sd["rotation"])
            tags = s.get("tags", {}) or {}
            if "rotate" in tags:
                rot = int(tags["rotate"])
            info["rotation"] = rot
            if abs(rot) in (90, 270):
                info["width"], info["height"] = info["height"], info["width"]
            if not info["duration"] and s.get("duration"):
                info["duration"] = float(s["duration"])
        elif s.get("codec_type") == "audio" and not info["has_audio"]:
            info["has_audio"] = True
            info["sample_rate"] = int(s.get("sample_rate") or 0)
            info["channels"] = int(s.get("channels") or 0)
            info["acodec"] = s.get("codec_name")
    return info


def measure_loudness(path, duration_limit=None):
    """Integrated loudness, true peak, LRA via ebur128. Returns dict or None if no audio."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
    if duration_limit:
        cmd += ["-t", str(duration_limit)]
    cmd += ["-af", "ebur128=peak=true", "-f", "null", "-"]
    p = subprocess.run(cmd, text=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    txt = p.stderr
    if "Summary:" in txt:
        txt = txt[txt.rfind("Summary:"):]
    res = {}
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
    if m:
        res["integrated_lufs"] = float(m[-1])
    m = re.findall(r"LRA:\s+([\d.]+) LU", txt)
    if m:
        res["lra_lu"] = float(m[-1])
    m = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)
    if m:
        res["true_peak_dbtp"] = float(m[-1])
    return res or None


def is_mac():
    return platform.system() == "Darwin"


def find_font(preferred=None):
    """Pick a usable bold-ish font file path."""
    cands = []
    if preferred:
        cands.append(os.path.expanduser(preferred))
    cands += [
        os.path.expanduser("~/Library/Fonts/Montserrat-Bold.ttf"),
        os.path.expanduser("~/Library/Fonts/Inter-Bold.ttf"),
        os.path.expanduser("~/Library/Fonts/Poppins-Bold.ttf"),
        "/System/Library/Fonts/Supplemental/Futura.ttc",
        "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
        "/System/Library/Fonts/Supplemental/Helvetica Neue.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def escape_drawtext(s):
    """Escape text for drawtext's text= option inside a filtergraph."""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\u2019")  # avoid quote hell; typographic apostrophe reads fine
    s = s.replace(":", "\\:")
    s = s.replace("%", "\\\\%")  # drawtext needs \% AFTER the graph parser eats one backslash
    s = s.replace(",", "\\,")
    s = s.replace("[", "\\[").replace("]", "\\]")
    s = s.replace(";", "\\;")
    return s


def escape_path(p):
    """Escape a file path for use inside a filtergraph option (fontfile=, subtitles=, lut3d=)."""
    p = str(p)
    p = p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")
    p = p.replace("[", "\\[").replace("]", "\\]").replace(";", "\\;")
    return p


def hex_to_ffcolor(h, alpha=None):
    h = h.lstrip("#")
    if len(h) == 6:
        c = "0x" + h
    else:
        c = h
    if alpha is not None:
        c += f"@{alpha}"
    return c


LOUDNESS_TARGETS = {
    "youtube": (-14.0, -1.0, 11.0),
    "social": (-14.0, -1.0, 11.0),
    "instagram": (-14.0, -1.0, 11.0),
    "tiktok": (-14.0, -1.0, 11.0),
    "linkedin": (-14.0, -1.0, 11.0),
    "podcast": (-16.0, -1.0, 11.0),
    "spotify": (-16.0, -1.0, 11.0),
    "broadcast": (-23.0, -1.0, 15.0),
    "ebu": (-23.0, -1.0, 15.0),
    "atsc": (-24.0, -2.0, 15.0),
    "review": (-16.0, -1.0, 11.0),
}
