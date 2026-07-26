#!/usr/bin/env bash
set -euo pipefail

CUSTOM_NODES_DIR="${COMFYUI_DIR:-/workspace/ComfyUI}/custom_nodes"
LIST_FILE="/workspace/custom_nodes.txt"

mkdir -p "$CUSTOM_NODES_DIR"

if [ ! -f "$LIST_FILE" ]; then
  echo "No custom_nodes.txt found, skipping custom nodes."
  exit 0
fi

while IFS= read -r repo_url; do
  repo_url="$(echo "$repo_url" | xargs)"
  if [ -z "$repo_url" ] || [[ "$repo_url" == \#* ]]; then
    continue
  fi

  repo_name="$(basename "$repo_url" .git)"
  target="$CUSTOM_NODES_DIR/$repo_name"

  if [ -d "$target/.git" ]; then
    echo "Custom node already installed: $repo_name"
  else
    echo "Installing custom node: $repo_url"
    git clone --depth 1 "$repo_url" "$target"
  fi

  if [ -f "$target/requirements.txt" ]; then
    pip3 install --no-cache-dir -r "$target/requirements.txt"
  fi
done < "$LIST_FILE"

