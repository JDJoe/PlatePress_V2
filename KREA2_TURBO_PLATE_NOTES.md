# Krea2 Turbo — plate notes (Same Clouds era)

Load this next session. Do not restart from Noodles / Beef / Widow.

## Stack

Plate Press prepends **ink + layout line** (and **closer** only if that Settings box has text). Cast lock is **not** pasted into the prompt. NEG is separate.  
**Book wall = shot only** (REFERENCE / SHOT / CAMERA / LOCATION / ACTION / GAZE / HANDS / MOTION). Do not repeat Moebius, cream paper, no text, no logos.

Official Krea 2 order (use it inside the scene):  
**subject + action + place + camera + light.** Style last, and Settings already owns style.

Settings Ink (current):

```text
aethernouveau. Ink and watercolor by Moebius, thin black outlines, muted ochre, rust, teal and black. Cream paper is the print stock, not the sky. vintage sci-fi comic art style, detailed linework, muted colors. Paint the whole plate: ground, horizon, and a real sky with weather and tone, architecture or landscape behind the figures, no bare sheet, no white void.
```

Layout: one undivided plate.  
TAIL: empty on Bos. Two-pane card fills “each pane is its own scene…”.

Assembler now: **STYLE → layout → [closer if any] → Book wall**

Settings **Model and LoRAs** are shared (not stored on the book). Load lists from Comfy. Combo name is the listed folder plus the listed file (`KREA2/krea2_turbo_bf16.safetensors`). Softlinks keep those names. CLIP and VAE stay. Must be Krea 2.

**API workflow** is per book. Open the default V3 graph in Comfy, change nodes or parameters, Save (API Format), drop the JSON in that book’s `workflows/` folder, pick it on the Book page. Extra nodes stay. The app still fills prompt, seed, Settings UNET/LoRAs, and the save prefix.

## Cast lock

Lock = face + suit + pack for you and the LLM sheet. The app does **not** paste it into the Comfy prompt. Put look, costume, and `picture1` on the Book wall.

**Never put in the lock:**
- looking back over her shoulder
- carrying a helmet under her arm
- standing / posing
- cute (pulls postcard)

Working PILOT lock:

```text
A young woman with a soft oval face, pale warm skin, dark almond eyes, heavy straight brows, a small closed mouth, short messy black hair with uneven bangs, wearing an opaque orange-red mechanical flight suit with cream thigh panels, a cream collar ring, grey plated gauntlets, a heavy white-and-grey life-support pack with black corrugated hoses over both shoulders, no helmet on her head
```

Helmet and over-shoulder live in **one slug** (p01), not in Cast.

`almond eyes` with no still drifts East Asian. Face match = low-strength still, not a longer lock.

## Stills / refs

- Frontal portrait still = she finds the camera on every plate.
- “Use as ref” on a postcard thumb clones the postcard.
- `picture1 for costume only` is weak if the still is a head. Use a full-body orange suit still.
- Cutout stills: turn **Stills are cutouts** ON so the beige circle is not the room.
- Teapot test: if the next plate becomes the teapot, the ref is the subject. If she stays and metal tints, text is the subject.
- Two seeds per plate. Two character seeds, not one book seed.
- No NASA / EMU / flag in lock or still filenames if you can help it. EMU = real white EVA suit prior.

## Camera (the thing that killed the postcard)

Krea defaults to: pretty woman, three-quarter, looking at you, hugging the helmet.

Force geometry so the face cannot find the lens:

```text
Camera: Wide shot from behind and slightly to the left of pilot1, over her shoulder. Full body in frame. We see her back, pack, and sword. Only the edge of one cheek is visible. Both eyes hidden. She does not face the viewer.
```

Rules:
- Name shot size: wide establishing, full body, head-to-toe, small in the frame.
- Name where we stand: behind, profile, behind the seat.
- Name where **eyes** go: a prop or a path in the frame, never “the viewer.”
- Both hands busy. Helmet on hip or on the seat unless the slug is about the helmet.
- `looking back over her shoulder` reprints p01. Use it only when eyes are on a **named distant craft**.
- `not looking at the viewer` is polite and often ignored. Hide the eyes.

Working verb grammar: **caught in the instant of [verb]**.

## Scene writing (Book wall)

Slug format: `p01_wreck` (two digits or folder sort breaks).

```text
p02_sword
PILOT
caught in the instant of wrenching a short samurai sword free from beneath the broken cockpit seat, crouched low and pulling hard with both gauntlets, one knee planted, head and eyes pointed down at the sword, helmet on the seat beside her, torn canopy, dusty plain and cloudy sky through the rip
```

Metaphors attach to **named objects**, not to the plate. Several are fine if each has its own noun. Do not hang two surfaces on the suit or the face.

Say `spacecraft`, not `ship` (boats appear).

If the background washes to cream, you did not name ground, horizon, weather. Settings asks for a real sky; the slug must still supply clouds / basin / hangar ribs.

Captions go in the other box. Never in the sampler. Letter after: bar under the plate, same W, extra H.

## Split plates

One sampler, two full prompts = soup.  
Template + two jobs, or regional masks.  
If one latent: `two equal vertical panes, thin black ink rule` + `they look at each other across the rule`.  
`comic panel with caption box` wrecks style.

## Labeled brief (raw Comfy keeper)

Use these five headings. Do not smash them into one sentence.

```text
Style: aethernouveau. Ink and watercolor by Moebius, thin black outlines, muted ochre, rust, teal and black. Cream paper is the print stock, not the sky. vintage sci-fi comic art style, detailed linework, muted colors.

Location: Interior of a small spacecraft bridge in orbit. Dark consoles, warning lights, a wide forward window showing black cosmos and a planet far below. Metal floor, loose tools in mid-air.

Characters: pilot1 - a female pilot, use picture1 for costume only. Ignore background and objects. Short samurai sword in both hands.
Second figure: unknown man, only a dark silhouette near the far hatch, no face, no detail.

Camera: Wide shot from behind and slightly to the left of pilot1, over her shoulder. Full body in frame. We see her back, pack, and sword. Only the edge of one cheek is visible. Both eyes hidden. She does not face the viewer.

Action: Caught in the instant she wrenches the short samurai sword sideways through a standing wrinkle in the air in front of her. The blade stretches the wrinkle open. It does not hit the silhouette. Her body twists with the cut, one boot sliding back on the deck. Head and eyes locked on the tear. Teal glass fractures outward from the blade. A cloudy ochre-and-blue sky is visible inside the opening. Warning lights flare. Loose objects fly sideways.
```

Every new raw-Comfy test: **Style, Location, Characters, Camera, Action.**  
In Plate Press, Style is Settings; the Book wall is REFERENCE + SHOT + CAMERA + LOCATION + ACTION + GAZE + HANDS + MOTION. Token on its own line must match Cast Name (`PILOT`, not `PILOT1`) if a still should attach.

## Book in progress

Title: **Same Clouds**  
16 plates, happy loop: crash → sword → ground fire → spaceport → orbit fight → sword cuts an hour → she lands on the same launch morning → aborts the doomed takeoff → leaves on the craft that fled in p01.

Keepers (v04): `p001_wreck`, `p002_sword_2`, `p003_dust`.  
Do not ref the standing-helmet `p004_ridge`.

Open repo: `https://github.com/JDJoe/PlatePress_V2`  
App: Settings / Cast / Book / Queue. Comfy at 8188. LoRA + Krea2 Turbo already in the graph.

## Next session

1. Read this file.  
2. Ask where Same Clouds left off (likely p04+ with “caught in the instant” grammar).  
3. Do not invent a new book unless asked.  
4. Do not put STYLE in the Book wall.  
5. Do not put helmet-hug or over-shoulder in Cast.
