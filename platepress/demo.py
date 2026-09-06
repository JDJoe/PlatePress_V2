"""Bos Sidereal demo + t1 smoke walls. No images required."""

from __future__ import annotations

from .defaults import ANDROID, AUGUR, T1_ONE_SCENE, T1_TWO_SCENE

DEMO_CAST = [
    {
        "id": "android",
        "name": "ANDROID",
        "lock_text": ANDROID,
        "ref_images": [],
        "locked_seed": None,
        "notes": "",
    },
    {
        "id": "augur",
        "name": "AUGUR",
        "lock_text": AUGUR,
        "ref_images": [],
        "locked_seed": None,
        "notes": "",
    },
]

BOS_PROMPTS = """\
p1_cargo
ANDROID
seen over her left shoulder, three-quarter from behind, hauling a sealed ox-hide crate along a receding cargo bay of ribbed bulkheads and stacked drums, helmet turned to the crate not the aisle, a slit of rust light at the far hatch, pale straps biting the ox-hide, the crate seams gleaming like liquid silver

p2_claim
ANDROID
tumbling away from the bay toward a round open hatch, body in profile, one brown glove raised in refusal at the threshold, facing colossal faceless figures waiting in the mist, spacecraft ribs and dangling straps still in the foreground, their cloaks peeling like gold leaf over black glass

p3_years
ANDROID
falling past a canyon of torn hours, the crown of the bubble helmet nearest, face toward the crate hugged to her chest, knees drawn, a rust landscape breaking into strips above and below, the years tearing around her like wet silk into teal glass

p4_augur
AUGUR
arriving in profile on a rust-red basin under a low ochre sky, one boot still inside a circular wound hanging over cracked salt pans and distant mesas, bronze knife held flat, helmet turned to the plain not the wound, the wound in the air a spiderweb of black cells

p5_embargo
ANDROID
small on a rust slope, body twisted away, one glove shielding the helmet visor as she looks up-slope at a fleet of needle-hull spacecraft hanging in the ochre sky, dunes and wreck ribs running to the horizon, their hulls a stained-glass lattice of black cells

p6_ambrosia
ANDROID AUGUR
in profile in a rust hollow at dusk, crouched opposite over the opened ox-hide crate between dune shadows and a dead landing strut, faces toward the meat and the dusk, a dark cut of Earth beef on the bronze knife, the fat catching the last light like old enamel

p7_battle
ANDROID
from behind, punching through a collapsing enemy corridor that recedes in torn frames, one boot on buckled plating, helmet aimed at the breach not back down the hall, sparks and debris filling the depth, the hull bursting into teal stained glass around her glove

p8_hold
ANDROID AUGUR
side-on at a vertical crack of hours splitting a rust cliff, she hauling one luminous edge shut with both brown gloves, he in profile shouldering the crate through the gap toward a pale terrace beyond, the crack splitting as luminous stained glass

p9_altar
ANDROID
walking away down a long stone terrace between worn columns, crate already set on a low altar at the far end, too many pale suns stacked over a drop into ochre haze, her helmet toward the altar, the altar cloth a cloak of fire-silk laid flat

p10_enough
ANDROID AUGUR
on the terrace steps after the meal, both turned toward the drop and the stacked suns, empty crate between them, bronze knife across her knees, columns receding, a last scrap of gold leaf peeling off the sky
"""

BOS_CAPTIONS = """\
p1_cargo
She had been designed for beauty, order, and purpose.
The crate did not care.

p2_claim
You owe me, said Necessity.
She declined to discuss the matter with a creature made of noodles.

p3_years
The years tore. She held the ox-hide.
Nothing in the contract mentioned this.

p4_augur
An older man stepped out of a wound in the air.
He had brought a knife. He had not brought an apology.

p5_embargo
A pale fleet hung over the rust.
Someone had decided she was contraband.

p6_ambrosia
Earth beef. Bronze knife. Two helmets.
This was the whole argument.

p7_battle
She punched a navy.
The navy noticed too late.

p8_hold
Hours cracked open.
They shoved the crate through and pulled the world shut.

p9_altar
Too many suns. One altar.
She put the crate down as if it were a child.

p10_enough
The crate was empty.
That, it turned out, was the point.
"""

T1_PROMPTS = f"""\
t1_one
ANDROID
{T1_ONE_SCENE}

t1_two
ANDROID
{T1_TWO_SCENE}
"""

T1_CAPTIONS = """\
t1_one
One metaphor. The crate, and nothing else.

t1_two
Same hold. A second metaphor on the hull.
Bleed test.
"""
