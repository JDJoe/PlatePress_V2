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


@dataclass
class NodeMap:
    lora: str | None = None
    positive: str | None = None
    negative: str | None = None
    sampler: str | None = None
    latent: str | None = None
    save: str | None = None
    load_images: list[str] = field(default_factory=list)
    ref_method: str | None = None
    unet: str | None = None
    clip: str | None = None
    vae: str | None = None
    is_ref_workflow: bool = False
    positive_key: str = "text"


def load_workflow(path: Path) -> Workflow:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise AdapterError(f"workflow JSON missing: {path}") from e
    except json.JSONDecodeError as e:
        raise AdapterError(f"workflow JSON is not valid JSON: {path}") from e
    if not isinstance(data, dict) or not data:
        raise AdapterError(f"workflow JSON has no nodes: {path}")
    # UI graphs have a top-level "nodes" list — refuse them.
    if "nodes" in data and "links" in data:
        raise AdapterError(
            f"{path.name} is a UI workflow. Export Save (API Format) from ComfyUI."
        )
    return data


def detect(workflow: Workflow) -> NodeMap:
    m = NodeMap()
    loaders: list[tuple[int, str]] = []
    for nid, node in workflow.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or ""
        title = ((node.get("_meta") or {}).get("title") or "").lower()
        if ct == "Lora Loader Stack (rgthree)" or "lora" in ct.lower():
            m.lora = str(nid)
        elif ct == "TextEncodeQwenImageEditPlus":
            m.positive = str(nid)
            m.positive_key = "prompt"
            m.is_ref_workflow = True
        elif ct == "CLIPTextEncode":
            if "prompt -" in title or "negative" in title:
                m.negative = str(nid)
            elif m.positive is None:
                m.positive = str(nid)
                m.positive_key = "text"
            else:
                m.negative = m.negative or str(nid)
        elif ct == "KSampler":
            m.sampler = str(nid)
        elif ct in ("EmptySD3LatentImage", "EmptyLatentImage"):
            m.latent = str(nid)
        elif ct == "SaveImage":
            m.save = str(nid)
        elif ct == "LoadImage":
            loaders.append((int(nid) if str(nid).isdigit() else 0, str(nid)))
        elif ct == "FluxKontextMultiReferenceLatentMethod":
            m.ref_method = str(nid)
        elif ct == "UNETLoader":
            m.unet = str(nid)
        elif ct == "CLIPLoader":
            m.clip = str(nid)
        elif ct == "VAELoader":
            m.vae = str(nid)
    loaders.sort()
    m.load_images = [nid for _, nid in loaders]
    if m.load_images:
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
    """Drop unused LoadImage nodes so example.png is not required."""
    if not nmap.positive:
        return
    pos = wf.get(nmap.positive, {})
    inputs = pos.setdefault("inputs", {})
    for i, nid in enumerate(nmap.load_images):
        slot = f"image{i + 1}"
        if i < n_images:
            inputs[slot] = [nid, 0]
        else:
            inputs.pop(slot, None)
            wf.pop(nid, None)
    # VAE on the encode node builds reference_latents. Without an edit LoRA
    # Krea pastes those stills into the plate as a diptych. Vision tokens only.
    inputs.pop("vae", None)


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
) -> Workflow:
    wf = copy.deepcopy(workflow)
    nmap = detect(wf)
    if nmap.positive is None:
        raise AdapterError("no positive encode node (CLIPTextEncode or TextEncodeQwenImageEditPlus)")
    if nmap.sampler is None:
        raise AdapterError("no KSampler node")

    _set(wf, nmap.positive, nmap.positive_key, positive)
    if nmap.negative:
        _set(wf, nmap.negative, "text", negative)
    if nmap.lora:
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
            _set(wf, nmap.load_images[i], "image", name)
        # Do not run the Kontext ref-latent path: it stamps/clones the still
        # into the plate (diptych, twin cosmonauts). Sampler reads encode only.
        if nmap.ref_method:
            wf.pop(nmap.ref_method, None)
            samp_in["positive"] = [nmap.positive, 0]
    return wf
