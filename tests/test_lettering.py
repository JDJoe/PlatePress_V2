from __future__ import annotations

from pathlib import Path

from PIL import Image

from platepress.lettering import attach


def test_letter_grows_height_keeps_width(tmp_path: Path):
    src = tmp_path / "p1_cargo_1.png"
    Image.new("RGB", (320, 240), (10, 10, 10)).save(src)
    out = tmp_path / "p1_cargo_1_lettered.png"
    attach(src, "She declined.\nThe crate did not care.", out)
    im = Image.open(out)
    assert im.size[0] == 320
    assert im.size[1] > 240
