"""Nơi làm việc: một thư mục chứa các dự án, chọn 1 lần ở ⚙ (`global_config › editor.workspace`).

    <Nơi làm việc>/
        _dung_chung/          kho media Dùng chung (GĐ 2)
        Du_an_A/.duan.json    mỗi thư mục con có `.duan.json` là một dự án

Dự án nằm NGOÀI Nơi làm việc vẫn mở được ("Nhập dự án") — đường dẫn ghi vào
`editor.du_an_ngoai[]` để trang chủ hiện cùng các dự án khác.

Mỗi dự án có `id` riêng trong `.duan.json`. Người dùng chép nguyên thư mục dự án
trong Explorer thì bản chép mang TRÙNG id — lúc quét phát hiện và cấp id mới cho
bản chép, nếu không mở dự án này lại vào nhầm dự án kia.
"""
import datetime
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from orchestrator import project
from orchestrator.editor import luu_tru
from orchestrator.storage import slugify

MAU_THONG_SO = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
}
FPS_HOP_LE = (23.976, 24, 25, 29.97, 30, 50, 60)


def workspace_mac_dinh() -> str:
    """`~/CaoDichVideo` — cố ý KHÔNG đặt trong Videos/Documents: máy bật Controlled Folder
    Access của Windows Defender chặn python.exe ghi vào các thư mục đó (xem `tao_thu_muc`)."""
    return os.path.join(os.path.expanduser("~"), "CaoDichVideo")


CFA_GIAI_THICH = (
    "Thường là do Windows Defender bật \"Controlled folder access\" (chống ransomware) — nó chặn "
    "ghi vào Videos, Documents, Pictures… Cách sửa: để dự án ở thư mục khác (vd C:\\Users\\<tên>\\CaoDichVideo "
    "hoặc ổ D:), hoặc vào Windows Security → Virus & threat protection → Ransomware protection → "
    "Allow an app through Controlled folder access → thêm python.exe, pythonw.exe (AIVoice\\.venv\\Scripts) "
    "và ffmpeg.exe.")


def giai_thich_loi_ghi(loi: str) -> str:
    """Thêm giải thích Controlled Folder Access vào lỗi WinError 2/5 lúc ghi (lỗi gốc không nói gì)."""
    if os.name == "nt" and ("WinError 2]" in loi or "WinError 5]" in loi) and "Controlled" not in loi:
        return f"Windows không cho ghi vào thư mục dự án. {CFA_GIAI_THICH}\nChi tiết: {loi}"
    return loi


def tao_thu_muc(path: str) -> None:
    """os.makedirs, nhưng báo rõ khi bị Controlled Folder Access chặn.

    Tính năng chống ransomware của Windows Defender chặn app lạ ghi vào Videos,
    Documents, Pictures… và trả về lỗi GIẢ "không tìm thấy file" (WinError 2) dù
    thư mục cha có thật — người dùng đọc lỗi đó không thể đoán ra nguyên nhân.
    """
    try:
        os.makedirs(path, exist_ok=True)
    except FileNotFoundError:
        cha = os.path.dirname(os.path.abspath(path))
        while cha and not os.path.exists(cha) and os.path.dirname(cha) != cha:
            cha = os.path.dirname(cha)
        if os.name == "nt" and os.path.isdir(cha):
            raise ValueError(f"Windows không cho app ghi vào '{path}'. {CFA_GIAI_THICH}") from None
        raise


def lay_workspace(cfg: Dict[str, Any]) -> str:
    path = ((cfg.get("editor") or {}).get("workspace") or "").strip()
    return os.path.abspath(path or workspace_mac_dinh())


def chuan_thong_so(ts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ts = dict(ts or {})
    try:
        rong, cao = int(ts.get("rong") or 1920), int(ts.get("cao") or 1080)
    except (TypeError, ValueError):
        raise ValueError("Độ phân giải phải là số.")
    if not (16 <= rong <= 8192 and 16 <= cao <= 8192):
        raise ValueError("Độ phân giải phải trong khoảng 16–8192 px.")
    # yuv420p không nhận cạnh lẻ — ffmpeg sẽ bỏ cuộc lúc xuất.
    rong, cao = rong - rong % 2, cao - cao % 2
    try:
        fps = float(ts.get("fps") or 30)
    except (TypeError, ValueError):
        raise ValueError("FPS phải là số.")
    if fps not in FPS_HOP_LE:
        raise ValueError(f"FPS phải là một trong: {', '.join(str(f) for f in FPS_HOP_LE)}.")
    return {"rong": rong, "cao": cao, "fps": int(fps) if fps.is_integer() else fps,
            "ti_le": luu_tru._ti_le(rong, cao), "mau_nen": ts.get("mau_nen") or "#000000",
            "theo_video_dau": bool(ts.get("theo_video_dau"))}


# ------------------------------------------------------------------------ Quét
def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def the_du_an(folder: str, data: Dict[str, Any], ngoai: bool = False) -> Dict[str, Any]:
    """Thông tin cho thẻ trên trang chủ — đọc `.duan.json` + mtime, KHÔNG đọc timeline."""
    folder = os.path.abspath(folder)
    sua = max(_mtime(luu_tru.duong_dan_duan(folder)),
              _mtime(os.path.join(folder, luu_tru.THU_MUC_EDITOR, "timeline.json")))
    ts = data.get("thong_so") or {}
    schema = int(data.get("schema") or 1)
    so_media = len(data.get("media") or []) if schema >= 2 else len(data.get("videos") or [])
    bia = data.get("anh_bia") or ""
    return {
        "id": data.get("id") or "", "name": data.get("name") or os.path.basename(folder),
        "mo_ta": data.get("mo_ta") or "", "folder": folder, "thong_so": ts, "schema": schema,
        "tao_luc": data.get("tao_luc") or data.get("created_at") or "",
        "sua_luc": datetime.datetime.fromtimestamp(sua).isoformat(timespec="seconds") if sua else "",
        "sua_ts": sua, "co_anh_bia": bool(bia) and os.path.exists(os.path.join(folder, *bia.split("/"))),
        "so_media": so_media, "ngoai": ngoai, "can_nang_cap": schema < luu_tru.SCHEMA,
    }


def quet(workspace: str, ngoai: List[str]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """(thẻ dự án mới sửa trước, bảng id → thư mục)."""
    ung_vien: List[Tuple[str, bool]] = []
    if os.path.isdir(workspace):
        for ten in sorted(os.listdir(workspace)):
            if ten.startswith((".", "_")):
                continue
            path = os.path.join(workspace, ten)
            if os.path.isdir(path) and os.path.exists(luu_tru.duong_dan_duan(path)):
                ung_vien.append((path, False))
    da = {os.path.normcase(p) for p, _ in ung_vien}
    for p in ngoai or []:
        p = os.path.abspath(p)
        if os.path.normcase(p) not in da and os.path.exists(luu_tru.duong_dan_duan(p)):
            ung_vien.append((p, True))
            da.add(os.path.normcase(p))

    the, bang = [], {}
    for folder, la_ngoai in ung_vien:
        data = luu_tru.doc_duan(folder)
        if data is None:
            continue
        pid = data.get("id") or ""
        if not pid or pid in bang:
            pid = uuid.uuid4().hex[:8]

            def dat_id(d, pid=pid):
                d["id"] = pid
            try:
                luu_tru.sua_duan(folder, dat_id)
            except (OSError, ValueError):
                continue
            data["id"] = pid
        bang[pid] = folder
        the.append(the_du_an(folder, data, la_ngoai))
    the.sort(key=lambda t: t["sua_ts"], reverse=True)
    return the, bang


# --------------------------------------------------------------- Tạo / nhập / xoá
def tao(workspace: str, ten: str, thong_so: Optional[Dict[str, Any]] = None, mo_ta: str = "") -> Dict[str, Any]:
    ten = (ten or "").strip()
    if not ten:
        raise ValueError("Phải đặt tên dự án.")
    ts = chuan_thong_so(thong_so)
    tao_thu_muc(workspace)
    goc = slugify(ten, 60)
    folder, n = os.path.join(workspace, goc), 1
    while os.path.exists(folder):
        n += 1
        folder = os.path.join(workspace, f"{goc}_{n}")
    tao_thu_muc(folder)
    luu_tru.tao_thu_muc_con(folder)
    bay_gio = luu_tru._iso()
    data = {
        "schema": luu_tru.SCHEMA, "id": uuid.uuid4().hex[:8], "name": ten, "mo_ta": (mo_ta or "").strip(),
        "tao_luc": bay_gio, "sua_luc": bay_gio, "thong_so": ts,
        "media": [], "dung_chung": [], "tac_vu": [], "anh_bia": "",
    }
    luu_tru.ghi_duan(folder, data)
    tl = luu_tru.timeline_rong()
    luu_tru.ghi_nguyen_tu(os.path.join(folder, luu_tru.THU_MUC_EDITOR, "timeline.json"), tl)
    return {**data, "folder": folder}


def nhap(folder: str, do_thong_so=None) -> Dict[str, Any]:
    """Đưa một thư mục vào danh sách dự án.

    - Đã là dự án schema 2: dùng luôn.
    - Dự án cũ (schema 1): nâng cấp tại chỗ, không di chuyển file.
    - Thư mục video thường: đánh dấu dự án (GIỮ NGUYÊN tên file) rồi nâng cấp.
    """
    folder = os.path.abspath(folder or "")
    if not os.path.isdir(folder):
        raise ValueError(f"Không có thư mục: {folder}")
    if not project.da_init(folder):
        project.init(folder, os.path.basename(folder), doi_ten=False)
    return luu_tru.nang_cap(folder, do_thong_so)


def trong_workspace(workspace: str, folder: str) -> bool:
    ws = os.path.normcase(os.path.abspath(workspace))
    f = os.path.normcase(os.path.abspath(folder))
    try:
        return os.path.commonpath([ws, f]) == ws and f != ws
    except ValueError:
        return False


def xoa(folder: str) -> None:
    """Chuyển cả thư mục dự án vào Thùng rác (không xoá hẳn)."""
    from send2trash import send2trash
    send2trash(os.path.abspath(folder))


def sua(folder: str, ten: Optional[str] = None, mo_ta: Optional[str] = None,
        thong_so: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ts = chuan_thong_so(thong_so) if thong_so is not None else None

    def ham(data):
        if ten is not None:
            if not ten.strip():
                raise ValueError("Tên dự án không được trống.")
            data["name"] = ten.strip()
        if mo_ta is not None:
            data["mo_ta"] = mo_ta.strip()
        if ts is not None:
            data["thong_so"] = ts
        return dict(data)
    return luu_tru.sua_duan(folder, ham)
