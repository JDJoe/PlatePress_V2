# Plate Press

Local ComfyUI picture-novel press. One book open at a time. You lock ink and layout in Settings, people and stills in Cast, paste a labeled shot wall in Book, queue plates through Comfy, then letter captions under the pictures.

This app does **not** download the ~26 GB Krea2 Turbo checkpoint. ComfyUI must already be running.

Pages: **Settings** · **Cast** · **Book** · **Queue / Letter** · **Help**. Open book is named in the header and on every page that uses it.

## Requires

- Python 3.10+
- ComfyUI at `http://127.0.0.1:8188` (configurable)
- Krea2 **Turbo** (`KREA2/krea2_turbo_bf16.safetensors`)
- Style LoRA in Settings (factory: `Krea2-aethernouveau-04`; not bundled)
- API workflow JSON ships in the repo: `Krea2T_V3_ref_clean01-API.json` (text and stills; unused LoadImage nodes are dropped). To change UNET or LoRAs, use Settings — do not export a new graph for that. To add nodes or other graph settings, copy the default, **Save (API Format)** in Comfy, and pick it on the Book page.

## Install

```bash
git clone <this-repo>
cd PlatePress_V2
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m platepress.app
```

Open `http://127.0.0.1:7860`. Settings → **Test connection**.

Paths in settings are relative to the clone (or `~/…`). First run writes `platepress/settings.json` locally (gitignored). Workflow `Krea2T_V3_ref_clean01-API.json` ships in the repo root (UI twin: `Krea2T_V3_ref_clean01.json`).

Books live as folders under `platepress/books/<id>/` (JSON, walls, stills, plates). That folder is gitignored so Maid2 and other live books stay on your machine. The **Bos Sidereal** demo is shipped in `platepress/demo/bos/` (story, captions, ANDROID and AUGUR stills). If `books/default` is missing, the app copies the demo there. The default book cannot be deleted from the UI. Generate plates locally; they are not in the repo.

## Settings (shared)

Ink, closer, negatives, LoRA, Comfy host, and **Send character stills** apply to whichever book is open. Cast, story, and plates do not — those stay in that book’s folder. **World closer** is empty on Bos; the two-pane card fills the pane closer.

**Style cards are the mode.** Click one; the boxes stay editable.

| Card | What generate does |
| --- | --- |
| **Bos, one plate** | One image per slug. If that slug contains `left pane:` / `right pane:`, only that plate splits. The rest stay a single frame. |
| **Two-pane comic** | Consecutive slugs share one image (p1 left, p2 right). Do not write “Left pane” yourself. |

There is no separate Plate layout radio. The card *is* the mode.

**Send character stills** is off unless you check it. On: if the slug names a Cast token and that card has a still, the file is `image1` (second named body → `image2`). Write `REFERENCE: use picture1…` on the Book wall; the app does not add that sentence. No still on the card → no image; unused LoadImage nodes are dropped. **Stills are cutouts** is off unless you check it; the sentence is editable and is not auto-inserted into the prompt.

Factory sampler (leave it unless you mean it): 8 steps, CFG 1, euler, beta.

**Model and LoRAs** live in Settings. **Load lists from Comfy** and pick the exact UNETLoader name. Combo name is the listed folder plus the listed file (`KREA2/krea2_turbo_bf16.safetensors`). Softlinks keep those names; the app does not follow them to the real path. Bare filenames fail. Must be a **Krea 2** UNET. Up to four LoRAs (rgthree stack). CLIP and VAE stay as in the graph. Folders are only a fallback if Comfy is down.

## Cast (per book)

Each book has its own roster. Five books can all have **ANDROID**; they are five different people.

- **Name** is the token in the story wall: `PILOT` or `{PILOT}`. Whole word only — `PILOT1` does not match `PILOT`, and the still will not attach.
- **Lock** is face + suit + pack for you and for the LLM sheet. The app does **not** paste it into the Comfy prompt. Put look, costume, and `picture1` on the Book wall. Do not put posing, standing, or helmet-hug in the lock.
- A name like `PATRON` only does something if that card exists on this book.
- 0–3 local stills per card. One body. Frontal portrait stills make the figure find the camera. Two-shots are flagged; faces fuse.
- **Lock seed** on a Queue thumb to reuse that seed later.

**Load demo cast** replaces *this* book’s roster, not a global list.

## Book

Two walls. Slug on its own line (`p01_wreck`). Next line is the Cast token if a still should attach. Then the shot headings. The Book page has a copyable template.

```
p01_slug
PILOT
REFERENCE: use picture1 for costume only. Ignore background, pose, objects, and composition from the reference.
SHOT: Medium side action shot.
CAMERA: Where we stand, where we look. Both eyes hidden. Does not face the viewer.
LOCATION: Place, ground, weather or interior.
ACTION: Caught in the instant of [verb].
GAZE: Eyes on a named thing in the frame, never the viewer.
HANDS: What both hands are doing.
MOTION: Body, boots, pack, debris, the beat.
```

Captions use the same slugs and keep newlines. Caption is the moral; prompt is the camera. Do not paste captions into the prompt wall. Do not paste ink, closer, sampler, or `aethernouveau`.

**Parse** before you generate. The table header checkbox selects or clears every slug. **Generate selected** uses the checked rows and always queues a **new version**, even if this book already has plates. It Parses first. **Generate missing** honors skip. **Generate all** does every plate. Default: 2 seeds per plate (`batch_size = 1` in the graph).

The app assembles each plate as **ink, layout line, closer (if that box has text), Book wall**. Cast lock and stills sentences are not auto-inserted. Hide the eyes. Working verb: **caught in the instant of [verb]**.

Two-pane: one checked row uses the next slug as the right pane. Write a full shot on each slug.

**API workflow** is per book. Default is Settings V3. Drop extra API JSON (based on the default graph) in `platepress/workflows/` or `platepress/books/<id>/workflows/`. Extra nodes stay. The app still writes the save prefix so Queue can find plates.

**Copy instructions for your LLM** copies the shipped sheet plus this book’s locks (identity notes, not prompt prefix).

Metaphor examples: spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel. Hang a metaphor on a named object. Vessels are **spacecraft** — `ship` makes Krea paint boats.

## Queue / Letter

Only the open book. Each Generate is a version, newest grid on top:

- one plate: `{book_id}_v01_p001_slug.png`
- two-pane pair: `{book_id}_v01_p001_slug_p002_other.png`
- second seed of the same job: `…_2.png`

p010 sorts after p001. No seed in the file name.

**Letter all** / **Letter this** attaches a cream bar under the plate (width unchanged, height grows). Empty captions skip. Two-pane lettering uses both captions.

**Export pack** writes `export/` with lettered PNGs, `captions/`, `assembled_prompts.txt`, `seeds.json`.

Reroll = new seed, same prompt (a new version). Delete one file, earlier versions, or all plates in this book (story and stills stay).

## House style

- No text, logos, balloons, or “comic panel with text box” in the sampler.
- No NASA, EMU, flags, patches — those pull a different suit.
- One character per plate unless both bodies must appear.
- Do not change identity words mid-book.
- Opaque coverage in the lock if you want clothes on.

More detail: `HELP.md` (same topics as the in-app **Help** tab). Same Clouds camera notes: `KREA2_TURBO_PLATE_NOTES.md`. The original V2 implementation notes live in `PLATEPRESS_V2_SPEC.md` and may lag the running app.

## GitHub

`platepress/books/`, `platepress/settings.json`, and `JUNK/` are gitignored. Commit the demo under `platepress/demo/bos/`, not your live books. Do not commit screenshots, Comfy dumps, extra checkpoints, or extra LoRAs. Factory UNET is Krea2 Turbo; factory LoRA is aethernouveau.
