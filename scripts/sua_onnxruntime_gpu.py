"""Giữ InsightFace chạy GPU: gỡ onnxruntime bản CPU lẫn vào .venv của AIVoice.

faster-whisper, insightface, piper-tts, vieneu đều khai báo cần gói ``onnxruntime``
nên mỗi lần pip cài/cập nhật chúng, bản CPU lại được kéo về và GHI ĐÈ lên
``onnxruntime-gpu`` (hai gói dùng chung thư mục ``onnxruntime/``). Hậu quả:
InsightFace âm thầm chạy CPU, không báo lỗi gì.

Chạy bằng python của .venv AIVoice (setup.bat, CAP-NHAT.bat gọi sau khi pip xong).
Máy không có GPU NVIDIA thì bỏ qua. Luôn thoát 0 — lỗi ở đây không được làm
hỏng cả quá trình cài.
"""
import shutil
import subprocess
import sys
from importlib import metadata

DEFAULT_GPU_VERSION = "1.20.2"  # khớp AIVoice/requirements.txt


def _has_nvidia_gpu() -> bool:
    if not shutil.which("nvidia-smi"):
        return False
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return False
    return any(line.startswith("GPU ") for line in out.splitlines())


def _is_rtx50() -> bool:
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return False
    return "RTX 50" in out


def _cuda_provider_ok() -> bool:
    # Tiến trình con: module onnxruntime đã import thì không nạp lại được sau khi cài.
    code = "import onnxruntime as o, sys; sys.exit(0 if 'CUDAExecutionProvider' in o.get_available_providers() else 1)"
    return subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0


def _version(dist: str):
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def _pip(*args: str) -> int:
    return subprocess.run([sys.executable, "-m", "pip", *args]).returncode


def main() -> int:
    if not _has_nvidia_gpu():
        print("[INFO] Khong co GPU NVIDIA - bo qua kiem tra onnxruntime-gpu.")
        return 0
    if _cuda_provider_ok():
        print("[OK] onnxruntime-gpu dung CUDA - InsightFace chay GPU.")
        return 0

    gpu_ver = _version("onnxruntime-gpu")
    if _is_rtx50() and (gpu_ver is None or tuple(int(x) for x in gpu_ver.split(".")[:2]) < (1, 22)):
        spec = "onnxruntime-gpu>=1.22"  # Blackwell sm_120 can >= 1.22
    else:
        spec = f"onnxruntime-gpu=={gpu_ver or DEFAULT_GPU_VERSION}"

    print(f"[INFO] onnxruntime khong co CUDA (ban CPU {_version('onnxruntime') or '-'} ghi de) "
          f"- cai lai {spec}...")
    _pip("uninstall", "-y", "onnxruntime", "onnxruntime-gpu")
    # --no-deps: khong de pip keo lai chinh ban CPU vua go.
    if _pip("install", "--default-timeout=1000", "--no-deps", spec) != 0:
        print("[CANH BAO] Cai onnxruntime-gpu that bai - InsightFace se chay CPU.")
        return 0

    if _cuda_provider_ok():
        print("[OK] Da sua: InsightFace chay GPU.")
    else:
        print("[CANH BAO] Da cai lai nhung van chua thay CUDA - InsightFace se chay CPU.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
