import copy
import json
from pathlib import Path
from typing import Any


def workflow_path(workflow_dir: str, workflow_name: str) -> Path:
    safe_name = workflow_name.replace("\\", "/").split("/")[-1]
    if safe_name.endswith(".json"):
        filename = safe_name
    elif (Path(workflow_dir) / f"{safe_name}.ui.json").exists():
        filename = f"{safe_name}.ui.json"
    else:
        filename = f"{safe_name}.json"
    return Path(workflow_dir) / filename


def load_workflow(workflow_dir: str, workflow_name: str) -> dict[str, Any]:
    path = workflow_path(workflow_dir, workflow_name)
    if not path.exists():
        raise FileNotFoundError(f"Workflow not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def replace_placeholders(value: Any, placeholders: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return placeholders.get(value, value)
    if isinstance(value, list):
        return [replace_placeholders(item, placeholders) for item in value]
    if isinstance(value, dict):
        return {key: replace_placeholders(item, placeholders) for key, item in value.items()}
    return value


def is_ui_workflow(workflow: dict[str, Any]) -> bool:
    return isinstance(workflow.get("nodes"), list) and isinstance(workflow.get("links"), list)


def _input_order_from_object_info(node_info: dict[str, Any]) -> list[str]:
    inputs = node_info.get("input", {})
    ordered: list[str] = []
    for group in ("required", "optional"):
        group_inputs = inputs.get(group) or {}
        ordered.extend(group_inputs.keys())
    return ordered


def _link_map(ui_workflow: dict[str, Any]) -> dict[int, list[Any]]:
    links: dict[int, list[Any]] = {}
    for link in ui_workflow.get("links", []):
        if isinstance(link, list) and link:
            links[int(link[0])] = link
    return links


def _patch_load_image_widgets(ui_workflow: dict[str, Any], input_image: str) -> dict[str, Any]:
    patched = copy.deepcopy(ui_workflow)
    for node in patched.get("nodes", []):
        if node.get("type") == "LoadImage":
            widgets = list(node.get("widgets_values") or [])
            if widgets:
                widgets[0] = input_image
            else:
                widgets = [input_image]
            node["widgets_values"] = widgets
    return patched


def ui_workflow_to_api_prompt(
    ui_workflow: dict[str, Any],
    object_info: dict[str, Any],
    input_image: str | None = None,
) -> dict[str, Any]:
    workflow = _patch_load_image_widgets(ui_workflow, input_image) if input_image else copy.deepcopy(ui_workflow)
    links = _link_map(workflow)
    prompt: dict[str, Any] = {}

    for node in workflow.get("nodes", []):
        node_id = str(node.get("id"))
        class_type = node.get("type")
        if not node_id or not class_type:
            continue

        node_info = object_info.get(class_type)
        if not node_info:
            raise ValueError(f"ComfyUI node type is missing or custom node is not installed: {class_type}")

        input_names = _input_order_from_object_info(node_info)
        api_inputs: dict[str, Any] = {}
        linked_inputs: set[str] = set()

        for input_spec in node.get("inputs") or []:
            link_id = input_spec.get("link")
            input_name = input_spec.get("name")
            if link_id is None or not input_name:
                continue
            link = links.get(int(link_id))
            if not link or len(link) < 4:
                continue
            api_inputs[input_name] = [str(link[1]), int(link[2])]
            linked_inputs.add(input_name)

        widget_values = list(node.get("widgets_values") or [])
        widget_index = 0
        for input_name in input_names:
            if input_name in linked_inputs or input_name in api_inputs:
                continue
            if widget_index >= len(widget_values):
                continue
            value = widget_values[widget_index]
            widget_index += 1
            if isinstance(value, dict) or isinstance(value, list):
                continue
            api_inputs[input_name] = value

        prompt[node_id] = {
            "class_type": class_type,
            "inputs": api_inputs,
        }

    return prompt


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def apply_node_overrides(workflow: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    if not overrides:
        return workflow
    patched = copy.deepcopy(workflow)
    for node_id, patch in overrides.items():
        if node_id not in patched:
            raise ValueError(f"Cannot override missing workflow node: {node_id}")
        patched[node_id] = deep_merge(patched[node_id], patch)
    return patched


def prepare_workflow(
    workflow: dict[str, Any],
    placeholders: dict[str, Any],
    node_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    patched = apply_node_overrides(workflow, node_overrides)
    return replace_placeholders(patched, placeholders)
