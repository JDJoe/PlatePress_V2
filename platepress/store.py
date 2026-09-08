"""settings.json + books/<id>/ persistence."""

from __future__ import annotations

import json
import os
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
    LORA_SLOTS,
    LORA_STRENGTH,
    NEG,
    PER_PROMPT,
    REF_CUTOUT,
    STYLE,
    UNET,
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


def normalize_loras(s: dict[str, Any]) -> list[dict[str, Any]]:
    """Up to four rgthree stack slots. Empty name is dropped."""
    out: list[dict[str, Any]] = []
    raw = s.get("loras")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name or name.lower() == "none":
                continue
            try:
                strength = float(item.get("strength") if item.get("strength") is not None else LORA_STRENGTH)
            except (TypeError, ValueError):
                strength = float(LORA_STRENGTH)
            out.append({"name": name, "strength": strength})
            if len(out) >= LORA_SLOTS:
                break
        return out
    name = str(s.get("lora_name") or "").strip()
    if name and name.lower() != "none":
        try:
            strength = float(s.get("lora_strength") if s.get("lora_strength") is not None else LORA_STRENGTH)
        except (TypeError, ValueError):
            strength = float(LORA_STRENGTH)
        return [{"name": name, "strength": strength}]
    return []


def migrate_loras(s: dict[str, Any]) -> dict[str, Any]:
    slots = normalize_loras(s)
    s["loras"] = slots
    if slots:
        s["lora_name"] = slots[0]["name"]
        s["lora_strength"] = slots[0]["strength"]
    else:
        s["lora_name"] = ""
        s["lora_strength"] = LORA_STRENGTH
    if not str(s.get("unet_name") or "").strip():
        s["unet_name"] = UNET
    s.setdefault("models_dir", "")
    s.setdefault("loras_dir", "")
    return s


_MODEL_ROOT_NAMES = {
    "diffusion_models",
    "unet",
    "unets",
    "loras",
    "checkpoints",
    "clip",
    "vae",
    "text_encoders",
    "models",
}


def _combo_name(root: Path, parent: Path, filename: str) -> str:
    """Keep the listed directory name, add the listed filename. Never resolve."""
    try:
        rel_parent = parent.relative_to(root)
    except ValueError:
        rel_parent = Path(".")
    if rel_parent == Path("."):
        if root.name.lower() in _MODEL_ROOT_NAMES:
            return filename
        return f"{root.name}/{filename}"
    return f"{rel_parent.as_posix()}/{filename}"


def list_weights(folder: str | Path, *, limit: int = 400) -> list[str]:
    """Comfy combo names: listed folder name + listed file name. Softlinks keep those names."""
    root = resolve_user_path(str(folder), follow_symlinks=False)
    if not root.is_dir():
        raise ValueError(f"not a folder: {root}")
    found: list[str] = []
    seen_real: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
        try:
            real = os.path.realpath(dirpath)
        except OSError:
            dirnames[:] = []
            continue
        if real in seen_real:
            dirnames[:] = []
            continue
        seen_real.add(real)
        parent = Path(dirpath)
        for name in filenames:
            if name.startswith(".") or Path(name).suffix.lower() not in WEIGHT_SUFFIXES:
                continue
            found.append(_combo_name(root, parent, name))
            if len(found) >= limit:
                return sorted(found, key=str.lower)
    return sorted(found, key=str.lower)


def match_combo_name(wanted: str, available: list[str]) -> str | None:
    """Exact Comfy combo name, or a unique basename (KREA2/file.safetensors)."""
    wanted = (wanted or "").strip()
    if not wanted:
        return None
    names = [str(n) for n in available if n and str(n).lower() != "none"]
    if wanted in names:
        return wanted
    low = wanted.lower()
    hits = [n for n in names if n.lower() == low]
    if len(hits) == 1:
        return hits[0]
    base = Path(wanted).name
    hits = [n for n in names if Path(n).name == base]
    if len(hits) == 1:
        return hits[0]
    hits = [n for n in names if Path(n).name.lower() == base.lower()]
    if len(hits) == 1:
        return hits[0]
    return None

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
DEFAULT_SETTINGS_PATH = PKG / "settings.json"
DEMO_BOOK_ID = "default"
DEMO_SEED = PKG / "demo" / "bos"
DEFAULT_API_WORKFLOW = "Krea2T_V3_ref_clean03-API.json"
_LEGACY_API_WORKFLOWS = {
    "Krea2T_V3_ref_clean01-API.json",
}
_PATH_KEYS = ("workflow_text", "workflow_ref", "output_root", "models_dir", "loras_dir")
_SYMLINK_PATH_KEYS = ("models_dir", "loras_dir")
WEIGHT_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".sft", ".gguf"}


def is_protected_book(book_id: str) -> bool:
    return (book_id or "") == DEMO_BOOK_ID


def resolve_user_path(value: str, *, follow_symlinks: bool = True) -> Path:
    """Relative to the repo root; ~ expands. Absolute paths stay as-is."""
    p = Path(str(value)).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    return p.resolve() if follow_symlinks else p.absolute()


def portable_path(value: str | Path, *, follow_symlinks: bool = True) -> str:
    """Repo-relative if possible, else ~/..., else absolute."""
    p = Path(value).expanduser()
    if not p.is_absolute():
        return Path(value).as_posix()
    p = p.resolve() if follow_symlinks else p.absolute()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        pass
    try:
        home = Path.home() if follow_symlinks else Path.home().absolute()
        return "~/" + p.relative_to(home).as_posix()
    except ValueError:
        return str(p)


def migrate_default_workflow(s: dict[str, Any]) -> dict[str, Any]:
    """If Settings still names the previous factory API graph, use the current one."""
    for key in ("workflow_text", "workflow_ref"):
        raw = str(s.get(key) or "").strip()
        if raw and Path(raw).name in _LEGACY_API_WORKFLOWS:
            s[key] = DEFAULT_API_WORKFLOW
    return s


def default_settings() -> dict[str, Any]:
    return {
        "host": "127.0.0.1",
        "port": 8188,
        "app_port": 7860,
        "workflow_text": DEFAULT_API_WORKFLOW,
        "workflow_ref": DEFAULT_API_WORKFLOW,
        "unet_name": UNET,
        "models_dir": "",
        "loras_dir": "",
        "lora_name": LORA,
        "lora_strength": LORA_STRENGTH,
        "loras": [{"name": LORA, "strength": LORA_STRENGTH}],
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
    s = migrate_loras(migrate_layout(migrate_default_workflow(base)))
    if not str(s.get("ref_cutout_text") or "").strip():
        s["ref_cutout_text"] = REF_CUTOUT
    for key in _PATH_KEYS:
        if s.get(key):
            s[key] = str(
                resolve_user_path(str(s[key]), follow_symlinks=key not in _SYMLINK_PATH_KEYS)
            )
    ensure_demo_book(s)
    return s


def save_settings(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or DEFAULT_SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = default_settings()
    merged.update(data)
    merged = migrate_loras(migrate_default_workflow(merged))
    for key in _PATH_KEYS:
        if merged.get(key):
            merged[key] = portable_path(
                merged[key], follow_symlinks=key not in _SYMLINK_PATH_KEYS
            )
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
        (d / "workflows").mkdir(exist_ok=True)
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


def is_api_workflow(path: Path) -> bool:
    """True for Comfy API JSON (class_type nodes). UI graphs have nodes+links."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict) or not data:
        return False
    if "nodes" in data and "links" in data:
        return False
    return any(isinstance(v, dict) and v.get("class_type") for v in data.values())


def list_api_workflows(settings: dict[str, Any], book_id: str | None = None) -> list[dict[str, str]]:
    """API graphs: Settings default, repo *-API.json, platepress/workflows/, this book."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []

    def add(path: Path, source: str) -> None:
        if not path.is_file() or not is_api_workflow(path):
            return
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            return
        seen.add(key)
        out.append({
            "path": portable_path(path, follow_symlinks=False),
            "name": path.name,
            "source": source,
        })

    for key in ("workflow_text", "workflow_ref"):
        raw = str(settings.get(key) or "").strip()
        if raw:
            add(resolve_user_path(raw), "settings")
    for p in sorted(ROOT.glob("*-API.json")):
        add(p, "shared")
    shared = PKG / "workflows"
    if shared.is_dir():
        for p in sorted(shared.glob("*.json")):
            add(p, "shared")
    bid = book_id or settings.get("current_book")
    if bid:
        bw = output_root(settings) / bid / "workflows"
        if bw.is_dir():
            for p in sorted(bw.glob("*.json")):
                add(p, "book")
    return out


def job_workflows(settings: dict[str, Any], book: dict[str, Any]) -> tuple[Path, Path]:
    """Book API graph overrides Settings for both text and stills."""
    raw = str(book.get("workflow") or "").strip()
    if raw:
        p = resolve_user_path(raw)
        return p, p
    text_wf = resolve_user_path(str(settings.get("workflow_text") or ""))
    ref_raw = str(settings.get("workflow_ref") or "").strip()
    ref_wf = resolve_user_path(ref_raw) if ref_raw else Path()
    return text_wf, ref_wf


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
