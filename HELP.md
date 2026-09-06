# Plate Press — UI help

One book at a time. ComfyUI must already be running. This app does not download the checkpoint.

Also in the app: **Help** tab. The header always shows the open book.

## Loop

1. Settings — pick a style card, Test connection.
2. Cast — this book’s people. Optional stills.
3. Book — paste scenes. Parse. Generate.
4. Queue — letter captions *after* the sampler. Never ask Comfy for text in the picture.

## Settings

Ink, closer, NEG, LoRA, and stills-on/off are **shared**. Cast, story, and plates belong to the open book.

- **Test connection** first.
- **Style cards are the mode.** There is no separate Plate layout radio.
- **Bos, one plate**: each slug is one image. If that slug contains `left pane:` / `right pane:`, only that plate splits. The rest stay undivided.
- **Two-pane comic**: consecutive slugs share one image (p1 left, p2 right). Do not write “Left pane” yourself. Each pane is its own scene as written — not “same place, same hour” unless you write that.
- Click a card to fill ink, layout line, closer, and matching negatives. The boxes stay editable.
- **Send character stills** is off unless you mean that. Off = text workflow, locks only. On: first still → `image1`, second → `image2`. Prompt says `use imageN as reference`.
- Optional: **Stills are cutouts** — tells Comfy the background is already gone.
- LoRA filename is a setting. Change it later. It is not the product.
- Do not touch sampler unless you mean it. Factory: 8 steps, CFG 1, euler, beta.

## Cast

- Cast is per book. Five books can all have ANDROID; they are not the same person.
- Header plus Cast, Book, Queue, and Settings headings show which book you are editing.
- Name is the token in the story wall: `ANDROID` or `{ANDROID}`.
- Lock is the identity sentence stuffed into every plate that names that character. A spacesuit lock will beat a gilt-chair scene. Put the clothes you want in the lock.
- A name like `PATRON` only works if that card exists on this book.
- 0–3 local stills per card. One body. Replace still on that card. Extra stills are not extra people.
- Two-shots are allowed and flagged. Faces fuse.
- **Lock seed** on a thumb in Queue, then later plates of that character can reuse it.
- **Load demo cast** replaces this book’s roster, not a global list.

## Book

Story wall:

```
p1_cargo
ANDROID
seen over her left shoulder, hauling a sealed ox-hide crate down a receding cargo bay,
the crate seams gleaming like liquid silver
```

- Slug on its own line (`p1_cargo`, `t1_one`).
- Then place + pose + exactly one metaphor. Not a studio. Not square to the camera.
- Do not paste STYLE, TAIL, sampler, or `aethernouveau` here. The app prepends those.
- Captions: same slugs, keep newlines, in the **Captions** box. Caption is the moral. Prompt is the camera. Narrator lines in the prompt wall go to the sampler.
- The default book is the demo. It cannot be deleted from the UI.
- **Parse** before generate. Check the two-shot column.
- The table header checkbox selects or clears every slug.
- **Generate selected** uses the checked rows and always queues a new version, even if images already exist. It Parses first. Skip only applies to Generate missing.
- Assembler order: ink (STYLE), layout line, cast lock, your slug, TAIL. Each chunk is its own sentence. Lock before the camera so the face does not outvote the action.
- Two-pane comic: one checked row uses the next slug as the right pane. Lock then camera in each pane.
- Default: 2 random seeds per plate.
- **Copy instructions for your LLM** copies the sheet plus current locks.

Metaphor examples: spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel. Any material metaphor is fine.

## Refs

- Off unless **Send character stills** is checked.
- One still per character named on that plate. Do not add a second ANDROID.
- If the photo still has a room, that room can become the plate unless cutouts is on.

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
