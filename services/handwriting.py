"""Husnixat (real qo'lyozma) generatori: matn -> daftar fonidagi JPG varoqlar + PDF."""
from __future__ import annotations

import asyncio
import math
import random
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from config import BASE_DIR, DATA_DIR

FONTS_DIR = BASE_DIR / "fonts"
OUT_DIR = DATA_DIR / "out"
PREVIEW_DIR = DATA_DIR / "previews"
PAGE_W, PAGE_H = 1240, 1754  # A4, 150 dpi
MARGIN_TOP, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_BOTTOM = 170, 170, 70, 110

FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


@dataclass(frozen=True)
class Style:
    key: str
    title: str
    font: str  # fonts/ papkasidagi TTF fayl nomi
    size: int = 44
    jitter: float = 1.0  # harf joylashuvidagi tasodifiy siljish (px)
    rotation: float = 1.0  # harf burilishi (gradus)
    ink: tuple = (25, 40, 130)
    line_gap: int = 62  # qator oralig'i
    paper: str = "lined"  # lined | grid
    wobble: float = 0.0  # qator bo'ylab "to'lqin" (px)
    spacing: float = 0.0  # harflar orasi (px)


# 12 xil variant. Shrift fayllarini fonts/ ga qo'ying (fonts/README.md ga qarang).
# Har bir variantga alohida TTF berish uchun faqat `font=` ni o'zgartiring.
STYLES: tuple[Style, ...] = (
    Style("calli_1", "Kaligrafik (juda chiroyli)", "BadScript-Regular.ttf", 46, 0.4, 0.6, (20, 30, 110), 64),
    Style("calli_2", "Klassik kalligrafiya", "MarckScript-Regular.ttf", 48, 0.5, 0.8, (15, 25, 90), 66),
    Style("student_neat", "Toza talaba yozuvi", "Caveat-Regular.ttf", 50, 0.8, 1.0, (30, 50, 140), 62),
    Style("student_avg", "O'rtacha talaba", "Kalam-Regular.ttf", 40, 1.2, 1.6, (40, 40, 40), 62),
    Style("round", "Yumaloq harflar", "Neucha-Regular.ttf", 42, 1.0, 1.2, (20, 70, 60), 62, "grid"),
    Style("print", "Aniq bosma-yozma", "Pangolin-Regular.ttf", 40, 0.8, 0.8, (10, 10, 10), 62),
    Style("tall", "Ingichka va baland", "AmaticSC-Regular.ttf", 54, 1.0, 1.2, (60, 30, 100), 62),
    Style("fast", "Shoshilib yozilgan", "Caveat-Bold.ttf", 52, 2.6, 4.0, (30, 30, 120), 62, "lined", 2.0, -1.0),
    Style("ugly", "Xunuk ma'ruza yozuvi", "Kalam-Light.ttf", 42, 3.4, 6.0, (50, 50, 55), 62, "lined", 3.0, -1.5),
    Style("childish", "Bolalarcha", "Underdog-Regular.ttf", 38, 2.0, 3.0, (150, 30, 30), 62, "grid"),
    Style("black_ink", "Qora siyoh", "MarckScript-Regular.ttf", 44, 0.9, 1.4, (0, 0, 0), 62),
    Style("pencil", "Qalam (grafit)", "BadScript-Regular.ttf", 42, 1.4, 1.8, (95, 95, 100), 62, "grid"),
)
STYLE_MAP = {s.key: s for s in STYLES}

_TRANSLATE = str.maketrans({"ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "´": "'", "`": "'", "“": '"', "”": '"', "\t": "    "})


def _load_font(style: Style) -> ImageFont.FreeTypeFont:
    for cand in (FONTS_DIR / style.font, *FALLBACK_FONTS):
        try:
            return ImageFont.truetype(str(cand), style.size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_paper(style: Style) -> Image.Image:
    img = Image.new("RGB", (PAGE_W, PAGE_H), (251, 249, 243))
    d = ImageDraw.Draw(img)
    gap = style.line_gap
    if style.paper == "grid":
        color = (190, 205, 225)
        for x in range(MARGIN_LEFT - 40, PAGE_W, 31):
            d.line([(x, 60), (x, PAGE_H - 60)], fill=color, width=1)
        for y in range(MARGIN_TOP, PAGE_H - 60, gap):
            d.line([(0, y), (PAGE_W, y)], fill=color, width=1)
    else:
        for y in range(MARGIN_TOP, PAGE_H - 60, gap):
            d.line([(0, y), (PAGE_W, y)], fill=(170, 195, 225), width=2)
    d.line([(MARGIN_LEFT - 30, 0), (MARGIN_LEFT - 30, PAGE_H)], fill=(215, 95, 95), width=3)
    return img


class _Metrics:
    def __init__(self, font: ImageFont.FreeTypeFont, spacing: float):
        self.font, self.spacing, self._c = font, spacing, {}

    def char(self, ch: str) -> float:
        if ch not in self._c:
            self._c[ch] = self.font.getlength(ch)
        return self._c[ch] + self.spacing

    def text(self, s: str) -> float:
        return sum(self.char(c) for c in s)


def wrap_text(text: str, m: _Metrics, max_width: float) -> list[str]:
    lines: list[str] = []
    for para in text.translate(_TRANSLATE).split("\n"):
        words, cur = para.split(" "), ""
        if not para.strip():
            lines.append("")
            continue
        for w in words:
            trial = f"{cur} {w}".strip() if cur else w
            if m.text(trial) <= max_width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            while m.text(w) > max_width:  # juda uzun so'z
                cut = len(w)
                while cut > 1 and m.text(w[:cut]) > max_width:
                    cut -= 1
                lines.append(w[:cut])
                w = w[cut:]
            cur = w
        lines.append(cur)
    return lines


def paginate(lines: list[str], pages: int, capacity: int) -> list[list[str]]:
    """Qatorlarni so'ralgan varoqlar soniga teng taqsimlaydi (sig'masa avtomatik ko'paytiradi)."""
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    if not lines:
        return [[]]
    need = math.ceil(len(lines) / capacity)
    n = max(need, min(pages, len(lines)))
    per = math.ceil(len(lines) / n)
    chunks = [lines[i * per:(i + 1) * per] for i in range(n)]
    return [c for c in chunks if c]


class _GlyphCache:
    def __init__(self, font, size):
        self.font, self.size, self._c = font, size, {}

    def get(self, ch: str, angle: float):
        key = (ch, round(angle * 4))
        if key not in self._c:
            pad = self.size
            base = int(self.size * 1.3)
            w = int(self.font.getlength(ch)) + 2 * pad
            tile = Image.new("L", (w, int(self.size * 2.2)), 0)
            ImageDraw.Draw(tile).text((pad, base), ch, font=self.font, fill=255, anchor="ls")
            tile = tile.rotate(key[1] / 4, resample=Image.BICUBIC, center=(pad, base))
            self._c[key] = (tile, pad, base)
        return self._c[key]


def render_pages(text: str, style_key: str, pages: int, seed: int | None = None) -> list[Image.Image]:
    style = STYLE_MAP[style_key]
    rng = random.Random(seed)
    font = _load_font(style)
    m = _Metrics(font, style.spacing)
    glyphs = _GlyphCache(font, style.size)
    max_w = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT
    capacity = (PAGE_H - MARGIN_TOP - MARGIN_BOTTOM) // style.line_gap
    chunks = paginate(wrap_text(text, m, max_w), pages, capacity)

    result = []
    for chunk in chunks:
        img = make_paper(style)
        for i, line in enumerate(chunk):
            if not line:
                continue
            baseline = MARGIN_TOP + i * style.line_gap + style.line_gap - 14
            x = MARGIN_LEFT + rng.uniform(-3, 8)
            shade = rng.randint(-12, 12)
            ink = tuple(max(0, min(255, c + shade)) for c in style.ink)
            phase = rng.uniform(0, 6.28)
            for k, ch in enumerate(line):
                adv = m.char(ch)
                if ch != " ":
                    angle = rng.uniform(-style.rotation, style.rotation)
                    tile, pad, base = glyphs.get(ch, angle)
                    dx = rng.uniform(-style.jitter, style.jitter)
                    dy = rng.uniform(-style.jitter, style.jitter) + style.wobble * math.sin(phase + k / 6)
                    img.paste(ink, (int(x - pad + dx), int(baseline - base + dy)), tile)
                x += adv + rng.uniform(-0.6, 0.9) * (1 + style.jitter / 2)
        result.append(img)
    return result


def build_outputs(text: str, style_key: str, pages: int, job_id: str | None = None) -> tuple[list[Path], Path]:
    job = job_id or uuid.uuid4().hex[:10]
    folder = OUT_DIR / job
    folder.mkdir(parents=True, exist_ok=True)
    imgs = render_pages(text, style_key, pages)
    jpgs = []
    for i, im in enumerate(imgs, 1):
        p = folder / f"husnixat_{i:02d}.jpg"
        im.save(p, "JPEG", quality=90, optimize=True)
        jpgs.append(p)
    pdf = folder / "husnixat.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    for p in jpgs:
        c.drawImage(str(p), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
    c.save()
    return jpgs, pdf


_sem = asyncio.Semaphore(2)  # bir vaqtda 2 tadan ortiq og'ir render bo'lmasin


async def generate(text: str, style_key: str, pages: int) -> tuple[list[Path], Path]:
    async with _sem:
        return await asyncio.to_thread(build_outputs, text, style_key, pages)


def cleanup(paths: list[Path]) -> None:
    for folder in {p.parent for p in paths}:
        shutil.rmtree(folder, ignore_errors=True)


SAMPLE = ("Assalomu alaykum! Bu husnixat namunasi. Ma'ruza matni shu ko'rinishda yoziladi: "
          "g'oya, o'zbek harflari va raqamlar 12345.")


def ensure_previews() -> dict[str, Path]:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for s in STYLES:
        p = PREVIEW_DIR / f"{s.key}.jpg"
        if not p.exists():
            im = render_pages(SAMPLE, s.key, 1, seed=7)[0].crop((0, 0, PAGE_W, 520))
            im.thumbnail((900, 900))
            im.save(p, "JPEG", quality=85)
        out[s.key] = p
    return out
