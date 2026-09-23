"""Xoay vong app.log: truoc day file chi ghi noi them va da phinh toi ~950 MB."""
import os

from orchestrator.desktop import _rotate_log


def test_log_nho_thi_giu_nguyen(tmp_path):
    log = tmp_path / "app.log"
    log.write_bytes(b"x" * 100)

    _rotate_log(str(log), max_bytes=1000, keep_tail=10)

    assert log.read_bytes() == b"x" * 100
    assert not (tmp_path / "app.log.old").exists()


def test_log_qua_co_thi_chi_giu_phan_cuoi(tmp_path):
    log = tmp_path / "app.log"
    log.write_bytes(b"a" * 5000 + b"LOI MOI NHAT")

    _rotate_log(str(log), max_bytes=1000, keep_tail=12)

    # File moi bat dau tu dau, con phan cuoi (chua loi gan nhat) sang .old.
    assert not log.exists()
    assert (tmp_path / "app.log.old").read_bytes() == b"LOI MOI NHAT"


def test_xoay_lan_hai_thay_the_ban_old_cu(tmp_path):
    log = tmp_path / "app.log"
    old = tmp_path / "app.log.old"
    old.write_bytes(b"cu" * 10_000)
    log.write_bytes(b"b" * 5000)

    _rotate_log(str(log), max_bytes=1000, keep_tail=100)

    # Khong duoc de .old tich luy mai thanh mot file khong lo khac.
    assert os.path.getsize(str(old)) == 100


def test_chua_co_log_thi_khong_lam_gi(tmp_path):
    _rotate_log(str(tmp_path / "app.log"))
    assert os.listdir(str(tmp_path)) == []
