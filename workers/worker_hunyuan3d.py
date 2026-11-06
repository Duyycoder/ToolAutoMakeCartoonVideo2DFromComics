"""Worker ảnh -> 3D chất lượng cao: Hunyuan3D-2mini (chỉ tạo HÌNH) + tô màu bằng cách chiếu ảnh gốc.

Chạy bằng .venv-hunyuan (KHÔNG phải .venv-ai — xung đột phiên bản transformers với TripoSR).
Chậm hơn TripoSR nhiều (vài phút) nhưng hình chi tiết hơn rõ rệt. Trên 6 GB: fp16, num_chunks nhỏ.
Trọng số: models/hy3dgen/tencent/Hunyuan3D-2mini/hunyuan3d-dit-v2-mini (scripts/setup-hunyuan3d.bat tải sẵn).

  .venv-hunyuan\\Scripts\\python.exe workers\\worker_hunyuan3d.py --image a.png --out-dir output\\job1
"""
import argparse
import gc
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HY3DGEN_MODELS", str(ROOT / "models" / "hy3dgen"))  # hy3dgen tìm model ở đây trước
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))
os.environ.setdefault("U2NET_HOME", str(ROOT / "models" / "u2net"))
sys.path.insert(0, str(ROOT / "third_party" / "Hunyuan3D-2"))
sys.path.insert(0, str(ROOT / "workers"))

from worker_protocol import emit, run_worker  # noqa: E402

MODEL_ID = "tencent/Hunyuan3D-2mini"
SUBFOLDER = "hunyuan3d-dit-v2-mini"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--octree-resolution", type=int, default=256)
    p.add_argument("--num-chunks", type=int, default=8000)
    p.add_argument("--max-faces", type=int, default=80000)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--device", default="auto", help="auto | cuda | cpu")
    return p.parse_args()


def load_rgba(path: str):
    """Ảnh có nền trong suốt sẵn thì giữ; không thì tách nền (rembg) rồi nhả bộ nhớ ngay."""
    from PIL import Image
    image = Image.open(path).convert("RGBA")
    if image.getextrema()[3][0] < 255:
        return image
    from hy3dgen.rembg import BackgroundRemover
    remover = BackgroundRemover()
    image = remover(image.convert("RGB"))
    del remover
    gc.collect()
    return image


def run(args) -> dict:
    import torch
    from hy3dgen.shapegen import DegenerateFaceRemover, FaceReducer, FloaterRemover, Hunyuan3DDiTFlowMatchingPipeline
    from mesh_image_projection import orient_and_colorize

    use_cuda = torch.cuda.is_available() and args.device != "cpu"
    device = "cuda" if use_cuda else "cpu"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    emit(type="progress", pct=5, msg="Đang tách nền ảnh...")
    image = load_rgba(args.image)
    image.save(out_dir / "input_processed.png")

    emit(type="progress", pct=15, msg="Đang nạp model Hunyuan3D (lần đầu khá lâu)...")
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        MODEL_ID, subfolder=SUBFOLDER, variant="fp16", use_safetensors=True,
        device=device, dtype=torch.float16 if use_cuda else torch.float32,  # CPU không chạy tốt fp16
    )
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()

    t0 = time.perf_counter()
    emit(type="progress", pct=30, msg=f"AI đang dựng hình chi tiết ({args.steps} bước, {'GPU' if use_cuda else 'CPU - rất chậm'})...")
    mesh = pipeline(
        image=image, num_inference_steps=args.steps, octree_resolution=args.octree_resolution,
        num_chunks=args.num_chunks, generator=torch.manual_seed(args.seed), output_type="trimesh",
    )[0]
    peak = round(torch.cuda.max_memory_allocated() / 2**20) if use_cuda else None
    del pipeline  # nhả VRAM trước bước hậu xử lý (chạy CPU)
    gc.collect()
    if use_cuda:
        torch.cuda.empty_cache()

    emit(type="progress", pct=80, msg="Đang dọn lưới (bỏ mảnh vụn, giảm số mặt)...")
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    mesh = FaceReducer()(mesh, max_facenum=args.max_faces)

    emit(type="progress", pct=90, msg="Đang tô màu theo ảnh gốc...")
    orientation = orient_and_colorize(mesh, image)
    mesh.export(out_dir / "mesh.glb")
    return {
        "model": "hunyuan3d-2mini", "device": device, "seconds": round(time.perf_counter() - t0, 1),
        "peak_vram_mb": peak, "tris": int(len(mesh.faces)), "steps": args.steps,
        "octree_resolution": args.octree_resolution, **orientation, "output": str(out_dir / "mesh.glb"),
    }


if __name__ == "__main__":
    sys.exit(run_worker(run, parse_args()))
