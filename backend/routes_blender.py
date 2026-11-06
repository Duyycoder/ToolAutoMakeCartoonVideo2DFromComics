"""Routes chạy Blender ẩn: bo tròn cạnh, làm lưới đều, sửa lỗi in 3D, render Cycles, mở file .blend.

Chỉ nhận thao tác trong danh sách + tham số đã kiểm tra/giới hạn -> không bao giờ chạy code tuỳ ý trong Blender.
Dùng chung hàng đợi job (routes_jobs.runner) -> không chạy song song với AI (tranh VRAM).
"""
import json
import re

from fastapi import APIRouter, HTTPException, Request

from backend.blender_environment import BLENDER_OPS, SETUP_HINT, find_blender, get_blender_status
from backend.routes_jobs import runner

router = APIRouter(prefix="/api/blender")
MAX_BYTES = 200 * 1024 * 1024
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
# .blend: "BLENDER" (thường), zstd (Blender 3.0+ nén) hoặc gzip (bản cũ nén)
BLEND_MAGIC = (b"BLENDER", bytes.fromhex("28b52ffd"), bytes.fromhex("1f8b"))


def input_name_for(op: str, data: bytes) -> str:
    if op == "skin_weights":
        return "skin-input.bin"
    if op != "import_blend":
        return "input.glb"
    if not data.startswith(BLEND_MAGIC):
        raise HTTPException(400, "File không phải .blend của Blender")
    return "input.blend"

# Tham số số: (nhỏ nhất, lớn nhất, mặc định)
NUMBERS = {
    "bevel": {"amount": (0.01, 1, 0.3), "segments": (1, 8, 3)},
    "remesh": {"detail": (0, 1, 0.5)},
    "repair": {},
    "skin_weights": {},
    "import_blend": {},  # .blend -> GLB (Easy3D mở được)
    "render": {"width": (64, 4096, 1920), "height": (64, 4096, 1080), "samples": (8, 1024, 96), "fov": (10, 120, 45),
               "sun_intensity": (0, 20, 2), "ambient": (0, 5, 1), "exposure": (0.1, 4, 1)},
}


def _vec3(raw, default):
    try:
        v = [float(x) for x in raw]
        return v if len(v) == 3 and all(abs(x) < 1e5 for x in v) else default
    except (TypeError, ValueError):
        return default


def clean_params(op: str, raw: dict) -> dict:
    out = {}
    for key, (lo, hi, default) in NUMBERS[op].items():
        try:
            out[key] = min(hi, max(lo, float(raw.get(key, default))))
        except (TypeError, ValueError):
            out[key] = default
    if op == "render":
        for key in ("width", "height", "samples"):
            out[key] = int(out[key])
        out["transparent"] = bool(raw.get("transparent", False))
        out["camera_position"] = _vec3(raw.get("camera_position"), [3.5, 2.6, 4.5])
        out["camera_target"] = _vec3(raw.get("camera_target"), [0, 0.5, 0])
        out["sun_position"] = _vec3(raw.get("sun_position"), [5, 8, 4])
        out["sun_shadows"] = bool(raw.get("sun_shadows", True))
        for key, default in (("background", "#1c1e24"), ("sun_color", "#ffffff"), ("sky", "#ffffff")):
            value = str(raw.get(key, default))
            out[key] = value if HEX.match(value) else default
    return out


@router.get("/status")
def blender_status():
    return get_blender_status()


@router.post("/{op}")
async def run_blender_op(op: str, request: Request, params: str = "{}"):
    if op not in NUMBERS:
        raise HTTPException(404, "Thao tác Blender không có")
    exe = find_blender()
    if exe is None:
        raise HTTPException(409, SETUP_HINT)
    try:
        clean = clean_params(op, json.loads(params))
    except (json.JSONDecodeError, AttributeError) as exc:
        raise HTTPException(400, "Tham số không hợp lệ") from exc
    data = await request.body()
    if not data:
        raise HTTPException(400, "Không có mô hình")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Mô hình quá lớn (tối đa 200 MB)")

    input_name = input_name_for(op, data)

    def command(work_dir, input_path):
        # --disable-autoexec: file .blend có thể nhúng script Python -> không bao giờ tự chạy
        return [exe, "--background", "--factory-startup", "--disable-autoexec", "--python", BLENDER_OPS, "--",
                "--op", op, "--in", input_path, "--out-dir", work_dir, "--params", json.dumps(clean)]

    return runner.submit_command(command, data, input_name).public()
