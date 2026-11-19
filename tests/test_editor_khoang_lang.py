"""Tìm khoảng lặng (khoang_lang.py): đọc log silencedetect + đo thật trên tiếng có đoạn im."""
import subprocess

import pytest

from orchestrator.editor import khoang_lang, media


def test_phan_tich_log_va_khoang_lang_keo_toi_het():
    log = ("[silencedetect @ 0x1] silence_start: 1.5\n[silencedetect @ 0x1] silence_end: 2.75 | silence_duration: 1.25\n"
           "size=N/A\n[silencedetect @ 0x1] silence_start: 4.2\n")
    assert khoang_lang.phan_tich(log, 10, 15) == [[11.5, 12.75], [14.2, 15]]
    assert khoang_lang.phan_tich("khong co gi", 0, 5) == []


def test_do_that(tmp_path):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    f = tmp_path / "a.wav"
    # 1 s tiếng · 1,5 s im · 1 s tiếng
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                          "sine=f=440:d=3.5,volume='if(between(t,1,2.5),0,1)':eval=frame", str(f)], capture_output=True, timeout=60)
    if res.returncode:
        pytest.skip("không tạo được tiếng mẫu")
    kq = khoang_lang.do(exe, str(f), 0, 3.5, -35, 0.5)
    assert len(kq) == 1 and abs(kq[0][0] - 1.0) < 0.08 and abs(kq[0][1] - 2.5) < 0.08, kq
    assert khoang_lang.do(exe, str(f), 0.5, 3.5, -35, 0.5)[0][0] == pytest.approx(1.0, abs=0.08)   # giờ tính theo media, không theo đoạn
    with pytest.raises(ValueError):
        khoang_lang.do(exe, str(f), 2, 2)
