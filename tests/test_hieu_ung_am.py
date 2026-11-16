"""Hiệu ứng âm thanh của clip (clip.hieu_ung_am) → ffmpeg chạy được thật và đổi tiếng đúng hướng."""
import re
import subprocess

import pytest

from orchestrator.editor import hieu_ung_am, media, render

FF = media.ffmpeg_exe()
pytestmark = pytest.mark.skipif(not FF, reason="cần ffmpeg")

DU_AN = {"thong_so": {"rong": 320, "cao": 180, "fps": 25},
         "media": [{"id": "m", "loai": "audio", "file": "media/a.m4a", "co_am_thanh": True}]}


@pytest.fixture(scope="module")
def goc(tmp_path_factory):
    g = tmp_path_factory.mktemp("am")
    (g / "media").mkdir()
    # 2 s: 1 s tiếng 440 Hz rồi 1 s im lặng — thấy được đuôi vang/dội ở giây sau.
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=f=440:d=1,apad=pad_dur=1", "-ac", "2", "-c:a", "aac", str(g / "media" / "a.m4a")], check=True)
    return g


def _xuat(goc, hu, ten):
    tl = {"tracks": [{"id": "V1", "loai": "video"}, {"id": "A1", "loai": "audio"}],
          "clips": [{"id": "c", "track": "A1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1, "hieu_ung_am": hu}]}
    ra = str(goc / f"{ten}.mp4")
    kq = render.dung_lenh_xuat(str(goc), DU_AN, tl, {"preset": "ultrafast"}, ra, FF)
    (goc / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    r = subprocess.run(kq["cmd"], cwd=str(goc), capture_output=True, text=True, errors="replace", timeout=120)
    assert r.returncode == 0, f"Xuất với {hu} lỗi: {r.stderr[-1200:]}"
    return ra


def _do(ra, t0, d):
    r = subprocess.run([FF, "-hide_banner", "-ss", str(t0), "-t", str(d), "-i", ra, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    m = re.search(r"mean_volume:\s*([-\d.]+)", r.stderr)
    return float(m.group(1)) if m else -91.0


@pytest.mark.parametrize("hu", [
    {"cao_do": 7}, {"cao_do": -5}, {"robot": True}, {"loc_bang": "dien_thoai"}, {"loc_bang": "loa"},
    {"meo": 60}, {"bit": 6}, {"rung": 80, "rung_tan": 8}, {"nen": 70}, {"dao_nguoc": True}, {"chuan_hoa": True},
    {"cao_do": 3, "robot": True, "meo": 20, "bit": 8, "rung": 30, "nen": 40, "doi": 50, "vang": 40, "phong": "hang",
     "chuan_hoa": True},
])
def test_moi_hieu_ung_xuat_duoc(goc, hu):
    ra = _xuat(goc, hu, "x")
    ts = media.do_thong_so(ra)
    assert abs(ts["thoi_luong"] - 2.0) < 0.15, f"{hu}: thời lượng phải giữ 2 s, ra {ts['thoi_luong']}"


def test_chi_xuat_am_thanh_chay_duoc(goc):
    """Chỉ xuất âm thanh (.m4a — cũng là đường server dựng tiếng cho xuất trên thiết bị) không được lỗi 'vc unconnected'."""
    tl = {"tracks": [{"id": "V1", "loai": "video"}, {"id": "A1", "loai": "audio"}],
          "clips": [{"id": "c", "track": "A1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
                     "hieu_ung_am": {"vang": 30}}]}
    ra = str(goc / "chi_tieng.m4a")
    kq = render.dung_lenh_xuat(str(goc), DU_AN, tl, {"chi_am_thanh": True}, ra, FF)
    (goc / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    r = subprocess.run(kq["cmd"], cwd=str(goc), capture_output=True, text=True, errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    ts = media.do_thong_so(ra)
    assert ts["co_am_thanh"] and not ts.get("co_hinh") and abs(ts["thoi_luong"] - 2.0) < 0.15


def test_vang_va_doi_de_lai_duoi_tieng(goc):
    kho = _do(_xuat(goc, {}, "kho"), 1.1, 0.4)
    vang = _do(_xuat(goc, {"vang": 80, "phong": "nha_tho"}, "vang"), 1.1, 0.4)
    doi = _do(_xuat(goc, {"doi": 80, "doi_tre": 300}, "doi"), 1.1, 0.4)
    assert vang > kho + 20, f"Sau khi hết tiếng phải còn đuôi vang (khô {kho} dB, vang {vang} dB)"
    assert doi > kho + 20, f"Sau khi hết tiếng phải còn tiếng dội (khô {kho} dB, dội {doi} dB)"


def test_dao_nguoc_dua_tieng_ve_cuoi(goc):
    ra = _xuat(goc, {"dao_nguoc": True}, "nguoc")
    assert _do(ra, 0.1, 0.6) < _do(ra, 1.3, 0.6) - 20, "Phát ngược: giây đầu im, giây sau có tiếng"


def test_khong_hieu_ung_thi_khong_them_loc():
    assert not hieu_ung_am.co_hieu_ung({}) and hieu_ung_am.loc_truoc_vang({}, 48000) == []
    assert hieu_ung_am.co_hieu_ung({"vang": 10}) and hieu_ung_am.co_hieu_ung({"robot": True})


def test_ir_phong_nang_luong_bang_1():
    du, dinh = hieu_ung_am.ir_phong("phong_nho")
    for k in (0, 1):
        e = sum((x[k] * dinh) ** 2 for x in du)
        assert abs(e - 1) < 1e-6, f"Năng lượng IR kênh {k} phải = 1 (đang {e})"


def test_hieu_ung_chung_ca_du_an(goc):
    """timeline.am_tong: hiệu ứng + âm lượng tổng áp lên tiếng đã trộn của cả dự án."""
    def xuat_tong(tong, ten):
        tl = {"tracks": [{"id": "V1", "loai": "video"}, {"id": "A1", "loai": "audio"}], "am_tong": tong,
              "clips": [{"id": "c", "track": "A1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1}]}
        ra = str(goc / f"{ten}.mp4")
        kq = render.dung_lenh_xuat(str(goc), DU_AN, tl, {"preset": "ultrafast"}, ra, FF)
        (goc / "loc.txt").write_text(kq["loc"], encoding="utf-8")
        r = subprocess.run(kq["cmd"], cwd=str(goc), capture_output=True, text=True, errors="replace", timeout=120)
        assert r.returncode == 0, r.stderr[-800:]
        return ra
    goc_ = xuat_tong({}, "tong0")
    nho = xuat_tong({"am_luong": 0.25}, "tong1")
    vang = xuat_tong({"vang": 80, "phong": "nha_tho", "nen": 30}, "tong2")
    assert _do(nho, 0.1, 0.8) < _do(goc_, 0.1, 0.8) - 10, "Âm lượng tổng 25% phải nhỏ hơn ~12 dB"
    assert _do(vang, 1.1, 0.4) > _do(goc_, 1.1, 0.4) + 20, "Vang tổng phải để lại đuôi sau khi hết tiếng"
    assert abs(media.do_thong_so(vang)["thoi_luong"] - 2.0) < 0.15
