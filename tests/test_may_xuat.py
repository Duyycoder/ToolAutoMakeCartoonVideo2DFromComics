"""Máy xuất từ xa: máy chính gửi lệnh render + file sang worker (laptop GPU) qua HTTP, nhận .mp4 về."""
import os
import socket
import subprocess
import threading
import time

import pytest

from orchestrator import may_xuat
from orchestrator.editor import media, render, xuat_tu_xa

FF = media.ffmpeg_exe()


def test_lenh_ngoai_cache_bi_chan():
    from fastapi import HTTPException
    ok = ["-i", "@tep:" + "a" * 40 + ".mp4", "-c:v", "libx264", "@ra"]
    may_xuat.kiem_lenh(ok)
    for xau in (["-i", "C:/Windows/x.mp4", "@ra"], ["-i", "@tep:" + "a" * 40 + ".mp4", "/tmp/x.mp4"],
                ["-i", "@tep:" + "a" * 40 + ".mp4", "-vf", "movie=../../x", "@ra"],
                ["-i", "@tep:" + "a" * 40 + ".mp4", "-y", "/etc/x", "@ra"]):
        with pytest.raises(HTTPException):
            may_xuat.kiem_lenh(xau)


def test_khoa_tep_theo_noi_dung(tmp_path):
    a, b = tmp_path / "a.MOV", tmp_path / "b.mov"
    a.write_bytes(b"x" * 3_000_000)
    b.write_bytes(b"x" * 3_000_000)
    assert xuat_tu_xa.khoa_tep(str(a)) == xuat_tu_xa.khoa_tep(str(b)) and xuat_tu_xa.khoa_tep(str(a)).endswith(".mov")
    b.write_bytes(b"x" * 2_999_999 + b"y")
    assert xuat_tu_xa.khoa_tep(str(a)) != xuat_tu_xa.khoa_tep(str(b))


@pytest.fixture
def worker(tmp_path):
    import uvicorn
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        cong = s.getsockname()[1]
    sv = uvicorn.Server(uvicorn.Config(may_xuat.tao_app(str(tmp_path / "worker"), "ma-thu"), host="127.0.0.1",
                                       port=cong, log_level="error"))
    t = threading.Thread(target=sv.run, daemon=True)
    t.start()
    for _ in range(100):
        if sv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{cong}", tmp_path / "worker"
    sv.should_exit = True
    t.join(5)


def test_sai_ma_bi_tu_choi(worker):
    url, _ = worker
    with pytest.raises(xuat_tu_xa.LoiMayXuat, match="sai mã"):
        xuat_tu_xa.MayXuat(url, "sai").ping()
    with pytest.raises(xuat_tu_xa.LoiMayXuat):
        xuat_tu_xa.MayXuat("http://127.0.0.1:1", "x").ping()


@pytest.mark.skipif(not FF, reason="cần ffmpeg")
def test_xuat_tu_xa_that_va_cache_file(worker, tmp_path):
    url, thu_muc_worker = worker
    goc = tmp_path / "duan"
    (goc / "media").mkdir(parents=True)
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(goc / "media" / "a.mp4")], check=True)
    da = {"thong_so": {"rong": 320, "cao": 180, "fps": 30},
          "media": [{"id": "m", "loai": "video", "file": "media/a.mp4", "co_am_thanh": True, "rong": 320, "cao": 180}]}
    tl = {"tracks": [{"id": "V1", "loai": "video"}, {"id": "O1", "loai": "lop_phu"}], "clips": [
        {"id": "c", "track": "V1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 1, "toc_do": 1, "mau": {"preset": "am_ap"}},
        {"id": "t", "track": "O1", "loai": "chu", "bat_dau": 0, "ket_thuc": 1, "noi_dung": "Xin chào"}]}
    may = xuat_tu_xa.MayXuat(url, "ma-thu")
    assert may.ping()["ok"]
    tien_do = []
    for lan in range(2):
        ra = str(goc / f"ra{lan}.mp4")
        kq = render.dung_lenh_xuat(str(goc), da, tl, {"preset": "ultrafast", "bo_ma_hoa": "x264"}, ra, FF)
        may.xuat(kq, ra, lambda p, t: tien_do.append((round(p), t)), lambda: False)
        assert os.path.getsize(ra) > 0
        info = subprocess.run([FF, "-hide_banner", "-i", ra], capture_output=True, text=True).stderr
        assert "Video: h264" in info and "320x180" in info
    gui = [t for _, t in tien_do if t.startswith("Gửi file")]
    assert gui, "lần đầu phải gửi file"
    assert len(os.listdir(thu_muc_worker / "tep")) == 1, "file media chỉ giữ một bản trong cache"
    assert not os.listdir(thu_muc_worker / "viec"), "việc xong phải dọn thư mục tạm"
