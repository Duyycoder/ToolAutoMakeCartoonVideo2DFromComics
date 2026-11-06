"""Thông tin GPU cho backend — KHÔNG import torch (backend phải nhẹ, không giữ VRAM).

`gpus` liệt kê card NVIDIA theo đúng chỉ số CUDA (cuda:N). Chỉ số này KHÁC số
"GPU 0/1" trong Task Manager (Task Manager đếm cả card tích hợp/ảo).
Máy không có NVIDIA -> fallback WMI chỉ để hiển thị tên card, AI sẽ chạy CPU.
"""
import os
import shutil
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_NVSMI_CANDIDATES = (
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
)


def find_nvidia_smi() -> str | None:
    """nvidia-smi không phải lúc nào cũng nằm trong PATH -> thử cả vị trí cài mặc định."""
    found = shutil.which("nvidia-smi")
    if found:
        return found
    return next((p for p in _NVSMI_CANDIDATES if os.path.exists(p)), None)


def parse_nvidia_smi_csv(stdout: str) -> list[dict]:
    """Parse output `--query-gpu=index,name,memory.total,memory.used --format=csv,noheader,nounits`."""
    gpus = []
    for line in stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 4 and parts[0].isdigit():
            gpus.append({
                "index": int(parts[0]),
                "name": parts[1],
                "vram_total_mb": int(parts[2]) if parts[2].isdigit() else None,
                "vram_used_mb": int(parts[3]) if parts[3].isdigit() else None,
            })
    return gpus


def query_nvidia_gpus() -> list[dict]:
    exe = find_nvidia_smi()
    if not exe:
        return []
    try:
        result = subprocess.run(
            [exe, "--query-gpu=index,name,memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_nvidia_smi_csv(result.stdout) if result.returncode == 0 else []


def query_wmi_gpu_names() -> list[str]:
    """Tên mọi card hình (kể cả AMD/Intel) — chỉ để hiển thị."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_VideoController).Name"],
            capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [n.strip() for n in result.stdout.splitlines() if n.strip()]


def get_gpu_info() -> dict:
    gpus = query_nvidia_gpus()
    if gpus:
        return {"cuda_available": True, "gpus": gpus, "other_adapters": []}
    return {"cuda_available": False, "gpus": [], "other_adapters": query_wmi_gpu_names()}
