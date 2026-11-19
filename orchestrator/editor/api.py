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
from orchestrator.editor import (ai_bridge, chuan_hoa_file, dao_nguoc, goi_du_an, hang_doi, khoang_lang, luu_tru, mau_nang_cao, media, nuong, render,
                                 srt, tai_len, thu_vien_am, workspace, xuat_tu_xa)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TIENG_THIET_BI = "tieng-thiet-bi"   # tên file tiếng tạm server dựng cho xuất trên thiết bị (ẩn khỏi "Bản đã xuất")
AI_MODE = os.environ.get("EDITOR_AI_MODE", "all" if os.environ.get("EDITOR_ENABLE_AI", "1").strip().lower() not in {"0", "false", "no"} else "off").strip().lower()
AI_ENABLED = AI_MODE != "off"
TAT_CA_AI = ["phu-de", "ocr", "dich", "long-tieng", "tach-giong", "lam-net", "can-gio", "tao-anh", "doc-van-ban"]


def tinh_nang_ai(che_do: str) -> List[str]:
    """EDITOR_AI_MODE → các tác vụ AI được bật. 'all' = hết, 'off' = không, còn lại là danh sách cách nhau
    bằng dấu phẩy (vd `translate,phu-de`; `translate` là tên cũ của `dich`)."""
    if che_do == "all":
        return list(TAT_CA_AI)
    if che_do == "off":
        return []
    ds = [{"translate": "dich"}.get(x.strip(), x.strip()) for x in che_do.split(",")]
    return [x for x in TAT_CA_AI if x in ds]


AI_TINH_NANG = tinh_nang_ai(AI_MODE)

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

class DaoNguocSchema(PhienSchema):
    vao: float = 0
    ra: float = 0

class KhoangLangSchema(BaseModel):
    vao: float = 0
    ra: float = 0
    nguong_db: float = -35
    toi_thieu: float = 0.6

class KhungDungSchema(PhienSchema):
    t: float = 0

class GoiSchema(BaseModel):
    kem_xuat: bool = False

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

class ThuVienAmSchema(PhienSchema):
    id: str

class VaoThuVienSchema(BaseModel):
    ten: str = ""
    nhom: str = "Của tôi"
    loai: str = "sfx"

class UrlSchema(PhienSchema):
    urls: List[str]

class TaiLenSchema(PhienSchema):
    ten: str
    kich_thuoc: int

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

class NuongSchema(PhienSchema):
    tuy_chon: Dict[str, Any] = {}
    n0: int = 0
    n1: int = 0
    lop_chu: bool = False
    doan: List[List[int]] = []

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

    # ------------------------------------------------------------ Gói dự án (.duan.zip) — mang dự án sang máy khác
    goi_viec: Dict[str, Dict[str, Any]] = {}          # pid → {trang_thai: dang|xong|loi, phan_tram, kich_thuoc, loi, file}

    def thu_muc_nhap_goi() -> str:
        return os.path.join(workspace.lay_workspace({"editor": _cfg_editor()}), ".nhap_goi")

    def file_nhap_goi(uid: str) -> str:
        if not uid or not all(c in "0123456789abcdef" for c in uid) or len(uid) != 32:
            raise HTTPException(status_code=400, detail="Mã tải lên không hợp lệ.")
        return os.path.join(thu_muc_nhap_goi(), uid + ".zip")

    @r.post("/api/du-an/nhap-goi")
    def import_package_start():
        import uuid
        os.makedirs(thu_muc_nhap_goi(), exist_ok=True)
        uid = uuid.uuid4().hex
        open(file_nhap_goi(uid), "wb").close()
        return {"uid": uid}

    @r.put("/api/du-an/nhap-goi/{uid}")
    async def import_package_chunk(uid: str, request: Request, vi_tri: int):
        """Nối một phần vào gói đang tải lên. `vi_tri` phải đúng bằng số byte đã nhận (gửi tuần tự, gửi lại được)."""
        path = file_nhap_goi(uid)
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Phiên tải gói đã hết — chọn lại file.")
        da_co = os.path.getsize(path)
        if vi_tri != da_co:
            raise HTTPException(status_code=409, detail=f"Sai vị trí: đã nhận {da_co} byte.")
        du_lieu = await request.body()
        with open(path, "ab") as f:
            f.write(du_lieu)
        return {"da_nhan": da_co + len(du_lieu)}

    @r.post("/api/du-an/nhap-goi/{uid}/xong")
    def import_package_finish(uid: str):
        path = file_nhap_goi(uid)
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Phiên tải gói đã hết — chọn lại file.")
        try:
            folder = goi_du_an.mo_goi(path, workspace.lay_workspace({"editor": _cfg_editor()}))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Không giải nén được gói: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)
        return the_cua(folder)

    @r.post("/api/du-an/{pid}/goi")
    def export_package(pid: str, body: GoiSchema):
        """Bắt đầu đóng gói dự án ở luồng nền (dự án vài GB mất cả phút) — hỏi tiến độ bằng GET cùng địa chỉ."""
        folder = folder_cua(pid)
        viec = goi_viec.get(pid)
        if viec and viec["trang_thai"] == "dang":
            return viec
        da = luu_tru.doc_duan(folder) or {}
        from orchestrator.storage import slugify
        dich = luu_tru._p(folder, luu_tru.CACHE, "goi", (slugify(str(da.get("name") or "")) or "du-an") + goi_du_an.DUOI)
        viec = {"trang_thai": "dang", "phan_tram": 0, "kich_thuoc": 0, "loi": "", "file": dich}
        goi_viec[pid] = viec

        def lam():
            try:
                viec["kich_thuoc"] = goi_du_an.dong_goi(folder, dich, lambda p: viec.update(phan_tram=int(p * 100)), body.kem_xuat)
                viec.update(trang_thai="xong", phan_tram=100)
            except Exception as e:                      # luồng nền: mọi lỗi phải tới được giao diện
                viec.update(trang_thai="loi", loi=str(e))
        threading.Thread(target=lam, daemon=True).start()
        return viec

    @r.get("/api/du-an/{pid}/goi")
    def export_package_status(pid: str):
        folder_cua(pid)
        return goi_viec.get(pid) or {"trang_thai": "chua", "phan_tram": 0, "kich_thuoc": 0, "loi": ""}

    @r.get("/api/du-an/{pid}/goi/tai")
    def export_package_download(pid: str):
        folder_cua(pid)
        viec = goi_viec.get(pid) or {}
        if viec.get("trang_thai") != "xong" or not os.path.isfile(viec.get("file") or ""):
            raise HTTPException(status_code=404, detail="Chưa có gói — bấm Xuất file dự án trước.")
        return FileResponse(viec["file"], media_type="application/zip", filename=os.path.basename(viec["file"]))

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

    # ------------------------------------------------------------ Thư viện âm thanh có sẵn (SFX + nhạc CC0)
    def ws_tv() -> str:
        return get_workspace()["duong_dan"]

    @r.get("/api/thu-vien-am")
    def sound_library():
        return {"muc": thu_vien_am.danh_muc_rieng(ws_tv()) + thu_vien_am.danh_muc()}

    @r.delete("/api/thu-vien-am/rieng/{tid}")
    def sound_library_delete(tid: str):
        if not thu_vien_am.xoa_rieng(ws_tv(), tid):
            raise HTTPException(status_code=404, detail="Không có âm thanh này trong thư viện của bạn.")
        return {"ok": True}

    @r.post("/api/du-an/{pid}/media/{mid}/vao-thu-vien")
    def sound_library_add(pid: str, mid: str, body: VaoThuVienSchema):
        """Lưu tiếng của một media (âm thanh hoặc video có tiếng) vào thư viện của tôi — dùng lại ở mọi dự án."""
        folder, m, path = media_path(pid, mid)
        if m.get("loai") not in ("audio", "video") or (m.get("loai") == "video" and m.get("co_am_thanh") is False):
            raise HTTPException(status_code=400, detail="Media này không có tiếng.")
        ff = media.ffmpeg_exe()
        if not ff or not os.path.isfile(path):
            raise HTTPException(status_code=500, detail="Thiếu ffmpeg hoặc file gốc.")
        try:
            return thu_vien_am.them_rieng(ws_tv(), path, body.ten or m.get("ten") or mid, body.nhom, body.loai, ff,
                                          m.get("thoi_luong") or 0)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.get("/api/thu-vien-am/tep/{rel:path}")
    def sound_library_file(rel: str):
        p = thu_vien_am.duong_dan(rel, ws_tv())
        if not p:
            raise HTTPException(status_code=404, detail="Không có file này trong thư viện.")
        return FileResponse(p, media_type="audio/mp4", headers={"Cache-Control": "public, max-age=604800"})

    @r.post("/api/du-an/{pid}/thu-vien-am")
    def sound_library_import(pid: str, body: ThuVienAmSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            return {"media": qlm.nhap(folder, pid, [thu_vien_am.ban_sao_de_nhap(body.id, ws_tv())])}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Tải file từ trình duyệt (điện thoại/máy khác) lên server theo từng phần — xem tai_len.py.
    ql_tai_len = tai_len.QuanLyTaiLen()

    def loi_tai_len(e: tai_len.LoiTaiLen) -> HTTPException:
        return HTTPException(status_code=e.ma, detail=str(e))

    def thu_muc_tai_len(folder: str) -> str:
        return os.path.join(folder, luu_tru.CACHE, "tai_len")

    @r.post("/api/du-an/{pid}/media/tai-len")
    def upload_start(pid: str, body: TaiLenSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        # Đuôi lạ (máy quay, iPhone không ghi đuôi…) vẫn cho tải; xong mới hỏi ffmpeg nội dung thật.
        if not chuan_hoa_file.nhan_duoc(body.ten):
            raise HTTPException(status_code=400, detail=f"Không nhận loại file này: {body.ten}")
        try:
            media.kiem_tra_dia(folder, body.kich_thuoc)
            uid = ql_tai_len.bat_dau(thu_muc_tai_len(folder), body.ten, body.kich_thuoc)
        except tai_len.LoiTaiLen as e:
            raise loi_tai_len(e)
        except ValueError as e:
            raise HTTPException(status_code=507, detail=str(e))
        return {"uid": uid}

    @r.get("/api/du-an/{pid}/media/tai-len/{uid}")
    def upload_status(pid: str, uid: str):
        try:
            return ql_tai_len.trang_thai(uid, thu_muc_tai_len(folder_cua(pid)))
        except tai_len.LoiTaiLen as e:
            raise loi_tai_len(e)

    @r.put("/api/du-an/{pid}/media/tai-len/{uid}")
    async def upload_chunk(pid: str, uid: str, request: Request, vi_tri: int, phien: str = ""):
        folder = folder_cua(pid)
        khoa_ghi(folder, phien)
        du_lieu = await request.body()
        try:
            return {"da_nhan": ql_tai_len.ghi_phan(uid, vi_tri, du_lieu, thu_muc_tai_len(folder))}
        except tai_len.LoiTaiLen as e:
            raise loi_tai_len(e)

    @r.post("/api/du-an/{pid}/media/tai-len/{uid}/xong")
    def upload_finish(pid: str, uid: str, body: PhienSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            path = chuan_hoa_file.chuan_hoa(ql_tai_len.hoan_tat(uid, thu_muc_tai_len(folder)))
        except tai_len.LoiTaiLen as e:
            raise loi_tai_len(e)
        try:
            return {"media": qlm.nhap(folder, pid, [path])}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @r.post("/api/du-an/{pid}/media/tai-len/{uid}/vao-xuat")
    def upload_finish_export(pid: str, uid: str, body: PhienSchema):
        """Bản xuất trên thiết bị đưa lên dự án: file tải xong vào xuat/<tên> (trùng tên thêm (2)…), KHÔNG nhập thành media."""
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        try:
            path = ql_tai_len.hoan_tat(uid, thu_muc_tai_len(folder))
        except tai_len.LoiTaiLen as e:
            raise loi_tai_len(e)
        goc, duoi = os.path.splitext(os.path.basename(path))
        goc = goc[len(uid) + 1:] if goc.startswith(uid + "_") else goc   # tai_len đặt tên "<uid>_<tên>"
        if duoi.lower() not in (".mp4", ".mov", ".m4v"):
            os.remove(path)
            raise HTTPException(status_code=400, detail="Chỉ nhận bản xuất video .mp4/.mov.")
        dich = render.ten_file_ra(folder, goc, duoi.lower())
        os.replace(path, dich)
        return {"ten": os.path.basename(dich), "kich_thuoc": os.path.getsize(dich)}

    @r.delete("/api/du-an/{pid}/media/tai-len/{uid}")
    def upload_cancel(pid: str, uid: str):
        ql_tai_len.huy(uid, thu_muc_tai_len(folder_cua(pid)))
        return {"status": "success"}

    @r.post("/api/du-an/{pid}/media/url")
    def import_url(pid: str, body: UrlSchema):
        from orchestrator.pipeline import AIVOICE_DIR, DOWNLOAD_ADAPTER, PYTHON_EXE, REPO_ROOT
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        g = load_global_config()
        cookies = ((g.get("download") or {}).get("cookies_file")
                   or (g.get("video") or {}).get("downloader_cookies") or "").strip()
        # Máy desktop có AIVoice/.venv thì dùng adapter đầy đủ; server (Linux, không AIVoice)
        # dùng CLI yt-dlp nhẹ chạy bằng chính Python của orchestrator.
        co_adapter = os.path.isfile(PYTHON_EXE) and os.path.isfile(DOWNLOAD_ADAPTER)
        dau_lenh = ([PYTHON_EXE, DOWNLOAD_ADAPTER] if co_adapter
                    else [sys.executable, "-m", "orchestrator.editor.tai_link_cli"])

        def lenh(tam: str) -> list:
            cmd = dau_lenh + ["--output-dir", tam, "--platform", "generic"]
            for u in body.urls:
                if (u or "").strip():
                    cmd += ["--url", u.strip()]
            return cmd + (["--cookies-file", cookies] if cookies else [])
        try:
            v = qlm.tai_url(folder, pid, body.urls, lenh, AIVOICE_DIR if co_adapter else REPO_ROOT)
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

    @r.post("/api/du-an/{pid}/media/{mid}/trich-am")
    def extract_audio(pid: str, mid: str, body: PhienSchema):
        """Trích tiếng của video ra media/<tên> (âm thanh).m4a — thành media âm thanh mới, tải về được."""
        folder, m, path = media_path(pid, mid)
        khoa_ghi(folder, body.phien)
        if m.get("loai") != "video" or m.get("co_am_thanh") is False:
            raise HTTPException(status_code=400, detail="Media này không phải video có tiếng.")
        ff = media.ffmpeg_exe()
        if not ff or not os.path.isfile(path):
            raise HTTPException(status_code=500, detail="Thiếu ffmpeg hoặc file video gốc.")
        ten = media.ten_dich(folder, f"{m.get('ten') or mid} (âm thanh).m4a", set())
        ra = os.path.join(folder, luu_tru.MEDIA_DIR, ten)
        ma = ["-c:a", "copy"] if m.get("codec_am") == "aac" else ["-c:a", "aac", "-b:a", "256k"]
        res = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", path, "-vn", "-map", "0:a:0", *ma, ra],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             errors="replace", timeout=1800, creationflags=media.NO_WINDOW)
        if res.returncode != 0 or not os.path.isfile(ra):
            if os.path.exists(ra):
                os.remove(ra)
            raise HTTPException(status_code=500, detail="ffmpeg lỗi: " + (res.stderr or "").strip()[-300:])
        return qlm.dang_ky_file(folder, pid, ra, tu_media=mid)

    @r.post("/api/du-an/{pid}/media/{mid}/dao-nguoc")
    def reverse_video(pid: str, mid: str, body: DaoNguocSchema):
        """Tua ngược đoạn [vao, ra] của video → media video mới (dùng lại file đã làm cho đúng đoạn đó)."""
        folder, m, path = media_path(pid, mid)
        khoa_ghi(folder, body.phien)
        if m.get("loai") != "video":
            raise HTTPException(status_code=400, detail="Chỉ tua ngược được clip video.")
        ff = media.ffmpeg_exe()
        if not ff or not os.path.isfile(path):
            raise HTTPException(status_code=500, detail="Thiếu ffmpeg hoặc file video gốc.")
        vao, ra = max(0.0, float(body.vao)), min(float(body.ra), float(m.get("thoi_luong") or body.ra))
        ten = f"{m.get('ten') or mid} (tua ngược {vao:.2f}-{ra:.2f}).mp4"
        dich = os.path.join(folder, luu_tru.MEDIA_DIR, ten)
        if not os.path.isfile(dich):
            try:
                dao_nguoc.tao(ff, path, dich, vao, ra, m.get("co_am_thanh") is not False)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                raise HTTPException(status_code=500, detail=str(e))
        return qlm.dang_ky_file(folder, pid, dich, tu_media=mid)

    @r.post("/api/du-an/{pid}/media/{mid}/khoang-lang")
    def find_silence(pid: str, mid: str, body: KhoangLangSchema):
        """Các khoảng lặng trong đoạn [vao, ra] của media (giây trong media) — cho nút Tự cắt khoảng lặng."""
        folder, m, path = media_path(pid, mid)
        if m.get("loai") not in ("video", "audio") or m.get("co_am_thanh") is False:
            raise HTTPException(status_code=400, detail="Media này không có tiếng.")
        ff = media.ffmpeg_exe()
        if not ff or not os.path.isfile(path):
            raise HTTPException(status_code=500, detail="Thiếu ffmpeg hoặc file gốc.")
        try:
            return {"khoang": khoang_lang.do(ff, path, max(0.0, body.vao), body.ra,
                                             max(-80.0, min(-10.0, body.nguong_db)), max(0.2, min(10.0, body.toi_thieu)))}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except (RuntimeError, OSError, subprocess.SubprocessError) as e:
            raise HTTPException(status_code=500, detail=str(e))

    @r.post("/api/du-an/{pid}/media/{mid}/khung-dung")
    def freeze_frame(pid: str, mid: str, body: KhungDungSchema):
        """Lấy khung hình tại giây `t` của video thành media ảnh PNG (đóng băng khung hình)."""
        folder, m, path = media_path(pid, mid)
        khoa_ghi(folder, body.phien)
        if m.get("loai") != "video":
            raise HTTPException(status_code=400, detail="Chỉ đóng băng được khung hình của video.")
        ff = media.ffmpeg_exe()
        if not ff or not os.path.isfile(path):
            raise HTTPException(status_code=500, detail="Thiếu ffmpeg hoặc file video gốc.")
        t = max(0.0, float(body.t))
        dich = os.path.join(folder, luu_tru.MEDIA_DIR, f"{m.get('ten') or mid} (khung {t:.3f}s).png")
        # Sát cuối video có thể không còn khung nào sau điểm seek → lùi dần cho tới khi lấy được.
        for lui in (0, 0.1, 0.5):
            if os.path.isfile(dich):
                break
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0.0, t - lui):.3f}", "-i", path,
                            "-frames:v", "1", dich], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
                           creationflags=media.NO_WINDOW)
        if not os.path.isfile(dich):
            raise HTTPException(status_code=500, detail="Không lấy được khung hình tại thời điểm này.")
        return qlm.dang_ky_file(folder, pid, dich, tu_media=mid)

    @r.get("/api/du-an/{pid}/media/{mid}/tieng-16k")
    def media_audio_16k(pid: str, mid: str):
        """Tiếng mono 16 kHz (WAV) cho Whisper chạy trong trình duyệt — khỏi tải cả video gốc về điện thoại."""
        folder, m, path = media_path(pid, mid)
        if m.get("loai") not in ("video", "audio") or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Media này không có tiếng.")
        ra = luu_tru._p(folder, luu_tru.CACHE, "tieng16k", f"{mid}.wav")
        if not os.path.isfile(ra) or os.path.getmtime(ra) < os.path.getmtime(path):
            from orchestrator.editor import whisper_truc_tiep
            os.makedirs(os.path.dirname(ra), exist_ok=True)
            try:
                whisper_truc_tiep.tach_tieng_16k(path, ra + ".tam.wav")
                os.replace(ra + ".tam.wav", ra)
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e))
        return gui_file(ra, "audio/wav")

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
    # Ngôn ngữ (giá trị ô Dịch sang) -> (mã ngôn ngữ, vùng ưu tiên) của giọng Edge.
    GIONG_EDGE = {
        "Vietnamese": ("vi", "vi-VN"), "Tiếng Việt": ("vi", "vi-VN"), "English": ("en", "en-US"),
        "Chinese": ("zh", "zh-CN"), "Japanese": ("ja", "ja-JP"), "Korean": ("ko", "ko-KR"),
        "Thai": ("th", "th-TH"), "Indonesian": ("id", "id-ID"), "Spanish": ("es", "es-ES"),
    }
    # Mất mạng không lấy được danh sách: vẫn có 2 giọng chuẩn để chọn.
    GIONG_EDGE_DU_PHONG = {
        "vi-VN": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"], "en-US": ["en-US-AriaNeural", "en-US-GuyNeural"],
        "zh-CN": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural"], "ja-JP": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
        "ko-KR": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"], "th-TH": ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"],
        "id-ID": ["id-ID-GadisNeural", "id-ID-ArdiNeural"], "es-ES": ["es-ES-ElviraNeural", "es-ES-AlvaroNeural"],
    }

    @r.get("/api/tts/giong")
    def get_tts_voices(engine: str = "edge", lang: str = ""):
        if engine == "edge":
            try:
                import asyncio
                import edge_tts
                async def _get():
                    return await edge_tts.list_voices()
                voices = asyncio.run(asyncio.wait_for(_get(), timeout=3.0))
                ten = [v["ShortName"] for v in voices]
            except Exception:
                ten = []
            # Chỉ giọng đúng ngôn ngữ đích (vùng phổ biến lên đầu): danh sách đủ 300+ giọng thì giọng cũ
            # (vd vi-VN) vẫn "hợp lệ" nên đổi Dịch sang Tiếng Anh xong vẫn lồng tiếng Anh bằng giọng Việt.
            ma = GIONG_EDGE.get(lang)
            if not ma:
                return {"giong": ten or GIONG_EDGE_DU_PHONG["vi-VN"]}
            hop = [t for t in ten if t.startswith(ma[0] + "-")]
            hop.sort(key=lambda t: not t.startswith(ma[1] + "-"))
            return {"giong": hop or GIONG_EDGE_DU_PHONG.get(ma[1], [])}
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
        from orchestrator.pipeline import AIVOICE_DIR, PYTHON_EXE
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
                from orchestrator.editor import dich
                bat_ollama = lambda: dam_bao_llm(ctx, g, tham_so, check_dich=True)  # noqa: E731
                # Engine Gemini: chỉ bật Ollama khi Gemini còn câu sót (thường không cần, đỡ chiếm GPU).
                if dich.chon_engine(tham_so, g.get("translate") or {}) not in dich.ENGINE_GEMINI:
                    bat_ollama()
                return dich.dich(ctx, folder, loai, m, tham_so, dam_bao_ollama=bat_ollama)
            viec.ham = lam
        elif loai == "phu-de" and not os.path.isfile(PYTHON_EXE):
            # Không có AIVoice (server Linux) → faster-whisper ngay trong tiến trình này.
            from orchestrator.editor import whisper_truc_tiep
            if not whisper_truc_tiep.co_san():
                raise ValueError("Máy chủ chưa cài faster-whisper (pip install faster-whisper).")
            viec.ham = lambda ctx: whisper_truc_tiep.chay(ctx, folder, m, tham_so)
        else:
            ke_hoach = ai_bridge.dung_lenh(folder, loai, m, tham_so, g, xay_lenh, viec.id)
            def lam(ctx):
                return ai_bridge.chay(ctx, folder, loai, m, ke_hoach, AIVOICE_DIR, tham_so,
                                      lambda f, wav, tu: qlm.dang_ky_file(f, pid, wav, tu))
            viec.ham = lam

        if tham_so.get("may") == "laptop" and loai in ("phu-de",):
            # Laptop GPU (run-worker.bat): pipeline AIVoice đầy đủ (PhoWhisper, Demucs, GPU). Không tới được → chạy ở đây.
            cau_hinh = _cfg_editor().get("may_xuat") or {}
            tai_cho = viec.ham

            def lam_laptop(ctx):
                try:
                    may = xuat_tu_xa.MayXuat(cau_hinh.get("url", ""), cau_hinh.get("token", ""))
                    kq = may.chay_ai(luu_tru.duong_dan_media(folder, m["file"]), loai, tham_so,
                                     lambda p, t: ctx.bao(p, t), lambda: ctx.da_huy)
                    return {**kq, "loai": loai, "media": m["id"], "may": "laptop"}
                except InterruptedError:
                    raise hang_doi.DaHuy()
                except xuat_tu_xa.LoiMayXuat as e:
                    ctx.bao(0, f"{e} — chạy bằng server…")
                    return tai_cho(ctx)
            viec.ham = lam_laptop
            viec.nhan += " (laptop)"

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
        if not AI_ENABLED:
            raise HTTPException(status_code=503, detail="Các tính năng AI đang tắt trên máy chủ này; chỉnh sửa và xuất video vẫn dùng được.")
        if loai not in AI_TINH_NANG and loai in TAT_CA_AI:
            raise HTTPException(status_code=503, detail="Máy chủ này không bật tác vụ AI này (chỉ bật: "
                                + ", ".join(ai_bridge.TEN.get(x, x) for x in AI_TINH_NANG) + ").")
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

    # --------------------------------------------------------------- LUT màu (.cube)
    def thu_muc_lut(pid: str) -> str:
        return os.path.join(folder_cua(pid), luu_tru.LUT_DIR)

    @r.get("/api/du-an/{pid}/lut")
    def list_lut(pid: str):
        d = thu_muc_lut(pid)
        return {"lut": sorted(f for f in os.listdir(d) if f.lower().endswith(".cube")) if os.path.isdir(d) else []}

    @r.get("/api/du-an/{pid}/lut/{ten}")
    def get_lut(pid: str, ten: str):
        path = os.path.join(thu_muc_lut(pid), os.path.basename(ten))
        if not os.path.isfile(path):
            raise HTTPException(status_code=404, detail=f"Không có LUT {ten}.")
        return FileResponse(path, media_type="text/plain")

    @r.post("/api/du-an/{pid}/lut")
    async def upload_lut(pid: str, request: Request, ten: str, phien: str = ""):
        folder = folder_cua(pid)
        khoa_ghi(folder, phien)
        du_lieu = await request.body()
        if len(du_lieu) > 64 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File LUT quá lớn (tối đa 64 MB).")
        noi = du_lieu.decode("utf-8", errors="replace")
        try:
            mau_nang_cao.doc_cube(noi)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        goc = os.path.splitext(tai_len.ten_an_toan(ten))[0]
        ten_an = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "-_") else "_" for ch in goc)[:60] or "lut"
        os.makedirs(thu_muc_lut(pid), exist_ok=True)
        with open(os.path.join(thu_muc_lut(pid), ten_an + ".cube"), "w", encoding="utf-8", newline="") as fh:
            fh.write(noi)
        return {"ten": ten_an + ".cube"}

    # --------------------------------------------------------------- Máy xuất từ xa (laptop GPU)
    @r.get("/api/may-xuat")
    def get_remote_exporter():
        c = _cfg_editor().get("may_xuat") or {}
        return {"url": c.get("url", ""), "co_token": bool(c.get("token"))}

    @r.post("/api/may-xuat")
    def set_remote_exporter(body: Dict[str, Any]):
        """Lưu địa chỉ/mã (mã để trống = giữ mã cũ) rồi thử kết nối."""
        cu_ = _cfg_editor().get("may_xuat") or {}
        moi = {"url": (body.get("url") or "").strip().rstrip("/"), "token": (body.get("token") or "").strip() or cu_.get("token", "")}
        if moi["url"] and not moi["url"].startswith(("http://", "https://")):
            moi["url"] = "http://" + moi["url"]
        _luu_cfg_editor(may_xuat=moi)
        try:
            return {"ok": True, **xuat_tu_xa.MayXuat(moi["url"], moi["token"]).ping()}
        except (xuat_tu_xa.LoiMayXuat, RuntimeError) as e:
            return {"ok": False, "loi": str(e)}

    # --------------------------------------------------------------- Xuất
    nvenc: Dict[str, bool] = {}

    def ghi_tep_phu(thu_muc: str, kq: Dict[str, Any]) -> None:
        """File phụ mà filter gọi bằng tên tương đối (LUT gộp của từng clip)."""
        for ten, noi in (kq.get("tep") or {}).items():
            with open(os.path.join(thu_muc, ten), "w", encoding="utf-8") as fh:
                fh.write(noi)

    def xep_xuat(folder: str, pid: str, tuy_chon: Dict[str, Any]) -> Tuple[hang_doi.Viec, str]:
        tc = dict(tuy_chon or {})
        ff = media.ffmpeg_exe()
        if not ff:
            raise RuntimeError("Không tìm thấy ffmpeg (imageio_ffmpeg).")
        may, canh_bao = None, ""
        if tc.get("may_xuat") == "laptop":
            cau_hinh = _cfg_editor().get("may_xuat") or {}
            try:
                may = xuat_tu_xa.MayXuat(cau_hinh.get("url", ""), cau_hinh.get("token", ""))
                tc["bo_ma_hoa"] = "nvenc" if may.ping().get("nvenc") else "x264"
            except (xuat_tu_xa.LoiMayXuat, RuntimeError) as e:
                may, canh_bao = None, f"{e} — xuất bằng server"
                tc["bo_ma_hoa"] = "auto"
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
                             nhan=f"Xuất {os.path.basename(ra)}" + (" (laptop)" if may else f" ({canh_bao})" if canh_bao else ""),
                             tham_so={k: v for k, v in tc.items()})

        def lam(ctx):
            kq_dung, bo = kq, tc["bo_ma_hoa"]
            if may is not None:
                try:
                    ctx.bao(0, "Chuẩn bị xuất trên laptop…")
                    may.xuat(kq, ra, lambda p, t: ctx.bao(p, t), lambda: ctx.da_huy)
                    return ket_qua(kq, "laptop " + tc["bo_ma_hoa"])
                except InterruptedError:
                    raise hang_doi.DaHuy()
                except xuat_tu_xa.LoiMayXuat as e:
                    tc_may = {**tc, "bo_ma_hoa": "nvenc" if nvenc.get("co") else "x264"}
                    kq_dung, bo = render.dung_lenh_xuat(folder, du_an, tl, tc_may, ra, ff), tc_may["bo_ma_hoa"]
                    ctx.bao(0, f"{e} — xuất bằng server…")
            thu_muc = luu_tru._p(folder, luu_tru.CACHE, "xuat", viec.id)
            os.makedirs(thu_muc, exist_ok=True)
            with open(os.path.join(thu_muc, "loc.txt"), "w", encoding="utf-8") as fh:
                fh.write(kq_dung["loc"])
            with open(os.path.join(thu_muc, "sub.ass"), "w", encoding="utf-8") as fh:
                fh.write(kq_dung["ass"])
            ghi_tep_phu(thu_muc, kq_dung)
            T = max(0.001, float(kq_dung["thoi_luong"]))
            ctx.bao(0, f"Đang xuất {kq_dung['kich_thuoc'][0]}×{kq_dung['kich_thuoc'][1]} ({bo})…")
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
                code = ctx.chay_doc_dong(kq_dung["cmd"], thu_muc, dong, log=os.path.join(thu_muc, "log.txt"))
            except hang_doi.DaHuy:
                if os.path.exists(ra):
                    os.remove(ra)
                raise

            if code != 0 and "-hwaccel" in kq_dung["cmd"]:
                cmd2 = []
                skip_next = False
                for x in kq_dung["cmd"]:
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
            return ket_qua(kq_dung, bo)

        def ket_qua(k, bo_ma_hoa):
            srt_rel = ""
            if tc.get("xuat_srt"):
                noi = render.xuat_srt(tl)
                if noi:
                    p_srt = os.path.splitext(ra)[0] + ".srt"
                    with open(p_srt, "w", encoding="utf-8") as fh:
                        fh.write(noi)
                    srt_rel = os.path.relpath(p_srt, folder).replace("\\", "/")
            return {"file": os.path.relpath(ra, folder).replace("\\", "/"), "thoi_luong": k["thoi_luong"],
                    "kich_thuoc": k["kich_thuoc"], "bo_ma_hoa": bo_ma_hoa, "srt": srt_rel,
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

    # Bản xuất nằm trong <dự án>/xuat/ trên SERVER — bản web/điện thoại cần tải về (mở thư mục chỉ có ở desktop).
    @r.get("/api/du-an/{pid}/xuat")
    def list_exports(pid: str):
        d = os.path.join(folder_cua(pid), luu_tru.XUAT_DIR)
        ds = []
        if os.path.isdir(d):
            for ten in os.listdir(d):
                p = os.path.join(d, ten)
                if (os.path.isfile(p) and not ten.startswith(".") and TIENG_THIET_BI not in ten
                        and os.path.splitext(ten)[1].lower() in (".mp4", ".m4a", ".mov", ".srt")):
                    ds.append({"ten": ten, "kich_thuoc": os.path.getsize(p), "luc": int(os.path.getmtime(p))})
        return {"ds": sorted(ds, key=lambda x: -x["luc"])}

    @r.get("/api/du-an/{pid}/xuat/tai")
    def download_export(pid: str, ten: str):
        d = os.path.abspath(os.path.join(folder_cua(pid), luu_tru.XUAT_DIR))
        p = os.path.abspath(os.path.join(d, ten))
        if os.path.dirname(p) != d or not os.path.isfile(p):
            raise HTTPException(status_code=404, detail="Không có bản xuất này.")
        mt = mimetypes.guess_type(p)[0] or "application/octet-stream"
        return FileResponse(p, media_type=mt, filename=os.path.basename(p))   # Content-Disposition: attachment (UTF-8)

    @r.delete("/api/du-an/{pid}/xuat/tai")
    def delete_device_audio(pid: str, ten: str):
        """Xuất trên thiết bị: server dựng TIẾNG (chi_am_thanh, tên chứa TIENG_THIET_BI) → máy tải về ghép xong thì xoá.
        Chỉ xoá được file tiếng tạm này, không xoá bản xuất thật."""
        d = os.path.abspath(os.path.join(folder_cua(pid), luu_tru.XUAT_DIR))
        p = os.path.abspath(os.path.join(d, ten))
        if os.path.dirname(p) != d or TIENG_THIET_BI not in os.path.basename(p) or not os.path.isfile(p):
            raise HTTPException(status_code=404, detail="Không có file tiếng tạm này.")
        os.remove(p)
        return {"ok": True}

    # ---- Xuất trên thiết bị: server nướng lớp chữ + đoạn máy không ghép được (nuong.py)
    @r.post("/api/du-an/{pid}/nuong")
    def bake_start(pid: str, body: NuongSchema):
        folder = folder_cua(pid)
        khoa_ghi(folder, body.phien)
        ff = media.ffmpeg_exe()
        if not ff:
            raise HTTPException(status_code=400, detail="Không tìm thấy ffmpeg.")
        if not (0 <= body.n0 < body.n1) or any(len(d) != 2 or not (0 <= d[0] < d[1]) for d in body.doan):
            raise HTTPException(status_code=400, detail="Đoạn nướng không hợp lệ.")
        if not body.lop_chu and not body.doan:
            raise HTTPException(status_code=400, detail="Không có gì để nướng.")
        nuong.don_cu(folder)
        du_an = luu_tru.doc_duan(folder) or {}
        tl, _ = luu_tru.doc_timeline(folder)
        tc = {k: body.tuy_chon.get(k) for k in ("do_phan_giai", "fps")}
        try:
            if tc["fps"] is not None and not (1 <= float(tc["fps"]) <= 240):
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="fps không hợp lệ.")
        if "co" not in nvenc:
            nvenc["co"] = render.co_nvenc(ff)
        tc["bo_ma_hoa"] = "nvenc" if nvenc["co"] else "x264"
        viec = hang_doi.Viec("nuong", lambda ctx: None, du_an=folder, du_an_id=pid, nhan="Nướng cho xuất trên thiết bị")
        tm = nuong.thu_muc(folder, viec.id)
        viec.ham = lambda ctx: {**nuong.chay(ctx, folder, du_an, tl, tc, body.n0, body.n1, body.lop_chu,
                                             body.doan, ff, tm), "id": viec.id}
        hang_gpu.them(viec)
        return {"viec": viec.to_dict()}

    @r.get("/api/du-an/{pid}/nuong/{vid}/{ten}")
    def bake_file(pid: str, vid: str, ten: str):
        if not nuong.TEN_FILE.match(vid) or not nuong.TEN_FILE.match(ten):
            raise HTTPException(status_code=404, detail="Không có file này.")
        p = os.path.join(nuong.thu_muc(folder_cua(pid), vid), ten)
        if not os.path.isfile(p):
            raise HTTPException(status_code=404, detail="Không có file này.")
        return FileResponse(p, media_type=mimetypes.guess_type(p)[0] or "application/octet-stream")

    @r.delete("/api/du-an/{pid}/nuong/{vid}")
    def bake_delete(pid: str, vid: str):
        if nuong.TEN_FILE.match(vid):
            import shutil
            shutil.rmtree(nuong.thu_muc(folder_cua(pid), vid), ignore_errors=True)
        return {"ok": True}

    @r.post("/api/du-an/{pid}/xuat/luu-ra")
    def save_export_to(pid: str, body: Dict[str, Any]):
        """App desktop (WebView2 không tải file như trình duyệt): chép bản xuất vào thư mục người dùng chọn
        (hộp thoại /api/system/pick-files). Trùng tên thì thêm (2), (3)… — không ghi đè."""
        ten, thu_muc = str(body.get("ten") or ""), str(body.get("thu_muc") or "")
        d = os.path.abspath(os.path.join(folder_cua(pid), luu_tru.XUAT_DIR))
        p = os.path.abspath(os.path.join(d, ten))
        if os.path.dirname(p) != d or not os.path.isfile(p):
            raise HTTPException(status_code=404, detail="Không có bản xuất này.")
        if not thu_muc or not os.path.isdir(thu_muc):
            raise HTTPException(status_code=400, detail="Thư mục đích không tồn tại.")
        goc, duoi = os.path.splitext(os.path.basename(p))
        dich, n = os.path.join(thu_muc, goc + duoi), 2
        while os.path.exists(dich):
            dich, n = os.path.join(thu_muc, f"{goc} ({n}){duoi}"), n + 1
        try:
            import shutil
            shutil.copyfile(p, dich)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Không chép được: {e}")
        return {"duong_dan": dich}

    r.hang_gpu = hang_gpu   # type: ignore[attr-defined] — cho GĐ 1 và test
    r.qlm = qlm             # type: ignore[attr-defined]
    r.ql_tai_len = ql_tai_len  # type: ignore[attr-defined]
    
    from orchestrator.editor import hang_loat
    @r.get("/api/ai/models")
    def ai_models():
        if not AI_ENABLED:
            return {"enabled": False}
        if AI_MODE != "all":
            return {"enabled": True, "features": AI_TINH_NANG}
        from orchestrator.pipeline import AIVOICE_DIR
        res = {"enabled": True, "features": list(TAT_CA_AI)}
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
            ghi_tep_phu(thu_muc, kq)
                
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

