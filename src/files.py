import base64
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

import requests


def _extension_from_content_type(content_type: str | None, fallback: str = ".png") -> str:
    if not content_type:
        return fallback
    extension = mimetypes.guess_extension(content_type.split(";")[0].strip())
    return extension or fallback


def save_input_image(job_input: dict[str, Any], input_dir: str) -> str:
    Path(input_dir).mkdir(parents=True, exist_ok=True)
    filename = f"artely_input_{uuid.uuid4().hex}.png"
    path = Path(input_dir) / filename

    image_url = job_input.get("image_url")
    image_base64 = job_input.get("image_base64")

    if image_url:
        response = requests.get(image_url, timeout=120)
        response.raise_for_status()
        extension = _extension_from_content_type(response.headers.get("content-type"))
        filename = f"artely_input_{uuid.uuid4().hex}{extension}"
        path = Path(input_dir) / filename
        path.write_bytes(response.content)
        return filename

    if image_base64:
        if "," in image_base64 and image_base64.strip().startswith("data:"):
            image_base64 = image_base64.split(",", 1)[1]
        path.write_bytes(base64.b64decode(image_base64))
        return filename

    raise ValueError("Provide image_url or image_base64.")


def read_output_file(path: str, return_base64: bool) -> dict[str, Any]:
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    payload: dict[str, Any] = {
        "filename": os.path.basename(path),
        "type": content_type,
        "base64": None,
    }
    if return_base64:
        payload["base64"] = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return payload


def upload_output(path: str, upload_url: str, content_type: str | None = None) -> dict[str, Any]:
    resolved_type = content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
    response = requests.put(
        upload_url,
        data=Path(path).read_bytes(),
        headers={"Content-Type": resolved_type},
        timeout=180,
    )
    return {
        "uploaded": 200 <= response.status_code < 300,
        "upload_status": response.status_code,
        "upload_response": response.text[:500],
    }

