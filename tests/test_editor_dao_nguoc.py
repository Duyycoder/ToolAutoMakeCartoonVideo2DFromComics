"""Tua ngược video (dao_nguoc.py): chia khúc phủ kín đoạn, file ra đúng thời lượng và khung đầu = khung cuối của gốc."""
import subprocess

import pytest

from orchestrator.editor import dao_nguoc, media


def test_cac_khuc_phu_kin_doan():
    k = dao_nguoc.cac_khuc(1.0, 6.5, 2.0)
    assert k == [[1.0, 2.0], [3.0, 2.0], [5.0, 1.5]]
    assert dao_nguoc.cac_khuc(0, 0.0005) == []


def test_doan_khong_hop_le_bi_tu_choi(tmp_path):
    with pytest.raises(ValueError):
        dao_nguoc.tao("ffmpeg", "a.mp4", str(tmp_path / "b.mp4"), 3, 3, False)
    with pytest.raises(ValueError):
        dao_nguoc.tao("ffmpeg", "a.mp4", str(tmp_path / "b.mp4"), 0, dao_nguoc.DAI_TOI_DA + 1, False)


def test_tua_nguoc_that(tmp_path):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    goc, ra = tmp_path / "a.mp4", tmp_path / "b.mp4"
    # Khung sáng dần theo thời gian: đầu video đen, cuối video trắng → bản tua ngược phải mở đầu bằng khung sáng.
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                          "color=c=black:s=160x90:r=25:d=5,geq=lum='255*T/5':cb=128:cr=128", "-f", "lavfi", "-i",
                          "sine=f=440:d=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(goc)],
                         capture_output=True, timeout=120)
    if res.returncode:
        pytest.skip("không tạo được video mẫu")
    dao_nguoc.tao(exe, str(goc), str(ra), 0.5, 5.0, True)
    ts = media.do_thong_so(str(ra))
    assert abs(float(ts["thoi_luong"]) - 4.5) < 0.15
    assert ts.get("co_am_thanh") is not False

    def sang(path, t):
        r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                            "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, timeout=60)
        return r.stdout[0]
    assert sang(ra, 0) > 200 and sang(ra, 4.3) < 60
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("dao_")]      # thư mục tạm đã dọn
