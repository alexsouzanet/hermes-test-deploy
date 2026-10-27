"""Missão China 2026 video kit: brand constants, caption builders (ASS) and PIL motion graphics.

Everything is 1080x1920 @ 30 fps. ASS files use PlayRes 1080x1920, so sizes are pixels.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BLUE_DARK = (0, 94, 184)      # #005EB8  "SEBRAE"
BLUE_LIGHT = (64, 185, 255)   # #40B9FF  symbol / "Startups"
WHITE = (255, 255, 255)
INK = (8, 20, 40)

FONT_DIR = Path("/usr/share/fonts/opentype/inter")
LOGOS = Path(__file__).resolve().parent.parent / "assets" / "logos"

# Instagram Reels safe area (UI covers top ~220px, bottom ~420px, right rail ~140px).
SAFE_TOP = 250
TOP_BAR_Y = 140             # tag + logo row: close to the top edge, clear of the face (approved 27/10)
TAG_H = 76
CAPTION_Y = 1340              # caption baseline, ~30% up from the bottom


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / f"Inter-{weight}.otf"), size)


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


# ---------------------------------------------------------------- transcript

# Spoken → written Portuguese for captions only (audio stays as spoken).
CORRECTIONS = {"cê": "você", "dum": "de um", "duma": "de uma", "sides": "side", "pra": "para",
               "pro": "para o", "pros": "para os", "tô": "estou", "tá": "está", "tamos": "estamos", "tão": "estão"}
# Multi-word names that must never split across caption cues.
KEEP_TOGETHER = [("startup", "summit"), ("summit", "week"), ("happy", "hour")]


def _fix(text: str) -> str:
    m = re.match(r"^(\W*)(\w+)(.*)$", text, re.UNICODE)
    if not m:
        return text
    pre, core, post = m.groups()
    rep = CORRECTIONS.get(core.lower())
    if rep is None:
        return text
    if core[0].isupper():
        rep = rep[0].upper() + rep[1:]
    return pre + rep + post


def load_words(transcript: Path, start: float, end: float) -> list[dict]:
    """Spoken words in [start, end], corrected and with KEEP_TOGETHER pairs merged."""
    raw = [w for w in json.loads(transcript.read_text())["words"]
           if w["type"] == "word" and w["start"] >= start - 0.01 and w["end"] <= end + 0.01]
    words = [{"text": _fix(w["text"]), "start": w["start"], "end": w["end"]} for w in raw]
    merged: list[dict] = []
    for w in words:
        if merged:
            a = re.sub(r"\W", "", merged[-1]["text"].split()[-1]).lower()
            b = re.sub(r"\W", "", w["text"].split()[0]).lower()
            if (a, b) in KEEP_TOGETHER and not merged[-1]["text"][-1] in ".,?!":
                merged[-1] = {"text": merged[-1]["text"] + " " + w["text"],
                              "start": merged[-1]["start"], "end": w["end"]}
                continue
        merged.append(dict(w))
    return merged


def chunk(words: list[dict], max_words: int, max_chars: int, min_dur: float = 0.35,
          pause: float = 0.3, punct: str = ".,?!;:") -> list[list[dict]]:
    """Group words into cues: close on punctuation, on a pause, or at the size limit."""
    out, cur = [], []
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        if cur and len(" ".join(x["text"] for x in cur + [w])) > max_chars:
            out.append(cur)
            cur = []
        cur.append(w)
        gap = (nxt["start"] - w["end"]) if nxt else 0
        dur = w["end"] - cur[0]["start"]
        n = sum(len(x["text"].split()) for x in cur)
        if (nxt is None or w["text"][-1] in punct or gap >= pause or w.get("cut_after")
                or n >= max_words + 1 or (n >= max_words and dur >= min_dur)):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- ASS captions

def _ts(s: float) -> str:
    s = max(0.0, s)
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def _ass_color(rgb, alpha=0) -> str:
    r, g, b = rgb
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

MARGIN_V = H - CAPTION_Y

STYLES = {
    # A: bold caps, 2-3 words, white with black outline (TikTok/Reels standard).
    "A": f"Style: A,Inter ExtraBold,82,{_ass_color(WHITE)},{_ass_color(WHITE)},{_ass_color((0,0,0))},{_ass_color((0,0,0),0x80)},-1,0,0,0,100,100,0,0,1,6,2,2,110,110,{MARGIN_V},1",
    # B: sentence case, 4-7 words, white on a soft dark box (documentary / LinkedIn feel).
    "B": f"Style: B,Inter SemiBold,58,{_ass_color(WHITE)},{_ass_color(WHITE)},{_ass_color((10,16,30),0x50)},{_ass_color((0,0,0),0xFF)},0,0,0,0,100,100,0,0,3,16,0,2,120,120,{MARGIN_V},1",
    # C: karaoke caps, the word being spoken lights up in brand light blue.
    "C": f"Style: C,Inter Black,84,{_ass_color(WHITE)},{_ass_color(WHITE)},{_ass_color(INK)},{_ass_color((0,0,0),0x80)},-1,0,0,0,100,100,0,0,1,7,3,2,100,100,{MARGIN_V},1",
    # EN: translation line under a smaller PT line.
    "EN": f"Style: EN,Inter ExtraBold,66,{_ass_color(BLUE_LIGHT)},{_ass_color(WHITE)},{_ass_color((0,0,0))},{_ass_color((0,0,0),0x80)},-1,0,0,0,100,100,0,0,1,5,2,2,110,110,{MARGIN_V},1",
    "PT": f"Style: PT,Inter SemiBold,46,{_ass_color(WHITE)},{_ass_color(WHITE)},{_ass_color((0,0,0))},{_ass_color((0,0,0),0x80)},0,0,0,0,100,100,0,0,1,4,1,2,110,110,{MARGIN_V + 190},1",
}


MAX_TEXT_W = 860  # px; keeps cues clear of the frame edge and the Reels right rail


def _fit(text: str, weight: str, size: int) -> str:
    """Prefix an ASS font-size override when one line would be wider than MAX_TEXT_W."""
    w = font(weight, size).getlength(text) * 1.04
    if w <= MAX_TEXT_W:
        return text
    return "{\\fs%d}" % int(size * MAX_TEXT_W / w) + text


def _clean_caps(text: str) -> str:
    return text.rstrip(",;:.").upper() if not text.endswith("?") else text.upper()


# Tag-question fillers dropped from captions only (the audio keeps them).
CAPTION_SKIP = {"né"}


def captions_ass(words: list[dict], style: str, t0: float, out: Path) -> int:
    """Write an ASS file for one block. t0 = source time that maps to block time 0."""
    words = [w for w in words if re.sub(r"\W", "", w["text"]).lower() not in CAPTION_SKIP]
    lines = []
    if style == "A":
        for c in chunk(words, 2, 16):
            text = _clean_caps(" ".join(w["text"] for w in c))
            lines.append((c[0]["start"] - t0, c[-1]["end"] - t0, "A", _fit(text, "ExtraBold", 82)))
    elif style == "B":
        sentence_start = True
        for c in chunk(words, 7, 36, pause=0.6, punct=".?!"):
            text = " ".join(w["text"] for w in c).rstrip(",;:")
            if sentence_start:
                text = text[0].upper() + text[1:]
            sentence_start = text[-1] in ".?!"
            lines.append((c[0]["start"] - t0, c[-1]["end"] - t0 + 0.15, "B", text))
    elif style == "C":
        for c in chunk(words, 2, 15):
            for i, w in enumerate(c):
                parts = []
                for j, x in enumerate(c):
                    t = _clean_caps(x["text"]) if j == len(c) - 1 else x["text"].upper()
                    if j == i:
                        r, g, b = BLUE_LIGHT
                        parts.append(f"{{\\c&H{b:02X}{g:02X}{r:02X}&\\fscx106\\fscy106}}{t}{{\\r}}")
                    else:
                        parts.append(t)
                end = c[i + 1]["start"] if i + 1 < len(c) else w["end"]
                plain = " ".join(_clean_caps(x["text"]) for x in c)
                fit = _fit(plain, "Black", 84)
                prefix = fit[: fit.index("}") + 1] if fit.startswith("{") else ""
                lines.append((w["start"] - t0, end - t0, "C", prefix + " ".join(parts).replace("{\\r}", "{\\r" + prefix[1:-1] + "}" if prefix else "{\\r}")))
    else:
        raise ValueError(style)
    _write_ass(out, lines)
    return len(lines)


def _write_ass(out: Path, lines) -> None:
    body = []
    for k, (a, b, st, tx) in enumerate(lines):
        b = max(b, a + 0.35)
        later = [x[0] for x in lines[k + 1:] if x[2] == st and x[0] > a]
        if later:
            b = min(b, later[0])
        body.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},{st},,0,0,0,,{tx}")
    out.write_text(ASS_HEADER.format(styles="\n".join(STYLES.values())) + "\n".join(body) + "\n")


def bilingual_ass(cues: list[tuple[float, float, str, str]], out: Path) -> None:
    """cues: (start, end, portuguese, english) in block time."""
    lines = []
    for a, b, pt, en in cues:
        lines.append((a, b, "PT", pt))
        lines.append((a, b, "EN", en.upper()))
    _write_ass(out, lines)


# ---------------------------------------------------------------- graphics

def logo_bug(variant: str = "B", width: int = 300) -> Image.Image:
    """Small corner logo. A = brand colours (dark-bg version), B = white. Soft shadow for bright scenes."""
    src = {"A": "horizontal_fundo_escuro.png", "B": "horizontal_branco.png",
           "C": "simbolo_fundo_claro.png", "D": "simbolo_branco.png"}[variant]
    lg = Image.open(LOGOS / src).convert("RGBA")
    if variant in "CD":
        width = 92
    h = int(lg.height * width / lg.width)
    lg = lg.resize((width, h), Image.LANCZOS)
    pad = 24
    canvas = Image.new("RGBA", (width + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new("RGBA", lg.size, (0, 0, 0, 0))
    shadow.putalpha(lg.getchannel("A").point(lambda v: int(v * 0.55)))
    canvas.alpha_composite(shadow, (pad + 2, pad + 3))
    canvas = canvas.filter(ImageFilter.GaussianBlur(6))
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * 0.92)))
    canvas.alpha_composite(lg, (pad, pad))
    return canvas


def logo_bug_frame(variant: str = "B") -> Image.Image:
    """Full-frame RGBA with the logo top-right inside the safe area."""
    bug = logo_bug(variant)
    f = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f.alpha_composite(bug, (W - bug.width - 40, TOP_BAR_Y + (TAG_H - (bug.height - 48)) // 2 - 24))
    return f


def _pin(draw: ImageDraw.ImageDraw, x: int, y: int, s: int, color) -> None:
    draw.ellipse((x, y, x + s, y + s), fill=color)
    draw.polygon([(x + s * 0.14, y + s * 0.62), (x + s * 0.86, y + s * 0.62), (x + s / 2, y + s * 1.35)], fill=color)
    draw.ellipse((x + s * 0.33, y + s * 0.33, x + s * 0.67, y + s * 0.67), fill=BLUE_DARK)


def location_tag_frames(day: str, place: str, dur: float, out_dir: Path) -> int:
    """'DIA 3 · HANGZHOU' pill, top-left. Slides in (0.45s ease-out), holds, fades out last 0.3s."""
    out_dir.mkdir(parents=True, exist_ok=True)
    f_day, f_place = font("Black", 40), font("ExtraBold", 40)
    day_t, place_t = day.upper(), place.upper()
    dw = f_day.getlength(day_t)
    pw = f_place.getlength(place_t)
    h = TAG_H
    pill_w = int(28 + 34 + 16 + dw + 26 + pw + 30)
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        k = ease_out_cubic(t / 0.45)
        fade = 1.0 if t < dur - 0.3 else max(0.0, (dur - t) / 0.3)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer = Image.new("RGBA", (pill_w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((0, 0, pill_w - 1, h - 1), radius=h // 2, fill=BLUE_DARK + (235,))
        split = int(28 + 34 + 16 + dw + 13)
        d.rounded_rectangle((split, 0, pill_w - 1, h - 1), radius=h // 2, fill=WHITE + (245,))
        d.rectangle((split, 0, split + h // 2, h - 1), fill=WHITE + (245,))
        _pin(d, 28, 18, 30, BLUE_LIGHT)
        d.text((28 + 34 + 16, h / 2), day_t, font=f_day, fill=WHITE, anchor="lm")
        d.text((split + 26, h / 2), place_t, font=f_place, fill=BLUE_DARK, anchor="lm")
        x = int(48 - (1 - k) * (pill_w + 60))
        alpha = layer.getchannel("A").point(lambda v: int(v * fade))
        layer.putalpha(alpha)
        img.alpha_composite(layer, (x, TOP_BAR_Y))
        img.save(out_dir / f"f_{i:04d}.png", compress_level=1)
    return n


def lower_third_frames(name: str, role: str, dur: float, out_dir: Path, y: int = 1030) -> int:
    """Name card: light-blue accent bar grows, panel wipes in, text rises. Out-wipe in the last 0.4s."""
    out_dir.mkdir(parents=True, exist_ok=True)
    f_name, f_role = font("ExtraBold", 54), font("SemiBold", 40)
    tw = int(max(f_name.getlength(name), f_role.getlength(role)) + 80)
    ph = 150
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        bar = ease_out_cubic(t / 0.3)
        wipe = ease_out_cubic((t - 0.15) / 0.5)
        text_k = ease_out_cubic((t - 0.35) / 0.45)
        out_k = ease_in_out_cubic((t - (dur - 0.4)) / 0.4)
        x0 = 48
        if out_k > 0:
            wipe = 1 - out_k
            bar = 1 - out_k
            text_k = 1 - out_k
        d.rectangle((x0, y + int(ph * (1 - bar)), x0 + 12, y + ph), fill=BLUE_LIGHT)
        pw = int(tw * wipe)
        if pw > 0:
            d.rectangle((x0 + 12, y, x0 + 12 + pw, y + ph), fill=(*BLUE_DARK, 225))
        if text_k > 0 and pw > 40:
            txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            td = ImageDraw.Draw(txt)
            dy = int((1 - text_k) * 22)
            a = int(255 * text_k)
            td.text((x0 + 44, y + 28 + dy), name, font=f_name, fill=(*WHITE, a))
            td.text((x0 + 44, y + 94 + dy), role, font=f_role, fill=(*BLUE_LIGHT, a))
            mask = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mask).rectangle((x0 + 12, y, x0 + 12 + pw, y + ph), fill=255)
            txt.putalpha(Image.composite(txt.getchannel("A"), Image.new("L", (W, H), 0), mask))
            img.alpha_composite(txt)
        img.save(out_dir / f"f_{i:04d}.png", compress_level=1)
    return n


def _brand_bg(still: Path) -> Image.Image:
    bg = Image.open(still).convert("RGB").resize((W, H)).filter(ImageFilter.GaussianBlur(28))
    tint = Image.new("RGB", (W, H), BLUE_DARK)
    bg = Image.blend(bg, tint, 0.72)
    grad = Image.new("L", (1, H))
    for yy in range(H):
        grad.putpixel((0, yy), int(150 * (yy / H) ** 1.6))
    dark = Image.new("RGB", (W, H), (0, 18, 45))
    bg.paste(dark, (0, 0), grad.resize((W, H)))
    return bg


def title_card_frames(still: Path, kicker: str, title: str, sub: str, dur: float, out_dir: Path) -> int:
    """Full-screen opener: symbol drops in, kicker/title/sub rise one after another (never in parallel)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bg = _brand_bg(still)
    sym = Image.open(LOGOS / "simbolo_branco.png").convert("RGBA")
    sym = sym.resize((150, int(sym.height * 150 / sym.width)), Image.LANCZOS)
    f_k, f_t, f_s = font("Bold", 40), font("Black", 112), font("ExtraBold", 54)
    title_lines = title.split("\n")
    n = int(round(dur * FPS))
    cy = 760
    for i in range(n):
        t = i / FPS
        img = bg.copy().convert("RGBA")
        layers = [
            (0.00, "sym", None),
            (0.25, "k", kicker.upper()),
            (0.50, "t", None),
            (0.85, "s", sub.upper()),
        ]
        for delay, kind, txt in layers:
            k = ease_out_cubic((t - delay) / 0.5)
            if k <= 0:
                continue
            dy = int((1 - k) * 40)
            a = int(255 * k)
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            if kind == "sym":
                s = sym.copy()
                s.putalpha(s.getchannel("A").point(lambda v: int(v * k)))
                lay.alpha_composite(s, ((W - s.width) // 2, cy - 330 + dy))
            elif kind == "k":
                d.text((W / 2, cy - 110 + dy), txt, font=f_k, fill=(*BLUE_LIGHT, a), anchor="mm")
            elif kind == "t":
                for li, line in enumerate(title_lines):
                    d.text((W / 2, cy + li * 122 + dy), line.upper(), font=f_t, fill=(*WHITE, a), anchor="mm")
            elif kind == "s":
                yy = cy + len(title_lines) * 122 + 40 + dy
                w = f_s.getlength(txt) + 70
                d.rounded_rectangle(((W - w) / 2, yy - 44, (W + w) / 2, yy + 44), radius=44, fill=(*BLUE_LIGHT, a))
                d.text((W / 2, yy), txt, font=f_s, fill=(*INK, a), anchor="mm")
            img.alpha_composite(lay)
        img.convert("RGB").save(out_dir / f"f_{i:04d}.png", compress_level=1)
    return n


def end_card_frames(still: Path, dur: float, out_dir: Path) -> int:
    """Closing card: full logo, mission line, both handles."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bg = _brand_bg(still)
    lg = Image.open(LOGOS / "horizontal_fundo_escuro.png").convert("RGBA")
    lg = lg.resize((760, int(lg.height * 760 / lg.width)), Image.LANCZOS)
    f_m, f_h = font("ExtraBold", 50), font("Bold", 46)
    n = int(round(dur * FPS))
    items = [(0.0, "logo"), (0.3, "line"), (0.6, "h1"), (0.8, "h2")]
    for i in range(n):
        t = i / FPS
        img = bg.copy().convert("RGBA")
        for delay, kind in items:
            k = ease_out_cubic((t - delay) / 0.5)
            if k <= 0:
                continue
            a, dy = int(255 * k), int((1 - k) * 36)
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            if kind == "logo":
                s = lg.copy()
                s.putalpha(s.getchannel("A").point(lambda v: int(v * k)))
                lay.alpha_composite(s, ((W - s.width) // 2, 640 + dy))
            elif kind == "line":
                d.text((W / 2, 860 + dy), "MISSÃO CHINA 2026 · SCALE IA", font=f_m, fill=(*WHITE, a), anchor="mm")
                d.rectangle((W / 2 - 60, 920 + dy, W / 2 + 60, 926 + dy), fill=(*BLUE_LIGHT, a))
            elif kind == "h1":
                d.text((W / 2, 1010 + dy), "@sebraestartups", font=f_h, fill=(*BLUE_LIGHT, a), anchor="mm")
            elif kind == "h2":
                d.text((W / 2, 1080 + dy), "@alexsouzanet", font=f_h, fill=(*BLUE_LIGHT, a), anchor="mm")
            img.alpha_composite(lay)
        img.convert("RGB").save(out_dir / f"f_{i:04d}.png", compress_level=1)
    return n


def review_label_frame(text: str) -> Image.Image:
    """Catalog-only chip at the very top: names the option being shown. Never used in published cuts."""
    f = font("Bold", 34)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = f.getlength(text) + 48
    d.rounded_rectangle(((W - w) / 2, 120, (W + w) / 2, 180), radius=30, fill=(255, 214, 0, 240))
    d.text((W / 2, 150), text, font=f, fill=(20, 20, 20), anchor="mm")
    return img
