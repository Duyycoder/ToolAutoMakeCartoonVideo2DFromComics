"""Tìm nhịp nhạc (nhip.py): chuỗi tiếng gõ đều 120 BPM phải ra đúng tempo và các nhịp cách đều 0,5 s."""
import subprocess

import pytest

from orchestrator.editor import media, nhip


def test_khong_co_nhip_ro_thi_tra_rong():
    assert nhip.tim_nhip([]) == (0.0, [])
    assert nhip.tim_nhip([0.0] * 500) == (0.0, [])


def test_do_that_120_bpm(tmp_path):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    f = tmp_path / "go.wav"
    # Tiếng gõ ngắn 40 ms cứ mỗi 0,5 s (120 BPM), dài 12 s, cái đầu ở giây 0,2.
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                          "sine=f=880:d=12,volume='if(lt(mod(t+0.3,0.5),0.04),1,0)':eval=frame", str(f)],
                         capture_output=True, timeout=60)
    if res.returncode:
        pytest.skip("không tạo được tiếng mẫu")
    bpm, ds = nhip.do(exe, str(f), 0, 12)
    assert abs(bpm - 120) < 4, bpm
    assert 20 <= len(ds) <= 26
    cach = [b - a for a, b in zip(ds, ds[1:])]
    assert all(abs(c - 0.5) < 0.03 for c in cach), cach[:5]
    assert abs((ds[0] - 0.2) % 0.5) < 0.06 or abs((ds[0] - 0.2) % 0.5 - 0.5) < 0.06, ds[:3]
    _, ds2 = nhip.do(exe, str(f), 4, 12)
    assert ds2 and ds2[0] >= 4                                   # giờ tính theo media, không theo đoạn đo
