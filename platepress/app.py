#!/usr/bin/env python3
"""Plate Press — local ComfyUI picture-novel press."""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .comfy_client import ComfyClient, ComfyError
from .defaults import EXAMPLES
from .demo import BOS_CAPTIONS, BOS_PROMPTS, DEMO_CAST, T1_CAPTIONS, T1_PROMPTS
from .lettering import attach
from .parser import (
    Character,
    assemble,
    assemble_pair,
    extract_inline_panes,
    pad_slug,
    parse_book,
    same_slug,
)
from .store import (
    PKG,
    append_run,
    book_dir,
    delete_book_dir,
    empty_book,
    is_protected_book,
    iter_image_files,
    job_workflows,
    list_api_workflows,
    list_books,
    list_weights,
    load_book,
    load_seeds,
    load_settings,
    match_combo_name,
    normalize_loras,
    new_id,
    portable_path,
    safe_book_id,
    save_book,
    save_settings,
    write_seeds,
)
from .workflow_adapter import fill, load_workflow

app = FastAPI(title="Plate Press")
STATIC = PKG / "static"
LLM_SHEET = (PKG / "llm_sheet.txt").read_text(encoding="utf-8")

_job_q: list[dict[str, Any]] = []
_q_lock = threading.Lock()
_worker_started = False
_pause = threading.Event()
_pause.set()


def _settings() -> dict[str, Any]:
    return load_settings()


def _client(s: dict[str, Any] | None = None) -> ComfyClient:
    s = s or _settings()
    return ComfyClient(host=s["host"], port=int(s["port"]))


def _safe_ref_key(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum() or ch in "_-") or "char"


def _char_ref_dir(s: dict[str, Any], book: dict[str, Any], c: dict[str, Any] | Character) -> Path:
    cid = c.id if isinstance(c, Character) else (c.get("id") or "")
    name = c.name if isinstance(c, Character) else (c.get("name") or "")
    key = _safe_ref_key(str(cid or name or "char"))
    return book_dir(s, book.get("id")) / "refs" / key


def _char_ref_dirs(s: dict[str, Any], book: dict[str, Any], c: dict[str, Any] | Character) -> list[Path]:
    cid = c.id if isinstance(c, Character) else (c.get("id") or "")
    name = c.name if isinstance(c, Character) else (c.get("name") or "")
    keys = []
    for raw in (cid, name):
        if not raw:
            continue
        k = _safe_ref_key(str(raw))
        if k not in keys:
            keys.append(k)
    root = book_dir(s, book.get("id")) / "refs"
    return [root / k for k in keys]


def _scan_ref_files(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    out: list[str] = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            out.append(str(p.resolve()))
    return out


def _enrich_character_refs(s: dict[str, Any], book: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
    """Folder is source of stills. Exactly one is active; the rest are disabled."""
    def _abs_ref(p: str) -> str:
        path = Path(str(p)).expanduser()
        if not path.is_absolute():
            path = book_dir(s, book.get("id"), create=False) / path
        return str(path.resolve())

    listed = [_abs_ref(p) for p in (c.get("ref_images") or []) if p]
    ignored = {_abs_ref(p) for p in (c.get("ref_ignored") or []) if p}
    scanned: list[str] = []
    for folder in _char_ref_dirs(s, book, c):
        scanned.extend(_scan_ref_files(folder))
    paths: list[str] = []
    for p in listed + scanned:
        if p in ignored:
            continue
        if p not in paths:
            paths.append(p)
    active = c.get("ref_active")
    if active:
        active = _abs_ref(str(active))
    if active not in paths:
        active = listed[-1] if listed else (paths[-1] if paths else None)
    c["ref_images"] = paths
    c["ref_active"] = active
    root = Path(s["output_root"]).resolve()
    slots = []
    for p in paths:
        fp = Path(p)
        try:
            url = "/media/" + fp.resolve().relative_to(root).as_posix()
        except ValueError:
            url = ""
        slots.append(
            {
                "path": p,
                "url": url,
                "name": fp.name,
                "active": bool(active and Path(active).resolve() == fp.resolve()),
            }
        )
    c["ref_slots"] = slots
    return c


def _chars(book: dict[str, Any]) -> list[Character]:
    s = _settings()
    out: list[Character] = []
    for raw in book.get("characters") or []:
        c = _enrich_character_refs(s, book, dict(raw))
        out.append(
            Character(
                id=c.get("id") or new_id(),
                name=c.get("name") or "",
                lock_text=c.get("lock_text") or "",
                ref_images=list(c.get("ref_images") or []),
                ref_active=c.get("ref_active"),
                locked_seed=c.get("locked_seed"),
                notes=c.get("notes") or "",
            )
        )
    return out


def _refs_for(plate, chars: list[Character], names: list[str] | None = None) -> list[Path]:
    """Exactly one still per character named on the plate. Default lock does not send a still."""
    by = {c.name: c for c in chars}
    paths: list[Path] = []
    if names is not None:
        ids = names
    elif getattr(plate, "named_ids", None) is not None:
        ids = plate.named_ids
    else:
        ids = plate.character_ids
    for name in ids:
        c = by.get(name)
        if not c:
            continue
        pick = c.ref_active
        if pick and Path(pick).exists():
            paths.append(Path(pick))
            continue
        existing = [Path(p) for p in c.ref_images if p and Path(p).exists()]
        if existing:
            paths.append(existing[-1])
    return paths[:3]


def _done_slugs(d: Path) -> set[str]:
    found: set[str] = set()
    plates = d / "plates"
    if not plates.exists():
        return found
    for p in plates.iterdir():
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        found.add(p.stem)
        slug = _plate_slug(p.name)
        found.add(slug)
        found.add(pad_slug(slug))
        parts = p.stem.rsplit("_", 1)
        if parts:
            found.add(parts[0])
    return found


def _parse(book: dict[str, Any], s: dict[str, Any], picture_counts: dict[str, int] | None = None):
    chars = _chars(book)
    style = book.get("style") or s["style"]
    tail = book.get("tail") or s.get("tail") or ""
    return parse_book(
        book.get("prompts_raw") or "",
        book.get("captions_raw") or "",
        chars,
        style=style,
        tail=tail,
        n_pictures_for=picture_counts,
        cutout=bool(s.get("ref_cutout")),
        cutout_text=str(s.get("ref_cutout_text") or ""),
        layout=s.get("layout") or "one",
        layout_text=s.get("layout_text") or "",
    )


def _start_worker() -> None:
    global _worker_started
    if _worker_started:
        return
    t = threading.Thread(target=_worker_loop, name="platepress-worker", daemon=True)
    t.start()
    _worker_started = True


def _worker_loop() -> None:
    while True:
        _pause.wait()
        with _q_lock:
            job = _job_q.pop(0) if _job_q else None
        if job is None:
            threading.Event().wait(0.25)
            continue
        try:
            _run_job(job)
        except Exception as e:
            _fail_job(job, str(e), traceback.format_exc())


def _fail_job(job: dict[str, Any], err: str, tb: str = "") -> None:
    s = _settings()
    run = {
        "plate_slug": job.get("slug"),
        "seed": job.get("seed"),
        "positive_prompt": job.get("assembled"),
        "negative_prompt": job.get("negative"),
        "output_path": None,
        "status": "error",
        "error": err,
        "trace": tb[-2000:],
        "prompt_id": job.get("prompt_id"),
        "batch_id": job.get("batch_id"),
        "batch_at": job.get("batch_at"),
    }
    append_run(s, run, job.get("book_id"))


def _run_job(job: dict[str, Any]) -> None:
    s = _settings()
    book_id = job["book_id"]
    d = book_dir(s, book_id)
    client = _client(s)
    ok, msg = client.ping()
    if not ok:
        raise ComfyError(msg)

    image_names: list[str] = []
    for p in job.get("ref_paths") or []:
        image_names.append(client.upload_image(Path(p)))

    wf_path = Path(job["workflow"])
    wf = load_workflow(wf_path)
    slots = normalize_loras(s)
    unet_name = str(s.get("unet_name") or "").strip() or None
    try:
        info = client.object_info()
        unets = client.list_unets(info)
        lora_names = client.list_loras(info)
    except Exception:
        unets, lora_names = [], []
    if unet_name and unets:
        resolved = match_combo_name(unet_name, unets)
        if not resolved:
            raise ComfyError(
                f"UNET {unet_name!r} is not in Comfy UNETLoader. "
                "Load lists from Comfy and pick the exact name "
                "(subfolder prefix counts, e.g. KREA2/krea2_turbo_bf16.safetensors)."
            )
        unet_name = resolved
    if lora_names:
        fixed: list[dict[str, Any]] = []
        for slot in slots:
            hit = match_combo_name(slot["name"], lora_names)
            if not hit:
                raise ComfyError(
                    f"LoRA {slot['name']!r} is not in Comfy's LoRA list. "
                    "Load lists from Comfy and pick the exact name (subfolder prefix counts)."
                )
            fixed.append({**slot, "name": hit})
        slots = fixed
    filled = fill(
        wf,
        positive=job["assembled"],
        negative=job["negative"],
        seed=int(job["seed"]),
        prefix=job["prefix"],
        lora_name=(slots[0]["name"] if slots else s.get("lora_name") or ""),
        lora_strength=float(slots[0]["strength"] if slots else s.get("lora_strength") or 0),
        image_names=image_names,
        batch_size=1,
        steps=int(s.get("steps") or 8),
        cfg=float(s.get("cfg") or 1),
        sampler_name=s.get("sampler_name") or "euler",
        scheduler=s.get("scheduler") or "beta",
        unet_name=unet_name,
        loras=slots,
    )
    prompt_id = client.queue(filled)
    job["prompt_id"] = prompt_id
    hist = client.wait(prompt_id, timeout_s=float(s.get("job_timeout_s") or 600))
    stem = _file_stem(book_id, job["slug"], int(job.get("run") or 1))
    written = client.fetch_images(hist, d / "plates", stem)
    if not written:
        raise ComfyError(f"job {prompt_id} produced no images")
    run = {
        "plate_slug": job["slug"],
        "seed": job["seed"],
        "positive_prompt": job["assembled"],
        "negative_prompt": job["negative"],
        "output_path": str(written[0]),
        "status": "done",
        "prompt_id": prompt_id,
        "workflow": wf_path.name,
        "refs": job.get("ref_paths") or [],
        "batch_id": job.get("batch_id"),
        "batch_at": job.get("batch_at"),
    }
    append_run(s, run, book_id)
    seeds = load_seeds(s, book_id)
    seeds.setdefault("plates", {}).setdefault(job["slug"], []).append(job["seed"])
    write_seeds(s, seeds, book_id)


def _enqueue(jobs: list[dict[str, Any]]) -> int:
    _start_worker()
    with _q_lock:
        _job_q.extend(jobs)
        n = len(_job_q)
    return n


def _assert_unique_names(chars: list[dict[str, Any]]) -> None:
    seen: list[str] = []
    for c in chars:
        n = (c.get("name") or "").strip()
        if not n:
            continue
        if n in seen:
            raise HTTPException(
                400,
                f"token {n} already exists. One card per name. Replace the still on that card.",
            )
        seen.append(n)


def _next_token(chars: list[dict[str, Any]]) -> str:
    names = {(c.get("name") or "") for c in chars}
    i = 1
    while True:
        n = "CHAR" if i == 1 else f"CHAR_{i}"
        if n not in names:
            return n
        i += 1


def _ref_notice(s: dict[str, Any], chars: list[Character]) -> str | None:
    has_refs = any(c.ref_images for c in chars)
    ref_path = Path(s.get("workflow_ref") or "")
    if has_refs and not ref_path.exists():
        return "Reference workflow not loaded. Running text locks only."
    return None


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = STATIC / "index.html"
    return HTMLResponse(html.read_text(encoding="utf-8"))


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    s = _settings()
    s["examples"] = EXAMPLES
    return s


@app.post("/api/settings")
def post_settings(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    body = dict(body)
    body.pop("examples", None)
    s.update(body)
    save_settings(s)
    out = _settings()
    out["examples"] = EXAMPLES
    return out


@app.get("/api/comfy/test")
def test_comfy() -> dict[str, Any]:
    ok, msg = _client().ping()
    return {"ok": ok, "message": msg}


@app.get("/api/workflows")
def get_workflows() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    return {
        "default": s.get("workflow_text") or "",
        "selected": book.get("workflow") or "",
        "workflows": list_api_workflows(s, book.get("id")),
    }


@app.post("/api/weights")
def post_weights(body: dict[str, Any]) -> dict[str, Any]:
    """Prefer Comfy's UNETLoader / LoRA combo lists so names match on queue."""
    models: list[str] = []
    loras: list[str] = []
    errors: list[str] = []
    source = ""
    s = _settings()
    host = str(body.get("host") or s.get("host") or "127.0.0.1")
    try:
        port = int(body.get("port") or s.get("port") or 8188)
    except (TypeError, ValueError):
        port = int(s.get("port") or 8188)
    client = ComfyClient(host=host, port=port)
    ok, msg = client.ping()
    if ok:
        try:
            info = client.object_info()
            models = client.list_unets(info)
            loras = client.list_loras(info)
            source = "comfy"
        except Exception as e:
            errors.append(f"Comfy lists: {e}")
    elif not (str(body.get("models_dir") or "").strip() or str(body.get("loras_dir") or "").strip()):
        errors.append(msg)
    models_dir = str(body.get("models_dir") or "").strip()
    loras_dir = str(body.get("loras_dir") or "").strip()
    if not models and models_dir:
        try:
            models = list_weights(models_dir)
            source = source or "folders"
        except Exception as e:
            errors.append(f"models folder: {e}")
    if not loras and loras_dir:
        try:
            loras = list_weights(loras_dir)
            source = source or "folders"
        except Exception as e:
            errors.append(f"loras folder: {e}")
    if not models and not models_dir and source != "comfy":
        errors.append("start Comfy, or set the diffusion models folder")
    if not loras and not loras_dir and source != "comfy":
        errors.append("start Comfy, or set the LoRAs folder")
    return {"models": models, "loras": loras, "errors": errors, "source": source}


@app.get("/api/book")
def get_book() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    book = _book_payload(s, book)
    notice = _ref_notice(s, _chars(book))
    return {"book": book, "notice": notice, "dir": str(book_dir(s))}


@app.post("/api/book")
def post_book(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    for k in (
        "title",
        "prompts_raw",
        "captions_raw",
        "characters",
        "style",
        "tail",
        "plates",
        "workflow",
    ):
        if k not in body:
            continue
        if k == "workflow":
            raw = body[k]
            if raw:
                book[k] = portable_path(raw, follow_symlinks=False)
            else:
                book[k] = None
        else:
            book[k] = body[k]
    if "characters" in body:
        _assert_unique_names(book.get("characters") or [])
    save_book(s, book)
    return {"book": _book_payload(s, book), "dir": str(book_dir(s))}


@app.post("/api/parse")
def post_parse() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    chars = _chars(book)
    picture_counts: dict[str, int] = {}
    result = _parse(book, s)
    ref_path = Path(s.get("workflow_ref") or "")
    use_ref = bool(s.get("send_refs")) and ref_path.exists()
    for p in result.plates:
        n = len(_refs_for(p, chars)) if use_ref else 0
        picture_counts[p.slug] = n
    result = _parse(book, s, picture_counts)
    book["plates"] = [
        {
            "slug": p.slug,
            "order": p.order,
            "scene_text": p.scene_text,
            "character_ids": p.character_ids,
            "metaphor": p.metaphor,
            "helmet_on": p.helmet_on,
            "caption": p.caption,
            "risky_twoshot": p.risky_twoshot,
            "assembled": p.assembled,
            "warnings": p.warnings,
            "pane": p.pane,
            "pair_with": p.pair_with,
        }
        for p in result.plates
    ]
    save_book(s, book)
    notice = _ref_notice(s, chars)
    return {
        "plates": book["plates"],
        "warnings": result.warnings,
        "notice": notice,
    }


def _split_units(want: list, all_plates: list) -> tuple[list[tuple], int, str]:
    """Pair selected plates. Inline left/right in one slug is a whole plate. Else 1|2, 3|4."""
    units: list[tuple] = []
    skipped = 0
    bits: list[str] = []
    i = 0
    while i < len(want):
        w = want[i]
        if (getattr(w, "pane_left", "") and getattr(w, "pane_right", "")) or extract_inline_panes(
            getattr(w, "scene_text", "") or ""
        ):
            units.append((w, w))
            i += 1
            continue
        if i + 1 < len(want):
            units.append((want[i], want[i + 1]))
            i += 2
            continue
        idx = next((n for n, p in enumerate(all_plates) if same_slug(p.slug, w.slug)), None)
        if idx is not None and idx + 1 < len(all_plates):
            nxt = all_plates[idx + 1]
            if not extract_inline_panes(getattr(nxt, "scene_text", "") or ""):
                units.append((w, nxt))
                i += 1
                continue
        skipped += 1
        bits.append(f"{w.slug} has no pair for two-pane (need a next prompt on the wall).")
        i += 1
    return units, skipped, " ".join(bits)


@app.post("/api/generate")
def post_generate(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    if "send_refs" in body:
        s["send_refs"] = bool(body["send_refs"])
        save_settings(s)
    book = load_book(s)
    chars = _chars(book)
    parsed = _parse(book, s)
    if not parsed.plates:
        raise HTTPException(400, "no plates — paste a prompt wall and Parse")
    slugs = body.get("slugs")
    skip_done = bool(body.get("skip_done", True))
    if slugs is not None:
        skip_done = False
    book_id = book.get("id") or "default"
    d = book_dir(s)
    renamed = normalize_plate_filenames(d, book_id)
    if _patch_run_output_paths(book, renamed):
        save_book(s, book)
    done_files = _done_slugs(d)
    run_no = _next_run(d / "plates", book_id)
    want = [
        p
        for p in parsed.plates
        if slugs is None or any(same_slug(p.slug, sel) for sel in slugs)
    ]
    if slugs:
        missing = [
            sel
            for sel in slugs
            if not any(same_slug(p.slug, sel) for p in parsed.plates)
        ]
        if missing:
            extra = (
                "not in the wall: "
                + ", ".join(missing)
                + ". Parse after you edit, then select again."
            )
            notice = extra
        else:
            notice = ""
    else:
        notice = ""
    if not want:
        raise HTTPException(400, "no matching slugs")

    ok, msg = _client(s).ping()
    if not ok:
        return {"ok": False, "error": msg, "queued": 0}

    text_wf, ref_wf = job_workflows(s, book)
    if str(book.get("workflow") or "").strip() and not text_wf.is_file():
        raise HTTPException(400, f"book workflow JSON missing: {text_wf}")
    per = int(s.get("images_per_plate") or 2)
    jobs: list[dict[str, Any]] = []
    skipped = 0
    by = {c.name: c for c in chars}
    ref_note = _ref_notice(s, chars)
    send_refs = bool(s.get("send_refs"))
    if not send_refs:
        extra = "Stills not sent. Text locks only."
        ref_note = f"{ref_note} {extra}".strip() if ref_note else extra
    notice = " ".join(x for x in (notice, ref_note) if x).strip()
    batch_id = new_id("b")
    batch_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    split = (s.get("layout") or "one") == "split"
    units: list[tuple] = []
    if split:
        more, nskip, extra = _split_units(want, parsed.plates)
        units = more
        skipped += nskip
        if extra:
            notice = f"{notice} {extra}".strip() if notice else extra
    else:
        units = [
            (p, p)
            if (getattr(p, "pane_left", "") and getattr(p, "pane_right", ""))
            or extract_inline_panes(getattr(p, "scene_text", "") or "")
            else (p, None)
            for p in want
        ]

    for left, right in units:
        inline = (
            right is left
            or (right is not None and same_slug(left.slug, right.slug))
        ) and extract_inline_panes(left.scene_text)
        if right is not None or inline:
            if inline:
                panes = extract_inline_panes(left.scene_text)
                ls = left.pane_left or (panes[0] if panes else "")
                rs = left.pane_right or (panes[1] if panes else "")
                combo = pad_slug(left.slug)
                ids_l = list(left.pane_left_ids or left.named_ids or [])
                ids_r = list(left.pane_right_ids or [])
                lock_ids_l = ids_l or list(left.character_ids or [])
                lock_ids_r = ids_r
                locks_l = [by[n].lock_text for n in lock_ids_l if n in by]
                locks_r = [by[n].lock_text for n in lock_ids_r if n in by]
                left_scene, right_scene = ls, rs
                refs_l = _refs_for(left, chars, ids_l) if (send_refs and ref_wf.exists()) else []
                refs_r = _refs_for(left, chars, ids_r) if (send_refs and ref_wf.exists() and ids_r) else []
            else:
                combo = f"{pad_slug(left.slug)}_{pad_slug(right.slug)}"
                refs_l = _refs_for(left, chars) if (send_refs and ref_wf.exists()) else []
                refs_r = _refs_for(right, chars) if (send_refs and ref_wf.exists()) else []
                locks_l = [by[n].lock_text for n in left.character_ids if n in by]
                locks_r = [by[n].lock_text for n in right.character_ids if n in by]
                left_scene, right_scene = left.scene_text, right.scene_text
            existing = [n for n in done_files if combo in n]
            if skip_done and existing:
                skipped += 1
                continue
            refs = (refs_l[:1] + refs_r[:1])[:3]
            assembled = assemble_pair(
                book.get("style") or s["style"],
                locks_l,
                left_scene,
                locks_r,
                right_scene,
                book.get("tail") or s.get("tail") or "",
                layout_text=s.get("layout_text") or "",
                n_left_refs=min(1, len(refs_l)),
                n_right_refs=min(1, len(refs_r)),
                cutout=bool(s.get("ref_cutout")),
                cutout_text=str(s.get("ref_cutout_text") or ""),
            )
            job_slug = combo
            seed_from = left
        else:
            p = left
            existing = [n for n in done_files if pad_slug(p.slug) in n or p.slug in n]
            if skip_done and existing:
                skipped += 1
                continue
            refs = _refs_for(p, chars) if (send_refs and ref_wf.exists()) else []
            locks = [by[n].lock_text for n in p.character_ids if n in by]
            assembled = assemble(
                book.get("style") or s["style"],
                locks,
                p.scene_text,
                book.get("tail") or s["tail"] or "",
                n_pictures=len(refs),
                cutout=bool(s.get("ref_cutout")),
                cutout_text=str(s.get("ref_cutout_text") or ""),
                layout=s.get("layout") or "one",
                layout_text=s.get("layout_text") or "",
            )
            job_slug = p.slug
            seed_from = p
        if refs:
            wf = str(ref_wf)
        elif text_wf.exists():
            wf = str(text_wf)
        elif ref_wf.exists():
            wf = str(ref_wf)
        else:
            raise HTTPException(400, f"workflow JSON missing: {text_wf}")
        seeds: list[int] = []
        locked = None
        if seed_from.character_ids:
            c = by.get(seed_from.character_ids[0])
            if c and c.locked_seed is not None:
                locked = int(c.locked_seed)
        if locked is not None:
            seeds.append(locked)
        while len(seeds) < per:
            seeds.append(random.randint(0, 2**53 - 1))
        for seed in seeds:
            prefix = f"PP_{book_id}_v{run_no:02d}_{pad_slug(job_slug) if right is None else job_slug}"
            jobs.append(
                {
                    "book_id": book_id,
                    "slug": job_slug,
                    "seed": seed,
                    "run": run_no,
                    "assembled": assembled,
                    "negative": s["neg"],
                    "prefix": prefix,
                    "workflow": wf,
                    "ref_paths": [str(x) for x in refs],
                    "batch_id": batch_id,
                    "batch_at": batch_at,
                }
            )
            append_run(
                s,
                {
                    "plate_slug": job_slug,
                    "seed": seed,
                    "positive_prompt": assembled,
                    "negative_prompt": s["neg"],
                    "output_path": None,
                    "status": "queued",
                    "batch_id": batch_id,
                    "batch_at": batch_at,
                },
                book.get("id"),
            )
    n = _enqueue(jobs)
    return {
        "ok": True,
        "queued": len(jobs),
        "queue_depth": n,
        "skipped": skipped,
        "notice": notice,
        "message": notice,
        "batch_id": batch_id,
    }


@app.post("/api/reroll")
def post_reroll(body: dict[str, Any]) -> dict[str, Any]:
    slug = body.get("slug")
    if not slug:
        raise HTTPException(400, "slug required")
    found = _slugs_in_name(slug)
    return post_generate({"slugs": found or [slug], "skip_done": False})


def _run_key(slug: Any, seed: Any) -> str:
    return f"{slug}_{seed}"


_SLUG_IN_NAME = re.compile(r"(?:^|_)((?:p|t)(\d+)_[A-Za-z0-9]+)", re.I)


def _slugs_in_name(name: str) -> list[str]:
    return [m.group(1) for m in _SLUG_IN_NAME.finditer(name or "")]


def _plate_slug(name: str) -> str:
    found = _slugs_in_name(name)
    return found[0] if found else Path(name).stem


def _seed_from_stem(stem: str, slug: str | None = None) -> int | None:
    if slug and (stem == f"{slug}" or stem.startswith(slug + "_")):
        rest = stem[len(slug) :].lstrip("_")
        if rest.isdigit():
            return int(rest)
    m = re.search(r"_(\d{10,})$", stem)
    return int(m.group(1)) if m else None


def _file_stem(book_id: str, slug: str, run: int) -> str:
    found = _slugs_in_name(slug)
    body = "_".join(pad_slug(x) for x in found[:2]) if found else pad_slug(slug)
    return f"{book_id}_v{int(run):02d}_{body}"


def _version_label(run: int | None) -> str:
    if not run:
        return "ungrouped"
    return f"v{int(run):02d}"


def _run_from_stem(stem: str, book_id: str) -> int | None:
    prefix = f"{book_id}_"
    if not stem.startswith(prefix):
        return None
    rest = stem[len(prefix) :]
    m = re.match(r"v(\d{2,})_", rest, re.I)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d{3})_", rest)
    return int(m.group(1)) if m else None


def _next_run(plates_dir: Path, book_id: str) -> int:
    n = 0
    if plates_dir.exists():
        for p in plates_dir.iterdir():
            r = _run_from_stem(p.stem, book_id)
            if r:
                n = max(n, r)
    return n + 1


def _is_canonical_stem(stem: str, book_id: str, slug: str) -> bool:
    prefix = f"{book_id}_"
    if not stem.startswith(prefix):
        return False
    rest = stem[len(prefix) :]
    return bool(
        re.match(
            r"v\d{2,}(?:_(?:p|t)\d{3,}_[A-Za-z0-9]+){1,2}(?:_\d{1,9})?$",
            rest,
            re.I,
        )
    )


def _next_canonical_stem(book_id: str, slug: str, taken: set[str], run: int) -> str:
    base = _file_stem(book_id, slug, run)
    if base not in taken:
        return base
    n = 2
    while f"{base}_{n}" in taken:
        n += 1
    return f"{base}_{n}"


def normalize_plate_filenames(book_root: Path, book_id: str) -> list[tuple[Path, Path]]:
    """Rename plates to {book_id}_v01_p001_slug.png. Seed is not in the file name."""
    plates = book_root / "plates"
    if not plates.exists():
        return []
    files = [
        p
        for p in plates.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    files.sort(key=lambda p: p.stat().st_mtime)
    taken: set[str] = set()
    pending: list[Path] = []
    for p in files:
        slug = _plate_slug(p.name)
        if _is_canonical_stem(p.stem, book_id, slug):
            taken.add(p.stem)
        else:
            pending.append(p)
    renamed: list[tuple[Path, Path]] = []
    lettered = book_root / "lettered"
    for p in pending:
        slug = _plate_slug(p.name)
        ver = _run_from_stem(p.stem, book_id) or 1
        new_stem = _next_canonical_stem(book_id, slug, taken, run=ver)
        taken.add(new_stem)
        dest = p.with_name(new_stem + p.suffix)
        if dest.exists():
            continue
        old_stem = p.stem
        p.rename(dest)
        renamed.append((p, dest))
        if lettered.exists():
            sib = lettered / f"{old_stem}_lettered{p.suffix}"
            if sib.exists():
                sib.rename(lettered / f"{new_stem}_lettered{p.suffix}")
    return renamed


def _patch_run_output_paths(book: dict[str, Any], renamed: list[tuple[Path, Path]]) -> bool:
    if not renamed:
        return False
    by_name = {old.name: str(new) for old, new in renamed}
    by_path = {str(old): str(new) for old, new in renamed}
    changed = False
    for run in book.get("runs") or []:
        op = run.get("output_path") or ""
        if not op:
            continue
        if op in by_path:
            run["output_path"] = by_path[op]
            changed = True
            continue
        bn = Path(op).name
        if bn in by_name:
            run["output_path"] = by_name[bn]
            changed = True
    return changed


def _slug_sort_key(t: dict[str, Any]) -> tuple:
    name = t.get("name") or t.get("stem") or t.get("slug") or ""
    run = t.get("run")
    if run is None:
        run = _run_from_stem(Path(name).stem, t.get("book_id") or "") or 0
    m = _SLUG_IN_NAME.search(name)
    plate = int(m.group(2)) if m else 10_000
    slug = m.group(1).lower() if m else name.lower()
    return (int(run), plate, slug, name.lower())


def _group_by_version(thumbs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One Queue grid per generate. Newest version first."""
    buckets: dict[int, list[dict[str, Any]]] = {}
    for t in thumbs:
        v = int(t.get("run") or t.get("version") or 0)
        buckets.setdefault(v, []).append(t)
    batches: list[dict[str, Any]] = []
    for v in sorted(buckets, reverse=True):
        group = sorted(buckets[v], key=_slug_sort_key)
        label = _version_label(v)
        mtime = max((t.get("mtime") or 0) for t in group) if group else 0
        batches.append(
            {
                "id": label,
                "version": v,
                "label": label,
                "thumbs": group,
                "n": len(group),
                "mtime": mtime,
            }
        )
    return batches


def _group_thumbs(thumbs: list[dict[str, Any]], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for run in runs:
        slug, seed = run.get("plate_slug"), run.get("seed")
        if slug is None or seed is None:
            continue
        by_key[_run_key(slug, seed)] = run
    def _tag(t: dict[str, Any], run: dict[str, Any]) -> None:
        t["batch_id"] = run.get("batch_id")
        t["batch_at"] = run.get("batch_at")
        if run.get("seed") is not None:
            t["seed"] = run.get("seed")
        if run.get("plate_slug"):
            t["slug"] = run.get("plate_slug")
        refs = run.get("refs") or []
        wf = run.get("workflow") or ""
        t["via"] = "still" if refs or "V2_ref" in wf else "text"

    by_path = {r.get("output_path"): r for r in runs if r.get("output_path")}
    for t in thumbs:
        run = by_path.get(t.get("path"))
        if run is None:
            run = by_key.get(t.get("stem") or "")
        if run is None:
            stem = t.get("stem") or ""
            for k, cand in by_key.items():
                if stem.endswith(k) or k in stem:
                    run = cand
                    break
        if run:
            _tag(t, run)
    tagged = [t for t in thumbs if t.get("batch_id")]
    loose = [t for t in thumbs if not t.get("batch_id")]
    batches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for t in tagged:
        bid = t["batch_id"]
        if bid in seen:
            continue
        seen.add(bid)
        group = [x for x in tagged if x.get("batch_id") == bid]
        when = t.get("batch_at") or ""
        batches.append({"id": bid, "at": when, "thumbs": group, "mtime": group[0].get("mtime") or 0})
    loose_sorted = sorted(loose, key=lambda x: x.get("mtime") or 0, reverse=True)
    gap = 120.0
    cluster: list[dict[str, Any]] = []
    clusters: list[list[dict[str, Any]]] = []
    for t in loose_sorted:
        if cluster and (cluster[-1].get("mtime") or 0) - (t.get("mtime") or 0) > gap:
            clusters.append(cluster)
            cluster = []
        cluster.append(t)
    if cluster:
        clusters.append(cluster)
    for i, group in enumerate(clusters):
        mtime = group[0].get("mtime") or 0
        when = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else ""
        batches.append({"id": f"disk-{i}", "at": when, "thumbs": group, "mtime": mtime})
    batches.sort(key=lambda b: b.get("mtime") or 0, reverse=True)
    for b in batches:
        b["thumbs"] = sorted(b.get("thumbs") or [], key=_slug_sort_key)
        n = len(b["thumbs"])
        b["label"] = f"{b.get('at') or ''} · {n}"
    return batches


def _thumbs_for_book(s: dict[str, Any], bid: str) -> list[dict[str, Any]]:
    root = Path(s["output_root"])
    d = root / bid
    plates = d / "plates"
    thumbs: list[dict[str, Any]] = []
    if not plates.exists():
        return thumbs
    for p in plates.iterdir():
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        rel = p.relative_to(root)
        found = _slugs_in_name(p.name)
        slug = "_".join(found) if found else _plate_slug(p.name)
        seed = _seed_from_stem(p.stem, slug)
        run = _run_from_stem(p.stem, bid)
        thumbs.append(
            {
                "path": str(p),
                "url": "/media/" + rel.as_posix(),
                "name": p.name,
                "stem": p.stem,
                "mtime": p.stat().st_mtime,
                "book_id": bid,
                "slug": slug,
                "seed": seed,
                "run": run,
                "version": run,
                "version_label": _version_label(run),
            }
        )
    return thumbs


@app.get("/api/runs")
def get_runs() -> dict[str, Any]:
    s = _settings()
    current = s.get("current_book") or "default"
    d = book_dir(s)
    data = load_book(s, current, create=False)
    renamed = normalize_plate_filenames(d, current)
    if _patch_run_output_paths(data, renamed):
        save_book(s, data)
    thumbs = _thumbs_for_book(s, current)
    batches = _group_by_version(thumbs)
    ordered = sorted(thumbs, key=_slug_sort_key)
    names = [c.get("name") for c in (data.get("characters") or []) if c.get("name")]
    book_block = {
        "id": current,
        "title": data.get("title") or current,
        "current": True,
        "mtime": max((t.get("mtime") or 0) for t in thumbs) if thumbs else 0,
        "n": len(ordered),
        "names": names,
        "thumbs": ordered,
        "batches": batches,
    }
    with _q_lock:
        depth = len(_job_q)
    ok, msg = _client(s).ping()
    return {
        "runs": data.get("runs") or [],
        "thumbs": ordered,
        "batches": batches,
        "books": [book_block],
        "current": current,
        "queue_depth": depth,
        "comfy": {"ok": ok, "message": msg},
        "dir": str(d),
    }


@app.post("/api/letter")
def post_letter(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    d = book_dir(s)
    parsed = _parse(book, s)
    by_slug = {p.slug: p for p in parsed.plates}
    only = body.get("slug")
    n = 0
    skipped = 0
    plates = d / "plates"
    if not plates.exists():
        raise HTTPException(400, "no plates folder")
    for img in sorted(plates.iterdir()):
        if img.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        file_slugs = _slugs_in_name(img.name)
        matched = [
            p
            for fs in file_slugs
            for slug, p in by_slug.items()
            if same_slug(slug, fs)
        ]
        if not matched:
            skipped += 1
            continue
        only_slugs = _slugs_in_name(only) if only else []
        if only and not any(
            same_slug(p.slug, o) or same_slug(p.slug, only)
            for p in matched
            for o in (only_slugs or [only])
        ):
            continue
        caption = "\n\n".join(p.caption.strip() for p in matched if p.caption.strip())
        if not caption:
            skipped += 1
            continue
        out = d / "lettered" / f"{img.stem}_lettered.png"
        attach(img, caption, out)
        n += 1
    return {"lettered": n, "skipped": skipped, "dir": str(d / "lettered")}


@app.post("/api/export")
def post_export() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    d = book_dir(s)
    exp = d / "export"
    if exp.exists():
        shutil.rmtree(exp)
    exp.mkdir()
    caps = exp / "captions"
    caps.mkdir()
    lettered = d / "lettered"
    n = 0
    if lettered.exists():
        for p in lettered.glob("*_lettered.png"):
            shutil.copy2(p, exp / p.name)
            n += 1
    parsed = _parse(book, s)
    lines = []
    for p in parsed.plates:
        if p.caption.strip():
            (caps / f"{p.slug}.txt").write_text(p.caption + "\n", encoding="utf-8")
        lines.append(f"{p.slug}\n{p.assembled}\n")
    (exp / "assembled_prompts.txt").write_text("\n".join(lines), encoding="utf-8")
    seeds = load_seeds(s)
    (exp / "seeds.json").write_text(json.dumps(seeds, indent=2) + "\n", encoding="utf-8")
    return {"dir": str(exp), "lettered": n}


def _contained(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


@app.get("/api/books")
def get_books() -> dict[str, Any]:
    s = _settings()
    return {"books": list_books(s), "current": s.get("current_book") or "default"}


@app.post("/api/book/new")
def post_book_new(body: dict[str, Any] | None = None) -> dict[str, Any]:
    s = _settings()
    body = body or {}
    title = (body.get("title") or "Untitled").strip() or "Untitled"
    raw = body.get("id") or title.lower().replace(" ", "_")
    try:
        bid = safe_book_id(raw)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    existing = {b["id"] for b in list_books(s)}
    base = bid
    n = 2
    while bid in existing:
        bid = f"{base}_{n}"
        n += 1
    s["current_book"] = bid
    save_settings(s)
    book = empty_book(bid)
    book["title"] = title
    save_book(s, book)
    return {"book": _book_payload(s, book), "books": list_books(s), "dir": str(book_dir(s))}


@app.post("/api/book/open")
def post_book_open(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    try:
        bid = safe_book_id(body.get("id") or "")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    ids = {b["id"] for b in list_books(s)}
    if bid not in ids:
        raise HTTPException(404, f"no book {bid}")
    s["current_book"] = bid
    save_settings(s)
    book = load_book(s)
    return {"book": _book_payload(s, book), "books": list_books(s), "dir": str(book_dir(s))}


@app.post("/api/book/delete")
def post_book_delete(body: dict[str, Any]) -> dict[str, Any]:
    if not body.get("confirm"):
        raise HTTPException(400, "confirm required")
    s = _settings()
    try:
        bid = safe_book_id(body.get("id") or "")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if is_protected_book(bid):
        raise HTTPException(400, "the default book cannot be deleted")
    try:
        delete_book_dir(s, bid)
    except FileNotFoundError:
        raise HTTPException(404, f"no book {bid}") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    remaining = list_books(s)
    if s.get("current_book") == bid:
        nxt = remaining[0]["id"] if remaining else "default"
        s["current_book"] = nxt
        save_settings(s)
        if not remaining:
            book = empty_book("default")
            save_book(s, book)
    return {"books": list_books(s), "current": s.get("current_book"), "book": _book_payload(s, load_book(s))}


@app.post("/api/plates/delete")
def post_plates_delete(body: dict[str, Any]) -> dict[str, Any]:
    if not body.get("confirm"):
        raise HTTPException(400, "confirm required")
    s = _settings()
    bid = body.get("book_id")
    if bid:
        try:
            bid = safe_book_id(str(bid))
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        d = Path(s["output_root"]) / bid
        if not d.is_dir():
            raise HTTPException(404, f"no book {bid}")
    else:
        d = book_dir(s)
        bid = d.name
    plates = d / "plates"
    lettered = d / "lettered"
    scope = body.get("scope") or "all"
    batches = _group_by_version(
        [
            {
                "path": str(p),
                "name": p.name,
                "stem": p.stem,
                "mtime": p.stat().st_mtime,
                "url": "",
                "book_id": bid,
                "run": _run_from_stem(p.stem, bid),
                "slug": _plate_slug(p.name),
            }
            for p in iter_image_files(plates)
        ]
    )
    targets: list[Path] = []
    if scope == "all":
        targets = list(iter_image_files(plates))
        targets.extend(iter_image_files(lettered))
    elif scope == "lettered":
        targets = list(iter_image_files(lettered))
    elif scope == "earlier":
        for b in batches[1:]:
            for t in b.get("thumbs") or []:
                targets.append(Path(t["path"]))
    elif scope == "batch":
        bid = body.get("batch_id")
        for b in batches:
            if b.get("id") == bid:
                for t in b.get("thumbs") or []:
                    targets.append(Path(t["path"]))
                break
        else:
            raise HTTPException(400, "batch not found")
    elif scope == "files":
        for raw in body.get("paths") or []:
            targets.append(Path(raw))
    else:
        raise HTTPException(400, f"bad scope {scope}")
    n = 0
    stems: set[str] = set()
    for p in targets:
        if not _contained(d, p):
            continue
        if not p.exists() or not p.is_file():
            continue
        stems.add(p.stem)
        p.unlink()
        n += 1
        sib = lettered / f"{p.stem}_lettered.png"
        if sib.exists():
            sib.unlink()
            n += 1
    book = load_book(s, bid)
    book["id"] = bid
    if scope == "all":
        book["runs"] = []
    else:
        keep = []
        for run in book.get("runs") or []:
            key = f"{run.get('plate_slug')}_{run.get('seed')}"
            if any(key in st or st.endswith(key) for st in stems):
                continue
            keep.append(run)
        book["runs"] = keep
    save_book(s, book)
    return {"deleted": n, "dir": str(d)}


@app.post("/api/open-folder")
def post_open_folder(body: dict[str, Any] | None = None) -> dict[str, Any]:
    s = _settings()
    d = book_dir(s)
    which = (body or {}).get("which") or "book"
    target = {"plates": d / "plates", "lettered": d / "lettered", "export": d / "export"}.get(which, d)
    target.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        return {"ok": False, "dir": str(target), "error": str(e)}
    return {"ok": True, "dir": str(target)}


@app.post("/api/lock-seed")
def post_lock_seed(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    name = body.get("character")
    seed = body.get("seed")
    clear = bool(body.get("clear"))
    if not name:
        raise HTTPException(400, "character required")
    for c in book.get("characters") or []:
        if c.get("name") == name:
            c["locked_seed"] = None if clear else int(seed)
            break
    else:
        raise HTTPException(400, f"no character {name}")
    save_book(s, book)
    seeds = load_seeds(s)
    seeds.setdefault("characters", {})
    if clear:
        seeds["characters"].pop(name, None)
    else:
        seeds["characters"][name] = int(seed)
    write_seeds(s, seeds)
    return {"book": book}


@app.post("/api/use-as-ref")
def post_use_as_ref(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    name = body.get("character")
    path = body.get("path")
    if not name or not path:
        raise HTTPException(400, "character and path required")
    fp = Path(path)
    if not fp.exists():
        raise HTTPException(400, f"missing file {path}")
    for c in book.get("characters") or []:
        if c.get("name") == name:
            c["ref_images"] = [str(fp)]
            c["ref_active"] = str(fp)
            break
    else:
        raise HTTPException(400, f"no character {name}")
    save_book(s, book)
    return {"book": book}


def _book_payload(s: dict[str, Any], book: dict[str, Any]) -> dict[str, Any]:
    book = dict(book)
    book["characters"] = [_enrich_character_refs(s, book, dict(c)) for c in (book.get("characters") or [])]
    return book


def _find_char(book: dict[str, Any], cid: str | None = None, name: str | None = None) -> dict[str, Any] | None:
    chars = book.get("characters") or []
    if cid:
        for c in chars:
            if c.get("id") == cid:
                return c
    if name:
        for c in chars:
            if c.get("name") == name:
                return c
    return None


@app.post("/api/character/add")
def post_add_character() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    chars = list(book.get("characters") or [])
    chars.append(
        {
            "id": new_id(),
            "name": _next_token(chars),
            "lock_text": "",
            "ref_images": [],
            "ref_active": None,
            "ref_ignored": [],
            "locked_seed": None,
            "notes": "",
        }
    )
    book["characters"] = chars
    save_book(s, book)
    return {"book": _book_payload(s, book)}


@app.post("/api/character/delete")
def post_delete_character(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    cid = str(body.get("id") or "").strip()
    name = str(body.get("name") or "").strip()
    if cid in {"undefined", "null", "None"}:
        cid = ""
    if not cid and not name:
        raise HTTPException(400, "id required")
    chars = list(book.get("characters") or [])
    keep = chars
    if cid:
        keep = [c for c in chars if str(c.get("id") or "") != cid]
    if len(keep) == len(chars) and name:
        keep = []
        dropped = False
        for c in chars:
            if not dropped and c.get("name") == name:
                dropped = True
                continue
            keep.append(c)
    if len(keep) == len(chars):
        raise HTTPException(400, "character not found")
    book["characters"] = keep
    save_book(s, book)
    return {"book": _book_payload(s, book)}


@app.post("/api/activate-ref")
def post_activate_ref(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    name = body.get("character")
    path = body.get("path")
    cid = body.get("id")
    if not path or not (name or cid):
        raise HTTPException(400, "character and path required")
    fp = str(Path(path).resolve())
    c = _find_char(book, cid=cid, name=name)
    if not c:
        raise HTTPException(400, f"no character {cid or name}")
    refs = list(c.get("ref_images") or [])
    if fp not in refs:
        refs.append(fp)
    ignored = [p for p in (c.get("ref_ignored") or []) if str(Path(p).resolve()) != fp]
    c["ref_images"] = refs
    c["ref_ignored"] = ignored
    c["ref_active"] = fp
    save_book(s, book)
    return {"book": _book_payload(s, book)}


@app.post("/api/remove-ref")
def post_remove_ref(body: dict[str, Any]) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    name = body.get("character")
    path = body.get("path")
    cid = body.get("id")
    if not (name or cid):
        raise HTTPException(400, "character required")
    c = _find_char(book, cid=cid, name=name)
    if not c:
        raise HTTPException(400, f"no character {cid or name}")
    refs = list(c.get("ref_images") or [])
    ignored = list(c.get("ref_ignored") or [])
    if path:
        target = str(Path(path).resolve())
        c["ref_images"] = [p for p in refs if str(Path(p).resolve()) != target]
        if target not in ignored:
            ignored.append(target)
        c["ref_ignored"] = ignored
        if c.get("ref_active") and str(Path(c["ref_active"]).resolve()) == target:
            c["ref_active"] = c["ref_images"][-1] if c["ref_images"] else None
    else:
        c["ref_images"] = []
        c["ref_active"] = None
        c["ref_ignored"] = ignored + refs
    save_book(s, book)
    return {"book": _book_payload(s, book)}


@app.post("/api/upload-ref")
async def post_upload_ref(
    character: str = Form(...),
    file: UploadFile = File(...),
    add: str = Form("0"),
    character_id: str = Form(""),
) -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    d = book_dir(s)
    c = _find_char(book, cid=character_id or None, name=character)
    if not c:
        raise HTTPException(400, f"no character {character_id or character}")
    dest_dir = _char_ref_dir(s, book, c)
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = Path(file.filename or "ref.png").name
    dest = dest_dir / fname
    dest.write_bytes(await file.read())
    dest_s = str(dest.resolve())
    ignored = [p for p in (c.get("ref_ignored") or []) if str(Path(p).resolve()) != dest_s]
    others: list[str] = []
    for folder in _char_ref_dirs(s, book, c):
        others.extend(_scan_ref_files(folder))
    if add in ("1", "true", "on"):
        refs = list(c.get("ref_images") or [])
        if dest_s not in refs:
            refs.append(dest_s)
        c["ref_images"] = refs[:3]
    else:
        for p in others:
            if p != dest_s and p not in ignored:
                ignored.append(p)
        c["ref_images"] = [dest_s]
    c["ref_ignored"] = ignored
    c["ref_active"] = dest_s
    save_book(s, book)
    return {"path": str(dest), "book": _book_payload(s, book)}


@app.post("/api/demo/cast")
def demo_cast() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    book["characters"] = json.loads(json.dumps(DEMO_CAST))
    save_book(s, book)
    return {"book": book}


@app.post("/api/demo/bos")
def demo_bos() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    book["title"] = "Bos Sidereal"
    book["characters"] = json.loads(json.dumps(DEMO_CAST))
    book["prompts_raw"] = BOS_PROMPTS
    book["captions_raw"] = BOS_CAPTIONS
    save_book(s, book)
    return post_parse()


@app.post("/api/demo/t1")
def demo_t1() -> dict[str, Any]:
    s = _settings()
    book = load_book(s)
    book["title"] = "t1 smoke"
    if not book.get("characters"):
        book["characters"] = json.loads(json.dumps(DEMO_CAST))
    book["prompts_raw"] = T1_PROMPTS
    book["captions_raw"] = T1_CAPTIONS
    save_book(s, book)
    return post_parse()


@app.get("/api/llm-sheet")
def llm_sheet() -> dict[str, str]:
    s = _settings()
    book = load_book(s)
    locks = ["CHARACTER LOCKS"]
    for c in book.get("characters") or []:
        locks.append(f"{c.get('name')}: {c.get('lock_text')}")
    text = LLM_SHEET.rstrip() + "\n\n" + "\n".join(locks) + "\n"
    return {"text": text}


@app.get("/media/{path:path}")
def media(path: str) -> FileResponse:
    s = _settings()
    root = Path(s["output_root"]).resolve()
    fp = (root / path).resolve()
    if root not in fp.parents and fp != root:
        raise HTTPException(403, "bad path")
    if not fp.is_file():
        raise HTTPException(404, "missing")
    return FileResponse(fp)


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def main() -> None:
    import uvicorn

    s = _settings()
    host = "127.0.0.1"
    port = int(s.get("app_port") or 7860)
    print(f"Plate Press  http://{host}:{port}")
    print("ComfyUI must already run. This app does not fetch the Turbo file.")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
