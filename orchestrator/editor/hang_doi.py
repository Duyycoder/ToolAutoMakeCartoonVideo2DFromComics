"""Hàng đợi tác vụ — mỗi hàng chạy ĐÚNG MỘT việc một lúc, theo thứ tự đến trước.

Trước đây app chỉ chặn chạy trùng *cùng một loại* (`task_key` cố định "download",
"translate", "merge"): dịch và ghép vẫn chạy song song được, còn dự án A đang
Whisper thì dự án B bị chặn hẳn. GPU 6 GB không kham nổi hai việc nặng một lúc,
nên editor dùng hàng đợi thật:

- `hang_gpu`   Whisper, OCR, dịch bằng Ollama, lồng tiếng, Demucs, làm nét, xuất video
- các hàng nhẹ (chép media, thumbnail/sóng âm, proxy) — tạo riêng trong `media.py`
  để chép file 4 GB không chặn thumbnail của file khác.

Tác vụ của một dự án ghi vào `.duan.json › tac_vu[]`. Đóng app thì `desktop._shutdown()`
gọi `process_mgr.stop_all()` → tiến trình con chết; lúc mở lại, tác vụ còn
`cho`/`dang_chay` mà hàng đợi không biết thì thành `bi_ngat` (xem `danh_dau_bi_ngat`).
"""
import datetime
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional

from orchestrator.editor import luu_tru

CHO, DANG_CHAY, XONG, LOI, BI_NGAT, DA_HUY = "cho", "dang_chay", "xong", "loi", "bi_ngat", "da_huy"
CON_DO = (CHO, DANG_CHAY)
SO_TAC_VU_GIU = 100


class DaHuy(Exception):
    """Việc bị người dùng huỷ giữa chừng."""


class Viec:
    def __init__(self, loai: str, ham: Callable[["NguCanh"], Any], du_an: str = "",
                 du_an_id: str = "", nhan: str = "", tham_so: Optional[dict] = None,
                 media: str = ""):
        self.id = uuid.uuid4().hex[:10]
        self.loai = loai
        self.ham = ham
        self.du_an = du_an            # thư mục dự án ("" = việc không thuộc dự án nào)
        self.du_an_id = du_an_id
        self.nhan = nhan
        self.media = media
        self.tham_so = tham_so or {}
        self.trang_thai = CHO
        self.tien_do: Optional[float] = None
        self.thong_diep = ""
        self.loi = ""
        self.ket_qua: Any = None
        self.tao_luc = _iso()
        self.bat_dau = ""
        self.xong_luc = ""
        self.huy_event = threading.Event()

    @property
    def task_key(self) -> str:
        return f"{self.du_an_id or '_'}:{self.loai}:{self.id}"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "loai": self.loai, "nhan": self.nhan, "media": self.media,
                "du_an_id": self.du_an_id, "tham_so": self.tham_so, "trang_thai": self.trang_thai,
                "tien_do": self.tien_do, "thong_diep": self.thong_diep, "loi": self.loi,
                "ket_qua": self.ket_qua if _json_duoc(self.ket_qua) else None,
                "task_key": self.task_key, "tao_luc": self.tao_luc, "bat_dau": self.bat_dau,
                "xong_luc": self.xong_luc, "da_ap_dung": False}


def _iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _json_duoc(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool, list, dict))


class NguCanh:
    """Thứ một việc được dùng khi chạy: báo tiến độ, chạy lệnh con, kiểm tra huỷ."""

    def __init__(self, viec: Viec, hang: "HangDoi"):
        self.viec = viec
        self._hang = hang

    @property
    def da_huy(self) -> bool:
        return self.viec.huy_event.is_set()

    def kiem_tra_huy(self) -> None:
        if self.da_huy:
            raise DaHuy()

    def bao(self, tien_do: Optional[float] = None, thong_diep: Optional[str] = None) -> None:
        if tien_do is not None:
            self.viec.tien_do = max(0.0, min(100.0, float(tien_do)))
        if thong_diep is not None:
            self.viec.thong_diep = thong_diep
        self._hang._bao_doi(self.viec, luu=False)

    def chay_lenh(self, cmd: list, cwd: str, env: Optional[dict] = None) -> int:
        """Chạy tiến trình con qua ProcessManager (log SSE theo `viec.task_key`) và CHỜ xong.

        Huỷ → diệt cả cây tiến trình. `stop_process` nhả slot mà không gọi
        `on_completed`, nên phải tự thăm dò `is_running` thay vì chỉ chờ callback.
        """
        pm = self._hang.process_mgr
        if pm is None:
            raise RuntimeError("Hàng đợi này không có ProcessManager.")
        xong = threading.Event()
        ma: Dict[str, int] = {}

        def on_completed(code: int):
            ma["code"] = code
            xong.set()

        key = self.viec.task_key
        if not pm.start_process(key, cmd, cwd, env_override=env, on_completed=on_completed):
            raise RuntimeError(f"Không khởi động được tiến trình cho '{self.viec.loai}'.")
        while not xong.wait(0.3):
            if self.da_huy:
                pm.stop_process(key)
                raise DaHuy()
            if not pm.is_running(key):
                if xong.wait(1.0):
                    break
                return pm.completed_exit_codes.get(key, -1)
        return ma.get("code", -1)


    def chay_doc_dong(self, cmd: list, cwd: str, khi_dong: Callable[[str], None],
                      log: str = "", env: Optional[dict] = None) -> int:
        """Chạy tiến trình con, đưa TỪNG DÒNG output cho `khi_dong` (đọc event JSON của adapter),
        chép hết ra file `log`. Huỷ → diệt cả cây tiến trình (adapter + ffmpeg/Whisper con)."""
        import os
        import subprocess
        from orchestrator.process_manager import NO_WINDOW, ProcessManager
        moi_truong = os.environ.copy()
        moi_truong["PYTHONIOENCODING"] = "utf-8"
        moi_truong.update(env or {})
        fh = None
        if log:
            os.makedirs(os.path.dirname(log), exist_ok=True)
            fh = open(log, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=moi_truong, creationflags=NO_WINDOW)
        dung = threading.Event()

        def canh():   # huỷ phải có hiệu lực cả khi tiến trình im lặng không in gì
            while not dung.wait(0.3):
                if self.da_huy and proc.poll() is None:
                    ProcessManager._kill_process_tree(proc)
                    return
        threading.Thread(target=canh, daemon=True).start()
        try:
            for dong in proc.stdout:
                if fh:
                    fh.write(dong)
                    fh.flush()
                try:
                    khi_dong(dong.rstrip("\n"))
                except Exception:
                    pass
            code = proc.wait()
        finally:
            dung.set()
            if proc.poll() is None:
                ProcessManager._kill_process_tree(proc)
            if fh:
                fh.close()
        if self.da_huy:
            raise DaHuy()
        return code


class HangDoi:
    def __init__(self, ten: str, process_mgr=None,
                 khi_doi: Optional[Callable[[Viec], None]] = None):
        self.ten = ten
        self.process_mgr = process_mgr
        self._khi_doi = khi_doi
        self._cho: Deque[Viec] = deque()
        self._dang_chay: Optional[Viec] = None
        self._da_xong: Deque[Viec] = deque(maxlen=50)
        self._cv = threading.Condition()
        self._luong: Optional[threading.Thread] = None

    # ---------------------------------------------------------------- công khai
    def them(self, viec: Viec) -> Viec:
        # Ghi "cho" TRƯỚC khi xếp hàng: ghi sau thì luồng chạy có thể đã ghi
        # "dang_chay" rồi bị bản "cho" đè lên.
        self._bao_doi(viec)
        with self._cv:
            self._cho.append(viec)
            if self._luong is None or not self._luong.is_alive():
                self._luong = threading.Thread(target=self._chay, name=f"hang-{self.ten}", daemon=True)
                self._luong.start()
            self._cv.notify_all()
        return viec

    def huy(self, viec_id: str) -> bool:
        with self._cv:
            for v in list(self._cho):
                if v.id == viec_id:
                    self._cho.remove(v)
                    v.trang_thai = DA_HUY
                    v.xong_luc = _iso()
                    self._da_xong.append(v)
                    break
            else:
                v = self._dang_chay if self._dang_chay and self._dang_chay.id == viec_id else None
                if v is None:
                    return False
                v.huy_event.set()
                return True
        self._bao_doi(v)
        return True

    def tim(self, viec_id: str) -> Optional[Viec]:
        with self._cv:
            for v in self._tat_ca():
                if v.id == viec_id:
                    return v
        return None

    def danh_sach(self, du_an_id: str = "") -> List[Dict[str, Any]]:
        with self._cv:
            out = []
            for thu_tu, v in enumerate(self._tat_ca()):
                if du_an_id and v.du_an_id != du_an_id:
                    continue
                d = v.to_dict()
                d["hang"] = self.ten
                if v.trang_thai == CHO:
                    d["vi_tri"] = list(self._cho).index(v) + (2 if self._dang_chay else 1)
                out.append(d)
            return out

    def ids_con_song(self) -> set:
        with self._cv:
            return {v.id for v in self._cho} | ({self._dang_chay.id} if self._dang_chay else set())

    def cho_rong(self, timeout: float = 10.0) -> bool:
        """Chờ hết việc (dùng cho test)."""
        het_han = time.time() + timeout
        with self._cv:
            while self._cho or self._dang_chay:
                con = het_han - time.time()
                if con <= 0:
                    return False
                self._cv.wait(con)
        return True

    # ----------------------------------------------------------------- nội bộ
    def _tat_ca(self) -> List[Viec]:
        return list(self._da_xong) + ([self._dang_chay] if self._dang_chay else []) + list(self._cho)

    def _chay(self) -> None:
        while True:
            with self._cv:
                if not self._cho:
                    self._luong = None
                    self._cv.notify_all()
                    return
                viec = self._cho.popleft()
                self._dang_chay = viec
                viec.trang_thai = DANG_CHAY
                viec.bat_dau = _iso()
            self._bao_doi(viec)
            try:
                viec.ket_qua = viec.ham(NguCanh(viec, self))
                viec.trang_thai = DA_HUY if viec.huy_event.is_set() else XONG
                if viec.trang_thai == XONG:
                    viec.tien_do = 100.0
            except DaHuy:
                viec.trang_thai = DA_HUY
            except Exception as e:  # việc lỗi không được chặn cả hàng
                viec.trang_thai = LOI
                viec.loi = str(e) or e.__class__.__name__
            viec.xong_luc = _iso()
            # Ghi trạng thái cuối trước khi nhả chỗ: ai thấy hàng rỗng là đọc được kết quả.
            self._bao_doi(viec)
            with self._cv:
                self._dang_chay = None
                self._da_xong.append(viec)
                self._cv.notify_all()

    def _bao_doi(self, viec: Viec, luu: bool = True) -> None:
        if luu and viec.du_an:
            try:
                ghi_tac_vu(viec.du_an, viec.to_dict())
            except (OSError, ValueError):
                pass
        if self._khi_doi:
            try:
                self._khi_doi(viec)
            except Exception:
                pass


# ------------------------------------------------------- Tác vụ trong .duan.json
def ghi_tac_vu(folder: str, tv: Dict[str, Any]) -> None:
    """Thêm/cập nhật một tác vụ trong `.duan.json › tac_vu[]` (giữ 100 cái gần nhất).

    Giữ nguyên `da_ap_dung` đã có: cờ này do người dùng bấm [Áp dụng], hàng đợi không biết.
    """
    def sua(data):
        ds = data.setdefault("tac_vu", [])
        for i, cu in enumerate(ds):
            if cu.get("id") == tv["id"]:
                ds[i] = {**tv, "da_ap_dung": cu.get("da_ap_dung", False)}
                break
        else:
            ds.append(dict(tv))
        del ds[:-SO_TAC_VU_GIU]
    luu_tru.sua_duan(folder, sua)


def danh_dau_bi_ngat(folder: str, ids_con_song: set) -> int:
    """Lúc mở dự án: tác vụ còn dở mà hàng đợi không biết (app đã tắt) → `bi_ngat`."""
    def sua(data):
        so = 0
        for tv in data.get("tac_vu") or []:
            if tv.get("trang_thai") in CON_DO and tv.get("id") not in ids_con_song:
                tv["trang_thai"] = BI_NGAT
                tv["thong_diep"] = "Bị ngắt vì app đã đóng — bấm Chạy lại."
                so += 1
        return so
    data = luu_tru.doc_duan(folder) or {}
    if not any(tv.get("trang_thai") in CON_DO and tv.get("id") not in ids_con_song
               for tv in data.get("tac_vu") or []):
        return 0
    return luu_tru.sua_duan(folder, sua)
