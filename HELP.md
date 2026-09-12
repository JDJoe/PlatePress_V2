# Plate Press — UI help

One book at a time. ComfyUI must already be running. This app does not download the checkpoint.

Also in the app: **Help** tab. The header always shows the open book.

## Loop

1. Settings — pick a style card, Test connection.
2. Cast — this book’s people. Optional stills.
3. Book — paste the labeled shot wall. Parse. Generate.
4. Queue — watch the plates. Captions and balloons are in the picture if the **letter** column was on at Generate. Same size as the plate.

## Settings

Ink, layout line, closer, NEG, **UNET, LoRAs**, and stills-on/off are **shared Settings** (not stored on the book). Cast, story, plates, and the book’s API workflow belong to the open book.

- **Test connection** first.
- **Style cards are the mode.** There is no separate Plate layout radio.
- **Bos, one plate**: each slug is one image. If that slug contains `left pane:` / `right pane:`, only that plate splits.
- **Two-pane comic**: consecutive slugs share one image (p1 left, p2 right). Do not write “Left pane” yourself. Each pane is its own scene as written.
- Click a card to fill ink, layout line, and matching negatives, and save Settings. World closer stays empty on Bos; two-pane fills the pane closer. The boxes stay editable.
- **Ink** and **Layout line** are prepended to every plate.
- **World closer** is empty on Bos. Two-pane fills “each pane is its own scene…”. Prepended only if that box has text.
- **NEG** is the negative prompt. It is written only if the API graph has a CLIP negative node. The shipped default keeps its own diptych negative.
- Stills and locks are **Text** / **Image** on the Book table, not Settings. **Cutout** is per character on Cast.
- **Model and LoRAs** — **Load lists from Comfy** and pick the exact UNETLoader name. Combo name is the listed folder plus the listed file (`KREA2/krea2_turbo_bf16.safetensors`). Softlinks keep those names. Must be a Krea 2 UNET. Shared Settings — not saved on the book.
- Do not touch sampler unless you mean it. Factory: 8 steps, CFG 1, euler, beta.

API graph: `krea2_character_consistency_workflow-03-API.json` (text and stills; Qwen encode + ReferenceLatent when a still is on; unused LoadImage nodes are dropped). **Per book:** open that default in Comfy, change nodes or parameters, **Save (API Format)**, drop the JSON in this book’s `workflows/` folder (or shared `platepress/workflows/`), pick it on the Book page. Extra nodes stay. The app still fills prompt, seed, Settings UNET/LoRAs, and the save prefix.

## Cast

- Cast is per book. Five books can all have ANDROID; they are not the same person.
- Header plus Cast, Book, Queue, and Settings headings show which book you are editing.
- First Cast card is `CHARACTER1` / `PILOT1`, second is `CHARACTER2`. `Anna` after `is` is writer text, not a Cast lookup.
- **Lock** is face + suit + pack. Book **Text** on prepends that lock. `PILOT1 is PingPong` stays as written. The app does not insert KEEP. Do not put posing, standing, or helmet-hug in the lock.
- **Cutout** is a checkbox on the card. Cutout sentence is on the Cast page. It is sent only when that plate’s Image column is on.
- Never put posing, standing, cute, helmet-hug, or looking over the shoulder in the lock. Helmet and over-shoulder live on one slug.
- A name like `PATRON` only works if that card exists on this book.
- 0–3 local stills per card. One body. Replace still on that card. Frontal portrait stills make the figure find the camera. Prefer a full-body still if you say “costume only.”
- Two-shots are allowed and flagged. Faces fuse.
- **Lock seed** on a thumb in Queue, then later plates of that character can reuse it.
- **Load demo cast** replaces this book’s roster, not a global list.

## Book

Story wall. Slug, then `PILOT1 is PingPong`, then KEEP / REFERENCE if you want the still, then the shot headings. Copy the template on the Book page. **Text**, **Image**, and **letter** start off.

```
p01_slug
PILOT1 is PingPong
KEEP the same woman from image1, her name is PingPong.
REFERENCE: use image1. Keep her face, hair, body, and clothes from image1. Ignore background, pose, and setting.
SHOT: Medium side action shot.
CAMERA: Where we stand, where we look. Full body / over the shoulder / profile. Both eyes hidden. Does not face the viewer.
LOCATION: Place, ground, weather or interior. Named objects.
ACTION: Caught in the instant of [verb].
GAZE: Eyes on a named thing in the frame, never the viewer.
HANDS: What both hands are doing.
MOTION: Body, boots, pack, debris, the beat.
```

- Slug on its own line (`p01_wreck`, `t1_one`). Two digits so p010 sorts after p001.
- Cast **name** can be anything (PingPong). New cards default to `CHARACTER1`, `CHARACTER2`. On the wall, `CHARACTER1` / `PILOT1` means **first card**, `CHARACTER2` second. **Text** on: that token becomes the lock, `is PingPong` stays. **Image** on: still is `image1`, token stays unless Text is also on. **Both**: same prompt as Text, plus the still. Write KEEP yourself.
- Do not paste ink, closer, sampler, or `aethernouveau` here. The app prepends ink and the layout line (and closer if that box is not empty).
- Hide the eyes. `not looking at the viewer` is often ignored. Name shot size and where we stand.
- Working verb: **caught in the instant of [verb]**.
- Captions: same slugs, in the **Captions** box. Check the **letter** column so Generate paints them on the plate. Untagged lines become a bottom box (`CAP_B`). `CAP_T` is the top box. The plate does not grow.
- The default book is the demo. It cannot be deleted from the UI.
- **Parse** before generate. Check the two-shot column. Click a prompt (or Copy) to copy the full assembled text Comfy will get.
- Header checkboxes: generate-select, Text, Image, letter.
- **Generate selected** uses the checked rows and always queues a new version. It Parses first. Skip only applies to Generate missing.
- Assembler: **ink, layout line, closer (if any), Book wall**. No KEEP line is added.
- Two-pane comic: one checked row uses the next slug as the right pane. Write a full shot on each slug.
- Default: 2 random seeds per plate.
- Caption tags (one per line). Speaker optional after the tag: `NS: PILOT2: We should sell them.`
  - Place the balloon in a cell: `NS_6: PILOT2 suggested selling them.` Grid, top to bottom:
    `1 2`
    `3 4`
    `5 6`
    Left column is odd (1, 3, 5), right is even (2, 4, 6). Tail points down in that cell.
  - `NS` normal oval speech · `NSV` vertical · `NS2` two connected balloons (`first | second`) · `OFFP` off-panel
  - `YELL` burst · `FADE` weak · `WHISP` dashed whisper · `ANN` starburst announcement
  - `THINK` oval thought · `DREAM` cloud · `DARK` black balloon, white letters
  - `CAP_B` rectangular caption box at the bottom · `CAP_T` at the top
- **Copy instructions for your LLM** copies the shipped sheet plus this book’s locks (as identity notes, not as prompt prefix).

Metaphor examples: spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel. Hang a metaphor on a **named object**. Vessels are **spacecraft** — `ship` makes Krea paint boats.

## Refs

- Per slug **Image** column, not a Settings switch. `CHARACTER1` → `image1`, `CHARACTER2` → `image2`.
- Text off + Image on: the wall reads `image1 is Anna`. Write KEEP/REFERENCE yourself if you want it.
- Frontal “look at me” stills clone that pose. Use a full-body costume still.
- Cutout is per Cast card. Prefer writing REFERENCE on the wall.

## Queue / Letter

- This page shows only the open book. Click a thumb to view it larger (Esc or click the dark to close).
- File names:
  - `{book_id}_v01_p001_slug.png`
  - two-pane pair: `{book_id}_v01_p001_slug_p002_other.png`
  - second seed: `…_2.png`
- Each Generate is a new version (v01, then v02) with its own grid, newest on top. p010 sorts after p001. No seed in the name.
- Thumbs land in the book `plates/` folder.
- **Letter all** / **Letter this** is optional extra drawing on a copy. The usual path is Generate with the letter column on.
- **Export pack** writes lettered PNGs, `captions/`, `assembled_prompts.txt`, `seeds.json`.
- Reroll = new seed from the current Book wall (saves first), not the old file. New version.
- Delete one file, earlier versions, or all plates in this book (story/stills stay).
- Settings → Books: new book, open, delete whole folder (not default).

## House style

- No text, logos, balloons, or “comic panel with text box” in the sampler.
- No NASA, EMU, flags, patches — those pull a different suit.
- One character per plate unless both bodies must appear.
- Do not change identity words mid-book.
- Vessels are spacecraft. The word ship (and spaceship) makes Krea paint boats with sails.
