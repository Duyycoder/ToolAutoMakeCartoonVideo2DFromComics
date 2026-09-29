"""Route FastAPI của editor: `/api/workspace`, `/api/du-an/...`, `/api/hang-doi`.

Dự án gọi bằng `id` (trong `.duan.json`), không bằng đường dẫn: URL gọn, và đổi
tên/chuyển thư mục dự án không làm gãy trang đang mở. Bảng id → thư mục lấy từ
lần quét gần nhất, không thấy thì quét lại.

Mọi thao tác GHI vào dự án đang mở phải kèm `phien` (mã phiên của cửa sổ giữ khoá).
"""
import json
import mimetypes
import os
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from orchestrator.config import load_global_config, save_global_config
from orchestrator.editor import ai_bridge, hang_doi, luu_tru, media, render, srt, workspace

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

class WorkspaceSchema(BaseModel):
    duong_dan: str

class TaoDuAnSchema(BaseModel):
    ten: str
    thong_so: Optional[Dict[str, Any]] = None
    mo_ta: Optional[str] = ""

class FolderSchema(BaseModel):
    folder: str

class SuaDuAnSchema(BaseModel):
    ten: Optional[str] = None
    mo_ta: Optional[str] = None
    thong_so: Optional[Dict[str, Any]] = None

class PhienSchema(BaseModel):
    phien: str = ""

class TimelineSchema(PhienSchema):
    phien_ban: int
    timeline: Dict[str, Any]
    hoan_tac: Optional[Dict[str, Any]] = None

class UiSchema(PhienSchema):
    ui: Dict[str, Any]

class LuuSchema(PhienSchema):
    nhan: Optional[str] = ""

class KhoiPhucSchema(PhienSchema):
    phien_ban: int

class NhapMediaSchema(PhienSchema):
    files: List[str]

class UrlSchema(PhienSchema):
    urls: List[str]

class NhapLaiSchema(PhienSchema):
    nguon: Optional[str] = ""

class PhatDuocSchema(BaseModel):
    ok: bool

class DocPhuDeSchema(BaseModel):
    path: Optional[str] = ""
    mid: Optional[str] = ""

class LuuPhuDeSchema(PhienSchema):
    ten: str
    noi_dung: str

class XuatSchema(PhienSchema):
    tuy_chon: Dict[str, Any] = {}

class AiSchema(PhienSchema):
    media: str = ""
    tham_so: Dict[str, Any] = {}

def _cfg_editor() -> Dict[str, Any]:
    return dict(load_global_config().get("editor") or {})

def _luu_cfg_editor(**thay: Any) -> None:
    cfg = load_global_config()
    ed = dict(cfg.get("editor") or {})
    ed.update(thay)
    cfg["editor"] = ed
    save_global_config(cfg)

def _mo_explorer(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - đường dẫn do server tự dựng
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

def tao_router(process_mgr, pipeline=None) -> APIRouter:
    r = APIRouter()
    hang_gpu = hang_doi.HangDoi("gpu", process_mgr)
    qlm = media.QuanLyMedia()
    bang: Dict[str, str] = {}
    bang_lock = threading.Lock()

    # ------------------------------------------------------------- tiện ích
    def quet_lai() -> List[Dict[str, Any]]:
        ed = _cfg_editor()
        the, moi = workspace.quet(workspace.lay_workspace({"editor": ed}), ed.get("du_an_ngoai") or [])
        with bang_lock:
            bang.clear()
            bang.update(moi)
        return the

    def folder_cua(pid: str) -> str:
        with bang_lock:
            f = bang.get(pid)
        if f and os.path.exists(luu_tru.duong_dan_duan(f)):
            return f
        quet_lai()
        with bang_lock:
            f = bang.get(pid)
        if not f:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy dự án '{pid}' (đã xoá hoặc chuyển đi?).")
        return f

    def khoa_ghi(folder: str, phien: str) -> None:
        try:
            luu_tru.kiem_tra_khoa(folder, phien)
        except luu_tru.KhongGiuKhoa as e:
            raise HTTPException(status_code=423, detail=str(e))

    def them_ngoai(folder: str) -> None:
        ed = _cfg_editor()
        if workspace.trong_workspace(workspace.lay_workspace({"editor": ed}), folder):
            return
        ds = [p for p in ed.get("du_an_ngoai") or [] if os.path.normcase(p) != os.path.normcase(folder)]
        _luu_cfg_editor(du_an_ngoai=[folder] + ds)

    def bo_ngoai(folder: str) -> None:
        ds = _cfg_editor().get("du_an_ngoai") or []
        _luu_cfg_editor(du_an_ngoai=[p for p in ds if os.path.normcase(p) != os.path.normcase(folder)])

    def the_cua(folder: str) -> Dict[str, Any]:
        for t in quet_lai():
            if os.path.normcase(t["folder"]) == os.path.normcase(folder):
                return t
        raise HTTPException(status_code=500, detail="Tạo xong nhưng quét không thấy dự án.")

    def gui_file(path: str, media_type: Optional[str] = None) -> FileResponse:
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Chưa có file.")
        mt = media_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        return FileResponse(path, media_type=mt, headers={"Cache-Control": "no-cache"})

    # ------------------------------------------------------------ Nơi làm việc
    @r.get("/api/workspace")
    def get_workspace():
        ed = _cfg_editor()
        return {"duong_dan": workspace.lay_workspace({"editor": ed}),
                "mac_dinh": not (ed.get("workspace") or "").strip(),
                "du_an": quet_lai(), "cau_hinh": ed}

    @r.post("/api/workspace")
    def set_workspace(body: WorkspaceSchema):
        path = os.path.abspath((body.duong_dan or "").strip())
        if not (body.duong_dan or "").strip():
            raise HTTPException(status_code=400, detail="Chưa chọn thư mục.")
        try:
            workspace.tao_thu_muc(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(status_code=400, detail=f"Không tạo được thư mục: {e}")
        _luu_cfg_editor(workspace=path)
        return get_workspace()

    @r.post("/api/workspace/mo-thu-muc")
    def open_workspace():
        path = workspace.lay_workspace({"editor": _cfg_editor()})
        try:
            workspace.tao_thu_muc(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        _mo_explorer(path)
        return {"path": path}

    # ------------------------------------------------------------------ Dự án
    @r.post("/api/du-an")
    def create_project(body: TaoDuAnSchema):
        ws = workspace.lay_workspace({"editor": _cfg_editor()})
        try:
            data = workspace.tao(ws, body.ten, body.thong_so, body.mo_ta or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Không tạo được thư mục dự án: {e}")
        return the_cua(data["folder"])

    @r.post("/api/du-an/nhap")
    def import_project(body: FolderSchema):
        try:
            workspace.nhap(body.folder, media.do_thong_so)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Không đọc/ghi được thư mục: {e}")
        folder = os.path.abspath(body.folder)
        them_ngoai(folder)
        return the_cua(folder)

    @r.get("/api/du-an/{pid}")
    def open_project(pid: str, phien: str = ""):
        folder = folder_cua(pid)
        thong_bao = []
        data = luu_tru.doc_duan(folder)
        if data is None:
            raise HTTPException(status_code=500, detail="File .duan.json bị hỏng — không mở được dự án.")
        if int(data.get("schema") or 1) < luu_tru.SCHEMA:
            try:
                data = luu_tru.nang_cap(folder, media.do_thong_so)
            except OSError as e:
                raise HTTPException(status_code=500, detail=f"Không nâng cấp được dự án cũ: {e}")
            thong_bao.append("Đã nâng cấp dự án cũ sang dạng mới — không file nào bị di chuyển.")
        so = qlm.don_khi_mo(folder)
        if so:
            thong_bao.append(f"{so} media đang nhập dở từ lần trước — bấm Nhập lại trên thẻ media.")
        so = hang_doi.danh_dau_bi_ngat(folder, hang_gpu.ids_con_song())
        if so:
            thong_bao.append(f"{so} tác vụ AI bị ngắt vì app đã đóng — có thể chạy lại.")
        khoa = luu_tru.lay_khoa(folder, phien)
        timeline, phuc_hoi = luu_tru.doc_timeline(folder)
        if phuc_hoi:
            thong_bao.append(phuc_hoi)
        hoan_tac, bo = luu_tru.doc_hoan_tac(folder, int(timeline.get("phien_ban") or 0))
        if bo:
            thong_bao.append("Lịch sử hoàn tác không khớp với tiến độ đã lưu (app tắt ngang) — đã bỏ, "
                             "không ảnh hưởng nội dung dựng.")
        data = luu_tru.doc_duan(folder) or data
        return {"du_an": {**data, "folder": folder}, "timeline": timeline, "ui": luu_tru.doc_ui(folder),
                "hoan_tac": hoan_tac, "khoa": khoa, "thong_bao": thong_bao, "cau_hinh": _cfg_editor()}

    @r.patch("/api/du-an/{pid}")
    def patch_project(pid: str, body: SuaDuAnSchema):
        folder = folder_cua(pid)
        try:
            data = workspace.sua(folder, body.ten, body.mo_ta, body.thong_so)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {**data, "folder": folder}

    @r.post("/api/du-an/{pid}/xoa")
    def delete_project(pid: str):
        folder = folder_cua(pid)
        if luu_tru.dang_bi_giu(folder):
            raise HTTPException(status_code=409, detail="Dự án đang mở ở một cửa sổ — đóng nó trước khi xoá.")
        try:
            workspace.xoa(folder)
        except (OSError, ImportError) as e:
            raise HTTPException(status_code=500, detail=f"Không chuyển được vào Thùng rác: {e}")
        bo_ngoai(folder)
        with bang_lock:
            bang.pop(pid, None)
        return {"status": "success"}

    @r.get("/api/workspace/dung-chung")
    def list_shared_media():
        ws = get_workspace()["duong_dan"]
        folder = os.path.join(ws, "_dung_chung")
        if not os.path.exists(folder):
            return {"media": []}
        
        from .media import loai_theo_duoi
        import time
        import hashlib
        media = []
        for root, dirs, files in os.walk(folder):
            for file in files:
                loai = loai_theo_duoi(file)
                if loai:
                    p = os.path.join(root, file)
                    rel = os.path.relpath(p, folder).replace("\\", "/")
                    media.append({
                        "id": f"dc_{hashlib.sha1(rel.encode('utf-8')).hexdigest()[:10]}",
                        "loai": loai,
                        "rel": rel,
                        "ten": os.path.splitext(file)[0],
                        "kich_thuoc": os.path.getsize(p),
                        "nhap_luc": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(os.path.getmtime(p))),
                        "trang_thai": "san_sang"
                    })
        return {"media": media}

    @r.get("/api/workspace/dung-chung/file")
    def get_shared_media_file(rel: str):
        ws = get_workspace()["duong_dan"]
        folder = os.path.abspath(os.path.join(ws, "_dung_chung"))
        p = os.path.abspath(os.path.join(folder, rel))
        try:
            if os.path.commonpath([folder, p]) != folder:
                raise HTTPException(status_code=404, detail="Đường dẫn không hợp lệ")
        except ValueError:
            raise HTTPException(status_code=404, detail="Đường dẫn không hợp lệ")
        if not os.path.exists(p):
            raise HTTPException(status_code=404, detail="Không tìm thấy file")
        from fastapi.responses import FileResponse
        return FileResponse(p)

    @r.post("/api/workspace/dung-chung/mo-thu-muc")
    def open_shared_media_folder():
        ws = get_workspace()["duong_dan"]
        folder = os.path.join(ws, "_dung_chung")
        os.makedirs(folder, exist_ok=True)
        _mo_explorer(folder)
        return {"status": "success"}

    @r.post("/api/du-an/{pid}/nhan-ban")
    def duplicate_project(pid: str, body: SuaDuAnSchema):
        folder = folder_cua(pid)
        da_cu = luu_tru.doc_duan(folder) or {}
        ten_moi = body.ten or f"{da_cu.get('name') or 'Dự án'} (bản sao)"
        from orchestrator.storage import slugify
        slug = slugify(ten_moi) or "ban-sao"
        goc_cha = os.path.dirname(folder)
        folder_moi = os.path.join(goc_cha, slug)
        lan = 2
        while os.path.exists(folder_moi):
            folder_moi = os.path.join(goc_cha, f"{slug}_{lan}")
            lan += 1
            
        def bo_qua(thu_muc, ds_file):
            if os.path.basename(os.path.normpath(thu_muc)) == ".duan":
                return [f for f in ds_file if f in ("lock", "cache")]
            return []
            
        import shutil, uuid
        try:
            shutil.copytree(folder, folder_moi, ignore=bo_qua)
        except OSError as e:
            if os.path.exists(folder_moi):
                shutil.rmtree(folder_moi, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Lỗi sao chép thư mục: {e}")
            
        try:
            def sua(da):
                da["id"] = uuid.uuid4().hex[:8]
                da["name"] = ten_moi
                da["tao_luc"] = luu_tru._iso()
                da["tac_vu"] = [t for t in da.get("tac_vu", []) if t.get("trang_thai") not in ("cho", "dang_chay")]
                return True
            luu_tru.sua_duan(folder_moi, sua)
        except Exception as e:
            shutil.rmtree(folder_moi, ignore_errors=True)
            raise HTTPException(status_code=500, detail=f"Lỗi cập nhật cấu hình dự án mới: {e}")
            
        them_ngoai(folder_moi)
        return the_cua(folder_moi)

    @r.post("/api/du-an/{pid}/mo-thu-muc")
    def open_project_folder(pid: str):
        folder = folder_cua(pid)
        _mo_explorer(folder)
        return {"path": folder}

    @r.get("/api/du-an/{pid}/anh-bia")
    def cover(pid: str):
        folder = folder_cua(pid)
        bia = (luu_tru.doc_duan(folder) or {}).get("anh_bia") or ""
        if not bia:
            raise HTTPException(status_code=404, detail="Chưa có ảnh bìa.")
        try:
            return gui_file(luu_tru.duong_dan_media(folder, bia))
        except ValueError:
            raise HTTPException(status_code=404, detail="Ảnh bìa không hợp lệ.")

    # -------------------------------------------------------- Lưu tiến độ
    @r.put("/api/du-an/{pid}/timeline")
    def put_timeline(pid: str, body: TimelineSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        so_ban = int(_cfg_editor().get("so_ban_lich_su") or luu_tru.SO_BAN_TU_DONG)
        try:
            moi = luu_tru.ghi_timeline(folder, body.timeline, body.phien_ban, body.hoan_tac, so_ban)
        except luu_tru.XungDotPhienBan as e:
            raise HTTPException(status_code=409, detail={"thong_diep": str(e), "hien_tai": e.hien_tai})
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"phien_ban": moi}

    @r.put("/api/du-an/{pid}/ui")
    def put_ui(pid: str, body: UiSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        luu_tru.ghi_ui(folder, body.ui)
        return {"status": "success"}

    @r.post("/api/du-an/{pid}/ui-beacon")
    async def beacon_ui(pid: str, request: Request):
        """Cho `navigator.sendBeacon` lúc đóng trang: chỉ POST được, thân ≤64 KB, nên chỉ nhận ui.json."""
        try:
            body = json.loads((await request.body()).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Thân yêu cầu không phải JSON.")
        folder = folder_cua(pid)
        khoa_ghi(folder, body.get("phien") or "")
        if isinstance(body.get("ui"), dict):
            luu_tru.ghi_ui(folder, body["ui"])
        if body.get("dong"):
            luu_tru.nha_khoa(folder, body.get("phien") or "")
        return {"status": "success"}

    @r.post("/api/du-an/{pid}/nhip")
    def heartbeat(pid: str, body: PhienSchema):
        folder = folder_cua(pid)
        return {"giu_khoa": luu_tru.nhip(folder, body.phien)}

    @r.post("/api/du-an/{pid}/luu")
    def save_version(pid: str, body: LuuSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        return {"ten": luu_tru.luu_thu_cong(folder, body.nhan or "")}

    @r.get("/api/du-an/{pid}/phien-ban")
    def list_versions(pid: str):
        return luu_tru.danh_sach_phien_ban(folder_cua(pid))

    @r.post("/api/du-an/{pid}/phien-ban/{ten}/khoi-phuc")
    def restore_version(pid: str, ten: str, body: KhoiPhucSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            return {"timeline": luu_tru.khoi_phuc(folder, ten, body.phien_ban)}
        except luu_tru.XungDotPhienBan as e:
            raise HTTPException(status_code=409, detail={"thong_diep": str(e), "hien_tai": e.hien_tai})
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/api/du-an/{pid}/dong")
    def close_project(pid: str, body: PhienSchema):
        luu_tru.nha_khoa(folder_cua(pid), body.phien)
        return {"status": "success"}

    # ------------------------------------------------------------------ Media
    def viec_media(pid: str) -> List[Dict[str, Any]]:
        """Việc đang chạy/chờ + các lượt TẢI LINK đã xong/lỗi (giao diện phải báo kết quả —
        trước đây lượt tải lỗi biến mất êm, người dùng không biết có tải được hay không)."""
        return [v for h in qlm.cac_hang() for v in h.danh_sach(pid)
                if v["trang_thai"] in hang_doi.CON_DO or v["loai"] == "tai_url"]

    @r.get("/api/du-an/{pid}/media")
    def list_media(pid: str):
        folder = folder_cua(pid)
        data = luu_tru.doc_duan(folder) or {}
        ds = []
        for m in data.get("media") or []:
            m = dict(m)
            try:
                m["mat_file"] = (m.get("trang_thai") == "san_sang"
                                 and not os.path.exists(luu_tru.duong_dan_media(folder, m.get("file") or "")))
            except ValueError:
                m["mat_file"] = True
            ds.append(m)
        return {"media": ds, "viec": viec_media(pid), "anh_bia": data.get("anh_bia") or "",
                "thong_so": data.get("thong_so") or {}}

    @r.post("/api/du-an/{pid}/media/nhap")
    def import_media(pid: str, body: NhapMediaSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            return {"media": qlm.nhap(folder, pid, body.files)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Không ghi được vào dự án: {e}")

    @r.post("/api/du-an/{pid}/media/url")
    def import_url(pid: str, body: UrlSchema):
        from orchestrator.pipeline import AIVOICE_DIR, DOWNLOAD_ADAPTER, PYTHON_EXE
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        g = load_global_config()
        cookies = ((g.get("download") or {}).get("cookies_file")
                   or (g.get("video") or {}).get("downloader_cookies") or "").strip()

        def lenh(tam: str) -> list:
            cmd = [PYTHON_EXE, DOWNLOAD_ADAPTER, "--output-dir", tam, "--platform", "generic"]
            for u in body.urls:
                if (u or "").strip():
                    cmd += ["--url", u.strip()]
            return cmd + (["--cookies-file", cookies] if cookies else [])
        try:
            v = qlm.tai_url(folder, pid, body.urls, lenh, AIVOICE_DIR)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"viec": v.to_dict()}

    @r.post("/api/du-an/{pid}/media/{mid}/nhap-lai")
    def reimport_media(pid: str, mid: str, body: NhapLaiSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            return qlm.nhap_lai(folder, pid, mid, body.nguon or "")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/api/du-an/{pid}/media/{mid}/phat-duoc")
    def report_playable(pid: str, mid: str, body: PhatDuocSchema):
        folder = folder_cua(pid)
        try:
            return qlm.bao_phat_duoc(folder, pid, mid, body.ok)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @r.delete("/api/du-an/{pid}/media/{mid}")
    def delete_media(pid: str, mid: str, phien: str = "", xoa_file: bool = False):
        folder = folder_cua(pid)
        khoa_ghi(folder, phien)
        timeline, _ = luu_tru.doc_timeline(folder)
        dang_dung = any(c.get("media") == mid or c.get("tu_media") == mid for c in timeline.get("clips") or [])
        try:
            qlm.xoa(folder, mid, xoa_file, dang_dung)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"status": "success"}

    def media_path(pid: str, mid: str):
        folder = folder_cua(pid)
        try:
            m = qlm.lay(folder, mid)
            return folder, m, luu_tru.duong_dan_media(folder, m.get("file") or "")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @r.get("/api/du-an/{pid}/media/{mid}/file")
    def media_file(pid: str, mid: str, goc: bool = False):
        """Phục vụ `<video>`/`<audio>` (FileResponse có hỗ trợ Range). Có proxy thì trả proxy."""
        folder, m, path = media_path(pid, mid)
        if not goc and m.get("proxy") == "xong":
            proxy = luu_tru._p(folder, luu_tru.CACHE, "proxy", f"{mid}.mp4")
            if os.path.isfile(proxy):
                return gui_file(proxy, "video/mp4")
        return gui_file(path)

    @r.get("/api/du-an/{pid}/media/{mid}/{loai}")
    def media_preview(pid: str, mid: str, loai: str):
        ten = {"thumb": f"{mid}.jpg", "dai-hinh": f"{mid}_dai.jpg", "song-am": f"{mid}_song.png"}.get(loai)
        if not ten:
            raise HTTPException(status_code=404, detail="Không có loại ảnh này.")
        folder = folder_cua(pid)
        return gui_file(luu_tru._p(folder, luu_tru.CACHE, "thumbs", ten))

    # ------------------------------------------------------------- Hàng đợi
    @r.get("/api/hang-doi")
    def list_queue():
        return {h.ten: h.danh_sach() for h in [hang_gpu] + qlm.cac_hang()}

    @r.post("/api/hang-doi/{vid}/huy")
    def cancel_job(vid: str):
        for h in [hang_gpu] + qlm.cac_hang():
            if h.huy(vid):
                return {"status": "success"}
        raise HTTPException(status_code=404, detail="Không có tác vụ này (đã xong?).")

    # ------------------------------------------------------------- Phụ đề
    @r.post("/api/du-an/{pid}/phu-de/doc")
    def read_subtitle(pid: str, body: DocPhuDeSchema):
        """Đọc .srt/.vtt/.ass (media phụ đề của dự án, hoặc file người dùng vừa chọn) → câu."""
        folder = folder_cua(pid)
        try:
            if body.mid:
                m = qlm.lay(folder, body.mid)
                path = luu_tru.duong_dan_media(folder, m["file"])
            else:
                path = os.path.abspath(body.path or "")
            if os.path.splitext(path)[1].lower() not in media.PHU_DE_EXTS or not os.path.isfile(path):
                raise ValueError("Chỉ đọc được file .srt / .vtt / .ass có thật.")
            return {"cau": srt.phan_tich(srt.doc_file(path)), "file": path}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/api/du-an/{pid}/phu-de/luu")
    def save_subtitle(pid: str, body: LuuPhuDeSchema):
        """Ghi .srt (client dựng nội dung theo giờ timeline) vào phu_de/ của dự án."""
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        import re as _re
        ten = _re.sub(r'[<>:"/\|?*\x00-\x1f]', "_", (body.ten or "phu_de").strip())[:80].strip(" .") or "phu_de"
        if not ten.lower().endswith(".srt"):
            ten += ".srt"
        path = os.path.join(folder, luu_tru.PHU_DE_DIR, ten)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body.noi_dung)
        return {"file": f"{luu_tru.PHU_DE_DIR}/{ten}", "path": path}

    # ------------------------------------------------------------- Lồng tiếng
    @r.get("/api/tts/giong")
    def get_tts_voices(engine: str = "edge", lang: str = ""):
        if engine == "edge":
            try:
                import asyncio
                import edge_tts
                async def _get():
                    return await edge_tts.list_voices()
                voices = asyncio.run(asyncio.wait_for(_get(), timeout=3.0))
                if lang == "Vietnamese" or lang == "Tiếng Việt":
                    return {"giong": [v["ShortName"] for v in voices if "vi-" in v["ShortName"]]}
                else:
                    return {"giong": [v["ShortName"] for v in voices]}
            except Exception:
                return {"giong": ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"]}
        elif engine == "piper":
            from orchestrator.pipeline import AIVOICE_DIR
            piper_dir = os.path.join(AIVOICE_DIR, "models", "piper")
            if os.path.exists(piper_dir):
                models = [f for f in os.listdir(piper_dir) if f.endswith(".onnx")]
                if models: return {"giong": models}
            return {"giong": ["vi_VN-vais1000-medium.onnx"]}
        elif engine == "kokoro":
            return {"giong": ["diem_trinh", "hung_thinh", "mai_linh", "mai_loan", "manh_dung", 
                    "my_yen", "ngoc_huyen", "phat_tai", "thanh_dat", "thuc_trinh", 
                    "tuan_ngoc", "storyvert", "duc_an", "duc_duy"]}
        elif engine == "vieneu":
            return {"giong": ["Ngọc Lan", "Gia Bảo", "Thái Sơn", "Đức Trí", "Mỹ Duyên", "Trúc Ly", "Xuân Vĩnh", "Trọng Hữu", "Bình An", "Ngọc Linh"]}
        return {"giong": []}


    # ---------------------------------------------------------- Tác vụ AI
    def xay_lenh(job, args, g):
        if pipeline is not None:
            return pipeline.build_translate_cmd(job, args, g)
        from orchestrator.pipeline import VideoPipeline
        return VideoPipeline.build_translate_cmd(None, job, args, g)

    def xep_ai(folder: str, pid: str, loai: str, media_id: str, tham_so: Dict[str, Any]) -> hang_doi.Viec:
        from orchestrator.pipeline import AIVOICE_DIR
        m = qlm.lay(folder, media_id) if loai not in ai_bridge.KHONG_CAN_MEDIA else None
        g = load_global_config()
        m_id = m["id"] if m else ""
        m_ten = m.get("ten") if m else ""
        nhan = f"{ai_bridge.TEN.get(loai, loai)} — {m_ten}" if loai not in ai_bridge.KHONG_CAN_MEDIA else ai_bridge.TEN.get(loai, loai)
        viec = hang_doi.Viec(loai, lambda ctx: None, du_an=folder, du_an_id=pid, media=m_id,
                             nhan=nhan,
                             tham_so={k: v for k, v in tham_so.items() if k != "cau"})
                             
        if loai == "dich":
            def lam(ctx):
                dam_bao_llm(ctx, g, tham_so, check_dich=True)
                from orchestrator.editor import dich
                return dich.dich(ctx, folder, loai, m, tham_so)
            viec.ham = lam
        else:
            ke_hoach = ai_bridge.dung_lenh(folder, loai, m, tham_so, g, xay_lenh, viec.id)
            def lam(ctx):
                return ai_bridge.chay(ctx, folder, loai, m, ke_hoach, AIVOICE_DIR, tham_so,
                                      lambda f, wav, tu: qlm.dang_ky_file(f, pid, wav, tu))
            viec.ham = lam
            
        hang_gpu.them(viec)
        return viec

    r.xep_ai = xep_ai  # type: ignore

    @r.get("/api/thuat-ngu/nguon")
    def get_thuat_ngu_nguon():
        import os
        
        goc_storage = getattr(r, "storage_truyen_dir", os.path.abspath("storage/truyen"))
        nguon = []
        if os.path.isdir(goc_storage):
            for d in os.listdir(goc_storage):
                p = os.path.join(goc_storage, d, "raw", "glossary.json")
                if os.path.isfile(p):
                    try:
                        data = json.load(open(p, "r", encoding="utf-8"))
                        if isinstance(data, dict):
                            nguon.append({"id": f"truyen_{d}", "ten": d, "so_muc": len(data), "data": data})
                    except Exception: pass
                    
        ws = _cfg_editor().get("workspace", "")
        if ws:
            chung = os.path.join(ws, "_dung_chung", "thuat_ngu.json")
            if os.path.isfile(chung):
                try:
                    data = json.load(open(chung, "r", encoding="utf-8"))
                    if isinstance(data, dict):
                        nguon.append({"id": "dung_chung", "ten": "Dùng chung", "so_muc": len(data), "data": data})
                except Exception: pass
                
        return {"nguon": nguon}

    @r.get("/api/du-an/{pid}/thuat-ngu")
    def get_thuat_ngu(pid: str):
        folder = folder_cua(pid)
        rieng_path = os.path.join(folder, ".duan", "thuat_ngu.json")
        tn = {}
        if os.path.exists(rieng_path):
            try:
                tn = json.load(open(rieng_path, "r", encoding="utf-8"))
            except Exception:
                pass
        text = "\n".join(f"{k} = {v}" for k, v in tn.items())
        return {"text": text}

    @r.put("/api/du-an/{pid}/thuat-ngu")
    async def put_thuat_ngu(pid: str, req: Request):
        folder = folder_cua(pid)
        body = await req.json()
        text = body.get("text", "")
        tn = {}
        for line in text.split("\n"):
            line = line.strip()
            if not line or "=" not in line: continue
            k, v = line.split("=", 1)
            tn[k.strip()] = v.strip()
            
        os.makedirs(os.path.join(folder, ".duan"), exist_ok=True)
        with open(os.path.join(folder, ".duan", "thuat_ngu.json"), "w", encoding="utf-8") as f:
            json.dump(tn, f, ensure_ascii=False, indent=2)
        return {"ok": True}

    @r.post("/api/du-an/{pid}/ai/{loai}")
    def start_ai(pid: str, loai: str, body: AiSchema):
        tham_so = body.tham_so or {}
        if loai == 'dich':
            if not tham_so.get('cau'): raise HTTPException(400, detail='Chưa có câu để dịch')
            if tham_so.get('source_lang') == 'auto': raise HTTPException(400, detail='Chưa biết ngôn ngữ nguồn')
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            viec = xep_ai(folder, pid, loai, body.media, body.tham_so)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"viec": viec.to_dict()}

    def dam_bao_llm(ctx, g, tham_so, check_dich=False):
        """Engine Ollama: bật server + tải model nếu thiếu TRƯỚC khi dịch (báo tiến độ lên thẻ)."""
        from orchestrator import ollama_manager
        tr = g.get("translate") or {}
        autosub = g.get("autosub") or {}
        engine = tham_so.get("llm_engine") or tr.get("engine") or autosub.get("llm_engine")
        if engine != "ollama" and not check_dich:
            return
        if check_dich:
            model = tham_so.get("mt_model") or tr.get("mt_model") or "hy-mt2:1.8b"
        else:
            model = tham_so.get("llm_model") or autosub.get("llm_model") or tr.get("ollama_model") or ""
        base_url = tham_so.get("llm_offline_base_url") or tham_so.get("llm_base_url") or autosub.get("llm_base_url") or tr.get("ollama_base_url") or ""
        kq = ollama_manager.ensure_ready(model, base_url,
                                         autostart=bool(tr.get("autostart_ollama", True)),
                                         progress_cb=lambda msg, pct=-1, *a: ctx.bao(pct if pct and pct >= 0 else None, msg))
        if not kq.get("ok"):
            raise RuntimeError(kq.get("reason") or f"Ollama chưa chạy ở {base_url} — bật Ollama hoặc đổi engine trong ⚙ Cấu hình")

    @r.get("/api/du-an/{pid}/tac-vu")
    def list_jobs(pid: str):
        """Tác vụ AI của dự án: đang chạy/chờ (tiến độ sống) + đã xong trong .duan.json."""
        folder = folder_cua(pid)
        song = {v["id"]: v for v in hang_gpu.danh_sach(pid)}
        ds = []
        for tv in reversed((luu_tru.doc_duan(folder) or {}).get("tac_vu") or []):
            v = song.pop(tv.get("id"), None)
            ds.append({**tv, **({k: v[k] for k in ("trang_thai", "tien_do", "thong_diep", "vi_tri", "loi", "ket_qua")
                                 if k in v} if v else {}), "da_ap_dung": tv.get("da_ap_dung", False)})
        return {"tac_vu": list(song.values()) + ds}

    @r.post("/api/du-an/{pid}/tac-vu/{tid}/ap-dung")
    def mark_applied(pid: str, tid: str, body: PhienSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)

        def ham(data):
            for tv in data.get("tac_vu") or []:
                if tv.get("id") == tid:
                    tv["da_ap_dung"] = True
                    return True
            return False
        if not luu_tru.sua_duan(folder, ham):
            raise HTTPException(status_code=404, detail="Không có tác vụ này.")
        return {"status": "success"}

    @r.post("/api/du-an/{pid}/tac-vu/{tid}/an")
    def hide_job(pid: str, tid: str, body: PhienSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        luu_tru.sua_duan(folder, lambda d: d.__setitem__("tac_vu", [t for t in d.get("tac_vu") or [] if t.get("id") != tid]))
        return {"status": "success"}

    # --------------------------------------------------------------- Xuất
    nvenc: Dict[str, bool] = {}

    def xep_xuat(folder: str, pid: str, tuy_chon: Dict[str, Any]) -> Tuple[hang_doi.Viec, str]:
        tc = dict(tuy_chon or {})
        ff = media.ffmpeg_exe()
        if not ff:
            raise RuntimeError("Không tìm thấy ffmpeg (imageio_ffmpeg).")
        if tc.get("bo_ma_hoa", "auto") == "auto":
            if "co" not in nvenc:
                nvenc["co"] = render.co_nvenc(ff)
            tc["bo_ma_hoa"] = "nvenc" if nvenc["co"] else "x264"
        du_an = luu_tru.doc_duan(folder) or {}
        tl, _ = luu_tru.doc_timeline(folder)
        chi_tieng = bool(tc.get("chi_am_thanh"))
        ra = render.ten_file_ra(folder, tc.get("ten") or du_an.get("name") or "video", ".m4a" if chi_tieng else ".mp4")
        try:
            kq = render.dung_lenh_xuat(folder, du_an, tl, tc, ra, ff)
        except ValueError as e:
            raise RuntimeError(str(e))
        viec = hang_doi.Viec("xuat", lambda ctx: None, du_an=folder, du_an_id=pid,
                             nhan=f"Xuất {os.path.basename(ra)}", tham_so={k: v for k, v in tc.items()})

        def lam(ctx):
            thu_muc = luu_tru._p(folder, luu_tru.CACHE, "xuat", viec.id)
            os.makedirs(thu_muc, exist_ok=True)
            with open(os.path.join(thu_muc, "loc.txt"), "w", encoding="utf-8") as fh:
                fh.write(kq["loc"])
            with open(os.path.join(thu_muc, "sub.ass"), "w", encoding="utf-8") as fh:
                fh.write(kq["ass"])
            T = max(0.001, float(kq["thoi_luong"]))
            ctx.bao(0, f"Đang xuất {kq['kich_thuoc'][0]}×{kq['kich_thuoc'][1]} ({tc['bo_ma_hoa']})…")
            cuoi = []

            def dong(line):
                if line.startswith("out_time_us="):
                    try:
                        ctx.bao(min(99.0, int(line.split("=", 1)[1]) / 1e6 * 100 / T))
                    except ValueError:
                        pass
                elif not line.startswith(("frame=", "fps=", "stream_", "bitrate=", "total_size=", "out_time",
                                          "dup_frames", "drop_frames", "speed=", "progress=")):
                    cuoi.append(line)
                    del cuoi[:-15]
            try:
                code = ctx.chay_doc_dong(kq["cmd"], thu_muc, dong, log=os.path.join(thu_muc, "log.txt"))
            except hang_doi.DaHuy:
                if os.path.exists(ra):
                    os.remove(ra)
                raise

            if code != 0 and "-hwaccel" in kq["cmd"]:
                cmd2 = []
                skip_next = False
                for x in kq["cmd"]:
                    if skip_next:
                        skip_next = False
                        continue
                    if x == "-hwaccel":
                        skip_next = True
                        continue
                    cmd2.append(x)
                try:
                    code = ctx.chay_doc_dong(cmd2, thu_muc, dong, log=os.path.join(thu_muc, "log.txt"))
                except hang_doi.DaHuy:
                    if os.path.exists(ra):
                        os.remove(ra)
                    raise

            if code != 0 or not os.path.exists(ra):
                if os.path.exists(ra):
                    os.remove(ra)
                raise RuntimeError("ffmpeg lỗi: " + " | ".join(x for x in cuoi[-4:] if x.strip())[-600:])
            srt_rel = ""
            if tc.get("xuat_srt"):
                noi = render.xuat_srt(tl)
                if noi:
                    p_srt = os.path.splitext(ra)[0] + ".srt"
                    with open(p_srt, "w", encoding="utf-8") as fh:
                        fh.write(noi)
                    srt_rel = os.path.relpath(p_srt, folder).replace("\\", "/")
            return {"file": os.path.relpath(ra, folder).replace("\\", "/"), "thoi_luong": kq["thoi_luong"],
                    "kich_thuoc": kq["kich_thuoc"], "bo_ma_hoa": tc["bo_ma_hoa"], "srt": srt_rel,
                    "dung_luong": os.path.getsize(ra)}
        viec.ham = lam
        hang_gpu.them(viec)
        return viec, os.path.relpath(ra, folder).replace("\\", "/")

    r.xep_xuat = xep_xuat

    @r.post("/api/du-an/{pid}/xuat")
    def export(pid: str, body: XuatSchema):
        """Xuất video (ffmpeg, file GỐC) → xuat/<tên>.mp4. Chạy ở hàng đợi GPU như tác vụ AI."""
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            viec, rel_path = xep_xuat(folder, pid, body.tuy_chon)
            return {"viec": viec.to_dict(), "file": rel_path}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/api/du-an/{pid}/mo-thu-muc-con")
    def open_sub_folder(pid: str, ten: str = "xuat"):
        folder = folder_cua(pid)
        con = {"xuat": luu_tru.XUAT_DIR, "phu_de": luu_tru.PHU_DE_DIR, "media": luu_tru.MEDIA_DIR,
               "long_tieng": luu_tru.LONG_TIENG_DIR}.get(ten, "")
        path = os.path.join(folder, con) if con else folder
        os.makedirs(path, exist_ok=True)
        _mo_explorer(path)
        return {"path": path}

    r.hang_gpu = hang_gpu   # type: ignore[attr-defined] — cho GĐ 1 và test
    r.qlm = qlm             # type: ignore[attr-defined]
    
    from orchestrator.editor import hang_loat
    @r.get("/api/ai/models")
    def ai_models():
        from orchestrator.pipeline import AIVOICE_DIR
        res = {}
        esrgan_dir = os.path.join(AIVOICE_DIR, "apps", "MediaComposer", "models", "realesrgan")
        if os.path.exists(os.path.join(esrgan_dir, "realesr-animevideov3.pth")):
            res["realesr_animevideov3"] = True
        else:
            res["realesr_animevideov3"] = False
        import importlib.util
        # Clone (coqui-tts) cần cả gói TTS lẫn torchcodec (PyTorch 2.9+) — thiếu một trong hai là chạy lỗi.
        res["clone"] = all(importlib.util.find_spec(g) is not None for g in ("TTS", "torchcodec"))
        # Model tạo ảnh có sẵn: cùng thư mục cache mà image_generator.py dùng (HF_HOME, không có thì MediaComposer/storage/models)
        # — máy người dùng đã có dreamshaper-8/anything-v5 từ công cụ cũ, UI không được báo "sẽ tải ~2 GB" sai.
        kho = os.environ.get("HF_HOME") or os.path.join(AIVOICE_DIR, "apps", "MediaComposer", "storage", "models")
        try:
            res["anh_co_san"] = sorted(t[len("models--"):].replace("--", "/") for t in os.listdir(kho)
                                       if t.startswith("models--") and os.path.isdir(os.path.join(kho, t, "snapshots")))
        except OSError:
            res["anh_co_san"] = []
        return res

    hang_loat.dang_ky_routes(r)

    class XemChinhXacSchema(BaseModel):
        phien: str
        t_vao: float
        t_ra: float

    @r.post("/api/du-an/{pid}/xem-chinh-xac")
    def xem_chinh_xac(pid: str, body: XemChinhXacSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
            
        tl, _ = luu_tru.doc_timeline(folder)
        du_an = luu_tru.doc_duan(folder) or {}
        
        hd = r.hang_gpu
        def chay_xem(ctx):
            thu_muc = luu_tru._p(folder, luu_tru.CACHE, "xem_chinh_xac", ctx.viec.id)
            os.makedirs(thu_muc, exist_ok=True)
            out_file = os.path.join(thu_muc, f"{ctx.viec.id}.mp4")
            
            from orchestrator.editor import render, media
            ff = media.ffmpeg_exe()
            tc = {
                "do_phan_giai": "720p",
                "preset": "fast",
                "vung_vao": body.t_vao,
                "vung_ra": body.t_ra,
                "bo_ma_hoa": "x264"
            }
            kq = render.dung_lenh_xuat(folder, du_an, tl, tc, out_file, ff)
            
            with open(os.path.join(thu_muc, "loc.txt"), "w", encoding="utf-8") as fh:
                fh.write(kq["loc"])
            with open(os.path.join(thu_muc, "sub.ass"), "w", encoding="utf-8") as fh:
                fh.write(kq["ass"])
                
            code = ctx.chay_doc_dong(kq["cmd"], thu_muc, lambda line: None, log=os.path.join(thu_muc, "log.txt"))
            
            if code != 0 or not os.path.exists(out_file):
                raise RuntimeError(f"FFmpeg thoát với lỗi {code}. Lệnh: {kq['cmd']}")
                
            ts = media.do_thong_so(out_file)
            return {
                "url": f"/api/du-an/{pid}/cache/xem-chinh-xac/{ctx.viec.id}",
                "file": f"/cache/xem_chinh_xac/{ctx.viec.id}/{ctx.viec.id}.mp4",
                "thoi_luong": ts.get("thoi_luong", body.t_ra - body.t_vao)
            }

        from orchestrator.editor import hang_doi
        viec = hang_doi.Viec("xem_chinh_xac", chay_xem, du_an=folder, du_an_id=pid,
                             nhan=f"Xem chính xác {body.t_vao:.1f} - {body.t_ra:.1f}")
        hd.them(viec)
        return {"id": viec.id}

    @r.get("/api/du-an/{pid}/cache/xem-chinh-xac/{vid}")
    def get_xem_chinh_xac(pid: str, vid: str):
        folder = folder_cua(pid)
        file_path = luu_tru._p(folder, luu_tru.CACHE, "xem_chinh_xac", vid, f"{vid}.mp4")
        return gui_file(file_path, "video/mp4")

    _cache_nhac_nen = {"mtime": 0, "data": []}

    @r.get("/api/nhac-nen")
    def api_nhac_nen_list():
        from orchestrator.pipeline import AIVOICE_DIR
        songs_dir = os.path.join(AIVOICE_DIR, "apps", "MediaComposer", "resource", "songs")
        if not os.path.isdir(songs_dir):
            return []
        
        mtime = os.path.getmtime(songs_dir)
        if _cache_nhac_nen["mtime"] == mtime:
            return _cache_nhac_nen["data"]
            
        res = []
        for f in sorted(os.listdir(songs_dir)):
            if f.endswith(".mp3"):
                path = os.path.join(songs_dir, f)
                ts = media.do_thong_so(path)
                res.append({"ten": f, "thoi_luong": ts.get("thoi_luong", 0), "duong_dan": path})
        
        _cache_nhac_nen["mtime"] = mtime
        _cache_nhac_nen["data"] = res
        return res

    @r.get("/api/nhac-nen/{ten}")
    def api_nhac_nen_file(ten: str):
        from orchestrator.pipeline import AIVOICE_DIR
        if ".." in ten or "/" in ten or "\\" in ten or os.path.isabs(ten):
            raise HTTPException(400, detail="Tên không hợp lệ.")
        path = os.path.join(AIVOICE_DIR, "apps", "MediaComposer", "resource", "songs", ten)
        return gui_file(path, "audio/mpeg")

    return r

