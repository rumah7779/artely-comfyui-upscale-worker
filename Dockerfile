FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_DIR=/workspace/ComfyUI
ENV WORKFLOW_DIR=/workspace/workflows
ENV INPUT_DIR=/workspace/ComfyUI/input
ENV OUTPUT_DIR=/workspace/ComfyUI/output

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    ffmpeg \
  && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /workspace/ComfyUI

WORKDIR /workspace/ComfyUI
RUN pip3 install --no-cache-dir --upgrade pip \
  && pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 \
  && pip3 install --no-cache-dir -r requirements.txt

WORKDIR /workspace
COPY requirements.txt /workspace/requirements.txt
RUN pip3 install --no-cache-dir -r /workspace/requirements.txt

COPY custom_nodes.txt /workspace/custom_nodes.txt
COPY scripts /workspace/scripts
RUN chmod +x /workspace/scripts/*.sh \
  && /workspace/scripts/install_custom_nodes.sh

COPY handler.py /workspace/handler.py
COPY src /workspace/src
COPY workflows /workspace/workflows
COPY models.json /workspace/models.json

EXPOSE 8188

CMD ["python3", "-u", "/workspace/handler.py"]

