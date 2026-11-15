"""File tải lên từ điện thoại/máy quay ở định dạng trình duyệt không dùng được → chuẩn hoá bằng ffmpeg thật."""
import os
import subprocess

import pytest

from orchestrator.editor import chuan_hoa_file, media
from orchestrator.editor.tai_len import LoiTaiLen

FF = media.ffmpeg_exe()
can_ffmpeg = pytest.mark.skipif(not FF, reason="cần ffmpeg")


def _tao(path, *lenh):
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *lenh, str(path)], check=True)
    return str(path)


def test_nhan_duoc_chan_file_khong_phai_media():
    assert chuan_hoa_file.nhan_duoc("IMG_0001.HEIC")
    assert chuan_hoa_file.nhan_duoc("A001_C001.MXF")
    assert chuan_hoa_file.nhan_duoc("khong_duoi")
    assert not chuan_hoa_file.nhan_duoc("virus.exe")


def test_video_may_quay_la_video_va_luon_proxy():
    assert media.loai_theo_duoi("00001.MTS") == "video"
    assert media.loai_theo_duoi("A001.mxf") == "video"
    assert media.can_proxy_ngay({"loai": "video", "file": "media/00001.MTS", "codec": "h264"})


@can_ffmpeg
def test_anh_tiff_doi_sang_jpg(tmp_path):
    src = _tao(tmp_path / "anh.tiff", "-f", "lavfi", "-i", "color=red:s=64x48", "-frames:v", "1")
    out = chuan_hoa_file.chuan_hoa(src)
    assert out.endswith(".jpg") and os.path.getsize(out) > 0
    assert not os.path.exists(src), "file gốc đã thay bằng bản chuẩn hoá"
    assert media.loai_theo_duoi(out) == "anh"


@can_ffmpeg
def test_am_thanh_caf_doi_sang_m4a(tmp_path):
    src = _tao(tmp_path / "ghi_am.caf", "-f", "lavfi", "-i", "sine=f=440:d=1", "-c:a", "pcm_s16le")
    out = chuan_hoa_file.chuan_hoa(src)
    assert out.endswith(".m4a") and media.do_thong_so(out).get("codec_am") == "aac"


@can_ffmpeg
def test_khong_co_duoi_doan_theo_noi_dung(tmp_path):
    vid = _tao(tmp_path / "v.mp4", "-f", "lavfi", "-i", "testsrc=s=64x48:d=1", "-pix_fmt", "yuv420p")
    os.replace(vid, tmp_path / "video_iphone")
    out = chuan_hoa_file.chuan_hoa(str(tmp_path / "video_iphone"))
    assert out.endswith(".mkv") and media.loai_theo_duoi(out) == "video"
    assert media.can_proxy_ngay({"loai": "video", "file": out}), "container lạ → luôn tạo proxy H.264"


def test_rac_khong_doc_duoc_bi_tu_choi(tmp_path):
    rac = tmp_path / "rac.xyz"
    rac.write_bytes(os.urandom(2048))
    with pytest.raises(LoiTaiLen):
        chuan_hoa_file.chuan_hoa(str(rac))
    assert not rac.exists()
