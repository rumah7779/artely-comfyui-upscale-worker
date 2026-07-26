import json
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import requests
import websocket


class ComfyClient:
    def __init__(self, host: str, port: int, output_dir: str):
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/ws"
        self.output_dir = output_dir
        self.client_id = str(uuid.uuid4())

    def wait_until_ready(self, timeout_seconds: int) -> None:
        deadline = time.time() + timeout_seconds
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                response = requests.get(f"{self.base_url}/system_stats", timeout=3)
                if response.status_code == 200:
                    return
            except Exception as exc:
                last_error = exc
            time.sleep(1)
        raise TimeoutError(f"ComfyUI did not become ready: {last_error}")

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        response = requests.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": self.client_id},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["prompt_id"]

    def object_info(self) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/object_info", timeout=60)
        response.raise_for_status()
        return response.json()

    def wait_for_prompt(self, prompt_id: str, timeout_seconds: int = 900) -> dict[str, Any]:
        socket = websocket.WebSocket()
        socket.connect(f"{self.ws_url}?clientId={urllib.parse.quote(self.client_id)}")
        deadline = time.time() + timeout_seconds
        try:
            while time.time() < deadline:
                message = socket.recv()
                if isinstance(message, bytes):
                    continue
                payload = json.loads(message)
                if payload.get("type") == "executing":
                    data = payload.get("data", {})
                    if data.get("node") is None and data.get("prompt_id") == prompt_id:
                        return self.history(prompt_id)
        finally:
            socket.close()
        raise TimeoutError(f"Timed out waiting for ComfyUI prompt: {prompt_id}")

    def history(self, prompt_id: str) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=30)
        response.raise_for_status()
        return response.json()[prompt_id]

    def output_paths_from_history(self, history: dict[str, Any]) -> list[str]:
        paths: list[str] = []
        outputs = history.get("outputs", {})
        for node_output in outputs.values():
            for image in node_output.get("images", []):
                filename = image.get("filename")
                subfolder = image.get("subfolder") or ""
                if filename:
                    path = Path(self.output_dir) / subfolder / filename
                    if path.exists():
                        paths.append(str(path))
        return paths
