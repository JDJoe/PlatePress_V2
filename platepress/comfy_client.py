"""Queue prompts on a local ComfyUI. Comfy is an external process."""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from .workflow_adapter import AdapterError, Workflow

LATENT_EDGE = 1024


def still_for_comfy(path: Path, max_edge: int = LATENT_EDGE) -> tuple[str, bytes]:
    """PNG for LoadImage. JPEG stills on flat white pixelate Qwen; latent is 1024."""
    im = Image.open(path)
    im.load()
    if im.mode == "P":
        im = im.convert("RGBA" if "transparency" in im.info else "RGB")
    elif im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    w, h = im.size
    if max_edge and max(w, h) > max_edge:
        scale = max_edge / max(w, h)
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return path.stem + ".png", buf.getvalue()


class ComfyError(Exception):
    pass


class ComfyClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8188, timeout: float = 30.0):
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def url(self, path: str) -> str:
        return self.base.rstrip("/") + path

    def ping(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=3.0) as c:
                r = c.get(self.url("/system_stats"))
                r.raise_for_status()
            return True, "ComfyUI is up"
        except httpx.ConnectError:
            return False, (
                "ComfyUI is not running. Start it, then set host/port in Settings. "
                "Plate Press will not download the checkpoint."
            )
        except Exception as e:
            try:
                with httpx.Client(timeout=3.0) as c:
                    r = c.get(self.url("/queue"))
                    r.raise_for_status()
                return True, "ComfyUI is up"
            except Exception:
                return False, f"ComfyUI not reachable: {e}"

    def object_info(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(self.url("/object_info"))
            r.raise_for_status()
            body = r.json()
        if not isinstance(body, dict):
            raise ComfyError("Comfy /object_info was not an object")
        return body

    def _combo(self, info: dict[str, Any], class_type: str, input_name: str) -> list[str]:
        node = info.get(class_type) or {}
        inputs = node.get("input") or {}
        spec = (inputs.get("required") or {}).get(input_name) or (inputs.get("optional") or {}).get(
            input_name
        )
        names = spec[0] if isinstance(spec, list) and spec else []
        if not isinstance(names, list):
            return []
        return [str(x) for x in names if x is not None and str(x) != ""]

    def list_unets(self, info: dict[str, Any] | None = None) -> list[str]:
        info = info if info is not None else self.object_info()
        return [n for n in self._combo(info, "UNETLoader", "unet_name") if n.lower() != "none"]

    def list_loras(self, info: dict[str, Any] | None = None) -> list[str]:
        info = info if info is not None else self.object_info()
        names = self._combo(info, "Lora Loader Stack (rgthree)", "lora_01")
        if not names:
            names = self._combo(info, "LoraLoader", "lora_name")
        return [n for n in names if n.lower() != "none"]

    def upload_image(self, path: Path) -> str:
        """POST /upload/image. Returns the filename Comfy LoadImage expects."""
        try:
            name, data = still_for_comfy(path)
        except Exception:
            name, data = path.name, path.read_bytes()
        files = {"image": (name, data, "application/octet-stream")}
        form = {"overwrite": "true", "type": "input"}
        try:
            with httpx.Client(timeout=60.0) as c:
                r = c.post(self.url("/upload/image"), files=files, data=form)
                r.raise_for_status()
                body = r.json()
        except httpx.ConnectError as e:
            raise ComfyError(
                "ComfyUI is not running. Start it, then set host/port in Settings."
            ) from e
        name = body.get("name") or path.name
        sub = body.get("subfolder") or ""
        return f"{sub}/{name}" if sub else str(name)

    def queue(self, prompt: Workflow) -> str:
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(self.url("/prompt"), json={"prompt": prompt})
                r.raise_for_status()
                body = r.json()
        except httpx.ConnectError as e:
            raise ComfyError(
                "ComfyUI is not running. Start it, then set host/port in Settings."
            ) from e
        except httpx.HTTPStatusError as e:
            raise ComfyError(f"Comfy /prompt failed: {e.response.text[:500]}") from e
        if body.get("node_errors"):
            raise AdapterError(f"workflow node error: {body['node_errors']}")
        pid = body.get("prompt_id")
        if not pid:
            raise ComfyError(f"Comfy /prompt returned no prompt_id: {body}")
        return str(pid)

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        with httpx.Client(timeout=self.timeout) as c:
            r = c.get(self.url(f"/history/{prompt_id}"))
            r.raise_for_status()
            body = r.json()
        return body.get(prompt_id)

    def wait(self, prompt_id: str, timeout_s: float = 600.0, poll: float = 1.0) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                h = self.history(prompt_id)
            except Exception as e:
                last_err = e
                time.sleep(poll)
                continue
            if h:
                status = h.get("status") or {}
                if status.get("status_str") == "error":
                    raise ComfyError(f"Comfy job {prompt_id} error: {status.get('messages')}")
                if h.get("outputs") and status.get("completed") is not False:
                    return h
                if h.get("outputs") and status.get("completed") is True:
                    return h
            time.sleep(poll)
        raise ComfyError(
            f"queue timeout for {prompt_id}" + (f" ({last_err})" if last_err else "")
        )

    def fetch_images(self, history: dict[str, Any], dest_dir: Path, stem: str) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        outputs = history.get("outputs") or {}
        n = 0
        for _nid, out in outputs.items():
            for img in out.get("images") or []:
                if img.get("type") == "temp":
                    continue
                n += 1
                filename = img.get("filename") or ""
                sub = img.get("subfolder") or ""
                itype = img.get("type") or "output"
                params = {"filename": filename, "subfolder": sub, "type": itype}
                with httpx.Client(timeout=120.0) as c:
                    r = c.get(self.url("/view"), params=params)
                    r.raise_for_status()
                    data = r.content
                ext = Path(filename).suffix or ".png"
                path = dest_dir / f"{stem}{ext}"
                if path.exists() or n > 1:
                    k = n if n > 1 else 2
                    while True:
                        cand = dest_dir / f"{stem}_{k}{ext}"
                        if not cand.exists():
                            path = cand
                            break
                        k += 1
                path.write_bytes(data)
                written.append(path)
        return written
