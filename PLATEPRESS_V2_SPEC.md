# Plate Press V2 — implementation spec

**Live product behavior** is `README.md`, `HELP.md`, and the in-app Help tab. This file is the original V2 implementation spec and may lag the running app (style cards, two-pane pairing, versioned filenames, per-book cast).

Give this file to a coding model together with:

1. The ComfyUI API workflow JSON (current: `Krea2T__00007b_API01.json` or whatever V2 graph replaces it).
2. The last working sweep script (example: `sweep_anvMv07b_API04-comix.py` / the `05` build).
3. Optional: `attach_captions.py` and `captions/*.txt`.

The model must **implement V2**, not redesign the look. The MVP already found the look. V2 makes it usable by a stranger on a local PC with ComfyUI already running.

Do **not** invent a new sampler, a new LoRA merge, or a cloud backend.

---

## 1. What this product is

A local **comic press** for one picture-novel at a time.

Loop that must stay intact:

1. Lock style (trigger + Moebius clause + tail).
2. Lock characters (identity sentence ± reference images).
3. One plate = one scene + **one** material metaphor.
4. Generate via ComfyUI HTTP API.
5. Letter **after** the sampler: caption bar attached under the plate (width unchanged, height grows).

Name in the UI: **Plate Press**.  
Subtitle: local ComfyUI picture-novel press.

---

## 2. Hard constraints (from production)

These are not suggestions. They are why the MVP worked.

### 2.1 Stack

- ComfyUI at `http://127.0.0.1:8188` (configurable host/port).
- Checkpoint: `krea2_turbo_bf16.safetensors` (Krea2 **Turbo**, not Raw).
- LoRA: `Krea2-aethernouveau-04_merged.safetensors` (or the path used in the sweep script).
- Default LoRA strength: `0.80`.
- Sampler lock unless the user explicitly opens Advanced:
  - 8 steps
  - CFG 1
  - euler + beta (or er_sde + simple if that is what the shipped workflow already uses)
  - Do not change sampler mid-book.
- `batch_size = 1` in the graph; the **app** queues 2 seeds per plate by default (variance).

Read node IDs from the **example sweep script**, not from guesswork. Current MVP mapped:

- LoRA loader: node `"7"` — `lora_01`, `strength_01`
- Positive prompt: node `"2"` — `text`
- Negative prompt: node `"3"` — `text`
- Sampler seed: node `"8"` — `seed`, `control_after_generate = "fixed"`
- Empty latent batch: node `"15"` — `batch_size`
- Save prefix: node `"10"` — `filename_prefix`

If the V2 workflow JSON uses different node IDs, detect them from the JSON (title / class_type) and keep a small adapter. Do not hardcode new IDs without reading the file.

### 2.2 Prompt grammar

Every positive prompt the app sends must be:

```text
{STYLE} {CHARACTER_LOCK} {scene + exactly one metaphor} {TAIL}
```

Shipped defaults (editable in Settings, but these are the factory strings):

```text
STYLE = (
    "aethernouveau. Ink and watercolor by Moebius, thin black outlines, "
    "cream paper, muted ochre and black."
)
TAIL = " Sharp and in focus. No text. No logos."
ANDROID = (
    "A slim beautiful bald female android with blue eyes, "
    "in an opaque sleek spacesuit and brown gloves, complete coverage, bubble helmet"
)

PROMPTS = {
    "t1_one": (
        STYLE
        + " " + ANDROID
        + ", braced in a narrow hold, both brown gloves on a sealed ox-hide crate, "
        "the crate seams gleaming like liquid silver."
        + TAIL
    ),
    "t1_two": (
        STYLE
        + " " + ANDROID
        + ", braced in a narrow hold, both brown gloves on a sealed ox-hide crate, "
        "the crate seams gleaming like liquid silver, "
        "the hull behind her peeling like gold leaf over black glass."
        + TAIL
    ),
}
```

`t1_one` / `t1_two` are the smoke-test pair: same lock and scene; one metaphor vs two. Factory rule is still **one** metaphor per plate (`t1_one`). `t1_two` is only for comparing bleed.

Allowed metaphors (one per plate):

- spiderweb of black cells
- wet silk into teal glass
- stained glass
- gold leaf over black glass
- liquid silver
- fire-silk
- enamel

Do not insert the word `cloisonné` in factory prompts.

Never send caption text, speech balloons, or “comic panel with text box” to Comfy. That phrase wrecks the style.

### 2.3 Character locks

Example factory cards (user can edit):

```text
ANDROID = "A slim beautiful bald female android with blue eyes, in an opaque sleek spacesuit and brown gloves, complete coverage, bubble helmet"
AUGUR   = "A lean older man with grey cropped hair and a short neat beard, in a worn ochre-pale spacesuit and dark gloves, complete coverage, bubble helmet"
```

Rules:

- Identity words stay stable across a book.
- Suits default to opaque + complete coverage + gloves + bubble helmet.
- Do not use `NASA`, `EMU`, flags, patches. Those pull a different prior.
- One character per plate by default.
- Two-shots are allowed but flagged as risky (faces fuse).

### 2.4 Negative (factory)

```text
text, watermark, signature, letters, logo, NASA, flag, patch, photoreal astronaut, modern EMU suit, blurry, bad anatomy, deformed hands, extra fingers, fused fingers, plastic skin, nude, overexposed, underexposed
```

### 2.5 Seeds

- Do **not** use one seed for the whole book.
- Store `seed` per character once the user clicks **Lock seed from this plate**.
- Default generation: two random seeds per plate (`PER_PROMPT = 2`).
- Reroll plate = new seed(s), same prompt.

### 2.6 Lettering

Reuse the behavior of `attach_captions.py`:

- Do not draw on the plate.
- New canvas: same W, H + caption bar (~22% of H, minimum ~160px).
- Cream paper `(245, 236, 214)`, ink `(28, 22, 16)`, thin rule between plate and bar.
- Centered serif if available (DejaVu Serif / Liberation Serif), else default.
- Match caption file to image by slug in the filename (`p1_cargo` inside `ANV04_…_p1_cargo_SEED.webp`).

---

## 3. Out of scope for V2

Do not build:

- Cloud accounts, payments, or remote GPUs
- LoRA training
- In-image lettering / balloons
- Full page layout / gutters / multi-panel sheets
- Video
- A bundled LLM
- Auto-download of the 24.5 GiB checkpoint
- ControlNet as a required path

Optional later, not V2: ControlNet pose, helmet-off toggle as a second factory lock, PDF export of the whole book.

---

## 4. Architecture

Single local process.

Suggested layout:

```text
platepress/
  app.py                 # entry (FastAPI or Flask + static UI is fine)
  comfy_client.py        # queue prompt, poll /history or /queue, read outputs
  workflow_adapter.py    # load API JSON, fill nodes, optional ref-image nodes
  parser.py              # story wall + caption wall → list[Plate]
  lettering.py           # attach_captions port
  llm_sheet.txt          # shipped copy-paste instructions
  settings.json          # host, paths, STYLE, TAIL, NEG, strength
  books/<book_id>/
    book.json
    characters.json
    prompts_raw.txt
    captions_raw.txt
    plates/<slug>_<seed>.webp
    lettered/<slug>_<seed>_lettered.png
    seeds.json
    run_log.jsonl
```

Python 3.10+. Dependencies: web server, Pillow, urllib or httpx. No React rewrite required. A single HTML page + vanilla JS or HTMX is enough. If the implementer wants a small frontend framework, keep it one page.

ComfyUI is an **external** process. On startup, GET `/system_stats` or `/queue`. If it fails, show:

> ComfyUI is not running. Start it, then set host/port in Settings. Plate Press will not download the checkpoint.

---

## 5. Data model

```text
Character
  id
  name                  # ANDROID
  lock_text             # the sentence inserted into prompts
  ref_images[]          # local paths, 0–3
  locked_seed           # int | null
  notes

Plate
  slug                  # p1_cargo
  order                 # 1
  scene_text            # user wall text WITHOUT style/lock
  character_ids[]       # ["ANDROID"] or ["ANDROID","AUGUR"]
  metaphor              # detected or user-picked; optional
  helmet_on             # bool, default true
  caption               # string, may be multiline
  risky_twoshot         # bool

Run
  plate_slug
  seed
  positive_prompt       # fully assembled
  negative_prompt
  output_path
  status                # queued | done | error
```

`book.json` stores title, STYLE/TAIL overrides, character list, plate list, workflow filename.

---

## 6. UI — four views

Keep it ugly-simple. One column on a desktop browser at `http://127.0.0.1:7860` (or similar). Do not require a design system.

### 6.1 Settings / Press

- Comfy host/port
- Workflow JSON path
- Checkpoint name (display only if the workflow already pins it)
- LoRA filename + strength (default 0.80)
- STYLE, TAIL, NEG — textareas
- Images per plate (default 2)
- Output root
- Button: **Test connection**

Advanced (collapsed): sampler fields, only if present in the workflow.

### 6.2 Cast

List of character cards.

Per card:

- Name (token), e.g. `ANDROID`
- Lock textarea
- Upload / choose 1–3 reference stills (V2)
- Locked seed (read-only + Clear)
- Delete

Factory button: **Load demo cast** (ANDROID + AUGUR strings from this spec).

### 6.3 Book

Two big textareas.

**Prompts / story** — placeholder explains the format (see §7).

**Captions** — same slugs.

Also:

- Book title
- Parse button → preview table: slug, characters used, two-shot warning, assembled prompt preview (truncated)
- Generate missing / Generate all / Generate selected
- Checkbox: skip plates that already have a done run

### 6.4 Queue / Letter

Grid of thumbs from Comfy output or from `books/.../plates`.

Per thumb:

- slug, seed
- Lock seed to character X
- Reroll
- Use as character ref (copies path onto that card)
- Letter this plate / Letter all

Export:

- Open folder
- Write `export/` with lettered PNGs + `captions/` + `assembled_prompts.txt` + `seeds.json`

---

## 7. Parser (the product)

Users write a wall of text. The parser must accept **both** of these:

### 7.1 Preferred

```text
p1_cargo
braced in a narrow hold, both brown gloves on a sealed ox-hide crate lashed with pale straps, the crate seams gleaming like liquid silver

p2_claim
floating backward from an open hatch, one glove raised in refusal, cloaks peeling like gold leaf over black glass
```

### 7.2 Quoted name (also valid)

```text
"p1_cargo" braced in a narrow hold...
"p2_claim"
floating backward...
```

Rules:

- Slug line: optional quotes, token matching `^[A-Za-z][A-Za-z0-9_]*$` or `^p\d+_[A-Za-z0-9_]+$`. Prefer slugs that start with `p` and a number so ordering is obvious.
- Body = all following non-slug lines, stripped, joined with spaces.
- Blank line is allowed inside a body.
- `{ANDROID}` or bare `ANDROID` in the body or on the slug line assigns that character. If none mentioned, use a book-level **default character** (first card).
- If two known character tokens appear, mark `risky_twoshot`.
- Caption wall uses the same slug rules. Captions keep newlines (do not join into one line).
- Slugs in captions that are missing from prompts: warn, do not crash.
- Slugs in prompts with empty caption: allowed (lettering skips).

The app **assembles** the Comfy positive prompt:

```text
STYLE + " " + lock_1 + optional(", " + lock_2) + ", " + scene_text + TAIL
```

If `helmet_on` is false (future checkbox), the assembler may swap in a user-supplied “helmet off” lock. V2 can ship helmet-on only if that keeps scope small; add a per-plate checkbox if cheap.

Do not let the user paste a full STYLE paragraph into the story box and double-prefix. If a body starts with `aethernouveau`, strip STYLE/TAIL duplicates or warn.

---

## 8. V2 Comfy workflow: reference images

MVP workflow is text-only. V2 must accept a **second** API workflow JSON that has image inputs for character refs.

Implementer tasks:

1. Ship or document a workflow named like `Krea2T__V2_ref_API.json`.
2. It must still contain LoRA + Krea2 Turbo + the locked sampler.
3. Character ref path: IP-Adapter / InstantID / “Apply Style Model” / whatever is already standard in that user’s Comfy build **only if present in the JSON they attach**.
4. `workflow_adapter.py` maps:
   - `LoadImage` nodes ← character ref paths (resize not required if Comfy handles it)
   - strength slider default **low** (start 0.35–0.45; expose in Cast card)
5. If the user has no refs, fall back to the text-only workflow automatically.

Do not fail the whole book because one card has no image.

If the attached V2 JSON is missing, ship text-only and show:

> Reference workflow not loaded. Running text locks only.

Do not hallucinate node types that are not in the JSON.

---

## 9. Comfy client behavior

Port the sweep script:

1. Load workflow JSON.
2. Deep copy per job.
3. Fill LoRA name/strength, positive, negative, seed, filename prefix.
4. POST `/prompt`.
5. Record `prompt_id`.
6. Poll `/queue` until idle **or** poll `/history/{id}` per job (prefer per-job history so the UI can update one thumb at a time).
7. Copy or reference Comfy’s output image into `books/<id>/plates/`.
8. Prefix format:

```text
PP_{book}_{slug}_{seed}
```

Error handling:

- Connection refused → Settings message.
- Workflow node missing → show the node id and the JSON key that failed.
- Queue timeout → mark plate error, continue the rest.

Do not block the UI thread; generate on a worker.

---

## 10. Lettering module

Port `attach_captions.py` as `lettering.py`.

CLI not required inside the app, but keep a function:

```text
attach(image_path, text, out_path, bar_ratio=0.22)
```

Batch: for each done plate with a caption, write `_lettered.png`.

---

## 11. Shipped LLM sheet

Create `llm_sheet.txt` (also visible in UI as **Copy instructions for your LLM**). Exact contents:

```text
You are writing plates for Plate Press, a local ComfyUI picture-novel app.

Output two walls of text only, in this order:

PROMPTS
CAPTIONS

Rules:

- Do not write style, sampler, LoRA, or negative prompts. The app prepends those.
- Each plate starts with a slug on its own line, like p1_cargo
- After the slug, write 1–3 sentences of SCENE plus exactly ONE material metaphor.
- Allowed metaphors (pick one per plate): spiderweb of black cells; wet silk into teal glass; stained glass; gold leaf over black glass; liquid silver; fire-silk; enamel.
- Do not write the word cloisonné.
- Do not ask for text, logos, captions, speech balloons, or comic-page layout in the picture.
- Refer to characters only by the lock names the user provides, e.g. ANDROID or {ANDROID}.
- Default to one character per plate. Use two names only when both bodies must appear.
- Keep identity words stable. Do not change hair, sex, suit, or helmet unless the user says helmets off.
- Suits stay opaque, complete coverage, gloves on, bubble helmet on unless specified.
- Tone: stoic, Roman/Greek, tongue-in-cheek. Short.

CAPTIONS:
- Same slugs as PROMPTS.
- Two or three short narrator lines.
- Do not repeat the prompt. The caption is the moral; the prompt is the camera.
- No lettering instructions.

The user will now paste character locks and a prose story.

Return only:

PROMPTS

p1_shortname
scene + one metaphor

p2_shortname
scene + one metaphor

CAPTIONS

p1_shortname
line
line

p2_shortname
line
line
```

UI button copies that sheet plus the current cast locks appended under a heading `CHARACTER LOCKS`.

---

## 12. Demo book (optional but useful)

If cheap, ship a “Load Bos Sidereal demo” that fills:

- Cast: ANDROID + AUGUR (strings in §2.3)
- Prompt wall and caption wall from the Bos Sidereal ten plates (p1_cargo … p10_enough)

Do not require demo images.

---

## 13. Acceptance tests

A coding model should not mark V2 done until these work on a machine that already runs the MVP sweep:

1. App starts, detects Comfy up/down.
2. User pastes a 3-plate prompt wall + captions, Parse shows 3 rows.
3. Generate queues 3 × 2 jobs (default) through the **existing** text workflow and writes files with slugs in the names.
4. Letter all produces taller PNGs, same width, caption text from the matching slug.
5. Two-shot plate shows a warning in the preview table.
6. Missing Comfy → no crash, visible error.
7. `{ANDROID}` in a body injects the ANDROID lock and does not leave the token in the assembled prompt.
8. Settings persist to `settings.json`.
9. README states: ComfyUI must already run; this app does not fetch the 26 GB Turbo file.

---

## 14. README (ship with V2)

Short:

- What it is
- Requires: ComfyUI + Krea2 Turbo + the LoRA + the API workflow JSON
- Install: `pip install …`, `python app.py`
- Put workflow JSON path in Settings
- How to paste a book
- How to letter
- How to copy the LLM sheet
- House style: no text in the sampler; one metaphor; opaque suits; no NASA words if you want this look

---

## 15. Implementation order for the coding model

1. Parser + unit tests on sample walls (no Comfy).
2. Port sweep script → `comfy_client.py` against the **provided** MVP workflow JSON.
3. Minimal UI: Settings, Book textareas, Generate, folder of outputs.
4. Port lettering.
5. Cast cards + seed lock.
6. Workflow adapter for ref images **only if** a V2 JSON is supplied.
7. LLM sheet button + export pack.
8. Polish: two-shot warning, demo book, README.

Stop after a stranger can paste Bos Sidereal, get plates, letter them, and export a folder.

---

## 16. Voice of the UI copy

Blunt. Short. No marketing. Errors name the missing node or the missing slug. Do not apologize at length.
