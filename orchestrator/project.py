"""Dự án video = MỘT THƯ MỤC trên đĩa của người dùng, đánh dấu bằng `.duan.json`.

Cố ý không giấu dữ liệu trong `storage/` của app: video gốc, phụ đề, bản đã gắn
sub và bản ghép đều nằm cạnh nhau ngay trong thư mục người dùng chọn — mở File
Explorer là thấy đủ, chuyển ổ hay đổi máy cũng không mất gì.

    <thư mục dự án>/
        .duan.json            # đánh dấu + siêu dữ liệu + BẢN ĐỒ HOÀN TÁC đổi tên
        001_tap_1.mp4         # video gốc đã đánh số theo thứ tự
        002_tap_2.mp4
        phu_de/               # .srt
        da_sub/               # bản đã gắn phụ đề / lồng tiếng
        ban_ghep/             # bản ghép nhiều video

Module này chỉ đụng hệ thống tệp — không ffmpeg, không mạng — nên chạy nhanh và
kiểm thử được trọn vẹn.
"""
import datetime
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from orchestrator.storage import natural_key, scan_video_files, slugify

MARKER = ".duan.json"
SUB_DIR = "phu_de"
OUT_DIR = "da_sub"
MERGE_DIR = "ban_ghep"
# Tên đã đúng định dạng thì có tiền tố "NNN_" — dùng để khỏi đánh số chồng lên số.
SO_THU_TU = re.compile(r"^(\d{3})_")


def ten_chuan(index: int, ten_cu: str) -> str:
    """Tên file theo định dạng dễ theo dõi: `001_ten_goc.mp4`.

    Bỏ tiền tố số cũ trước khi đánh số lại, nếu không mỗi lần init là tên dài
    thêm một cụm (`001_001_tap_1.mp4`).
    """
    goc, duoi = os.path.splitext(ten_cu)
    goc = SO_THU_TU.sub("", goc)
    return f"{index:03d}_{slugify(goc, 50)}{duoi.lower()}"


def ke_hoach_doi_ten(ten_files: List[str]) -> List[Dict[str, Any]]:
    """[{cu, moi, doi}] — đánh số theo thứ tự TỰ NHIÊN của tên cũ (tap2 trước tap10)."""
    ten_files = sorted(ten_files, key=natural_key)
    da_dung, ke_hoach = set(), []
    for i, cu in enumerate(ten_files, 1):
        moi = ten_chuan(i, cu)
        if moi != cu:
            # Hai video khác nhau ra cùng một tên đích thì phải tách ra, nếu
            # không pha đổi tên sẽ đè mất một cái.
            goc, duoi = os.path.splitext(moi)
            n = 1
            while moi in da_dung:
                n += 1
                moi = f"{goc}_{n}{duoi}"
        da_dung.add(moi)
        ke_hoach.append({"cu": cu, "moi": moi, "doi": moi != cu})
    return ke_hoach


def _doi_ten_hai_pha(folder: str, ke_hoach: List[Dict[str, Any]]) -> None:
    """Đổi tên qua tên tạm rồi mới sang tên đích.

    Đổi thẳng sẽ mất file khi có hoán vị (`a→b` trong lúc `b→a`). Hỏng giữa
    chừng thì trả lại nguyên trạng chứ không bỏ lại một đống tên tạm.
    """
    can_doi = [item for item in ke_hoach if item["doi"]]
    if not can_doi:
        return
    dau = uuid.uuid4().hex[:8]
    da_sang_tam: List[tuple] = []
    try:
        for i, item in enumerate(can_doi):
            src = os.path.join(folder, item["cu"])
            tmp = os.path.join(folder, f".doiten_{dau}_{i}")
            os.rename(src, tmp)
            da_sang_tam.append((tmp, os.path.join(folder, item["moi"]), src))
        for tmp, dst, _src in da_sang_tam:
            os.rename(tmp, dst)
    except OSError:
        for tmp, _dst, src in da_sang_tam:
            if os.path.exists(tmp):
                try:
                    os.rename(tmp, src)
                except OSError:
                    pass
        raise


def duong_dan_marker(folder: str) -> str:
    return os.path.join(os.path.abspath(folder), MARKER)


def da_init(folder: str) -> bool:
    return os.path.exists(duong_dan_marker(folder))


def doc(folder: str) -> Optional[Dict[str, Any]]:
    """Nội dung `.duan.json`, None nếu thư mục chưa phải dự án hoặc file hỏng."""
    path = duong_dan_marker(folder)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    data["folder"] = os.path.abspath(folder)
    return data


def ghi(folder: str, data: Dict[str, Any]) -> None:
    data = {k: v for k, v in data.items() if k != "folder"}
    with open(duong_dan_marker(folder), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def xem_xet(folder: str) -> Dict[str, Any]:
    """Nhìn một thư mục: có video không, đã là dự án chưa, đổi tên sẽ ra sao.

    Chỉ ĐỌC — không đụng gì tới file. Giao diện gọi hàm này để hiện bảng xem
    trước cho người dùng duyệt, rồi mới gọi `init`.
    """
    folder = os.path.abspath(folder or "")
    if not os.path.isdir(folder):
        raise ValueError(f"Không có thư mục: {folder}")

    ten_files = [os.path.basename(p) for p in scan_video_files(folder)]
    data = doc(folder)
    ke_hoach = ke_hoach_doi_ten(ten_files)
    return {
        "folder": folder,
        "co_video": bool(ten_files),
        "so_video": len(ten_files),
        "da_init": data is not None,
        "ten": (data or {}).get("name", "") or os.path.basename(folder),
        "xem_truoc": ke_hoach,
        "so_phai_doi": sum(1 for item in ke_hoach if item["doi"]),
    }


def init(folder: str, name: str = "", doi_ten: bool = True) -> Dict[str, Any]:
    """Biến một thư mục thành dự án: đổi tên video rồi ghi `.duan.json`.

    `doi_ten=False` thì giữ nguyên tên file, chỉ đánh dấu dự án — dành cho người
    xem bảng xem trước xong đổi ý.
    """
    folder = os.path.abspath(folder or "")
    if not os.path.isdir(folder):
        raise ValueError(f"Không có thư mục: {folder}")

    ten_files = [os.path.basename(p) for p in scan_video_files(folder)]
    if not ten_files:
        raise ValueError(f"Thư mục '{folder}' không có file video nào.")

    ke_hoach = ke_hoach_doi_ten(ten_files)
    if doi_ten:
        _doi_ten_hai_pha(folder, ke_hoach)

    cu = doc(folder) or {}
    data = {
        "version": 1,
        "name": (name or cu.get("name") or os.path.basename(folder)).strip(),
        "created_at": cu.get("created_at") or datetime.datetime.now().isoformat(timespec="seconds"),
        "videos": [
            {
                "index": i,
                "file": item["moi"] if doi_ten else item["cu"],
                # Giữ tên gốc = giữ đường lui: hoàn tác lúc nào cũng được.
                "ten_goc": item["cu"],
                "title": os.path.splitext(SO_THU_TU.sub("", item["moi" if doi_ten else "cu"]))[0],
                "merged_into": "",
            }
            for i, item in enumerate(ke_hoach, 1)
        ],
        "merges": cu.get("merges") or [],
    }
    ghi(folder, data)
    for sub in (SUB_DIR, OUT_DIR, MERGE_DIR):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
    return doc(folder)


def tao_moi(thu_muc_cha: str, ten: str) -> Dict[str, Any]:
    """Tạo thư mục dự án RỖNG để tải video về (luồng dán link).

    Người dùng chọn chỗ đặt + đặt tên; video tải về sẽ được đánh số ngay từ đầu
    nên không phải đổi tên lần nữa.
    """
    ten = (ten or "").strip()
    if not ten:
        raise ValueError("Phải đặt tên dự án.")
    thu_muc_cha = os.path.abspath(thu_muc_cha or "")
    if not os.path.isdir(thu_muc_cha):
        raise ValueError(f"Không có thư mục: {thu_muc_cha}")

    folder = os.path.join(thu_muc_cha, slugify(ten, 60))
    if os.path.exists(folder) and da_init(folder):
        raise ValueError(f"Đã có dự án tên '{ten}' ở đây rồi.")
    os.makedirs(folder, exist_ok=True)

    data = {
        "version": 1,
        "name": ten,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "videos": [],
        "merges": [],
    }
    ghi(folder, data)
    for sub in (SUB_DIR, OUT_DIR, MERGE_DIR):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
    return doc(folder)


def hoan_tac(folder: str) -> Dict[str, Any]:
    """Trả tên file về y như trước khi init, rồi bỏ đánh dấu dự án."""
    data = doc(folder)
    if not data:
        raise ValueError(f"Thư mục '{folder}' chưa phải là dự án.")
    folder = os.path.abspath(folder)

    ke_hoach = [
        {"cu": v.get("file", ""), "moi": v.get("ten_goc", ""),
         "doi": bool(v.get("ten_goc")) and v.get("ten_goc") != v.get("file")}
        for v in data.get("videos", [])
    ]
    ke_hoach = [item for item in ke_hoach
                if item["cu"] and os.path.exists(os.path.join(folder, item["cu"]))]
    _doi_ten_hai_pha(folder, ke_hoach)

    try:
        os.remove(duong_dan_marker(folder))
    except OSError:
        pass
    # Trả thư mục về đúng như trước khi init: dọn nốt các thư mục con do app tạo
    # ra, nhưng CHỈ khi chúng rỗng — có phụ đề/bản ghép trong đó là của người dùng.
    for sub in (SUB_DIR, OUT_DIR, MERGE_DIR):
        try:
            os.rmdir(os.path.join(folder, sub))
        except OSError:
            pass
    return {"folder": folder, "so_da_tra_lai": sum(1 for item in ke_hoach if item["doi"])}


def danh_sach_video(folder: str, ke_ca_da_ghep: bool = False) -> List[Dict[str, Any]]:
    """Video của dự án theo đúng thứ tự đã đánh số.

    Mặc định BỎ các video đã nằm trong một bản ghép — ghép xong rồi thì không
    còn là thứ đang chờ xử lý nữa.
    """
    data = doc(folder)
    if not data:
        return []
    folder = os.path.abspath(folder)
    out = []
    for video in sorted(data.get("videos", []), key=lambda v: v.get("index", 0)):
        if not ke_ca_da_ghep and video.get("merged_into"):
            continue
        path = os.path.join(folder, video.get("file", ""))
        item = dict(video)
        item["path"] = path
        item["exists"] = os.path.exists(path)
        item["size"] = os.path.getsize(path) if item["exists"] else 0
        out.append(item)
    return out


def danh_dau_da_ghep(folder: str, files: List[str], ban_ghep: str) -> None:
    """Ghi nhận các video vừa được ghép vào đâu, để thư viện thôi hiện chúng."""
    data = doc(folder)
    if not data:
        return
    ten_files = {os.path.basename(f) for f in files}
    for video in data.get("videos", []):
        if video.get("file") in ten_files:
            video["merged_into"] = os.path.basename(ban_ghep)
    data.setdefault("merges", []).append({
        "file": os.path.join(MERGE_DIR, os.path.basename(ban_ghep)),
        "videos": sorted(ten_files),
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
    })
    ghi(folder, data)
