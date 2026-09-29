"""Đóng cửa sổ desktop: flush editor ở luồng riêng rồi mới đóng thật (không treo luồng giao diện)."""
import threading

from orchestrator import desktop


class _SuKien:
    def __init__(self):
        self.ham = []

    def __iadd__(self, f):
        self.ham.append(f)
        return self


class CuaSoGia:
    def __init__(self, tra_loi=True):
        self.events = type("E", (), {})()
        self.events.closing = _SuKien()
        self.tra_loi = tra_loi
        self.da_eval = []
        self.da_dong = threading.Event()

    def evaluate_js(self, script, callback=None):
        self.da_eval.append(script)
        if self.tra_loi and callback:
            threading.Timer(0.05, lambda: callback(True)).start()

    def destroy(self):
        # destroy() của WinForms gọi Close() → FormClosing chạy lại handler.
        if self.events.closing.ham[0]() is not False:
            self.da_dong.set()


def test_lan_dong_dau_huy_roi_flush_xong_moi_dong():
    w = CuaSoGia()
    on_closing = desktop._gan_flush_khi_dong(w, timeout=2)
    assert on_closing() is False, "lần đầu phải huỷ đóng để flush"
    assert w.da_dong.wait(3)
    assert w.da_eval == [desktop.FLUSH_JS]


def test_flush_khong_tra_loi_thi_van_dong_sau_timeout():
    w = CuaSoGia(tra_loi=False)
    on_closing = desktop._gan_flush_khi_dong(w, timeout=0.2)
    on_closing()
    assert w.da_dong.wait(2)


def test_huy_hop_thoai_xac_nhan_thi_lan_sau_lai_flush():
    w = CuaSoGia()
    on_closing = desktop._gan_flush_khi_dong(w, timeout=1)
    on_closing()
    assert w.da_dong.wait(3)
    # Người dùng bấm Cancel ở hộp "Bạn có chắc?" → cửa sổ còn; lần bấm X tiếp theo flush lại.
    assert on_closing() is False
