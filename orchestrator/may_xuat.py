"""MÁY XUẤT từ xa (chạy trên laptop có GPU NVIDIA) — editor ở máy khác gửi việc xuất qua Tailscale.

Máy chính dựng sẵn lệnh ffmpeg (render.py) rồi gửi sang đây kèm loc.txt/sub.ass/LUT; file media gốc
được gửi MỘT lần và giữ trong cache theo khoá nội dung, lần xuất sau chỉ gửi timeline.
Xuất xong máy chính tải file .mp4 về. Phía máy chính: orchestrator/editor/xuat_tu_xa.py.

Bảo mật: mọi yêu cầu cần token (Authorization: Bearer …), token sinh ngẫu nhiên lần đầu ở
configs/may_xuat_token.txt (không commit). Server chỉ nghe trên IP Tailscale (100.64.0.0/10) nếu có.
Lệnh ffmpeg chỉ được đọc file trong cache (@tep:<khoá>) và ghi ra file kết quả (@ra) — không đường dẫn tự do.

Chạy trên laptop: run-worker.bat   (hoặc: python -m orchestrator.may_xuat)
"""
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

GOC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONG = int(os.environ.get("MAY_XUAT_PORT", "8300"))
THU_MUC = os.environ.get("MAY_XUAT_DIR") or os.path.join(GOC, "storage", "may_xuat")
FILE_TOKEN = os.path.join(GOC, "configs", "may_xuat_token.txt")
KHOA_TEP = re.compile(r"^[0-9a-f]{40}\.[a-z0-9]{1,5}$")
TEN_PHU = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
GIU_CACHE = 14 * 24 * 3600


def token() -> str:
    try:
        with open(FILE_TOKEN, encoding="utf-8") as f:
            t = f.read().strip()
        if t:
            return t
    except OSError:
        pass
    t = secrets.token_urlsafe(24)
    os.makedirs(os.path.dirname(FILE_TOKEN), exist_ok=True)
    with open(FILE_TOKEN, "w", encoding="utf-8") as f:
        f.write(t)
    return t


def ffmpeg_exe() -> str:
    from orchestrator.video_merger import _ffmpeg_exe
    return _ffmpeg_exe() or "ffmpeg"


def kiem_lenh(lenh: List[str]) -> None:
    """Chặn lệnh đọc/ghi ngoài cache: sau -i phải là @tep:…, đầu ra duy nhất là @ra ở cuối."""
    if not lenh or lenh[-1] != "@ra" or lenh.count("@ra") != 1:
        raise HTTPException(400, "Lệnh phải kết thúc bằng @ra.")
    for i, a in enumerate(lenh):
        if not isinstance(a, str):
            raise HTTPException(400, "Tham số phải là chuỗi.")
        if i and lenh[i - 1] == "-i" and not a.startswith("@tep:"):
            raise HTTPException(400, "Đầu vào phải là file đã gửi (@tep:).")
        if a.startswith("@tep:") and not KHOA_TEP.match(a[5:]):
            raise HTTPException(400, "Khoá file không hợp lệ.")
        if ".." in a or re.match(r"^([A-Za-z]:[\\/]|[\\/])", a):
            raise HTTPException(400, f"Không cho phép đường dẫn: {a[:60]}")


class Viec:
    def __init__(self, thu_muc: str):
        self.id = uuid.uuid4().hex[:12]
        self.thu_muc = thu_muc
        self.ra = os.path.join(thu_muc, "ra.mp4")
        self.trang_thai = "dang_chay"
        self.tien_do_us = 0
        self.loi = ""
        self.proc = None
        self.huy = False


def tao_app(thu_muc: str = THU_MUC, ma: str = "") -> FastAPI:
    ma = ma or token()
    cache = os.path.join(thu_muc, "tep")
    os.makedirs(cache, exist_ok=True)
    han = time.time() - GIU_CACHE
    for ten in os.listdir(cache):          # dọn file lâu không dùng
        p = os.path.join(cache, ten)
        try:
            if os.path.getmtime(p) < han:
                os.remove(p)
        except OSError:
            pass
    ds_viec: Dict[str, Viec] = {}
    khoa_chay = threading.Lock()
    app = FastAPI(title="May xuat video")

    @app.middleware("http")
    async def xac_thuc(request: Request, call_next):
        if not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {ma}"):
            from starlette.responses import JSONResponse
            return JSONResponse({"detail": "Sai mã bí mật của máy xuất."}, status_code=401)
        return await call_next(request)

    def lay(vid: str) -> Viec:
        v = ds_viec.get(vid)
        if not v:
            raise HTTPException(404, "Không có việc này.")
        return v

    @app.get("/ping")
    def ping():
        from orchestrator.editor.render import co_nvenc
        exe = ffmpeg_exe()
        return {"ok": True, "nvenc": co_nvenc(exe), "may": os.environ.get("COMPUTERNAME") or os.uname().nodename}

    @app.get("/tep/{khoa}")
    def co_tep(khoa: str):
        if not KHOA_TEP.match(khoa) or not os.path.isfile(os.path.join(cache, khoa)):
            raise HTTPException(404, "Chưa có.")
        os.utime(os.path.join(cache, khoa))
        return {"co": True}

    @app.put("/tep/{khoa}")
    async def gui_tep(khoa: str, request: Request):
        if not KHOA_TEP.match(khoa):
            raise HTTPException(400, "Khoá file không hợp lệ.")
        dich = os.path.join(cache, khoa)
        tam = dich + f".{uuid.uuid4().hex[:6]}.part"
        try:
            with open(tam, "wb") as f:
                async for khuc in request.stream():
                    f.write(khuc)
            os.replace(tam, dich)
        finally:
            if os.path.exists(tam):
                os.remove(tam)
        return {"co": True}

    @app.post("/viec")
    def tao_viec(body: dict):
        lenh = list(body.get("lenh") or [])
        kiem_lenh(lenh)
        tep_phu = body.get("tep_phu") or {}
        for ten in tep_phu:
            if not TEN_PHU.match(ten):
                raise HTTPException(400, f"Tên file phụ không hợp lệ: {ten}")
        for a in lenh:
            if a.startswith("@tep:") and not os.path.isfile(os.path.join(cache, a[5:])):
                raise HTTPException(409, f"Thiếu file {a[5:]} — gửi lại.")
        v = Viec(os.path.join(thu_muc, "viec", uuid.uuid4().hex[:12]))
        os.makedirs(v.thu_muc)
        for ten, noi in tep_phu.items():
            with open(os.path.join(v.thu_muc, ten), "w", encoding="utf-8", newline="") as f:
                f.write(noi)
        that = [ffmpeg_exe()] + [os.path.join(cache, a[5:]) if a.startswith("@tep:") else v.ra if a == "@ra" else a
                                 for a in lenh]
        ds_viec[v.id] = v
        threading.Thread(target=chay, args=(v, that), daemon=True).start()
        return {"id": v.id}

    def chay(v: Viec, lenh: List[str]) -> None:
        with khoa_chay:                     # một việc một lúc — GPU/CPU dồn hết cho nó
            for thu in (lenh, _bo_hwaccel(lenh)):
                if v.huy or thu is None:
                    break
                cuoi: List[str] = []
                v.proc = subprocess.Popen(thu, cwd=v.thu_muc, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          text=True, encoding="utf-8", errors="replace",
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for dong in v.proc.stdout:
                    dong = dong.strip()
                    if dong.startswith("out_time_us="):
                        try:
                            v.tien_do_us = int(dong.split("=", 1)[1])
                        except ValueError:
                            pass
                    elif dong and "=" not in dong:
                        cuoi = (cuoi + [dong])[-6:]
                if v.proc.wait() == 0 and os.path.isfile(v.ra):
                    v.trang_thai = "xong"
                    return
                v.loi = " | ".join(cuoi)[-600:]
            v.trang_thai = "da_huy" if v.huy else "loi"

    @app.get("/viec/{vid}")
    def xem_viec(vid: str):
        v = lay(vid)
        return {"trang_thai": v.trang_thai, "tien_do_us": v.tien_do_us, "loi": v.loi,
                "kich_thuoc": os.path.getsize(v.ra) if v.trang_thai == "xong" else 0}

    @app.get("/viec/{vid}/file")
    def tai_ket_qua(vid: str):
        v = lay(vid)
        if v.trang_thai != "xong":
            raise HTTPException(409, "Chưa xuất xong.")
        return FileResponse(v.ra, media_type="video/mp4")

    @app.delete("/viec/{vid}")
    def xoa_viec(vid: str):
        v = ds_viec.pop(vid, None)
        if v:
            v.huy = True
            if v.proc and v.proc.poll() is None:
                v.proc.kill()
                v.proc.wait()
            shutil.rmtree(v.thu_muc, ignore_errors=True)
        return {"ok": True}

    return app


def _bo_hwaccel(lenh: List[str]):
    """Lần thử thứ hai: bỏ giải mã GPU (-hwaccel cuda) — vài file/driver giải mã CUDA lỗi."""
    if "-hwaccel" not in lenh:
        return None
    out, bo = [], False
    for a in lenh:
        if bo:
            bo = False
            continue
        if a == "-hwaccel":
            bo = True
            continue
        out.append(a)
    return out


def ip_tailscale() -> str:
    from orchestrator.chay_mang_noi_bo import dia_chi_lan
    return next((ip for ip in dia_chi_lan() if ip.startswith("100.") and 64 <= int(ip.split(".")[1]) <= 127), "")


def main() -> int:
    ma = token()
    ip = ip_tailscale()
    print("=" * 66)
    print(" MAY XUAT VIDEO (GPU) - editor o may khac gui viec xuat qua Tailscale")
    print(f"   Dia chi : http://{ip or '<IP Tailscale cua may nay>'}:{CONG}")
    print(f"   Ma bi mat: {ma}")
    print(" Nhap 2 dong tren vao hop Xuat video > May xuat > Laptop o may chinh.")
    if not ip:
        print(" [CANH BAO] Khong thay IP Tailscale - dang nghe tren moi card mang.")
    print(" Dong cua so nay de tat.")
    print("=" * 66, flush=True)
    import uvicorn
    uvicorn.run(tao_app(ma=ma), host=ip or "0.0.0.0", port=CONG, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
