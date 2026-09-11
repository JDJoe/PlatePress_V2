from __future__ import annotations

from pathlib import Path

from platepress.store import DEFAULT_API_WORKFLOW
from platepress.workflow_adapter import detect, fill, load_workflow

ROOT = Path(__file__).resolve().parent.parent


V3 = ROOT / DEFAULT_API_WORKFLOW
QWEN_MIN = {
    "2": {
        "inputs": {"prompt": "old", "clip": ["7", 1], "image1": ["11", 0]},
        "class_type": "TextEncodeQwenImageEditPlus",
        "_meta": {"title": "Prompt + Picture 1/2/3 (no VAE)"},
    },
    "3": {
        "inputs": {"text": "old-neg", "clip": ["7", 1]},
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Negative"},
    },
    "7": {
        "inputs": {"lora_01": "None", "strength_01": 0},
        "class_type": "Lora Loader Stack (rgthree)",
    },
    "8": {
        "inputs": {
            "seed": 1,
            "steps": 8,
            "cfg": 1,
            "sampler_name": "euler",
            "scheduler": "beta",
            "positive": ["2", 0],
            "negative": ["3", 0],
        },
        "class_type": "KSampler",
    },
    "11": {
        "inputs": {"image": "example.png"},
        "class_type": "LoadImage",
        "_meta": {"title": "Picture 1 — identity"},
    },
}


def test_detect_consistency_workflow():
    wf = load_workflow(V3)
    m = detect(wf)
    assert m.positive == "13"
    assert m.positive_key == "prompt"
    assert wf[m.positive]["class_type"] == "TextEncodeQwenImageEditPlus"
    assert "positive" in (wf[m.positive].get("_meta") or {}).get("title", "").lower()
    assert m.is_ref_workflow is True
    assert m.load_images == ["7", "28", "29"]
    assert m.negative == "14"
    assert m.negative_has_text is True
    assert m.ref_latent == "23"
    assert m.ref_vae_encode == "22"
    assert m.sampler == "15"
    assert m.lora == "27"
    assert m.unet == "6"
    assert m.latent == "24"
    assert m.save == "21"
    assert m.ref_method is None


def test_load_ui_graph_uses_api_sibling():
    ui = ROOT / "krea2_character_consistency_workflow-03.json"
    wf = load_workflow(ui)
    assert wf["13"]["class_type"] == "TextEncodeQwenImageEditPlus"
    assert "nodes" not in wf


def test_fill_ref_one_image_drops_unused_loaders():
    wf = load_workflow(V3)
    out = fill(
        wf,
        positive="hello",
        negative="neg",
        seed=42,
        prefix="PP_test_t1_one_42",
        lora_name="Krea2-aethernouveau-04/Krea2-aethernouveau-04_merged.safetensors",
        lora_strength=0.8,
        image_names=["android.png"],
        batch_size=1,
    )
    assert out["13"]["inputs"]["prompt"] == "hello"
    assert out["13"]["inputs"]["image1"] == ["7", 0]
    assert "image2" not in out["13"]["inputs"]
    assert "28" not in out
    assert "29" not in out
    assert out["7"]["inputs"]["image"] == "android.png"
    assert out["24"]["inputs"]["batch_size"] == 1
    assert out["15"]["inputs"]["seed"] == 42
    assert out["15"]["inputs"]["control_after_generate"] == "fixed"
    assert out["21"]["inputs"]["filename_prefix"] == "PP_test_t1_one_42"
    assert out["27"]["inputs"]["lora_01"].endswith("merged.safetensors")
    assert out["27"]["inputs"]["strength_01"] == 0.8
    # Keep ReferenceLatent between encode and sampler.
    assert out["15"]["inputs"]["positive"] == ["23", 0]
    assert out["15"]["inputs"]["negative"] == ["14", 0]
    assert "diptych" in out["14"]["inputs"]["prompt"]
    assert out["14"]["inputs"]["prompt"] != "neg"


def test_fill_no_still_drops_all_loaders():
    wf = load_workflow(V3)
    out = fill(
        wf,
        positive="hello",
        negative="neg",
        seed=1,
        prefix="PP_x",
        lora_name="foo.safetensors",
        lora_strength=0.5,
        image_names=[],
    )
    assert out["13"]["inputs"]["prompt"] == "hello"
    assert "image1" not in out["13"]["inputs"]
    assert "image2" not in out["13"]["inputs"]
    assert "7" not in out
    assert "28" not in out
    assert "29" not in out
    assert "22" not in out
    assert "23" not in out
    assert out["15"]["inputs"]["positive"] == ["13", 0]


def test_fill_two_stills_keeps_image2():
    wf = load_workflow(V3)
    out = fill(
        wf,
        positive="hello",
        negative="neg",
        seed=1,
        prefix="PP_x",
        lora_name="foo.safetensors",
        lora_strength=0.5,
        image_names=["a.png", "b.png"],
    )
    assert out["13"]["inputs"]["image1"] == ["7", 0]
    assert out["13"]["inputs"]["image2"] == ["28", 0]
    assert "image3" not in out["13"]["inputs"]
    assert out["7"]["inputs"]["image"] == "a.png"
    assert out["28"]["inputs"]["image"] == "b.png"
    assert "29" not in out
    assert out["15"]["inputs"]["positive"] == ["23", 0]


def test_fill_legacy_qwen_graph_still_works():
    wf = QWEN_MIN
    m = detect(wf)
    assert m.positive == "2"
    assert m.negative == "3"
    assert m.negative_has_text is True
    out = fill(
        wf,
        positive="hello",
        negative="neg",
        seed=1,
        prefix="PP_x",
        lora_name="foo.safetensors",
        lora_strength=0.5,
        image_names=[],
    )
    assert out["2"]["inputs"]["prompt"] == "hello"
    assert out["3"]["inputs"]["text"] == "neg"
    assert "11" not in out


def test_fill_unet_and_lora_stack():
    wf = load_workflow(V3)
    out = fill(
        wf,
        positive="hello",
        negative="neg",
        seed=1,
        prefix="PP_x",
        lora_name="ignored.safetensors",
        lora_strength=0.1,
        image_names=[],
        unet_name="KREA2/krea2_turbo_bf16.safetensors",
        loras=[
            {"name": "style/one.safetensors", "strength": 0.8},
            {"name": "extra/two.safetensors", "strength": 0.4},
        ],
    )
    assert out["6"]["inputs"]["unet_name"] == "KREA2/krea2_turbo_bf16.safetensors"
    assert out["27"]["inputs"]["lora_01"] == "style/one.safetensors"
    assert out["27"]["inputs"]["strength_01"] == 0.8
    assert out["27"]["inputs"]["lora_02"] == "extra/two.safetensors"
    assert out["27"]["inputs"]["strength_02"] == 0.4
    assert out["27"]["inputs"]["lora_03"] == "None"
    assert out["27"]["inputs"]["strength_03"] == 0.0
    assert out["27"]["inputs"]["lora_04"] == "None"


def test_still_for_comfy_rewrites_jpeg_as_png(tmp_path):
    from io import BytesIO

    from PIL import Image

    from platepress.comfy_client import still_for_comfy

    im = Image.new("RGB", (1408, 1408), (255, 255, 255))
    im.putpixel((10, 10), (200, 40, 40))
    src = tmp_path / "PILOT1A.jpg"
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=70)
    src.write_bytes(buf.getvalue())
    name, data = still_for_comfy(src)
    assert name == "PILOT1A.png"
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    out = Image.open(BytesIO(data))
    assert out.format == "PNG"
    assert max(out.size) <= 1024
