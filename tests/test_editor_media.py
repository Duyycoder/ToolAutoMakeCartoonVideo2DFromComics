"""Media của editor: đọc thông số từ `ffmpeg -i`, nhập (chép, giữ tên gốc), dọn dở dang, ảnh xem trước."""
import os
import subprocess

import pytest

from orchestrator.editor import luu_tru, media

IPHONE_MOV = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'IMG_0896.MOV':
  Duration: 00:00:05.20, start: 0.000000, bitrate: 11532 kb/s
  Stream #0:0[0x1](und): Video: hevc (Main) (hvc1 / 0x31637668), yuv420p(tv, bt709), 1920x1080, 11342 kb/s, 29.98 fps, 30 tbr, 600 tbn (default)
      Side data:
        displaymatrix: rotation of -90.00 degrees
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, mono, fltp, 94 kb/s (default)
"""

MP3_CO_BIA = """Input #0, mp3, from 'nhac.mp3':
  Duration: 00:03:21.55, start: 0.025057, bitrate: 320 kb/s
  Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, stereo, fltp, 320 kb/s
  Stream #0:1: Video: mjpeg (Baseline), yuvj420p(pc, bt470bg/unknown/unknown), 500x500 [SAR 1:1 DAR 1:1], 90k tbr, 90k tbn (attached pic)
"""

PNG = """Input #0, png_pipe, from 'logo.png':
  Duration: N/A, bitrate: N/A
  Stream #0:0: Video: png, rgba(pc), 512x256, 25 fps, 25 tbr, 25 tbn
"""


def test_phan_tich_video_iphone_quay_doc():
    ts = media.phan_tich(IPHONE_MOV)
    assert ts["thoi_luong"] == 5.2
    assert (ts["rong"], ts["cao"]) == (1080, 1920), "đổi chiều theo rotation"
    assert ts["codec"] == "hevc" and ts["fps"] == 29.98
    assert ts["co_am_thanh"] and ts["codec_am"] == "aac"


def test_phan_tich_mp3_bo_anh_bia():
    ts = media.phan_tich(MP3_CO_BIA)
    assert ts["co_hinh"] is False and ts["co_am_thanh"]
    assert ts["thoi_luong"] == 201.55


def test_phan_tich_anh():
    ts = media.phan_tich(PNG)
    assert ts["co_hinh"] and (ts["rong"], ts["cao"]) == (512, 256)
    assert "thoi_luong" not in ts


def test_loai_theo_duoi():
    assert media.loai_theo_duoi("a.MOV") == "video"
    assert media.loai_theo_duoi("a.mp3") == "audio"
    assert media.loai_theo_duoi("a.webp") == "anh"
    assert media.loai_theo_duoi("a.srt") == "phu_de"
    assert media.loai_theo_duoi("a.exe") == ""


def test_ten_dich_giu_ten_goc_va_khong_de(tmp_path):
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "IMG_0896.mov").write_bytes(b"x")
    assert media.ten_dich(str(tmp_path), "khac.mov", set()) == "khac.mov"
    assert media.ten_dich(str(tmp_path), "IMG_0896.mov", set()) == "IMG_0896 (2).mov"
    assert media.ten_dich(str(tmp_path), "IMG_0896.mov", {"img_0896 (2).mov"}) == "IMG_0896 (3).mov"


def test_kiem_tra_dia_bao_loi_ro_rang(tmp_path, monkeypatch):
    monkeypatch.setattr(media.shutil, "disk_usage", lambda p: type("U", (), {"free": 100 * 1024 * 1024})())
    with pytest.raises(ValueError, match="chỉ còn"):
        media.kiem_tra_dia(str(tmp_path), 10 * 1024 * 1024)


def test_lenh_dai_hinh_moi_khung_mot_lan_tua():
    cmd = media.lenh_dai_hinh("ffmpeg", "a.mp4", "o.jpg", 60.0)
    assert cmd.count("-ss") == media.SO_KHUNG_DAI
    assert "hstack=inputs=12" in cmd[cmd.index("-filter_complex") + 1]
    ngan = media.lenh_dai_hinh("ffmpeg", "a.mp4", "o.jpg", 0.5)
    assert ngan.count("-ss") == 1 and "hstack" not in ngan[ngan.index("-filter_complex") + 1]


# ----------------------------------------------------------------- nhập (giả ffmpeg)
@pytest.fixture
def du_an(tmp_path):
    folder = str(tmp_path / "da")
    luu_tru.tao_thu_muc_con(folder)
    luu_tru.ghi_duan(folder, {"schema": 2, "id": "abc", "name": "x", "media": [], "tac_vu": []})
    return folder


@pytest.fixture
def gia_ffmpeg(monkeypatch):
    monkeypatch.setattr(media, "do_thong_so", lambda p: {"thoi_luong": 5.2, "rong": 1080, "cao": 1920,
                                                          "fps": 30, "co_hinh": True, "co_am_thanh": True,
                                                          "codec": "hevc"})

    def thumb(src, dst, t):
        open(dst, "wb").write(b"jpg")
        return True
    monkeypatch.setattr(media, "tao_thumb", thumb)
    monkeypatch.setattr(media, "tao_dai_hinh", lambda s, d, dai: 0)
    monkeypatch.setattr(media, "tao_song_am", lambda s, d: False)


def _cho(qlm):
    for h in qlm.cac_hang():
        assert h.cho_rong(10)


def test_nhap_chep_vao_media_giu_ten_goc(du_an, tmp_path, gia_ffmpeg):
    src = tmp_path / "IMG_0896.mov"
    src.write_bytes(os.urandom(3000))
    qlm = media.QuanLyMedia()
    moi = qlm.nhap(du_an, "abc", [str(src), str(src)])
    assert [m["file"] for m in moi] == ["media/IMG_0896.mov", "media/IMG_0896.mov"]
    _cho(qlm)

    ds = luu_tru.doc_duan(du_an)["media"]
    assert len(ds) == 1
    assert all(m["trang_thai"] == "san_sang" for m in ds)
    assert ds[0]["thoi_luong"] == 5.2 and ds[0]["thumb"] is True
    assert open(os.path.join(du_an, "media", "IMG_0896.mov"), "rb").read() == src.read_bytes()
    assert src.exists(), "không bao giờ động vào file gốc"
    assert luu_tru.doc_duan(du_an)["anh_bia"].endswith("m_01.jpg")


def test_lay_thong_so_theo_video_dau_tien(du_an, tmp_path, gia_ffmpeg):
    def bat_co(d):
        d["thong_so"] = {"rong": 1920, "cao": 1080, "fps": 30, "ti_le": "16:9", "theo_video_dau": True}
    luu_tru.sua_duan(du_an, bat_co)
    src = tmp_path / "doc.mov"
    src.write_bytes(b"x")
    qlm = media.QuanLyMedia()
    qlm.nhap(du_an, "abc", [str(src)])
    _cho(qlm)
    ts = luu_tru.doc_duan(du_an)["thong_so"]
    assert (ts["rong"], ts["cao"], ts["fps"], ts["ti_le"]) == (1080, 1920, 30, "9:16")
    assert ts["theo_video_dau"] is False, "chỉ lấy theo video ĐẦU TIÊN"


def test_file_da_nam_trong_du_an_thi_khong_chep(du_an, gia_ffmpeg):
    trong = os.path.join(du_an, "media", "san.mp4")
    open(trong, "wb").write(b"x" * 10)
    qlm = media.QuanLyMedia()
    moi = qlm.nhap(du_an, "abc", [trong])
    _cho(qlm)
    assert moi[0]["file"] == "media/san.mp4"
    assert os.listdir(os.path.join(du_an, "media")) == ["san.mp4"]


def test_nhap_tu_choi_file_la_va_file_mat(du_an, tmp_path):
    qlm = media.QuanLyMedia()
    (tmp_path / "a.exe").write_bytes(b"x")
    with pytest.raises(ValueError, match="Không nhận"):
        qlm.nhap(du_an, "abc", [str(tmp_path / "a.exe")])
    with pytest.raises(ValueError, match="Không tìm thấy"):
        qlm.nhap(du_an, "abc", [str(tmp_path / "khong_co.mp4")])


def test_mo_lai_sau_khi_tat_ngang_luc_dang_chep(du_an, tmp_path, gia_ffmpeg):
    def dang_chep(d):
        d["media"].append({"id": "m_01", "loai": "video", "file": "media/to.mp4",
                           "nguon": str(tmp_path / "to.mp4"), "trang_thai": "dang_chep"})
    luu_tru.sua_duan(du_an, dang_chep)
    tam = os.path.join(du_an, "media", media.TIEN_TO_TAM + "to.mp4")
    open(tam, "wb").write(b"cut")

    qlm = media.QuanLyMedia()
    assert qlm.don_khi_mo(du_an) == 1
    m = luu_tru.doc_duan(du_an)["media"][0]
    assert m["trang_thai"] == "bi_ngat" and "Nhập lại" in m["loi"]
    assert not os.path.exists(tam)

    (tmp_path / "to.mp4").write_bytes(b"du" * 100)
    qlm.nhap_lai(du_an, "abc", "m_01")
    _cho(qlm)
    assert luu_tru.doc_duan(du_an)["media"][0]["trang_thai"] == "san_sang"


ADAPTER_GIA = r'''
import json, os, sys
out = sys.argv[1]
d = os.path.join(out, "clip_abc"); os.makedirs(d, exist_ok=True)
p = os.path.join(d, "clip.mp4"); open(p, "wb").write(b"video")
open(os.path.join(d, "video.json"), "w").write("{}")
for ev in ({"event": "item_start", "index": 1, "total": 2, "title": "Clip: hay?"},
           {"event": "download_progress", "percent": 50},
           {"event": "item_done", "path": p, "title": "Clip: hay?", "url": "https://x/1"},
           {"event": "item_failed", "error": "403"}):
    print(json.dumps(ev), flush=True)
'''


def test_tai_url_chuyen_vao_media_ten_an_toan(du_an, tmp_path, gia_ffmpeg):
    import sys
    script = tmp_path / "gia.py"
    script.write_text(ADAPTER_GIA, encoding="utf-8")
    qlm = media.QuanLyMedia()
    v = qlm.tai_url(du_an, "abc", ["https://x/1", "https://x/2"],
                    lambda tam: [sys.executable, str(script), tam], str(tmp_path))
    _cho(qlm)
    assert v.trang_thai == "xong" and v.ket_qua["so_tai"] == 1 and v.ket_qua["loi"] == ["403"]
    m = luu_tru.doc_duan(du_an)["media"][0]
    assert m["file"] == "media/Clip_ hay_.mp4" and m["url"] == "https://x/1" and m["trang_thai"] == "san_sang"
    assert os.listdir(os.path.join(du_an, ".duan", "cache", "tai_ve")) == [], "dọn thư mục tải tạm"


def test_xoa_media_dang_dung_bi_chan(du_an):
    qlm = media.QuanLyMedia()
    with pytest.raises(ValueError, match="timeline"):
        qlm.xoa(du_an, "m_01", dang_dung=True)


# -------------------------------------------------------- ffmpeg thật (tích hợp)
@pytest.fixture(scope="module")
def video_mau(tmp_path_factory):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg (imageio_ffmpeg)")
    out = str(tmp_path_factory.mktemp("mau") / "mau thử.mkv")
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y",
                          "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=3",
                          "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                          "-c:v", "libx264", "-c:a", "aac", "-shortest", out],
                         capture_output=True, timeout=120)
    if res.returncode != 0:
        pytest.skip(f"ffmpeg không tạo được video mẫu: {res.stderr[-300:]}")
    return out


def test_ffmpeg_that_thong_so_anh_proxy(video_mau, tmp_path):
    ts = media.do_thong_so(video_mau)
    assert (ts["rong"], ts["cao"]) == (640, 360) and ts["fps"] == 25
    assert 2.9 <= ts["thoi_luong"] <= 3.1 and ts["co_am_thanh"]

    assert media.tao_thumb(video_mau, str(tmp_path / "t.jpg"), 1.0)
    assert media.tao_dai_hinh(video_mau, str(tmp_path / "d.jpg"), ts["thoi_luong"]) == 3
    assert media.tao_song_am(video_mau, str(tmp_path / "s.png"))
    assert media.tao_proxy(video_mau, str(tmp_path / "p.mp4"), ts["thoi_luong"])
    p = media.do_thong_so(str(tmp_path / "p.mp4"))
    assert p["codec"] == "h264" and p["cao"] == 360, "không phóng to video nhỏ hơn 720p"


ADAPTER_LOI = r'''
import json
print(json.dumps({"event": "item_failed", "error": "[WinError 2] The system cannot find the file specified: 'C:/x'"}), flush=True)
'''


def test_tai_url_loi_het_thi_viec_loi_kem_giai_thich(du_an, tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(os, "name", "nt")
    script = tmp_path / "loi.py"
    script.write_text(ADAPTER_LOI, encoding="utf-8")
    qlm = media.QuanLyMedia()
    v = qlm.tai_url(du_an, "abc", ["https://x/1"], lambda tam: [sys.executable, str(script)], str(tmp_path))
    _cho(qlm)
    assert v.trang_thai == "loi"
    assert "Controlled folder access" in v.loi and "WinError 2" in v.loi

def test_hai_file_cung_ten_khac_kich_thuoc(du_an, tmp_path, gia_ffmpeg):
    src1 = tmp_path / "IMG_0896.mov"
    src1.write_bytes(b"x" * 1000)
    
    thu2 = tmp_path / "thu2"
    thu2.mkdir()
    src2 = thu2 / "IMG_0896.mov"
    src2.write_bytes(b"x" * 2000)
    
    qlm = media.QuanLyMedia()
    moi = qlm.nhap(du_an, "abc", [str(src1), str(src2)])
    _cho(qlm)
    
    ds_file = [m["file"] for m in moi]
    assert ds_file == ["media/IMG_0896.mov", "media/IMG_0896 (2).mov"]
    assert luu_tru.doc_duan(du_an)["media"][0]["file"] == "media/IMG_0896.mov"
    assert luu_tru.doc_duan(du_an)["media"][1]["file"] == "media/IMG_0896 (2).mov"


def test_dai_hinh_video_xoay_that_ra_khung_doc(tmp_path):
    """Video 320×180 mang displaymatrix xoay 90° (điện thoại quay dọc) → hiển thị 180×320; dải khung phải DỌC (≈30×54),
    không xoay hai lần thành ngang (96×54) — ffmpeg tự xoay khi giải mã."""
    import re
    import subprocess
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("Không có ffmpeg")
    goc, xoay = tmp_path / "goc.mp4", tmp_path / "xoay.mp4"
    subprocess.run([exe, "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(goc)],
                   capture_output=True, check=True)
    subprocess.run([exe, "-y", "-display_rotation", "90", "-i", str(goc), "-c", "copy", str(xoay)], capture_output=True, check=True)
    ts = media.do_thong_so(str(xoay))
    assert (ts["rong"], ts["cao"]) == (180, 320)
    dai = tmp_path / "dai.jpg"
    subprocess.run(media.lenh_dai_hinh(exe, str(xoay), str(dai), 1.0, so=1, xoay=ts.get("xoay", 0)), capture_output=True, check=True)
    thong_tin = subprocess.run([exe, "-i", str(dai)], capture_output=True, text=True).stderr.split("Stream")[1]
    rong, cao = map(int, re.search(r"(\d+)x(\d+)", thong_tin).groups())
    assert cao == 54 and rong < cao, f"dải khung phải dọc, nhận {rong}x{cao}"
