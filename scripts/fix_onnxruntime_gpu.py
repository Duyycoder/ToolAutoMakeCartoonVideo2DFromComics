"""Giữ rembg chạy GPU: đổi onnxruntime bản CPU sang onnxruntime-gpu trong .venv-ai.

rembg khai báo cần `onnxruntime` nên mỗi lần pip cài/cập nhật, bản CPU lại GHI ĐÈ
`onnxruntime-gpu` (chung thư mục `onnxruntime/`) và rembg âm thầm chạy CPU.
Logic lấy từ AutoCartoon scripts/sua_onnxruntime_gpu.py. Luôn thoát 0 — lỗi ở đây
không được làm hỏng cả quá trình cài (rembg chạy CPU vẫn dùng được, chỉ chậm hơn).
"""
import subprocess
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.gpu_info import query_nvidia_gpus  # noqa: E402

DEFAULT_GPU_VERSION = "1.20.2"  # cần cuDNN 9 — có sẵn trong torch 2.4.1+cu121


def _cuda_provider_ok() -> bool:
    # Tiến trình con: onnxruntime đã import thì không nạp lại được sau khi cài.
    code = ("import onnxruntime as o, sys; "
            "sys.exit(0 if 'CUDAExecutionProvider' in o.get_available_providers() else 1)")
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


def _version(dist: str):
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def _pip(*args: str) -> int:
    return subprocess.run([sys.executable, "-m", "pip", *args]).returncode


def main() -> int:
    gpus = query_nvidia_gpus()
    if not gpus:
        print("[INFO] Khong co GPU NVIDIA - rembg chay CPU, bo qua onnxruntime-gpu.")
        return 0
    if _cuda_provider_ok():
        print("[OK] onnxruntime-gpu dung CUDA.")
        return 0

    is_rtx50 = any("RTX 50" in g["name"] for g in gpus)
    spec = "onnxruntime-gpu>=1.22" if is_rtx50 else \
        f"onnxruntime-gpu=={_version('onnxruntime-gpu') or DEFAULT_GPU_VERSION}"
    print(f"[INFO] onnxruntime chua co CUDA - cai {spec}...")
    _pip("uninstall", "-y", "onnxruntime", "onnxruntime-gpu")
    # --no-deps: không để pip kéo lại chính bản CPU vừa gỡ.
    if _pip("install", "--default-timeout=1000", "--no-deps", spec) != 0:
        print("[CANH BAO] Cai onnxruntime-gpu that bai - rembg se chay CPU.")
        return 0
    print("[OK] Da sua: rembg chay GPU." if _cuda_provider_ok()
          else "[CANH BAO] Da cai lai nhung chua thay CUDA - rembg se chay CPU.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
