#!/usr/bin/env bash
# Chạy Easy3D bản online: chỉ nghe 127.0.0.1:8200, Cloudflare Tunnel đưa ra tên miền công khai.
# Tên miền: EASY3D_ALLOWED_HOSTS (mặc định bên dưới). Bản online xuất file sẽ tải về máy người dùng.
cd "$(dirname "$0")/.."
export LD_LIBRARY_PATH="$PWD/tools/blender/syslibs/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export EASY3D_ALLOWED_HOSTS="${EASY3D_ALLOWED_HOSTS:-easy3dtool.ririmimivn.id.vn}"
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8200
