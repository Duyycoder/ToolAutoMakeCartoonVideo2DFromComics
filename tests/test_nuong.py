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


def test_doan_nuong_that_co_tieng_dai_va_tieng_vang_van_thoat_sach(tmp_path):
    """Hồi quy: nướng chỉ lấy vài khung đầu, hình kết thúc sớm trong khi nhánh tiếng (clip dài, có tiếng vang afir, nhiều
    track) còn đang chạy → ffmpeg ghi đủ khung rồi thoát mã lỗi "Invalid data found…", việc nướng bị coi là hỏng và
    xuất trên thiết bị dừng. Bản nướng không dùng tiếng nên không được dựng nhánh tiếng."""
    import subprocess

    import pytest

    from orchestrator.editor import media
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    (tmp_path / "media").mkdir()
    lam = tmp_path / "lam"
    lam.mkdir()
    for ten, nguon in (("v.mp4", ["-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=6", "-f", "lavfi", "-i", "sine=f=440:d=6",
                                  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"]),
                       ("a.mp3", ["-f", "lavfi", "-i", "sine=f=220:d=20"]), ("b.m4a", ["-f", "lavfi", "-i", "sine=f=330:d=12"])):
        r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *nguon, str(tmp_path / "media" / ten)],
                           capture_output=True, timeout=120)
        if r.returncode:
            pytest.skip("không tạo được media mẫu")
    du_an = {"thong_so": {"rong": 320, "cao": 180, "fps": 30}, "media": [
        {"id": "mv", "file": "media/v.mp4", "loai": "video", "rong": 320, "cao": 180, "thoi_luong": 6, "co_am_thanh": True},
        {"id": "ma", "file": "media/a.mp3", "loai": "audio", "thoi_luong": 20, "co_am_thanh": True},
        {"id": "mb", "file": "media/b.m4a", "loai": "audio", "thoi_luong": 12, "co_am_thanh": True}]}
    tl = {"tracks": [{"id": "V1", "loai": "video"}, {"id": "A1", "loai": "audio"}, {"id": "A2", "loai": "audio"}], "clips": [
        {"id": "c1", "track": "V1", "media": "mv", "bat_dau": 0, "vao": 0, "ra": 6, "toc_do": 1,
         "hieu_ung_am": {"vang": 60, "phong": "phong_lon"}},
        {"id": "c2", "track": "A1", "media": "ma", "bat_dau": 0, "vao": 0, "ra": 20, "toc_do": 1,
         "hieu_ung_am": {"vang": 40, "phong": "nha_tho", "doi": 30}},
        {"id": "c3", "track": "A2", "media": "mb", "bat_dau": 1, "vao": 0, "ra": 12, "toc_do": 1.5},
        {"id": "c4", "track": "A2", "media": "mb", "bat_dau": 10, "vao": 2, "ra": 9, "toc_do": 1}]}
    kq = render.dung_lenh_xuat(str(tmp_path), du_an, tl, {"doan_nuong": [[0, 20]], "bo_ma_hoa": "x264"},
                               str(lam / "doan.mp4"), exe, co_ass=False)
    assert "afir" not in kq["loc"] and "amix" not in kq["loc"], "bản nướng không được dựng nhánh tiếng thật"
    (lam / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    for ten, noi in (kq.get("tep") or {}).items():
        (lam / ten).write_text(noi, encoding="utf-8")
    res = subprocess.run(kq["cmd"], cwd=str(lam), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert res.returncode == 0, res.stderr[-600:]
    assert (lam / "doan.mp4").stat().st_size > 1000
