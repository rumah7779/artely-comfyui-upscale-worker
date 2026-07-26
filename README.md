# Artely ComfyUI Upscale Worker

RunPod Serverless worker for Artely.ai ComfyUI upscale workflows.

Artely should call this worker only from Convex. The frontend should never receive
the RunPod API key or call this endpoint directly.

## Flow

1. User starts upscale in Artely.
2. Convex validates auth, credits, and file ownership.
3. Convex sends the source image URL and workflow options to RunPod.
4. RunPod runs ComfyUI.
5. The worker returns output metadata and can upload the result to a signed URL.

## Repo Layout

- `handler.py` - RunPod serverless entrypoint.
- `src/comfy_client.py` - ComfyUI API client.
- `src/files.py` - Input download/base64 and output upload helpers.
- `src/workflow.py` - Workflow loading, placeholder replacement, and node overrides.
- `workflows/upscale.example.json` - Placeholder API workflow.
- `workflows/seedvr2-4k-upscale.ui.json` - Artely 4K SeedVR2 upscale workflow.
- `workflows/seedvr2-8k-upscale.ui.json` - Artely 8K SeedVR2 upscale workflow.
- `models.json` - Model manifest placeholder.
- `custom_nodes.txt` - Custom node git URLs, one per line.
- `scripts/download_models.sh` - Optional model downloader.
- `scripts/install_custom_nodes.sh` - Custom node installer.
- `Dockerfile` - Container image for RunPod.

## Worker Input

```json
{
  "workflow": "upscale.example",
  "image_url": "https://signed-or-public-image-url.png",
  "image_base64": null,
  "return_base64": false,
  "output_upload_url": "https://signed-upload-url",
  "output_content_type": "image/png",
  "placeholders": {
    "__UPSCALE_MODEL__": "RealESRGAN_x4plus.pth"
  },
  "node_overrides": {
    "1": {
      "inputs": {
        "image": "__INPUT_IMAGE__"
      }
    }
  }
}
```

Use either `image_url` or `image_base64`. `output_upload_url` is optional, but it
is the best production path because Convex can generate a signed storage URL and
the worker does not need Google Cloud credentials.

## Add The Real Upscale Workflow

Export the ComfyUI workflow in **API format** and put it in `workflows/`, for example:

```text
workflows/artely-upscale-v1.json
```

Then call:

```json
{ "workflow": "artely-upscale-v1", "image_url": "..." }
```

The workflow can use placeholders like `__INPUT_IMAGE__`, `__OUTPUT_PREFIX__`,
and `__UPSCALE_MODEL__`. You can also patch specific node inputs with
`node_overrides`.

This worker also supports `.ui.json` visual workflows. For UI workflows it asks
the running ComfyUI server for `/object_info` and converts widget values and
links into API prompt format at runtime. The uploaded image is automatically
patched into every `LoadImage` node.

Current Artely workflows:

```json
{ "workflow": "seedvr2-4k-upscale", "image_url": "..." }
{ "workflow": "seedvr2-8k-upscale", "image_url": "..." }
```

## Current Workflow Requirements

Custom nodes:

- `ComfyUI-SeedVR2_VideoUpscaler`
- `ComfyUI-Easy-Use`
- `comfyui-vrgamedevgirl`
- `rgthree-comfy`

Model files referenced by your workflows:

- `ema_vae_fp16.safetensors`
- `seedvr2_ema_7b-Q4_K_M.gguf`

Production note: SeedVR2 can auto-download models on first use, but for RunPod
serverless it is better to pre-cache the models on a RunPod network volume so
cold starts do not become painfully slow.

## Secrets

Do not commit API keys, RunPod keys, or storage credentials. Put those in Convex
environment variables and RunPod endpoint settings.

## Next Things I Need From You

Send, if anything changes:

1. Your real ComfyUI upscale workflow JSON.
2. The model file names it needs.
3. Any custom node GitHub URLs it uses.
