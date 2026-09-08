from __future__ import annotations

from platepress.defaults import ANDROID, AUGUR, STYLE, TAIL
from platepress.parser import (
    Character,
    assemble,
    assemble_pair,
    extract_inline_panes,
    pad_slug,
    parse_book,
    same_slug,
)

CAST = [
    Character(id="android", name="ANDROID", lock_text=ANDROID),
    Character(id="augur", name="AUGUR", lock_text=AUGUR),
]


def test_pad_slug_orders_p10_after_p1():
    assert pad_slug("p1_cargo") == "p001_cargo"
    assert pad_slug("p10_enough") == "p010_enough"
    assert pad_slug("t1_one") == "t001_one"
    assert pad_slug("p001_cargo") == "p001_cargo"
    assert same_slug("p1_cargo", "p001_cargo")
    assert pad_slug("p10_enough") > pad_slug("p1_cargo")


def test_preferred_wall_three_plates():
    wall = """
p1_cargo
braced in a narrow hold, both brown gloves on a sealed ox-hide crate lashed with pale straps, the crate seams gleaming like liquid silver

p2_claim
floating backward from an open hatch, one glove raised in refusal, cloaks peeling like gold leaf over black glass

p3_years
curled tight as if falling, the ox-hide crate tucked to her chest, the years tearing around her like wet silk into teal glass
"""
    caps = """
p1_cargo
She had been designed for beauty, order, and purpose.
Unfortunately, chaos had learned to fly.

p2_claim
You owe me, said Necessity.
She declined.

p3_years
The years did not ask.
"""
    r = parse_book(wall, caps, CAST)
    assert len(r.plates) == 3
    assert [p.slug for p in r.plates] == ["p1_cargo", "p2_claim", "p3_years"]
    assert r.plates[0].character_ids == ["ANDROID"]
    assert r.plates[0].named_ids == []
    assert r.plates[0].metaphor == "liquid silver"
    assert "\n" in r.plates[0].caption
    assert r.plates[0].caption.startswith("She had been designed")
    assert "ANDROID" not in r.plates[0].assembled.replace(ANDROID, "")
    assert r.plates[0].assembled.startswith("aethernouveau.")
    assert ANDROID in r.plates[0].assembled
    assert "braced in a narrow hold" in r.plates[0].assembled


def test_quoted_slug():
    wall = '''
"p1_cargo" braced in a narrow hold, the crate seams gleaming like liquid silver
"p2_claim"
floating backward, cloaks peeling like gold leaf over black glass
'''
    r = parse_book(wall, "", CAST)
    assert [p.slug for p in r.plates] == ["p1_cargo", "p2_claim"]
    assert "braced in a narrow hold" in r.plates[0].scene_text


def test_unnamed_plate_does_not_ask_for_a_still():
    wall = """
p11_cut
Behind her, the space starts to rip apart, both gauntlets wrenching the short sword sideways
"""
    r = parse_book(wall, "", CAST)
    p = r.plates[0]
    assert p.character_ids == ["ANDROID"]
    assert p.named_ids == []
    assert "Use image1" not in p.assembled
    assert "Keep the locked look" not in p.assembled
    assert ANDROID in p.assembled
    assert any("stills not attached" in w for w in r.warnings)


def test_android_token_stripped():
    wall = """
p1_cargo
{ANDROID} braced in a narrow hold, the crate seams gleaming like liquid silver
"""
    r = parse_book(wall, "", CAST)
    p = r.plates[0]
    assert p.character_ids == ["ANDROID"]
    assert p.named_ids == ["ANDROID"]
    assert "{ANDROID}" not in p.assembled
    assert "ANDROID" not in p.scene_text
    assert ANDROID in p.assembled


def test_twoshot_warning():
    wall = """
p6_ambrosia
ANDROID AUGUR crouched opposite each other over the opened ox-hide crate, the fat catching light like old enamel
"""
    r = parse_book(wall, "", CAST)
    p = r.plates[0]
    assert p.risky_twoshot
    assert p.character_ids == ["ANDROID", "AUGUR"]
    assert any("two-shot" in w for w in r.warnings)
    assert ANDROID in p.assembled and AUGUR in p.assembled


def test_caption_matches_padded_slug():
    wall = """
p01_dower
ANDROID
she sits on the gilt chair, enamel
"""
    caps = """
p1_dower
This is the last house that still employs her.
She is an android left in the salon.
"""
    r = parse_book(wall, caps, CAST)
    assert r.plates[0].slug == "p01_dower"
    assert "last house" in r.plates[0].caption


def test_caption_missing_slug_warns():
    wall = """
p1_cargo
braced in a narrow hold, liquid silver
"""
    caps = """
p1_cargo
ok

p9_ghost
no such plate
"""
    r = parse_book(wall, caps, CAST)
    assert len(r.plates) == 1
    assert any("p9_ghost" in w for w in r.warnings)


def test_empty_caption_allowed():
    wall = """
p1_cargo
braced in a narrow hold, liquid silver
"""
    r = parse_book(wall, "", CAST)
    assert r.plates[0].caption == ""


def test_double_style_stripped():
    wall = f"""
p1_cargo
{STYLE} braced in a narrow hold, liquid silver.{TAIL}
"""
    r = parse_book(wall, "", CAST, tail=TAIL)
    p = r.plates[0]
    assert p.assembled.count("aethernouveau.") == 1
    assert any("aethernouveau" in w for w in p.warnings)


def test_any_metaphor_is_kept():
    wall = """
p1_crate
braced in a narrow hold, the crate seams like rusted bronze
"""
    r = parse_book(wall, "", CAST)
    p = r.plates[0]
    assert "rusted bronze" in p.scene_text
    assert "rusted bronze" in p.assembled
    assert not any("banned" in w.lower() for w in p.warnings)


def test_t1_smoke_pair():
    wall = """
t1_one
braced in a narrow hold, both brown gloves on a sealed ox-hide crate, the crate seams gleaming like liquid silver.

t1_two
braced in a narrow hold, both brown gloves on a sealed ox-hide crate, the crate seams gleaming like liquid silver, the hull behind her peeling like gold leaf over black glass.
"""
    r = parse_book(wall, "", CAST)
    assert [p.slug for p in r.plates] == ["t1_one", "t1_two"]
    assert r.plates[0].metaphor == "liquid silver"
    assert r.plates[1].metaphor == "gold leaf over black glass"
    assert r.plates[0].assembled.startswith(STYLE)
    assert ANDROID in r.plates[0].assembled
    assert r.plates[0].assembled.rstrip(".").endswith("liquid silver")
    assert TAIL.strip() not in r.plates[0].assembled


def test_blank_line_inside_body():
    wall = """
p1_cargo
braced in a narrow hold,

the crate seams gleaming like liquid silver
"""
    r = parse_book(wall, "", CAST)
    assert "narrow hold" in r.plates[0].scene_text
    assert "liquid silver" in r.plates[0].scene_text


def test_vessel_words_become_spacecraft():
    from platepress.parser import _spacecraft

    assert _spacecraft("a fleet of thin pale ships") == "a fleet of thin pale spacecraft"
    assert _spacecraft("spaceship ribs") == "spacecraft ribs"
    assert _spacecraft("starships filling the sky") == "spacecraft filling the sky"
    assert "spacesuit" in _spacecraft("in an opaque sleek spacesuit")
    text = assemble(STYLE, [ANDROID], "looking up at pale ships", TAIL)
    assert "ship" not in text.lower().replace("spacesuit", "")
    assert "spacecraft" in text


def test_assemble_shape():
    text = assemble(STYLE, [ANDROID], "braced in a hold, liquid silver", TAIL)
    assert text.startswith(STYLE)
    assert ANDROID in text
    assert "braced in a hold" in text
    assert "No logos." in text
    assert "Keep the locked look" not in text
    assert text.find(TAIL.strip()) < text.find("braced in a hold")
    assert text.find(ANDROID) < text.find("braced in a hold")
    blank = assemble(STYLE, [ANDROID], "braced in a hold, liquid silver", "")
    assert "No empty studio" not in blank
    assert blank.rstrip(".").endswith("liquid silver")


def test_lock_omitted_when_a_still_is_attached():
    text = assemble(STYLE, [ANDROID], "braced in a hold, liquid silver", "", n_pictures=1)
    assert ANDROID not in text
    assert "braced in a hold" in text


def test_picture_slots_stay_out_of_the_prompt():
    text = assemble(STYLE, [ANDROID], "braced in a hold, liquid silver", TAIL, n_pictures=1, cutout=True)
    assert "Use image1" not in text
    assert "Stills are cutouts" not in text
    assert "braced in a hold" in text
    custom = assemble(
        STYLE, [ANDROID], "braced in a hold, liquid silver", TAIL,
        n_pictures=1, cutout=True, cutout_text="The still is a paper doll.",
    )
    assert "paper doll" not in custom


def test_picture_slots_two_bodies():
    text = assemble(STYLE, [ANDROID, AUGUR], "two figures, enamel", TAIL, n_pictures=2)
    assert "Use image1" not in text
    assert "Use image2" not in text
    assert "two figures" in text


def test_assemble_pair_two_prompts():
    text = assemble_pair(
        STYLE,
        [ANDROID],
        "hauling a crate in the cargo bay, liquid silver",
        [ANDROID],
        "facing colossal figures in the mist, gold leaf over black glass",
        TAIL,
        n_left_refs=1,
        n_right_refs=1,
    )
    assert "two equal vertical panes" in text
    assert "Left pane:" in text and "cargo bay" in text
    assert "Right pane:" in text and "mist" in text
    assert "Use image1" not in text
    assert ANDROID not in text
    assert text.find("cargo bay") < text.find("mist")
    assert "two different scenes" in text
    no_stills = assemble_pair(
        STYLE,
        [ANDROID],
        "hauling a crate in the cargo bay, liquid silver",
        [ANDROID],
        "facing colossal figures in the mist, gold leaf over black glass",
        "",
        n_left_refs=0,
        n_right_refs=0,
    )
    assert ANDROID in no_stills
    assert no_stills.find("Left pane:") < no_stills.find("Right pane:")


def test_extract_inline_panes():
    left, right = extract_inline_panes(
        "Left pane, hauling a crate in the cargo bay, liquid silver "
        "right pane: tumbling toward the hatch, gold leaf over black glass"
    )
    assert "cargo bay" in left and "hatch" in right
    assert extract_inline_panes("just a cargo bay") is None


def test_split_units_one_selection_uses_next_on_wall():
    from platepress.app import _split_units

    class P:
        def __init__(self, slug):
            self.slug = slug

    all_p = [P("p1_cargo"), P("p2_claim"), P("p3_years")]
    units, skipped, msg = _split_units([all_p[0]], all_p)
    assert skipped == 0 and msg == ""
    assert units[0][0].slug == "p1_cargo" and units[0][1].slug == "p2_claim"


def test_parse_split_pairs_consecutive_prompts():
    wall = """
p1_cargo
hauling a crate, liquid silver

p2_claim
facing figures in the mist, gold leaf over black glass

p3_years
falling, wet silk into teal glass
"""
    r = parse_book(wall, "", CAST, layout="split")
    assert r.plates[0].pane == "left"
    assert r.plates[0].pair_with == "p2_claim"
    assert r.plates[1].pane == "right"
    assert r.plates[1].pair_with == "p1_cargo"
    assert "crate" in r.plates[0].assembled and "mist" in r.plates[0].assembled
    assert r.plates[0].assembled == r.plates[1].assembled
    assert r.plates[2].pane == ""
    assert any("no pair" in w for w in r.warnings)


def test_parse_inline_panes_does_not_eat_next_slug():
    wall = """
p1_cargo
ANDROID
Left pane, hauling a crate, liquid silver
right pane: tumbling toward the hatch, gold leaf over black glass

p2_claim
Red mist, weird shadows, wet silk into teal glass
"""
    r = parse_book(wall, "", CAST, layout="split")
    assert r.plates[0].pane == "inline"
    assert "crate" in r.plates[0].assembled and "hatch" in r.plates[0].assembled
    left_i = r.plates[0].assembled.lower().find("left pane:")
    right_i = r.plates[0].assembled.lower().find("right pane:")
    crate_i = r.plates[0].assembled.find("crate")
    hatch_i = r.plates[0].assembled.find("hatch")
    assert left_i < crate_i < right_i < hatch_i
    assert "Red mist" not in r.plates[0].assembled


def test_one_scene_inline_does_not_split_the_rest():
    wall = """
p1_dower
ANDROID
left pane: She sits on the gilt chair, enamel
right pane: PATRON looks down from the portrait, gold leaf

p2_clock
ANDROID
She walks to the mantel and turns the clock, stained glass
"""
    r = parse_book(wall, "", CAST, layout="one")
    assert r.plates[0].pane == "inline"
    assert "gilt chair" in r.plates[0].assembled and "portrait" in r.plates[0].assembled
    assert r.plates[1].pane == ""
    assert "Left pane:" not in r.plates[1].assembled
    assert "two equal vertical panes" not in r.plates[1].assembled
    assert "mantel" in r.plates[1].assembled


def test_assemble_clauses_are_sentences():
    text = assemble(STYLE, [ANDROID], "standing amidst the wreckage", TAIL)
    assert "no second panel. " in text
    assert "no second panel standing" not in text
    assert ". standing amidst" in text


def test_assemble_wall_after_settings():
    text = assemble(STYLE, [ANDROID], "hauling the wreck, liquid silver", TAIL)
    assert ANDROID in text
    assert text.find(STYLE[:20]) < text.find("hauling the wreck")
    assert text.find(TAIL.strip()[:20]) < text.find("hauling the wreck")
    pair = assemble_pair(
        STYLE,
        [ANDROID],
        "hauling the wreck",
        [AUGUR],
        "in the cockpit",
        TAIL,
    )
    assert ANDROID in pair and AUGUR in pair
    assert pair.find("hauling the wreck") < pair.find("in the cockpit")


def test_inline_panes_locks_per_side():
    wall = """
p1_dower
ANDROID
left pane: She sits still on the gilt salon chair, stockings like enamel
right pane: PATRON He looks down from the cracked oil portrait, gold leaf on the frame
"""
    r = parse_book(wall, "", CAST, layout="split")
    p = r.plates[0]
    assert p.pane == "inline"
    assert p.pane_left_ids == ["ANDROID"]
    assert "PATRON" not in p.pane_right_ids
    asm = p.assembled
    chair = asm.find("gilt salon chair")
    portrait = asm.find("cracked oil portrait")
    left_lock = asm.find(ANDROID, chair)
    assert chair < portrait
    assert left_lock == -1 or left_lock < portrait or ANDROID not in asm[portrait:]
