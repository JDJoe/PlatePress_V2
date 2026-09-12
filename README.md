# Plate Press

Local ComfyUI picture-novel press. One book open at a time. You lock ink and layout in Settings, people and stills in Cast, paste a labeled shot wall and captions in Book, then queue plates through Comfy. The letter column sends captions and balloons onto the plate at Generate. Same size. No bar under the image.

This app does **not** download the ~26 GB Krea2 Turbo checkpoint. ComfyUI must already be running.

Pages: **Settings** · **Cast** · **Book** · **Queue / Letter** · **Help**. Open book is named in the header and on every page that uses it.

## Requires

- Python 3.10+
- ComfyUI at `http://127.0.0.1:8188` (configurable)
- Krea2 **Turbo** (`KREA2/krea2_turbo_bf16.safetensors`)
- Style LoRA in Settings (factory: `Krea2-aethernouveau-04`; not bundled)
- API workflow JSON ships in the repo: `krea2_character_consistency_workflow-03-API.json` (text and stills; unused LoadImage nodes are dropped). Encode is `TextEncodeQwenImageEditPlus` plus `ReferenceLatent` when a still is on. The graph’s second Qwen encode is a diptych negative (Settings NEG is not written there). To change UNET or LoRAs, use Settings — do not export a new graph for that. To add nodes or other graph settings, copy the default, **Save (API Format)** in Comfy, and pick it on the Book page.

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

Paths in settings are relative to the clone (or `~/…`). First run writes `platepress/settings.json` locally (gitignored). Workflow `krea2_character_consistency_workflow-03-API.json` ships in the repo root (UI twin: `krea2_character_consistency_workflow-03.json`).

Books live as folders under `platepress/books/<id>/` (JSON, walls, stills, plates). That folder is gitignored so Maid2 and other live books stay on your machine. The **Bos Sidereal** demo is shipped in `platepress/demo/bos/` (story, captions, ANDROID and AUGUR stills). If `books/default` is missing, the app copies the demo there. The default book cannot be deleted from the UI. Generate plates locally; they are not in the repo.

## Settings (shared)

Ink, closer, negatives, **UNET, LoRAs**, and Comfy host are **shared Settings**. They are not stored on the book. Cast, story, plates, per-slug Text/Image, and the book’s API workflow stay in that book’s folder. **World closer** is empty on Bos; the two-pane card fills the pane closer.

**Style cards are the mode.** Click one; the boxes stay editable.

| Card | What generate does |
| --- | --- |
| **Bos, one plate** | One image per slug. If that slug contains `left pane:` / `right pane:`, only that plate splits. The rest stay a single frame. |
| **Two-pane comic** | Consecutive slugs share one image (p1 left, p2 right). Do not write “Left pane” yourself. |

There is no separate Plate layout radio. The card *is* the mode.

Stills and locks are per slug on the Book table (**Text** / **Image** columns). There is no global stills switch. **Cutout** is per character on Cast.

Factory sampler (leave it unless you mean it): 8 steps, CFG 1, euler, beta.

**Model and LoRAs** live in Settings (shared). **Load lists from Comfy** and pick the exact UNETLoader name. Combo name is the listed folder plus the listed file (`KREA2/krea2_turbo_bf16.safetensors`). Softlinks keep those names. Bare filenames fail. Must be a **Krea 2** UNET. Up to four LoRAs. CLIP and VAE stay as in the graph. Changing UNET/LoRA here does not write them into the book.

## Cast (per book)

Each book has its own roster. Five books can all have **ANDROID**; they are five different people.

- Cast **order** is the slot: first card is `CHARACTER1` (also `PILOT1`), second is `CHARACTER2`. The name on the card is for you; `Anna` in the wall is writer text, not a lookup.
- **Lock** is face + suit + pack. Book **Text** on prepends that lock. `PILOT1 is PingPong` stays as written. The app does not insert KEEP. Do not put posing, standing, or helmet-hug in the lock.
- **Cutout** is a checkbox on the card. The cutout sentence lives on the Cast page.
- A name like `PATRON` only does something if that card exists on this book.
- 0–3 local stills per card. One body. Frontal portrait stills make the figure find the camera. Two-shots are flagged; faces fuse.
- **Lock seed** on a Queue thumb to reuse that seed later.

**Load demo cast** replaces *this* book’s roster, not a global list.

## Book

Two walls. Slug on its own line (`p01_wreck`). Then `PILOT1 is PingPong` as you want it in the prompt. Write KEEP / REFERENCE yourself. After Parse, **Text**, **Image**, and **letter** columns start off. Text = Cast lock. Image = still. letter = captions and balloons on the plate.

```
p01_slug
PILOT1 is PingPong
KEEP the same woman from image1, her name is PingPong.
REFERENCE: use image1. Keep her face, hair, body, and clothes from image1. Ignore background, pose, and setting.
SHOT: Medium side action shot.
CAMERA: Where we stand, where we look. Both eyes hidden. Does not face the viewer.
LOCATION: Place, ground, weather or interior.
ACTION: Caught in the instant of [verb].
GAZE: Eyes on a named thing in the frame, never the viewer.
HANDS: What both hands are doing.
MOTION: Body, boots, pack, debris, the beat.
```

Captions use the same slugs. Check **letter** so Generate paints them on the plate (same size, no extra bar). Untagged lines become a bottom box (`CAP_B`). `CAP_T` is the top box. Tags (`NS`, `NS_6`, …) choose balloon shape and cell. Do not paste ink, closer, sampler, or `aethernouveau`.

**Parse** before you generate. The table header checkbox selects or clears every slug. Click a prompt (or Copy) to copy the full assembled text Comfy will get — the hover hint cannot be selected. **Generate selected** uses the checked rows and always queues a **new version**, even if this book already has plates. It Parses first. **Generate missing** honors skip. **Generate all** does every plate. Default: 2 seeds per plate (`batch_size = 1` in the graph).

The app assembles **ink, layout line, closer (if that box has text), Book wall**. It does not add KEEP lines. **Text** on replaces `CHARACTER1` with the first Cast lock. **Image** on (Text off) turns that into `image1 is Anna` and uploads the still. Both off: no lock, no still. Hide the eyes. Working verb: **caught in the instant of [verb]**.

Two-pane: one checked row uses the next slug as the right pane. Write a full shot on each slug.

**API workflow** is per book. Default is Settings `krea2_character_consistency_workflow-03-API.json`. To customize: open the default graph in Comfy, change nodes or parameters, **Save (API Format)**, put the JSON in this book’s `workflows/` folder (or shared `platepress/workflows/`), then pick it on the Book page. Extra nodes stay. The app still fills prompt, seed, Settings UNET/LoRAs, and the save prefix. If that graph has a CLIP negative node, Settings NEG is written there. The shipped default keeps its own diptych negative.

**Copy instructions for your LLM** copies the shipped sheet plus this book’s locks (identity notes, not prompt prefix).

Metaphor examples: spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel. Hang a metaphor on a named object. Vessels are **spacecraft** — `ship` makes Krea paint boats.

## Queue / Letter

Only the open book. Each Generate is a version, newest grid on top:

- one plate: `{book_id}_v01_p001_slug.png`
- two-pane pair: `{book_id}_v01_p001_slug_p002_other.png`
- second seed of the same job: `…_2.png`

p010 sorts after p001. No seed in the file name.

**Letter all** / **Letter this** is optional extra drawing on a copy. The usual path is Generate with the letter column on.

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
