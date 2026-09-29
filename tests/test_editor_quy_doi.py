"""Neo phụ đề/vùng che theo media gốc — cùng bộ ca với bản JS (tests/js/ca_quy_doi.json)."""
import json
import os

import pytest

from orchestrator.editor import quy_doi

CA = json.load(open(os.path.join(os.path.dirname(__file__), "js", "ca_quy_doi.json"), encoding="utf-8"))


@pytest.mark.parametrize("ca", CA["ca"], ids=[c["ten"] for c in CA["ca"]])
def test_ca_chung_voi_js(ca):
    assert quy_doi.hien_thi(CA["timeline"], ca["clip"]) == ca["ket_qua"]


def test_phu_de_tren_timeline_bo_track_an_va_cau_rong():
    tl = json.loads(json.dumps(CA["timeline"]))
    tl["clips"] += [
        {"id": "s_1", "track": "S1", "loai": "phu_de", "tu_media": "m_01", "t_vao": 3, "t_ra": 7, "text": "vắt"},
        {"id": "s_2", "track": "S1", "loai": "phu_de", "bat_dau": 0.5, "ket_thuc": 1, "text": "đầu"},
        {"id": "s_3", "track": "S1", "loai": "phu_de", "bat_dau": 9, "ket_thuc": 10, "text": "  "},
    ]
    assert [(p["id"], p["bd"], p["kt"]) for p in quy_doi.phu_de_tren_timeline(tl)] == [
        ("s_2", 0.5, 1), ("s_1", 3, 4), ("s_1", 6, 7)]
    tl["tracks"][1]["an"] = True
    assert quy_doi.phu_de_tren_timeline(tl) == []
