"""Xoá nền AI (xoa_nen.py): ghép màu khoá theo mặt nạ, đường ống ffmpeg với hàm dự đoán giả, và model thật nếu có."""
import os
import subprocess

import pytest

from orchestrator.editor import media, xoa_nen

np = pytest.importorskip("numpy")


def test_kich_thuoc_ra_giu_ti_le_va_chan():
    assert xoa_nen.kich_thuoc_ra(1920, 1080) == [1280, 720]
    assert xoa_nen.kich_thuoc_ra(1080, 1920) == [720, 1280]
    assert xoa_nen.kich_thuoc_ra(641, 359) == [640, 360]             # nhỏ hơn giới hạn: chỉ làm chẵn


def test_ghep_mau_khoa_giu_chu_the_thay_nen():
    khung = np.full((40, 60, 3), 200, dtype=np.uint8)
    mat_na = np.zeros((8, 8), dtype=np.float32)
    mat_na[:, 4:] = 1.0                                              # nửa phải là chủ thể
    ra = xoa_nen.ghep_mau_khoa(khung, mat_na)
    assert tuple(ra[20, 5]) == xoa_nen.MAU_KHOA and tuple(ra[20, 55]) == (200, 200, 200)
    assert ra.shape == khung.shape and ra.dtype == np.uint8


def _video_mau(exe, path):
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:r=10:d=2",
                          "-f", "lavfi", "-i", "sine=f=440:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                          "-shortest", str(path)], capture_output=True, timeout=60)
    return res.returncode == 0


def _diem(exe, path, t, x, y):
    r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=60)
    return np.frombuffer(r.stdout, dtype=np.uint8).reshape(180, 320, 3)[y, x]


def test_duong_ong_voi_du_doan_gia(tmp_path):
    exe = media.ffmpeg_exe()
    if not exe or not _video_mau(exe, tmp_path / "a.mp4"):
        pytest.skip("không có ffmpeg / không tạo được video mẫu")

    def gia(khung):                                                  # "chủ thể" = nửa trái khung
        m = np.zeros((xoa_nen.CANH, xoa_nen.CANH), dtype=np.float32)
        m[:, :xoa_nen.CANH // 2] = 1.0
        return m
    tien_do = []
    so = xoa_nen.tao(exe, str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4"), 0.5, 1.5, 320, 180, 10, True, gia, tien_do.append)
    assert so == 10 and tien_do[-1] == 1.0
    ts = media.do_thong_so(str(tmp_path / "b.mp4"))
    assert abs(float(ts["thoi_luong"]) - 1.0) < 0.15 and ts.get("rong") == 320 and ts.get("co_am_thanh") is not False
    trai, phai = _diem(exe, tmp_path / "b.mp4", 0.5, 60, 90), _diem(exe, tmp_path / "b.mp4", 0.5, 260, 90)
    assert trai[0] > 180 and trai[1] < 80, f"chủ thể (nửa trái) giữ màu đỏ: {trai}"
    assert phai[1] > 180 and phai[0] < 80, f"nền (nửa phải) thành xanh khoá: {phai}"
    with pytest.raises(ValueError):
        xoa_nen.tao(exe, "a.mp4", "b.mp4", 1, 1, 320, 180, 10, False, gia)


def test_model_that_ra_mat_na_dung_co(tmp_path):
    if not os.path.isfile(xoa_nen.MODEL):
        pytest.skip("chưa có model u2netp.onnx")
    pytest.importorskip("onnxruntime")
    du_doan = xoa_nen.tao_du_doan()
    # Hình tròn sáng giữa nền tối: model phải thấy "chủ thể" ở giữa nổi hơn bốn góc.
    yy, xx = np.mgrid[0:240, 0:320]
    khung = np.where(((yy - 120) ** 2 + (xx - 160) ** 2 < 70 ** 2)[..., None], 230, 20).astype(np.uint8).repeat(3, axis=2)
    m = du_doan(khung)
    assert m.shape == (xoa_nen.CANH, xoa_nen.CANH) and 0.0 <= float(m.min()) and float(m.max()) <= 1.0
    assert float(m[140:180, 140:180].mean()) > float(m[:30, :30].mean()) + 0.3
