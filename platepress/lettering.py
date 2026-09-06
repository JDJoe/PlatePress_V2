"""Attach a caption bar under a plate. Width unchanged. Height grows."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CREAM = (245, 236, 214)
INK = (28, 22, 16)
RULE = (42, 34, 26)
PAPER_EDGE = (228, 216, 188)


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
    bar_h = max(int(h * bar_ratio), 160)
    canvas = Image.new("RGB", (w, h + bar_h), CREAM)
    canvas.paste(im, (0, 0))

    draw = ImageDraw.Draw(canvas)
    margin = max(18, w // 60)
    box = (margin, h + margin // 2, w - margin, h + bar_h - margin // 2)
    draw.rectangle([0, h, w, h + 3], fill=RULE)
    draw.rectangle(box, outline=RULE, width=max(2, w // 500))
    draw.rectangle(
        [box[0] + 3, box[1] + 3, box[2] - 3, box[3] - 3],
        outline=PAPER_EDGE,
        width=1,
    )

    fsize = max(18, w // 42)
    fnt = font(fsize)
    inner_w = box[2] - box[0] - 2 * margin
    raw_lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    lines: list[str] = []
    for ln in raw_lines:
        lines.extend(wrap(draw, ln, fnt, inner_w) or [ln])

    line_h = int(fsize * 1.35)
    block_h = line_h * max(len(lines), 1)
    y = box[1] + ((box[3] - box[1]) - block_h) // 2
    for ln in lines:
        tw = draw.textlength(ln, font=fnt)
        x = box[0] + ((box[2] - box[0]) - tw) // 2
        draw.text((x, y), ln, font=fnt, fill=INK)
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    return out_path
