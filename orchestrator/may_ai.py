"""Tác vụ AI trên MÁY XUẤT từ xa (laptop GPU) — gắn thêm vào app của orchestrator/may_xuat.py.

Server (thường là Linux, không có AIVoice/GPU) gửi file media một lần vào cache chung với xuất video
(PUT /tep/<khoá>), rồi POST /ai. Laptop chạy ĐÚNG pipeline AIVoice như app desktop (PhoWhisper,
Demucs, GPU) qua `ai_bridge` + hàng đợi `hang_doi`, trả `ket_qua` (danh sách câu) cho server áp vào timeline.

Chỉ nhận tác vụ không ghi file ra ngoài (danh sách LOAI_NHAN) — kết quả là JSON, không có đường dẫn tự do.
"""
import os
import shutil
import uuid
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

LOAI_NHAN = ("phu-de",)   # tác vụ AI laptop nhận làm hộ (kết quả chỉ là câu phụ đề)


def _xay_lenh(job, args, g):
    from orchestrator.pipeline import VideoPipeline
    return VideoPipeline.build_translate_cmd(None, job, args, g)


def gan_routes(app: FastAPI, cache: str, thu_muc: str, khoa_hop_le) -> None:
    """Thêm /ai vào app máy xuất. `cache`: thư mục file đã gửi (khoá nội dung); `thu_muc`: chỗ làm việc."""
    from orchestrator.editor import ai_bridge, hang_doi
    hang = hang_doi.HangDoi("ai-tu-xa")
    cho_lam: Dict[str, str] = {}   # id việc → thư mục làm việc (xoá khi server dọn)

    @app.get("/ai")
    def kha_nang():
        from orchestrator.pipeline import PYTHON_EXE
        return {"loai": list(LOAI_NHAN), "aivoice": os.path.isfile(PYTHON_EXE)}

    @app.post("/ai")
    def tao(body: Dict[str, Any]):
        loai, khoa = body.get("loai"), str(body.get("tep") or "")
        tham_so = dict(body.get("tham_so") or {})
        if loai not in LOAI_NHAN:
            raise HTTPException(400, f"Laptop không nhận tác vụ '{loai}'.")
        if not khoa_hop_le(khoa) or not os.path.isfile(os.path.join(cache, khoa)):
            raise HTTPException(409, f"Thiếu file {khoa} — gửi lại.")
        # Dự án tạm: ai_bridge đọc media theo đường dẫn tương đối trong thư mục dự án.
        folder = os.path.join(thu_muc, "ai", uuid.uuid4().hex[:12])
        os.makedirs(os.path.join(folder, "media"))
        file_media = os.path.join(folder, "media", khoa)
        try:
            os.link(os.path.join(cache, khoa), file_media)   # cùng ổ → không tốn chỗ
        except OSError:
            shutil.copyfile(os.path.join(cache, khoa), file_media)
        m = {"id": "m_tu_xa", "loai": "video", "file": f"media/{khoa}", "ten": khoa}
        from orchestrator.config import load_global_config
        from orchestrator.pipeline import AIVOICE_DIR
        viec = hang_doi.Viec(loai, lambda ctx: None, nhan=f"AI {loai} (từ xa)", tham_so=tham_so)
        try:
            ke_hoach = ai_bridge.dung_lenh(folder, loai, m, tham_so, load_global_config(), _xay_lenh, viec.id)
        except ValueError as e:
            shutil.rmtree(folder, ignore_errors=True)
            raise HTTPException(400, str(e))
        viec.ham = lambda ctx: ai_bridge.chay(ctx, folder, loai, m, ke_hoach, AIVOICE_DIR, tham_so, lambda *a: {})
        cho_lam[viec.id] = folder
        hang.them(viec)
        return {"id": viec.id}

    def _lay(vid: str) -> Dict[str, Any]:
        v = next((x for x in hang.danh_sach() if x["id"] == vid), None)
        if not v:
            raise HTTPException(404, "Không có việc AI này.")
        return v

    @app.get("/ai/{vid}")
    def xem(vid: str):
        v = _lay(vid)
        return {k: v.get(k) for k in ("trang_thai", "tien_do", "thong_diep", "loi", "ket_qua")}

    @app.delete("/ai/{vid}")
    def xoa(vid: str):
        hang.huy(vid)
        folder = cho_lam.pop(vid, None)
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
        return {"ok": True}
