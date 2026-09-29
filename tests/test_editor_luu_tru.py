"""Lưu tiến độ dự án (editor): ghi nguyên tử, phiên bản/409, hoàn tác, lịch sử, khoá, nâng cấp."""
import json
import os

import pytest

from orchestrator import project
from orchestrator.editor import luu_tru


class DongHo:
    """Đồng hồ giả: test tự vặn giờ thay vì ngủ 5 phút."""

    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def gio(monkeypatch):
    dh = DongHo()
    monkeypatch.setattr(luu_tru, "_gio", dh)
    return dh


@pytest.fixture
def du_an(tmp_path):
    folder = tmp_path / "du_an"
    folder.mkdir()
    luu_tru.tao_thu_muc_con(str(folder))
    luu_tru.ghi_duan(str(folder), {"schema": 2, "id": "abc", "name": "x", "media": [], "tac_vu": []})
    return str(folder)


def _tl(**them):
    tl = luu_tru.timeline_rong()
    tl.update(them)
    return tl


# ------------------------------------------------------------- ghi nguyên tử
def test_ghi_nguyen_tu_bi_ngat_luc_doi_ten_giu_nguyen_ban_cu(tmp_path, monkeypatch):
    path = str(tmp_path / "a.json")
    luu_tru.ghi_nguyen_tu(path, {"v": 1})

    def hong(*_a):
        raise OSError("mất điện")
    monkeypatch.setattr(luu_tru.os, "replace", hong)
    with pytest.raises(OSError):
        luu_tru.ghi_nguyen_tu(path, {"v": 2})

    assert json.load(open(path, encoding="utf-8")) == {"v": 1}
    assert os.listdir(tmp_path) == ["a.json"], "không được để lại file tạm"


def test_ghi_nguyen_tu_loi_giua_luc_ghi_noi_dung(tmp_path, monkeypatch):
    path = str(tmp_path / "a.json")
    luu_tru.ghi_nguyen_tu(path, {"v": 1})

    def dump_do_dang(data, fh, **_kw):
        fh.write('{"v": 2, "cat_ngang')
        raise OSError("tắt ngang")
    monkeypatch.setattr(luu_tru.json, "dump", dump_do_dang)
    with pytest.raises(OSError):
        luu_tru.ghi_nguyen_tu(path, {"v": 2})
    monkeypatch.undo()
    assert json.load(open(path, encoding="utf-8")) == {"v": 1}


# --------------------------------------------------------- phiên bản + hoàn tác
def test_ghi_timeline_tang_phien_ban_va_409_khi_lech(du_an, gio):
    assert luu_tru.ghi_timeline(du_an, _tl(), 0) == 1
    assert luu_tru.ghi_timeline(du_an, _tl(), 1) == 2
    with pytest.raises(luu_tru.XungDotPhienBan) as e:
        luu_tru.ghi_timeline(du_an, _tl(), 1)   # cửa sổ thứ hai còn giữ bản cũ
    assert e.value.hien_tai == 2
    tl, thong_bao = luu_tru.doc_timeline(du_an)
    assert tl["phien_ban"] == 2 and thong_bao is None


def test_timeline_khong_hop_le_bi_tu_choi(du_an):
    with pytest.raises(ValueError):
        luu_tru.ghi_timeline(du_an, {"clips": "x"}, 0)


def test_hoan_tac_ghi_kem_phien_ban_va_bo_khi_lech(du_an, gio):
    luu_tru.ghi_timeline(du_an, _tl(), 0, {"hoan_tac": list(range(80)), "lam_lai": []})
    ht, bo = luu_tru.doc_hoan_tac(du_an, 1)
    assert not bo and ht["phien_ban"] == 1
    assert len(ht["hoan_tac"]) == luu_tru.SO_BUOC_HOAN_TAC and ht["hoan_tac"][-1] == 79

    # Tắt ngang sau khi ghi timeline v2 nhưng trước khi ghi hoan_tac → hoan_tac còn v1.
    luu_tru.ghi_timeline(du_an, _tl(), 1)
    ht, bo = luu_tru.doc_hoan_tac(du_an, 2)
    assert ht is None and bo


# ------------------------------------------------------------------- lịch sử
def test_lich_su_tu_dong_5_phut_mot_ban_va_xoay_vong_20(du_an, gio):
    pb = 0
    pb = luu_tru.ghi_timeline(du_an, _tl(), pb)
    gio.t += 60
    pb = luu_tru.ghi_timeline(du_an, _tl(), pb)     # chưa đủ 5 phút → không chụp thêm
    assert [b["loai"] for b in luu_tru.danh_sach_phien_ban(du_an)] == ["tu_dong"]

    ten_luu = luu_tru.luu_thu_cong(du_an, "Bản gửi khách")
    for _ in range(25):
        gio.t += luu_tru.CHU_KY_TU_DONG + 1
        pb = luu_tru.ghi_timeline(du_an, _tl(), pb)
    ds = luu_tru.danh_sach_phien_ban(du_an)
    assert sum(b["loai"] == "tu_dong" for b in ds) == 20
    luu = [b for b in ds if b["loai"] == "luu"]
    assert [b["ten"] for b in luu] == [ten_luu], "bản lưu tay không bị xoá vòng"
    assert luu[0]["nhan"] == "Bản gửi khách"
    assert ds[0]["loai"] == "tu_dong", "mới nhất đứng đầu"


def test_khoi_phuc_ban_cu_la_mot_lan_ghi_moi(du_an, gio):
    luu_tru.ghi_timeline(du_an, _tl(thoi_luong=5), 0)
    ten = luu_tru.luu_thu_cong(du_an)
    gio.t += 10
    luu_tru.ghi_timeline(du_an, _tl(thoi_luong=99), 1)

    tl = luu_tru.khoi_phuc(du_an, ten, 2)
    assert tl["thoi_luong"] == 5 and tl["phien_ban"] == 3 and "_nhan" not in tl
    with pytest.raises(ValueError):
        luu_tru.khoi_phuc(du_an, "../../.duan.json", 3)


def test_timeline_hong_lay_lai_ban_lich_su(du_an, gio):
    luu_tru.ghi_timeline(du_an, _tl(thoi_luong=7), 0)   # chụp tu_dong luôn
    with open(os.path.join(du_an, ".duan", "timeline.json"), "w", encoding="utf-8") as fh:
        fh.write('{"clips": [')                         # mất điện giữa lúc ghi (không qua ghi_nguyen_tu)

    tl, thong_bao = luu_tru.doc_timeline(du_an)
    assert tl["thoi_luong"] == 7
    assert "khôi phục" in thong_bao
    assert any(f.startswith("timeline.hong_") for f in os.listdir(os.path.join(du_an, ".duan")))
    # Đã ghi lại timeline lành → lần mở sau không báo nữa.
    assert luu_tru.doc_timeline(du_an)[1] is None


def test_timeline_hong_khong_co_lich_su_mo_trong(du_an):
    with open(os.path.join(du_an, ".duan", "timeline.json"), "w", encoding="utf-8") as fh:
        fh.write("rác")
    tl, thong_bao = luu_tru.doc_timeline(du_an)
    assert tl["clips"] == [] and "không có bản lịch sử" in thong_bao


# ----------------------------------------------------------------------- khoá
def test_khoa_cua_so_thu_hai_chi_doc_toi_khi_het_nhip(du_an, gio):
    a = luu_tru.lay_khoa(du_an)
    b = luu_tru.lay_khoa(du_an)
    assert not a["chi_doc"] and b["chi_doc"]
    with pytest.raises(luu_tru.KhongGiuKhoa):
        luu_tru.kiem_tra_khoa(du_an, b["phien"])
    luu_tru.kiem_tra_khoa(du_an, a["phien"])

    gio.t += 30
    assert luu_tru.nhip(du_an, a["phien"])            # A còn sống, nhịp mới
    gio.t += 30
    assert not luu_tru.nhip(du_an, b["phien"])        # mới 30s từ nhịp cuối của A

    gio.t += luu_tru.KHOA_HET_HAN + 1                 # A chết (tắt ngang, không nhả khoá)
    assert luu_tru.nhip(du_an, b["phien"])
    with pytest.raises(luu_tru.KhongGiuKhoa):
        luu_tru.kiem_tra_khoa(du_an, a["phien"])


def test_dong_app_mo_lai_ngay_khong_bi_chi_doc(du_an, gio, monkeypatch):
    """Khoá do lần chạy server trước để lại (app đã tắt) — nhịp còn mới vẫn coi là chết."""
    luu_tru.lay_khoa(du_an)
    monkeypatch.setattr(luu_tru, "MAY_CHU", "lan_chay_moi")
    gio.t += 2
    assert not luu_tru.lay_khoa(du_an)["chi_doc"]


def test_tai_lai_trang_cung_phien_khong_tu_khoa_minh(du_an, gio):
    a = luu_tru.lay_khoa(du_an)
    lai = luu_tru.lay_khoa(du_an, a["phien"])
    assert lai["phien"] == a["phien"] and not lai["chi_doc"]


def test_hai_cua_so_cung_pid_van_phan_biet_duoc(du_an, gio):
    """Khoá theo pid sẽ cho qua cả hai (cùng một server uvicorn) — khoá theo phiên thì không."""
    a, b = luu_tru.lay_khoa(du_an), luu_tru.lay_khoa(du_an)
    assert a["phien"] != b["phien"] and b["chi_doc"]


def test_nha_khoa_chi_khi_dung_phien(du_an, gio):
    a = luu_tru.lay_khoa(du_an)
    luu_tru.nha_khoa(du_an, "phien_khac")
    assert luu_tru.dang_bi_giu(du_an)
    luu_tru.nha_khoa(du_an, a["phien"])
    assert not luu_tru.dang_bi_giu(du_an)
    assert not luu_tru.lay_khoa(du_an)["chi_doc"]


# ------------------------------------------------------------------ tiện ích
def test_duong_dan_media_chan_ra_ngoai_du_an(du_an):
    assert luu_tru.duong_dan_media(du_an, "media/a b.mp4").endswith(os.path.join("media", "a b.mp4"))
    for xau in ("../x.mp4", "media/../../x.mp4", "", "C:/Windows/win.ini"):
        with pytest.raises(ValueError):
            luu_tru.duong_dan_media(du_an, xau)


def test_id_moi_noi_tiep_so_lon_nhat():
    assert luu_tru.id_moi([], "m") == "m_01"
    assert luu_tru.id_moi(["m_01", "m_07", "x_99", "m_x"], "m") == "m_08"


# ------------------------------------------------------------ nâng cấp 1 → 2
@pytest.fixture
def du_an_cu(tmp_path):
    folder = tmp_path / "cu"
    folder.mkdir()
    for ten in ("tap 1.mp4", "tap 2.mp4", "tap 3.mp4"):
        (folder / ten).write_bytes(b"0" * 64)
    project.init(str(folder), "Phim cũ", doi_ten=True)
    data = project.doc(str(folder))
    data["videos"][2]["merged_into"] = "phim.mp4"
    project.ghi(str(folder), data)
    (folder / "phu_de" / "001_tap_1.en.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    (folder / "da_sub" / "001_tap_1.mp4").write_bytes(b"1" * 64)
    return str(folder)


def _cay(folder):
    out = []
    for goc, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != ".duan"]
        out += [os.path.relpath(os.path.join(goc, f), folder) for f in files if f != ".duan.json"]
    return sorted(out)


def test_nang_cap_schema1_khong_di_chuyen_file(du_an_cu):
    truoc = _cay(du_an_cu)
    dai = {"001_tap_1.mp4": 5.0, "002_tap_2.mp4": 7.5, "003_tap_3.mp4": 2.0}
    data = luu_tru.nang_cap(du_an_cu, lambda p: {"thoi_luong": dai.get(os.path.basename(p), 3.0),
                                                 "rong": 1080, "cao": 1920, "fps": 30})
    assert _cay(du_an_cu) == truoc, "không file nào bị di chuyển/đổi tên"
    assert data["schema"] == 2 and data["id"] and data["thong_so"]["ti_le"] == "9:16"
    assert data["videos"], "giữ khoá cũ để 'Hoàn tác đổi tên' vẫn chạy"
    assert os.path.exists(os.path.join(du_an_cu, ".duan", "lich_su", "schema1.json"))

    theo_file = {m["file"]: m for m in data["media"]}
    assert theo_file["001_tap_1.mp4"]["loai"] == "video"
    srt = theo_file["phu_de/001_tap_1.en.srt"]
    assert srt["loai"] == "phu_de" and srt["tu_media"] == theo_file["001_tap_1.mp4"]["id"]
    assert theo_file["da_sub/001_tap_1.mp4"]["la_ban_xuat"] is True

    tl, _ = luu_tru.doc_timeline(du_an_cu)
    v1 = [(c["media"], c["bat_dau"], c["ra"]) for c in tl["clips"] if c["track"] == "V1"]
    assert v1 == [(theo_file["001_tap_1.mp4"]["id"], 0.0, 5.0),
                  (theo_file["002_tap_2.mp4"]["id"], 5.0, 7.5)], "theo thứ tự cũ, bỏ video đã ghép"
    assert tl["thoi_luong"] == 12.5

    # Chạy lại không làm gì thêm.
    assert luu_tru.nang_cap(du_an_cu)["id"] == data["id"]


def test_nang_cap_xong_van_hoan_tac_doi_ten_duoc(du_an_cu):
    luu_tru.nang_cap(du_an_cu)
    project.hoan_tac(du_an_cu)
    assert os.path.exists(os.path.join(du_an_cu, "tap 1.mp4"))
