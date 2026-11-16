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


def test_phan_loai_lam_duoc_va_chua_duoc():
    tl = {"tracks": [{"id": "V2", "loai": "video"}, {"id": "V1", "loai": "video"}, {"id": "S1", "loai": "phu_de"},
                     {"id": "O1", "loai": "lop_phu"}, {"id": "A1", "loai": "audio"}],
          "clips": [{"id": "a", "track": "V1", "media": "m", "bat_dau": 0, "vao": 0, "ra": 3, "toc_do": 1},
                    {"id": "b", "track": "V1", "media": "m", "bat_dau": 3, "vao": 0, "ra": 3, "toc_do": 1},
                    {"id": "s", "track": "S1", "bat_dau": 10, "ket_thuc": 11, "text": "x"},
                    {"id": "t", "track": "O1", "loai": "chu", "bat_dau": 8, "ket_thuc": 9},
                    {"id": "m2", "track": "V2", "media": "m", "bat_dau": 1, "vao": 0, "ra": 1, "toc_do": 1,
                     "mau": {"preset": "dien_anh"}}],
          "chuyen_canh": [{"truoc": "a", "sau": "b", "loai": "wipeleft", "dai": 1},
                          {"truoc": "a", "sau": "b", "loai": "circleopen", "dai": 1}]}
    media = [{"id": "m", "loai": "video"}]
    js = (f"import {{ phanLoai }} from '{(GOC / 'phan_loai.js').as_uri()}';"
          f"const tl = {json.dumps(tl)}, md = {json.dumps(media)};"
          "console.log(JSON.stringify([phanLoai(tl, md, 0, 6), phanLoai(tl, md, 0, 12), phanLoai(tl, md, 2.5, 6)]));")
    dau, ca, sau = _node(js)
    assert any("nâng cao" in x for x in dau["chan"]), "clip V2 có preset màu trong 0–6 s → chặn"
    assert not any("phụ đề" in x or "chữ" in x for x in dau["chan"]), "phụ đề/chữ nằm ngoài đoạn 0–6 s"
    assert any("phụ đề" in x for x in ca["chan"]) and any("chữ" in x for x in ca["chan"])
    assert sau["chan"] == [], "đoạn 2,5–6 s không còn clip màu nâng cao"
    assert any("circleopen" in x for x in sau["canhBao"]) and not any("wipeleft" in x for x in sau["canhBao"]), \
        "wipeleft vẽ khớp; circleopen chỉ gần giống → cảnh báo"
