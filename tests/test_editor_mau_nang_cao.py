"""Chỉnh màu nâng cao: công thức Python (xuất) và JS (xem trước) phải cho cùng màu; ffmpeg nhận LUT gộp."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from orchestrator.editor import mau_nang_cao as mnc, media
from tests.test_js_cu_phap import get_node_path

GOC = Path(__file__).parent.parent
MAU = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.5, 0.5, 0.5), (0.9, 0.2, 0.1), (0.2, 0.7, 0.3),
       (0.1, 0.3, 0.95), (0.8, 0.6, 0.4), (0.33, 0.1, 0.6), (0.95, 0.9, 0.2)]
CA = [
    {"preset": "dien_anh"},
    {"preset": "den_trang", "preset_manh": 60},
    {"cong": {"tong": [[0, 10], [128, 150], [255, 240]], "lam": [[0, 0], [200, 220], [255, 255]]}},
    {"hsl": {"lam": [20, -30, 15], "cam": [-10, 25, 5], "hong": [0, -50, -20]}},
    {"preset": "neon", "preset_manh": 80, "cong": {"do": [[0, 0], [64, 80], [255, 255]]}, "hsl": {"luc": [30, 40, -10]}},
    {"can_trang": [1.2, 1.0, 0.8]},
    {"tong": {"den": -40, "toi": 30, "sang": -25, "trang": 50}},
    {"banh_xe": {"lift": [0.3, -0.2, 10], "gamma": [-0.4, 0.1, -20], "gain": [0.1, 0.5, 15], "offset": [0, 0, -10]}},
    {"can_trang": [0.9, 1.1, 1.3], "tong": {"toi": 20}, "banh_xe": {"gain": [0.6, 0.6, 0]}, "preset": "dien_anh", "hsl": {"do": [10, 20, 0]}},
]
LUT_THU = "LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n0.9 0.9 0.8\n"


def test_khong_chinh_gi_thi_khong_can_lut():
    assert mnc.ham_mau({}) is None
    assert mnc.ham_mau({"cong": {"tong": [[0, 0], [255, 255]]}, "hsl": {"do": [0, 0, 0]}}) is None
    assert mnc.loc_clip({"sang": 10}, lambda t: "") == ([], {})


def test_den_trang_va_xam_giu_nguyen():
    f = mnc.ham_mau({"preset": "den_trang_mem", "preset_manh": 100})
    r, g, b = f((0.9, 0.2, 0.1))
    assert abs(r - g) < 1e-9 and abs(g - b) < 1e-9, "đen trắng: hết màu"
    f = mnc.ham_mau({"hsl": {"lam": [50, 80, 50]}})
    assert f((0.4, 0.4, 0.4)) == (0.4, 0.4, 0.4), "HSL không đụng vào màu xám"


def test_doc_cube_va_tron_do_manh():
    lut = mnc.doc_cube(LUT_THU)
    f = mnc.ham_mau({"lut": "x.cube", "lut_manh": 50}, lut)
    trang = f((1.0, 1.0, 1.0))
    assert abs(trang[2] - 0.9) < 1e-9, "trắng → (0.9,0.9,0.8), trộn 50% → b = 0.9"
    with pytest.raises(ValueError):
        mnc.doc_cube("LUT_3D_SIZE 3\n0 0 0\n")


def test_js_va_python_cung_mau():
    node = get_node_path()
    if not node:
        pytest.skip("cần node")
    url = (GOC / "webui" / "editor" / "mau_nang_cao.js").as_uri()
    js = (f"import * as m from {json.dumps(url)}; await m.sanSang;"
          f"const ca = {json.dumps(CA)}, mau = {json.dumps(MAU)}, lut = m.docCube({json.dumps(LUT_THU)});"
          "const out = ca.map((c) => mau.map((x) => m.hamMau(c)(x)));"
          "out.push(mau.map((x) => m.hamMau({lut: 'a', lut_manh: 70, preset: 'am_ap'}, lut)(x)));"
          "console.log(JSON.stringify(out));")
    res = subprocess.run([node, "--input-type=module", "-e", js], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    ket_qua_js = json.loads(res.stdout)
    lut = mnc.doc_cube(LUT_THU)
    ham = [mnc.ham_mau(c) for c in CA] + [mnc.ham_mau({"lut": "a", "lut_manh": 70, "preset": "am_ap"}, lut)]
    for i, f in enumerate(ham):
        for j, x in enumerate(MAU):
            py = f(x)
            assert all(abs(a - b) < 1e-9 for a, b in zip(py, ket_qua_js[i][j])), (i, x, py, ket_qua_js[i][j])


@pytest.mark.skipif(not media.ffmpeg_exe(), reason="cần ffmpeg")
def test_ffmpeg_ap_lut_gop(tmp_path):
    loc, tep = mnc.loc_clip({"preset": "den_trang", "lam_net": 40, "khu_nhieu": 30}, lambda t: "")
    assert loc[0].startswith("hqdn3d") and loc[1].startswith("unsharp") and loc[2].startswith("lut3d=file=lut_")
    for ten, noi in tep.items():
        (tmp_path / ten).write_text(noi, encoding="utf-8")
    ra = tmp_path / "ra.png"
    subprocess.run([media.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=0xE03020:s=64x48", "-vf", ",".join(loc), "-frames:v", "1", str(ra)],
                   check=True, cwd=tmp_path)
    from PIL import Image
    r, g, b = Image.open(ra).convert("RGB").getpixel((32, 24))
    assert abs(r - g) <= 3 and abs(g - b) <= 3, f"preset đen trắng qua lut3d phải ra xám, được {(r, g, b)}"
    assert os.path.getsize(ra) > 0
