"""Kiểm tra việc ghi tham số sinh ảnh xuống config.toml của MediaComposer."""
import os

import pytest

from orchestrator import mediacomposer_config as MC

SAMPLE = """[app]
name = "demo"

[storytelling]
aspect_ratio = "16:9"
image_width = 768
image_height = 432
# 5.0 chu KHONG phai 1.5 - chu thich giai thich ly do, khong duoc mat
guidance_scale = 5.0
num_inference_steps = 8
video_fps = 24

[other]
keep = true
"""


@pytest.fixture
def cfg_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(SAMPLE, encoding="utf-8")
    return str(p)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_ghi_dung_gia_tri(cfg_file):
    written = MC.apply_sd_params(
        {"sd_steps": 22, "sd_guidance": 7.5, "sd_image_width": 832}, cfg_file
    )
    assert written["num_inference_steps"] == 22
    txt = _read(cfg_file)
    assert "num_inference_steps = 22" in txt
    assert "guidance_scale = 7.5" in txt
    assert "image_width = 832" in txt


def test_giu_nguyen_chu_thich(cfg_file):
    """config.toml có chú thích giải thích vì sao một giá trị được đặt như vậy.

    Parse-rồi-ghi-lại bằng thư viện TOML sẽ xoá sạch chúng, nên phải sửa từng dòng.
    """
    MC.apply_sd_params({"sd_guidance": 9.0}, cfg_file)
    assert "chu thich giai thich ly do" in _read(cfg_file)


def test_khong_dung_den_muc_khac(cfg_file):
    MC.apply_sd_params({"sd_steps": 30}, cfg_file)
    txt = _read(cfg_file)
    assert '[app]' in txt and 'name = "demo"' in txt
    assert "keep = true" in txt


def test_chan_gia_tri_vo_ly(cfg_file):
    """Steps 999 hay guidance âm sẽ làm Bước 3 chạy rất lâu rồi mới lỗi."""
    written = MC.apply_sd_params({"sd_steps": 999, "sd_guidance": -5}, cfg_file)
    assert written["num_inference_steps"] == 60
    assert written["guidance_scale"] == 0.0


def test_them_khoa_chua_co_vao_dung_muc(cfg_file):
    MC.apply_sd_params({"sd_ip_adapter_scale": 0.7}, cfg_file)
    txt = _read(cfg_file)
    assert "ip_adapter_scale = 0.7" in txt
    # Phải nằm TRONG [storytelling], không rơi xuống [other].
    story = txt.index("[storytelling]")
    other = txt.index("[other]")
    assert story < txt.index("ip_adapter_scale") < other


def test_bo_qua_khoa_rong(cfg_file):
    before = _read(cfg_file)
    assert MC.apply_sd_params({"sd_steps": "", "sd_guidance": None}, cfg_file) == {}
    assert _read(cfg_file) == before


def test_thieu_file_thi_khong_no(tmp_path):
    """Máy chưa chạy setup thì chưa có config.toml — không được chặn Bước 3."""
    missing = str(tmp_path / "khong-ton-tai.toml")
    assert MC.apply_sd_params({"sd_steps": 10}, missing) == {}
    assert not os.path.exists(missing)
