"""Hàng đợi tác vụ của editor: một việc một lúc, huỷ, lỗi không chặn hàng, trạng thái trong dự án."""
import sys
import threading
import time

import pytest

from orchestrator.editor import hang_doi, luu_tru
from orchestrator.process_manager import ProcessManager


def test_khong_bao_gio_chay_hai_viec_cung_luc():
    h = hang_doi.HangDoi("gpu")
    dang, dinh, thu_tu = [0], [0], []
    khoa = threading.Lock()

    def viec(i):
        def lam(ctx):
            with khoa:
                dang[0] += 1
                dinh[0] = max(dinh[0], dang[0])
            time.sleep(0.03)
            thu_tu.append(i)
            with khoa:
                dang[0] -= 1
        return lam

    for i in range(6):
        h.them(hang_doi.Viec("whisper", viec(i)))
    assert h.cho_rong(5)
    assert dinh[0] == 1
    assert thu_tu == list(range(6)), "đến trước chạy trước"


def test_vi_tri_trong_hang_va_huy_viec_dang_cho():
    h = hang_doi.HangDoi("gpu")
    cho_mo = threading.Event()
    chay = []
    h.them(hang_doi.Viec("a", lambda ctx: cho_mo.wait(5)))
    b = h.them(hang_doi.Viec("b", lambda ctx: chay.append("b")))
    c = h.them(hang_doi.Viec("c", lambda ctx: chay.append("c")))
    time.sleep(0.05)
    vi_tri = {v["loai"]: v.get("vi_tri") for v in h.danh_sach()}
    assert vi_tri["b"] == 2 and vi_tri["c"] == 3

    assert h.huy(b.id)
    cho_mo.set()
    assert h.cho_rong(5)
    assert chay == ["c"] and b.trang_thai == hang_doi.DA_HUY


def test_viec_loi_khong_chan_hang():
    h = hang_doi.HangDoi("gpu")

    def hong(ctx):
        raise RuntimeError("CUDA out of memory")
    a = h.them(hang_doi.Viec("a", hong))
    b = h.them(hang_doi.Viec("b", lambda ctx: 42))
    assert h.cho_rong(5)
    assert a.trang_thai == hang_doi.LOI and "CUDA" in a.loi
    assert b.trang_thai == hang_doi.XONG and b.ket_qua == 42


def test_huy_viec_dang_chay():
    h = hang_doi.HangDoi("gpu")
    bat_dau = threading.Event()

    def lau(ctx):
        bat_dau.set()
        for _ in range(500):
            ctx.kiem_tra_huy()
            time.sleep(0.01)
    v = h.them(hang_doi.Viec("xuat", lau))
    assert bat_dau.wait(2)
    assert h.huy(v.id)
    assert h.cho_rong(5)
    assert v.trang_thai == hang_doi.DA_HUY


def test_chay_lenh_qua_process_manager_va_huy_diet_tien_trinh():
    pm = ProcessManager()
    h = hang_doi.HangDoi("gpu", pm)
    ok = h.them(hang_doi.Viec("thu", lambda ctx: ctx.chay_lenh([sys.executable, "-c", "print('xin chao')"], ".")))
    assert h.cho_rong(20)
    assert ok.trang_thai == hang_doi.XONG and ok.ket_qua == 0

    lau = h.them(hang_doi.Viec("lau", lambda ctx: ctx.chay_lenh(
        [sys.executable, "-c", "import time; time.sleep(60)"], ".")))
    han = time.time() + 10
    while lau.trang_thai != hang_doi.DANG_CHAY and time.time() < han:
        time.sleep(0.05)
    time.sleep(0.3)
    assert h.huy(lau.id)
    assert h.cho_rong(20)
    assert lau.trang_thai == hang_doi.DA_HUY
    assert not pm.is_running(lau.task_key)


def test_task_key_gan_voi_du_an():
    v = hang_doi.Viec("whisper", lambda c: None, du_an_id="abc")
    assert v.task_key.startswith("abc:whisper:")


@pytest.fixture
def du_an(tmp_path):
    folder = str(tmp_path / "da")
    luu_tru.tao_thu_muc_con(folder)
    luu_tru.ghi_duan(folder, {"schema": 2, "id": "abc", "name": "x", "media": [], "tac_vu": []})
    return folder


def test_trang_thai_tac_vu_ghi_vao_duan_va_bi_ngat_khi_mo_lai(du_an):
    h = hang_doi.HangDoi("gpu")
    xong = h.them(hang_doi.Viec("dich", lambda c: {"srt": "phu_de/a.vi.srt"}, du_an=du_an, du_an_id="abc"))
    assert h.cho_rong(5)
    tv = {t["id"]: t for t in luu_tru.doc_duan(du_an)["tac_vu"]}
    assert tv[xong.id]["trang_thai"] == "xong" and tv[xong.id]["ket_qua"] == {"srt": "phu_de/a.vi.srt"}

    # App tắt khi một tác vụ đang chạy: .duan.json còn ghi "dang_chay".
    def gia_dang_chay(d):
        d["tac_vu"].append({"id": "chet", "loai": "whisper", "trang_thai": "dang_chay"})
        d["tac_vu"].append({"id": "cho", "loai": "dich", "trang_thai": "cho"})
    luu_tru.sua_duan(du_an, gia_dang_chay)

    assert hang_doi.danh_dau_bi_ngat(du_an, ids_con_song={"cho"}) == 1
    tv = {t["id"]: t for t in luu_tru.doc_duan(du_an)["tac_vu"]}
    assert tv["chet"]["trang_thai"] == "bi_ngat"
    assert tv["cho"]["trang_thai"] == "cho", "việc còn trong hàng đợi thì không đụng"
    assert tv[xong.id]["trang_thai"] == "xong"


def test_cap_nhat_tac_vu_giu_co_da_ap_dung(du_an):
    hang_doi.ghi_tac_vu(du_an, {"id": "t1", "trang_thai": "xong"})

    def ap_dung(d):
        d["tac_vu"][0]["da_ap_dung"] = True
    luu_tru.sua_duan(du_an, ap_dung)
    hang_doi.ghi_tac_vu(du_an, {"id": "t1", "trang_thai": "xong", "thong_diep": "x"})
    assert luu_tru.doc_duan(du_an)["tac_vu"][0]["da_ap_dung"] is True
