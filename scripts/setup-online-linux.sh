#!/usr/bin/env bash
# Cài Easy3D bản online trên Ubuntu KHÔNG cần sudo: .venv (FastAPI) + Blender 5.2.3 Linux
# + thư viện X11/GL mà Blender cần (tải .deb, giải nén vào tools/blender/syslibs).
# Không cài AI (TripoSR). Chạy: bash scripts/setup-online-linux.sh  -> rồi scripts/run-online-linux.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
    python3 -m venv --without-pip .venv   # Ubuntu thiếu python3-venv (ensurepip) mà không có sudo
    curl -sSfL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    .venv/bin/python /tmp/get-pip.py -q
fi
.venv/bin/pip install -q "fastapi>=0.115" "uvicorn>=0.30"

BL_VER=5.2.3
BL_DIR="tools/blender/blender-$BL_VER-linux-x64"
if [ ! -x "$BL_DIR/blender" ]; then
    mkdir -p tools/blender && cd tools/blender
    file="blender-$BL_VER-linux-x64.tar.xz"
    base="https://download.blender.org/release/Blender${BL_VER%.*}"
    curl -sSfL "$base/blender-$BL_VER.sha256" -o sums.txt
    curl -sSfL "$base/$file" -o "$file"
    grep " $file\$" sums.txt | sha256sum -c -
    tar -xf "$file" && rm "$file" sums.txt
    cd ../..
fi

LIBS=tools/blender/syslibs
if [ ! -d "$LIBS/root" ]; then
    mkdir -p "$LIBS/debs"
    (cd "$LIBS/debs" && apt-get download libxrender1 libxfixes3 libxi6 libsm6 libice6 \
        libgl1 libglx0 libglvnd0 libglx-mesa0 libxkbcommon0 libxxf86vm1 libegl1)
    for deb in "$LIBS"/debs/*.deb; do dpkg -x "$deb" "$LIBS/root"; done
fi
echo "Xong. Chạy: scripts/run-online-linux.sh"
