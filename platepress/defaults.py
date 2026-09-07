"""Factory strings. STYLE/TAIL/locks are settings; this LoRA is not the product."""

from __future__ import annotations

INK_BOS = (
    "aethernouveau. Ink and watercolor by Moebius, thin black outlines, "
    "muted ochre, rust, teal and black. Cream paper is the print stock, not the sky. "
    "Paint the whole plate: ground, horizon, and a real sky with weather and tone, "
    "architecture or landscape behind the figures, no bare sheet, no white void."
)
INK_PANE = (
    "aethernouveau. Ink and watercolor by Moebius, thin black outlines, "
    "cream paper, muted ochre and black."
)
STYLE = INK_BOS

LAYOUT_ONE = (
    "A single undivided plate, one scene, no split, no second panel."
)
LAYOUT_SPLIT = (
    "A single comic plate split into two equal vertical panes divided by a thin black ink rule, "
    "cream margins, no text, no captions, no speech balloons, no logos, no letters."
)

CLOSER_ONE = (
    " Environment to all four edges, ground underfoot, "
    "painted sky to the horizon, depth behind. No empty studio. No blank paper sky. "
    "Sharp and in focus. No text. No logos."
)
CLOSER_SPLIT = (
    " Each pane is its own scene as written. "
    "Not a collage. Not two posters glued together. Not a mirrored face. "
    "Sharp and in focus. No text. No logos."
)
TAIL = CLOSER_ONE

REF_CUTOUT = (
    "Stills are cutouts: background already removed. "
    "Use only the subject. "
    "Do not use the still's room, window, furniture, sky, or ground. "
    "Place the subject in the new scene."
)
LOCK_POSE = (
    "Keep the locked look. The lock is how this subject appears, whatever it is. "
    "Place, action, and camera follow the scene as written."
)
ANDROID = (
    "A slim beautiful bald female android with blue eyes, "
    "in an opaque sleek spacesuit and brown gloves, complete coverage, bubble helmet"
)
AUGUR = (
    "A lean older man with grey cropped hair and a short neat beard, "
    "in a worn ochre-pale spacesuit and dark gloves, complete coverage, bubble helmet"
)
NEG_ALWAYS = (
    "text, watermark, signature, letters, logo, NASA, flag, patch, "
    "photoreal astronaut, modern EMU suit, blurry, bad anatomy, deformed hands, "
    "extra fingers, fused fingers, plastic skin, nude, overexposed, underexposed, "
    "empty background, blank backdrop, studio cyclorama, plain cream void, "
    "white void, featureless background, floating in nothing, portrait on empty paper, "
    "fairy wings, sailing ship, sails, mast, masts, galleon, schooner, boat, tall ship, "
    "canvas sails, rigging, square-rigger"
)
NEG_ONE_EXTRA = (
    "diptych, triptych, split screen, two panels, side by side collage, "
    "polaroid, picture-in-picture, multiple images"
)
NEG_SPLIT_EXTRA = (
    "collage, two posters, mirrored face, polaroid, picture-in-picture"
)


def neg_for(layout: str) -> str:
    extra = NEG_SPLIT_EXTRA if layout == "split" else NEG_ONE_EXTRA
    return f"{NEG_ALWAYS}, {extra}"


NEG = neg_for("one")

EXAMPLES = {
    "bos": {
        "id": "bos",
        "label": "Bos, one plate",
        "blurb": "One image per slug. A slug may still split if it contains left pane / right pane.",
        "layout": "one",
        "style": INK_BOS,
        "layout_text": LAYOUT_ONE,
        "tail": "",
        "neg": neg_for("one"),
    },
    "split": {
        "id": "split",
        "label": "Two-pane comic",
        "blurb": "Consecutive slugs share one image: first left, next right.",
        "layout": "split",
        "style": INK_PANE,
        "layout_text": LAYOUT_SPLIT,
        "tail": CLOSER_SPLIT,
        "neg": neg_for("split"),
    },
}

UNET = "KREA2/krea2_turbo_bf16.safetensors"
LORA = "Krea2-aethernouveau-04/Krea2-aethernouveau-04_merged.safetensors"
LORA_STRENGTH = 0.80
LORA_SLOTS = 4
PER_PROMPT = 2
SAMPLER = {
    "steps": 8,
    "cfg": 1,
    "sampler_name": "euler",
    "scheduler": "beta",
}

# Examples for the Book preview column. Any metaphor in the wall is sent as written.
METAPHORS = (
    "spiderweb of black cells",
    "wet silk into teal glass",
    "stained glass",
    "gold leaf over black glass",
    "liquid silver",
    "fire-silk",
    "enamel",
)

T1_ONE_SCENE = """\
REFERENCE: use picture1 for costume only. Ignore background, pose, objects, and composition from the reference.
SHOT: Medium over-the-shoulder, three-quarter from behind.
CAMERA: Behind her left shoulder. Full body in the bay. Both eyes hidden. Does not face the viewer.
LOCATION: Long cargo bay, ribbed decking, stacked drums, a slit of rust light at the far hatch.
ACTION: Caught in the instant of hauling a sealed ox-hide crate down the aisle.
GAZE: Helmet toward the crate, not the aisle, never the viewer.
HANDS: Both brown gloves on the crate.
MOTION: Crate seams gleaming like liquid silver."""
T1_TWO_SCENE = """\
REFERENCE: use picture1 for costume only. Ignore background, pose, objects, and composition from the reference.
SHOT: Medium over-the-shoulder, three-quarter from behind.
CAMERA: Behind her left shoulder. Full body in the bay. Both eyes hidden. Does not face the viewer.
LOCATION: Long cargo bay, ribbed decking, stacked drums, a slit of rust light at the far hatch.
ACTION: Caught in the instant of hauling a sealed ox-hide crate down the aisle.
GAZE: Helmet toward the crate, not the aisle, never the viewer.
HANDS: Both brown gloves on the crate.
MOTION: Crate seams gleaming like liquid silver. Hull plates over her shoulder peeling like gold leaf over black glass."""
