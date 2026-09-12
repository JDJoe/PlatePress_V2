"""Letter a plate after the sampler. Original file is not modified."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .parser import LetterBeat

CREAM = (245, 236, 214)
INK = (28, 22, 16)
RULE = (42, 34, 26)
PAPER_EDGE = (228, 216, 188)
BALLOON = (252, 248, 238)
FADE_INK = (96, 86, 74)
WHITE = (252, 248, 238)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    words = text.replace("\n", " \n ").split()
    lines: list[str] = []
    cur = ""
    for word in words:
        if word == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = word if not cur else f"{cur} {word}"
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def attach(image_path: Path, text: str, out_path: Path, bar_ratio: float = 0.22) -> Path:
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    margin = max(18, w // 60)
    fsize = max(18, w // 42)
    fnt = font(fsize)
    inner_w = max(8, w - 4 * margin)
    probe = ImageDraw.Draw(Image.new("RGB", (max(w, 8), 16)))
    raw_lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    lines: list[str] = []
    for ln in raw_lines:
        lines.extend(wrap(probe, ln, fnt, inner_w) or [ln])
    line_h = int(fsize * 1.35)
    block_h = line_h * max(len(lines), 1)
    pad_y = margin + 12
    bar_h = max(int(h * bar_ratio), 160, block_h + pad_y * 2)
    canvas = Image.new("RGB", (w, h + bar_h), CREAM)
    canvas.paste(im, (0, 0))

    draw = ImageDraw.Draw(canvas)
    box = (margin, h + margin // 2, w - margin, h + bar_h - margin // 2)
    draw.rectangle([0, h, w, h + 3], fill=RULE)
    draw.rectangle(box, outline=RULE, width=max(2, w // 500))
    draw.rectangle(
        [box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3],
        outline=PAPER_EDGE,
        width=1,
    )

    y = box[1] + ((box[3] - box[1]) - block_h) // 2
    for ln in lines:
        tw = draw.textlength(ln, font=fnt)
        x = box[0] + ((box[2] - box[0]) - tw) // 2
        draw.text((x, y), ln, font=fnt, fill=INK)
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    return out_path


def letter_plate(image_path: Path, beats: list[LetterBeat], out_path: Path) -> Path:
    """Draw caption boxes and balloons on a copy. Source file is left as-is."""
    src = Image.open(image_path).convert("RGB")
    canvas = src.copy()
    w, h = canvas.size
    draw = ImageDraw.Draw(canvas)
    m = max(14, w // 55)
    fsize = max(15, w // 52)
    fnt = font(fsize)
    line_h = int(fsize * 1.32)
    stroke = max(2, w // 420)

    caps_t = [b for b in beats if b.tag == "CAP_T"]
    caps_b = [b for b in beats if b.tag == "CAP_B"]
    speech = [b for b in beats if b.tag not in {"CAP_T", "CAP_B"}]

    top = m
    if caps_t:
        top = _caption_box(draw, w, h, caps_t, "top", fnt, line_h, m, stroke) + m
    bottom = h - m
    if caps_b:
        used = _caption_box(draw, w, h, caps_b, "bottom", fnt, line_h, m, stroke)
        bottom = h - used - m // 2

    _speech_balloons(draw, w, h, speech, fnt, line_h, m, top, bottom, stroke)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    return out_path


def _caption_box(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    beats: list[LetterBeat],
    edge: str,
    fnt,
    line_h: int,
    m: int,
    stroke: int,
) -> int:
    text = " ".join(b.text.strip() for b in beats if b.text.strip())
    if not text:
        return 0
    inner_w = max(8, w - 4 * m)
    lines: list[str] = []
    for ln in [text]:
        lines.extend(wrap(draw, ln, fnt, inner_w) or [ln])
    block_h = line_h * max(len(lines), 1)
    box_h = block_h + m
    y0 = m // 2 if edge == "top" else h - m // 2 - box_h
    box = (m, y0, w - m, y0 + box_h)
    draw.rectangle(box, fill=CREAM, outline=INK, width=stroke)
    draw.rectangle(
        [box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3],
        outline=PAPER_EDGE,
        width=1,
    )
    y = y0 + (box_h - block_h) // 2
    for ln in lines:
        tw = draw.textlength(ln, font=fnt)
        x = m + ((w - 2 * m) - tw) // 2
        draw.text((x, y), ln, font=fnt, fill=INK)
        y += line_h
    return box_h


def _measure(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int, line_h: int) -> tuple[list[str], int, int]:
    lines = wrap(draw, text, fnt, max(8, max_w)) or [text]
    tw = max((draw.textlength(ln, font=fnt) for ln in lines), default=0)
    return lines, int(tw), line_h * max(len(lines), 1)


def _speaker_x(speaker: str, slot: int, i: int, n: int, w: int) -> float:
    if slot == 1:
        return w * 0.30
    if slot == 2:
        return w * 0.70
    if slot >= 3:
        return w * min(0.82, 0.30 + 0.20 * (slot - 1))
    raw = (speaker or "").strip().lower()
    if raw.endswith("2") or raw.endswith("_2"):
        return w * 0.70
    if raw.endswith("1") or raw.endswith("_1"):
        return w * 0.30
    if n <= 1:
        return w * 0.50
    return w * (0.30 if i % 2 == 0 else 0.70)


def _tail_tip(
    tag: str,
    speaker: str,
    slot: int,
    i: int,
    w: int,
    h: int,
    cx: float,
    cy: float,
) -> tuple[float, float]:
    if tag == "OFFP":
        edge_x = 2.0 if cx < w / 2 else float(w - 3)
        return edge_x, cy + max(12, h * 0.04)
    tx = _speaker_x(speaker, slot, i, 2, w)
    ty = min(h * 0.80, cy + (h - cy) * 0.55)
    return tx, ty


def _star(cx: float, cy: float, r_out: float, r_in: float, n: int = 14) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _cloud_ellipses(cx: float, cy: float, bw: float, bh: float) -> list[tuple[float, float, float, float]]:
    return [
        (cx - bw * 0.35, cy - bh * 0.05, bw * 0.55, bh * 0.70),
        (cx + bw * 0.05, cy - bh * 0.18, bw * 0.58, bh * 0.72),
        (cx - bw * 0.08, cy + bh * 0.08, bw * 0.62, bh * 0.62),
        (cx + bw * 0.28, cy + bh * 0.02, bw * 0.42, bh * 0.55),
        (cx - bw * 0.48, cy + bh * 0.05, bw * 0.40, bh * 0.50),
    ]


def _dashed_ellipse(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[float, float, float, float],
    outline: tuple[int, int, int],
    width: int,
) -> None:
    x0, y0, x1, y1 = bbox
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    steps = 72
    dash, gap = 3, 2
    on = True
    n = 0
    pts: list[tuple[float, float]] = []
    for i in range(steps + 1):
        a = 2 * math.pi * i / steps
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    for i in range(len(pts) - 1):
        if on:
            draw.line([pts[i], pts[i + 1]], fill=outline, width=width)
        n += 1
        if on and n >= dash:
            on, n = False, 0
        elif not on and n >= gap:
            on, n = True, 0


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    fnt,
    line_h: int,
    cx: float,
    cy: float,
    fill: tuple[int, int, int],
) -> None:
    block_h = line_h * max(len(lines), 1)
    y = cy - block_h / 2
    for ln in lines:
        tw = draw.textlength(ln, font=fnt)
        draw.text((cx - tw / 2, y), ln, font=fnt, fill=fill)
        y += line_h


def _cell_rect(cell: int, w: int, h: int, pad: float) -> tuple[float, float, float, float]:
    """1 2 / 3 4 / 5 6 — left column odd, right column even, top to bottom."""
    cell = max(1, min(6, int(cell)))
    col = 0 if cell % 2 else 1
    row = (cell - 1) // 2
    cw, ch = w / 2.0, h / 3.0
    return (col * cw + pad, row * ch + pad, (col + 1) * cw - pad, (row + 1) * ch - pad)


def _resolve_cell(b: LetterBeat, i: int) -> int:
    if 1 <= (b.cell or 0) <= 6:
        return b.cell
    if b.slot == 2:
        return 2
    if b.slot == 1:
        return 1
    return 1 if i % 2 == 0 else 2


def _clamp_bbox(
    cx: float, cy: float, bw: float, bh: float, box: tuple[float, float, float, float]
) -> tuple[float, float, tuple[float, float, float, float]]:
    x0, y0, x1, y1 = box
    bw = min(bw, max(8, x1 - x0))
    bh = min(bh, max(8, y1 - y0))
    if cx - bw / 2 < x0:
        cx = x0 + bw / 2
    if cx + bw / 2 > x1:
        cx = x1 - bw / 2
    if cy - bh / 2 < y0:
        cy = y0 + bh / 2
    if cy + bh / 2 > y1:
        cy = y1 - bh / 2
    return cx, cy, (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)


def _speech_balloons(
    draw: ImageDraw.ImageDraw,
    w: int,
    h: int,
    beats: list[LetterBeat],
    fnt,
    line_h: int,
    m: int,
    top: float,
    bottom: float,
    stroke: int,
) -> None:
    n = len(beats)
    if not n:
        return
    pad = max(8, w // 90)
    for i, b in enumerate(beats):
        cell = _resolve_cell(b, i)
        x0, y0, x1, y1 = _cell_rect(cell, w, h, pad)
        cx = (x0 + x1) / 2
        cy = y0 + (y1 - y0) * 0.38
        if b.tag == "OFFP":
            cx = x0 + (x1 - x0) * (0.32 if cell % 2 else 0.68)
        max_w = max(48, int((x1 - x0) * 0.82))
        texts = [b.text]
        if b.tag == "NS2" and b.part2:
            texts = [b.text, b.part2]
        fill = INK if b.tag == "DARK" else BALLOON
        ink = WHITE if b.tag == "DARK" else (FADE_INK if b.tag == "FADE" else INK)
        if b.tag == "NS2" and len(texts) == 2:
            _draw_ns2(draw, texts, fnt, line_h, cx, cy, max_w, w, h, b, i, fill, ink, stroke, (x0, y0, x1, y1))
            continue
        lines, tw, th = _measure(draw, texts[0], fnt, max_w, line_h)
        bw = min(max(tw + 2 * pad, (x1 - x0) * 0.45), x1 - x0)
        bh = min(max(th + 2 * pad, (y1 - y0) * 0.28), (y1 - y0) * 0.62)
        if b.tag == "NSV":
            bw = min(bw, (x1 - x0) * 0.55)
            bh = max(bh, min(bw * 1.2, (y1 - y0) * 0.7))
        if b.tag in {"YELL", "ANN"}:
            bw = min(bw * 1.06, x1 - x0)
            bh = min(bh * 1.08, (y1 - y0) * 0.7)
        cx, cy, bbox = _clamp_bbox(cx, cy, bw, bh, (x0, y0, x1, y1))
        if b.tag == "OFFP":
            tip = (2.0 if cell % 2 else float(w - 3), cy)
        else:
            tip = ((x0 + x1) / 2, y1 - 2)
        _draw_shape(draw, b.tag, bbox, tip, fill, INK if b.tag != "FADE" else FADE_INK, stroke)
        _draw_text_block(draw, lines, fnt, line_h, cx, cy, ink)


def _draw_ns2(
    draw: ImageDraw.ImageDraw,
    texts: list[str],
    fnt,
    line_h: int,
    cx: float,
    cy: float,
    max_w: int,
    w: int,
    h: int,
    beat: LetterBeat,
    i: int,
    fill: tuple[int, int, int],
    ink: tuple[int, int, int],
    stroke: int,
    box: tuple[float, float, float, float] | None = None,
) -> None:
    pad = max(10, w // 90)
    boxes = []
    for k, t in enumerate(texts):
        lines, tw, th = _measure(draw, t, fnt, max(60, max_w // 2), line_h)
        bw = tw + 2 * pad
        bh = th + 2 * pad
        ox = cx + (-1 if k == 0 else 1) * (bw * 0.42)
        bbox = (ox - bw / 2, cy - bh / 2, ox + bw / 2, cy + bh / 2)
        boxes.append((bbox, lines, ox))
    if box:
        tip = ((box[0] + box[2]) / 2, box[3] - 2)
    else:
        tip = _tail_tip("NS", beat.speaker, beat.slot, i, w, h, cx, cy)
    right = boxes[1][0]
    base = ((right[0] + right[2]) / 2, right[3] - 2)
    draw.polygon(
        [(base[0] - 10, base[1]), (base[0] + 10, base[1]), tip],
        fill=fill,
        outline=INK,
    )
    for bbox, lines, ox in boxes:
        draw.ellipse(bbox, fill=fill, outline=INK, width=stroke)
        _draw_text_block(draw, lines, fnt, line_h, ox, cy, ink)


def _draw_shape(
    draw: ImageDraw.ImageDraw,
    tag: str,
    bbox: tuple[float, float, float, float],
    tip: tuple[float, float],
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    stroke: int,
) -> None:
    x0, y0, x1, y1 = bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = x1 - x0, y1 - y0
    if tag not in {"THINK", "DREAM"}:
        spread = bw * (0.14 if tag != "OFFP" else 0.10)
        draw.polygon(
            [(cx - spread, y1 - 3), (cx + spread, y1 - 3), tip],
            fill=fill,
            outline=outline,
        )
    if tag in {"YELL", "ANN"}:
        r_out = max(bw, bh) / 2
        r_in = r_out * (0.62 if tag == "YELL" else 0.55)
        n = 12 if tag == "YELL" else 16
        draw.polygon(_star(cx, cy, r_out, r_in, n), fill=fill, outline=outline)
        return
    if tag == "DREAM":
        for ex, ey, ew, eh in _cloud_ellipses(cx, cy, bw, bh):
            draw.ellipse([ex, ey, ex + ew, ey + eh], fill=fill, outline=outline, width=stroke)
        _thought_dots(draw, cx, y1, tip, fill, outline, stroke)
        return
    if tag == "THINK":
        draw.ellipse(bbox, fill=fill, outline=outline, width=stroke)
        _thought_dots(draw, cx, y1, tip, fill, outline, stroke)
        return
    if tag == "WHISP":
        draw.ellipse(bbox, fill=fill, outline=None)
        _dashed_ellipse(draw, bbox, outline, stroke)
        return
    if tag == "FADE":
        wobble = [
            (cx + (bw / 2) * math.cos(a) * (1.0 + 0.06 * math.sin(3 * a)),
             cy + (bh / 2) * math.sin(a) * (1.0 + 0.05 * math.cos(2 * a)))
            for a in [i * math.pi / 16 for i in range(32)]
        ]
        draw.polygon(wobble, fill=fill, outline=outline)
        return
    draw.ellipse(bbox, fill=fill, outline=outline, width=stroke)


def _thought_dots(
    draw: ImageDraw.ImageDraw,
    cx: float,
    y1: float,
    tip: tuple[float, float],
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
    stroke: int,
) -> None:
    x1, y2 = tip
    for t, r in ((0.35, 7), (0.62, 5), (0.88, 3.5)):
        x = cx + (x1 - cx) * t
        y = y1 + (y2 - y1) * t
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline, width=max(1, stroke - 1))
