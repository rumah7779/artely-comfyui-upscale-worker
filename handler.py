import os
import subprocess
import time
import uuid
from typing import Any

import runpod

from src.comfy_client import ComfyClient
from src.files import read_output_file, save_input_image, upload_output
from src.workflow import is_ui_workflow, load_workflow, prepare_workflow, ui_workflow_to_api_prompt


COMFYUI_DIR = os.getenv("COMFYUI_DIR", "/workspace/ComfyUI")
COMFY_HOST = os.getenv("COMFY_HOST", "127.0.0.1")
COMFY_PORT = int(os.getenv("COMFY_PORT", "8188"))
WORKFLOW_DIR = os.getenv("WORKFLOW_DIR", "/workspace/workflows")
INPUT_DIR = os.getenv("INPUT_DIR", f"{COMFYUI_DIR}/input")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", f"{COMFYUI_DIR}/output")
START_TIMEOUT = int(os.getenv("COMFY_START_TIMEOUT_SECONDS", "180"))

_comfy_process: subprocess.Popen | None = None
_client: ComfyClient | None = None


def start_comfyui() -> ComfyClient:
    global _comfy_process, _client

    if _client is not None:
        return _client

    command = [
        "python3",
        "main.py",
        "--listen",
        COMFY_HOST,
        "--port",
        str(COMFY_PORT),
    ]

    _comfy_process = subprocess.Popen(command, cwd=COMFYUI_DIR)
    _client = ComfyClient(COMFY_HOST, COMFY_PORT, OUTPUT_DIR)
    _client.wait_until_ready(START_TIMEOUT)
    return _client


def normalize_input(event: dict[str, Any]) -> dict[str, Any]:
    if "input" in event and isinstance(event["input"], dict):
        return event["input"]
    return event


def handler(event: dict[str, Any]) -> dict[str, Any]:
    started = time.time()
    job_input = normalize_input(event)
    client = start_comfyui()

    workflow_name = job_input.get("workflow", "upscale.example")
    output_prefix = job_input.get("output_prefix") or f"artely_upscale_{uuid.uuid4().hex[:10]}"
    input_filename = save_input_image(job_input, INPUT_DIR)

    workflow = load_workflow(WORKFLOW_DIR, workflow_name)
    placeholders = {
    "__INPUT_IMAGE__": input_filename,
    "__OUTPUT_PREFIX__": output_prefix,
}
    placeholders.update(job_input.get("placeholders") or {})

    if is_ui_workflow(workflow):
        workflow = ui_workflow_to_api_prompt(
            workflow,
            object_info=client.object_info(),
            input_image=input_filename,
        )

    prepared = prepare_workflow(
        workflow,
        placeholders=placeholders,
        node_overrides=job_input.get("node_overrides"),
    )

    prompt_id = client.queue_prompt(prepared)
    history = client.wait_for_prompt(prompt_id, timeout_seconds=int(job_input.get("timeout_seconds", 900)))
    output_paths = client.output_paths_from_history(history)

    if not output_paths:
        raise RuntimeError("ComfyUI finished but no output images were found.")

    return_base64 = bool(job_input.get("return_base64", False))
    upload_url = job_input.get("output_upload_url")
    upload_content_type = job_input.get("output_content_type")
    outputs = []

    for path in output_paths:
        output = read_output_file(path, return_base64=return_base64)
        if upload_url:
            output.update(upload_output(path, upload_url, upload_content_type))
        outputs.append(output)

    return {
        "ok": True,
        "workflow": workflow_name,
        "prompt_id": prompt_id,
        "duration_seconds": round(time.time() - started, 3),
        "outputs": outputs,
    }


runpod.serverless.start({"handler": handler})
