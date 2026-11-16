"""Thư viện âm thanh có sẵn (assets/thu_vien_am): đủ file, toàn CC0, API liệt kê / phát / thêm vào dự án."""
import os

from orchestrator.editor import thu_vien_am
from tests.test_editor_api import _cho_media, _tao, ws  # noqa: F401  (fixture ws)


def test_danh_muc_du_file_va_toan_cc0():
    ds = thu_vien_am.danh_muc()
    assert sum(m["loai"] == "sfx" for m in ds) >= 300, "Thư viện phải có vài trăm SFX"
    assert sum(m["loai"] == "nhac" for m in ds) >= 15, "Thư viện phải có nhạc nền"
    assert len({m["id"] for m in ds}) == len(ds), "id không được trùng"
    for m in ds:
        assert m["giay_phep"] == "CC0-1.0", f"{m['id']} không phải CC0"
        assert m["file"].endswith(".m4a") and os.path.isfile(os.path.join(thu_vien_am.GOC, m["file"])), m["file"]
        assert m["nguon"].startswith("https://"), f"{m['id']} thiếu link nguồn"
    nhom = {m["nhom"] for m in ds}
    for can in ("Hài hước", "Đám đông", "Whoosh", "Gameshow"):
        assert can in nhom, f"Thiếu nhóm SFX hay dùng: {can}"


def test_chan_duong_dan_ra_ngoai_thu_vien():
    assert thu_vien_am.duong_dan("../thu_vien.json") is None
    assert thu_vien_am.duong_dan("../../orchestrator/editor/api.py") is None
    m = thu_vien_am.danh_muc()[0]
    assert thu_vien_am.duong_dan(m["file"])


def test_api_liet_ke_phat_va_them_vao_du_an(ws):  # noqa: F811
    ds = ws.get("/api/thu-vien-am").json()["muc"]
    m = next(x for x in ds if x["loai"] == "sfx")
    r = ws.get("/api/thu-vien-am/tep/" + m["file"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/") and len(r.content) > 1000
    assert ws.get("/api/thu-vien-am/tep/..%2F..%2Forchestrator%2Fconfig.py").status_code == 404

    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    a = ws.post(f"/api/du-an/{pid}/thu-vien-am", json={"phien": phien, "id": m["id"]})
    assert a.status_code == 200, a.text
    media = a.json()["media"][0]
    assert media["loai"] == "audio" and media["ten"] == m["ten"], "Media mang tên dễ đọc trong thư viện"
    _cho_media(ws)
    b = ws.post(f"/api/du-an/{pid}/thu-vien-am", json={"phien": phien, "id": m["id"]}).json()["media"][0]
    assert b["id"] == media["id"], "Thêm lại cùng SFX thì dùng lại media cũ, không chép thêm"
    assert ws.post(f"/api/du-an/{pid}/thu-vien-am", json={"phien": phien, "id": "khong-co"}).status_code == 400
