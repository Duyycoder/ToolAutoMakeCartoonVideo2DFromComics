"""Gửi việc xuất video sang MÁY XUẤT từ xa (laptop GPU, orchestrator/may_xuat.py) qua Tailscale.

Lệnh ffmpeg dựng sẵn ở đây (render.py); đường dẫn file media đổi thành @tep:<khoá nội dung>, đầu ra
thành @ra. File máy xuất chưa có thì gửi lên (một lần, giữ cache), rồi theo dõi tiến độ và tải .mp4 về.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

KHUC = 1024 * 1024


class LoiMayXuat(RuntimeError):
    """Không nói chuyện được với máy xuất (tắt máy, sai địa chỉ/mã) — máy chính tự xuất thay."""


def khoa_tep(path: str) -> str:
    """Khoá nội dung nhanh: cỡ file + 3 khúc 1 MB (đầu/giữa/cuối) — khỏi băm cả file 4 GB mỗi lần xuất."""
    n = os.path.getsize(path)
    h = hashlib.sha1(str(n).encode())
    with open(path, "rb") as f:
        for vt in sorted({0, max(0, n // 2 - KHUC // 2), max(0, n - KHUC)}):
            f.seek(vt)
            h.update(f.read(KHUC))
    duoi = (os.path.splitext(path)[1].lower().lstrip(".") or "bin")[:5]
    return f"{h.hexdigest()}.{duoi if duoi.isalnum() else 'bin'}"


class _DocCoTienDo:
    """File object cho urllib gửi từng khúc và báo số byte đã gửi."""

    def __init__(self, path: str, bao: Callable[[int], None]):
        self.f = open(path, "rb")
        self.bao = bao
        self.da = 0

    def read(self, n: int = -1) -> bytes:
        b = self.f.read(KHUC if n is None or n < 0 else min(n, KHUC))
        self.da += len(b)
        self.bao(self.da)
        return b

    def close(self):
        self.f.close()


class MayXuat:
    def __init__(self, url: str, token: str, het_gio: float = 30):
        if not url or not token:
            raise LoiMayXuat("Chưa nhập địa chỉ hoặc mã bí mật của máy xuất.")
        self.url = url.rstrip("/")
        self.token = token
        self.het_gio = het_gio

    def _goi(self, method: str, path: str, data: Any = None, het_gio: Optional[float] = None,
             headers: Optional[Dict[str, str]] = None) -> Tuple[int, bytes]:
        h = {"Authorization": f"Bearer {self.token}", **(headers or {})}
        if isinstance(data, (dict, list)):
            data, h["Content-Type"] = json.dumps(data).encode(), "application/json"
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=het_gio or self.het_gio) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 401:
                raise LoiMayXuat("Máy xuất từ chối: sai mã bí mật.")
            return e.code, body
        except (urllib.error.URLError, OSError) as e:
            raise LoiMayXuat(f"Không kết nối được máy xuất {self.url} ({getattr(e, 'reason', e)}).")

    def _json(self, method: str, path: str, data: Any = None, **kw) -> Dict[str, Any]:
        code, body = self._goi(method, path, data, **kw)
        try:
            d = json.loads(body or b"{}")
        except ValueError:
            d = {}
        if code >= 400:
            raise RuntimeError(f"Máy xuất báo lỗi {code}: {d.get('detail') or body[:200]!r}")
        return d

    def ping(self) -> Dict[str, Any]:
        return self._json("GET", "/ping", het_gio=6)

    def _gui_tep(self, path: str, khoa: str, bao: Callable[[int], None]) -> None:
        code, _ = self._goi("GET", f"/tep/{khoa}")
        if code == 200:
            return
        doc = _DocCoTienDo(path, bao)
        try:
            code, body = self._goi("PUT", f"/tep/{khoa}", doc, het_gio=600,
                                   headers={"Content-Length": str(os.path.getsize(path)),
                                            "Content-Type": "application/octet-stream"})
        finally:
            doc.close()
        if code >= 400:
            raise RuntimeError(f"Gửi {os.path.basename(path)} lỗi {code}: {body[:200]!r}")

    def chay_ai(self, path: str, loai: str, tham_so: Dict[str, Any], bao: Callable[[float, str], None],
                da_huy: Callable[[], bool]) -> Dict[str, Any]:
        """Tác vụ AI trên laptop (orchestrator/may_ai.py): gửi media (0–10 %), chờ laptop chạy, trả `ket_qua`."""
        khoa = khoa_tep(path)
        n = os.path.getsize(path) or 1
        self._gui_tep(path, khoa, lambda d: bao(10 * d / n, "Gửi file lên laptop…"))
        code, body = self._goi("POST", "/ai", {"loai": loai, "tep": khoa, "tham_so": tham_so})
        if code == 404:
            raise LoiMayXuat("Laptop đang chạy bản run-worker cũ chưa có AI — cập nhật code trên laptop.")
        try:
            vid = json.loads(body)["id"] if code < 400 else None
        except (ValueError, KeyError):
            vid = None
        if not vid:
            raise RuntimeError(f"Laptop từ chối tác vụ AI ({code}): {body[:200]!r}")
        try:
            while True:
                if da_huy():
                    raise InterruptedError()
                v = self._json("GET", f"/ai/{vid}")
                if v["trang_thai"] == "xong":
                    return v.get("ket_qua") or {}
                if v["trang_thai"] in ("loi", "da_huy", "bi_ngat"):
                    raise RuntimeError("Laptop: " + (v.get("loi") or v["trang_thai"]))
                bao(10 + 0.89 * float(v.get("tien_do") or 0), "Laptop (GPU): " + (v.get("thong_diep") or "đang chạy…"))
                time.sleep(1)
        finally:
            try:
                self._goi("DELETE", f"/ai/{vid}", het_gio=10)
            except LoiMayXuat:
                pass

    def xuat(self, kq: Dict[str, Any], ra: str, bao: Callable[[float, str], None],
             da_huy: Callable[[], bool]) -> None:
        """Gửi file còn thiếu (0–30 %), chạy ffmpeg trên máy xuất (30–95 %), tải kết quả về `ra`."""
        lenh: List[str] = list(kq["cmd"][1:])
        if lenh[-1] != ra:
            raise RuntimeError("Lệnh xuất không kết thúc bằng file ra.")
        lenh[-1] = "@ra"
        tep: List[Tuple[str, str]] = []
        for i in range(1, len(lenh)):
            if lenh[i - 1] == "-i":
                khoa = khoa_tep(lenh[i])
                tep.append((lenh[i], khoa))
                lenh[i] = "@tep:" + khoa
        doc_nhat = {p: k for p, k in tep}
        tong = sum(os.path.getsize(p) for p in doc_nhat) or 1
        da_gui = 0
        for j, (p, k) in enumerate(doc_nhat.items(), 1):
            if da_huy():
                raise InterruptedError()
            goc = da_gui
            self._gui_tep(p, k, lambda n: bao(30 * (goc + n) / tong, f"Gửi file {j}/{len(doc_nhat)} lên laptop…"))
            da_gui += os.path.getsize(p)
        tep_phu = {"loc.txt": kq["loc"], "sub.ass": kq.get("ass") or "", **(kq.get("tep") or {})}
        vid = self._json("POST", "/viec", {"lenh": lenh, "tep_phu": tep_phu})["id"]
        try:
            T = max(0.001, float(kq["thoi_luong"]))
            while True:
                if da_huy():
                    raise InterruptedError()
                v = self._json("GET", f"/viec/{vid}")
                if v["trang_thai"] == "xong":
                    break
                if v["trang_thai"] != "dang_chay":
                    raise RuntimeError("Laptop xuất lỗi: " + (v.get("loi") or v["trang_thai"]))
                bao(30 + min(65.0, v["tien_do_us"] / 1e6 * 65 / T), "Laptop đang xuất (GPU)…")
                time.sleep(1)
            bao(96, "Tải video từ laptop về server…")
            req = urllib.request.Request(f"{self.url}/viec/{vid}/file", headers={"Authorization": f"Bearer {self.token}"})
            with urllib.request.urlopen(req, timeout=600) as r, open(ra + ".tai", "wb") as f:
                while True:
                    b = r.read(KHUC)
                    if not b:
                        break
                    f.write(b)
            os.replace(ra + ".tai", ra)
        finally:
            try:
                self._goi("DELETE", f"/viec/{vid}", het_gio=10)
            except LoiMayXuat:
                pass
            if os.path.exists(ra + ".tai"):
                os.remove(ra + ".tai")
