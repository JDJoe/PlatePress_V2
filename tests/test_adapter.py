from __future__ import annotations

from pathlib import Path

from platepress.store import DEFAULT_API_WORKFLOW
from platepress.workflow_adapter import detect, fill, load_workflow

ROOT = Path(__file__).resolve().parent.parent


V3 = ROOT / DEFAULT_API_WORKFLOW
V3_PREV = ROOT / "Krea2T_V3_ref_clean01-API.json"


def test_detect_v3_ref_workflow():
    wf = load_workflow(V3)
    m = detect(wf)
    assert m.positive == "16"
    assert m.positive_key == "prompt"
    assert wf[m.positive]["class_type"] == "TextEncodeKrea2"
    assert m.is_ref_workflow is True
    assert m.load_images == ["11", "12", "13"]
    assert m.negative == "18"
    assert m.negative_has_text is False
    assert m.rebalance == "17"
    assert m.previews == ["15"]
    assert m.sampler == "8"
    assert m.lora == "7"
    assert m.unet == "4"
    assert m.latent == "10"
    assert m.save == "14"
    assert m.ref_method is None


def test_load_ui_graph_uses_api_sibling():
    ui = ROOT / "Krea2T_V3_ref_clean03.json"
    wf = load_workflow(ui)
    assert wf["16"]["class_type"] == "TextEncodeKrea2"
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
    assert out["16"]["inputs"]["prompt"] == "hello"
    assert out["16"]["inputs"]["image1"] == ["11", 0]
    assert "vae" not in out["16"]["inputs"]
    assert "image2" not in out["16"]["inputs"]
    assert "12" not in out
    assert "13" not in out
    assert out["11"]["inputs"]["image"] == "android.png"
    assert out["10"]["inputs"]["batch_size"] == 1
    assert out["8"]["inputs"]["seed"] == 42
    assert out["8"]["inputs"]["control_after_generate"] == "fixed"
    assert out["14"]["inputs"]["filename_prefix"] == "PP_test_t1_one_42"
    assert out["7"]["inputs"]["lora_01"].endswith("merged.safetensors")
    assert out["7"]["inputs"]["strength_01"] == 0.8
    # Rebalance stays between encode and sampler. Do not rewire to node 16.
    assert out["8"]["inputs"]["positive"] == ["17", 0]
    assert out["8"]["inputs"]["negative"] == ["18", 0]
    assert out["18"]["class_type"] == "ConditioningZeroOut"
    assert "text" not in out["18"]["inputs"]
    assert "15" not in out
    assert "mask2" not in out["16"]["inputs"]


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
    assert out["16"]["inputs"]["prompt"] == "hello"
    assert "image1" not in out["16"]["inputs"]
    assert "image2" not in out["16"]["inputs"]
    assert "11" not in out
    assert "12" not in out
    assert "13" not in out
    assert "15" not in out
    assert "3" not in out
    assert "text" not in out["18"]["inputs"]


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
    assert out["16"]["inputs"]["image1"] == ["11", 0]
    assert out["16"]["inputs"]["image2"] == ["12", 0]
    assert "image3" not in out["16"]["inputs"]
    assert out["11"]["inputs"]["image"] == "a.png"
    assert out["12"]["inputs"]["image"] == "b.png"
    assert "13" not in out
    assert out["8"]["inputs"]["positive"] == ["17", 0]


def test_fill_legacy_qwen_graph_still_works():
    wf = load_workflow(V3_PREV)
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
    assert out["4"]["inputs"]["unet_name"] == "KREA2/krea2_turbo_bf16.safetensors"
    assert out["7"]["inputs"]["lora_01"] == "style/one.safetensors"
    assert out["7"]["inputs"]["strength_01"] == 0.8
    assert out["7"]["inputs"]["lora_02"] == "extra/two.safetensors"
    assert out["7"]["inputs"]["strength_02"] == 0.4
    assert out["7"]["inputs"]["lora_03"] == "None"
    assert out["7"]["inputs"]["strength_03"] == 0.0
    assert out["7"]["inputs"]["lora_04"] == "None"


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
