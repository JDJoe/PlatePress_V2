from __future__ import annotations

from platepress.defaults import ANDROID, AUGUR, STYLE, TAIL
from platepress.parser import (
    Character,
    assemble,
    assemble_pair,
    extract_inline_panes,
    locks_for_scene,
    pad_slug,
    parse_book,
    parse_caption_lettering,
    parse_wall,
    render_lettering,
    same_slug,
)

CAST = [
    Character(id="android", name="ANDROID", lock_text=ANDROID),
    Character(id="augur", name="AUGUR", lock_text=AUGUR),
]


def _text_on(wall, characters=CAST):
    names = [c.name for c in characters]
    return {s: True for s, _ in parse_wall(wall, names)}


def parse_on(wall, caps="", characters=CAST, **kw):
    kw.setdefault("use_text_for", _text_on(wall, characters))
    return parse_book(wall, caps, characters, **kw)


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
    assert r.plates[0].character_ids == []
    assert r.plates[0].named_ids == []
    assert r.plates[0].metaphor == "liquid silver"
    assert "\n" in r.plates[0].caption
    assert r.plates[0].caption.startswith("She had been designed")
    assert "She had been designed for beauty" not in r.plates[0].assembled
    assert "rectangular caption box" in r.plates[0].lettering_prompt
    assert "ANDROID" not in r.plates[0].assembled.replace(ANDROID, "")
    assert r.plates[0].assembled.startswith("aethernouveau.")
    assert ANDROID not in r.plates[0].assembled
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
    assert p.character_ids == []
    assert p.named_ids == []
    assert "Use image1" not in p.assembled
    assert ANDROID not in p.assembled
    assert not any("stills not attached" in w for w in r.warnings)


def test_android_token_stripped():
    wall = """
p1_cargo
{ANDROID} braced in a narrow hold, the crate seams gleaming like liquid silver
"""
    r = parse_on(wall, "", CAST)
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
    r = parse_on(wall, "", CAST)
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


def test_letter_column_sends_caption_onto_the_plate():
    wall = """
p02_treasure
a cargo hold, liquid silver
"""
    caps = """
p02_treasure
CAP_B: The capsules were unmarked.
NS_6: PILOT2 suggested selling them.
"""
    r = parse_book(wall, caps, CAST, use_letter_for={"p02_treasure": True})
    p = r.plates[0]
    assert p.use_letter is True
    assert "The capsules were unmarked" in p.assembled
    assert "bottom-right sixth" in p.assembled
    assert "Do not grow the canvas" in p.assembled
    off = parse_book(wall, caps, CAST)
    assert "The capsules were unmarked" not in off.plates[0].assembled


def test_untagged_captions_go_to_the_model():
    wall = """
p1_cargo
braced in a narrow hold, liquid silver
"""
    caps = """
p1_cargo
She had been designed for beauty, order, and purpose.
The crate did not care.
"""
    r = parse_book(wall, caps, CAST)
    p = r.plates[0]
    assert "She had been designed for beauty" not in p.assembled
    assert "She had been designed for beauty" in p.lettering_prompt
    assert "The crate did not care" in p.lettering_prompt
    assert "CAP_B:" not in p.assembled
    assert p.caption_bar.startswith("She had been designed")


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
    assert r.plates[0].character_ids == []
    assert ANDROID not in r.plates[0].assembled
    assert r.plates[0].assembled.rstrip(".").endswith("liquid silver")
    assert TAIL.strip() not in r.plates[0].assembled


def test_blank_line_inside_body():
    wall = """
p1_cargo
braced in a narrow hold,

the crate seams gleaming like liquid silver
"""
    r = parse_book(wall, "", CAST)
    scene = r.plates[0].scene_text
    assert "narrow hold" in scene
    assert "liquid silver" in scene
    assert "hold,." not in scene
    assert "hold. the crate" in scene


def test_text_on_replaces_character1_with_lock():
    cast = [Character(id="c", name="Celine", lock_text="A blond 30 year old")]
    wall = """
p001_bed
CHARACTER1 is Celine

Celine, a woman with focused expression, turns a brass dial on the bedside table with two fingers.
"""
    r = parse_book(wall, "", cast, use_text_for={"p001_bed": True})
    p = r.plates[0]
    assert p.use_text is True
    assert "CHARACTER1" not in p.scene_text
    assert "CHARACTER1" not in p.assembled
    assert p.scene_text.startswith("A blond 30 year old is Celine.")
    assert "Celine, a woman with focused expression" in p.scene_text
    assert "A blond 30 year old is Celine." in p.assembled


def test_text_default_on_expands_without_per_slug_opt():
    cast = [Character(id="c", name="Celine", lock_text="A blond 30 year old")]
    wall = """
p001_bed
CHARACTER1 is Celine
Celine, a woman with focused expression, turns a brass dial.
"""
    r = parse_book(wall, "", cast, text_default=True)
    p = r.plates[0]
    assert p.use_text is True
    assert "CHARACTER1" not in p.assembled
    assert "A blond 30 year old is Celine." in p.assembled


def test_character_lock_line_does_not_glue_to_name():
    wall = """
p001_bed
CHARACTER1 is Celine

Celine, a woman with focused expression, turns a brass dial on the bedside table with two fingers.
"""
    r = parse_book(wall, "", CAST)
    p = r.plates[0]
    assert "CHARACTER1 is Celine Celine" not in p.scene_text
    assert "CHARACTER1 is Celine Celine" not in p.assembled
    assert "CHARACTER1 is Celine." in p.scene_text
    assert "Celine, a woman with focused expression" in p.scene_text
    assert "CHARACTER1 is Celine." in p.assembled


def test_character_lock_line_split_without_blank():
    wall = """
p01_heist
CHARACTER1 is Anna
SHOT: Wide action shot inside a cargo bay.
ACTION: Anna is forcing open the alien container.
"""
    r = parse_book(wall, "", CAST)
    scene = r.plates[0].scene_text
    assert "CHARACTER1 is Anna." in scene
    assert "SHOT: Wide action shot" in scene
    assert "CHARACTER1 is Anna SHOT" not in scene
    assert "CHARACTER1 is Anna. SHOT" in scene


def test_image_on_without_pilot_uses_first_cast_still():
    still = Character(
        id="p1",
        name="PILOT1",
        lock_text="",
        ref_images=["/tmp/pingpong.png"],
        ref_active="/tmp/pingpong.png",
    )
    wall = """
p04_ridge
KEEP the same woman from image1, her name is PingPong
REFERENCE: use picture1 for costume only. Ignore background, pose, objects, and composition from the reference.
"""
    r = parse_book(wall, "", [still], use_image_for={"p04_ridge": True})
    p = r.plates[0]
    assert p.named_ids == ["PILOT1"]
    assert "picture1" not in p.assembled
    assert "image1" in p.assembled
    assert "for costume only" not in p.assembled.lower()
    assert any("no PILOT1" in w for w in p.warnings)


def test_picture1_becomes_image1_and_warns():
    wall = """
p04_ridge
KEEP the same woman from image1, her name is PingPong
REFERENCE: use picture1 for costume only. Ignore background, pose, objects, and composition from the reference.
ACTION: PingPong drops behind the ridge.
"""
    r = parse_book(wall, "", CAST, use_image_for={"p04_ridge": True})
    p = r.plates[0]
    assert "picture1" not in p.assembled
    assert "image1" in p.assembled
    off = parse_book(wall, "", CAST)
    assert any("Image is off" in w for w in off.plates[0].warnings)


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
    from platepress.defaults import REF_CUTOUT

    text = assemble(STYLE, [ANDROID], "braced in a hold, liquid silver", TAIL, n_pictures=1, cutout=True, cutout_text=REF_CUTOUT)
    assert "Use image1" not in text
    assert "Stills are cutouts" in text
    assert "braced in a hold" in text
    custom = assemble(
        STYLE, [ANDROID], "braced in a hold, liquid silver", TAIL,
        n_pictures=1, cutout=True, cutout_text="The still is a paper doll.",
    )
    assert "paper doll" in custom
    no_still = assemble(
        STYLE, [ANDROID], "braced in a hold, liquid silver", TAIL,
        n_pictures=0, cutout=True, cutout_text="The still is a paper doll.",
    )
    assert "paper doll" not in no_still


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
    r = parse_on(wall, "", CAST, layout="split")
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


def test_character1_is_cast_slot_one_alias_is_writer_text():
    wall = """
p01_heist
CHARACTER1 is Anna
SHOT: Wide action shot inside a cargo bay.
ACTION: Anna is forcing open the alien container.
"""
    r = parse_on(wall, "", CAST)
    p = r.plates[0]
    assert p.character_ids == ["ANDROID"]
    assert p.named_ids == ["ANDROID"]
    assert ANDROID in p.scene_text
    assert "CHARACTER1" not in p.scene_text
    assert "is Anna" in p.scene_text
    assert "Anna is forcing" in p.scene_text
    assert ANDROID in p.assembled
    assert "KEEP the woman same" not in p.assembled


def test_pilot1_as_cast_name_stays_in_the_wall():
    cast = [Character(id="p1", name="PILOT1", lock_text="")]
    wall = """
p02_treasure
PILOT1 is PingPong
REFERENCE: use picture1 for costume only.
"""
    r = parse_book(wall, "", cast, use_text_for={"p02_treasure": True})
    p = r.plates[0]
    assert "PILOT1 is PingPong" in p.scene_text
    assert "PILOT1 is PingPong" in p.assembled
    assert not p.assembled.strip().endswith("panel. is PingPong")
    assert "KEEP the same woman" not in p.assembled


def test_character1_is_replaced_lock_rest_kept():
    wall = """
p01_heist
CHARACTER1 is Anna and she is now wearing a blue space suit.
"""
    r = parse_on(wall, "", CAST)
    scene = r.plates[0].scene_text
    assert scene == f"{ANDROID} is Anna and she is now wearing a blue space suit."
    assert "CHARACTER1" not in scene


def test_pilot1_alias_and_keep_lines_when_stills_on():
    wall = """
p01_heist
PILOT1 = Anna. Use picture1 for Anna's costume only.
ACTION: Anna is forcing open the container.
"""
    r = parse_on(
        wall, "", CAST,
        n_pictures_for={"p01_heist": 1},
        use_image_for={"p01_heist": True},
    )
    p = r.plates[0]
    assert p.named_ids == ["ANDROID"]
    assert ANDROID in p.assembled
    assert "CHARACTER1" not in p.assembled and "PILOT1" not in p.assembled
    assert "KEEP the woman same" not in p.assembled
    assert "Anna is forcing" in p.assembled


def test_character2_two_slots():
    wall = """
p01_heist
CHARACTER1 is Anna
CHARACTER2 is Betty
ACTION: Anna cuts. Betty watches the door.
"""
    r = parse_on(wall, "", CAST)
    p = r.plates[0]
    assert p.character_ids == ["ANDROID", "AUGUR"]
    assert ANDROID in p.scene_text
    assert AUGUR in p.scene_text
    assert "Anna cuts" in p.scene_text
    assert "Betty watches" in p.scene_text
    assert "CHARACTER1" not in p.assembled
    assert "CHARACTER2" not in p.assembled


def test_use_text_off_strips_character_token_no_lock():
    wall = """
p01_heist
CHARACTER1 is Anna and she is now wearing a blue space suit.
ACTION: empty cargo bay, no people.
"""
    r = parse_book(wall, "", CAST, use_text_for={"p01_heist": False}, use_image_for={"p01_heist": False})
    p = r.plates[0]
    assert "CHARACTER1 is Anna" in p.assembled
    assert ANDROID not in p.assembled
    assert "blue space suit" in p.scene_text
    assert p.use_text is False
    assert p.use_image is False
    assert p.character_ids == []


def test_use_image_without_text_keeps_keep_line():
    wall = """
p01_heist
CHARACTER1 is Anna
ACTION: Anna opens the crate.
"""
    r = parse_book(
        wall, "", CAST,
        use_text_for={"p01_heist": False},
        use_image_for={"p01_heist": True},
        n_pictures_for={"p01_heist": 1},
    )
    p = r.plates[0]
    assert "CHARACTER1 is Anna" in p.scene_text
    assert "image1 is Anna" not in p.scene_text
    assert "KEEP the woman same" not in p.assembled
    assert p.use_image is True
    assert p.named_ids == ["ANDROID"]


def test_text_and_image_same_prompt_as_text():
    wall = """
p01_heist
CHARACTER1 is PingPong
KEEP the same woman from image1, her name is PingPong
"""
    text_only = parse_book(wall, "", CAST, use_text_for={"p01_heist": True})
    both = parse_book(
        wall, "", CAST,
        use_text_for={"p01_heist": True},
        use_image_for={"p01_heist": True},
        n_pictures_for={"p01_heist": 1},
    )
    t, b = text_only.plates[0], both.plates[0]
    assert ANDROID in t.scene_text and ANDROID in b.scene_text
    assert "is PingPong" in t.assembled and "is PingPong" in b.assembled
    assert "CHARACTER1" not in t.assembled and "CHARACTER1" not in b.assembled
    assert b.named_ids == ["ANDROID"]
    assert "KEEP the same woman from image1" in b.assembled


def test_text_column_defaults_off():
    wall = """
p01_heist
CHARACTER1 is Anna
ACTION: Anna opens the crate.
"""
    r = parse_book(wall, "", CAST)
    p = r.plates[0]
    assert p.use_text is False
    assert p.use_image is False
    assert p.character_ids == []
    assert ANDROID not in p.scene_text
    assert "CHARACTER1 is Anna" in p.scene_text


def test_locks_for_scene_skips_embedded_character1():
    by = {c.name: c for c in CAST}
    embedded = f"{ANDROID} is Anna in the bay"
    assert locks_for_scene(["ANDROID"], by, embedded, True) == []
    stripped = "braced in a hold, liquid silver"
    locks = locks_for_scene(["ANDROID"], by, stripped, True)
    assert locks == [ANDROID]
    assert locks_for_scene(["ANDROID"], by, stripped, False) == []


def test_caption_tags_are_not_slugs():
    wall = """
p02_treasure
ANDROID
a cargo hold, liquid silver
"""
    caps = """
p02_treasure
CAP_B: The capsules were beautiful, warm, and completely unmarked.
NS: PILOT2 suggested selling them.
NSV: PILOT1 suggested finding out why someone was transporting them under armed guard.
"""
    r = parse_on(wall, caps, CAST)
    assert len(r.plates) == 1
    p = r.plates[0]
    assert p.slug == "p02_treasure"
    assert "CAP_B:" not in p.assembled
    assert "The capsules were beautiful" not in p.assembled
    assert "The capsules were beautiful" in p.lettering_prompt
    assert "suggested selling them" in p.lettering_prompt
    assert "rectangular caption box along the bottom" in p.lettering_prompt
    assert "tall oval speech balloon" in p.lettering_prompt
    assert p.caption_bar == ""
    assert "suggested selling" in p.lettering_prompt


def test_caption_tag_speaker_colon_and_bar_kept():
    wall = """
p02_treasure
a cargo hold, liquid silver
"""
    caps = """
p02_treasure
She had been designed for beauty.
NS: PILOT2: We should sell them.
NS2: Speech in | two parts
"""
    r = parse_book(wall, caps, CAST)
    p = r.plates[0]
    assert p.caption_bar == "She had been designed for beauty."
    assert "We should sell them" not in p.assembled
    assert "We should sell them" in p.lettering_prompt
    assert "tail points at AUGUR" in p.lettering_prompt
    assert "First balloon exactly" in p.lettering_prompt
    assert "two parts" in p.lettering_prompt


def test_ns_cell_is_not_a_slug_and_parses():
    wall = """
p02_treasure
a cargo hold, liquid silver
"""
    caps = """
p02_treasure
NS_6: PILOT2 suggested selling them.
NS_1: PILOT1: Then why the guard?
"""
    r = parse_book(wall, caps, CAST)
    assert [p.slug for p in r.plates] == ["p02_treasure"]
    beats, bar = parse_caption_lettering(
        "NS_6: PILOT2 suggested selling them.\nNS_1: PILOT1: Then why the guard?",
        CAST,
    )
    assert bar == ""
    assert beats[0].tag == "NS" and beats[0].cell == 6
    assert "suggested selling" in beats[0].text
    assert beats[1].tag == "NS" and beats[1].cell == 1
    assert beats[1].slot == 1
    assert beats[1].text == "Then why the guard?"


def test_speech_speaker_keeps_cast_slot():
    beats, _ = parse_caption_lettering(
        "NS: PILOT2: We should sell them.\nNSV: PILOT1: Then why the guard?\nNS: AUGUR: Again.",
        CAST,
    )
    assert [b.slot for b in beats] == [2, 1, 2]
    assert beats[0].speaker == "AUGUR"
    assert beats[1].speaker == "ANDROID"
    assert beats[0].text == "We should sell them."


def test_parse_caption_lettering_shapes():
    beats, bar = parse_caption_lettering(
        "CAP_T: Earlier.\nYELL: Get down!\nWHISP: Don't turn.\nTHINK: Not the crate.\n",
        CAST,
    )
    assert bar == ""
    tags = [b.tag for b in beats]
    assert tags == ["CAP_T", "YELL", "WHISP", "THINK"]
    text = render_lettering(beats)
    assert "top edge" in text
    assert "spiky burst" in text
    assert "dashed outline" in text
    assert "thought balloon" in text


def test_lettering_strips_no_text_from_layout():
    from platepress.defaults import LAYOUT_SPLIT

    text = assemble_pair(
        STYLE,
        [ANDROID],
        "left hold",
        [AUGUR],
        "right mist",
        "Sharp and in focus. No text. No logos.",
        layout_text=LAYOUT_SPLIT,
        lettering='Draw a normal oval speech balloon. Hand-lettered ink inside, exactly: "Go."',
    )
    assert "no speech balloons" not in text.lower()
    assert "No text." not in text
    assert "No logos." in text
    assert 'exactly: "Go."' in text
