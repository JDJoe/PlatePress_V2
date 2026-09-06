from __future__ import annotations

from pathlib import Path

from platepress.workflow_adapter import detect, fill, load_workflow

ROOT = Path(__file__).resolve().parent.parent


def test_detect_text_workflow():
    wf = load_workflow(ROOT / "Krea2T_API01.json")
    m = detect(wf)
    assert m.positive == "2"
    assert m.positive_key == "text"
    assert m.negative == "3"
    assert m.lora == "7"
    assert m.sampler == "8"
    assert m.latent == "15"
    assert m.save == "10"
    assert m.is_ref_workflow is False


def test_detect_ref_workflow():
    wf = load_workflow(ROOT / "Krea2T_V2_ref_API.json")
    m = detect(wf)
    assert m.positive == "2"
    assert m.positive_key == "prompt"
    assert m.is_ref_workflow is True
    assert m.load_images == ["16", "17", "18"]
    assert m.ref_method == "19"
    assert m.sampler == "8"
    assert m.lora == "7"


def test_fill_ref_one_image_drops_unused_loaders():
    wf = load_workflow(ROOT / "Krea2T_V2_ref_API.json")
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
    assert out["2"]["inputs"]["image1"] == ["16", 0]
    assert "vae" not in out["2"]["inputs"]
    assert "image2" not in out["2"]["inputs"]
    assert "17" not in out
    assert "18" not in out
    assert out["16"]["inputs"]["image"] == "android.png"
    assert out["15"]["inputs"]["batch_size"] == 1
    assert out["8"]["inputs"]["seed"] == 42
    assert out["8"]["inputs"]["control_after_generate"] == "fixed"
    assert out["10"]["inputs"]["filename_prefix"] == "PP_test_t1_one_42"
    assert out["7"]["inputs"]["lora_01"].endswith("merged.safetensors")
    assert out["7"]["inputs"]["strength_01"] == 0.8
    assert out["8"]["inputs"]["positive"] == ["2", 0]
    assert "19" not in out


def test_fill_text_uses_text_key():
    wf = load_workflow(ROOT / "Krea2T_API01.json")
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
    assert out["2"]["inputs"]["text"] == "hello"
    assert out["3"]["inputs"]["text"] == "neg"
