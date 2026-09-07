from __future__ import annotations

from pathlib import Path

from platepress.workflow_adapter import detect, fill, load_workflow

ROOT = Path(__file__).resolve().parent.parent


V3 = ROOT / "Krea2T_V3_ref_clean01-API.json"


def test_detect_v3_ref_workflow():
    wf = load_workflow(V3)
    m = detect(wf)
    assert m.positive == "2"
    assert m.positive_key == "prompt"
    assert m.is_ref_workflow is True
    assert m.load_images == ["11", "12", "13"]
    assert m.negative == "3"
    assert m.sampler == "8"
    assert m.lora == "7"
    assert m.latent == "10"
    assert m.save == "14"
    assert m.ref_method is None


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
    assert out["2"]["inputs"]["prompt"] == "hello"
    assert out["2"]["inputs"]["image1"] == ["11", 0]
    assert "vae" not in out["2"]["inputs"]
    assert "image2" not in out["2"]["inputs"]
    assert "12" not in out
    assert "13" not in out
    assert out["11"]["inputs"]["image"] == "android.png"
    assert out["10"]["inputs"]["batch_size"] == 1
    assert out["8"]["inputs"]["seed"] == 42
    assert out["8"]["inputs"]["control_after_generate"] == "fixed"
    assert out["14"]["inputs"]["filename_prefix"] == "PP_test_t1_one_42"
    assert out["7"]["inputs"]["lora_01"].endswith("merged.safetensors")
    assert out["7"]["inputs"]["strength_01"] == 0.8
    assert out["8"]["inputs"]["positive"] == ["2", 0]


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
    assert out["2"]["inputs"]["prompt"] == "hello"
    assert "image1" not in out["2"]["inputs"]
    assert "11" not in out
    assert "12" not in out
    assert "13" not in out
    assert out["3"]["inputs"]["text"] == "neg"


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
