#!/usr/bin/env bash
# Cài AI tạo 3D từ ảnh (TripoSR, chạy CPU) cho bản online trên Ubuntu, KHÔNG cần sudo.
# Python hệ thống có thể quá mới cho torch 2.4.1 / transformers 4.35 -> dùng uv tải Python 3.11 riêng.
# Chạy SAU scripts/setup-online-linux.sh, rồi khởi động lại scripts/run-online-linux.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

UV="$HOME/.local/bin/uv"
if [ ! -x "$UV" ]; then
    mkdir -p "$HOME/.local/bin"
    curl -sSfL https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz \
        | tar -xz -C "$HOME/.local/bin" --strip-components=1
fi

[ -x .venv-ai/bin/python ] || "$UV" venv --python 3.11 .venv-ai
export VIRTUAL_ENV="$PWD/.venv-ai"
"$UV" pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu
[ -d third_party/TripoSR/tsr ] || git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git third_party/TripoSR
"$UV" pip install -r workers/requirements-ai.txt

echo "Tải trọng số TripoSR (~1.7 GB) vào models/hf..."
HF_HOME="$PWD/models/hf" .venv-ai/bin/python -c \
    "from huggingface_hub import hf_hub_download as d; d('stabilityai/TripoSR','config.yaml'); d('stabilityai/TripoSR','model.ckpt')"
echo "Xong. Khởi động lại scripts/run-online-linux.sh"
