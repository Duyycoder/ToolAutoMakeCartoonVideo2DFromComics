"""Spike Phase 01: chạy TripoSR 1 ảnh với 1 cấu hình, đo peak VRAM + thời gian.

Chạy bằng .venv-ai. Mỗi cấu hình 1 tiến trình riêng -> đo VRAM sạch, OOM không ảnh hưởng lần sau.
Giao thức stdout (dòng JSON): progress / done / error — giống worker AutoCartoon.

  .venv-ai\\Scripts\\python.exe workers\\spike_triposr_single_run.py --image a.png --out-dir output\\spike
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))  # weights nằm trong repo, đã .gitignore
os.environ.setdefault("U2NET_HOME", str(ROOT / "models" / "u2net"))  # model tách nền của rembg
sys.path.insert(0, str(ROOT / "third_party" / "TripoSR"))
sys.path.insert(0, str(ROOT / "workers"))


def emit(**payload):
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--image", default=str(ROOT / "third_party" / "TripoSR" / "examples" / "chair.png"))
    p.add_argument("--out-dir", default=str(ROOT / "output" / "spike"))
    p.add_argument("--chunk-size", type=int, default=8192)
    p.add_argument("--mc-resolution", type=int, default=256)
    p.add_argument("--foreground-ratio", type=float, default=0.85)
    p.add_argument("--device", default="auto", help="auto | cuda:0 | cpu")
    p.add_argument("--bake-texture", action="store_true")
    p.add_argument("--texture-resolution", type=int, default=1024)
    return p.parse_args()


def preprocess(image_path: str, foreground_ratio: float):
    import numpy as np
    import rembg
    from PIL import Image
    from tsr.utils import remove_background, resize_foreground

    image = remove_background(Image.open(image_path), rembg.new_session())
    image = resize_foreground(image, foreground_ratio)
    arr = np.array(image).astype(np.float32) / 255.0
    arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5  # nền xám như TripoSR gốc
    return Image.fromarray((arr * 255.0).astype(np.uint8))


def export_baked(mesh, model, scene_code, out_dir: Path, tex_res: int) -> str:
    import numpy as np
    import xatlas
    from PIL import Image
    from tsr.bake_texture import bake_texture

    bake = bake_texture(mesh, model, scene_code, tex_res)
    out_mesh = out_dir / "mesh_textured.obj"
    xatlas.export(str(out_mesh), mesh.vertices[bake["vmapping"]], bake["indices"],
                  bake["uvs"], mesh.vertex_normals[bake["vmapping"]])
    Image.fromarray((bake["colors"] * 255.0).astype(np.uint8)).transpose(
        Image.FLIP_TOP_BOTTOM).save(out_dir / "texture.png")
    return str(out_mesh)


def run(args) -> dict:
    from marching_cubes_fallback import install_if_missing
    mc_backend = install_if_missing()

    import torch
    from tsr.system import TSR

    device = args.device
    if device == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    use_cuda = device.startswith("cuda")
    out_dir = Path(args.out_dir) / f"c{args.chunk_size}_r{args.mc_resolution}"
    out_dir.mkdir(parents=True, exist_ok=True)

    emit(type="progress", pct=5, msg=f"Tach nen anh (device={device}, mc={mc_backend})")
    image = preprocess(args.image, args.foreground_ratio)
    image.save(out_dir / "input_processed.png")

    emit(type="progress", pct=20, msg="Nap model TripoSR")
    model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
    model.renderer.set_chunk_size(args.chunk_size)
    model.to(device)
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()

    t0 = time.perf_counter()
    emit(type="progress", pct=50, msg="Suy luan TripoSR")
    with torch.no_grad():
        scene_codes = model([image], device=device)
    emit(type="progress", pct=75, msg="Tao luoi (marching cubes)")
    mesh = model.extract_mesh(scene_codes, has_vertex_color=True, resolution=args.mc_resolution)[0]
    if mesh.is_watertight and mesh.volume < 0:
        mesh.invert()  # sửa mặt bị lật do đảo trục ở marching_cubes_fallback
    mesh.export(out_dir / "mesh.glb")
    infer_seconds = time.perf_counter() - t0

    textured = None
    if args.bake_texture:
        emit(type="progress", pct=90, msg="Bake texture")
        textured = export_baked(mesh, model, scene_codes[0], out_dir, args.texture_resolution)

    return {
        "device": device,
        "mc_backend": mc_backend,
        "chunk_size": args.chunk_size,
        "mc_resolution": args.mc_resolution,
        "seconds": round(infer_seconds, 2),
        "peak_vram_mb": round(torch.cuda.max_memory_allocated() / 2**20) if use_cuda else None,
        "tris": int(len(mesh.faces)),
        "output": str(out_dir / "mesh.glb"),
        "textured_output": textured,
    }


def main() -> int:
    args = parse_args()
    try:
        emit(type="done", stats=run(args))
        return 0
    except Exception as exc:  # báo mọi lỗi theo giao thức JSON để runner phân loại
        code = "CUDA_OOM" if "out of memory" in str(exc).lower() else type(exc).__name__
        emit(type="error", code=code, msg=str(exc)[:500])
        return 1


if __name__ == "__main__":
    sys.exit(main())
