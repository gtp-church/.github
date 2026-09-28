"""Собирает картинки профиля: profile/assets/banner.svg и directions.svg.

Текст переводится в контуры, поэтому SVG выглядит одинаково везде и не зависит
от шрифтов у зрителя. Логотип берётся из брендбука (scripts/src/logo.svg).

    uv run --with fonttools --with uharfbuzz scripts/build_assets.py [путь к Manrope[wght].ttf]

Manrope (SIL OFL) — https://github.com/sharanda/manrope
"""

import re
import sys
from pathlib import Path
from urllib.parse import quote

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "profile" / "assets"
FONT = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Library/Fonts/Manrope[wght].ttf")

COPPER = "#CA6E34"
INK = "#1A171B"        # тёмный цвет бренда
BG = "#151214"
LIGHT = "#F3EEE9"
MUTED = "#A3968D"
STROKE = "#2B2421"

W = 1280


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Text:
    """Набор строки через HarfBuzz и перевод глифов в SVG-контуры."""

    def __init__(self, path):
        data = path.read_bytes()
        self.tt = TTFont(path)
        self.face = hb.Face(data)
        self.order = self.tt.getGlyphOrder()

    def _shape(self, s, size, wght, tracking):
        font = hb.Font(self.face)
        font.set_variations({"wght": wght})
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(font, buf, {"kern": True, "liga": True})
        k = size / self.face.upem
        extra = tracking * self.face.upem
        return buf.glyph_infos, buf.glyph_positions, k, extra

    def width(self, s, size, wght, tracking=0.0):
        _, pos, k, extra = self._shape(s, size, wght, tracking)
        return sum(p.x_advance + extra for p in pos) * k - (extra * k if pos else 0)

    def path(self, s, size, wght, x, y, fill, tracking=0.0, anchor="start", opacity=None):
        infos, pos, k, extra = self._shape(s, size, wght, tracking)
        if anchor != "start":
            w = self.width(s, size, wght, tracking)
            x -= w if anchor == "end" else w / 2
        glyphs = self.tt.getGlyphSet(location={"wght": wght})
        pen = SVGPathPen(glyphs, ntos=num)
        cx = 0
        for info, p in zip(infos, pos):
            name = self.order[info.codepoint]
            gx = x + (cx + p.x_offset) * k
            gy = y - p.y_offset * k
            glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, gx, gy)))
            cx += p.x_advance + extra
        op = f' fill-opacity="{opacity}"' if opacity is not None else ""
        return f'<path fill="{fill}"{op} d="{pen.getCommands()}"/>'

    def wrap(self, s, size, wght, max_w):
        # короткие слова («и», «в») не оставляем в конце строки
        words = []
        for w in s.split():
            if words and len(words[-1]) <= 2 and not words[-1].endswith(","):
                words[-1] += "\u00a0" + w
            else:
                words.append(w)
        lines, cur = [], ""
        for word in words:
            probe = f"{cur} {word}".strip()
            if cur and self.width(probe, size, wght) > max_w:
                lines.append(cur)
                cur = word
            else:
                cur = probe
        return lines + [cur]


def logo_parts():
    """Элементы логотипа: знак (крест и книга) отдельно от надписей."""
    src = (ROOT / "scripts/src/logo.svg").read_text(encoding="utf-8")
    sign, full = [], []
    for m in re.finditer(r"<(path|polygon)\s+class=\"(fil\d)\"\s+(d|points)=\"([^\"]+)\"\s*/>", src):
        tag, cls, attr, geom = m.groups()
        first_x = float(re.match(r"[ML]?\s*(-?[\d.]+)", geom).group(1))
        el = (tag, cls, attr, geom)
        full.append(el)
        if first_x < 4000:      # надписи начинаются правее знака
            sign.append(el)
    return sign, full


def render(parts, colors, opacity=None):
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return "".join(f'<{t} fill="{colors[c]}"{op} {a}="{g}"/>' for t, c, a, g in parts)


def banner(tx):
    h = 460
    sign, full = logo_parts()
    logo_w = 600
    s_logo = logo_w / 15898.89
    s_sign = 0.115          # знак ≈ 3400×4400 единиц → ~390×505 px

    body = [
        f'<rect width="{W}" height="{h}" fill="{BG}"/>',
        f'<rect width="{W}" height="{h}" fill="url(#glow)"/>',
        # крупный знак справа, как водяной знак
        f'<g transform="translate(858 12) scale({s_sign:.5f})">'
        + render(sign, {"fil0": COPPER, "fil1": COPPER, "fil2": COPPER}, opacity=0.18)
        + "</g>",
        tx.path("GOSPEL TO PEOPLE", 17, 700, 76, 96, COPPER, tracking=0.28),
        f'<g transform="translate(72 124) scale({s_logo:.6f})">'
        + render(full, {"fil0": LIGHT, "fil1": COPPER, "fil2": LIGHT})
        + "</g>",
        tx.path("Цифровые инструменты церкви «Евангелие людям»", 30, 600, 74, 374, LIGHT),
        tx.path("Every line of code for the glory of God!", 19, 500, 75, 412, MUTED),
    ]
    return svg(W, h, "Gospel To People — цифровые инструменты церкви «Евангелие людям»",
               body, defs=(
                   '<radialGradient id="glow" cx="0.84" cy="0.45" r="0.62">'
                   f'<stop offset="0" stop-color="{COPPER}" stop-opacity=".26"/>'
                   f'<stop offset="1" stop-color="{COPPER}" stop-opacity="0"/>'
                   "</radialGradient>"
               ), rounded=True)


ICONS = {  # 24×24, штрих, в духе Lucide (ISC)
    "video": '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 11"/>',
    "book": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "music": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "tent": '<path d="M3.5 21 14 3"/><path d="M20.5 21 10 3"/><path d="M15.5 21 12 15l-3.5 6"/><path d="M2 21h20"/>',
    "bus": '<path d="M8 6v6"/><path d="M15 6v6"/><path d="M2 12h19.6"/><path d="M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"/><circle cx="7" cy="18" r="2"/><path d="M9 18h5"/><circle cx="16" cy="18" r="2"/>',
}

DIRECTIONS = [
    ("video", "Медиа", "проповеди и трансляции"),
    ("book", "Писание", "аудио-Библия и титры"),
    ("music", "Музыка и хор", "гимны, аккорды и партии"),
    ("tent", "Молодёжь", "выезды и лагеря"),
    ("bus", "Церковная жизнь", "транспорт и учёт"),
]


def directions(tx):
    h, gap, pad = 236, 16, 26
    n = len(DIRECTIONS)
    cw = (W - gap * (n - 1)) / n
    body = []
    for i, (icon, title, sub) in enumerate(DIRECTIONS):
        x = i * (cw + gap)
        inner = cw - 2 * pad
        cx, cy = x + pad + 28, 30 + 28
        size = 23
        while tx.width(title, size, 700) > inner:
            size -= 0.5
        body += [
            f'<rect x="{num(x + .5)}" y=".5" width="{num(cw - 1)}" height="{h - 1}" rx="24" fill="{BG}" stroke="{STROKE}"/>',
            f'<circle cx="{num(cx)}" cy="{cy}" r="28" fill="{COPPER}" fill-opacity=".16"/>',
            f'<g transform="translate({num(cx - 15)} {cy - 15}) scale(1.25)" fill="none" stroke="{COPPER}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>',
            tx.path(title, size, 700, x + pad, 134, LIGHT),
        ]
        for j, line in enumerate(tx.wrap(sub, 17, 500, inner)):
            body.append(tx.path(line, 17, 500, x + pad, 168 + j * 24, MUTED))
    label = "Направления: " + "; ".join(f"{t} — {s}" for _, t, s in DIRECTIONS)
    return svg(W, h, label, body)


def svg(w, h, label, body, defs="", rounded=False):
    clip = f'<clipPath id="card"><rect width="{w}" height="{h}" rx="32"/></clipPath>' if rounded else ""
    inner = "".join(body)
    if rounded:
        inner = f'<g clip-path="url(#card)">{inner}</g>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{label}"><title>{label}</title><defs>{clip}{defs}</defs>{inner}</svg>\n'
    )


def badge(label, color, logo):
    """URL бейджа shields.io: в тексте '-' и '_' экранируются удвоением."""
    text = quote(label.replace("-", "--").replace("_", "__"))
    return f"https://img.shields.io/badge/{text}-{color.lstrip('#')}?style=for-the-badge&logo={logo}&logoColor=white"


if __name__ == "__main__":
    tx = Text(FONT)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "banner.svg").write_text(banner(tx), encoding="utf-8")
    (OUT / "directions.svg").write_text(directions(tx), encoding="utf-8")
    for label, color, logo in [("@gtp_media_bot", COPPER, "telegram"),
                               ("евангелие-людям.рф", INK, "googlechrome"),
                               ("Москва", INK, "googlemaps")]:
        print(badge(label, color, logo))
