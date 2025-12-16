# GPU-enabled Dockerfile for TRELLIS
# Base image provides CUDA 11.8 + cuDNN on Ubuntu 22.04. Adjust tag for your GPU/CUDA version.
FROM pytorch/pytorch:2.4.0-cuda11.8-cudnn9-devel

WORKDIR /app


RUN apt update && apt install git sudo curl wget python3-venv python3-pip libgl1 -y

# Install FreeCAD so the container can perform STL -> STEP conversions headlessly.
# This is intentionally done via apt (no conda) per project constraints.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y freecad && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install build tools separately (kept separate so the original command above stays unchanged)
RUN apt update && apt install -y build-essential cmake ninja-build pkg-config libjpeg-dev libpng-dev

RUN git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git

RUN bash TRELLIS/setup.sh --basic --xformers --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast --demo

RUN pip install kaolin -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.4.0_cu121.html
RUN pip install xformers==0.0.27.post2 --index-url https://download.pytorch.org/whl/cu118
RUN pip install spconv-cu118
RUN pip install gradio==4.44.1 gradio_litmodel3d==0.0.1

RUN mkdir -p /tmp/extensions
RUN git clone https://github.com/NVlabs/nvdiffrast.git /tmp/extensions/nvdiffrast
RUN pip install /tmp/extensions/nvdiffrast

# Ensure mip-splatting's diff-gaussian-rasterization is installed (used by TRELLIS renderers)
RUN mkdir -p /tmp/extensions
RUN git clone https://github.com/autonomousvision/mip-splatting.git /tmp/extensions/mip-splatting
# Set CUDA arch list to avoid build-time GPU detection failure during docker build
ENV TORCH_CUDA_ARCH_LIST="8.6;8.0;7.5"
RUN pip install /tmp/extensions/mip-splatting/submodules/diff-gaussian-rasterization/



ENV  ATTN_BACKEND=xformers

EXPOSE 7860

CMD ["python", "app_combined.py"]