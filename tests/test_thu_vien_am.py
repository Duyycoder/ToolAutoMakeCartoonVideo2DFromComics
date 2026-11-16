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


def test_thu_vien_cua_toi_luu_dung_lai_va_xoa(ws):  # noqa: F811
    import subprocess
    from orchestrator.editor import media as media_mod
    ff = media_mod.ffmpeg_exe()
    if not ff:
        import pytest
        pytest.skip("cần ffmpeg")
    src = ws.tmp / "tieng cuoi.m4a"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=660:d=1",
                    "-c:a", "aac", str(src)], check=True)
    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    m = ws.post(f"/api/du-an/{pid}/media/nhap", json={"phien": phien, "files": [str(src)]}).json()["media"][0]
    _cho_media(ws)

    r = ws.post(f"/api/du-an/{pid}/media/{m['id']}/vao-thu-vien", json={"ten": "Tiếng cười của tôi", "loai": "sfx"})
    assert r.status_code == 200, r.text
    muc = r.json()
    assert muc["id"].startswith("toi-") and muc["rieng"] and muc["nhom"] == "Của tôi"
    assert (ws.tmp / "ws" / "_thu_vien_am" / muc["file"].split("/", 1)[1]).is_file(), "File lưu ở workspace/_thu_vien_am"
    ds = ws.get("/api/thu-vien-am").json()["muc"]
    assert ds[0]["id"] == muc["id"], "Mục của tôi đứng đầu danh sách"
    tep = ws.get("/api/thu-vien-am/tep/" + muc["file"])
    assert tep.status_code == 200 and len(tep.content) > 500
    lai = ws.post(f"/api/du-an/{pid}/media/{m['id']}/vao-thu-vien", json={"ten": "Đổi tên", "loai": "nhac"}).json()
    assert lai["id"] == muc["id"] and lai["loai"] == "nhac", "Lưu lại cùng file thì cập nhật, không nhân đôi"

    pid2 = _tao(ws, ten="Dự án 2")["id"]
    phien2 = ws.get(f"/api/du-an/{pid2}").json()["khoa"]["phien"]
    a = ws.post(f"/api/du-an/{pid2}/thu-vien-am", json={"phien": phien2, "id": muc["id"]})
    assert a.status_code == 200 and a.json()["media"][0]["ten"] == "Đổi tên", "Dùng lại ở dự án khác"

    assert ws.delete(f"/api/thu-vien-am/rieng/{muc['id']}").status_code == 200
    assert all(x["id"] != muc["id"] for x in ws.get("/api/thu-vien-am").json()["muc"])
    assert ws.delete(f"/api/thu-vien-am/rieng/{muc['id']}").status_code == 404
    assert ws.get("/api/thu-vien-am/tep/rieng/..%2F..%2Fx").status_code == 404
