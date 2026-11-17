"""Server nướng cho xuất trên thiết bị: kế hoạch ảnh lớp chữ (libass) + lệnh đoạn nướng."""
from orchestrator.editor import nuong, render

ASS = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 5,0:00:01.00,0:00:02.00,k_mac_dinh,,0,0,0,,Câu một
Dialogue: 5,0:00:01.50,0:00:03.00,k_mac_dinh,,0,0,0,,Câu hai
Dialogue: 2,0:00:04.00,0:00:04.20,k_mac_dinh,,0,0,0,,{\\fad(500,0)}Động
"""


def test_su_kien_ass():
    assert nuong.su_kien_ass(ASS) == [(1000, 2000, False), (1500, 3000, False), (4000, 4200, True)]


def test_ke_hoach_lop_chu_gop_doan_dung_yen_va_tach_khung_dong():
    kh = nuong.ke_hoach_lop_chu(ASS, 0, 150, 10)
    assert kh[:3] == [{"tu": 10, "den": 15, "khung": 10}, {"tu": 15, "den": 20, "khung": 15},
                      {"tu": 20, "den": 30, "khung": 20}]
    assert kh[3:] == [{"tu": n, "den": n + 1, "khung": n} for n in (40, 41)]


def test_ke_hoach_cat_theo_vung_xuat():
    assert nuong.ke_hoach_lop_chu(ASS, 12, 18, 10) == [{"tu": 12, "den": 15, "khung": 12}, {"tu": 15, "den": 18, "khung": 15}]


def test_khung_dau_khop_moc_ms_libass():
    # 29.97 fps: khung 30 = 1001 ms → sự kiện bắt đầu 1000 ms hiện từ khung 30 (khung 29 = 968 ms chưa hiện).
    assert nuong._khung_dau(1000, 30000 / 1001) == 30


def test_loc_lop_chu_chon_dung_khung():
    loc = nuong.loc_lop_chu(1280, 720, 30, [3, 4, 5, 9])
    assert "select='between(n,3,5)+eq(n,9)'" in loc
    assert "unpremultiply" in loc and loc.count("subtitles=sub.ass") == 2


def test_ten_file_nuong_khong_thoat_thu_muc():
    for ten in ("chu_00001.png", "doan.mp4", "a1b2c3d4e5"):
        assert nuong.TEN_FILE.match(ten)
    for ten in ("..", ".", "../x", "a/b", "a\\b", "x..png", ".thu", "A.png", ""):
        assert not nuong.TEN_FILE.match(ten), ten


def test_doan_nuong_chi_giu_khung_can(tmp_path):
    du_an = {"thong_so": {"rong": 1920, "cao": 1080, "fps": 30}, "media": [
        {"id": "m1", "file": "a.mp4", "loai": "video", "rong": 1920, "cao": 1080, "thoi_luong": 10, "co_am_thanh": True}]}
    tl = {"tracks": [{"id": "V1", "loai": "video"}],
          "clips": [{"id": "c1", "track": "V1", "media": "m1", "bat_dau": 0, "vao": 0, "ra": 10}]}
    kq = render.dung_lenh_xuat(str(tmp_path), du_an, tl, {"doan_nuong": [[30, 60], [90, 120]]}, "doan.mp4", co_ass=False)
    assert "select='between(n,30,59)+between(n,90,119)'" in kq["loc"] and "trim=end_frame=120" in kq["loc"]
    assert kq["so_khung"] == 60 and "-an" in kq["cmd"] and kq["cmd"][-1] == "doan.mp4"
    assert "[aout]" not in " ".join(kq["cmd"]) and "[aout]anullsink" in kq["loc"]
