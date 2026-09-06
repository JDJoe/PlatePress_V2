# Plate Press

Local ComfyUI picture-novel press. One book open at a time. You lock ink in Settings, lock people in Cast, paste a scene wall in Book, queue plates through Comfy, then letter captions under the pictures.

This app does **not** download the ~26 GB Krea2 Turbo checkpoint. ComfyUI must already be running.

Pages: **Settings** · **Cast** · **Book** · **Queue / Letter** · **Help**. Open book is named in the header and on every page that uses it.

## Requires

- Python 3.10+
- ComfyUI at `http://127.0.0.1:8188` (configurable)
- Krea2 **Turbo** (`KREA2/krea2_turbo_bf16.safetensors` or the path already in your graph)
- The LoRA currently in your graph (swap it in Settings; it is not bundled)
- API workflow JSON (ComfyUI → **Save (API Format)**):
  - text-only: `Krea2T_API01.json`
  - with character stills: `Krea2T_V2_ref_API.json`

## Install

```bash
git clone <this-repo>
cd PlatePress_V2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m platepress.app
```

Open `http://127.0.0.1:7860`. Settings → **Test connection**.

Paths in settings are relative to the clone (or `~/…`). First run writes `platepress/settings.json` locally (gitignored). Workflows `Krea2T_API01.json` and `Krea2T_V2_ref_API.json` ship in the repo root.

Books live as folders under `platepress/books/<id>/` (JSON, walls, stills, plates). That folder is gitignored so Maid2 and other live books stay on your machine. The **Bos Sidereal** demo is shipped in `platepress/demo/bos/` (story, captions, ANDROID and AUGUR stills). If `books/default` is missing, the app copies the demo there. The default book cannot be deleted from the UI. Generate plates locally; they are not in the repo.

## Settings (shared)

Ink, closer, negatives, LoRA, Comfy host, and **Send character stills** apply to whichever book is open. Cast, story, and plates do not — those stay in that book’s folder.

**Style cards are the mode.** Click one; the boxes stay editable.

| Card | What generate does |
| --- | --- |
| **Bos, one plate** | One image per slug. If that slug contains `left pane:` / `right pane:`, only that plate splits. The rest stay a single frame. |
| **Two-pane comic** | Consecutive slugs share one image (p1 left, p2 right). Do not write “Left pane” yourself. |

There is no separate Plate layout radio. The card *is* the mode.

**Send character stills** is off unless you check it. Off = text locks only (text workflow). On = first still → `image1`, second → `image2`; the prompt says `use imageN as reference`. Optional: stills are cutouts.

Factory sampler (leave it unless you mean it): 8 steps, CFG 1, euler, beta. LoRA filename is a setting, not the product.

## Cast (per book)

Each book has its own roster. Five books can all have **ANDROID**; they are five different people.

- **Name** is the token in the story wall: `ANDROID` or `{ANDROID}`.
- **Lock** is the identity sentence. Whatever you write here is stuffed into every plate that names that character. A spacesuit lock will beat a gilt-chair scene.
- A name like `PATRON` only does something if that card exists on this book.
- 0–3 local stills per card. One body. Replace still on that card. Two-shots are flagged; faces fuse.
- **Lock seed** on a Queue thumb to reuse that seed later.

**Load demo cast** replaces *this* book’s roster, not a global list.

## Book

Two walls. Slug on its own line (`p1_cargo`, `t1_one`). Then place + pose + **one** material metaphor. Put the token on its own line after the slug.

```
p1_cargo
ANDROID
seen over her left shoulder, hauling a sealed ox-hide crate down a receding cargo bay,
the crate seams gleaming like liquid silver
```

Captions use the same slugs and keep newlines. Caption is the moral; prompt is the camera. Do not paste captions into the prompt wall. Do not paste STYLE, TAIL, sampler, or `aethernouveau`.

**Parse** before you generate. The table header checkbox selects or clears every slug. **Generate selected** uses the checked rows and always queues a **new version**, even if this book already has plates. It Parses first. **Generate missing** honors skip. **Generate all** does every plate. Default: 2 seeds per plate (`batch_size = 1` in the graph).

The app assembles each plate as **ink (STYLE), layout line, cast lock, your slug, TAIL**. Each chunk is its own sentence. Lock comes before the camera so the face does not outvote the action.

Two-pane: one checked row uses the next slug as the right pane. Lock then camera in each pane.

**Copy instructions for your LLM** copies the shipped sheet plus this book’s locks.

Metaphor examples: spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel. Any material metaphor is fine. Vessels are **spacecraft** — `ship` makes Krea paint boats.

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

More detail: `HELP.md` (same text as the in-app **Help** tab). The original V2 implementation notes live in `PLATEPRESS_V2_SPEC.md` and may lag the running app.

## GitHub

`platepress/books/` and `platepress/settings.json` are gitignored. Commit the demo under `platepress/demo/bos/`, not your live books. Do not commit screenshots or Comfy dumps at the repo root.
