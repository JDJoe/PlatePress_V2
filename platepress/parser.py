"""Story wall + caption wall → plates. Ink, layout, closer, lock-if-no-still, Book wall."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .defaults import LAYOUT_ONE, LAYOUT_SPLIT, METAPHORS, REF_CUTOUT, STYLE

# Preferred: p1_cargo / t1_one. Also any identifier that is not a known character.
_SLUG_PREF = re.compile(r"^p\d+_[A-Za-z0-9_]+$")
_SLUG_ANY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SLUG_NUM = re.compile(r"^([pt])(\d+)_(.+)$", re.I)
_QUOTED = re.compile(r'^"([^"]+)"\s*(.*)$')
_BRACE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
SLUG_PAD = 3
# Krea still hears "ship" inside spaceship/starship and paints sails.
_VESSEL = re.compile(r"\b(?:star|space)?ships?\b", re.I)
# Qwen still slots are image1..image3. "picture1" does not bind the LoadImage.
_INLINE_PANES = re.compile(
    r"left\s*pane\s*[:,]?\s*(.*?)\s*right\s*pane\s*[:,]?\s*(.*)",
    re.I | re.S,
)
# CHARACTER1 / PILOT1 → Cast slot 1. The name after "is" is writer text, not a lookup.
_CHAR_TOKEN = re.compile(r"(?i)\b(?:CHARACTER|PILOT)(\d+)\b")
_SLOT_LOCK_LINE = re.compile(r"(?i)^(?:CHARACTER|PILOT)\d+\s+is\b")
_NO_LETTER_LAYOUT = re.compile(
    r",?\s*no (?:text|captions|speech balloons|letters)\b",
    re.I,
)
_NO_TEXT_TAIL = re.compile(r"No text\.\s*", re.I)

# Caption-wall tags → balloon / box instructions. Codes must not parse as slugs.
LETTER_SHAPES: dict[str, str] = {
    "NS": "a normal oval speech balloon with a tail, white fill, thin black ink outline",
    "NSV": "a tall oval speech balloon with a tail, letters stacked or set vertically, white fill, thin black ink outline",
    "NS2": "two connected oval speech balloons sharing one tail, white fill, thin black ink outline",
    "OFFP": "a round speech balloon whose tail points off the panel edge, off-panel speaker, white fill, thin black ink outline",
    "YELL": "a spiky burst speech balloon, shouting, white fill, thin black ink outline, bold letters",
    "FADE": "a wobbly fading speech balloon, weak voice, white fill, thin black ink outline",
    "WHISP": "an oval speech balloon with a dashed outline, whispering, small letters",
    "ANN": "a jagged starburst announcement balloon, thin black ink outline",
    "THINK": "a smooth oval thought balloon with small circles instead of a tail",
    "DREAM": "a scalloped cloud thought balloon with small circles, daydream",
    "CAP_B": "a rectangular caption box along the bottom edge, cream fill, thin black ink outline",
    "CAP_T": "a rectangular caption box along the top edge, cream fill, thin black ink outline",
    "DARK": "a black-filled oval balloon, white letters, negative emotion",
}
LETTER_ALIASES = {
    "CAP": "CAP_B",
    "WHISPER": "WHISP",
    "YELLING": "YELL",
    "THINKING": "THINK",
}
LETTER_TAG_CODES = frozenset({*LETTER_SHAPES, *LETTER_ALIASES})
_TAG_CODES = sorted(LETTER_TAG_CODES, key=len, reverse=True)
_TAG_LINE = re.compile(
    r"^(" + "|".join(re.escape(c) for c in _TAG_CODES) + r")(?:_([1-6]))?\s*:\s*(.*)$",
    re.I,
)
_TAG_CELL = re.compile(
    r"^(" + "|".join(re.escape(c) for c in _TAG_CODES) + r")_([1-6])$",
    re.I,
)
_SPEAKER_PREFIX = re.compile(
    r"^((?:CHARACTER|PILOT)\d+|[A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+)$",
    re.I,
)
LETTERING_CLOSER = (
    "Hand-lettered readable ink in the balloons and caption boxes on the plate. "
    "Quoted words are exact. Do not garble, misspell, translate, or replace them. "
    "No extra balloons. Do not grow the canvas. No caption bar under the image."
)
LETTER_CELLS = {
    1: "top-left sixth of the plate",
    2: "top-right sixth of the plate",
    3: "middle-left sixth of the plate",
    4: "middle-right sixth of the plate",
    5: "bottom-left sixth of the plate",
    6: "bottom-right sixth of the plate",
}


def pad_slug(slug: str, width: int = SLUG_PAD) -> str:
    """p1_cargo → p001_cargo so p010 sorts after p001, not before p1."""
    m = _SLUG_NUM.match(slug or "")
    if not m:
        return slug
    return f"{m.group(1).lower()}{int(m.group(2)):0{width}d}_{m.group(3)}"


def same_slug(a: str, b: str) -> bool:
    return a == b or pad_slug(a) == pad_slug(b)


def _slug_flag(d: dict[str, bool], slug: str, default: bool) -> bool:
    if slug in d:
        return bool(d[slug])
    for key, val in d.items():
        if same_slug(str(key), slug):
            return bool(val)
    return default


def caption_for(slug: str, caps: dict[str, str]) -> str:
    """p1_dower and p01_dower are the same plate."""
    if slug in caps:
        return caps[slug]
    for key, text in caps.items():
        if same_slug(key, slug):
            return text
    return ""


@dataclass
class Character:
    id: str
    name: str
    lock_text: str
    ref_images: list[str] = field(default_factory=list)
    ref_active: str | None = None
    locked_seed: int | None = None
    notes: str = ""
    ref_cutout: bool = False


@dataclass
class Plate:
    slug: str
    order: int
    scene_text: str
    character_ids: list[str]
    metaphor: str | None
    helmet_on: bool
    caption: str
    risky_twoshot: bool
    assembled: str = ""
    warnings: list[str] = field(default_factory=list)
    pane: str = ""
    pair_with: str = ""
    pane_left: str = ""
    pane_right: str = ""
    pane_left_ids: list[str] = field(default_factory=list)
    pane_right_ids: list[str] = field(default_factory=list)
    named_ids: list[str] | None = None
    use_text: bool = False
    use_image: bool = False
    use_letter: bool = False
    lettering_prompt: str = ""
    caption_bar: str = ""


@dataclass
class ParseResult:
    plates: list[Plate]
    warnings: list[str]


def _is_letter_tag_token(token: str) -> bool:
    t = (token or "").upper()
    if t in LETTER_TAG_CODES:
        return True
    return bool(_TAG_CELL.match(t))


def _looks_like_slug(token: str, character_names: set[str]) -> bool:
    if token in character_names:
        return False
    if _is_letter_tag_token(token):
        return False
    if _SLUG_PREF.match(token) or re.match(r"^t\d+_[A-Za-z0-9_]+$", token):
        return True
    if _SLUG_ANY.match(token) and "_" in token:
        return True
    return False


def _split_slug_line(line: str, character_names: set[str]) -> tuple[str, str] | None:
    raw = line.strip()
    if not raw:
        return None
    m = _QUOTED.match(raw)
    if m:
        token, rest = m.group(1).strip(), m.group(2).strip()
        if token in character_names:
            return None
        if _is_letter_tag_token(token):
            return None
        if _SLUG_ANY.match(token) or _SLUG_PREF.match(token):
            return token, rest
        return None
    parts = raw.split(None, 1)
    token = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    if not _looks_like_slug(token, character_names):
        return None
    return token, rest


def _character_hits(text: str, character_names: list[str]) -> list[str]:
    found: list[str] = []
    for name in character_names:
        if re.search(r"\{" + re.escape(name) + r"\}", text):
            if name not in found:
                found.append(name)
            continue
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", text):
            if name not in found:
                found.append(name)
    return found


def parse_character_decls(body: str, character_names: list[str]) -> list[tuple[int, str]]:
    """CHARACTER1 → first Cast card, CHARACTER2 → second. Writer alias is ignored."""
    slots: dict[int, str] = {}
    for m in _CHAR_TOKEN.finditer(body or ""):
        slot = int(m.group(1))
        idx = slot - 1
        if slot >= 1 and idx < len(character_names):
            slots[slot] = character_names[idx]
    return sorted(slots.items())


def expand_character_decls(body: str, by_name: dict[str, Character]) -> str:
    """Replace CHARACTER1 with that slot's Cast lock. Leave 'is Anna and …' as written."""
    names = list(by_name)
    slots = dict(parse_character_decls(body, names))

    def repl(m: re.Match[str]) -> str:
        name = slots.get(int(m.group(1)))
        if not name:
            return ""
        lock = (by_name[name].lock_text or "").strip().rstrip(".,; ")
        if not lock:
            return m.group(0)
        return lock

    return _CHAR_TOKEN.sub(repl, body or "")


def character_tokens_to_images(body: str) -> str:
    """CHARACTER1 is Anna → image1 is Anna. Text off, still on."""
    return _CHAR_TOKEN.sub(lambda m: f"image{int(m.group(1))}", body or "")


def _strip_character_tokens(text: str, character_names: set[str]) -> str:
    out = text
    for name in sorted(character_names, key=len, reverse=True):
        out = re.sub(r"\{" + re.escape(name) + r"\}", " ", out)
        out = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", " ", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+,", ",", out)
    return out.strip(" ,")


def _strip_style_tail(body: str, style: str, tail: str, warnings: list[str], slug: str) -> str:
    b = body.strip()
    if b.lower().startswith("aethernouveau"):
        warnings.append(f"{slug}: body starts with aethernouveau — stripped duplicate STYLE/TAIL")
        st = style.strip()
        if b.startswith(st):
            b = b[len(st) :].strip(" ,")
        else:
            # Cut through first sentence-ish prefix up to the usual period after STYLE.
            b = re.sub(r"^aethernouveau\.[^.]*\.\s*", "", b, flags=re.I).strip(" ,")
    tail_s = tail.strip()
    if tail_s and b.endswith(tail_s):
        b = b[: -len(tail_s)].rstrip()
        if slug and f"{slug}: body starts" not in " ".join(warnings):
            warnings.append(f"{slug}: stripped duplicate TAIL")
    return b.strip()


def detect_metaphor(scene: str) -> str | None:
    low = scene.lower()
    hits = [m for m in METAPHORS if m in low]
    if not hits:
        return None
    # Prefer the longest match (stained glass vs teal stained glass still counts).
    hits.sort(key=len, reverse=True)
    return hits[0]


def parse_wall(text: str, character_names: list[str]) -> list[tuple[str, str]]:
    """Return (slug, body) in order. Body is raw joined scene lines."""
    names = set(character_names)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    items: list[tuple[str, str]] = []
    current_slug: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current_slug, buf
        if current_slug is None:
            buf = []
            return
        body = "\n".join(buf).strip()
        items.append((current_slug, body))
        current_slug = None
        buf = []

    for line in lines:
        split = _split_slug_line(line, names)
        if split is not None:
            token, rest = split
            flush()
            current_slug = token
            if rest:
                buf.append(rest)
            continue
        if current_slug is None:
            continue
        buf.append(line)
    flush()
    return items


def parse_captions(text: str, character_names: list[str]) -> dict[str, str]:
    """Captions keep newlines. Do not join into one line."""
    names = set(character_names)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    caps: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current is None:
            buf = []
            return
        # Keep internal newlines; strip leading/trailing blank lines only.
        while buf and buf[0].strip() == "":
            buf.pop(0)
        while buf and buf[-1].strip() == "":
            buf.pop()
        caps[current] = "\n".join(buf)
        current = None
        buf = []

    for line in lines:
        split = _split_slug_line(line, names)
        if split is not None:
            token, rest = split
            quoted = bool(_QUOTED.match(line.strip()))
            if quoted or rest == "" or _strip_character_tokens(rest, names) == "":
                flush()
                current = token
                if rest and _strip_character_tokens(rest, names):
                    buf.append(rest)
                continue
            if current is None:
                flush()
                current = token
                if rest:
                    buf.append(rest)
                continue
        if current is None:
            continue
        buf.append(line)
    flush()
    return caps


def _cast_slot_name(token: str, characters: list[Character]) -> str | None:
    raw = (token or "").strip()
    if not raw:
        return None
    m = re.match(r"(?i)^(?:CHARACTER|PILOT)(\d+)$", raw)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(characters):
            return characters[idx].name
        return None
    names = [c.name for c in characters]
    for n in names:
        if n.lower() == raw.lower():
            return n
    return None


def _expand_cast_in_lettering(text: str, characters: list[Character]) -> str:
    def repl(m: re.Match[str]) -> str:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(characters):
            return characters[idx].name
        return m.group(0)

    return _CHAR_TOKEN.sub(repl, text or "")


def _quote_lettering(text: str) -> str:
    return (text or "").replace('"', "'").strip()


def _ns2_parts(text: str) -> tuple[str, str] | None:
    for sep in (" | ", " |", "| ", "|", " // ", "//"):
        if sep in text:
            a, b = text.split(sep, 1)
            if a.strip() and b.strip():
                return a.strip(), b.strip()
    bits = re.split(r"\s*(?:\.{3}|…)\s*", text, maxsplit=1)
    if len(bits) == 2 and bits[0].strip() and bits[1].strip():
        return bits[0].strip().rstrip(".") + "…", "…" + bits[1].strip()
    return None


@dataclass
class LetterBeat:
    tag: str
    text: str
    speaker: str = ""
    part2: str = ""
    slot: int = 0
    cell: int = 0


def parse_caption_lettering(
    caption: str,
    characters: list[Character] | None = None,
) -> tuple[list[LetterBeat], str]:
    """Caption wall → model beats. Untagged narrator lines become a bottom box (CAP_B)."""
    characters = characters or []
    beats: list[LetterBeat] = []
    bar: list[str] = []
    for raw in (caption or "").splitlines():
        line = raw.strip()
        if not line:
            if bar and bar[-1] != "":
                bar.append("")
            continue
        m = _TAG_LINE.match(line)
        if not m:
            bar.append(raw.rstrip())
            continue
        tag = LETTER_ALIASES.get(m.group(1).upper(), m.group(1).upper())
        cell = int(m.group(2)) if m.group(2) else 0
        if tag in {"CAP_B", "CAP_T"}:
            cell = 0
        rest = (m.group(3) or "").strip()
        speaker = ""
        slot = 0
        sm = _SPEAKER_PREFIX.match(rest)
        if sm and tag not in {"CAP_B", "CAP_T"}:
            maybe = _cast_slot_name(sm.group(1), characters)
            if maybe or re.match(r"(?i)^(?:CHARACTER|PILOT)\d+$", sm.group(1) or ""):
                speaker = maybe or sm.group(1)
                rest = (sm.group(2) or "").strip()
                mslot = re.match(r"(?i)^(?:CHARACTER|PILOT)(\d+)$", sm.group(1) or "")
                if mslot:
                    slot = int(mslot.group(1))
                elif maybe:
                    for i, c in enumerate(characters, start=1):
                        if c.name.lower() == maybe.lower():
                            slot = i
                            break
        rest = _expand_cast_in_lettering(rest, characters)
        speaker = _expand_cast_in_lettering(speaker, characters)
        part2 = ""
        if tag == "NS2":
            parts = _ns2_parts(rest)
            if parts:
                rest, part2 = parts
        if not rest:
            continue
        beats.append(
            LetterBeat(tag=tag, text=rest, speaker=speaker, part2=part2, slot=slot, cell=cell)
        )
    while bar and bar[0] == "":
        bar.pop(0)
    while bar and bar[-1] == "":
        bar.pop()
    bar_text = "\n".join(bar)
    if bar_text.strip() and not any(b.tag in {"CAP_B", "CAP_T"} for b in beats):
        joined = " ".join(ln.strip() for ln in bar_text.splitlines() if ln.strip())
        beats.insert(0, LetterBeat(tag="CAP_B", text=joined))
    return beats, bar_text


def render_lettering(beats: list[LetterBeat]) -> str:
    out: list[str] = []
    for b in beats:
        shape = LETTER_SHAPES.get(b.tag) or LETTER_SHAPES["NS"]
        q1 = _quote_lettering(b.text)
        if b.tag == "NS2" and b.part2:
            q2 = _quote_lettering(b.part2)
            clause = (
                f"Draw {shape}. First balloon exactly: \"{q1}\". "
                f"Second balloon exactly: \"{q2}\"."
            )
        else:
            clause = f"Draw {shape}. Hand-lettered ink inside, exactly: \"{q1}\"."
        if b.speaker and b.tag not in {"CAP_B", "CAP_T"}:
            if b.tag == "OFFP":
                clause += f" The voice is {b.speaker}, off-panel."
            else:
                clause += f" The tail points at {b.speaker}."
        if b.cell in LETTER_CELLS and b.tag not in {"CAP_B", "CAP_T"}:
            clause += f" Place it in the {LETTER_CELLS[b.cell]}."
        out.append(clause)
    return " ".join(out)


def layout_allow_lettering(text: str) -> str:
    out = _NO_LETTER_LAYOUT.sub("", text or "")
    return re.sub(r"\s{2,}", " ", out).strip(" ,")


def tail_allow_lettering(text: str) -> str:
    return _NO_TEXT_TAIL.sub("", text or "").strip()


def combine_lettering(left: str, right: str = "") -> str:
    bits: list[str] = []
    if left and right:
        bits.append("Left pane lettering. " + left.strip())
        bits.append("Right pane lettering. " + right.strip())
        return " ".join(bits)
    return (left or right or "").strip()


def _spacecraft(text: str) -> str:
    """ship / spaceship / starship → spacecraft. Does not touch spacesuit."""
    return _VESSEL.sub("spacecraft", text or "")


def _join_scene_clauses(clauses: list[str]) -> str:
    """Join wall chunks as sentences. 'CHARACTER1 is Celine' then 'Celine, …' must not glue."""
    parts = [c.strip() for c in clauses if c and str(c).strip()]
    if not parts:
        return ""
    out = parts[0]
    for nxt in parts[1:]:
        if out[-1] in ",;:":
            out = out.rstrip(",; ") + "."
        elif out[-1] not in ".!?":
            out += "."
        out += " " + nxt
    return out


def _flatten_scene(scene: str) -> str:
    """One line for the API. Blank lines and CHARACTER1 is … stay their own sentences."""
    clauses: list[str] = []
    for para in re.split(r"\n\s*\n", scene or ""):
        chunk: list[str] = []
        for raw in para.splitlines():
            ln = re.sub(r"\s+", " ", raw).strip()
            if not ln:
                continue
            if _SLOT_LOCK_LINE.match(ln):
                if chunk:
                    clauses.append(" ".join(chunk))
                    chunk = []
                clauses.append(ln)
            else:
                chunk.append(ln)
        if chunk:
            clauses.append(" ".join(chunk))
    return _join_scene_clauses(clauses)


def _image_slots(text: str) -> str:
    """picture1 → image1 so Qwen binds the still that was uploaded."""
    return re.sub(r"\bpicture(\d+)\b", r"image\1", text or "", flags=re.I)


def _clause(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    return s.rstrip(".,; ") + "."


def _join_clauses(*parts: str) -> str:
    return " ".join(_clause(p) for p in parts if p and str(p).strip())


def _lock_bits(locks: list[str] | None) -> list[str]:
    return [x.strip() for x in (locks or []) if x and str(x).strip()]


def assemble(
    style: str,
    locks: list[str],
    scene: str,
    tail: str,
    n_pictures: int = 0,
    cutout: bool = False,
    cutout_text: str = "",
    layout: str = "one",
    layout_text: str = "",
    lettering: str = "",
) -> str:
    """Ink + layout + closer + lock-if-no-still + Book wall."""
    style = style.strip()
    scene = _spacecraft(scene.strip().rstrip(".,; "))
    lt = (layout_text or LAYOUT_ONE).strip()
    closer = (tail or "").strip()
    lettering = (lettering or "").strip()
    if lettering:
        lt = layout_allow_lettering(lt)
        closer = tail_allow_lettering(closer)
    bits: list[str] = [style]
    if lt and (layout or "one") != "split":
        bits.append(lt)
    if closer:
        bits.append(closer)
    if not n_pictures:
        bits.extend(_lock_bits(locks))
    if n_pictures and cutout:
        bits.extend(_lock_bits([cutout_text]))
    if scene:
        bits.append(scene)
    core = _join_clauses(*bits)
    if not lettering:
        return core
    return f"{core} {LETTERING_CLOSER} {lettering}".strip()


def extract_inline_panes(scene: str) -> tuple[str, str] | None:
    """If the wall already wrote left pane / right pane, split them."""
    m = _INLINE_PANES.search(scene or "")
    if not m:
        return None
    left, right = m.group(1).strip(), m.group(2).strip()
    if left and right:
        return left, right
    return None


def locks_for_scene(
    ids: list[str] | None,
    by_name: dict[str, Character],
    scene: str,
    use_text: bool = True,
) -> list[str]:
    """Cast locks for a scene. Skip a lock already written into the wall (CHARACTER1)."""
    if not use_text:
        return []
    scene = scene or ""
    out: list[str] = []
    for name in ids or []:
        c = by_name.get(name)
        if not c:
            continue
        raw = (c.lock_text or "").strip()
        if not raw:
            continue
        if raw.rstrip(".,; ") in scene:
            continue
        out.append(c.lock_text)
    return out


def _pane_block(label: str, scene: str, locks: list[str], ref_n: int, cutout: bool) -> str:
    scene = _spacecraft(scene.strip().rstrip(".,; "))
    parts: list[str] = []
    if not ref_n:
        parts.extend(_lock_bits(locks))
    if scene:
        parts.append(scene)
    inner = _join_clauses(*parts)
    return f"{label}: {inner}" if inner else f"{label}:"


def assemble_pair(
    style: str,
    left_locks: list[str],
    left_scene: str,
    right_locks: list[str],
    right_scene: str,
    tail: str,
    layout_text: str = "",
    n_left_refs: int = 0,
    n_right_refs: int = 0,
    cutout: bool = False,
    cutout_text: str = "",
    lettering: str = "",
) -> str:
    """Two different scenes: left pane, right pane. Lock in a pane only if that pane has no still."""
    style = style.strip()
    lt = (layout_text or LAYOUT_SPLIT).strip()
    closer = (tail or "").strip()
    lettering = (lettering or "").strip()
    if lettering:
        lt = layout_allow_lettering(lt)
        closer = tail_allow_lettering(closer)
    bits: list[str] = [style]
    if lt:
        bits.append(lt)
    if closer:
        bits.append(closer)
    bits.append(_pane_block("Left pane", left_scene, left_locks, 1 if n_left_refs else 0, cutout))
    right_ref = (2 if n_left_refs else 1) if n_right_refs else 0
    bits.append(_pane_block("Right pane", right_scene, right_locks, right_ref, cutout))
    if (n_left_refs or n_right_refs) and cutout:
        bits.extend(_lock_bits([cutout_text]))
    bits.append(
        "The left pane and the right pane are two different scenes, two different poses. "
        "Do not mirror. Do not copy the left place or action into the right pane."
    )
    core = _join_clauses(*bits)
    if not lettering:
        return core
    return f"{core} {LETTERING_CLOSER} {lettering}".strip()


def apply_split_pairs(
    plates: list[Plate],
    by_name: dict[str, Character],
    style: str,
    tail: str,
    layout_text: str,
    n_pictures_for: dict[str, int],
    cutout: bool,
    warnings: list[str],
    pair_consecutive: bool = True,
    cutout_text: str = "",
) -> None:
    """Split only plates that ask for it. Consecutive pairing is Settings two-pane only."""
    i = 0
    while i < len(plates):
        a = plates[i]
        inline = (a.pane_left and a.pane_right) or extract_inline_panes(a.scene_text)
        if inline:
            if a.pane_left and a.pane_right:
                ls, rs = a.pane_left, a.pane_right
                ids_l, ids_r = a.pane_left_ids or a.character_ids, a.pane_right_ids
            else:
                ls, rs = extract_inline_panes(a.scene_text) or ("", "")
                ids_l, ids_r = a.character_ids, a.character_ids
            locks_l = locks_for_scene(ids_l, by_name, ls, a.use_text)
            locks_r = locks_for_scene(ids_r, by_name, rs, a.use_text)
            pane_cutout = cutout or any(
                bool(getattr(by_name.get(n), "ref_cutout", False)) for n in (ids_l or []) + (ids_r or [])
            )
            text = assemble_pair(
                style,
                locks_l,
                ls,
                locks_r,
                rs,
                tail,
                layout_text=layout_text,
                n_left_refs=n_pictures_for.get(a.slug, 0),
                n_right_refs=n_pictures_for.get(a.slug, 0),
                cutout=pane_cutout,
                cutout_text=cutout_text,
                lettering=a.lettering_prompt if a.use_letter else "",
            )
            a.assembled = text
            a.pane, a.pair_with = "inline", a.slug
            i += 1
            continue
        if not pair_consecutive:
            i += 1
            continue
        if i + 1 >= len(plates):
            msg = f"{a.slug}: no pair for two-pane (need a next prompt)"
            a.warnings.append(msg)
            warnings.append(msg)
            i += 1
            continue
        b = plates[i + 1]
        locks_a = locks_for_scene(a.character_ids, by_name, a.scene_text, a.use_text)
        locks_b = locks_for_scene(b.character_ids, by_name, b.scene_text, b.use_text)
        pair_cutout = cutout or any(
            bool(getattr(by_name.get(n), "ref_cutout", False))
            for n in list(a.character_ids or []) + list(b.character_ids or [])
        )
        text = assemble_pair(
            style,
            locks_a,
            a.scene_text,
            locks_b,
            b.scene_text,
            tail,
            layout_text=layout_text,
            n_left_refs=n_pictures_for.get(a.slug, 0),
            n_right_refs=n_pictures_for.get(b.slug, 0),
            cutout=pair_cutout,
            cutout_text=cutout_text,
            lettering=combine_lettering(
                a.lettering_prompt if a.use_letter else "",
                b.lettering_prompt if b.use_letter else "",
            ),
        )
        a.assembled = text
        b.assembled = text
        a.pane, a.pair_with = "left", b.slug
        b.pane, b.pair_with = "right", a.slug
        i += 2


def parse_book(
    prompts_raw: str,
    captions_raw: str,
    characters: list[Character],
    style: str = STYLE,
    tail: str = "",
    n_pictures_for: dict[str, int] | None = None,
    cutout: bool = False,
    cutout_text: str = "",
    layout: str = "one",
    layout_text: str = "",
    use_text_for: dict[str, bool] | None = None,
    use_image_for: dict[str, bool] | None = None,
    use_letter_for: dict[str, bool] | None = None,
    text_default: bool = False,
    image_default: bool = False,
    letter_default: bool = False,
) -> ParseResult:
    names = [c.name for c in characters]
    name_set = set(names)
    by_name = {c.name: c for c in characters}
    n_pictures_for = n_pictures_for or {}
    use_text_for = use_text_for or {}
    use_image_for = use_image_for or {}
    use_letter_for = use_letter_for or {}
    warnings: list[str] = []

    prompt_items = parse_wall(prompts_raw, names)
    caps = parse_captions(captions_raw, names)

    prompt_slugs = [s for s, _ in prompt_items]
    for slug in caps:
        if not any(same_slug(slug, s) for s in prompt_slugs):
            warnings.append(f"caption slug {slug} has no prompt — ignored")

    plates: list[Plate] = []
    for i, (slug, raw_body) in enumerate(prompt_items, start=1):
        pw: list[str] = []
        body = _strip_style_tail(raw_body, style, tail, pw, slug)
        body = _flatten_scene(body)
        use_text = _slug_flag(use_text_for, slug, text_default)
        use_image = _slug_flag(use_image_for, slug, image_default)
        use_letter = _slug_flag(use_letter_for, slug, letter_default)
        decls = parse_character_decls(body, names)
        if decls:
            hits = [n for _, n in decls] if (use_text or use_image) else []
            named = list(hits)
            if use_text:
                body = expand_character_decls(body, by_name)
            scene = body
            locks_for_assemble = []
        elif use_text:
            hits = _character_hits(slug + " " + body, names)
            named = list(hits)
            scene = _strip_character_tokens(body, name_set)
            locks_for_assemble = [by_name[n].lock_text for n in hits if n in by_name]
        else:
            hits = []
            named = []
            scene = body
            locks_for_assemble = []
        scene = _image_slots(_spacecraft(scene))
        if re.search(r"\bKEEP\b", scene, re.I):
            scene = re.sub(r"\s*for costume only\b", "", scene, flags=re.I)
        if use_image and not named:
            nums = [int(x) for x in re.findall(r"\b(?:image|picture)(\d+)\b", scene, re.I)]
            n_slots = max(nums) if nums else 1
            named = [
                c.name for c in characters if c.name and (c.ref_images or c.ref_active)
            ][: max(1, n_slots)]
            hits = list(named)
            if named:
                pw.append(
                    f"{slug}: Image on, no PILOT1 in the wall — {', '.join(named)} → image1"
                )
            else:
                pw.append(f"{slug}: Image is on but no still on Cast")
        if re.search(r"\b(?:image|picture)\d+\b", raw_body, re.I) and not use_image:
            pw.append(f"{slug}: wall names image1/picture1 but Image is off — no still is sent")
        if re.search(r"costume only", raw_body, re.I) and "KEEP" not in (raw_body or "").upper():
            pw.append(
                f"{slug}: 'costume only' tells Krea to drop face and body from the still"
            )
        pane_left = pane_right = ""
        pane_left_ids: list[str] = []
        pane_right_ids: list[str] = []
        if raw_panes := extract_inline_panes(body):
            pre = re.split(r"left\s*pane", body, maxsplit=1, flags=re.I)[0]
            pane_left_ids = _character_hits(pre + " " + raw_panes[0], names)
            pane_right_ids = _character_hits(raw_panes[1], names)
            pane_left = _image_slots(
                _spacecraft(
                    re.sub(r"\s+", " ", _strip_character_tokens(raw_panes[0], name_set)).strip()
                )
            )
            pane_right = _image_slots(
                _spacecraft(
                    re.sub(r"\s+", " ", _strip_character_tokens(raw_panes[1], name_set)).strip()
                )
            )
        risky = len(hits) >= 2
        if risky:
            pw.append(f"{slug}: two-shot — faces fuse")
        metaphor = detect_metaphor(scene)
        caption = caption_for(slug, caps)
        beats, caption_bar = parse_caption_lettering(caption, characters)
        lettering_prompt = render_lettering(beats)
        n_pic = n_pictures_for.get(slug, 0) if use_image else 0
        plate_cutout = any(
            bool(getattr(by_name.get(n), "ref_cutout", False)) for n in (named or [])
        )
        assembled = assemble(
            style,
            locks_for_assemble,
            scene,
            tail,
            n_pictures=n_pic,
            cutout=plate_cutout,
            cutout_text=cutout_text,
            layout="one",
            layout_text=layout_text or LAYOUT_ONE,
            lettering=lettering_prompt if use_letter else "",
        )
        plates.append(
            Plate(
                slug=slug,
                order=i,
                scene_text=scene,
                character_ids=hits,
                metaphor=metaphor,
                helmet_on=True,
                caption=caption,
                risky_twoshot=risky,
                assembled=assembled,
                warnings=pw,
                pane_left=pane_left,
                pane_right=pane_right,
                pane_left_ids=pane_left_ids,
                pane_right_ids=pane_right_ids,
                named_ids=named,
                use_text=use_text,
                use_image=use_image,
                use_letter=use_letter,
                lettering_prompt=lettering_prompt,
                caption_bar=caption_bar,
            )
        )
        warnings.extend(pw)

    has_inline = any(p.pane_left and p.pane_right for p in plates)
    if (layout or "one") == "split":
        apply_split_pairs(
            plates,
            by_name,
            style,
            tail,
            layout_text or LAYOUT_SPLIT,
            n_pictures_for,
            cutout,
            warnings,
            pair_consecutive=True,
            cutout_text=cutout_text,
        )
    elif has_inline:
        apply_split_pairs(
            plates,
            by_name,
            style,
            tail,
            LAYOUT_SPLIT,
            n_pictures_for,
            cutout,
            warnings,
            pair_consecutive=False,
            cutout_text=cutout_text,
        )

    return ParseResult(plates=plates, warnings=warnings)
