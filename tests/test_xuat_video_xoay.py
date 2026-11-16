"""Video quay dọc trên điện thoại (luồng ngang + thẻ "Display Matrix: rotation -90"): ffmpeg tự xoay khung khi giải mã,
nhưng ffmpeg mới (7.1+/9) còn CHÉP thẻ xoay sang file xuất → trình phát xoay thêm lần nữa, video bị nằm ngang.
Bản xuất phải đúng khung dự án và KHÔNG mang thẻ xoay."""
import subprocess

import pytest

from orchestrator.editor import media, render

FF = media.ffmpeg_exe()
pytestmark = pytest.mark.skipif(not FF, reason="cần ffmpeg")


@pytest.fixture(scope="module")
def video_doc(tmp_path_factory):
    """Giống video iPhone dọc: luồng 320×180 (ngang) + thẻ xoay -90 → hiển thị 180×320."""
    g = tmp_path_factory.mktemp("xoay")
    (g / "media").mkdir()
    goc = g / "goc.mp4"
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(goc)], check=True)
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-display_rotation", "-90", "-i", str(goc),
                    "-c", "copy", str(g / "media" / "doc.mov")], check=True)
    info = subprocess.run([FF, "-hide_banner", "-i", str(g / "media" / "doc.mov")], capture_output=True, text=True).stderr
    assert "rotation of" in info, "file mẫu phải mang thẻ xoay như video iPhone"
    return g


def test_ban_xuat_dung_khung_doc_va_khong_mang_the_xoay(video_doc):
    g = video_doc
    da = {"thong_so": {"rong": 180, "cao": 320, "fps": 30},
          "media": [{"id": "m", "loai": "video", "file": "media/doc.mov", "co_am_thanh": True, "rong": 180, "cao": 320}]}
    tl = {"tracks": [{"id": "V1", "loai": "video"}],
          "clips": [{"id": "c", "track": "V1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 1, "toc_do": 1}]}
    ra = str(g / "ra.mp4")
    kq = render.dung_lenh_xuat(str(g), da, tl, {"preset": "ultrafast", "bo_ma_hoa": "x264"}, ra, FF)
    (g / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    r = subprocess.run(kq["cmd"], cwd=str(g), capture_output=True, text=True, errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr[-1000:]
    info = subprocess.run([FF, "-hide_banner", "-i", ra], capture_output=True, text=True).stderr
    assert "180x320" in info, f"Khung xuất phải dọc 180×320: {info}"
    assert "rotation of" not in info and "Display Matrix" not in info, \
        f"Bản xuất không được mang thẻ xoay (trình phát sẽ xoay thêm → nằm ngang): {info}"


def test_nvenc_khong_giai_ma_gpu_video_co_the_xoay(tmp_path):
    """Giải mã CUDA không tự xoay theo thẻ → chỉ dùng -hwaccel cuda khi CHẮC media không xoay (xoay == 0)."""
    def lenh(xoay):
        m = {"id": "m", "loai": "video", "file": "media/a.mov", "co_am_thanh": False, "rong": 180, "cao": 320}
        if xoay is not None:
            m["xoay"] = xoay
        da = {"thong_so": {"rong": 180, "cao": 320, "fps": 30}, "media": [m]}
        tl = {"tracks": [{"id": "V1", "loai": "video"}],
              "clips": [{"id": "c", "track": "V1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 1, "toc_do": 1}]}
        return render.dung_lenh_xuat(str(tmp_path), da, tl, {"bo_ma_hoa": "nvenc"}, "ra.mp4", "ffmpeg")
    assert "-hwaccel" in lenh(0)["cmd"]
    assert "-hwaccel" not in lenh(-90)["cmd"], "video quay dọc điện thoại: giải mã CPU để ffmpeg tự xoay"
    assert "-hwaccel" not in lenh(None)["cmd"], "media cũ chưa đo xoay: không đoán, giải mã CPU"
    assert "sidedata=mode=delete:type=DISPLAYMATRIX" in lenh(0)["loc"]
