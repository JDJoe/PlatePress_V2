"""Story wall + caption wall → plates. The app assembles STYLE/lock/TAIL."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .defaults import CLOSER_SPLIT, LAYOUT_ONE, LAYOUT_SPLIT, LOCK_POSE, METAPHORS, REF_CUTOUT, STYLE, TAIL

# Preferred: p1_cargo / t1_one. Also any identifier that is not a known character.
_SLUG_PREF = re.compile(r"^p\d+_[A-Za-z0-9_]+$")
_SLUG_ANY = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SLUG_NUM = re.compile(r"^([pt])(\d+)_(.+)$", re.I)
_QUOTED = re.compile(r'^"([^"]+)"\s*(.*)$')
_BRACE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
SLUG_PAD = 3
# Krea still hears "ship" inside spaceship/starship and paints sails.
_VESSEL = re.compile(r"\b(?:star|space)?ships?\b", re.I)
_INLINE_PANES = re.compile(
    r"left\s*pane\s*[:,]?\s*(.*?)\s*right\s*pane\s*[:,]?\s*(.*)",
    re.I | re.S,
)


def pad_slug(slug: str, width: int = SLUG_PAD) -> str:
    """p1_cargo → p001_cargo so p010 sorts after p001, not before p1."""
    m = _SLUG_NUM.match(slug or "")
    if not m:
        return slug
    return f"{m.group(1).lower()}{int(m.group(2)):0{width}d}_{m.group(3)}"


def same_slug(a: str, b: str) -> bool:
    return a == b or pad_slug(a) == pad_slug(b)


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


@dataclass
class ParseResult:
    plates: list[Plate]
    warnings: list[str]


def _looks_like_slug(token: str, character_names: set[str]) -> bool:
    if token in character_names:
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


def _spacecraft(text: str) -> str:
    """ship / spaceship / starship → spacecraft. Does not touch spacesuit."""
    return _VESSEL.sub("spacecraft", text or "")


def _cutout_clause(cutout: bool, cutout_text: str = "") -> str:
    if not cutout:
        return ""
    return (cutout_text or REF_CUTOUT).strip()


def _ref_hint(n: int, cutout: bool) -> str:
    if cutout:
        return (
            f"Use image{n} as reference for how this subject looks, background removed. "
            "Do not copy its pose, seat, window, room, or composition."
        )
    return (
        f"Use image{n} as reference for how this subject looks. "
        "Do not copy its pose, seat, window, room, or composition."
    )


def _close(text: str, tail: str) -> str:
    tail = tail if tail.startswith(" ") or tail == "" else " " + tail
    text = text.rstrip(".,; ") + "."
    if tail.strip():
        t = tail.strip()
        if not text.endswith(t):
            text = text.rstrip() + (tail if tail.startswith(" ") else " " + tail)
    return text


def _clause(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    return s.rstrip(".,; ") + "."


def _join_clauses(*parts: str) -> str:
    return " ".join(_clause(p) for p in parts if p and str(p).strip())


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
) -> str:
    """Ink + layout + optional closer + Book wall. Cast lock and stills copy live in the wall."""
    style = style.strip()
    scene = _spacecraft(scene.strip().rstrip(".,; "))
    lt = (layout_text or LAYOUT_ONE).strip()
    bits: list[str] = [style]
    if lt and (layout or "one") != "split":
        bits.append(lt)
    if (tail or "").strip():
        bits.append(tail.strip())
    if scene:
        bits.append(scene)
    return _join_clauses(*bits)


def extract_inline_panes(scene: str) -> tuple[str, str] | None:
    """If the wall already wrote left pane / right pane, split them."""
    m = _INLINE_PANES.search(scene or "")
    if not m:
        return None
    left, right = m.group(1).strip(), m.group(2).strip()
    if left and right:
        return left, right
    return None


def _pane_block(label: str, scene: str, locks: list[str], ref_n: int, cutout: bool) -> str:
    scene = _spacecraft(scene.strip().rstrip(".,; "))
    inner = _join_clauses(scene)
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
) -> str:
    """Two different scenes: left pane, right pane. Wall text only in each pane."""
    style = style.strip()
    lt = (layout_text or LAYOUT_SPLIT).strip()
    bits: list[str] = [style]
    if lt:
        bits.append(lt)
    if (tail or "").strip():
        bits.append(tail.strip())
    bits.append(_pane_block("Left pane", left_scene, left_locks, 1 if n_left_refs else 0, cutout))
    right_ref = (2 if n_left_refs else 1) if n_right_refs else 0
    bits.append(_pane_block("Right pane", right_scene, right_locks, right_ref, cutout))
    bits.append(
        "The left pane and the right pane are two different scenes, two different poses. "
        "Do not mirror. Do not copy the left place or action into the right pane."
    )
    return _join_clauses(*bits)


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
        locks_a = [by_name[n].lock_text for n in a.character_ids if n in by_name]
        inline = (a.pane_left and a.pane_right) or extract_inline_panes(a.scene_text)
        if inline:
            if a.pane_left and a.pane_right:
                ls, rs = a.pane_left, a.pane_right
                ids_l, ids_r = a.pane_left_ids or a.character_ids, a.pane_right_ids
            else:
                ls, rs = extract_inline_panes(a.scene_text) or ("", "")
                ids_l, ids_r = a.character_ids, a.character_ids
            locks_l = [by_name[n].lock_text for n in ids_l if n in by_name]
            locks_r = [by_name[n].lock_text for n in ids_r if n in by_name]
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
                cutout=cutout,
                cutout_text=cutout_text,
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
        locks_b = [by_name[n].lock_text for n in b.character_ids if n in by_name]
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
            cutout=cutout,
            cutout_text=cutout_text,
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
    tail: str = TAIL,
    n_pictures_for: dict[str, int] | None = None,
    cutout: bool = False,
    cutout_text: str = "",
    layout: str = "one",
    layout_text: str = "",
) -> ParseResult:
    names = [c.name for c in characters]
    name_set = set(names)
    default_id = names[0] if names else None
    by_name = {c.name: c for c in characters}
    n_pictures_for = n_pictures_for or {}
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
        hits = _character_hits(slug + " " + raw_body, names)
        body = _strip_style_tail(raw_body, style, tail, pw, slug)
        raw_panes = extract_inline_panes(body)
        scene = _strip_character_tokens(body, name_set)
        scene = re.sub(r"\s+", " ", scene).strip()
        scene = _spacecraft(scene)
        pane_left = pane_right = ""
        pane_left_ids: list[str] = []
        pane_right_ids: list[str] = []
        if raw_panes:
            pre = re.split(r"left\s*pane", body, maxsplit=1, flags=re.I)[0]
            pane_left_ids = _character_hits(pre + " " + raw_panes[0], names)
            pane_right_ids = _character_hits(raw_panes[1], names)
            pane_left = _spacecraft(
                re.sub(r"\s+", " ", _strip_character_tokens(raw_panes[0], name_set)).strip()
            )
            pane_right = _spacecraft(
                re.sub(r"\s+", " ", _strip_character_tokens(raw_panes[1], name_set)).strip()
            )
        named = list(hits)
        if not hits and default_id:
            hits = [default_id]
            pw.append(
                f"{slug}: no character token — used {default_id} lock, stills not attached"
            )
        risky = len(hits) >= 2
        if risky:
            pw.append(f"{slug}: two-shot — faces fuse")
        metaphor = detect_metaphor(scene)
        caption = caption_for(slug, caps)
        locks = [by_name[n].lock_text for n in hits if n in by_name]
        n_pic = n_pictures_for.get(slug, 0)
        assembled = assemble(
            style,
            locks,
            scene,
            tail,
            n_pictures=n_pic,
            cutout=cutout,
            cutout_text=cutout_text,
            layout="one",
            layout_text=layout_text or LAYOUT_ONE,
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
            CLOSER_SPLIT,
            LAYOUT_SPLIT,
            n_pictures_for,
            cutout,
            warnings,
            pair_consecutive=False,
            cutout_text=cutout_text,
        )

    return ParseResult(plates=plates, warnings=warnings)
