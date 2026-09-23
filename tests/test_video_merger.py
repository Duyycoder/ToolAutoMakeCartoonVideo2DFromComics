"""Noi video: duong nhanh (copy) va duong chuan hoa (khac do phan giai).

Khong goi ffmpeg that - moi lenh deu bi chan lai de doc.
"""
import os

import pytest

from orchestrator import video_merger as vm
from orchestrator.video_merger import _select_files, _sizes_match, _target_size


def test_select_files_no_only_files():
    mp4_files = ["/a/b/c/1.mp4", "/a/b/c/TongHop_1.mp4", "/a/b/c/2.mp4"]
    result = _select_files(mp4_files, None)
    assert result == ["/a/b/c/1.mp4", "/a/b/c/2.mp4"]


def test_select_files_with_only_files():
    mp4_files = ["/a/b/c/1.mp4", "/a/b/c/2.mp4", "/a/b/c/3.mp4"]
    result = _select_files(mp4_files, ["1.mp4", "3.mp4"])
    assert result == ["/a/b/c/1.mp4", "/a/b/c/3.mp4"]


def test_select_files_path_traversal():
    mp4_files = ["/a/b/c/1.mp4", "/a/b/c/2.mp4"]
    result = _select_files(mp4_files, ["../secret.mp4", "1.mp4", "/etc/passwd.mp4"])
    # only "1.mp4" is a pure basename. The others contain path separators and will be rejected.
    assert result == ["/a/b/c/1.mp4"]


def test_select_files_filter_tonghop_with_only_files():
    mp4_files = ["/a/b/c/TongHop_1.mp4", "/a/b/c/1.mp4"]
    # Even if explicitly requested, TongHop_ should be filtered out
    result = _select_files(mp4_files, ["TongHop_1.mp4", "1.mp4"])
    assert result == ["/a/b/c/1.mp4"]


# ------------------------------------------------------------- Chon co dich
def test_co_dich_la_khung_lon_nhat_va_luon_chan():
    assert _target_size([(1080, 1920), (1920, 1080)]) == (1080, 1920)
    assert _target_size([(640, 360), (1280, 720)]) == (1280, 720)
    # yuv420p khong nhan chieu le -> phai ep chan, neu khong ffmpeg bo cuoc.
    assert _target_size([(1081, 607)]) == (1080, 606)
    assert _target_size([]) is None
    assert _target_size([(0, 0)]) is None


def test_chi_noi_thang_khi_biet_ro_MOI_co_va_chung_giong_nhau():
    assert _sizes_match([(1920, 1080), (1920, 1080)], 2) is True
    assert _sizes_match([(1920, 1080), (1080, 1920)], 2) is False
    assert _sizes_match([(1920, 1080), (0, 0)], 2) is False      # mot video khong ro co
    assert _sizes_match([(1920, 1080)], 2) is False              # thieu so lieu
    assert _sizes_match(None, 2) is False


# ---------------------------------------------------------------- merge_files
@pytest.fixture
def ffmpeg(monkeypatch):
    """Chan moi lenh ffmpeg lai, tra ve ket qua dat truoc."""
    calls = []
    plan = {"fail_concat": False, "has_audio": True}

    class Res:
        def __init__(self, code, stderr=""):
            self.returncode, self.stdout, self.stderr = code, "", stderr

    def fake_run(cmd):
        calls.append(cmd)
        if "-hide_banner" in cmd:      # probe_media
            audio = "\n  Stream #0:1: Audio: aac, 48000 Hz" if plan["has_audio"] else ""
            return Res(1, "  Stream #0:0: Video: h264, yuv420p, 1920x1080, 30 fps" + audio)
        if "concat" in cmd and plan["fail_concat"]:
            return Res(1, "Invalid data")
        return Res(0)

    monkeypatch.setattr(vm, "_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(vm, "_run", fake_run)
    return {"calls": calls, "plan": plan}


def make_videos(tmp_path, count=2):
    out = []
    for i in range(1, count + 1):
        path = tmp_path / f"tap{i}.mp4"
        path.write_bytes(b"0" * 32)
        out.append(str(path))
    return out


def test_cung_co_thi_noi_thang_khong_ma_hoa_lai(tmp_path, ffmpeg):
    files = make_videos(tmp_path)
    ok = vm.merge_files(files, str(tmp_path / "out.mp4"),
                        sizes=[(1920, 1080), (1920, 1080)])
    assert ok is True
    assert len(ffmpeg["calls"]) == 1
    assert "-c" in ffmpeg["calls"][0] and "copy" in ffmpeg["calls"][0]
    assert not any("libx264" in c for c in ffmpeg["calls"][0])


def test_khac_co_thi_chuan_hoa_ve_khung_lon_nhat(tmp_path, ffmpeg):
    files = make_videos(tmp_path)
    ok = vm.merge_files(files, str(tmp_path / "out.mp4"),
                        sizes=[(1080, 1920), (1920, 1080)], work_dir=str(tmp_path))
    assert ok is True

    encodes = [c for c in ffmpeg["calls"] if "libx264" in c]
    assert len(encodes) == 2                      # moi video mot lan chuan hoa
    filters = encodes[0][encodes[0].index("-vf") + 1]
    assert "scale=1080:1920" in filters           # khung doc lon hon ve dien tich
    assert "pad=1080:1920" in filters             # them vien den thay vi keo meo
    assert "setsar=1" in filters
    # Nối lại bằng copy sau khi đã chuẩn hoá.
    assert any("concat" in c and "copy" in c for c in ffmpeg["calls"])


def test_video_cam_duoc_chen_luong_tieng_im_lang(tmp_path, ffmpeg):
    ffmpeg["plan"]["has_audio"] = False
    files = make_videos(tmp_path)
    vm.merge_files(files, str(tmp_path / "out.mp4"),
                   sizes=[(1080, 1920), (1920, 1080)], work_dir=str(tmp_path))

    encodes = [c for c in ffmpeg["calls"] if "libx264" in c]
    # Thieu luong tieng thi concat demuxer hong vi so luong lech nhau.
    assert all(any("anullsrc" in str(arg) for arg in cmd) for cmd in encodes)


def test_khong_ro_co_thi_thu_noi_thang_truoc_roi_moi_chuan_hoa(tmp_path, ffmpeg):
    ffmpeg["plan"]["fail_concat"] = True
    files = make_videos(tmp_path)
    vm.merge_files(files, str(tmp_path / "out.mp4"), sizes=None, work_dir=str(tmp_path))

    assert "copy" in ffmpeg["calls"][0]                        # thu duong nhanh truoc
    assert any("libx264" in c for c in ffmpeg["calls"])        # roi moi chuan hoa


def test_tat_chuan_hoa_thi_hong_la_dung_han(tmp_path, ffmpeg):
    ffmpeg["plan"]["fail_concat"] = True
    files = make_videos(tmp_path)
    ok = vm.merge_files(files, str(tmp_path / "out.mp4"),
                        sizes=[(1080, 1920), (1920, 1080)], normalize="never")
    assert ok is False
    assert not any("libx264" in c for c in ffmpeg["calls"])


def test_don_thu_muc_tam_sau_khi_ghep(tmp_path, ffmpeg):
    files = make_videos(tmp_path)
    work = tmp_path / "tasks"
    work.mkdir()
    vm.merge_files(files, str(tmp_path / "out.mp4"),
                   sizes=[(1080, 1920), (1920, 1080)], work_dir=str(work))
    assert os.listdir(str(work)) == []


def test_khong_co_file_nao_thi_bao_that_bai(tmp_path, ffmpeg):
    assert vm.merge_files([], str(tmp_path / "out.mp4")) is False
    assert vm.merge_files(["Z:/khong/co.mp4"], str(tmp_path / "out.mp4")) is False
