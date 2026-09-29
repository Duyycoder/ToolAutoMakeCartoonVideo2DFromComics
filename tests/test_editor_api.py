"""API editor qua TestClient trên một app FastAPI riêng (không nạp orchestrator.main).

Cấu hình chung giữ trong bộ nhớ, Nơi làm việc là thư mục tạm, ffmpeg bị thay bằng hàm giả.
"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator import project
from orchestrator.editor import api, luu_tru, media
from orchestrator.process_manager import ProcessManager


@pytest.fixture
def ws(tmp_path, monkeypatch):
    cfg = {"editor": {"workspace": str(tmp_path / "ws"), "du_an_ngoai": []}}
    monkeypatch.setattr(api, "load_global_config", lambda: cfg)
    monkeypatch.setattr(api, "save_global_config", lambda c: cfg.update(c) or True)
    monkeypatch.setattr(api, "_mo_explorer", lambda p: None)
    monkeypatch.setattr(media, "do_thong_so", lambda p: {"thoi_luong": 4.0, "rong": 1280, "cao": 720,
                                                          "fps": 25, "co_hinh": True, "co_am_thanh": False})
    monkeypatch.setattr(media, "tao_thumb", lambda s, d, t: open(d, "wb").write(b"j") > 0)
    monkeypatch.setattr(media, "tao_dai_hinh", lambda s, d, dai: 0)
    monkeypatch.setattr(media, "tao_song_am", lambda s, d: False)
    app = FastAPI()
    router = api.tao_router(ProcessManager())
    app.include_router(router)
    c = TestClient(app)
    c.cfg, c.router, c.tmp = cfg, router, tmp_path
    return c


def _tao(ws, ten="Phim Test", **kw):
    r = ws.post("/api/du-an", json={"ten": ten, "thong_so": {"rong": 1920, "cao": 1080, "fps": 30}, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _cho_media(ws):
    for h in ws.router.qlm.cac_hang():
        assert h.cho_rong(10)


def test_tao_du_an_va_trang_chu(ws):
    the = _tao(ws, mo_ta="thử")
    assert the["name"] == "Phim Test" and the["schema"] == 2 and the["thong_so"]["ti_le"] == "16:9"
    assert os.path.isdir(os.path.join(the["folder"], "media"))
    ds = ws.get("/api/workspace").json()
    assert [d["id"] for d in ds["du_an"]] == [the["id"]]

    lai = _tao(ws)
    assert lai["folder"] != the["folder"], "trùng tên thì thư mục thêm hậu tố"


def test_thong_so_sai_bi_tu_choi(ws):
    r = ws.post("/api/du-an", json={"ten": "x", "thong_so": {"rong": 1920, "cao": 1080, "fps": 31}})
    assert r.status_code == 400
    assert ws.post("/api/du-an", json={"ten": "  "}).status_code == 400


def test_mo_luu_dong_mo_lai_thay_y_nhu_cu(ws):
    """Tiêu chí GĐ 0: nhập media → đóng → mở lại thấy đúng bảng, đúng kích thước cột."""
    pid = _tao(ws)["id"]
    mo = ws.get(f"/api/du-an/{pid}").json()
    phien = mo["khoa"]["phien"]
    assert not mo["khoa"]["chi_doc"] and mo["timeline"]["phien_ban"] == 0

    src = ws.tmp / "IMG_0896.mov"
    src.write_bytes(b"v" * 5000)
    r = ws.post(f"/api/du-an/{pid}/media/nhap", json={"phien": phien, "files": [str(src)]})
    assert r.status_code == 200, r.text
    _cho_media(ws)
    m = ws.get(f"/api/du-an/{pid}/media").json()["media"][0]
    assert m["trang_thai"] == "san_sang" and m["thoi_luong"] == 4.0 and m["file"] == "media/IMG_0896.mov"
    assert ws.get(f"/api/du-an/{pid}/media/{m['id']}/thumb").status_code == 200
    f = ws.get(f"/api/du-an/{pid}/media/{m['id']}/file", headers={"Range": "bytes=0-9"})
    assert f.status_code == 206 and len(f.content) == 10

    ui = {"bang_trai": "media", "kich_thuoc": {"trai": 333, "phai": 444, "timeline": 222}}
    assert ws.put(f"/api/du-an/{pid}/ui", json={"phien": phien, "ui": ui}).status_code == 200
    tl = mo["timeline"]
    r = ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl,
                                                    "hoan_tac": {"hoan_tac": [{"x": 1}], "lam_lai": []}})
    assert r.json() == {"phien_ban": 1}
    assert ws.post(f"/api/du-an/{pid}/dong", json={"phien": phien}).status_code == 200

    lai = ws.get(f"/api/du-an/{pid}").json()
    assert lai["ui"] == ui and lai["timeline"]["phien_ban"] == 1
    assert lai["hoan_tac"]["hoan_tac"] == [{"x": 1}] and lai["thong_bao"] == []


def test_cua_so_thu_hai_chi_doc_va_ghi_bi_423(ws):
    pid = _tao(ws)["id"]
    a = ws.get(f"/api/du-an/{pid}").json()["khoa"]
    b = ws.get(f"/api/du-an/{pid}").json()["khoa"]
    assert b["chi_doc"]
    tl = luu_tru.timeline_rong()
    r = ws.put(f"/api/du-an/{pid}/timeline", json={"phien": b["phien"], "phien_ban": 0, "timeline": tl})
    assert r.status_code == 423
    assert ws.post(f"/api/du-an/{pid}/nhip", json={"phien": b["phien"]}).json() == {"giu_khoa": False}
    assert ws.post(f"/api/du-an/{pid}/xoa").status_code == 409, "đang mở thì không cho xoá"
    ws.post(f"/api/du-an/{pid}/dong", json={"phien": a["phien"]})
    assert ws.post(f"/api/du-an/{pid}/nhip", json={"phien": b["phien"]}).json() == {"giu_khoa": True}


def test_ghi_timeline_lech_phien_ban_tra_409_kem_so_hien_tai(ws):
    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    tl = luu_tru.timeline_rong()
    ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl})
    r = ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl})
    assert r.status_code == 409 and r.json()["detail"]["hien_tai"] == 1


def test_beacon_chi_nhan_ui_va_nha_khoa(ws):
    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    r = ws.post(f"/api/du-an/{pid}/ui-beacon", content=f'{{"phien":"{phien}","ui":{{"dau_phat":12.5}},"dong":true}}',
                headers={"Content-Type": "text/plain;charset=UTF-8"})
    assert r.status_code == 200
    folder = ws.get("/api/workspace").json()["du_an"][0]["folder"]
    assert luu_tru.doc_ui(folder) == {"dau_phat": 12.5}
    assert not luu_tru.dang_bi_giu(folder)


def test_luu_tay_va_khoi_phuc(ws):
    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    tl = luu_tru.timeline_rong()
    tl["thoi_luong"] = 9
    ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl})
    ten = ws.post(f"/api/du-an/{pid}/luu", json={"phien": phien, "nhan": "trước khi cắt"}).json()["ten"]
    tl["thoi_luong"] = 1
    ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 1, "timeline": tl})

    ds = ws.get(f"/api/du-an/{pid}/phien-ban").json()
    assert any(b["ten"] == ten and b["nhan"] == "trước khi cắt" for b in ds)
    r = ws.post(f"/api/du-an/{pid}/phien-ban/{ten}/khoi-phuc", json={"phien": phien, "phien_ban": 2})
    assert r.json()["timeline"]["thoi_luong"] == 9 and r.json()["timeline"]["phien_ban"] == 3


def test_nhap_du_an_cu_ngoai_noi_lam_viec(ws):
    cu = ws.tmp / "ngoai" / "phim cu"
    cu.mkdir(parents=True)
    (cu / "tap 1.mp4").write_bytes(b"0" * 10)
    project.init(str(cu), "Phim cũ", doi_ten=False)
    the = ws.post("/api/du-an/nhap", json={"folder": str(cu)}).json()
    assert the["ngoai"] and the["schema"] == 2
    assert os.path.normcase(str(cu)) in [os.path.normcase(p) for p in ws.cfg["editor"]["du_an_ngoai"]]
    assert (cu / "tap 1.mp4").exists()
    mo = ws.get(f"/api/du-an/{the['id']}").json()
    assert [c["media"] for c in mo["timeline"]["clips"]] == ["m_01"]


def test_nhap_thu_muc_video_thuong_thanh_du_an_khong_doi_ten(ws):
    thu = ws.tmp / "video le"
    thu.mkdir()
    (thu / "b.mp4").write_bytes(b"0")
    (thu / "a.mp4").write_bytes(b"0")
    the = ws.post("/api/du-an/nhap", json={"folder": str(thu)}).json()
    assert sorted(os.listdir(thu)) == [".duan", ".duan.json", "a.mp4", "b.mp4", "ban_ghep", "da_sub", "phu_de"]
    assert the["so_media"] == 2


def test_ban_chep_du_an_trung_id_duoc_cap_id_moi(ws):
    import shutil
    the = _tao(ws)
    shutil.copytree(the["folder"], the["folder"] + "_ban_chep")
    ids = [d["id"] for d in ws.get("/api/workspace").json()["du_an"]]
    assert len(ids) == 2 and len(set(ids)) == 2


def test_xoa_media_dang_tren_timeline_bi_chan(ws):
    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    src = ws.tmp / "a.mp4"
    src.write_bytes(b"x")
    mid = ws.post(f"/api/du-an/{pid}/media/nhap", json={"phien": phien, "files": [str(src)]}).json()["media"][0]["id"]
    _cho_media(ws)
    tl = luu_tru.timeline_rong()
    tl["clips"].append(luu_tru.clip_video("c_1", "V1", mid, 0, 4))
    ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl})
    assert ws.delete(f"/api/du-an/{pid}/media/{mid}", params={"phien": phien}).status_code == 400
    tl["clips"] = []
    ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 1, "timeline": tl})
    assert ws.delete(f"/api/du-an/{pid}/media/{mid}", params={"phien": phien}).status_code == 200
    assert ws.get(f"/api/du-an/{pid}/media").json()["media"] == []


def test_phat_khong_duoc_thi_xep_proxy(ws, monkeypatch):
    lam = []
    monkeypatch.setattr(media, "tao_proxy", lambda s, d, dai, ctx=None: lam.append(s) or open(d, "wb").write(b"p") > 0)
    pid = _tao(ws)["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    src = ws.tmp / "hevc.mov"
    src.write_bytes(b"x" * 100)
    mid = ws.post(f"/api/du-an/{pid}/media/nhap", json={"phien": phien, "files": [str(src)]}).json()["media"][0]["id"]
    _cho_media(ws)
    assert ws.post(f"/api/du-an/{pid}/media/{mid}/phat-duoc", json={"ok": False}).status_code == 200
    _cho_media(ws)
    m = ws.get(f"/api/du-an/{pid}/media").json()["media"][0]
    assert m["proxy"] == "xong" and m["phat_duoc"] is False and len(lam) == 1
    r = ws.get(f"/api/du-an/{pid}/media/{mid}/file")
    assert r.content == b"p", "có proxy thì preview dùng proxy"
    assert ws.get(f"/api/du-an/{pid}/media/{mid}/file", params={"goc": True}).content == b"x" * 100


def test_bi_controlled_folder_access_chan_thi_bao_ro_nguyen_nhan(tmp_path, monkeypatch):
    """Defender chặn ghi vào Videos/Documents và trả lỗi GIẢ "không tìm thấy file" (WinError 2)."""
    from orchestrator.editor import workspace

    def chan(path, exist_ok=False):
        raise FileNotFoundError(2, "The system cannot find the file specified", path)
    monkeypatch.setattr(workspace.os, "makedirs", chan)
    monkeypatch.setattr(workspace.os, "name", "nt")
    with pytest.raises(ValueError, match="Controlled folder access"):
        workspace.tao_thu_muc(str(tmp_path / "CaoDichVideo"))


def test_noi_lam_viec_mac_dinh_khong_nam_trong_videos():
    from orchestrator.editor import workspace
    assert os.path.basename(os.path.dirname(workspace.workspace_mac_dinh())) != "Videos"

def test_nhan_ban_du_an(ws):
    pid = _tao(ws, ten="Dự án 1")["id"]
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    src = ws.tmp / "a.mp4"
    src.write_bytes(b"x")
    ws.post(f"/api/du-an/{pid}/media/nhap", json={"phien": phien, "files": [str(src)]})
    _cho_media(ws)
    
    tl = luu_tru.timeline_rong()
    tl["clips"].append(luu_tru.clip_video("c_1", "V1", "m_01", 0, 4))
    ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl})
    
    # Nhân bản lần 1
    the = ws.post(f"/api/du-an/{pid}/nhan-ban", json={"ten": "Dự án mới"}).json()
    assert the["name"] == "Dự án mới"
    assert the["id"] != pid
    
    folder_moi = the["folder"]
    assert not os.path.exists(os.path.join(folder_moi, ".duan", "lock"))
    assert not os.path.exists(os.path.join(folder_moi, ".duan", "cache"))

    mo = ws.get(f"/api/du-an/{the['id']}").json()
    assert mo["du_an"]["name"] == "Dự án mới"
    assert mo["timeline"]["clips"][0]["id"] == "c_1"
    assert "m_01" in [m["id"] for m in mo["du_an"]["media"]]
    
    # Nhân bản lần 2 trùng tên -> thêm _2
    the2 = ws.post(f"/api/du-an/{pid}/nhan-ban", json={"ten": "Dự án mới"}).json()
    assert the2["id"] != pid and the2["id"] != the["id"]
    assert os.path.basename(the2["folder"]) == "du_an_moi_2"

def test_kho_dung_chung(ws):
    ws_dir = ws.get("/api/workspace").json()["duong_dan"]
    dc_dir = os.path.join(ws_dir, "_dung_chung")
    os.makedirs(dc_dir, exist_ok=True)
    
    file_path = os.path.join(dc_dir, "test.mp4")
    with open(file_path, "wb") as f:
        f.write(b"0")
        
    r1 = ws.get("/api/workspace/dung-chung").json()
    assert len(r1["media"]) == 1
    id1 = r1["media"][0]["id"]
    
    r2 = ws.get("/api/workspace/dung-chung").json()
    id2 = r2["media"][0]["id"]
    
    assert id1 == id2, "ID phải ổn định"
    
    # rel tuyệt đối ngoài hoặc ra khỏi _dung_chung
    r3 = ws.get("/api/workspace/dung-chung/file", params={"rel": "../../x"})
    assert r3.status_code == 404
    
    win_ini = "C:/Windows/win.ini" if os.name == "nt" else "/etc/passwd"
    r4 = ws.get("/api/workspace/dung-chung/file", params={"rel": win_ini})
    assert r4.status_code == 404
    
    # luu_tru.duong_dan_media
    import pytest
    from orchestrator.editor import luu_tru
    with pytest.raises(ValueError, match="Đường dẫn ngoài dự án"):
        luu_tru.duong_dan_media(ws_dir, "../_dung_chung/x")


def test_ai_models_tra_trang_thai_model(ws):
    """Route /api/ai/models có đăng ký (lượt 16 từng đặt sau `return r` → 404): báo model AI video + Clone dùng được không."""
    r = ws.get("/api/ai/models")
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("realesr_animevideov3"), bool) and isinstance(d.get("clone"), bool)
    assert isinstance(d.get("anh_co_san"), list)

def test_xem_chinh_xac_api(ws):
    # Tạo dự án mẫu như xuất thật
    the = _tao(ws, ten="du_an_xuat_thu")
    pid = the["id"]
    du_an_dir = the["folder"]
    from orchestrator.editor import luu_tru, media, api
    
    # Tạo media giả
    media_dir = os.path.join(du_an_dir, "media")
    os.makedirs(media_dir, exist_ok=True)
    vid_file = os.path.join(media_dir, "test.mp4")
    # Lấy ffmpeg tạo video đỏ dài 2 giây
    ff = media.ffmpeg_exe()
    import subprocess
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", "color=c=red:s=320x240:d=2", "-c:v", "libx264", vid_file], check=True, capture_output=True)
    
    phien = ws.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    
    # Gọi API để nạp media
    res_nhap = ws.post(f"/api/du-an/{pid}/media/nhap", json={"phien": phien, "files": [vid_file]})
    assert res_nhap.status_code == 200, res_nhap.text
    mid = res_nhap.json()["media"][0]["id"]
    _cho_media(ws)
    
    # Cập nhật timeline qua API
    tl = luu_tru.timeline_rong()
    tl["clips"].append({
        "id": "c1", "track": "V1", "media": mid, "loai": "video",
        "vao": 0, "ra": 2, "bat_dau": 0, "toc_do": 1
    })
    tl["thoi_luong"] = 2
    res_put = ws.put(f"/api/du-an/{pid}/timeline", json={"phien": phien, "phien_ban": 0, "timeline": tl})
    assert res_put.status_code == 200, res_put.text
    
    # Gọi API xem chính xác
    res = ws.post(f"/api/du-an/{pid}/xem-chinh-xac", json={"phien": phien, "t_vao": 0.5, "t_ra": 1.5})
    assert res.status_code == 200, res.text
    viec_id = res.json()["id"]
    
    # Đợi hàng đợi chạy
    import time
    v = None
    for _ in range(100):
        hds = ws.get(f"/api/du-an/{pid}/tac-vu").json()["tac_vu"]
        v = next((x for x in hds if x["id"] == viec_id), None)
        if not v or v["trang_thai"] in ("xong", "loi", "bi_ngat"):
            break
        time.sleep(0.1)
        
    assert v is not None
    assert v["trang_thai"] == "xong", v.get("loi")
    assert "url" in v["ket_qua"]
    
    out_file = luu_tru._p(du_an_dir, luu_tru.CACHE, "xem_chinh_xac", viec_id, f"{viec_id}.mp4")
    assert os.path.exists(out_file)
    
    # Đo bằng ffmpeg THẬT: fixture `ws` giả `media.do_thong_so` luôn trả 4.0 s (cho các test nhập media nhanh) —
    # đọc qua hàm giả là ra 4.0 dù file đúng 1 s.
    res_do = subprocess.run([ff, "-hide_banner", "-i", out_file], capture_output=True, text=True, encoding="utf-8", errors="replace")
    duration = media.phan_tich(res_do.stderr).get("thoi_luong", 0)
    assert 0.8 <= duration <= 1.2, f"đoạn xem chính xác 0.5–1.5 s phải dài ≈1 s, nhận {duration}"

def test_api_nhac_nen(ws, tmp_path, monkeypatch):
    import orchestrator.pipeline
    monkeypatch.setattr(orchestrator.pipeline, "AIVOICE_DIR", str(tmp_path))
    songs_dir = tmp_path / "apps" / "MediaComposer" / "resource" / "songs"
    songs_dir.mkdir(parents=True)
    (songs_dir / "bai1.mp3").write_text("dummy")
    (songs_dir / "bai2.mp3").write_text("dummy")
    
    app = FastAPI()
    app.include_router(api.tao_router(ProcessManager()))
    client = TestClient(app)
    
    # Mock do_thong_so to avoid ffmpeg
    monkeypatch.setattr(media, "do_thong_so", lambda path: {"thoi_luong": 100.0} if "bai1" in path else {"thoi_luong": 200.0})
    
    res = client.get("/api/nhac-nen")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["ten"] == "bai1.mp3"
    assert data[0]["thoi_luong"] == 100.0
    
    # Test path traversal
    res2 = client.get("/api/nhac-nen/..%2F..%2Ftest.txt")
    assert res2.status_code in (400, 404)
    
    res3 = client.get("/api/nhac-nen/bai1.mp3")
    assert res3.status_code == 200
    assert res3.content == b"dummy"


