"""Media của dự án: nhập (CHÉP vào `media/`, giữ tên gốc), đọc thông số, ảnh xem trước, proxy.

Máy đích KHÔNG có `ffprobe` (gói `imageio_ffmpeg` chỉ ship `ffmpeg.exe`) nên thông
số đọc từ stderr của `ffmpeg -i <file>` — chỉ mở file, không giải mã, gần như tức thì.

Mỗi media trong `.duan.json › media[]` đi qua các trạng thái:
    dang_chep → dang_doc → san_sang        (hoặc loi / bi_ngat khi app tắt giữa chừng)
rồi ở nền mới tạo thumbnail, dải khung hình, sóng âm và (nếu WebView2 không phát
được) proxy H.264 720p. Ba loại việc đó chạy ở ba hàng đợi riêng để chép một file
4 GB không chặn thumbnail của file khác. Bản xuất luôn dùng file GỐC, không dùng proxy.
"""
import os
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional

from orchestrator.editor import hang_doi, luu_tru
from orchestrator.storage import VIDEO_EXTS

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma")
ANH_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
PHU_DE_EXTS = (".srt", ".ass", ".vtt")
# Container WebView2 chắc chắn không phát → tạo proxy ngay lúc nhập, khỏi thử.
LUON_PROXY = (".mkv", ".flv", ".avi", ".ts", ".wmv")
DU_TRU_DIA = 500 * 1024 * 1024     # chừa 500 MB cho thumbnail/proxy/bản xuất
KHUC_CHEP = 8 * 1024 * 1024
SO_KHUNG_DAI = 12
TIEN_TO_TAM = ".dang_chep_"

_ffmpeg_cache: Dict[str, Optional[str]] = {}


def ffmpeg_exe() -> Optional[str]:
    if "exe" not in _ffmpeg_cache:
        from orchestrator.video_merger import _ffmpeg_exe
        _ffmpeg_cache["exe"] = _ffmpeg_exe()
    return _ffmpeg_cache["exe"]


def loai_theo_duoi(path: str) -> str:
    duoi = os.path.splitext(path)[1].lower()
    if duoi in VIDEO_EXTS:
        return "video"
    if duoi in AUDIO_EXTS:
        return "audio"
    if duoi in ANH_EXTS:
        return "anh"
    if duoi in PHU_DE_EXTS:
        return "phu_de"
    return ""


# ------------------------------------------------------------------ Thông số
def phan_tich(stderr: str) -> Dict[str, Any]:
    """Thông số từ output của `ffmpeg -i`. Thiếu gì thì bỏ khoá đó (không đoán)."""
    out: Dict[str, Any] = {"co_hinh": False, "co_am_thanh": False}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if m:
        out["thoi_luong"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3)

    for line in stderr.splitlines():
        if "Stream #" not in line:
            continue
        if ": Video:" in line and "attached pic" not in line:
            if out["co_hinh"]:
                continue   # lấy luồng hình đầu tiên
            out["co_hinh"] = True
            codec = re.search(r": Video:\s*([A-Za-z0-9_]+)", line)
            if codec:
                out["codec"] = codec.group(1)
            size = re.search(r"[ ,](\d{2,5})x(\d{2,5})(?=[ ,\[]|$)", line)
            if size:
                out["rong"], out["cao"] = int(size.group(1)), int(size.group(2))
            fps = re.search(r"(\d+(?:\.\d+)?) fps", line) or re.search(r"(\d+(?:\.\d+)?) tbr", line)
            if fps:
                out["fps"] = round(float(fps.group(1)), 3)
        elif ": Audio:" in line and not out["co_am_thanh"]:
            out["co_am_thanh"] = True
            codec = re.search(r": Audio:\s*([A-Za-z0-9_]+)", line)
            if codec:
                out["codec_am"] = codec.group(1)

    # Video iPhone quay dọc: luồng ghi 1920x1080 kèm "rotation of -90" — khung hiển thị là 1080x1920.
    rot = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees", stderr) or re.search(r"rotate\s*:\s*(-?\d+)", stderr)
    if rot:
        out["xoay"] = round(float(rot.group(1)))
        if "rong" in out and abs(out["xoay"]) % 180 == 90:
            out["rong"], out["cao"] = out["cao"], out["rong"]
    return out


def do_thong_so(path: str) -> Dict[str, Any]:
    exe = ffmpeg_exe()
    if not exe:
        return {}
    try:
        res = subprocess.run([exe, "-hide_banner", "-i", path], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             errors="replace", timeout=60, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return {}
    return phan_tich(res.stderr or "")


def can_proxy_ngay(m: Dict[str, Any]) -> bool:
    return m.get("loai") == "video" and os.path.splitext(m.get("file") or "")[1].lower() in LUON_PROXY


# --------------------------------------------------------------------- Nhập
def ten_dich(folder: str, ten: str, da_giu: set) -> str:
    """Giữ TÊN GỐC; trùng thì thêm " (2)", " (3)"… — không bao giờ đè file có sẵn."""
    goc, duoi = os.path.splitext(ten)
    thu, n = ten, 1
    while thu.lower() in da_giu or os.path.exists(os.path.join(folder, luu_tru.MEDIA_DIR, thu)):
        n += 1
        thu = f"{goc} ({n}){duoi}"
    return thu


def kiem_tra_dia(folder: str, can: int) -> None:
    try:
        trong = shutil.disk_usage(folder).free
    except OSError:
        return
    if can + DU_TRU_DIA > trong:
        raise ValueError(f"Ổ đĩa chứa dự án chỉ còn {_co(trong)} trống, cần khoảng {_co(can + DU_TRU_DIA)} "
                         "(gồm chỗ cho proxy/bản xuất). Dọn bớt ổ hoặc chuyển Nơi làm việc sang ổ khác.")


def _co(n: int) -> str:
    from orchestrator.storage import human_size
    return human_size(n)


def chep_co_tien_do(src: str, dst: str, bao: Callable[[float], None],
                    kiem_tra_huy: Callable[[], None]) -> None:
    """Chép qua file tạm cùng thư mục rồi đổi tên — tắt ngang không để lại file cụt mang tên thật."""
    tong = max(1, os.path.getsize(src))
    tmp = os.path.join(os.path.dirname(dst), TIEN_TO_TAM + os.path.basename(dst))
    da = 0
    try:
        with open(src, "rb") as fi, open(tmp, "wb") as fo:
            while True:
                kiem_tra_huy()
                khuc = fi.read(KHUC_CHEP)
                if not khuc:
                    break
                fo.write(khuc)
                da += len(khuc)
                bao(da * 100.0 / tong)
        shutil.copystat(src, tmp)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


class QuanLyMedia:
    """Điều phối nhập/đọc/ảnh xem trước/proxy cho mọi dự án. Một đối tượng dùng chung cả app."""

    def __init__(self):
        self.hang_chep = hang_doi.HangDoi("chep")
        self.hang_nhe = hang_doi.HangDoi("anh")
        self.hang_proxy = hang_doi.HangDoi("proxy")

    def cac_hang(self) -> List[hang_doi.HangDoi]:
        return [self.hang_chep, self.hang_nhe, self.hang_proxy]

    def ids_con_song(self) -> set:
        out = set()
        for h in self.cac_hang():
            out |= h.ids_con_song()
        return out

    # ------------------------------------------------------------------- nhập
    def nhap(self, folder: str, du_an_id: str, paths: List[str]) -> List[Dict[str, Any]]:
        folder = os.path.abspath(folder)
        paths = [os.path.abspath(p) for p in paths if (p or "").strip()]
        if not paths:
            raise ValueError("Chưa chọn file nào.")
        thieu = [p for p in paths if not os.path.isfile(p)]
        if thieu:
            raise ValueError("Không tìm thấy file: " + ", ".join(thieu[:3]))
        la = [os.path.basename(p) for p in paths if not loai_theo_duoi(p)]
        if la:
            raise ValueError("Không nhận loại file này: " + ", ".join(la[:5]))

        media_dir = os.path.join(folder, luu_tru.MEDIA_DIR)
        os.makedirs(media_dir, exist_ok=True)
        can_chep = [p for p in paths if not _trong(folder, p)]
        kiem_tra_dia(folder, sum(os.path.getsize(p) for p in can_chep))

        moi: List[Dict[str, Any]] = []

        tra_ve: List[Dict[str, Any]] = []

        def them(data):
            ds = data.setdefault("media", [])
            da_giu = {os.path.basename(m.get("file") or "").lower() for m in ds}
            for p in paths:
                kt = os.path.getsize(p)
                ten_goc = os.path.splitext(os.path.basename(p))[0]
                cu = next((x for x in ds if x.get("ten") == ten_goc and x.get("kich_thuoc") == kt), None)
                if cu:
                    tra_ve.append(dict(cu))
                    continue

                mid = luu_tru.id_moi([x["id"] for x in ds], "m")
                if _trong(folder, p):
                    rel = os.path.relpath(p, folder).replace("\\", "/")
                    trang_thai = "dang_doc"
                else:
                    ten = ten_dich(folder, os.path.basename(p), da_giu)
                    da_giu.add(ten.lower())
                    rel = f"{luu_tru.MEDIA_DIR}/{ten}"
                    trang_thai = "dang_chep"
                m = {"id": mid, "loai": loai_theo_duoi(p), "file": rel, "nguon": p,
                     "ten": ten_goc, "nhap_luc": luu_tru._iso(),
                     "url": "", "kich_thuoc": kt, "trang_thai": trang_thai}
                ds.append(m)
                moi.append(dict(m))
                tra_ve.append(dict(m))
        luu_tru.sua_duan(folder, them)
        for m in moi:
            self._xep_nhap(folder, du_an_id, m)
        return tra_ve

    def dang_ky_file(self, folder: str, du_an_id: str, path: str, tu_media: str = "") -> Dict[str, Any]:
        """Đưa một file ĐÃ NẰM TRONG dự án (vd long_tieng/*.wav do AI sinh ra) vào danh sách media.

        Đọc thông số ngay (đồng bộ) để lúc [Áp dụng] clip có sẵn thời lượng; sóng âm làm ở nền.
        """
        folder = os.path.abspath(folder)
        if not _trong(folder, path):
            raise ValueError("File phải nằm trong thư mục dự án.")
        rel = os.path.relpath(path, folder).replace("\\", "/")
        ts = do_thong_so(path)

        def them(data):
            ds = data.setdefault("media", [])
            for x in ds:
                if x.get("file") == rel:          # chạy lại tác vụ → ghi đè cùng file
                    x.update(luu_tru._chon_thong_so(ts))
                    x["trang_thai"] = "san_sang"
                    return dict(x)
            m = {"id": luu_tru.id_moi([x["id"] for x in ds], "m"), "loai": loai_theo_duoi(path) or "audio",
                 "file": rel, "nguon": "", "ten": os.path.splitext(os.path.basename(path))[0],
                 "nhap_luc": luu_tru._iso(), "url": "", "kich_thuoc": os.path.getsize(path),
                 "trang_thai": "san_sang", **luu_tru._chon_thong_so(ts)}
            if tu_media:
                m["tu_media"] = tu_media
            ds.append(m)
            return dict(m)
        m = luu_tru.sua_duan(folder, them)
        self.xep_anh(folder, du_an_id, m["id"])
        return m

    def nhap_lai(self, folder: str, du_an_id: str, mid: str, nguon: str = "") -> Dict[str, Any]:
        """Chép lại media bị ngắt/lỗi, hoặc "Tìm lại…" file đã mất bằng file khác (`nguon`)."""
        folder = os.path.abspath(folder)
        m = self.lay(folder, mid)
        src = os.path.abspath(nguon or m.get("nguon") or "")
        if not os.path.isfile(src):
            raise ValueError(f"Không còn file nguồn: {src or '(trống)'} — chọn file khác.")
        if loai_theo_duoi(src) != m.get("loai"):
            raise ValueError("File thay thế phải cùng loại (video/âm thanh/ảnh/phụ đề).")
        if not _trong(folder, src):
            kiem_tra_dia(folder, os.path.getsize(src))

        def sua(data):
            for x in data.get("media") or []:
                if x["id"] == mid:
                    if _trong(folder, src):
                        x["file"] = os.path.relpath(src, folder).replace("\\", "/")
                        x["trang_thai"] = "dang_doc"
                    else:
                        if nguon:
                            ds = {os.path.basename(y.get("file") or "").lower()
                                  for y in data["media"] if y["id"] != mid}
                            x["file"] = f"{luu_tru.MEDIA_DIR}/{ten_dich(folder, os.path.basename(src), ds)}"
                        x["trang_thai"] = "dang_chep"
                    x["nguon"] = src
                    x["kich_thuoc"] = os.path.getsize(src)
                    for k in ("loi", "tien_do", "thumb", "dai_hinh", "song_am", "proxy", "phat_duoc"):
                        x.pop(k, None)
                    return dict(x)
            raise ValueError(f"Không có media '{mid}'.")
        m = luu_tru.sua_duan(folder, sua)
        for f in (f"{mid}.jpg", f"{mid}_dai.jpg", f"{mid}_song.png"):
            _xoa(luu_tru._p(folder, luu_tru.CACHE, "thumbs", f))
        _xoa(luu_tru._p(folder, luu_tru.CACHE, "proxy", f"{mid}.mp4"))
        self._xep_nhap(folder, du_an_id, m)
        return m

    def tai_url(self, folder: str, du_an_id: str, urls: List[str], lenh: Callable[[str], list],
                cwd: str) -> hang_doi.Viec:
        """Tải link (yt-dlp qua adapter có sẵn) vào `.duan/cache/tai_ve/`, xong CHUYỂN vào media/.

        Chạy ở hàng riêng (mạng, không dùng GPU). `lenh(thu_muc_tam)` dựng lệnh adapter —
        tách ra để api.py lắp cookies/cấu hình và test thay bằng lệnh giả.
        """
        import json
        folder = os.path.abspath(folder)
        urls = [u.strip() for u in urls if (u or "").strip()]
        if not urls:
            raise ValueError("Chưa nhập link nào.")

        def lam(ctx: hang_doi.NguCanh):
            ctx.bao(0, f"Đang chuẩn bị tải {len(urls)} link…")
            tam = luu_tru._p(folder, luu_tru.CACHE, "tai_ve")
            os.makedirs(tam, exist_ok=True)
            proc = subprocess.Popen(lenh(tam), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
            xong, loi = [], []
            try:
                for line in proc.stdout:
                    if ctx.da_huy:
                        proc.kill()
                        raise hang_doi.DaHuy()
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    kind = ev.get("event")
                    if kind == "item_start":
                        ctx.bao(0, f"Đang tải {ev.get('index')}/{ev.get('total')}: {ev.get('title') or ''}")
                    elif kind == "download_progress" and ev.get("percent") is not None:
                        ctx.bao(float(ev["percent"]))
                    elif kind == "item_done" and ev.get("path"):
                        xong.append((ev["path"], ev.get("title") or "", ev.get("url") or ""))
                    elif kind in ("item_failed", "batch_failed"):
                        loi.append(ev.get("error") or "lỗi không rõ")
                proc.wait()
            finally:
                if proc.poll() is None:
                    proc.kill()
            for path, title, url in xong:
                self._dua_ban_tai_vao(folder, du_an_id, path, title, url)
            from orchestrator.editor.workspace import giai_thich_loi_ghi
            loi = [giai_thich_loi_ghi(x) for x in loi]
            if not xong:
                raise RuntimeError("; ".join(loi[:3]) or f"Không tải được (adapter thoát mã {proc.returncode}).")
            return {"so_tai": len(xong), "loi": loi}

        return self.hang_chep.them(hang_doi.Viec("tai_url", lam, du_an_id=du_an_id,
                                                 nhan=f"Tải {len(urls)} link", tham_so={"urls": urls}))

    def _dua_ban_tai_vao(self, folder: str, du_an_id: str, path: str, title: str, url: str) -> None:
        duoi = os.path.splitext(path)[1] or ".mp4"
        ten_goc = (title or os.path.splitext(os.path.basename(path))[0]).strip()
        ten_goc = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", ten_goc)[:80].strip(" .") or "video"

        def them(data):
            ds = data.setdefault("media", [])
            da_giu = {os.path.basename(x.get("file") or "").lower() for x in ds}
            ten = ten_dich(folder, ten_goc + duoi, da_giu)
            shutil.move(path, os.path.join(folder, luu_tru.MEDIA_DIR, ten))
            m = {"id": luu_tru.id_moi([x["id"] for x in ds], "m"), "loai": "video",
                 "file": f"{luu_tru.MEDIA_DIR}/{ten}", "nguon": "", "ten": ten_goc,
                 "nhap_luc": luu_tru._iso(), "url": url, "trang_thai": "dang_doc"}
            ds.append(m)
            return dict(m)
        os.makedirs(os.path.join(folder, luu_tru.MEDIA_DIR), exist_ok=True)
        m = luu_tru.sua_duan(folder, them)
        # Thư mục con adapter tạo cho từng video (còn video.json của thư viện cũ) — dọn đi.
        _xoa(os.path.join(os.path.dirname(path), "video.json"))
        try:
            os.rmdir(os.path.dirname(path))
        except OSError:
            pass
        self._xep_nhap(folder, du_an_id, m)

    def _xep_nhap(self, folder: str, du_an_id: str, m: Dict[str, Any]) -> None:
        mid = m["id"]

        def lam(ctx: hang_doi.NguCanh):
            if m["trang_thai"] == "dang_chep":
                dst = luu_tru.duong_dan_media(folder, m["file"])
                ctx.bao(0, "Đang chép…")
                try:
                    chep_co_tien_do(m["nguon"], dst, lambda pct: ctx.bao(pct), ctx.kiem_tra_huy)
                except hang_doi.DaHuy:
                    self._xoa_media_khoi_duan(folder, mid)
                    raise
                except OSError as e:
                    from orchestrator.editor.workspace import giai_thich_loi_ghi
                    self._cap_nhat(folder, mid, {"trang_thai": "loi", "loi": giai_thich_loi_ghi(f"Chép lỗi: {e}")})
                    raise
            self._cap_nhat(folder, mid, {"trang_thai": "dang_doc"})
            path = luu_tru.duong_dan_media(folder, m["file"])
            ts = do_thong_so(path) if m["loai"] != "phu_de" else {}
            sua: Dict[str, Any] = {"trang_thai": "san_sang", **luu_tru._chon_thong_so(ts)}
            if m["loai"] == "video" and ts and not ts.get("co_hinh"):
                sua["loai"] = "audio"
            self._cap_nhat(folder, mid, sua)
            if sua.get("loai", m["loai"]) == "video" and ts.get("rong"):
                theo_video_dau(folder, ts)
            self.xep_anh(folder, du_an_id, mid)
            if can_proxy_ngay({**m, **sua}):
                self.xep_proxy(folder, du_an_id, mid)

        self.hang_chep.them(hang_doi.Viec("nhap", lam, du_an_id=du_an_id, media=mid,
                                          nhan=f"Nhập {os.path.basename(m['file'])}"))

    # ----------------------------------------------------- ảnh xem trước + proxy
    def xep_anh(self, folder: str, du_an_id: str, mid: str) -> None:
        def lam(ctx):
            m = self.lay(folder, mid)
            src = luu_tru.duong_dan_media(folder, m["file"])
            thu = luu_tru._p(folder, luu_tru.CACHE, "thumbs")
            os.makedirs(thu, exist_ok=True)
            sua: Dict[str, Any] = {}
            dai = float(m.get("thoi_luong") or 0)
            if m["loai"] in ("video", "anh") and tao_thumb(src, os.path.join(thu, f"{mid}.jpg"),
                                                          min(1.0, dai * 0.1) if m["loai"] == "video" else None):
                sua["thumb"] = True
            if m["loai"] == "video" and dai > 0:
                so = tao_dai_hinh(src, os.path.join(thu, f"{mid}_dai.jpg"), dai)
                if so:
                    sua["dai_hinh"] = so
            if m["loai"] in ("video", "audio") and m.get("co_am_thanh", m["loai"] == "audio"):
                if tao_song_am(src, os.path.join(thu, f"{mid}_song.png")):
                    sua["song_am"] = True
            self._cap_nhat(folder, mid, sua)
            if sua.get("thumb"):
                def bia(data):
                    if not data.get("anh_bia"):
                        data["anh_bia"] = f"{luu_tru.THU_MUC_EDITOR}/{luu_tru.CACHE}/thumbs/{mid}.jpg"
                luu_tru.sua_duan(folder, bia)

        self.hang_nhe.them(hang_doi.Viec("anh", lam, du_an_id=du_an_id, media=mid))

    def xep_proxy(self, folder: str, du_an_id: str, mid: str) -> None:
        m = self.lay(folder, mid)
        if m.get("proxy") in ("dang_tao", "xong") or m.get("loai") != "video":
            return
        self._cap_nhat(folder, mid, {"proxy": "dang_tao"})

        def lam(ctx: hang_doi.NguCanh):
            src = luu_tru.duong_dan_media(folder, m["file"])
            dst = luu_tru._p(folder, luu_tru.CACHE, "proxy", f"{mid}.mp4")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                ok = tao_proxy(src, dst, float(m.get("thoi_luong") or 0), ctx)
            except hang_doi.DaHuy:
                self._cap_nhat(folder, mid, {"proxy": ""})
                raise
            self._cap_nhat(folder, mid, {"proxy": "xong" if ok else "loi"})
            if not ok:
                raise RuntimeError("Không tạo được bản xem trước (proxy).")

        self.hang_proxy.them(hang_doi.Viec("proxy", lam, du_an_id=du_an_id, media=mid,
                                           nhan=f"Tạo bản xem trước {os.path.basename(m['file'])}"))

    def bao_phat_duoc(self, folder: str, du_an_id: str, mid: str, ok: bool) -> Dict[str, Any]:
        """Client đã thử phát trong WebView2: không phát được thì tạo proxy nền."""
        self._cap_nhat(folder, mid, {"phat_duoc": bool(ok)})
        if not ok:
            self.xep_proxy(folder, du_an_id, mid)
        return self.lay(folder, mid)

    # ------------------------------------------------------------- mở dự án
    def don_khi_mo(self, folder: str) -> int:
        """Media dở dang từ lần chạy trước (app tắt khi đang chép/tạo proxy) → bi_ngat + dọn file tạm."""
        con_song = {v["media"] for h in self.cac_hang() for v in h.danh_sach() if v["trang_thai"] in hang_doi.CON_DO}
        data = luu_tru.doc_duan(folder) or {}
        dang_chep = {os.path.basename(m.get("file") or "") for m in data.get("media") or []
                     if m.get("id") in con_song}
        media_dir = os.path.join(os.path.abspath(folder), luu_tru.MEDIA_DIR)
        if os.path.isdir(media_dir):
            for f in os.listdir(media_dir):
                if f.startswith(TIEN_TO_TAM) and f[len(TIEN_TO_TAM):] not in dang_chep:
                    _xoa(os.path.join(media_dir, f))
        can = [m for m in data.get("media") or []
               if m.get("id") not in con_song and (m.get("trang_thai") in ("dang_chep", "dang_doc")
                                                    or m.get("proxy") == "dang_tao")]
        if not can:
            return 0

        def sua(d):
            for m in d.get("media") or []:
                if m.get("id") in con_song:
                    continue
                if m.get("trang_thai") in ("dang_chep", "dang_doc"):
                    m["trang_thai"] = "bi_ngat"
                    m["loi"] = "Bị ngắt vì app đã đóng khi đang nhập — bấm Nhập lại."
                if m.get("proxy") == "dang_tao":
                    m["proxy"] = ""
        luu_tru.sua_duan(folder, sua)
        return len(can)

    # --------------------------------------------------------------- tiện ích
    @staticmethod
    def lay(folder: str, mid: str) -> Dict[str, Any]:
        for m in (luu_tru.doc_duan(folder) or {}).get("media") or []:
            if m.get("id") == mid:
                return m
        raise ValueError(f"Không có media '{mid}'.")

    @staticmethod
    def _cap_nhat(folder: str, mid: str, sua: Dict[str, Any]) -> None:
        if not sua:
            return

        def ham(data):
            for m in data.get("media") or []:
                if m.get("id") == mid:
                    m.update(sua)
                    if sua.get("trang_thai") == "san_sang":
                        m.pop("loi", None)
        try:
            luu_tru.sua_duan(folder, ham)
        except ValueError:
            pass

    @staticmethod
    def _xoa_media_khoi_duan(folder: str, mid: str) -> None:
        def ham(data):
            data["media"] = [m for m in data.get("media") or [] if m.get("id") != mid]
        luu_tru.sua_duan(folder, ham)

    def xoa(self, folder: str, mid: str, xoa_file: bool = False, dang_dung: bool = False) -> None:
        """Bỏ media khỏi dự án. `dang_dung` = timeline còn clip trỏ tới nó → chặn."""
        if dang_dung:
            raise ValueError("Media đang có trên timeline — xoá các clip dùng nó trước.")
        m = self.lay(folder, mid)
        for h in self.cac_hang():
            for v in h.danh_sach():
                if v["media"] == mid and v["trang_thai"] in hang_doi.CON_DO:
                    h.huy(v["id"])
        self._xoa_media_khoi_duan(folder, mid)
        for f in (f"{mid}.jpg", f"{mid}_dai.jpg", f"{mid}_song.png"):
            _xoa(luu_tru._p(folder, luu_tru.CACHE, "thumbs", f))
        _xoa(luu_tru._p(folder, luu_tru.CACHE, "proxy", f"{mid}.mp4"))
        if xoa_file and (m.get("file") or "").startswith(f"{luu_tru.MEDIA_DIR}/"):
            try:
                from send2trash import send2trash
                send2trash(luu_tru.duong_dan_media(folder, m["file"]))
            except (ImportError, OSError, ValueError):
                pass


def fps_gan_nhat(fps: float) -> float:
    from orchestrator.editor.workspace import FPS_HOP_LE
    return min(FPS_HOP_LE, key=lambda f: abs(f - float(fps or 30)))


def theo_video_dau(folder: str, ts: Dict[str, Any]) -> bool:
    """Dự án tạo với "Lấy theo video đầu tiên nhập vào": lấy khung + fps của video đầu rồi tắt cờ."""
    def ham(data):
        tsda = data.get("thong_so") or {}
        if not tsda.get("theo_video_dau"):
            return False
        rong, cao = int(ts["rong"]) - int(ts["rong"]) % 2, int(ts["cao"]) - int(ts["cao"]) % 2
        fps = fps_gan_nhat(ts.get("fps") or 30)
        data["thong_so"] = {**tsda, "rong": rong, "cao": cao, "fps": int(fps) if float(fps).is_integer() else fps,
                            "ti_le": luu_tru._ti_le(rong, cao), "theo_video_dau": False}
        return True
    try:
        return luu_tru.sua_duan(folder, ham)
    except ValueError:
        return False


def _trong(folder: str, path: str) -> bool:
    folder = os.path.normcase(os.path.abspath(folder))
    path = os.path.normcase(os.path.abspath(path))
    
    try:
        return os.path.commonpath([folder, path]) == folder
    except ValueError:
        return False


def _xoa(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ---------------------------------------------------------------- lệnh ffmpeg
def _chay(cmd: list, timeout: float = 300) -> bool:
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout,
                             creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0


def tao_thumb(src: str, dst: str, t: Optional[float]) -> bool:
    exe = ffmpeg_exe()
    if not exe:
        return False
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y"]
    if t:
        cmd += ["-ss", f"{t:.3f}"]
    cmd += ["-i", src, "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "4", dst]
    return _chay(cmd, 60) and os.path.exists(dst)


def lenh_dai_hinh(exe: str, src: str, dst: str, dai: float, so: int = SO_KHUNG_DAI, xoay: int = 0) -> list:
    """Dải khung hình cho clip trên timeline: `so` khung cao 54px ghép ngang thành một ảnh.

    Mỗi khung là một đầu vào `-ss` riêng (tua nhanh theo keyframe) thay vì
    `fps=…` trên cả file — video 1 giờ không phải giải mã hết.
    """
    so = max(1, min(so, int(dai) or 1))
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y"]
    for i in range(so):
        t = min(max(0.0, dai - 0.2), dai * (i + 0.5) / so)
        cmd += ["-ss", f"{t:.3f}", "-i", src]
        
    # KHÔNG tự transpose theo `xoay`: ffmpeg đã tự xoay khung theo displaymatrix khi giải mã (autorotate mặc định) —
    # thêm transpose là xoay HAI lần (video dọc 180×320 ra khung ngang 96×54). `xoay` giữ trong chữ ký để tương thích.
    loc = ";".join(f"[{i}:v]scale=-2:54,setsar=1,trim=end_frame=1[k{i}]" for i in range(so))
    if so > 1:
        loc += ";" + "".join(f"[k{i}]" for i in range(so)) + f"hstack=inputs={so}[ra]"
    else:
        loc += ";[k0]null[ra]"
    return cmd + ["-filter_complex", loc, "-map", "[ra]", "-frames:v", "1", "-q:v", "5", dst]


def tao_dai_hinh(src: str, dst: str, dai: float) -> int:
    exe = ffmpeg_exe()
    if not exe:
        return 0
    ts = do_thong_so(src)
    cmd = lenh_dai_hinh(exe, src, dst, dai, xoay=ts.get("xoay", 0))
    so = cmd.count("-ss")
    return so if _chay(cmd, 180) and os.path.exists(dst) else 0


def tao_song_am(src: str, dst: str) -> bool:
    exe = ffmpeg_exe()
    if not exe:
        return False
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-filter_complex",
           "aformat=channel_layouts=mono,showwavespic=s=1600x64:colors=white", "-frames:v", "1", dst]
    return _chay(cmd, 300) and os.path.exists(dst)


def lenh_proxy(exe: str, src: str, dst: str) -> list:
    return [exe, "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1", "-y",
            "-i", src, "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "scale=-2:'min(720,ih)':flags=bicubic,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-g", "30",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-movflags", "+faststart", dst]


def tao_proxy(src: str, dst: str, dai: float, ctx: Optional[hang_doi.NguCanh] = None) -> bool:
    """Bản H.264 720p cho preview. `-g 30` để tua trên timeline nhanh (keyframe dày)."""
    exe = ffmpeg_exe()
    if not exe:
        return False
    tmp = dst + ".tmp.mp4"
    try:
        proc = subprocess.Popen(lenh_proxy(exe, src, tmp), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                errors="replace", creationflags=NO_WINDOW)
    except OSError:
        return False
    try:
        for line in proc.stdout:
            if ctx is not None:
                if ctx.da_huy:
                    proc.kill()
                    raise hang_doi.DaHuy()
                m = re.match(r"out_time_us=(\d+)", line.strip())
                if m and dai > 0:
                    ctx.bao(int(m.group(1)) / 1e6 * 100.0 / dai)
        ok = proc.wait() == 0 and os.path.exists(tmp)
        if ok:
            os.replace(tmp, dst)
        return ok
    finally:
        if proc.poll() is None:
            proc.kill()
        _xoa(tmp)
