"""Đồ thị tốc độ clip — cùng bộ ca với bản JS (tests/js/ca_toc_do_cong.json) + lệnh xuất ffmpeg."""
import json
import os

import pytest

from orchestrator.editor import render, toc_do_cong as tdc

CA = json.load(open(os.path.join(os.path.dirname(__file__), "js", "ca_toc_do_cong.json"), encoding="utf-8"))


@pytest.mark.parametrize("ca", CA["ca"], ids=[c["ten"] for c in CA["ca"]])
def test_ca_chung(ca):
    d = tdc.chuan(ca["cong"])
    assert tdc.trung_binh(d) == pytest.approx(ca["trung_binh"])
    for q, p in ca["nguon"]:
        assert tdc.nguon_tai(d, q) == pytest.approx(p, abs=1e-6)
        assert tdc.vi_tri_tai(d, p) == pytest.approx(q, abs=1e-6)


def test_khuc_am_noi_lien_va_du_doan():
    d = tdc.chuan([{"q": 0, "v": 1}, {"q": 1, "v": 3}])
    k = tdc.khuc_am(d, 4.0, 2.0)
    assert k[0][0] == 0 and k[-1][1] == pytest.approx(4.0)
    assert all(abs(a[1] - b[0]) < 1e-9 for a, b in zip(k, k[1:]))
    assert sum((s1 - s0) / tp for s0, s1, tp in k) == pytest.approx(2.0)
    assert len(k) == 8 and 1 <= k[0][2] < k[-1][2] <= 3


def _bieu_thuc(expr: str, T: float) -> float:
    """Tính biểu thức setpts bằng Python (if/lt/sqrt/max, TB = 1) để so với vi_tri_tai."""
    e = expr.replace("\\,", ",").replace("TB", "1").replace("T", repr(T)).replace("if(", "iff(")
    return eval(e, {"iff": lambda c, a, b: a if c else b, "lt": lambda a, b: a < b, "sqrt": lambda x: x ** 0.5, "max": max})


def test_bieu_thuc_pts_khop_nghich_dao():
    d = tdc.chuan([{"q": 0, "v": 1}, {"q": 0.5, "v": 1}, {"q": 0.75, "v": 4}, {"q": 1, "v": 4}])
    L, D = 4.0, 4.0 / tdc.trung_binh(d)
    bt = tdc.bieu_thuc_pts(d, L, D, -0.5)          # luồng bắt đầu sớm 0.5 s (kéo dài cho chuyển cảnh)
    goc = D * tdc.vi_tri_tai(d, -0.5 / L)
    for T in (0.0, 0.3, 1.7, 2.6, 3.9, 4.4):
        assert _bieu_thuc(bt, T) == pytest.approx(D * tdc.vi_tri_tai(d, (T - 0.5) / L) - goc, abs=1e-5)


def test_lenh_xuat_clip_co_do_thi(tmp_path):
    du_an = {"thong_so": {"rong": 1280, "cao": 720, "fps": 30}, "media": [
        {"id": "m1", "file": "a.mp4", "loai": "video", "rong": 1280, "cao": 720, "thoi_luong": 10, "co_am_thanh": True}]}
    tl = {"tracks": [{"id": "V1", "loai": "video"}], "clips": [
        {"id": "c1", "track": "V1", "media": "m1", "bat_dau": 0, "vao": 1, "ra": 5, "toc_do": 2,
         "toc_do_cong": [{"q": 0, "v": 1}, {"q": 1, "v": 3}]}]}
    kq = render.dung_lenh_xuat(str(tmp_path), du_an, tl, {}, "ra.mp4", co_ass=False)
    loc = kq["loc"]
    assert "setpts='(" in loc and "sqrt(" in loc and "setpts=PTS/" not in loc
    assert "asplit=8" in loc and loc.count("atempo=") >= 8 and "concat=n=8:v=0:a=1" in loc
    assert "trim=duration=2" in loc
