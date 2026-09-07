from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from platepress.app import app


def test_portable_paths_are_repo_relative():
    from platepress import store

    rel = store.portable_path(store.ROOT / "Krea2T_V3_ref_clean01-API.json")
    assert rel == "Krea2T_V3_ref_clean01-API.json"
    got = store.resolve_user_path("Krea2T_V3_ref_clean01-API.json")
    assert got == (store.ROOT / "Krea2T_V3_ref_clean01-API.json").resolve()
    s = store.default_settings()
    assert not Path(s["workflow_text"]).is_absolute()
    assert not Path(s["output_root"]).is_absolute()
    assert "/home/" not in s["workflow_text"]
    assert "/home/" not in s["output_root"]
    assert s["ref_cutout"] is False
    assert s["tail"] == ""
    assert "cutouts" in (s.get("ref_cutout_text") or "").lower()


def test_ensure_demo_book_seeds_missing_default(tmp_path):
    from platepress import store

    s = store.default_settings()
    s["output_root"] = str(tmp_path / "books")
    store.ensure_demo_book(s)
    dest = tmp_path / "books" / "default"
    assert (dest / "book.json").exists()
    assert (dest / "prompts_raw.txt").read_text(encoding="utf-8").startswith("p1_cargo")
    chars = json.loads((dest / "characters.json").read_text(encoding="utf-8"))
    assert {c["name"] for c in chars} == {"ANDROID", "AUGUR"}
    assert not any("/home/" in (c.get("ref_active") or "") for c in chars)
    store.ensure_demo_book(s)
    # second call does not clobber
    (dest / "prompts_raw.txt").write_text("keep-me", encoding="utf-8")
    store.ensure_demo_book(s)
    assert (dest / "prompts_raw.txt").read_text(encoding="utf-8") == "keep-me"


def test_index_and_parse_t1(tmp_path, monkeypatch):
    from platepress import store

    monkeypatch.setattr(store, "DEFAULT_SETTINGS_PATH", tmp_path / "settings.json")
    s = store.default_settings()
    s["output_root"] = str(tmp_path / "books")
    store.save_settings(s, tmp_path / "settings.json")
    # app load_settings uses DEFAULT_SETTINGS_PATH — patched.
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Plate Press" in r.text
    r = client.post("/api/demo/t1")
    assert r.status_code == 200
    body = r.json()
    slugs = [p["slug"] for p in body["plates"]]
    assert slugs == ["t1_one", "t1_two"]
    assert body["plates"][0]["risky_twoshot"] is False
    assert "aethernouveau." in body["plates"][0]["assembled"]
    r = client.post("/api/demo/bos")
    assert r.status_code == 200
    body = r.json()
    assert len(body["plates"]) == 10
    assert any(p["risky_twoshot"] for p in body["plates"])
    r = client.get("/api/llm-sheet")
    assert "CHARACTER LOCKS" in r.json()["text"]
    assert "ANDROID" in r.json()["text"]
    r = client.post("/api/character/delete", json={"id": "augur", "name": "AUGUR"})
    assert r.status_code == 200, r.text
    names = [c["name"] for c in r.json()["book"]["characters"]]
    assert "AUGUR" not in names
    assert "ANDROID" in names
    r = client.post("/api/character/add")
    assert r.status_code == 200
    added = r.json()["book"]["characters"][-1]["name"]
    assert added != "ANDROID"
    r = client.post(
        "/api/book",
        json={"characters": [
            {"id": "a", "name": "ANDROID", "lock_text": "x", "ref_images": []},
            {"id": "b", "name": "ANDROID", "lock_text": "y", "ref_images": []},
        ]},
    )
    assert r.status_code == 400


def test_delete_plates_and_book(tmp_path, monkeypatch):
    from platepress import store
    from platepress.app import app as flaskish

    monkeypatch.setattr(store, "DEFAULT_SETTINGS_PATH", tmp_path / "settings.json")
    s = store.default_settings()
    s["output_root"] = str(tmp_path / "books")
    store.save_settings(s, tmp_path / "settings.json")
    client = TestClient(flaskish)
    d = tmp_path / "books" / "default" / "plates"
    d.mkdir(parents=True)
    (d / "p1_cargo_1.png").write_bytes(b"x")
    r = client.post("/api/plates/delete", json={"scope": "all"})
    assert r.status_code == 400
    r = client.post("/api/plates/delete", json={"confirm": True, "scope": "all"})
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1
    assert not (d / "p1_cargo_1.png").exists()
    r = client.post("/api/book/new", json={"title": "Scratch"})
    assert r.status_code == 200
    nid = r.json()["book"]["id"]
    r = client.post("/api/book/delete", json={"id": nid})
    assert r.status_code == 400
    r = client.post("/api/book/delete", json={"confirm": True, "id": nid})
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["books"]]
    assert nid not in ids
    r = client.post("/api/book/delete", json={"confirm": True, "id": "default"})
    assert r.status_code == 400
    assert (tmp_path / "books" / "default").is_dir()


def test_books_list_keeps_disk_folders_after_restart(tmp_path, monkeypatch):
    from platepress import store

    monkeypatch.setattr(store, "DEFAULT_SETTINGS_PATH", tmp_path / "settings.json")
    s = store.default_settings()
    root = tmp_path / "books"
    s["output_root"] = str(root)
    store.save_settings(s, tmp_path / "settings.json")
    client = TestClient(app)
    r = client.post("/api/book/new", json={"title": "Same Clouds", "id": "same_clouds"})
    assert r.status_code == 200
    assert r.json()["book"]["id"] == "same_clouds"
    dropped = root / "from_disk"
    dropped.mkdir()
    (dropped / "prompts_raw.txt").write_text("p1_one\nscene\n", encoding="utf-8")
    # New client = app restart; settings.json + folders on disk must still list.
    restarted = TestClient(app)
    r = restarted.get("/api/books")
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()["books"]]
    assert "same_clouds" in ids
    assert "from_disk" in ids
    assert "default" in ids
    assert r.json()["current"] == "same_clouds"


def test_runs_only_current_book(tmp_path, monkeypatch):
    from platepress import store

    monkeypatch.setattr(store, "DEFAULT_SETTINGS_PATH", tmp_path / "settings.json")
    s = store.default_settings()
    root = tmp_path / "books"
    s["output_root"] = str(root)
    store.save_settings(s, tmp_path / "settings.json")
    old = root / "default" / "plates"
    old.mkdir(parents=True)
    (old / "p1_cargo_1.png").write_bytes(b"old")
    client = TestClient(app)
    r = client.post("/api/book/new", json={"title": "Scratch"})
    assert r.status_code == 200
    nid = r.json()["book"]["id"]
    fresh = root / nid / "plates"
    fresh.mkdir(parents=True, exist_ok=True)
    (fresh / "p1_new_2.png").write_bytes(b"new")
    r = client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert body["current"] == nid
    names = [t["name"] for t in body["thumbs"]]
    assert names == [f"{nid}_v01_p001_new.png"]
    assert [b["id"] for b in body["books"]] == [nid]
    assert body["thumbs"][0]["book_id"] == nid
    assert body["thumbs"][0]["slug"] == "p001_new"
    assert body["thumbs"][0]["run"] == 1
    assert body["batches"][0]["label"] == "v01"


def test_settings_includes_layout_examples(tmp_path, monkeypatch):
    from platepress import store

    monkeypatch.setattr(store, "DEFAULT_SETTINGS_PATH", tmp_path / "settings.json")
    s = store.default_settings()
    s["output_root"] = str(tmp_path / "books")
    s["tail"] = " Single divided plate, two scenes. Environment to all four edges."
    s["neg"] = "two panels, diptych, text"
    store.save_settings(s, tmp_path / "settings.json")
    client = TestClient(app)
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["layout"] == "split"
    assert "vertical panes" in body["layout_text"]
    assert "two panels" not in body["neg"]
    assert "examples" in body and "bos" in body["examples"]
    assert "Single divided" not in (body.get("tail") or "")


def test_plate_name_slug_not_seed():
    from platepress.app import _plate_slug, _seed_from_stem

    assert _plate_slug("untitled_p5_embargo.png") == "p5_embargo"
    assert _seed_from_stem("untitled_p5_embargo", "p5_embargo") is None
    assert _seed_from_stem("untitled_p5_embargo_2", "p5_embargo") is None
    assert _plate_slug("p5_embargo_1346841254129315.png") == "p5_embargo"
    assert _seed_from_stem("p5_embargo_1346841254129315", "p5_embargo") == 1346841254129315


def test_normalize_plate_filenames_uses_book_id(tmp_path):
    from platepress.app import normalize_plate_filenames

    plates = tmp_path / "plates"
    plates.mkdir()
    (plates / "p5_embargo_1346841254129315.png").write_bytes(b"a")
    (plates / "p5_embargo_999.png").write_bytes(b"b")
    (plates / "untitled_p5_embargo.png").write_bytes(b"keep")
    renamed = normalize_plate_filenames(tmp_path, "untitled")
    names = sorted(p.name for p in plates.iterdir())
    assert "untitled_v01_p005_embargo.png" in names
    assert all("1346841254129315" not in n for n in names)
    assert all(n.startswith("untitled_v01_p005_embargo") for n in names)
    assert len(renamed) == 3


def test_next_run_groups_regenerates(tmp_path):
    from platepress.app import _file_stem, _next_run, _run_from_stem, normalize_plate_filenames

    plates = tmp_path / "plates"
    plates.mkdir()
    (plates / "default_v01_p001_cargo.png").write_bytes(b"a")
    (plates / "default_v01_p010_enough.png").write_bytes(b"b")
    assert _next_run(plates, "default") == 2
    assert _file_stem("default", "p1_cargo", 2) == "default_v02_p001_cargo"
    assert _file_stem("default", "p001_cargo_p002_claim", 4) == "default_v04_p001_cargo_p002_claim"
    assert _run_from_stem("default_v02_p001_cargo_2", "default") == 2
    assert _run_from_stem("default_001_p001_cargo", "default") == 1
    names = [
        _file_stem("default", "p1_cargo", 1),
        _file_stem("default", "p10_enough", 1),
        _file_stem("default", "p1_cargo", 2),
    ]
    assert names == [
        "default_v01_p001_cargo",
        "default_v01_p010_enough",
        "default_v02_p001_cargo",
    ]
    assert sorted(names) == names
    (plates / "default_002_p001_cargo.png").write_bytes(b"legacy")
    renamed = normalize_plate_filenames(tmp_path, "default")
    assert any(new.name == "default_v02_p001_cargo.png" for old, new in renamed)


def test_group_thumbs_splits_batches():
    from platepress.app import _group_thumbs

    thumbs = [
        {"name": "p1_cargo_1.png", "stem": "p1_cargo_1", "mtime": 300, "url": "/a"},
        {"name": "p1_cargo_2.png", "stem": "p1_cargo_2", "mtime": 290, "url": "/b"},
        {"name": "old_1.png", "stem": "p2_claim_9", "mtime": 10, "url": "/c"},
    ]
    runs = [
        {"plate_slug": "p1_cargo", "seed": 1, "batch_id": "bnew", "batch_at": "2026-09-05 21:40"},
        {"plate_slug": "p1_cargo", "seed": 2, "batch_id": "bnew", "batch_at": "2026-09-05 21:40"},
    ]
    batches = _group_thumbs(thumbs, runs)
    assert len(batches[0]["thumbs"]) == 2
    assert any("p2_claim" in (t.get("stem") or "") for b in batches for t in b["thumbs"])


def test_group_by_version_newest_first():
    from platepress.app import _group_by_version

    thumbs = [
        {"name": "default_v01_p001_cargo.png", "stem": "default_v01_p001_cargo", "run": 1, "mtime": 10},
        {"name": "default_v01_p001_cargo_2.png", "stem": "default_v01_p001_cargo_2", "run": 1, "mtime": 11},
        {"name": "default_v02_p001_cargo.png", "stem": "default_v02_p001_cargo", "run": 2, "mtime": 20},
        {"name": "default_v02_p010_enough.png", "stem": "default_v02_p010_enough", "run": 2, "mtime": 21},
    ]
    batches = _group_by_version(thumbs)
    assert [b["label"] for b in batches] == ["v02", "v01"]
    assert [t["name"] for t in batches[0]["thumbs"]] == [
        "default_v02_p001_cargo.png",
        "default_v02_p010_enough.png",
    ]
    assert len(batches[1]["thumbs"]) == 2


def test_one_ref_per_character_even_if_card_has_two(tmp_path):
    from platepress.app import _refs_for
    from platepress.parser import Character, Plate

    a = tmp_path / "old.png"
    b = tmp_path / "new.png"
    a.write_bytes(b"x")
    b.write_bytes(b"y")
    chars = [
        Character(
            id="android",
            name="ANDROID",
            lock_text="lock",
            ref_images=[str(a), str(b)],
            ref_active=str(b),
        ),
    ]
    plate = Plate(
        slug="p1_cargo",
        order=1,
        scene_text="scene",
        character_ids=["ANDROID"],
        metaphor=None,
        helmet_on=True,
        caption="",
        risky_twoshot=False,
    )
    refs = _refs_for(plate, chars)
    assert refs == [b]
    plate.named_ids = []
    assert _refs_for(plate, chars) == []
