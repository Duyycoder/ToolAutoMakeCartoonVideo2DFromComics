"""Worker giả cho test JobRunner — in đúng giao thức JSON của workers/worker_image_to_3d.py.

Hành vi theo biến môi trường FAKE_MODE:
  ok     : thành công; riêng chunk_size 2048 (mức "detailed") báo CUDA_OOM để test retry
  crash  : thoát mã 3 không kịp in done/error
  error  : báo lỗi thường (không retry)
  slow   : ngủ lâu để test huỷ
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path


def emit(**payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--image")
    p.add_argument("--out-dir")
    p.add_argument("--chunk-size", type=int)
    p.add_argument("--mc-resolution", type=int)
    p.add_argument("--steps", type=int)  # preset Hunyuan
    args, _ = p.parse_known_args()
    mode = os.environ.get("FAKE_MODE", "ok")
    emit(type="progress", pct=10, msg="Đang tách nền ảnh...")
    if mode == "crash":
        return 3
    if mode == "slow":
        time.sleep(30)
    if mode == "error":
        emit(type="error", code="ValueError", msg="ảnh hỏng")
        return 1
    if args.chunk_size == 2048:
        emit(type="error", code="CUDA_OOM", msg="CUDA out of memory")
        return 1
    (Path(args.out_dir) / "mesh.glb").write_bytes(b"glTF-fake")
    emit(type="done", stats={"tris": 123, "mc_resolution": args.mc_resolution, "steps": args.steps})
    return 0


if __name__ == "__main__":
    sys.exit(main())
