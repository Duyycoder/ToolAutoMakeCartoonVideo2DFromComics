"""Test chức năng chạy lô (Hàng loạt)."""
import os
import time
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.editor import api, luu_tru, media, hang_loat, workspace
from orchestrator.process_manager import ProcessManager

ADAPTER = r'''
import json, sys, os
out = sys.argv[sys.argv.index("--srt-out-dir") + 1] if "--srt-out-dir" in sys.argv else "tam"
def ev(e, **k): print(json.dumps({"event": e, **k}, ensure_ascii=False), flush=True)
if "--voiceover-only" in sys.argv:
    d = sys.argv[sys.argv.index("--audio-out-dir") + 1]
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "a.vi.long_tieng.wav")
    open(p, "wb").write(b"RIFF")
    ev("autosub_done", voiceover=p, voiceover_only=True)
    sys.exit(0)
os.makedirs(out, exist_ok=True)
p = os.path.join(out, "a.vi.srt")
open(p, "w", encoding="utf-8").write("1\n00:00:01,000 --> 00:00:02,000\nhello\n\n2\n00:00:03,000 --> 00:00:04,000\nworld\n")
ev("autosub_done", srt_source=p)
'''

class PipelineGia:
    def __init__(self, script):
        self.script = script
    def build_translate_cmd(self, job, args, g):
        import sys
        cmd = [sys.executable, self.script]
        if args.get("tts_engine"):
            cmd += ["--voiceover-only", "--audio-out-dir", job["audio_dir"]]
        else:
            cmd += ["--srt-out-dir", job["srt_dir"]]
        return cmd

@pytest.fixture
def c(tmp_path, monkeypatch):
    import sys
    cfg = {"editor": {"workspace": str(tmp_path / "ws")}, "translate": {"engine": "gia"}}
    monkeypatch.setattr(api, "load_global_config", lambda: cfg)
    monkeypatch.setattr(api, "save_global_config", lambda x: True)
    monkeypatch.setattr(hang_loat, "load_global_config", lambda: cfg)
    monkeypatch.setattr(media, "do_thong_so", lambda p: {"thoi_luong": 5.0, "co_am_thanh": True, "co_hinh": False, "rong": 1920, "cao": 1080})
    for ten in ("tao_thumb", "tao_song_am"):
        monkeypatch.setattr(media, ten, lambda *a, **k: False)
    monkeypatch.setattr(media, "tao_dai_hinh", lambda *a, **k: 0)
    
    script = tmp_path / "adapter_gia.py"
    script.write_text(ADAPTER, encoding="utf-8")
    pl = PipelineGia(str(script))
    
    app = FastAPI()
    router = api.tao_router(ProcessManager(), pl)
    app.include_router(router)
    cl = TestClient(app)
    cl.ws = str(tmp_path / "ws")
    os.makedirs(cl.ws, exist_ok=True)
    return cl

def test_hang_loat_tao_du_an_va_chay(c):
    # Tạo 1 file giả
    v1 = os.path.join(c.ws, "v1.mp4")
    open(v1, "wb").write(b"video")
    
    r = c.post("/api/hang-loat", json={
        "files": [v1],
        "urls": [],
        "che_do": "moi_video_mot_du_an",
        "ten": "Lo thu",
        "thong_so": {"theo_video_dau": True},
        "buoc": {
            "phu_de": "whisper"
        }
    })
    assert r.status_code == 200
    lid = r.json()["id"]
    
    # Chờ chạy
    for _ in range(20):
        r2 = c.get(f"/api/hang-loat/{lid}")
        if r2.status_code == 200:
            lo = r2.json()["lo"]
            if all(m["trang_thai"] in ("xong", "loi") for m in lo["muc"]):
                break
        time.sleep(0.5)
        
    lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
    assert lo["muc"][0]["trang_thai"] == "xong", lo["muc"][0].get("loi")
    
    pid = lo["muc"][0]["du_an_id"]
    assert pid
    
    # Kiểm tra timeline xem đã có subtitle chưa
    # Project in c.ws / ...
    the, bang = workspace.quet(c.ws, [])
    pdir = bang.get(pid, "")
            
    assert pdir
    tl, _ = luu_tru.doc_timeline(pdir)
    # Phải có clips trên S1
    s1 = [c for c in tl["clips"] if c.get("loai") == "phu_de"]
    print("\nTIMELINE:", json.dumps(tl, ensure_ascii=False))
    print("\nLO:", json.dumps(lo, ensure_ascii=False))
    assert len(s1) == 2
    assert s1[0]["text_goc"] == "hello"  # Do adapter giả trả về 

def test_hang_loat_gom_mot_du_an(c):
    v1 = os.path.join(c.ws, "v1.mp4")
    v2 = os.path.join(c.ws, "v2.mp4")
    open(v1, "wb").write(b"video1")
    open(v2, "wb").write(b"video2")
    
    r = c.post("/api/hang-loat", json={
        "files": [v1, v2],
        "urls": [],
        "che_do": "gom_mot_du_an",
        "ten": "Lo Gom",
        "buoc": {"phu_de": "whisper"}
    })
    assert r.status_code == 200
    lid = r.json()["id"]
    
    for _ in range(20):
        lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
        if all(m["trang_thai"] in ("xong", "loi") for m in lo["muc"]):
            break
        time.sleep(0.5)
        
    lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
    assert lo["muc"][0]["trang_thai"] == "xong"
    assert lo["muc"][1]["trang_thai"] == "xong"
    
    pid = lo["muc"][0]["du_an_id"]
    assert pid == lo["muc"][1]["du_an_id"]
    
    the, bang = workspace.quet(c.ws, [])
    pdir = bang.get(pid, "")
    tl, _ = luu_tru.doc_timeline(pdir)
    v_clips = [clip for clip in tl["clips"] if clip["track"] == "V1"]
    assert len(v_clips) == 2
    assert v_clips[0]["bat_dau"] == 0
    assert v_clips[1]["bat_dau"] == 5.0 # as mocked thoi_luong is 5.0

def test_hang_loat_bi_ngat_va_chay_tiep(c):
    v1 = os.path.join(c.ws, "v1.mp4")
    open(v1, "wb").write(b"video1")
    
    r = c.post("/api/hang-loat", json={
        "files": [v1], "urls": [], "che_do": "moi_video_mot_du_an", "ten": "L", "buoc": {"phu_de": "whisper"}
    })
    lid = r.json()["id"]
    
    time.sleep(0.1) # Let it start
    
    # Test GET does not interrupt active thread
    r2 = c.get("/api/hang-loat")
    lo = next(x for x in r2.json()["lo"] if x["id"] == lid)
    assert lo["muc"][0]["trang_thai"] != "bi_ngat"
    
    # Stop thread forcefully via manager to simulate app close
    for _ in range(20):
        lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
        if lo["muc"][0]["trang_thai"] == "xong": break
        time.sleep(0.5)
    
    lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
    lo["muc"][0]["trang_thai"] = "bi_ngat" # Fake interrupted
    lo["muc"][0]["da_xong"] = ["nhap"] # Has imported media but not timeline
    
    ws = c.ws
    path = os.path.join(ws, ".hang_loat", f"{lid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lo, f)
        
    # Check bi_ngat triggers
    r3 = c.get("/api/hang-loat")
    lo3 = next(x for x in r3.json()["lo"] if x["id"] == lid)
    assert lo3["muc"][0]["trang_thai"] == "bi_ngat"
    
    # Chạy tiếp
    r_ct = c.post(f"/api/hang-loat/{lid}/chay-tiep")
    assert r_ct.status_code == 200, r_ct.text
    for _ in range(20):
        r_get = c.get(f"/api/hang-loat/{lid}")
        assert r_get.status_code == 200, r_get.text
        lo4 = r_get.json()["lo"]
        if lo4["muc"][0]["trang_thai"] == "xong": break
        time.sleep(0.5)
        
    the, bang = workspace.quet(c.ws, [])
    pid = lo4["muc"][0]["du_an_id"]
    pdir = bang.get(pid, "")
    da = luu_tru.doc_duan(pdir)
    assert len(da["media"]) == 1 # No double import

def test_hang_loat_huy(c):
    v1 = os.path.join(c.ws, "v1.mp4")
    open(v1, "wb").write(b"video1")
    r = c.post("/api/hang-loat", json={
        "files": [v1], "urls": [], "che_do": "moi_video_mot_du_an", "ten": "L", "buoc": {"phu_de": "whisper"}
    })
    lid = r.json()["id"]
    c.post(f"/api/hang-loat/{lid}/huy")
    # should be stopped eventually
    for _ in range(20):
        lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
        if lo["muc"][0]["trang_thai"] in ("loi", "cho", "dang_chay"): 
            if lo["muc"][0].get("loi") == "Bị huỷ" or lo["muc"][0].get("loi") == "Lỗi tác vụ": break
        time.sleep(0.5)
        
def test_hang_loat_du_an_khoa(c):
    # Tạo sẵn dự án và khoá
    v1 = os.path.join(c.ws, "v1.mp4")
    open(v1, "wb").write(b"video")
    
    da = workspace.tao(c.ws, "Khoa", {}, "")
    pid = da["id"]
    luu_tru.lay_khoa(da["folder"], "phien1")
    
    r = c.post("/api/hang-loat", json={
        "files": [v1], "urls": [], "che_do": "gom_mot_du_an", "ten": "K", "buoc": {}
    })
    lid = r.json()["id"]
    
    # Wait for completion first
    for _ in range(20):
        lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
        if lo["muc"][0]["trang_thai"] == "xong": break
        time.sleep(0.5)
        
    lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
    pid_chay = lo["muc"][0]["du_an_id"]
    
    the, bang = workspace.quet(c.ws, [])
    pdir = bang.get(pid_chay, "")
    luu_tru.lay_khoa(pdir, "phien1")
    
    # fake interrupted state
    lo["muc"][0]["trang_thai"] = "bi_ngat"
    lo["muc"][0]["da_xong"] = ["nhap"]
    
    path = os.path.join(c.ws, ".hang_loat", f"{lid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(lo, f)
        
    c.post(f"/api/hang-loat/{lid}/chay-tiep")
    for _ in range(20):
        r_get = c.get(f"/api/hang-loat/{lid}")
        if r_get.status_code != 200:
            break
        lo = r_get.json()["lo"]
        if lo["muc"][0]["trang_thai"] == "loi":
            break
        time.sleep(0.5)
        
    lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
    assert "cửa sổ khác" in lo["muc"][0]["loi"]

def test_ap_dung_cac_loai():
    tl = {
        "tracks": [
            {"id": "V1", "loai": "video"},
            {"id": "S1", "loai": "phu_de"}
        ],
        "clips": [
            {"id": "v1", "track": "V1", "loai": "video", "media": "m1", "vao": 0, "ra": 5, "bat_dau": 0},
            {"id": "c1", "track": "S1", "loai": "phu_de", "tu_media": "m1", "t_vao": 0, "t_ra": 2, "text": "cũ"},
            {"id": "c2", "track": "S1", "loai": "phu_de", "tu_media": "m2", "text": "không đổi"}
        ]
    }
    cac_media = [
        {"id": "m1", "thoi_luong": 5.0},
        {"id": "m_giong", "thoi_luong": 3.0}
    ]
    
    # Test phu-de
    tl1 = json.loads(json.dumps(tl))
    kq1 = {"cau": [{"t_vao": 0.5, "t_ra": 1.5, "text": "mới"}]}
    hang_loat.ap_dung("phu-de", tl1, kq1, "m1", {}, cac_media)
    s1 = [c for c in tl1["clips"] if c["track"] == "S1" and c.get("tu_media") == "m1"]
    assert len(s1) == 1
    assert s1[0]["text"] == "mới"
    assert s1[0]["text_goc"] == "mới"
    assert s1[0]["kieu"] == "k_mac_dinh"
    assert any(c["id"] == "c2" for c in tl1["clips"]) # Không chạm media khác
    
    # Test ocr + tạo che
    tl2 = json.loads(json.dumps(tl))
    tl2["tracks"].append({"id": "O1", "loai": "lop_phu"})
    kq2 = {"cau": [{"t_vao": 0, "t_ra": 1, "text": "ocr"}], "vung": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}
    hang_loat.ap_dung("ocr", tl2, kq2, "m1", {"tao_che": True}, cac_media)
    che = [c for c in tl2["clips"] if c["loai"] == "che_phu_de"]
    assert len(che) == 1
    assert che[0]["t_ra"] == 5.0 # lấy độ dài media
    assert che[0]["vung"] == kq2["vung"]
    
    # Test dich
    tl3 = json.loads(json.dumps(tl))
    kq3 = {"ids": ["c1"], "cau": [{"text": "dịch"}]}
    hang_loat.ap_dung("dich", tl3, kq3, "m1", {}, cac_media)
    c1 = next(c for c in tl3["clips"] if c["id"] == "c1")
    assert c1["text"] == "dịch"
    assert c1["text_goc"] == "cũ"
    
    # Test dich lech_so_cau
    tl4 = json.loads(json.dumps(tl))
    kq4 = {"lech_so_cau": True, "cau": [{"t_vao": 0, "t_ra": 2, "text": "mới"}]}
    hang_loat.ap_dung("dich", tl4, kq4, "m1", {}, cac_media)
    s1_dich = [c for c in tl4["clips"] if c["track"] == "S1" and c.get("tu_media") == "m1"]
    assert len(s1_dich) == 1
    assert s1_dich[0]["text"] == "mới"
    assert s1_dich[0]["text_goc"] == "" # text_goc rỗng do dịch
    
    # Test long-tieng
    tl5 = json.loads(json.dumps(tl))
    kq5 = {"media_moi": "m_giong"}
    hang_loat.ap_dung("long-tieng", tl5, kq5, "m1", {}, cac_media)
    a2 = next(t for t in tl5["tracks"] if t.get("vai") == "long_tieng")
    lt = [c for c in tl5["clips"] if c["track"] == a2["id"]]
    assert len(lt) == 1
    assert lt[0]["long_tieng_cho"] == "m1"
    assert lt[0]["media"] == "m_giong"
    assert lt[0]["ra"] == 3.0 # bị cắt theo giọng (3s < 5s)

def test_hang_loat_xuat(c):
    v1 = os.path.join(c.ws, "v1.mp4")
    # Tạo video thật cho FFmpeg xuất
    import subprocess
    from imageio_ffmpeg import get_ffmpeg_exe
    ffmpeg = get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:v", "libx264", "-c:a", "aac", v1], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    r = c.post("/api/hang-loat", json={
        "files": [v1], "urls": [], "che_do": "moi_video_mot_du_an", "ten": "L", "buoc": {"xuat": {}}
    })
    lid = r.json()["id"]
    for _ in range(30):
        lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
        if lo["muc"][0]["trang_thai"] in ("xong", "loi"): break
        time.sleep(0.5)
        
    lo = c.get(f"/api/hang-loat/{lid}").json()["lo"]
    assert lo["muc"][0]["trang_thai"] == "xong", lo["muc"][0].get("loi")
    assert "xuat" in lo["muc"][0]["da_xong"]
    
    pid = lo["muc"][0]["du_an_id"]
    the, bang = workspace.quet(c.ws, [])
    pdir = bang.get(pid, "")
    xuat_dir = os.path.join(pdir, "xuat")
    assert os.path.exists(xuat_dir)
    mp4 = [f for f in os.listdir(xuat_dir) if f.endswith(".mp4")]
    assert len(mp4) > 0
