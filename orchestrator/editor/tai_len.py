"""Tải file từ trình duyệt lên server theo TỪNG PHẦN (chunk), gửi song song và tải tiếp được.

Một request multipart chứa nguyên video điện thoại (vài trăm MB) bị Cloudflare Tunnel/Caddy
cắt (HTTP 408/413: giới hạn ~100 MB và ~100 s mỗi request). Trình duyệt chia file thành các
phần nhỏ, mỗi phần một request PUT ngắn; server ghi vào đúng vị trí trong file `.part`.

- Các phần đến không theo thứ tự (client gửi vài phần cùng lúc cho nhanh).
- Gửi lại một phần là an toàn: ghi đè đúng vị trí.
- Danh sách phần đã nhận lưu cạnh file (`.part.json`) — server khởi động lại, hoặc iPhone
  khoá màn hình làm Safari ngắt giữa chừng, thì client hỏi `trang_thai` rồi gửi tiếp phần thiếu.
"""
import json
import os
import re
import threading
import time
import uuid
from typing import Dict

TOI_DA_FILE = 8 * 1024 * 1024 * 1024  # 8 GB (video 4K/ProRes từ máy quay)
TOI_DA_PHAN = 32 * 1024 * 1024        # client gửi 8 MB; chừa rộng để đổi cỡ phần sau này
HET_HAN_PART = 3 * 24 * 3600          # file .part bỏ dở quá 3 ngày thì xoá
UID_HOP_LE = re.compile(r"^[0-9a-f]{12}$")


class LoiTaiLen(ValueError):
    """Lỗi do dữ liệu người dùng gửi lên — api.py đổi thành HTTP 4xx."""

    def __init__(self, thong_diep: str, ma: int = 400):
        super().__init__(thong_diep)
        self.ma = ma


def ten_an_toan(ten: str) -> str:
    ten = os.path.basename((ten or "media").replace("\\", "/")).replace("\x00", "").strip()
    if not ten or ten in {".", ".."}:
        raise LoiTaiLen("Tên file không hợp lệ.")
    return ten[-120:]


def so_byte_da_co(phan: Dict[int, int]) -> int:
    """Tổng byte của các khoảng đã nhận (gộp chồng lấn)."""
    tong, het = 0, 0
    for vt in sorted(phan):
        dau, cuoi = max(vt, het), vt + phan[vt]
        if cuoi > dau:
            tong += cuoi - dau
        het = max(het, cuoi)
    return tong


class QuanLyTaiLen:
    def __init__(self):
        self._phien: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def bat_dau(self, thu_muc: str, ten: str, kich_thuoc: int) -> str:
        if kich_thuoc <= 0:
            raise LoiTaiLen("File rỗng.")
        if kich_thuoc > TOI_DA_FILE:
            raise LoiTaiLen("Mỗi file tải lên tối đa 8 GB.", 413)
        os.makedirs(thu_muc, exist_ok=True)
        self._don_part_cu(thu_muc)
        uid = uuid.uuid4().hex[:12]
        dich = os.path.join(thu_muc, f"{uid}_{ten_an_toan(ten)}")
        with open(dich + ".part", "wb") as f:
            f.truncate(kich_thuoc)
        p = {"dich": dich, "kich_thuoc": kich_thuoc, "phan": {}, "lock": threading.Lock()}
        self._luu(p)
        with self._lock:
            self._phien[uid] = p
        return uid

    @staticmethod
    def _luu(p: dict) -> None:
        with open(p["dich"] + ".part.json", "w", encoding="utf-8") as f:
            json.dump({"dich": p["dich"], "kich_thuoc": p["kich_thuoc"], "phan": p["phan"]}, f)

    def _lay(self, uid: str, thu_muc: str = "") -> dict:
        with self._lock:
            p = self._phien.get(uid)
            if p or not thu_muc or not UID_HOP_LE.match(uid):
                if not p:
                    raise LoiTaiLen("Phiên tải lên đã hết hạn — hãy chọn file và tải lại.", 404)
                return p
            # Server vừa khởi động lại: đọc lại phiên từ .part.json trong thư mục tải lên.
            for ten in os.listdir(thu_muc) if os.path.isdir(thu_muc) else []:
                if ten.startswith(uid + "_") and ten.endswith(".part.json"):
                    try:
                        with open(os.path.join(thu_muc, ten), encoding="utf-8") as f:
                            d = json.load(f)
                    except (OSError, ValueError):
                        break
                    if os.path.isfile(d["dich"] + ".part"):
                        p = {"dich": d["dich"], "kich_thuoc": int(d["kich_thuoc"]),
                             "phan": {int(k): int(v) for k, v in d["phan"].items()},
                             "lock": threading.Lock()}
                        self._phien[uid] = p
                        return p
            raise LoiTaiLen("Phiên tải lên đã hết hạn — hãy chọn file và tải lại.", 404)

    def trang_thai(self, uid: str, thu_muc: str = "") -> Dict[str, object]:
        p = self._lay(uid, thu_muc)
        with p["lock"]:
            return {"kich_thuoc": p["kich_thuoc"], "da_nhan": so_byte_da_co(p["phan"]),
                    "phan": sorted(p["phan"])}

    def ghi_phan(self, uid: str, vi_tri: int, du_lieu: bytes, thu_muc: str = "") -> int:
        """Ghi một phần tại `vi_tri`; trả về tổng số byte server đã có."""
        p = self._lay(uid, thu_muc)
        if len(du_lieu) > TOI_DA_PHAN:
            raise LoiTaiLen("Phần tải lên quá lớn.", 413)
        if not du_lieu:
            raise LoiTaiLen("Phần tải lên rỗng.")
        with p["lock"]:
            if vi_tri < 0 or vi_tri + len(du_lieu) > p["kich_thuoc"]:
                raise LoiTaiLen("Dữ liệu vượt quá kích thước file đã khai báo.")
            with open(p["dich"] + ".part", "r+b") as f:
                f.seek(vi_tri)
                f.write(du_lieu)
            p["phan"][vi_tri] = max(p["phan"].get(vi_tri, 0), len(du_lieu))
            self._luu(p)
            return so_byte_da_co(p["phan"])

    def hoan_tat(self, uid: str, thu_muc: str = "") -> str:
        """Đủ byte thì đổi `.part` → file thật, trả đường dẫn để nhập vào dự án."""
        p = self._lay(uid, thu_muc)
        with p["lock"]:
            da = so_byte_da_co(p["phan"])
            if da != p["kich_thuoc"]:
                raise LoiTaiLen(f"File chưa tải đủ ({da}/{p['kich_thuoc']} byte).", 409)
            os.replace(p["dich"] + ".part", p["dich"])
            self._xoa(p["dich"] + ".part.json")
        with self._lock:
            self._phien.pop(uid, None)
        return p["dich"]

    def huy(self, uid: str, thu_muc: str = "") -> None:
        try:
            p = self._lay(uid, thu_muc)
        except LoiTaiLen:
            return
        with self._lock:
            self._phien.pop(uid, None)
        self._xoa(p["dich"] + ".part")
        self._xoa(p["dich"] + ".part.json")

    @staticmethod
    def _xoa(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def _don_part_cu(thu_muc: str) -> None:
        han = time.time() - HET_HAN_PART
        for ten in os.listdir(thu_muc):
            path = os.path.join(thu_muc, ten)
            try:
                if (ten.endswith(".part") or ten.endswith(".part.json")) and os.path.getmtime(path) < han:
                    os.remove(path)
            except OSError:
                pass
