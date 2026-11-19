"""Chống rung (chong_rung.py): chuỗi bộ lọc theo độ mạnh + chạy thật trên video rung nhân tạo."""
import subprocess

import pytest

from orchestrator.editor import chong_rung, media


def test_bo_loc_theo_do_manh_va_du_phong_deshake():
    assert "smoothing=5:" in chong_rung.loc_buoc_2(1, True) and "smoothing=40:" in chong_rung.loc_buoc_2(100, True)
    assert chong_rung.loc_buoc_2(50, False).startswith("deshake=")
    with pytest.raises(ValueError):
        chong_rung.tao("ffmpeg", "a.mp4", "b.mp4", 2, 2, False)


def test_chong_rung_that(tmp_path):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    goc, ra = tmp_path / "rung.mp4", tmp_path / "on dinh.mp4"       # tên có dấu cách: đường dẫn không được lọt vào bộ lọc
    # Hình mẫu bị xê dịch qua lại vài điểm ảnh mỗi khung (rung) trên nền 320×240.
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=360x280:r=25:d=3",
                          "-f", "lavfi", "-i", "sine=f=440:d=3", "-vf", "crop=320:240:20+12*sin(n*1.7):20+10*cos(n*2.3)",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(goc)],
                         capture_output=True, timeout=120)
    if res.returncode:
        pytest.skip("không tạo được video mẫu")
    chong_rung.tao(exe, str(goc), str(ra), 0.5, 2.5, True, 60)
    ts = media.do_thong_so(str(ra))
    assert abs(float(ts["thoi_luong"]) - 2.0) < 0.15 and ts.get("rong") == 320 and ts.get("co_am_thanh") is not False
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("rung_")]            # thư mục tạm đã dọn
