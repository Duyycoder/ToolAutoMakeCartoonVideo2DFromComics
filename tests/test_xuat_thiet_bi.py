"""Xuất trên thiết bị (webui/editor/xuat_thiet_bi/): phần logic thuần chạy bằng Node — phân loại làm được / chưa được,
quy đổi kích thước khớp render.kich_thuoc_xuat. (Ghép khung + mã hoá thật kiểm bằng Chrome headless, xem docs.)"""
import json
import subprocess
from pathlib import Path

import pytest

from orchestrator.editor import render
from tests.test_js_cu_phap import get_node_path

GOC = Path(__file__).parent.parent / "webui" / "editor" / "xuat_thiet_bi"


def _node(js):
    node = get_node_path()
    if not node:
        pytest.skip("cần node")
    r = subprocess.run([node, "--input-type=module", "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_kich_thuoc_xuat_khop_server():
    ca = [({"rong": 1080, "cao": 1920}, ""), ({"rong": 1080, "cao": 1920}, "720p"), ({"rong": 1920, "cao": 1080}, "4k"),
          ({"rong": 1080, "cao": 1080}, "1440p"), ({"rong": 1279, "cao": 721}, "")]
    kq = _node(f"import {{ kichThuocXuat }} from '{(GOC / 'vong_xuat.js').as_uri()}';"
               f"console.log(JSON.stringify({json.dumps(ca)}.map(([ts, l]) => kichThuocXuat(ts, l))));")
    assert kq == [list(render.kich_thuoc_xuat(ts, l)) for ts, l in ca]


def test_phan_loai_may_ghep_va_server_nuong():
    tl = {"tracks": [{"id": "V2", "loai": "video"}, {"id": "V1", "loai": "video"}, {"id": "S1", "loai": "phu_de"},
                     {"id": "O1", "loai": "lop_phu"}, {"id": "A1", "loai": "audio"}],
          "clips": [{"id": "a", "track": "V1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 3, "toc_do": 1},
                    {"id": "b", "track": "V1", "media": "m", "bat_dau": 3, "vao": 0, "ra": 3, "toc_do": 1},
                    {"id": "c", "track": "V1", "media": "h", "bat_dau": 6, "vao": 0, "ra": 2, "toc_do": 1},
                    {"id": "s", "track": "S1", "loai": "phu_de", "bat_dau": 10, "ket_thuc": 11, "text": "x"},
                    {"id": "t", "track": "O1", "loai": "chu", "bat_dau": 8, "ket_thuc": 9},
                    {"id": "k", "track": "O1", "loai": "che_phu_de", "kieu": "blur", "tu_media": "m", "t_vao": 0, "t_ra": 1},
                    {"id": "m2", "track": "V2", "media": "m", "bat_dau": 1, "vao": 0, "ra": 1, "toc_do": 1,
                     "mau": {"preset": "dien_anh"}}],
          "chuyen_canh": [{"truoc": "a", "sau": "b", "loai": "wipeleft", "dai": 1},
                          {"truoc": "a", "sau": "b", "loai": "circleopen", "dai": 1}]}
    media = [{"id": "m", "loai": "video", "ten": "m"}, {"id": "h", "loai": "video", "ten": "hevc.mov"}]
    js = (f"import {{ phanLoai }} from '{(GOC / 'phan_loai.js').as_uri()}';"
          f"const tl = {json.dumps(tl)}, md = {json.dumps(media)};"
          "console.log(JSON.stringify([phanLoai(tl, md, 0, 60, 10), phanLoai(tl, md, 0, 120, 10, new Set(['h'])),"
          " phanLoai(tl, md, 25, 60, 10)]));")
    dau, ca, sau = _node(js)
    # Màu nâng cao 1–2 s (khung 10–20) + circleopen quanh 3 s (25–35) → server nướng; wipeleft máy vẽ khớp.
    assert dau["doan"] == [[10, 20], [25, 35]] and not dau["lopChu"] and dau["chan"] == []
    assert abs(dau["tiLeNuong"] - 20 / 60) < 1e-9
    assert not any("wipeleft" in x for x in dau["lyDoNuong"]) and any("circleopen" in x for x in dau["lyDoNuong"])
    assert any("che" in x for x in dau["canhBao"]), "che làm mờ vẽ bằng trình duyệt → cảnh báo gần giống"
    # Cả video: có phụ đề + chữ → lớp chữ; nguồn h máy không đọc → nướng 6–8 s.
    assert ca["lopChu"] and ca["doan"] == [[10, 20], [25, 35], [60, 80]]
    assert any("hevc.mov" in x for x in ca["lyDoNuong"])
    assert sau["doan"] == [[25, 35]], "đoạn 2,5–6 s chỉ còn chuyển cảnh"


def test_gop_khuc_bitrate_va_uoc_luong():
    js = (f"import {{ gopKhuc }} from '{(GOC / 'phan_loai.js').as_uri()}';"
          f"import {{ bitrateXuat }} from '{(GOC / 'vong_xuat.js').as_uri()}';"
          f"import {{ danhGia, mucChoKhung }} from '{(GOC / 'ui_ho_so.js').as_uri()}';"
          "const hs = { ma_hoa: [{ codec: 'avc', do_phan_giai: '1080p', nhan: true, khung_giay: 120, phan_cung: true },"
          " { codec: 'avc', do_phan_giai: '4k', nhan: true, khung_giay: 5, phan_cung: true },"
          " { codec: 'hevc', do_phan_giai: '4k', nhan: false }] };"
          "console.log(JSON.stringify([gopKhuc([[5, 9], [0, 3], [3, 4], [8, 12]], 1, 11),"
          " bitrateXuat(3840, 2160, 60, 16), bitrateXuat(1920, 1080, 30, 19),"
          " danhGia(hs, 'avc', 1080, 1920, 30, 60), danhGia(hs, 'avc', 3840, 2160, 60, 60), danhGia(hs, 'hevc', 3840, 2160, 30, 60),"
          " danhGia(null, 'avc', 1920, 1080, 30, 60), mucChoKhung(hs, 'avc', 7680, 4320)]));")
    gop, br4k, br1080, doc, k4, hevc, chua, qua = _node(js)
    assert gop == [[1, 4], [5, 11]]
    assert 90e6 < br4k < 110e6 and 7e6 < br1080 < 9e6
    assert doc["lam_duoc"] and doc["giay"] == 23, "khung dọc 1080×1920 dùng số đo 1080p: 60 s × 30 / 120 × 1,5 ≈ 23"
    assert k4["lam_duoc"] is False and "quá chậm" in k4["chu"], "4K60 ở 5 khung/s: 60·60/5·1,5 = 1080 s > 10× thời lượng"
    assert hevc["lam_duoc"] is False and chua["lam_duoc"] is None and qua["nhan"] is False
