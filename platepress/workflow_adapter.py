"""Load a Comfy API JSON, detect nodes by class_type, fill one job."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Workflow = dict[str, Any]


class AdapterError(Exception):
    def __init__(self, message: str, node_id: str | None = None, key: str | None = None):
        super().__init__(message)
        self.node_id = node_id
        self.key = key


# Prompt key for vision encode nodes. CLIPTextEncode stays on "text".
_PROMPT_ENCODERS = {
    "TextEncodeQwenImageEditPlus": "prompt",
    "TextEncodeKrea2": "prompt",
}


@dataclass
class NodeMap:
    lora: str | None = None
    positive: str | None = None
    negative: str | None = None
    sampler: str | None = None
    latent: str | None = None
    save: str | None = None
    load_images: list[str] = field(default_factory=list)
    previews: list[str] = field(default_factory=list)
    ref_method: str | None = None
    rebalance: str | None = None
    unet: str | None = None
    clip: str | None = None
    vae: str | None = None
    is_ref_workflow: bool = False
    positive_key: str = "text"
    negative_key: str = "text"
    negative_has_text: bool = False
    ref_latent: str | None = None
    ref_vae_encode: str | None = None


def _is_ui_graph(data: dict[str, Any]) -> bool:
    return "nodes" in data and "links" in data


def _api_sibling(path: Path) -> Path | None:
    """foo.json → foo-API.json"""
    stem = path.stem
    if stem.endswith("-API"):
        return None
    cand = path.with_name(f"{stem}-API.json")
    return cand if cand.is_file() else None


def load_workflow(path: Path) -> Workflow:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise AdapterError(f"workflow JSON missing: {path}") from e
    except json.JSONDecodeError as e:
        raise AdapterError(f"workflow JSON is not valid JSON: {path}") from e
    if not isinstance(data, dict) or not data:
        raise AdapterError(f"workflow JSON has no nodes: {path}")
    # UI graphs have a top-level "nodes" list. Use the sibling API export if present.
    if _is_ui_graph(data):
        alt = _api_sibling(path)
        if alt is not None:
            return load_workflow(alt)
        raise AdapterError(
            f"{path.name} is a UI workflow. Export Save (API Format) from ComfyUI."
        )
    return data


def _still_slot_order(workflow: Workflow, positive_id: str | None) -> list[str]:
    """image1, image2, image3 on the positive encode — not LoadImage node-id order."""
    if not positive_id:
        return []
    node = workflow.get(positive_id) or {}
    inputs = node.get("inputs") or {}
    out: list[str] = []
    for i in range(1, 8):
        v = inputs.get(f"image{i}")
        if isinstance(v, list) and v:
            out.append(str(v[0]))
    return out


def detect(workflow: Workflow) -> NodeMap:
    m = NodeMap()
    loaders: list[tuple[int, str]] = []
    for nid, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or ""
        title = ((node.get("_meta") or {}).get("title") or "").lower()
        inputs = node.get("inputs") or {}
        if ct == "Lora Loader Stack (rgthree)" or "lora" in ct.lower():
            m.lora = str(nid)
        elif ct in _PROMPT_ENCODERS:
            key = _PROMPT_ENCODERS[ct]
            has_still = isinstance(inputs.get("image1"), list)
            if "positive" in title or (m.positive is None and has_still):
                m.positive = str(nid)
                m.positive_key = key
                m.is_ref_workflow = True
            elif m.positive is None:
                m.positive = str(nid)
                m.positive_key = key
                m.is_ref_workflow = True
            else:
                m.negative = str(nid)
                m.negative_key = key
                m.negative_has_text = True
        elif ct == "CLIPTextEncode":
            if "prompt -" in title or "negative" in title:
                m.negative = str(nid)
                m.negative_has_text = True
                m.negative_key = "text"
            elif m.positive is None:
                m.positive = str(nid)
                m.positive_key = "text"
            elif m.negative is None:
                m.negative = str(nid)
                m.negative_has_text = True
                m.negative_key = "text"
        elif ct == "KSampler":
            m.sampler = str(nid)
        elif ct in ("EmptySD3LatentImage", "EmptyLatentImage"):
            m.latent = str(nid)
        elif ct == "SaveImage":
            m.save = str(nid)
        elif ct == "PreviewImage":
            m.previews.append(str(nid))
        elif ct == "LoadImage":
            loaders.append((int(nid) if str(nid).isdigit() else 0, str(nid)))
        elif ct == "FluxKontextMultiReferenceLatentMethod":
            m.ref_method = str(nid)
        elif ct == "ReferenceLatent":
            m.ref_latent = str(nid)
        elif ct == "VAEEncode":
            m.ref_vae_encode = str(nid)
        elif ct == "ConditioningKrea2Rebalance":
            m.rebalance = str(nid)
        elif ct == "ConditioningZeroOut":
            if m.negative is None:
                m.negative = str(nid)
                m.negative_has_text = False
        elif ct == "UNETLoader":
            m.unet = str(nid)
        elif ct == "CLIPLoader":
            m.clip = str(nid)
        elif ct == "VAELoader":
            m.vae = str(nid)
    loaders.sort()
    linked = _still_slot_order(workflow, m.positive)
    if linked:
        m.load_images = linked
    else:
        m.load_images = [nid for _, nid in loaders]
    if m.load_images or m.ref_latent:
        m.is_ref_workflow = True
    return m


def _set(wf: Workflow, node_id: str | None, key: str, value: Any) -> None:
    if node_id is None:
        raise AdapterError(f"workflow missing node for {key}", key=key)
    node = wf.get(node_id)
    if not isinstance(node, dict):
        raise AdapterError(f"workflow node {node_id} missing", node_id=node_id, key=key)
    inputs = node.setdefault("inputs", {})
    inputs[key] = value


def prune_unused_refs(wf: Workflow, nmap: NodeMap, n_images: int) -> None:
    """Wire stills to image1..N. Drop unused LoadImage so example.png is not required.

    TextEncodeKrea2 only declares image1 in object_info; extra image2/image3 slots are
    dynamic kwargs and are valid. Unused slots must be omitted, not left on example.png.
    """
    if not nmap.positive:
        return
    pos = wf.get(nmap.positive, {})
    inputs = pos.setdefault("inputs", {})
    used: set[str] = set()
    for i, nid in enumerate(nmap.load_images):
        slot = f"image{i + 1}"
        mask = f"mask{i + 1}"
        if i < n_images:
            inputs[slot] = [nid, 0]
            used.add(nid)
        else:
            inputs.pop(slot, None)
            inputs.pop(mask, None)
            wf.pop(nid, None)
    # VAE on a Qwen-edit encode builds reference_latents. Krea pastes those stills
    # as a diptych. TextEncodeKrea2 has no VAE; popping is a no-op.
    inputs.pop("vae", None)
    for nid, node in list(wf.items()):
        if not isinstance(node, dict) or node.get("class_type") != "LoadImage":
            continue
        if nid not in used:
            wf.pop(nid, None)


def fill(
    workflow: Workflow,
    *,
    positive: str,
    negative: str,
    seed: int,
    prefix: str,
    lora_name: str,
    lora_strength: float,
    image_names: list[str],
    batch_size: int = 1,
    steps: int | None = None,
    cfg: float | None = None,
    sampler_name: str | None = None,
    scheduler: str | None = None,
    unet_name: str | None = None,
    loras: list[dict[str, Any]] | None = None,
) -> Workflow:
    wf = copy.deepcopy(workflow)
    nmap = detect(wf)
    if nmap.positive is None:
        raise AdapterError(
            "no positive encode node (CLIPTextEncode, TextEncodeQwenImageEditPlus, or TextEncodeKrea2)"
        )
    if nmap.sampler is None:
        raise AdapterError("no KSampler node")

    _set(wf, nmap.positive, nmap.positive_key, positive)
    if nmap.negative and nmap.negative_has_text:
        neg_ct = (wf.get(nmap.negative) or {}).get("class_type") or ""
        # Leave Qwen negative as the graph's diptych ban. CLIP neg gets Settings NEG.
        if neg_ct == "CLIPTextEncode":
            _set(wf, nmap.negative, nmap.negative_key or "text", negative)
    if nmap.unet and unet_name:
        _set(wf, nmap.unet, "unet_name", unet_name)
    if nmap.lora:
        if loras is not None:
            slots = [
                (str(item.get("name") or "").strip(), float(item.get("strength") or 0))
                for item in loras
                if isinstance(item, dict) and str(item.get("name") or "").strip()
                and str(item.get("name") or "").strip().lower() != "none"
            ][:4]
            for i in range(1, 5):
                if i <= len(slots):
                    _set(wf, nmap.lora, f"lora_0{i}", slots[i - 1][0])
                    _set(wf, nmap.lora, f"strength_0{i}", slots[i - 1][1])
                else:
                    _set(wf, nmap.lora, f"lora_0{i}", "None")
                    _set(wf, nmap.lora, f"strength_0{i}", 0.0)
        else:
            _set(wf, nmap.lora, "lora_01", lora_name)
            _set(wf, nmap.lora, "strength_01", float(lora_strength))
    _set(wf, nmap.sampler, "seed", int(seed))
    samp_in = wf[nmap.sampler]["inputs"]
    samp_in["control_after_generate"] = "fixed"
    if steps is not None:
        samp_in["steps"] = int(steps)
    if cfg is not None:
        samp_in["cfg"] = float(cfg)
    if sampler_name:
        samp_in["sampler_name"] = sampler_name
    if scheduler:
        samp_in["scheduler"] = scheduler
    if nmap.latent:
        _set(wf, nmap.latent, "batch_size", int(batch_size))
    if nmap.save:
        _set(wf, nmap.save, "filename_prefix", prefix)

    n_img = len(image_names)
    if nmap.is_ref_workflow:
        prune_unused_refs(wf, nmap, n_img)
        for i, name in enumerate(image_names):
            if i >= len(nmap.load_images):
                break
            if nmap.load_images[i] not in wf:
                break
            _set(wf, nmap.load_images[i], "image", name)
        # Do not run the Kontext ref-latent path: it stamps/clones the still
        # into the plate (diptych, twin cosmonauts). Sampler reads encode only.
        # Keep ConditioningKrea2Rebalance between encode and sampler.
        if nmap.ref_method:
            wf.pop(nmap.ref_method, None)
            if nmap.rebalance is None and nmap.ref_latent is None:
                samp_in["positive"] = [nmap.positive, 0]
        # No still: do not VAE-encode a leftover LoadImage. Sampler reads the text encode.
        if n_img == 0 and nmap.ref_latent:
            samp_in["positive"] = [nmap.positive, 0]
            wf.pop(nmap.ref_latent, None)
            if nmap.ref_vae_encode:
                wf.pop(nmap.ref_vae_encode, None)
    for nid in nmap.previews:
        wf.pop(nid, None)
    return wf
