"""settings.json + books/<id>/ persistence."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

from .defaults import (
    CLOSER_SPLIT,
    LAYOUT_ONE,
    LAYOUT_SPLIT,
    LORA,
    LORA_STRENGTH,
    NEG,
    PER_PROMPT,
    REF_CUTOUT,
    STYLE,
    neg_for,
)

_LAYOUT_HEAD = re.compile(
    r"^\s*Single (?:un)?divided plate[^.]*\.\s*",
    re.I,
)


def migrate_layout(s: dict[str, Any]) -> dict[str, Any]:
    """Lift a layout sentence out of TAIL; keep ink/closer/neg in sync."""
    tail = s.get("tail") or ""
    m = _LAYOUT_HEAD.match(tail)
    if m:
        head = m.group(0).lower()
        if "undivided" in head:
            s["layout"] = "one"
        elif "divided" in head or "two scene" in head:
            s["layout"] = "split"
        rest = tail[m.end() :].lstrip()
        s["tail"] = (" " + rest) if rest else ""
        s["layout_text"] = LAYOUT_SPLIT if s.get("layout") == "split" else LAYOUT_ONE
    if s.get("layout") not in ("one", "split"):
        s["layout"] = "one"
    if not s.get("layout_text"):
        s["layout_text"] = LAYOUT_SPLIT if s["layout"] == "split" else LAYOUT_ONE
    if s["layout"] == "split" and "two panels" in (s.get("neg") or ""):
        s["neg"] = neg_for("split")
    tail_now = s.get("tail") or ""
    if "same place, same hour" in tail_now.lower():
        s["tail"] = CLOSER_SPLIT
    return s

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PKG / "settings.json"
DEMO_BOOK_ID = "default"
DEMO_SEED = PKG / "demo" / "bos"
_PATH_KEYS = ("workflow_text", "workflow_ref", "output_root")


def is_protected_book(book_id: str) -> bool:
    return (book_id or "") == DEMO_BOOK_ID


def resolve_user_path(value: str) -> Path:
    """Relative to the repo root; ~ expands. Absolute paths stay as-is."""
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    return p.resolve()


def portable_path(value: str | Path) -> str:
    """Repo-relative if possible, else ~/..., else absolute."""
    p = Path(value).expanduser()
    if not p.is_absolute():
        return Path(value).as_posix()
    p = p.resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        pass
    try:
        return "~/" + p.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(p)


def default_settings() -> dict[str, Any]:
    return {
        "host": "127.0.0.1",
        "port": 8188,
        "app_port": 7860,
        "workflow_text": "Krea2T_V3_ref_clean01-API.json",
        "workflow_ref": "Krea2T_V3_ref_clean01-API.json",
        "lora_name": LORA,
        "lora_strength": LORA_STRENGTH,
        "style": STYLE,
        "layout": "one",
        "layout_text": LAYOUT_ONE,
        "tail": "",
        "neg": NEG,
        "images_per_plate": PER_PROMPT,
        "output_root": "platepress/books",
        "current_book": "default",
        "steps": 8,
        "cfg": 1,
        "sampler_name": "euler",
        "scheduler": "beta",
        "job_timeout_s": 600,
        "send_refs": False,
        "ref_cutout": False,
        "ref_cutout_text": REF_CUTOUT,
    }


def load_settings(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_SETTINGS_PATH
    base = default_settings()
    if path.exists():
        try:
            base.update(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    s = migrate_layout(base)
    if not str(s.get("ref_cutout_text") or "").strip():
        s["ref_cutout_text"] = REF_CUTOUT
    for key in _PATH_KEYS:
        if s.get(key):
            s[key] = str(resolve_user_path(str(s[key])))
    ensure_demo_book(s)
    return s


def save_settings(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = default_settings()
    merged.update(data)
    for key in _PATH_KEYS:
        if merged.get(key):
            merged[key] = portable_path(merged[key])
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def output_root(settings: dict[str, Any]) -> Path:
    return resolve_user_path(str(settings.get("output_root") or "platepress/books"))


def book_dir(settings: dict[str, Any], book_id: str | None = None, create: bool = True) -> Path:
    bid = book_id or settings.get("current_book") or "default"
    d = output_root(settings) / bid
    if create:
        d.mkdir(parents=True, exist_ok=True)
        (d / "plates").mkdir(exist_ok=True)
        (d / "lettered").mkdir(exist_ok=True)
        (d / "refs").mkdir(exist_ok=True)
        (d / "export").mkdir(exist_ok=True)
    return d


def empty_book(book_id: str = "default") -> dict[str, Any]:
    return {
        "id": book_id,
        "title": "Untitled",
        "style": None,
        "tail": None,
        "workflow": None,
        "characters": [],
        "plates": [],
        "prompts_raw": "",
        "captions_raw": "",
        "runs": [],
    }


def load_book(settings: dict[str, Any], book_id: str | None = None, create: bool = True) -> dict[str, Any]:
    d = book_dir(settings, book_id, create=create)
    path = d / "book.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            chars_path = d / "characters.json"
            if chars_path.exists():
                data["characters"] = json.loads(chars_path.read_text(encoding="utf-8"))
            return data
        except json.JSONDecodeError:
            pass
    return empty_book(d.name)


def _book_rel(book_root: Path, value: str) -> str:
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        return Path(str(value)).as_posix()
    try:
        return p.resolve().relative_to(book_root.resolve()).as_posix()
    except ValueError:
        return portable_path(p)


def ensure_demo_book(settings: dict[str, Any]) -> None:
    """Copy shipped Bos demo into books/default if that folder is missing."""
    dest = output_root(settings) / DEMO_BOOK_ID
    if (dest / "book.json").exists() or (dest / "prompts_raw.txt").exists():
        return
    if not DEMO_SEED.is_dir():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(DEMO_SEED, dest, dirs_exist_ok=True)


def save_book(settings: dict[str, Any], book: dict[str, Any]) -> Path:
    d = book_dir(settings, book.get("id"))
    chars = book.get("characters") or []
    for c in chars:
        c["ref_images"] = [_book_rel(d, p) for p in (c.get("ref_images") or []) if p]
        if c.get("ref_active"):
            c["ref_active"] = _book_rel(d, c["ref_active"])
    (d / "characters.json").write_text(json.dumps(chars, indent=2) + "\n", encoding="utf-8")
    (d / "prompts_raw.txt").write_text(book.get("prompts_raw") or "", encoding="utf-8")
    (d / "captions_raw.txt").write_text(book.get("captions_raw") or "", encoding="utf-8")
    (d / "book.json").write_text(json.dumps(book, indent=2) + "\n", encoding="utf-8")
    return d


def append_run(settings: dict[str, Any], run: dict[str, Any], book_id: str | None = None) -> None:
    d = book_dir(settings, book_id)
    with (d / "run_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(run) + "\n")
    book = load_book(settings, book_id)
    runs = book.setdefault("runs", [])
    runs.append(run)
    save_book(settings, book)


def write_seeds(settings: dict[str, Any], seeds: dict[str, Any], book_id: str | None = None) -> None:
    d = book_dir(settings, book_id)
    (d / "seeds.json").write_text(json.dumps(seeds, indent=2) + "\n", encoding="utf-8")


def load_seeds(settings: dict[str, Any], book_id: str | None = None) -> dict[str, Any]:
    p = book_dir(settings, book_id) / "seeds.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"characters": {}, "plates": {}}


def new_id(prefix: str = "c") -> str:
    return prefix + uuid.uuid4().hex[:8]


def safe_book_id(raw: str) -> str:
    bid = "".join(ch for ch in (raw or "") if ch.isalnum() or ch in "_-")
    if not bid:
        raise ValueError("bad book id")
    return bid


def list_books(settings: dict[str, Any]) -> list[dict[str, Any]]:
    root = output_root(settings)
    if not root.exists():
        return []
    current = settings.get("current_book") or "default"
    out: list[dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        title = d.name
        n = 0
        try:
            bj = d / "book.json"
            if bj.is_file():
                title = json.loads(bj.read_text(encoding="utf-8")).get("title") or d.name
            plates = d / "plates"
            if plates.is_dir():
                n = sum(
                    1
                    for p in plates.iterdir()
                    if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
                )
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, TypeError, AttributeError):
            title = d.name
        out.append({
            "id": d.name,
            "title": title,
            "n_plates": n,
            "current": d.name == current,
            "protected": is_protected_book(d.name),
        })
    return out


def delete_book_dir(settings: dict[str, Any], book_id: str) -> None:
    import shutil

    bid = safe_book_id(book_id)
    if is_protected_book(bid):
        raise ValueError("the default book cannot be deleted")
    root = output_root(settings).resolve()
    d = (root / bid).resolve()
    if root not in d.parents:
        raise ValueError("bad book path")
    if not d.is_dir():
        raise FileNotFoundError(bid)
    shutil.rmtree(d)


def iter_image_files(folder: Path):
    if not folder.exists():
        return
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            yield p
