from __future__ import annotations

from pathlib import Path

from PIL import Image

from platepress.lettering import attach, letter_plate
from platepress.parser import LetterBeat


def test_letter_grows_height_keeps_width(tmp_path: Path):
    src = tmp_path / "p1_cargo_1.png"
    Image.new("RGB", (320, 240), (10, 10, 10)).save(src)
    out = tmp_path / "p1_cargo_1_lettered.png"
    attach(src, "She declined.\nThe crate did not care.", out)
    im = Image.open(out)
    assert im.size[0] == 320
    assert im.size[1] > 240


def test_letter_grows_bar_for_long_caption(tmp_path: Path):
    src = tmp_path / "p1_cargo_1.png"
    Image.new("RGB", (320, 240), (10, 10, 10)).save(src)
    out = tmp_path / "p1_cargo_1_lettered.png"
    lines = "\n".join(f"Caption line {i} is a full moral." for i in range(12))
    attach(src, lines, out)
    im = Image.open(out)
    assert im.size[0] == 320
    assert im.size[1] > 240 + 160


def test_cell_grid_is_two_by_three():
    from platepress.lettering import _cell_rect, _resolve_cell

    assert _cell_rect(1, 100, 90, 0) == (0, 0, 50, 30)
    assert _cell_rect(2, 100, 90, 0) == (50, 0, 100, 30)
    assert _cell_rect(3, 100, 90, 0) == (0, 30, 50, 60)
    assert _cell_rect(6, 100, 90, 0) == (50, 60, 100, 90)
    b = LetterBeat(tag="NS", text="x", slot=2)
    assert _resolve_cell(b, 0) == 2
    b = LetterBeat(tag="NS", text="x", cell=6)
    assert _resolve_cell(b, 0) == 6


def test_letter_plate_keeps_source_and_size(tmp_path: Path):
    src = tmp_path / "p02_treasure.png"
    Image.new("RGB", (640, 480), (40, 80, 40)).save(src)
    before = src.read_bytes()
    out = tmp_path / "p02_treasure_lettered.png"
    beats = [
        LetterBeat(tag="CAP_B", text="The capsules were unmarked."),
        LetterBeat(tag="NS", text="We should sell them.", speaker="AUGUR"),
        LetterBeat(tag="NSV", text="Why the armed guard?", speaker="ANDROID"),
    ]
    letter_plate(src, beats, out)
    assert src.read_bytes() == before
    lettered = Image.open(out)
    original = Image.open(src)
    assert lettered.size == original.size
    assert lettered.tobytes() != original.tobytes()
