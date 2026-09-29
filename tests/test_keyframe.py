import json
from pathlib import Path
from orchestrator.editor.keyframe import gia_tri_tai

def test_keyframe_noi_suy():
    ca = json.loads(Path('tests/js/ca_keyframe.json').read_text(encoding='utf-8'))
    for c in ca:
        kq = gia_tri_tai(c['clip'], c['duongDan'], c['t'])
        assert abs(kq - c['kq']) < 1e-6, f"{c['ten']}: mong {c['kq']}, thực tế {kq}"
