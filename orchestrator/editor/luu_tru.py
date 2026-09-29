"""Lưu tiến độ dự án: đóng app lúc nào (kể cả tắt ngang, mất điện) mở lại vẫn y như cũ.

    <dự án>/
        .duan.json             danh tính + thông số + danh sách media (ÍT đổi)
        .duan/
            timeline.json      tiến độ dựng — đổi liên tục, có `phien_ban`
            ui.json            trạng thái màn hình editor
            hoan_tac.json      ngăn hoàn tác, ghi kèm `phien_ban` của timeline nó khớp
            lich_su/           tu_dong_*.json (xoay vòng) + luu_*.json (lưu tay, không xoá)
            lock               {phien, pid, luc_mo, nhip_cuoi} — chống 2 cửa sổ cùng sửa

Mọi file JSON ghi qua `ghi_nguyen_tu`: ghi file tạm → fsync → os.replace, nên tắt
ngang giữa lúc ghi chỉ mất lần ghi đó chứ không bao giờ để lại file nửa vời.

Khoá dùng MÃ PHIÊN + heartbeat chứ không dùng pid: mọi cửa sổ/tab đều nói chuyện
với cùng một server uvicorn nên cùng pid, và Windows còn cấp lại pid cũ cho tiến
trình khác.

Module chỉ đụng hệ thống tệp — không ffmpeg, không mạng — nên kiểm thử trọn vẹn.
"""
import copy
import datetime
import json
import os
import re
import shutil
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

from orchestrator.storage import natural_key, slugify

MARKER = ".duan.json"
THU_MUC_EDITOR = ".duan"
LICH_SU = "lich_su"
CACHE = "cache"
MEDIA_DIR = "media"
PHU_DE_DIR = "phu_de"
LONG_TIENG_DIR = "long_tieng"
XUAT_DIR = "xuat"
SCHEMA = 2

KHOA_HET_HAN = 45.0        # giây không có heartbeat thì coi khoá là của cửa sổ đã chết
MAY_CHU = uuid.uuid4().hex  # mã của lần chạy server này (mỗi lần mở app là một server mới)
CHU_KY_TU_DONG = 300.0     # 5 phút có thay đổi thì chụp một bản lịch sử tự động
SO_BAN_TU_DONG = 20
SO_BUOC_HOAN_TAC = 50

_TEN_BAN = re.compile(r"^(tu_dong|luu)_(\d{8}_\d{6})(_\d+)?(_[a-z0-9_-]+)?\.json$")

# Một khoá ghi cho mỗi dự án: đọc-so-ghi phiên bản phải liền một mạch, và
# luồng nền (chép media, tạo thumbnail) cũng sửa `.duan.json` cùng lúc với API.
_khoa_ghi: Dict[str, threading.RLock] = defaultdict(threading.RLock)
_khoa_bang = threading.Lock()


def _gio() -> float:
    """Đồng hồ của module — test thay bằng đồng hồ giả."""
    return time.time()


def _khoa(folder: str) -> threading.RLock:
    key = os.path.normcase(os.path.abspath(folder))
    with _khoa_bang:
        return _khoa_ghi[key]


class XungDotPhienBan(Exception):
    """Timeline trên đĩa đã mới hơn bản client đang sửa (thường là cửa sổ thứ hai)."""

    def __init__(self, hien_tai: int):
        super().__init__(f"Dự án đã được sửa ở nơi khác (phiên bản {hien_tai}).")
        self.hien_tai = hien_tai


class KhongGiuKhoa(Exception):
    """Phiên này không giữ khoá dự án — đang mở chỉ đọc."""


# ------------------------------------------------------------ Ghi/đọc an toàn
def ghi_nguyen_tu(path: str, data: Any) -> None:
    """Ghi JSON sao cho file đích luôn là bản cũ nguyên vẹn hoặc bản mới nguyên vẹn."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{uuid.uuid4().hex[:6]}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        # Windows: trình quét virus/Windows Search có thể đang mở file đích vài
        # mili-giây — thử lại thay vì báo lỗi lưu cho người dùng.
        for lan in range(6):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if lan == 5:
                    raise
                time.sleep(0.05 * (lan + 1))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


class _Hong:
    """Đánh dấu file có mà đọc không ra JSON."""


HONG = _Hong()


def doc_json(path: str) -> Any:
    """None nếu không có file, `HONG` nếu có mà hỏng."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return HONG


def thu_muc_editor(folder: str) -> str:
    return os.path.join(os.path.abspath(folder), THU_MUC_EDITOR)


def _p(folder: str, *parts: str) -> str:
    return os.path.join(thu_muc_editor(folder), *parts)


def tao_thu_muc_con(folder: str) -> None:
    folder = os.path.abspath(folder)
    for sub in (MEDIA_DIR, PHU_DE_DIR, LONG_TIENG_DIR, XUAT_DIR):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
    for sub in (LICH_SU, os.path.join(CACHE, "thumbs"), os.path.join(CACHE, "proxy")):
        os.makedirs(_p(folder, sub), exist_ok=True)
    _an_thu_muc(thu_muc_editor(folder))


def _an_thu_muc(path: str) -> None:
    """Ẩn `.duan/` trên Windows — người dùng không cần mở, tránh xoá nhầm."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)  # FILE_ATTRIBUTE_HIDDEN
    except (OSError, AttributeError):
        pass


# ------------------------------------------------------------------ .duan.json
def duong_dan_duan(folder: str) -> str:
    return os.path.join(os.path.abspath(folder), MARKER)


def doc_duan(folder: str) -> Optional[Dict[str, Any]]:
    data = doc_json(duong_dan_duan(folder))
    if not isinstance(data, dict):
        return None
    return data


def ghi_duan(folder: str, data: Dict[str, Any]) -> None:
    data = {k: v for k, v in data.items() if k != "folder"}
    with _khoa(folder):
        ghi_nguyen_tu(duong_dan_duan(folder), data)


def sua_duan(folder: str, ham: Callable[[Dict[str, Any]], Any]) -> Any:
    """Đọc → sửa → ghi `.duan.json` liền một mạch (API và luồng nền cùng sửa)."""
    with _khoa(folder):
        data = doc_duan(folder)
        if data is None:
            raise ValueError(f"Thư mục '{folder}' chưa phải là dự án.")
        ket_qua = ham(data)
        data["sua_luc"] = _iso()
        ghi_nguyen_tu(duong_dan_duan(folder), data)
        return ket_qua


def _iso(t: Optional[float] = None) -> str:
    return datetime.datetime.fromtimestamp(_gio() if t is None else t).isoformat(timespec="seconds")


def duong_dan_media(folder: str, rel: str) -> str:
    """Đường dẫn tuyệt đối của một file ghi TƯƠNG ĐỐI trong dự án."""
    folder = os.path.abspath(folder)
    goc = (rel or "").replace("\\\\", "/")
    

    rel = goc.strip("/")
    if not rel or ":" in rel or goc.startswith("/"):
        raise ValueError(f"Đường dẫn ngoài dự án: {goc}")
    path = os.path.abspath(os.path.join(folder, *rel.split("/")))
    if os.path.commonpath([folder, path]) != folder:
        raise ValueError(f"Đường dẫn ngoài dự án: {rel}")
    return path


def id_moi(ids: List[str], tien_to: str) -> str:
    """`m_01`, `m_02`… nối tiếp số lớn nhất đang có (không dùng lại id đã xoá)."""
    so = 0
    for i in ids:
        m = re.match(rf"^{re.escape(tien_to)}_(\d+)$", str(i or ""))
        if m:
            so = max(so, int(m.group(1)))
    return f"{tien_to}_{so + 1:02d}"


# -------------------------------------------------------------------- Timeline
def kieu_phu_de_mac_dinh() -> Dict[str, Any]:
    return {"font": "", "co": 48, "mau": "#ffffff", "vien": "#000000",
            "do_day_vien": 2, "nen": "None", "vi_tri_y": 0.9}


def timeline_rong() -> Dict[str, Any]:
    return {
        "schema": 1, "phien_ban": 0, "thoi_luong": 0,
        "tracks": [
            {"id": "V1", "loai": "video", "ten": "V1", "an": False, "khoa": False, "tat_tieng": False},
            {"id": "S1", "loai": "phu_de", "ten": "S1", "an": False, "khoa": False, "tat_tieng": False},
            {"id": "O1", "loai": "lop_phu", "ten": "O1", "an": False, "khoa": False, "tat_tieng": False},
            {"id": "A1", "loai": "audio", "ten": "A1", "an": False, "khoa": False, "tat_tieng": False},
        ],
        "clips": [],
        "chuyen_canh": [],
        "kieu_phu_de": {"k_mac_dinh": kieu_phu_de_mac_dinh()},
        "danh_dau": [],
    }


def _hop_le(timeline: Any) -> bool:
    return (isinstance(timeline, dict) and isinstance(timeline.get("clips"), list)
            and isinstance(timeline.get("tracks"), list))


def doc_timeline(folder: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """(timeline, thông báo phục hồi hoặc None).

    Timeline hỏng (JSON lỗi) thì lấy bản lịch sử mới nhất còn đọc được, giữ lại
    file hỏng dưới tên `timeline.hong_<giờ>.json` để còn cứu tay.
    """
    with _khoa(folder):
        path = _p(folder, "timeline.json")
        data = doc_json(path)
        if data is None:
            return timeline_rong(), None
        if _hop_le(data):
            return data, None

        hong = _p(folder, f"timeline.hong_{time.strftime('%Y%m%d_%H%M%S', time.localtime(_gio()))}.json")
        try:
            os.replace(path, hong)
        except OSError:
            pass
        for ban in danh_sach_phien_ban(folder):
            snap = doc_json(_p(folder, LICH_SU, ban["ten"]))
            if _hop_le(snap):
                snap.pop("_nhan", None)
                ghi_nguyen_tu(path, snap)
                return snap, (f"Tiến độ dựng bị hỏng — đã khôi phục bản lưu lúc {ban['luc_hien']}. "
                              f"File hỏng giữ ở .duan/{os.path.basename(hong)}.")
        return timeline_rong(), ("Tiến độ dựng bị hỏng và không có bản lịch sử nào — mở timeline trống. "
                                 f"File hỏng giữ ở .duan/{os.path.basename(hong)}.")


def phien_ban_hien_tai(folder: str) -> int:
    data = doc_json(_p(folder, "timeline.json"))
    if isinstance(data, dict):
        try:
            return int(data.get("phien_ban") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def ghi_timeline(folder: str, timeline: Dict[str, Any], phien_ban: int,
                 hoan_tac: Optional[Dict[str, Any]] = None,
                 so_ban_giu: int = SO_BAN_TU_DONG) -> int:
    """Ghi timeline nếu client đang sửa đúng bản mới nhất; trả số phiên bản mới.

    Thứ tự ghi: timeline trước, hoàn tác sau. Tắt ngang ở giữa thì `hoan_tac.json`
    mang số phiên bản cũ → lúc mở bị bỏ (xem `doc_hoan_tac`), không áp nhầm patch.
    """
    if not _hop_le(timeline):
        raise ValueError("Timeline không hợp lệ (thiếu 'tracks' hoặc 'clips').")
    with _khoa(folder):
        hien_tai = phien_ban_hien_tai(folder)
        if int(phien_ban or 0) != hien_tai:
            raise XungDotPhienBan(hien_tai)
        moi = hien_tai + 1
        timeline = dict(timeline)
        timeline["phien_ban"] = moi
        ghi_nguyen_tu(_p(folder, "timeline.json"), timeline)
        if hoan_tac is not None:
            ghi_hoan_tac(folder, hoan_tac, moi)
        chup_tu_dong(folder, so_ban_giu=so_ban_giu)
        return moi


def ghi_hoan_tac(folder: str, hoan_tac: Dict[str, Any], phien_ban: int) -> None:
    data = dict(hoan_tac or {})
    for key in ("hoan_tac", "lam_lai"):
        if isinstance(data.get(key), list):
            data[key] = data[key][-SO_BUOC_HOAN_TAC:]
    data["phien_ban"] = phien_ban
    ghi_nguyen_tu(_p(folder, "hoan_tac.json"), data)


def doc_hoan_tac(folder: str, phien_ban: int) -> Tuple[Optional[Dict[str, Any]], bool]:
    """(ngăn hoàn tác, bị_bỏ). Bị bỏ khi nó không khớp đúng phiên bản timeline."""
    data = doc_json(_p(folder, "hoan_tac.json"))
    if data is None:
        return None, False
    if not isinstance(data, dict) or data.get("phien_ban") != phien_ban:
        return None, True
    return data, False


# ------------------------------------------------------------------------ ui.json
def doc_ui(folder: str) -> Dict[str, Any]:
    data = doc_json(_p(folder, "ui.json"))
    return data if isinstance(data, dict) else {}


def ghi_ui(folder: str, ui: Dict[str, Any]) -> None:
    if not isinstance(ui, dict):
        raise ValueError("ui phải là object.")
    ghi_nguyen_tu(_p(folder, "ui.json"), ui)


# ---------------------------------------------------------------------- Lịch sử
def _ten_ban(folder: str, loai: str, nhan: str = "") -> str:
    goc = f"{loai}_{time.strftime('%Y%m%d_%H%M%S', time.localtime(_gio()))}"
    duoi = f"_{slugify(nhan, 30).lower()}" if nhan else ""
    ten, n = f"{goc}{duoi}.json", 1
    while os.path.exists(_p(folder, LICH_SU, ten)):
        n += 1
        ten = f"{goc}_{n}{duoi}.json"
    return ten


def _thoi_diem(ten: str) -> float:
    m = _TEN_BAN.match(ten)
    if not m:
        return 0.0
    try:
        return time.mktime(time.strptime(m.group(2), "%Y%m%d_%H%M%S"))
    except ValueError:
        return 0.0


def chup_tu_dong(folder: str, bat_buoc: bool = False, so_ban_giu: int = SO_BAN_TU_DONG) -> Optional[str]:
    """Chép timeline hiện tại sang `lich_su/tu_dong_*.json` nếu đã quá 5 phút từ bản trước.

    Giữ `so_ban_giu` bản tự động mới nhất; bản lưu tay (`luu_*`) không bao giờ bị xoá vòng.
    """
    src = _p(folder, "timeline.json")
    if not os.path.exists(src):
        return None
    thu_muc = _p(folder, LICH_SU)
    os.makedirs(thu_muc, exist_ok=True)
    tu_dong = sorted((f for f in os.listdir(thu_muc) if f.startswith("tu_dong_") and _TEN_BAN.match(f)),
                     key=lambda f: (_thoi_diem(f), natural_key(f)))
    if not bat_buoc and tu_dong and _gio() - _thoi_diem(tu_dong[-1]) < CHU_KY_TU_DONG:
        return None
    ten = _ten_ban(folder, "tu_dong")
    shutil.copyfile(src, os.path.join(thu_muc, ten))
    tu_dong.append(ten)
    for cu in tu_dong[:-max(1, int(so_ban_giu))]:
        try:
            os.remove(os.path.join(thu_muc, cu))
        except OSError:
            pass
    return ten


def luu_thu_cong(folder: str, nhan: str = "") -> str:
    """Bản lưu có tên (nút Lưu / Ctrl+S) — không bị xoá vòng."""
    with _khoa(folder):
        timeline, _ = doc_timeline(folder)
        snap = copy.deepcopy(timeline)
        snap["_nhan"] = (nhan or "").strip()
        ten = _ten_ban(folder, "luu", nhan)
        ghi_nguyen_tu(_p(folder, LICH_SU, ten), snap)
        return ten


def danh_sach_phien_ban(folder: str) -> List[Dict[str, Any]]:
    """Các bản lịch sử, MỚI NHẤT trước."""
    thu_muc = _p(folder, LICH_SU)
    if not os.path.isdir(thu_muc):
        return []
    out = []
    for ten in os.listdir(thu_muc):
        m = _TEN_BAN.match(ten)
        if not m:
            continue
        t = _thoi_diem(ten)
        nhan = ""
        if m.group(1) == "luu":
            data = doc_json(os.path.join(thu_muc, ten))
            nhan = (data.get("_nhan") or "") if isinstance(data, dict) else ""
        out.append({
            "ten": ten, "loai": m.group(1), "nhan": nhan,
            "luc": _iso(t), "luc_hien": time.strftime("%H:%M %d/%m/%Y", time.localtime(t)),
            "kich_thuoc": os.path.getsize(os.path.join(thu_muc, ten)),
        })
    out.sort(key=lambda b: (_thoi_diem(b["ten"]), natural_key(b["ten"])), reverse=True)
    return out


def khoi_phuc(folder: str, ten: str, phien_ban: int) -> Dict[str, Any]:
    """Đưa một bản lịch sử lên làm timeline hiện tại (qua kiểm tra phiên bản như mọi lần ghi).

    Chụp bản hiện tại trước khi đè, nên khôi phục nhầm vẫn quay lại được từ menu Phiên bản.
    """
    if not _TEN_BAN.match(os.path.basename(ten or "")) or os.path.basename(ten) != ten:
        raise ValueError(f"Không có bản lịch sử '{ten}'.")
    with _khoa(folder):
        snap = doc_json(_p(folder, LICH_SU, ten))
        if not _hop_le(snap):
            raise ValueError(f"Bản lịch sử '{ten}' không đọc được.")
        snap.pop("_nhan", None)
        chup_tu_dong(folder, bat_buoc=True)
        moi = ghi_timeline(folder, snap, phien_ban)
        snap["phien_ban"] = moi
        return snap


# -------------------------------------------------------------------------- Khoá
def _doc_khoa(folder: str) -> Optional[Dict[str, Any]]:
    data = doc_json(_p(folder, "lock"))
    return data if isinstance(data, dict) and data.get("phien") else None


def _con_song(khoa: Dict[str, Any]) -> bool:
    # Khoá của lần chạy server TRƯỚC là khoá chết dù nhịp còn mới: đóng app rồi mở
    # lại ngay (dưới 45 s) không được bị "đang mở ở cửa sổ khác".
    if khoa.get("may_chu") != MAY_CHU:
        return False
    try:
        return _gio() - float(khoa.get("nhip_cuoi") or 0) < KHOA_HET_HAN
    except (TypeError, ValueError):
        return False


def lay_khoa(folder: str, phien: str = "") -> Dict[str, Any]:
    """Mở dự án: giữ khoá nếu được, không thì mở chỉ đọc.

    `phien` = mã phiên cũ của cửa sổ này (F5 trang giữ lại qua sessionStorage)
    để tải lại trang không tự khoá mình ra ngoài.
    """
    with _khoa(folder):
        cu = _doc_khoa(folder)
        phien = phien or uuid.uuid4().hex
        if cu and cu["phien"] != phien and _con_song(cu):
            return {"phien": phien, "chi_doc": True,
                    "nguoi_giu": {"luc_mo": cu.get("luc_mo"), "nhip_cuoi": cu.get("nhip_cuoi")}}
        bay_gio = _gio()
        ghi_nguyen_tu(_p(folder, "lock"), {
            "phien": phien, "pid": os.getpid(), "may_chu": MAY_CHU,
            "luc_mo": cu.get("luc_mo") if cu and cu["phien"] == phien else bay_gio,
            "nhip_cuoi": bay_gio,
        })
        return {"phien": phien, "chi_doc": False, "nguoi_giu": None}


def nhip(folder: str, phien: str) -> bool:
    """Heartbeat. True = phiên này đang (hoặc vừa lấy lại được) quyền sửa."""
    return not lay_khoa(folder, phien)["chi_doc"]


def kiem_tra_khoa(folder: str, phien: str) -> None:
    """Chặn ghi từ phiên không giữ khoá. Khoá đã chết/mất thì phiên này lấy lại."""
    if not phien:
        raise KhongGiuKhoa("Thiếu mã phiên — mở lại dự án.")
    if lay_khoa(folder, phien)["chi_doc"]:
        raise KhongGiuKhoa("Dự án đang mở ở cửa sổ khác — cửa sổ này chỉ xem.")


def dang_bi_giu(folder: str) -> bool:
    """Có cửa sổ nào đang mở (và còn heartbeat) dự án này không."""
    cu = _doc_khoa(folder)
    return bool(cu and _con_song(cu))


def nha_khoa(folder: str, phien: str) -> None:
    with _khoa(folder):
        cu = _doc_khoa(folder)
        if cu and cu["phien"] == phien:
            try:
                os.remove(_p(folder, "lock"))
            except OSError:
                pass


# ---------------------------------------------------------- Nâng cấp schema 1 → 2
def nang_cap(folder: str, do_thong_so: Optional[Callable[[str], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Dự án cũ (video `001_…` ở gốc + phu_de/ da_sub/ ban_ghep/) → schema 2.

    KHÔNG di chuyển hay đổi tên file nào: media trỏ tương đối tới đúng chỗ cũ.
    Giữ nguyên các khoá cũ (`videos`, `merges`…) để "Hoàn tác đổi tên" vẫn chạy.
    `do_thong_so(path)` trả {thoi_luong, rong, cao, fps, ...} — tách ra để test không cần ffmpeg.
    """
    folder = os.path.abspath(folder)
    with _khoa(folder):
        data = doc_duan(folder)
        if data is None:
            raise ValueError(f"Thư mục '{folder}' chưa phải là dự án.")
        if int(data.get("schema") or 0) >= SCHEMA:
            return data

        tao_thu_muc_con_nhe(folder)
        ban_sao = _p(folder, LICH_SU, "schema1.json")
        if not os.path.exists(ban_sao):
            shutil.copyfile(duong_dan_duan(folder), ban_sao)

        do_thong_so = do_thong_so or (lambda _p: {})
        media: List[Dict[str, Any]] = []
        clip_v1: List[Tuple[str, float]] = []
        videos = sorted(data.get("videos") or [], key=lambda v: v.get("index", 0))
        for v in videos:
            rel = (v.get("file") or "").replace("\\", "/")
            if not rel:
                continue
            mid = id_moi([m["id"] for m in media], "m")
            path = os.path.join(folder, rel)
            ts = do_thong_so(path) if os.path.exists(path) else {}
            media.append({"id": mid, "loai": "video", "file": rel, "nguon": v.get("nguon") or "",
                          "ten": v.get("title") or os.path.splitext(os.path.basename(rel))[0],
                          "nhap_luc": data.get("created_at") or _iso(), "url": v.get("url") or "",
                          "trang_thai": "san_sang", **_chon_thong_so(ts)})
            if not v.get("merged_into"):
                clip_v1.append((mid, float(ts.get("thoi_luong") or 0)))

        stems = {os.path.splitext(os.path.basename(m["file"]))[0]: m["id"] for m in media}
        for sub, loai, la_xuat in (("phu_de", "phu_de", False), ("da_sub", "video", True),
                                   ("ban_ghep", "video", True)):
            thu_muc = os.path.join(folder, sub)
            if not os.path.isdir(thu_muc):
                continue
            for ten in sorted(os.listdir(thu_muc), key=natural_key):
                duoi = os.path.splitext(ten)[1].lower()
                if loai == "phu_de" and duoi not in (".srt", ".ass", ".vtt"):
                    continue
                if loai == "video" and duoi not in (".mp4", ".mkv", ".mov", ".webm"):
                    continue
                mid = id_moi([m["id"] for m in media], "m")
                item = {"id": mid, "loai": loai, "file": f"{sub}/{ten}", "nguon": "",
                        "ten": os.path.splitext(ten)[0], "nhap_luc": _iso(), "url": "",
                        "trang_thai": "san_sang"}
                goc = ten.split(".")[0]
                if goc in stems:
                    item["tu_media"] = stems[goc]
                if la_xuat:
                    item["la_ban_xuat"] = True
                    item.update(_chon_thong_so(do_thong_so(os.path.join(thu_muc, ten))))
                media.append(item)

        dau = next((m for m in media if m["loai"] == "video" and m.get("rong")), {})
        data.update({
            "schema": SCHEMA,
            "id": data.get("id") or uuid.uuid4().hex[:8],
            "name": data.get("name") or os.path.basename(folder),
            "mo_ta": data.get("mo_ta") or "",
            "tao_luc": data.get("tao_luc") or data.get("created_at") or _iso(),
            "sua_luc": _iso(),
            "thong_so": data.get("thong_so") or {
                "rong": dau.get("rong") or 1920, "cao": dau.get("cao") or 1080,
                "fps": dau.get("fps") or 30, "ti_le": _ti_le(dau.get("rong") or 1920, dau.get("cao") or 1080),
                "mau_nen": "#000000"},
            "media": media,
            "dung_chung": data.get("dung_chung") or [],
            "tac_vu": data.get("tac_vu") or [],
            "anh_bia": data.get("anh_bia") or "",
        })

        timeline = timeline_rong()
        t = 0.0
        for i, (mid, dai) in enumerate(clip_v1, 1):
            timeline["clips"].append(clip_video(f"c_{i}", "V1", mid, t, dai))
            t += dai
        timeline["thoi_luong"] = round(t, 3)
        timeline["phien_ban"] = 1
        if not os.path.exists(_p(folder, "timeline.json")):
            ghi_nguyen_tu(_p(folder, "timeline.json"), timeline)
        ghi_nguyen_tu(duong_dan_duan(folder), data)
        return data


def tao_thu_muc_con_nhe(folder: str) -> None:
    """Chỉ tạo `.duan/` — dự án cũ không cần media/ long_tieng/ xuat/ tới khi dùng."""
    for sub in (LICH_SU, os.path.join(CACHE, "thumbs"), os.path.join(CACHE, "proxy")):
        os.makedirs(_p(folder, sub), exist_ok=True)
    _an_thu_muc(thu_muc_editor(folder))


def _chon_thong_so(ts: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("thoi_luong", "rong", "cao", "fps", "co_am_thanh", "co_hinh", "codec", "codec_am")
    return {k: ts[k] for k in keys if k in ts and ts[k] is not None}


def _ti_le(rong: int, cao: int) -> str:
    from math import gcd
    rong, cao = int(rong or 0), int(cao or 0)
    if rong <= 0 or cao <= 0:
        return ""
    g = gcd(rong, cao)
    return f"{rong // g}:{cao // g}"


def clip_video(cid: str, track: str, mid: str, bat_dau: float, dai: float) -> Dict[str, Any]:
    return {
        "id": cid, "track": track, "media": mid,
        "bat_dau": round(bat_dau, 3), "vao": 0.0, "ra": round(dai, 3),
        "toc_do": 1.0, "am_luong": 1.0, "nhac_nen_giam": 0,
        "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 1.0, "xoay": 0},
        "cat_khung": {"trai": 0, "phai": 0, "tren": 0, "duoi": 0, "mem": 0},
        "hien_thi": {"do_mo": 1.0, "hoa_tron": "normal", "bo_goc": 0},
        "hieu_ung": [], "keyframes": {},
    }
