"""Dashboard: xem/sua/xoa truyen + quan ly tai lieu chatbot (docs/kb)."""
import os

import pytest
from fastapi.testclient import TestClient

import orchestrator.main as main
from orchestrator.storage import StorageManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    sm = StorageManager(base_storage_dir=str(tmp_path / "storage"))
    monkeypatch.setattr(main, "storage_mgr", sm)
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "00-tong-quan.md").write_text("# Tong quan\n\n## Muc\n\nnoi dung\n", encoding="utf-8")
    monkeypatch.setattr(main.chat_mgr, "kb_dir", str(kb))
    monkeypatch.setattr(main.chat_mgr, "index_path", str(tmp_path / "kb_index.db"))
    saved = list(main.chat_mgr.kb_sections)
    yield TestClient(main.app)
    # chat_mgr dùng chung cả phiên test: trả lại KB thật cho các test chatbot sau
    main.chat_mgr.kb_sections[:] = saved
    main.chat_mgr._build_idf()


def _create(client, name):
    assert client.post("/api/stories", json={"story_name": name}).status_code == 200


def test_xem_chi_tiet_truyen(client):
    _create(client, "Đắc Kỷ")
    d = client.get("/api/stats/stories/dac_ky").json()
    assert d["slug"] == "dac_ky" and d["name"] == "Đắc Kỷ"
    assert d["busy"] is False and d["chapters"] == []


def test_doi_ten_doi_ca_thu_muc(client):
    _create(client, "Truyen A")
    r = client.patch("/api/stories/truyen_a", json={"new_name": "Truyen B", "status": "TRANSLATED"})
    assert r.status_code == 200
    sm = main.storage_mgr
    assert not os.path.exists(sm.get_story_dir("Truyen A"))
    assert sm.read_story_meta("Truyen B")["status"] == "TRANSLATED"
    slugs = [s["slug"] for s in client.get("/api/stats").json()["stories"]]
    assert slugs == ["truyen_b"]


def test_doi_ten_trung_bi_tu_choi(client):
    _create(client, "A")
    _create(client, "B")
    assert client.patch("/api/stories/a", json={"new_name": "B"}).status_code == 409


def test_trang_thai_la_bi_tu_choi(client):
    _create(client, "A")
    assert client.patch("/api/stories/a", json={"status": "XYZ"}).status_code == 400


def test_xoa_truyen(client):
    _create(client, "A")
    assert client.delete("/api/stories/a").status_code == 200
    assert client.get("/api/stats").json()["stories"] == []
    assert client.delete("/api/stories/a").status_code == 404


def test_khong_xoa_khi_dang_chay(client, monkeypatch):
    _create(client, "A")
    monkeypatch.setattr(main.process_mgr, "is_running", lambda k: k == "a_step2")
    assert client.delete("/api/stories/a").status_code == 400
    assert os.path.isdir(main.storage_mgr.get_story_dir("A"))


def test_kb_them_sua_xoa(client):
    names = [d["name"] for d in client.get("/api/kb").json()["docs"]]
    assert names == ["00-tong-quan.md"]

    body = "# Moi\n\n## Phan\n\ntu khoa doc nhat xyzabc\n"
    assert client.put("/api/kb/11-moi.md", json={"content": body}).status_code == 200
    assert client.get("/api/kb/11-moi.md").json()["content"] == body
    assert any("xyzabc" in s["content"] for s in main.chat_mgr.kb_sections)

    assert client.delete("/api/kb/11-moi.md").status_code == 200
    assert not any("xyzabc" in s["content"] for s in main.chat_mgr.kb_sections)


@pytest.mark.parametrize("bad", ["..%2Fx.md", "x.txt", ".hidden.md"])
def test_kb_ten_tep_xau(client, bad):
    # %2F không khớp route nào -> 404/405; còn lại do _kb_path chặn -> 400
    assert client.put(f"/api/kb/{bad}", json={"content": "x"}).status_code in (400, 404, 405)
    assert not os.path.exists(os.path.join(main.chat_mgr.kb_dir, "..", "x.md"))
