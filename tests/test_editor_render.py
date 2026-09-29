"""Dựng lệnh xuất (render.py): cấu trúc filter cho từng loại clip + một lần xuất thật bằng ffmpeg."""
import os
import subprocess

import pytest

from orchestrator.editor import media, render, srt


def _du_an():
    return {"thong_so": {"rong": 1280, "cao": 720, "fps": 30, "mau_nen": "#000000"}, "media": [
        {"id": "m_v", "loai": "video", "file": "media/a.mp4", "co_am_thanh": True, "rong": 640, "cao": 360},
        {"id": "m_k", "loai": "video", "file": "media/khong_tieng.mp4", "co_am_thanh": False, "rong": 640, "cao": 360},
        {"id": "m_i", "loai": "anh", "file": "media/logo.png"},
        {"id": "m_n", "loai": "audio", "file": "media/nhac.mp3"},
        {"id": "m_g", "loai": "audio", "file": "long_tieng/a.vi.long_tieng.wav"},
    ]}


def _tl(*clips, tracks=None):
    return {"tracks": tracks or [{"id": "V1", "loai": "video"}, {"id": "S1", "loai": "phu_de"},
                                 {"id": "O1", "loai": "lop_phu"}, {"id": "A1", "loai": "audio"},
                                 {"id": "A2", "loai": "audio", "vai": "long_tieng"}],
            "clips": list(clips), "kieu_phu_de": {}}


def _v(cid, mid, bd, vao, ra, toc=1, **kw):
    return {"id": cid, "track": "V1", "media": mid, "bat_dau": bd, "vao": vao, "ra": ra, "toc_do": toc, **kw}


def test_khung_xuat_theo_du_an_hoac_canh_ngan():
    assert render.kich_thuoc_xuat({"rong": 1920, "cao": 1080}, "") == (1920, 1080)
    assert render.kich_thuoc_xuat({"rong": 1080, "cao": 1920}, "720p") == (720, 1280), "dọc: cạnh ngắn là chiều rộng"
    assert render.kich_thuoc_xuat({"rong": 1921, "cao": 1081}, "") == (1920, 1080), "ép số chẵn cho yuv420p"


def test_atempo_xau_chuoi_ngoai_khoang_05_2():
    assert render._atempo(1) == ""
    assert render._atempo(4) == ",atempo=2.0,atempo=2.000000"
    assert render._atempo(0.25) == ",atempo=0.5,atempo=0.500000"


def test_khoang_trong_la_khung_mau_nen_va_concat_dung_thu_tu(tmp_path):
    tl = _tl(_v("c_1", "m_v", 0, 0, 3), _v("c_2", "m_v", 5, 3, 7, toc=2))
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")
    assert kq["thoi_luong"] == 7.0
    loc = kq["loc"]
    assert "color=c=0x000000:s=1280x720" in loc and "d=2" in loc, "khoảng trống 3→5s"
    assert "[a0][ga1][a1]concat=n=3:v=0:a=1[ac]" in loc and "[v0][g1][v1]concat=n=3:v=1:a=0[vc]" in loc
    assert "setpts=PTS/2.000000" in loc and "atempo=2.000000" in loc
    cmd = kq["cmd"]
    assert ("-ss", "3") in zip(cmd, cmd[1:]), "clip 2 tua tới giây 3 của media"
    assert "-filter_complex_script" in cmd and cmd[-1] == "ra.mp4"


def test_video_khong_tieng_va_anh_dung_am_thanh_im_lang(tmp_path):
    tl = _tl(_v("c_1", "m_k", 0, 0, 2), _v("c_2", "m_i", 2, 0, 3))
    loc = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")["loc"]
    assert loc.count("anullsrc") == 2
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")
    assert "-loop" in kq["cmd"], "ảnh tĩnh lặp khung"


def test_che_phu_de_theo_gio_cuc_bo_cua_clip(tmp_path):
    che = {"id": "o", "track": "O1", "loai": "che_phu_de", "tu_media": "m_v", "t_vao": 4, "t_ra": 20,
           "vung": {"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.1}, "kieu": "blur", "do_manh": 20}
    mau = dict(che, id="o2", kieu="mau", mau="#ff0000")
    tl = _tl(_v("c_1", "m_v", 0, 3, 8), che, mau)
    loc = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")["loc"]
    assert "enable='between(t,1,5)'" in loc, "media 4→8 trong clip bắt đầu từ giây 3 = cục bộ 1→5"
    assert "gblur" in loc and "split[" in loc and "overlay=x=main_w*0.1000" in loc
    assert "drawbox=" in loc and "color=0xff0000@1" in loc


def test_che_tren_track_an_thi_bo_qua(tmp_path):
    che = {"id": "o", "track": "O1", "loai": "che_phu_de", "tu_media": "m_v", "t_vao": 0, "t_ra": 5,
           "vung": {"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.1}}
    tl = _tl(_v("c_1", "m_v", 0, 0, 5), che)
    tl["tracks"][2]["an"] = True
    assert "gblur" not in render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")["loc"]


def test_long_tieng_lam_nhac_nen_tu_giam(tmp_path):
    nhac = {"id": "n", "track": "A1", "media": "m_n", "bat_dau": 1, "vao": 0, "ra": 4}
    giong = {"id": "g", "track": "A2", "media": "m_g", "bat_dau": 0, "vao": 0, "ra": 4}
    loc = render.dung_lenh_xuat(str(tmp_path), _du_an(), _tl(_v("c_1", "m_v", 0, 0, 5), nhac, giong), {}, "ra.mp4")["loc"]
    assert "adelay=1000|1000" in loc
    assert "sidechaincompress" in loc and "[giong]asplit=2" in loc


def test_phu_de_sinh_ass_va_nvenc(tmp_path):
    pd = {"id": "s", "track": "S1", "loai": "phu_de", "tu_media": "m_v", "t_vao": 1, "t_ra": 2, "text": "Xin chào"}
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), _tl(_v("c_1", "m_v", 0, 0, 5), pd), {"bo_ma_hoa": "nvenc"}, "ra.mp4")
    assert "subtitles=sub.ass" in kq["loc"]
    assert "Dialogue: 6,0:00:01.00,0:00:02.00" in kq["ass"] and "Xin chào" in kq["ass"]
    assert "h264_nvenc" in kq["cmd"]


def test_timeline_trong_bao_loi(tmp_path):
    with pytest.raises(ValueError, match="trống"):
        render.dung_lenh_xuat(str(tmp_path), _du_an(), _tl(), {}, "ra.mp4")


def test_ten_file_ra_khong_de(tmp_path):
    a = render.ten_file_ra(str(tmp_path), "Phim: tập 1")
    open(a, "w").close()
    assert os.path.basename(a) == "Phim_ tập 1.mp4"
    assert os.path.basename(render.ten_file_ra(str(tmp_path), "Phim: tập 1")) == "Phim_ tập 1 (2).mp4"


def test_srt_ass_doc_ghi():
    cau = srt.phan_tich("1\n00:00:01,000 --> 00:00:02,500\n<i>Xin</i> chào\n\n2\n00:00:03,000 --> 00:00:04,000\nhai\n")
    assert cau == [{"t_vao": 1.0, "t_ra": 2.5, "text": "Xin chào"}, {"t_vao": 3.0, "t_ra": 4.0, "text": "hai"}]
    assert srt.phan_tich(srt.ghi_srt(cau)) == cau
    vtt = srt.phan_tich("WEBVTT\n\n00:01.000 --> 00:02.000\nvtt\n")
    assert vtt == [{"t_vao": 1.0, "t_ra": 2.0, "text": "vtt"}]
    ass = srt.ghi_ass([{"bd": 1, "kt": 2, "text": "a\nb"}], {"k_mac_dinh": {"co": 54}}, 1280, 720)
    assert srt.phan_tich(ass) == [{"t_vao": 1.0, "t_ra": 2.0, "text": "a\nb"}]


# ------------------------------------------------------------ ffmpeg thật
@pytest.fixture(scope="module")
def du_an_that(tmp_path_factory):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    goc = tmp_path_factory.mktemp("xuat")
    (goc / "media").mkdir()
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                          "testsrc2=size=640x360:rate=25:duration=4", "-f", "lavfi", "-i", "sine=f=440:d=4",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                          str(goc / "media" / "a.mp4")], capture_output=True, timeout=120)
    if res.returncode:
        pytest.skip("không tạo được video mẫu")
    return goc, exe


def test_xuat_that_ra_dung_thoi_luong_va_khung(du_an_that):
    goc, exe = du_an_that
    da = {"thong_so": {"rong": 854, "cao": 480, "fps": 25}, "media": [
        {"id": "m_v", "loai": "video", "file": "media/a.mp4", "co_am_thanh": True, "rong": 640, "cao": 360}]}
    tl = _tl(_v("c_1", "m_v", 0, 0, 2), _v("c_2", "m_v", 3, 2, 4, toc=2),
             {"id": "s", "track": "S1", "loai": "phu_de", "tu_media": "m_v", "t_vao": 0.5, "t_ra": 1.5, "text": "Chào"},
             {"id": "o", "track": "O1", "loai": "che_phu_de", "tu_media": "m_v", "t_vao": 0, "t_ra": 4,
              "vung": {"x": 0.1, "y": 0.7, "w": 0.5, "h": 0.2}, "kieu": "mosaic", "do_manh": 16})
    lam = goc / "lam"
    lam.mkdir(exist_ok=True)
    ra = str(goc / "ra.mp4")
    kq = render.dung_lenh_xuat(str(goc), da, tl, {"preset": "ultrafast"}, ra, exe)
    (lam / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    (lam / "sub.ass").write_text(kq["ass"], encoding="utf-8")
    res = subprocess.run(kq["cmd"], cwd=str(lam), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert res.returncode == 0, res.stderr[-1500:]
    ts = media.do_thong_so(ra)
    assert (ts["rong"], ts["cao"]) == (854, 480) and ts["co_am_thanh"]
    assert abs(ts["thoi_luong"] - 4.0) < 0.15, "2s + khoảng trống 1s + 2s ở tốc 2× = 4s"

def test_lop_phu_bien_doi_va_am_thanh_fade(tmp_path):
    tl = _tl(_v("c_1", "m_v", 0, 0, 5), tracks=[
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
        {"id": "O1", "loai": "lop_phu"}, 
        {"id": "A1", "loai": "audio"},
        {"id": "A2", "loai": "audio", "vai": "long_tieng"}
    ])
    c2 = _v("c_2", "m_v", 1, 0, 3)
    c2["track"] = "V2"
    c2["bien_doi"] = {"x": 0.2, "y": 0.3, "ti_le": 0.5, "xoay": 15}
    c2["cat_khung"] = {"trai": 0.1, "phai": 0.1, "tren": 0, "duoi": 0.2}
    c2["hien_thi"] = {"do_mo": 0.8, "bo_goc": 20}
    c2["am_vao"] = 1.0
    c2["am_ra"] = 0.5
    tl["clips"].append(c2)
    
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")
    loc = kq["loc"]
    assert "crop=iw*0.8000:ih*0.8000:iw*0.1000:ih*0.0000" in loc
    assert "geq=lum='p(X,Y)'" in loc
    assert "colorchannelmixer=aa=0.800" in loc
    assert "rotate=0.261799" in loc
    assert "afade=t=in:st=0:d=1" in loc
    assert "afade=t=out:st=2.5:d=0.5" in loc
    assert "adelay=1000|1000" in loc

def test_vung_xuat_cat_bot(tmp_path):
    tl = _tl(_v("c_1", "m_v", 0, 0, 10))
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {"vung_vao": 2.5, "vung_ra": 7.5}, "ra.mp4")
    assert kq["thoi_luong"] == 5.0
    cmd = kq["cmd"]
    i_t = cmd.index("-filter_complex_script")
    assert "-ss" in cmd[i_t+2:]
    assert cmd[cmd.index("-ss", i_t) + 1] == "2.5"
    assert cmd[cmd.index("-t", i_t) + 1] == "5"

def test_track_an_tat_tieng(tmp_path):
    tl = _tl(_v("c_1", "m_v", 0, 0, 5), tracks=[
        {"id": "V1", "loai": "video"},
        {"id": "V2", "loai": "video", "an": True},
        {"id": "A1", "loai": "audio", "tat_tieng": True}
    ])
    c2 = _v("c_2", "m_v", 0, 0, 5)
    c2["track"] = "V2"
    tl["clips"].append(c2)
    ca = _v("c_3", "m_a", 0, 0, 5)
    ca["track"] = "A1"
    tl["clips"].append(ca)
    
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")
    loc = kq["loc"]
    assert "color=c=" in loc # background generated
    assert loc.count("adelay") == 0 # no audio tracks added since A1 is muted


# ============================================================
# TEST XUẤT THẬT NHIỀU LỚP — 10 ca kiểm (lỗi 6 / luot5.md)
# Mỗi ca tự sinh media bằng ffmpeg, xuất thật, kiểm pixel đầu ra.
# ============================================================
import math
import struct
import numpy as np


def _ffmpeg():
    """Lấy đường dẫn ffmpeg, trả None nếu không có."""
    exe = media.ffmpeg_exe()
    return exe or None


def _tao_video_mau(exe, path, rong=320, cao=180, fps=30, giay=2, mau="red", co_am=True):
    """Tạo video .mp4 đơn sắc có tiếng sine 440Hz."""
    loi = [exe, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c={mau}:s={rong}x{cao}:r={fps}:d={giay}"]
    if co_am:
        loi += ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={giay}"]
        loi += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest"]
    else:
        loi += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"]
    loi.append(str(path))
    res = subprocess.run(loi, capture_output=True, timeout=120)
    assert res.returncode == 0, f"Không tạo được video mẫu: {res.stderr.decode(errors='replace')[-500:]}"


def _tao_anh_mau(exe, path, rong=320, cao=180, mau="blue"):
    """Tạo ảnh PNG đơn sắc."""
    loi = [exe, "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c={mau}:s={rong}x{cao}:d=0.04",
           "-frames:v", "1", str(path)]
    res = subprocess.run(loi, capture_output=True, timeout=30)
    assert res.returncode == 0, f"Không tạo được ảnh mẫu: {res.stderr.decode(errors='replace')[-300:]}"


def _xuat_va_kiem(exe, goc, du_an, tl, tuy_chon=None):
    """Dựng lệnh, ghi filter + ass, chạy ffmpeg, trả đường dẫn file ra."""
    lam = goc / "lam"
    lam.mkdir(exist_ok=True)
    ra = str(goc / "ra.mp4")
    kq = render.dung_lenh_xuat(str(goc), du_an, tl, tuy_chon or {"preset": "ultrafast"}, ra, exe)
    (lam / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    if kq.get("ass"):
        (lam / "sub.ass").write_text(kq["ass"], encoding="utf-8")
    res = subprocess.run(kq["cmd"], cwd=str(lam), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=300)
    assert res.returncode == 0, f"ffmpeg thất bại:\n{res.stderr[-2000:]}"
    return ra, kq


def _doc_khung(exe, path, giay, rong, cao):
    """Trích 1 khung tại giây `giay` → numpy array (cao, rong, 3) RGB."""
    loi = [exe, "-hide_banner", "-loglevel", "error",
           "-ss", str(giay), "-i", path,
           "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    res = subprocess.run(loi, capture_output=True, timeout=30)
    assert res.returncode == 0 and len(res.stdout) == rong * cao * 3, \
        f"Trích khung thất bại (giây={giay}, kích thước={rong}x{cao}, nhận {len(res.stdout)} bytes)"
    return np.frombuffer(res.stdout, dtype=np.uint8).reshape(cao, rong, 3)


def _mau_tai(khung, x, y):
    """Lấy màu (R,G,B) tại toạ độ (x,y) — x cột, y dòng."""
    return tuple(int(v) for v in khung[y, x])


def _gan_mau(mau_thuc, mau_ky_vong, sai_so=40):
    """Kiểm tra hai màu RGB gần nhau (sai số do nén YUV)."""
    for i in range(3):
        assert abs(mau_thuc[i] - mau_ky_vong[i]) <= sai_so, \
            f"Kênh {i}: thực={mau_thuc[i]}, kỳ vọng={mau_ky_vong[i]} (sai số >{sai_so})"


# Màu tham chiếu (RGB) — ffmpeg color filter dùng tên chuẩn X11
MAU_DO = (255, 0, 0)
MAU_XANH_LA = (0, 128, 0)      # "green" trong ffmpeg = X11 green = (0,128,0)
MAU_XANH_DA = (0, 0, 255)
MAU_DEN = (0, 0, 0)


@pytest.fixture(scope="module")
def media_mau(tmp_path_factory):
    """Fixture tạo sẵn các media mẫu dùng chung cho 10 test."""
    exe = _ffmpeg()
    if not exe:
        pytest.skip("Không có ffmpeg")
    goc = tmp_path_factory.mktemp("lop")
    (goc / "media").mkdir()
    # Video đỏ 320×180, 30fps, 3 giây, có tiếng
    _tao_video_mau(exe, goc / "media" / "do.mp4", 320, 180, 30, 3, "red")
    # Video xanh lá 320×180, 30fps, 3 giây, có tiếng
    _tao_video_mau(exe, goc / "media" / "xanh_la.mp4", 320, 180, 30, 3, "green")
    # Video xanh dương 320×180, 30fps, 3 giây, có tiếng
    _tao_video_mau(exe, goc / "media" / "xanh_da.mp4", 320, 180, 30, 3, "blue")
    # Video 180×320 (dọc) 25fps, 2 giây — khác tỉ lệ/fps
    _tao_video_mau(exe, goc / "media" / "doc.mp4", 180, 320, 25, 2, "yellow")
    # Ảnh PNG xanh lá 320×180
    _tao_anh_mau(exe, goc / "media" / "xanh_la.png", 320, 180, "green")
    return goc, exe


def _da(rong=320, cao=180, fps=30, mau_nen="#000000", them_media=None):
    """Dữ liệu dự án mẫu."""
    ms = [
        {"id": "m_do", "loai": "video", "file": "media/do.mp4", "co_am_thanh": True, "rong": 320, "cao": 180},
        {"id": "m_xl", "loai": "video", "file": "media/xanh_la.mp4", "co_am_thanh": True, "rong": 320, "cao": 180},
        {"id": "m_xd", "loai": "video", "file": "media/xanh_da.mp4", "co_am_thanh": True, "rong": 320, "cao": 180},
        {"id": "m_doc", "loai": "video", "file": "media/doc.mp4", "co_am_thanh": True, "rong": 180, "cao": 320},
        {"id": "m_anh", "loai": "anh", "file": "media/xanh_la.png", "rong": 320, "cao": 180},
    ]
    if them_media:
        ms.extend(them_media)
    return {"thong_so": {"rong": rong, "cao": cao, "fps": fps, "mau_nen": mau_nen}, "media": ms}


# ──────────────────────────────────────────────────────────────
# Ca 1: Nền đỏ + lớp phủ xanh lá ti_le=0.5 đặt giữa
# → điểm giữa khung = xanh lá, góc = đỏ
# ──────────────────────────────────────────────────────────────
def test_lop_nen_do_phu_xanh_la_giua(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},   # lớp phủ (trên)
        {"id": "V1", "loai": "video"},   # nền (dưới)
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 0.5}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    # Kiểm thời lượng
    ts = media.do_thong_so(ra)
    assert abs(ts["thoi_luong"] - 2.0) < 0.2, f"Thời lượng sai: {ts['thoi_luong']}"
    # Kiểm pixel
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    # Giữa khung (160, 90) phải là xanh lá
    _gan_mau(_mau_tai(khung, 160, 90), MAU_XANH_LA, sai_so=45)
    # Góc trên trái (5, 5) phải là đỏ (nền)
    _gan_mau(_mau_tai(khung, 5, 5), MAU_DO, sai_so=45)


# ──────────────────────────────────────────────────────────────
# Ca 2: Lớp phủ dịch sang góc phải dưới
# → xanh lá nằm ở góc phải dưới
# ──────────────────────────────────────────────────────────────
def test_lop_phu_dich_goc_phai_duoi(media_mau):
    goc, exe = media_mau
    # Đặt tâm lớp phủ ở (0.85, 0.85) với ti_le 0.3 → lớp phủ nhỏ nằm sát góc phải dưới
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.85, "y": 0.85, "ti_le": 0.3}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    # Tâm lớp phủ ở khoảng x=0.85*320=272, y=0.85*180=153 → phải là xanh lá
    _gan_mau(_mau_tai(khung, 272, 153), MAU_XANH_LA, sai_so=50)
    # Góc trên trái (5, 5) → phải là đỏ (nền, không bị phủ)
    _gan_mau(_mau_tai(khung, 5, 5), MAU_DO, sai_so=45)
    # Giữa khung (160, 90) → đỏ (lớp phủ nhỏ không tới đây)
    _gan_mau(_mau_tai(khung, 160, 90), MAU_DO, sai_so=45)


# ──────────────────────────────────────────────────────────────
# Ca 3: Lớp phủ xoay 90° → kích thước đảo chiều
# Media 320×180, ti_le=0.5 → trước xoay: 160×90, sau xoay 90°: ~90×160
# Kiểm bằng pixel ở mép ngang và dọc
# ──────────────────────────────────────────────────────────────
def test_lop_phu_xoay_90_do(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 0.5, "xoay": 90}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    # Giữa (160, 90) → xanh lá (tâm lớp phủ)
    _gan_mau(_mau_tai(khung, 160, 90), MAU_XANH_LA, sai_so=50)
    # Sau xoay 90°, chiều ngang lớp phủ ~90px, chiều dọc ~160px
    # Điểm (160, 10) — cách tâm 80px theo dọc, trong phạm vi ~80px → xanh lá
    _gan_mau(_mau_tai(khung, 160, 15), MAU_XANH_LA, sai_so=50)
    # Điểm (110, 90) — cách tâm 50px theo ngang, ngoài ~45px → đỏ (nền)
    _gan_mau(_mau_tai(khung, 110, 90), MAU_DO, sai_so=50)


# ──────────────────────────────────────────────────────────────
# Ca 4: Độ mờ 0.5 → màu trộn ~50%
# Nền đỏ (255,0,0) + phủ xanh lá (0,128,0) ở 50% mờ
# → kỳ vọng ≈ (128, 64, 0) tại tâm (sai số ±20 do YUV)
# ──────────────────────────────────────────────────────────────
def test_do_mo_05_tron_mau(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 1.0},
         "hien_thi": {"do_mo": 0.5}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    mau = _mau_tai(khung, 160, 90)
    # Kỳ vọng: R≈128, G≈64, B≈0 (blend alpha 50% nền đỏ + phủ xanh lá)
    # Sai số rộng hơn vì nén YUV chuyển đổi 2 lần
    assert 80 < mau[0] < 200, f"Kênh R ngoài khoảng trộn: {mau[0]}"
    assert 30 < mau[1] < 110, f"Kênh G ngoài khoảng trộn: {mau[1]}"
    assert mau[2] < 60, f"Kênh B quá cao cho trộn đỏ+xanh lá: {mau[2]}"


# ──────────────────────────────────────────────────────────────
# Ca 5: Bo góc → điểm sát góc lớp phủ là màu nền, giữa là lớp phủ
# ──────────────────────────────────────────────────────────────
def test_bo_goc_goc_la_nen(media_mau):
    goc, exe = media_mau
    # bo_goc=200 → r=200*180/1080≈33px — đủ lớn để pixel (5,5) chắc chắn nằm
    # trong vùng bo (cách góc ~7px << 33px). Sai số 65 vì yuva420p chroma subsampling.
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "hien_thi": {"bo_goc": 200}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    # Giữa → xanh lá (lớp phủ)
    _gan_mau(_mau_tai(khung, 160, 90), MAU_XANH_LA, sai_so=50)
    # Góc trên trái (5, 5) — nằm sâu trong vùng bo → đỏ (nền)
    mau_goc = _mau_tai(khung, 5, 5)
    _gan_mau(mau_goc, MAU_DO, sai_so=65)


# ──────────────────────────────────────────────────────────────
# Ca 6: Cắt khung trái 50% → nửa trái lớp phủ biến mất
# ──────────────────────────────────────────────────────────────
def test_cat_khung_trai_50_phan_tram(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        # Lớp phủ xanh lá, cắt trái 50% → chỉ nửa phải của lớp phủ hiện ra
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 1.0},
         "cat_khung": {"trai": 0.5, "phai": 0, "tren": 0, "duoi": 0}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    # Giữa khung (160, 90): cắt trái 50% → tâm lớp phủ dịch phải, vùng giữa
    # có thể là biên lớp phủ. Điểm bên phải xa (250, 90) nên thuộc lớp phủ
    _gan_mau(_mau_tai(khung, 250, 90), MAU_XANH_LA, sai_so=50)
    # Điểm bên trái (30, 90) — nên là nền đỏ vì cắt trái 50%
    _gan_mau(_mau_tai(khung, 30, 90), MAU_DO, sai_so=50)


# ──────────────────────────────────────────────────────────────
# Ca 7: Lớp phủ chỉ xuất hiện [1s, 2s] → khung 0.5s không có, 1.5s có
# ──────────────────────────────────────────────────────────────
def test_lop_phu_chi_hien_trong_khoang(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V2", "loai": "video"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 3, "toc_do": 1},
        # Lớp phủ xanh lá bắt đầu ở giây 1, dài 1 giây
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 1, "vao": 0, "ra": 1, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 1.0}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    ts = media.do_thong_so(ra)
    assert abs(ts["thoi_luong"] - 3.0) < 0.2, f"Thời lượng sai: {ts['thoi_luong']}"
    # Khung tại 0.5s → chỉ nền đỏ (chưa có lớp phủ)
    khung_05 = _doc_khung(exe, ra, 0.5, 320, 180)
    _gan_mau(_mau_tai(khung_05, 160, 90), MAU_DO, sai_so=45)
    # Khung tại 1.5s → lớp phủ xanh lá phủ kín (ti_le=1)
    khung_15 = _doc_khung(exe, ra, 1.5, 320, 180)
    _gan_mau(_mau_tai(khung_15, 160, 90), MAU_XANH_LA, sai_so=50)
    # Khung tại 2.5s → lại đỏ (lớp phủ hết)
    khung_25 = _doc_khung(exe, ra, 2.5, 320, 180)
    _gan_mau(_mau_tai(khung_25, 160, 90), MAU_DO, sai_so=45)


# ──────────────────────────────────────────────────────────────
# Ca 8: Fade tiếng (am_vao/am_ra) — biên độ đầu đoạn nhỏ hơn giữa
# ──────────────────────────────────────────────────────────────
def test_fade_am_thanh(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 3, "toc_do": 1,
         "am_vao": 1.0, "am_ra": 1.0},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30)
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    # Đo biên độ RMS bằng ffmpeg volumedetect ở 2 đoạn: đầu (0–0.3s) và giữa (1.2–1.8s)
    def _am_luong_doan(bat_dau, thoi_gian):
        loi = [exe, "-hide_banner", "-ss", str(bat_dau), "-t", str(thoi_gian),
               "-i", ra, "-af", "volumedetect", "-f", "null", "-"]
        res = subprocess.run(loi, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30)
        import re
        m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", res.stderr)
        return float(m.group(1)) if m else 0.0
    am_dau = _am_luong_doan(0, 0.3)
    am_giua = _am_luong_doan(1.2, 0.6)
    # Fade vào → đầu phải nhỏ hơn giữa (dB âm hơn)
    assert am_dau < am_giua - 2, f"Fade vào không hoạt động: đầu={am_dau:.1f}dB, giữa={am_giua:.1f}dB"


# ──────────────────────────────────────────────────────────────
# Ca 9: Concat hai clip khác độ phân giải + fps + ảnh PNG
# 320×180@30 + 180×320@25 + ảnh → đúng thời lượng tổng
# ──────────────────────────────────────────────────────────────
def test_concat_khac_do_phan_giai_va_fps(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 1, "toc_do": 1},
        {"id": "c2", "track": "V1", "media": "m_doc", "bat_dau": 1, "vao": 0, "ra": 1, "toc_do": 1},
        {"id": "c3", "track": "V1", "media": "m_anh", "bat_dau": 2, "vao": 0, "ra": 1, "toc_do": 1},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30)
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    ts = media.do_thong_so(ra)
    # Tổng: 1s + 1s + 1s = 3s
    assert abs(ts["thoi_luong"] - 3.0) < 0.3, f"Thời lượng concat sai: {ts['thoi_luong']}"
    assert ts["rong"] == 320 and ts["cao"] == 180, f"Kích thước sai: {ts['rong']}x{ts['cao']}"


# ──────────────────────────────────────────────────────────────
# Ca 10: Track lớp phủ ẩn (an: true) → không thấy lớp phủ
# ──────────────────────────────────────────────────────────────
def test_track_an_khong_hien_lop_phu(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "V2", "loai": "video", "an": True},  # ẩn!
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xl", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 1.0}},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    khung = _doc_khung(exe, ra, 0.5, 320, 180)
    # Track V2 ẩn → giữa khung phải là đỏ (nền), KHÔNG phải xanh lá
    _gan_mau(_mau_tai(khung, 160, 90), MAU_DO, sai_so=45)

def test_loc_mau_hieu_ung(tmp_path):
    c = _v("c_1", "m_v", 0, 0, 3)
    c["mau"] = {"sang": 10, "tuong_phan": 20, "bao_hoa": -30, "nhiet": 50}
    c["hieu_ung"] = [{"id": "x", "loai": "vintage", "do_manh": 100}, {"id": "y", "loai": "mo_hop", "do_manh": 20}]
    tl = _tl(c)
    kq = render.dung_lenh_xuat(str(tmp_path), _du_an(), tl, {}, "ra.mp4")
    loc = kq["loc"]
    chuoi = [x for x in loc.split(";") if "eq=brightness=0.1:contrast=1.2:saturation=0.7:gamma=1" in x]
    assert len(chuoi) == 1
    assert "colortemperature=temperature=4750.0" in chuoi[0]
    assert "colorchannelmixer=" in chuoi[0]
    assert "boxblur=lr=4:cr=4" in chuoi[0]

def test_xuat_that_grayscale_invert(tmp_path):
    # Tạo video ngắn xám đều
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = tmp_path / "xam.mp4"
    subprocess.run([ffmpeg, "-f", "lavfi", "-i", "color=c=gray:s=100x100:r=10:d=1", "-c:v", "libx264", str(mp4)], check=True)
    
    du = {"thong_so": {"rong": 100, "cao": 100, "fps": 10, "mau_nen": "#000000"}, "media": [
        {"id": "m1", "loai": "video", "file": "xam.mp4", "rong": 100, "cao": 100}
    ]}
    # Gray = 128. Grayscale giữ nguyên 128. Invert thành 127. Wait, color=gray is 0x808080 (128). Invert is 127.
    c = _v("c1", "m1", 0, 0, 1)
    c["hieu_ung"] = [{"id": "1", "loai": "grayscale", "do_manh": 100, "bat": True},
                     {"id": "2", "loai": "invert", "do_manh": 100, "bat": True}]
    tl = _tl(c)
    
    out = tmp_path / "out.mp4"
    kq = render.dung_lenh_xuat(str(tmp_path), du, tl, {}, str(out), ffmpeg=ffmpeg)
    
    # render.py dùng tmp_path là folder dự án, nên file phải ở đó
    script_sh = tmp_path / "run.bat"
    script_sh.write_text(" ".join(kq["cmd"]), encoding="utf-8")
    
    # render.py giả định cwd là thư mục xuất, tạo script ffmpeg + loc.txt
    (tmp_path / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    
    # Chạy ffmpeg
    subprocess.run(kq["cmd"], cwd=tmp_path, check=True)
    
    # Đọc frame đầu xem có phải màu sáng không
    import imageio.v3 as iio
    frame = iio.imread(str(out), index=0)
    # Lấy pixel giữa
    r, g, b = frame[50, 50]
    # rgb ban đầu là 128. invert -> 127. Do x264 nén có thể sai lệch chút ít.
    assert 120 <= r <= 135
    assert 120 <= g <= 135
    assert 120 <= b <= 135

def test_hieu_ung_do_manh(tmp_path):
    import json
    from orchestrator.editor.hieu_ung import loc_hieu_ung
    
    # 0 -> không sinh bộ lọc nếu grayscale hoặc invert, nhưng ma trận thì sao? 
    # ma trận m=0 => I. 
    res0 = loc_hieu_ung([{"loai": "sepia", "do_manh": 0}])
    assert "colorchannelmixer=rr=1.000:rg=0.000:rb=0.000:gr=0.000:gg=1.000:gb=0.000:br=0.000:bg=0.000:bb=1.000" in res0[0]
    
    res50 = loc_hieu_ung([{"loai": "sepia", "do_manh": 50}])
    assert "rr=0.696" in res50[0] or "rr=0.697" in res50[0]

def test_xuat_that_cold(tmp_path):
    import imageio_ffmpeg, imageio.v3 as iio
    import subprocess
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = tmp_path / "xam2.mp4"
    subprocess.run([ffmpeg, "-f", "lavfi", "-i", "color=c=gray:s=100x100:r=10:d=1", "-c:v", "libx264", str(mp4)], check=True)
    
    du = {"thong_so": {"rong": 100, "cao": 100, "fps": 10, "mau_nen": "#000000"}, "media": [
        {"id": "m1", "loai": "video", "file": "xam2.mp4", "rong": 100, "cao": 100}
    ]}
    
    from orchestrator.editor import render
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m1", "bat_dau": 0, "vao": 0, "ra": 1, "toc_do": 1, 
         "hieu_ung": [{"loai": "cold", "do_manh": 100, "bat": True}]}
    ], "kieu_phu_de": {}}
    out = tmp_path / "out_cold.mp4"
    
    kq = render.dung_lenh_xuat(str(tmp_path), du, tl, {}, str(out), ffmpeg=ffmpeg)
    (tmp_path / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    subprocess.run(kq["cmd"], cwd=tmp_path, check=True)
    
    frame = iio.imread(str(out), index=0)
    r, g, b = frame[50, 50]
    # cold 100% -> kênh B > kênh R (ám xanh)
    assert int(b) > int(r)

def test_xuat_that_mosaic_khong_chan(tmp_path):
    import imageio_ffmpeg, imageio.v3 as iio
    import subprocess
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = tmp_path / "lech.mp4"
    # Video lẻ 322x182
    subprocess.run([ffmpeg, "-f", "lavfi", "-i", "color=c=blue:s=322x182:r=10:d=1", "-c:v", "libx264", str(mp4)], check=True)
    
    du = {"thong_so": {"rong": 322, "cao": 182, "fps": 10, "mau_nen": "#000000"}, "media": [
        {"id": "m1", "loai": "video", "file": "lech.mp4", "rong": 322, "cao": 182}
    ]}
    
    from orchestrator.editor import render
    # Thêm mosaic
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m1", "bat_dau": 0, "vao": 0, "ra": 1, "toc_do": 1, 
         "hieu_ung": [{"loai": "mosaic", "do_manh": 20, "bat": True}]}
    ], "kieu_phu_de": {}}
    out = tmp_path / "out_mosaic.mp4"
    
    kq = render.dung_lenh_xuat(str(tmp_path), du, tl, {}, str(out), ffmpeg=ffmpeg)
    (tmp_path / "loc.txt").write_text(kq["loc"], encoding="utf-8")
    subprocess.run(kq["cmd"], cwd=tmp_path, check=True)
    
    frame = iio.imread(str(out), index=0)
    assert frame.shape[0] == 182
    assert frame.shape[1] == 322


# ============================================================
# TEST CHUYỂN CẢNH XFADE (lượt 9b)
# ============================================================


def test_tinh_xfade_offset_va_tong_thoi_luong():
    """Hàm thuần: 2 clip 2s + fade 1s → offset đúng, tổng thời lượng 4s."""
    clips = [
        {"id": "c1", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1, "media": "m1"},
        {"id": "c2", "bat_dau": 2, "vao": 0, "ra": 2, "toc_do": 1, "media": "m2"},
    ]
    cc = [{"truoc": "c1", "sau": "c2", "loai": "fade", "dai": 1}]
    kq = render.tinh_xfade(clips, cc)
    assert len(kq) == 2
    # Clip 1: mở rộng ra thêm 0.5s (dai/2) → ra_moi = 2.5
    assert abs(kq[0]["ra_moi"] - 2.5) < 0.01
    assert kq[0]["sau_cc"] is not None
    assert kq[0]["truoc_cc"] is None
    # Clip 2: mở rộng vào trước 0.5s → vao_moi = -0.5 → pad nếu có media_info
    assert abs(kq[1]["vao_moi"] - (-0.5)) < 0.01
    assert kq[1]["truoc_cc"] is not None
    # Tổng thời lượng timeline phải giữ nguyên = 4s (2 + 2)
    tong = render.tong_thoi_luong_xfade(clips, cc)
    assert abs(tong - 4.0) < 0.01


def test_tinh_xfade_tpad_khi_thieu_media():
    """Clip không đủ media phía trước → pad_truoc > 0."""
    clips = [
        {"id": "c1", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1, "media": "m1"},
        {"id": "c2", "bat_dau": 2, "vao": 0, "ra": 2, "toc_do": 1, "media": "m2"},
    ]
    cc = [{"truoc": "c1", "sau": "c2", "loai": "fade", "dai": 1}]
    # Giải thích: clip c2 có vao=0, cần mở rộng 0.5s trước → vao_moi = -0.5.
    # Media m2 chỉ dài 2s, nên không có đủ trước giây 0 → pad_truoc = 0.5s.
    mi = {"m1": {"thoi_luong": 10}, "m2": {"thoi_luong": 2}}
    kq = render.tinh_xfade(clips, cc, mi)
    assert abs(kq[1]["pad_truoc"] - 0.5) < 0.01, "Phải có tpad clone 0.5s trước clip 2"
    assert abs(kq[1]["vao_moi"]) < 0.01, "vao_moi bị kẹp về 0"


def test_tinh_xfade_clip_khong_ke_bi_bo():
    """Chuyển cảnh giữa 2 clip KHÔNG kề nhau → bị bỏ (concat thường)."""
    clips = [
        {"id": "c1", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1, "media": "m1"},
        {"id": "c2", "bat_dau": 5, "vao": 0, "ra": 2, "toc_do": 1, "media": "m2"},
    ]
    cc = [{"truoc": "c1", "sau": "c2", "loai": "fade", "dai": 1}]
    kq = render.tinh_xfade(clips, cc)
    assert kq[0]["sau_cc"] is None, "Chuyển cảnh phải bị bỏ vì clip không kề"
    assert kq[1]["truoc_cc"] is None


def test_xuat_that_xfade_2_clip_do_xanh(media_mau):
    """XUẤT THẬT: 2 clip đỏ/xanh dương 320×180, 2s + fade 1s → đúng thời lượng 4.0 ±0.1s.
    Khung 1.0s = đỏ, khung 3.0s = xanh dương, khung 2.0s = màu trộn (R>60 và B>60)."""
    goc, exe = media_mau
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V1", "media": "m_xd", "bat_dau": 2, "vao": 0, "ra": 2, "toc_do": 1},
    ], "chuyen_canh": [
        {"id": "cc_1", "truoc": "c1", "sau": "c2", "loai": "fade", "dai": 1}
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30)
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    ts = media.do_thong_so(ra)
    assert abs(ts["thoi_luong"] - 4.0) < 0.1, f"Thời lượng sai: {ts['thoi_luong']}"
    # Khung 1.0s = đỏ
    k1 = _doc_khung(exe, ra, 1.0, 320, 180)
    m1 = _mau_tai(k1, 160, 90)
    assert m1[0] > 180, f"Khung 1.0s phải đỏ, nhận R={m1[0]}"
    # Khung 3.0s = xanh dương
    k3 = _doc_khung(exe, ra, 3.0, 320, 180)
    m3 = _mau_tai(k3, 160, 90)
    assert m3[2] > 180, f"Khung 3.0s phải xanh dương, nhận B={m3[2]}"
    # Khung 2.0s = màu trộn (cả R và B đều > 60)
    k2 = _doc_khung(exe, ra, 2.0, 320, 180)
    m2 = _mau_tai(k2, 160, 90)
    assert m2[0] > 60 and m2[2] > 60, f"Khung 2.0s phải trộn, nhận R={m2[0]} B={m2[2]}"


def test_xuat_that_3_clip_2_chuyen_canh(media_mau):
    """3 clip + 2 chuyển cảnh khác kiểu (fade, wipeleft) xuất không lỗi và đúng thời lượng."""
    goc, exe = media_mau
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V1", "media": "m_xl", "bat_dau": 2, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c3", "track": "V1", "media": "m_xd", "bat_dau": 4, "vao": 0, "ra": 2, "toc_do": 1},
    ], "chuyen_canh": [
        {"id": "cc_1", "truoc": "c1", "sau": "c2", "loai": "fade", "dai": 0.5},
        {"id": "cc_2", "truoc": "c2", "sau": "c3", "loai": "wipeleft", "dai": 0.5},
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30)
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    ts = media.do_thong_so(ra)
    # Tổng timeline = 2+2+2 = 6s
    assert abs(ts["thoi_luong"] - 6.0) < 0.2, f"Thời lượng sai: {ts['thoi_luong']}"


def test_xuat_that_chuyen_canh_qua_anh_va_clip_het_media(media_mau):
    """Video dùng HẾT media (phải tpad clone) → ẢNH → video, chuyển cảnh 1 s ở mỗi điểm nối.

    Test cũ không khai `thoi_luong` nên không bao giờ đi vào nhánh tpad; dự án thật thì có —
    người giám sát từng gặp bản xuất mất hẳn clip ảnh và 6 giây cuối đen."""
    goc, exe = media_mau
    ms = [{"id": "m_do3", "loai": "video", "file": "media/do.mp4", "co_am_thanh": True, "rong": 320, "cao": 180, "thoi_luong": 3},
          {"id": "m_anh3", "loai": "anh", "file": "media/xanh_la.png", "rong": 320, "cao": 180},
          {"id": "m_xd3", "loai": "video", "file": "media/xanh_da.mp4", "co_am_thanh": True, "rong": 320, "cao": 180, "thoi_luong": 3}]
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do3", "bat_dau": 0, "vao": 0, "ra": 3, "toc_do": 1},
        {"id": "c2", "track": "V1", "media": "m_anh3", "bat_dau": 3, "vao": 0, "ra": 3, "toc_do": 1},
        {"id": "c3", "track": "V1", "media": "m_xd3", "bat_dau": 6, "vao": 0, "ra": 3, "toc_do": 1},
    ], "chuyen_canh": [
        {"id": "cc_1", "truoc": "c1", "sau": "c2", "loai": "fade", "dai": 1},
        {"id": "cc_2", "truoc": "c2", "sau": "c3", "loai": "fade", "dai": 1},
    ], "kieu_phu_de": {}}
    ra, kq = _xuat_va_kiem(exe, goc, _da(them_media=ms), tl)
    assert abs(media.do_thong_so(ra)["thoi_luong"] - 9.0) < 0.2
    for giay, mau in ((1.0, (255, 0, 0)), (4.5, (0, 128, 0)), (7.5, (0, 0, 255)), (8.8, (0, 0, 255))):
        khung = _doc_khung(exe, ra, giay, 320, 180)
        _gan_mau(_mau_tai(khung, 160, 90), mau, 60)


def test_phu_de_neo_khong_doi_khi_co_chuyen_canh(media_mau):
    """Phụ đề neo media + chuyển cảnh: giờ phụ đề trong .ass không đổi so với không có chuyển cảnh."""
    goc, exe = media_mau
    pd = {"id": "s", "track": "S1", "loai": "phu_de", "tu_media": "m_do", "t_vao": 0.5, "t_ra": 1.5, "text": "Chào"}
    clips_base = [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V1", "media": "m_xd", "bat_dau": 2, "vao": 0, "ra": 2, "toc_do": 1},
    ]
    tracks = [{"id": "V1", "loai": "video"}, {"id": "S1", "loai": "phu_de"}]
    # Không chuyển cảnh
    tl_ko = {"tracks": tracks, "clips": clips_base + [pd], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30)
    _, kq_ko = _xuat_va_kiem(exe, goc, da, tl_ko)
    # Có chuyển cảnh
    tl_co = {"tracks": tracks, "clips": clips_base + [pd], "chuyen_canh": [
        {"id": "cc_1", "truoc": "c1", "sau": "c2", "loai": "fade", "dai": 1}
    ], "kieu_phu_de": {}}
    _, kq_co = _xuat_va_kiem(exe, goc, da, tl_co)
    # Giờ phụ đề trong .ass phải giống nhau
    assert kq_ko["ass"] == kq_co["ass"], "Giờ phụ đề phải không đổi khi thêm chuyển cảnh"


def test_cac_kieu_xfade_co_trong_ffmpeg():
    """Mỗi kiểu trong CAC_KIEU_XFADE phải có trong ffmpeg -h filter=xfade."""
    exe = _ffmpeg()
    if not exe:
        pytest.skip("Không có ffmpeg")
    res = subprocess.run([exe, "-h", "filter=xfade"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=30)
    output = res.stdout + res.stderr
    for kieu in render.CAC_KIEU_XFADE:
        assert kieu in output, f"Kiểu xfade '{kieu}' không có trong ffmpeg"
def test_chu_hinh_sinh_ass():
    tl = _tl(
        {"id": "c1", "track": "O1", "loai": "chu", "bat_dau": 1, "vao": 0, "ra": 3, "toc_do": 1, "noi_dung": "Test chữ",
         "kieu": {"font": "Arial", "co": 48, "mau": "#ff0000", "vien_day": 2, "vien_mau": "#00ff00"},
         "bien_doi": {"x": 0.2, "y": 0.8, "ti_le": 1.5, "xoay": 10},
         "hien_thi": {"do_mo": 0.5}, "hieu_ung_vao": "mo_dan"},
        {"id": "c2", "track": "O1", "loai": "hinh", "bat_dau": 2, "ket_thuc": 5, "dang": "tron", "mau": "#0000ff", "do_mo": 1.0,
         "bien_doi": {"x": 0.5, "y": 0.5, "rong": 0.4, "cao": 0.4, "xoay": 0}}
    )
    # Call tao_ass
    from orchestrator.editor.chu_hinh import tao_ass
    ass = tao_ass(tl, 1920, 1080)
    # Check Text properties
    assert "Dialogue: 3,0:00:01.00,0:00:04.00,k_mac_dinh,,0,0,0,," in ass
    assert "\\pos(384.0,864.0)" in ass
    assert "\\frz-10.00" in ass
    assert "\\fscx150.0\\fscy150.0" in ass
    assert "\\fnArial\\fs48.0" in ass
    assert "\\1c&H0000FF&" in ass  # red (BGR, so FF0000)
    assert "\\alpha&H7F&" in ass
    assert "\\bord2.0" in ass
    assert "\\3c&H00FF00&" in ass
    assert "\\fad(500,0)" in ass
    assert "Test chữ" in ass
    # Hình: toạ độ vẽ DƯƠNG (libass dời hộp bao về 0,0 nên vẽ quanh tâm bằng số âm làm lệch hình)
    assert "Dialogue: 3,0:00:02.00,0:00:05.00,k_mac_dinh" in ass
    assert "\\pos(960.0,540.0)" in ass
    assert "\\1c&HFF0000&" in ass  # xanh dương (BGR)
    assert "\\p1}m 384 0 b 596 0 768 96" in ass


def test_chu_hinh_thu_tu_lop_va_escape():
    """Track đứng TRƯỚC trong mảng hiện ĐÈ LÊN → layer lớn hơn; phụ đề trên cùng; `{}` người dùng gõ không thành thẻ ASS."""
    from orchestrator.editor.chu_hinh import tao_ass
    hinh = lambda cid, tr: {"id": cid, "track": tr, "loai": "hinh", "bat_dau": 0, "ket_thuc": 2, "dang": "chu_nhat",
                            "mau": "#00ff00", "bien_doi": {"x": 0.5, "y": 0.5, "rong": 0.2, "cao": 0.2}}
    tl = {"tracks": [{"id": "O2", "loai": "lop_phu"}, {"id": "O1", "loai": "lop_phu"}, {"id": "V1", "loai": "video"}],
          "clips": [hinh("h_tren", "O2"), hinh("h_duoi", "O1"),
                    {"id": "c", "track": "O1", "loai": "chu", "bat_dau": 0, "ket_thuc": 2, "noi_dung": "a{\\b1}b"}]}
    dong = [l for l in tao_ass(tl, 320, 180).splitlines() if l.startswith("Dialogue:")]
    ds_hinh = [l for l in dong if "\\p1" in l]
    assert len(ds_hinh) == 2
    # clip của O2 xuất hiện trước trong clips → dòng hình đầu là của O2
    assert int(ds_hinh[0].split(",")[0].split()[1]) > int(ds_hinh[1].split(",")[0].split()[1])
    dong_chu = next(l for l in dong if "\\p1" not in l)
    assert "{\\b1}" not in dong_chu and "b1" in dong_chu

def test_xuat_that_chu_hinh(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [
        {"id": "O1", "loai": "lop_phu"},
        {"id": "V1", "loai": "video"},
    ], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 3, "toc_do": 1},
        {"id": "c_chu", "track": "O1", "loai": "chu", "bat_dau": 0.5, "ket_thuc": 2.5, "noi_dung": "O",
         "kieu": {"font": "Arial", "co": 100, "mau": "#ffffff"},
         "bien_doi": {"x": 0.2, "y": 0.2, "ti_le": 1.0, "xoay": 0},
         "hien_thi": {"do_mo": 1.0}},
        {"id": "c_hinh", "track": "O1", "loai": "hinh", "bat_dau": 1.0, "ket_thuc": 3.0, "dang": "chu_nhat", "mau": "#00ff00", "do_mo": 1.0,
         "bien_doi": {"x": 0.8, "y": 0.8, "rong": 0.2, "cao": 0.2, "xoay": 0}}
    ], "kieu_phu_de": {}}
    da = _da(rong=320, cao=180, fps=30, mau_nen="#ff0000")
    ra, kq = _xuat_va_kiem(exe, goc, da, tl)
    assert "subtitles=sub.ass" in kq["loc"]
    
    # Kiem tra diem anh
    import numpy as np
    khung = _doc_khung(exe, ra, 1.5, 320, 180)
    
    # Hinh chu nhat xanh la: cx=0.8, cy=0.8, w=0.2, h=0.2 => center(256, 144)
    px_hinh = khung[144, 256]
    assert px_hinh[1] > 200 and px_hinh[0] < 50 and px_hinh[2] < 50, f"Hinh khong ve dung (diem anh xanh la: {px_hinh})"
    
    # Chu O trang: cx=0.2, cy=0.2 => center(64, 36)
    vung_chu = khung[16:56, 44:84]
    assert np.max(vung_chu) > 200, f"Chu O khong hien thi tren vung"


def test_xuat_that_keyframe_lop_phu_chay_trai_sang_phai(media_mau):
    """XUẤT THẬT keyframe (lượt 11): lớp phủ xanh dương ti_le 0.3 trên nền đỏ, `bien_doi.x` 0.2→0.8 trong 2 s
    → khung 0.2 s xanh ở nửa TRÁI, khung 1.8 s xanh ở nửa PHẢI (preview dùng giaTriTai, xuất dùng biểu thức ffmpeg)."""
    goc, exe = media_mau
    tl = {"tracks": [{"id": "V2", "loai": "video"}, {"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
        {"id": "c2", "track": "V2", "media": "m_xd", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 0.3, "xoay": 0},
         "keyframes": {"bien_doi.x": [{"t": 0, "v": 0.2, "em": "tuyen_tinh"}, {"t": 2, "v": 0.8, "em": "tuyen_tinh"}]}},
    ], "kieu_phu_de": {}}
    ra, _ = _xuat_va_kiem(exe, goc, _da(), tl)
    def tam_xanh(giay):
        k = _doc_khung(exe, ra, giay, 320, 180)
        xanh = np.argwhere((k[:, :, 2] > 150) & (k[:, :, 0] < 100))
        assert len(xanh), f"Khung {giay}s không thấy lớp phủ xanh"
        return xanh[:, 1].mean()
    trai, phai = tam_xanh(0.2), tam_xanh(1.8)
    # x 0.2 → 0.26 tại 0.2 s (≈83 px), x ≈ 0.74 tại 1.8 s (≈237 px)
    assert trai < 120, f"0.2 s lớp phủ phải ở trái, tâm x={trai:.0f}"
    assert phai > 200, f"1.8 s lớp phủ phải ở phải, tâm x={phai:.0f}"



def test_render_bieu_thuc_keyframe_tu_ca_chung(tmp_path):
    import json
    with open("tests/js/ca_keyframe.json", encoding="utf-8") as f:
        ca = json.load(f)
    def ff_if(cond, a, b): return a if cond else b
    def ff_lt(a, b): return a < b
    for c in ca:
        kf = c["clip"]["keyframes"].get(c["duongDan"])
        if not kf: continue
        expr = render.bieu_thuc(kf, "t", 0.0)
        expr = expr.replace("\\\\,", ",").replace("\\,", ",").replace("if(", "iff(")
        val = eval(expr, {"iff": ff_if, "lt": ff_lt, "t": c["t"]})
        assert abs(val - c["kq"]) < 1e-4, f"{c['ten']}: mong {c['kq']}, nhận {val}"

    # Test 1 diem -> hang, lech
    assert render.bieu_thuc([{"t": 1, "v": 2}]) == "2"
    # Test lech
    expr2 = render.bieu_thuc([{"t": 1.0, "v": 1.0}, {"t": 2.0, "v": 2.0}], lech=1.0)
    expr2 = expr2.replace("\\,", ",").replace("if(", "iff(")
    assert eval(expr2, {"iff": ff_if, "lt": ff_lt, "t": 2.5}) == 1.5

def test_xuat_that_keyframe_mo_am_luong_nen_bien_doi(media_mau):
    goc, exe = media_mau
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m_do", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1,
         "bien_doi": {"x": 0.5, "y": 0.5, "ti_le": 1.0, "xoay": 0},
         "hien_thi": {"do_mo": 1.0},
         "keyframes": {
             "bien_doi.ti_le": [{"t": 0, "v": 1.0}, {"t": 2, "v": 0.5}],
             "hien_thi.do_mo": [{"t": 0, "v": 0.0}, {"t": 2, "v": 1.0}],
             "am_luong": [{"t": 0, "v": 0.0}, {"t": 2, "v": 1.0}]
         }}
    ], "kieu_phu_de": {}}
    ra, _ = _xuat_va_kiem(exe, goc, _da(), tl)
    
    k1 = _doc_khung(exe, ra, 0.2, 320, 180)
    k2 = _doc_khung(exe, ra, 1.8, 320, 180)
    m1 = _mau_tai(k1, 160, 90)
    m2 = _mau_tai(k2, 160, 90)
    assert m1[0] < 50, f"Giay 0.2 do mo 0.1 phai toi, nhan {m1[0]}"
    assert m2[0] > 180, f"Giay 1.8 do mo 0.9 phai sang do, nhan {m2[0]}"
    
    import subprocess, re
    def _am_luong(bat_dau, thoi_gian):
        res = subprocess.run([exe, "-hide_banner", "-ss", str(bat_dau), "-t", str(thoi_gian), "-i", ra, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", res.stderr)
        return float(m.group(1)) if m else -91.0
    am_dau = _am_luong(0.0, 0.5)
    am_cuoi = _am_luong(1.5, 0.5)
    assert am_dau < am_cuoi - 10, f"Am luong dau ({am_dau}) phai nho hon cuoi ({am_cuoi})"
