# Plate Press — UI help

One book at a time. ComfyUI must already be running. This app does not download the checkpoint.

Also in the app: **Help** tab. The header always shows the open book.

## Loop

1. Settings — pick a style card, Test connection.
2. Cast — this book’s people. Optional stills.
3. Book — paste the labeled shot wall. Parse. Generate.
4. Queue — letter captions *after* the sampler. Never ask Comfy for text in the picture.

## Settings

Ink, layout line, closer, NEG, LoRA, and stills-on/off are **shared**. Cast, story, and plates belong to the open book.

- **Test connection** first.
- **Style cards are the mode.** There is no separate Plate layout radio.
- **Bos, one plate**: each slug is one image. If that slug contains `left pane:` / `right pane:`, only that plate splits.
- **Two-pane comic**: consecutive slugs share one image (p1 left, p2 right). Do not write “Left pane” yourself. Each pane is its own scene as written.
- Click a card to fill ink, layout line, and matching negatives. World closer stays empty on Bos; two-pane fills the pane closer. The boxes stay editable.
- **Ink** and **Layout line** are prepended to every plate.
- **World closer** is empty on Bos. Two-pane fills “each pane is its own scene…”. Prepended only if that box has text.
- **NEG** is the negative prompt.
- **Send character stills** is off unless you check it. On: if the slug names a Cast token and that card has a still, the file is `image1` (second named body → `image2`). No still on the card → no image, same graph, unused LoadImage nodes dropped. Write `REFERENCE: use picture1…` in the Book wall yourself; the app does not add that sentence.
- **Stills are cutouts** is off unless you check it. The cutout sentence is editable. It is not stuffed into the prompt unless you put it on the wall.
- **Model and LoRAs** — set the Comfy diffusion-models folder and the loras folder, Scan, then pick. The UNET must be Krea 2. Up to four LoRAs (rgthree stack). This swaps files in the V3 graph; do not export a new API workflow. CLIP and VAE stay as they are.
- Do not touch sampler unless you mean it. Factory: 8 steps, CFG 1, euler, beta.

API graph: `Krea2T_V3_ref_clean01-API.json` (text and stills).

## Cast

- Cast is per book. Five books can all have ANDROID; they are not the same person.
- Header plus Cast, Book, Queue, and Settings headings show which book you are editing.
- **Name** is the token on the wall: `PILOT` or `{PILOT}`. It must be a whole word. `PILOT1` does not match `PILOT`, and the still will not attach.
- **Lock** is face + suit + pack for *you* and for **Copy instructions for your LLM**. The app does **not** paste the lock into the Comfy prompt. Put look, costume, and `picture1` instructions on the Book wall.
- Never put posing, standing, cute, helmet-hug, or looking over the shoulder in the lock. Helmet and over-shoulder live on one slug.
- A name like `PATRON` only works if that card exists on this book.
- 0–3 local stills per card. One body. Replace still on that card. Frontal portrait stills make the figure find the camera. Prefer a full-body still if you say “costume only.”
- Two-shots are allowed and flagged. Faces fuse.
- **Lock seed** on a thumb in Queue, then later plates of that character can reuse it.
- **Load demo cast** replaces this book’s roster, not a global list.

## Book

Story wall. Slug, then the Cast token if a still should attach, then the shot headings. Copy the template on the Book page.

```
p01_slug
PILOT
REFERENCE: use picture1 for costume only. Ignore background, pose, objects, and composition from the reference.
SHOT: Medium side action shot.
CAMERA: Where we stand, where we look. Full body / over the shoulder / profile. Both eyes hidden. Does not face the viewer.
LOCATION: Place, ground, weather or interior. Named objects.
ACTION: Caught in the instant of [verb].
GAZE: Eyes on a named thing in the frame, never the viewer.
HANDS: What both hands are doing.
MOTION: Body, boots, pack, debris, the beat.
```

- Slug on its own line (`p01_wreck`, `t1_one`). Two digits so p010 sorts after p001.
- Token on the next line must match the Cast **Name** exactly if you want that still.
- Do not paste ink, closer, sampler, or `aethernouveau` here. The app prepends ink and the layout line (and closer if that box is not empty).
- Hide the eyes. `not looking at the viewer` is often ignored. Name shot size and where we stand.
- Working verb: **caught in the instant of [verb]**.
- Captions: same slugs, keep newlines, in the **Captions** box. Caption is the moral. Prompt is the camera.
- The default book is the demo. It cannot be deleted from the UI.
- **Parse** before generate. Check the two-shot column.
- The table header checkbox selects or clears every slug.
- **Generate selected** uses the checked rows and always queues a new version. It Parses first. Skip only applies to Generate missing.
- Assembler order: **ink, layout line, closer (if any), Book wall**. Cast lock and stills sentences are not auto-inserted.
- Two-pane comic: one checked row uses the next slug as the right pane. Write a full shot on each slug.
- Default: 2 random seeds per plate.
- **Copy instructions for your LLM** copies the shipped sheet plus this book’s locks (as identity notes, not as prompt prefix).

Metaphor examples: spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel. Hang a metaphor on a **named object**. Vessels are **spacecraft** — `ship` makes Krea paint boats.

## Refs

- Off unless **Send character stills** is checked.
- One still per Cast token named on that plate. `PILOT` attaches; `PILOT1` does not.
- Frontal “look at me” stills clone that pose. Use a full-body costume still.
- Cutouts: optional checkbox plus editable sentence. Prefer writing REFERENCE on the wall.

## Queue / Letter

- This page shows only the open book.
- File names:
  - `{book_id}_v01_p001_slug.png`
  - two-pane pair: `{book_id}_v01_p001_slug_p002_other.png`
  - second seed: `…_2.png`
- Each Generate is a new version (v01, then v02) with its own grid, newest on top. p010 sorts after p001. No seed in the name.
- Thumbs land in the book `plates/` folder.
- **Letter all** / **Letter this** attaches a cream bar under the plate. Width unchanged. Height grows. Empty captions skip. Pair files use both captions.
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
