"""Route /ai của máy xuất từ xa (orchestrator/may_ai.py): cần mã, chỉ nhận tác vụ cho phép, file phải có trong cache."""
from fastapi.testclient import TestClient

from orchestrator import may_xuat

KHOA = "a" * 40 + ".mp4"


def _client(tmp_path):
    return TestClient(may_xuat.tao_app(thu_muc=str(tmp_path), ma="ma-thu"))


def test_ai_can_ma(tmp_path):
    c = _client(tmp_path)
    assert c.post("/ai", json={"loai": "phu-de", "tep": KHOA}).status_code == 401


def test_ai_chi_nhan_tac_vu_cho_phep(tmp_path):
    c = _client(tmp_path)
    h = {"Authorization": "Bearer ma-thu"}
    r = c.post("/ai", json={"loai": "long-tieng", "tep": KHOA}, headers=h)
    assert r.status_code == 400
    assert c.get("/ai", headers=h).json()["loai"] == ["phu-de"]


def test_ai_thieu_file_hoac_khoa_la(tmp_path):
    c = _client(tmp_path)
    h = {"Authorization": "Bearer ma-thu"}
    assert c.post("/ai", json={"loai": "phu-de", "tep": KHOA}, headers=h).status_code == 409
    # Khoá có đường dẫn → không được coi là file trong cache.
    assert c.post("/ai", json={"loai": "phu-de", "tep": "../../x.mp4"}, headers=h).status_code == 409
    assert c.get("/ai/khong-co", headers=h).status_code == 404
