"""Tác vụ AI + xuất qua API: adapter GIẢ in đúng các event của adapter_autosub_cli.py."""
import json
import os
import subprocess
import sys
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator.editor import api, luu_tru, media
from orchestrator.process_manager import ProcessManager

ADAPTER = r'''
import json, os, sys
a, i = {}, 1
while i < len(sys.argv):
    if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
        a[sys.argv[i]] = sys.argv[i + 1]; i += 2
    else:
        a[sys.argv[i]] = True; i += 1
out = a["--srt-out-dir"]
def ev(e, **k): print(json.dumps({"event": e, **k}, ensure_ascii=False), flush=True)
ev("autosub_progress", message="Bắt đầu", percent=10)
print("dòng log thường của loguru", flush=True)
if a.get("--loi"):
    ev("autosub_error", error="CUDA out of memory"); sys.exit(1)
if "--voiceover-only" in sys.argv:
    d = a["--audio-out-dir"]; os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "a.vi.long_tieng.wav"); open(p, "wb").write(b"RIFF")
    ev("autosub_done", voiceover=p, voiceover_only=True); sys.exit(0)
if "--tach-giong-only" in sys.argv:
    d = a["--audio-out-dir"]; os.makedirs(d, exist_ok=True)
    idx = 1
    pg = os.path.join(d, "a.giong.wav")
    while os.path.exists(pg):
        idx += 1
        pg = os.path.join(d, f"a.giong({idx}).wav")
    idx_nhac = 1
    pn = os.path.join(d, "a.nhac.wav")
    while os.path.exists(pn):
        idx_nhac += 1
        pn = os.path.join(d, f"a.nhac({idx_nhac}).wav")
    open(pg, "wb").write(b"RIFF")
    open(pn, "wb").write(b"RIFF")
    ev("autosub_done", vocals=pg, no_vocals=pn, tach_giong_only=True); sys.exit(0)
if "--lam-net-only" in sys.argv:
    d = a.get("--output-dir", ".")
    idx = 1
    p = os.path.join(d, "a_net.mp4")
    while os.path.exists(p):
        idx += 1
        p = os.path.join(d, f"a_net({idx}).mp4")
    open(p, "wb").write(b"RIFF")
    with open(p + ".cmd", "w") as f: f.write(a.get("--lam-net-kieu", "nhanh") + "|" + a.get("--lam-net-do-phan-giai", "Gốc"))
    ev("autosub_done", output=p, lam_net_only=True); sys.exit(0)
if "--tao-anh-only" in sys.argv:
    d = a.get("--output-dir", ".")
    os.makedirs(d, exist_ok=True)
    imgs = []
    seeds = []
    num = int(a.get("--anh-so", "1"))
    for i in range(num):
        p = os.path.join(d, f"anh_{i}.png")
        open(p, "wb").write(b"\x89PNG")
        imgs.append(p)
        seeds.append(123 + i)
    ev("autosub_done", images=imgs, seeds=seeds)
    sys.exit(0)
if "--minh-hoa-only" in sys.argv:
    if "--pexels-api-key" not in sys.argv and "--pixabay-api-key" not in sys.argv and "--coverr-api-key" not in sys.argv:
        ev("autosub_error", error="Cần API key Pexels/Pixabay/Coverr")
        sys.exit(1)
    d = a.get("--output-dir", ".")
    os.makedirs(d, exist_ok=True)
    f1 = os.path.join(d, "vid_01.mp4"); open(f1, "wb").write(b"RIFF")
    f2 = os.path.join(d, "vid_02.mp4"); open(f2, "wb").write(b"RIFF")
    ev("autosub_done", doan=[
        {"t_vao": 1.0, "t_ra": 2.0, "file": f1, "tu_khoa": "hello"},
        {"t_vao": 3.0, "t_ra": 4.0, "file": f2, "tu_khoa": "world"}
    ])
    sys.exit(0)
if a.get("--sub-source") == "import":
    src = open(a["--source-srt"], encoding="utf-8").read()
    p = os.path.join(out, "a.vi.srt"); open(p, "w", encoding="utf-8").write(src.replace("hello", "xin chào").replace("world", "thế giới"))
    ev("autosub_done", srt_translated=p); sys.exit(0)
p = os.path.join(out, "a.zh.srt")
open(p, "w", encoding="utf-8").write("1\n00:00:01,000 --> 00:00:02,000\nhello\n\n2\n00:00:03,000 --> 00:00:04,000\nworld\n")
ev("autosub_done", srt_source=p)
'''



class PipelineGia:
    def __init__(self, script):
        self.script = script
        self.args = []

    def build_translate_cmd(self, job, args, g):
        self.args.append(args)
        cmd = [sys.executable, self.script, "--srt-out-dir", job["srt_dir"], "--sub-source", args.get("sub_source", "none"), "--video-path", job.get("video_path", ".")]
        if args.get("source_srt"):
            cmd += ["--source-srt", args["source_srt"]]
        if args.get("tts_engine") == "hong":
            cmd += ["--loi", "1"]
        if args.get("tao_anh_only"):
            cmd += ["--tao-anh-only", "--output-dir", job["output_dir"]]
            if args.get("anh_so"):
                cmd += ["--anh-so", str(args["anh_so"])]
        return cmd


@pytest.fixture
def c(tmp_path, monkeypatch):
    cfg = {"editor": {"workspace": str(tmp_path / "ws"), "du_an_ngoai": []}, "translate": {"engine": "gemini"}, "api_keys": {"gemini": "test-key"}}
    monkeypatch.setattr(api, "load_global_config", lambda: cfg)
    monkeypatch.setattr(api, "save_global_config", lambda x: True)
    monkeypatch.setattr(media, "do_thong_so", lambda p: {"thoi_luong": 5.0, "co_am_thanh": True, "co_hinh": False})
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
    the = cl.post("/api/du-an", json={"ten": "AI"}).json()
    pid = the["id"]
    phien = cl.get(f"/api/du-an/{pid}").json()["khoa"]["phien"]
    video = os.path.join(the["folder"], "media", "a.mp4")
    open(video, "wb").write(b"x")
    luu_tru.sua_duan(the["folder"], lambda d: d["media"].append(
        {"id": "m_01", "loai": "video", "file": "media/a.mp4", "ten": "a", "trang_thai": "san_sang", "rong": 640, "cao": 360}))
    cl.pid, cl.phien, cl.router, cl.pl, cl.folder = pid, phien, router, pl, the["folder"]
    
    from orchestrator.editor import dich
    class FakeDichResp:
        def raise_for_status(self): pass
        def __init__(self, text): self._text = text
        def json(self): return {"response": self._text}
    def mock_post(url, json, **k):
        prompt = json.get("prompt", "")
        if prompt.endswith("hello"): return FakeDichResp("xin chào")
        if prompt.endswith("world"): return FakeDichResp("thế giới")
        return FakeDichResp("lỗi")
    monkeypatch.setattr(dich.requests, "post", mock_post)
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    
    return cl


def _cho(c, vid, han=20):
    t = time.time() + han
    while time.time() < t:
        for v in c.get(f"/api/du-an/{c.pid}/tac-vu").json()["tac_vu"]:
            if v["id"] == vid and v["trang_thai"] not in ("cho", "dang_chay"):
                return v
        time.sleep(0.1)
    raise AssertionError("tác vụ không xong")


def _chay(c, loai, **ts):
    r = c.post(f"/api/du-an/{c.pid}/ai/{loai}", json={"phien": c.phien, "media": "m_01", "tham_so": ts})
    assert r.status_code == 200, r.text
    return _cho(c, r.json()["viec"]["id"])


def test_whisper_tra_cau_va_luu_trang_thai(c):
    v = _chay(c, "phu-de", source_lang="Chinese")
    assert v["trang_thai"] == "xong", v
    assert v["ket_qua"]["cau"] == [{"t_vao": 1.0, "t_ra": 2.0, "text": "hello"}, {"t_vao": 3.0, "t_ra": 4.0, "text": "world"}]
    assert c.pl.args[-1]["sub_source"] == "whisper" and c.pl.args[-1]["no_translate"] is True
    assert not v["da_ap_dung"]
    assert c.post(f"/api/du-an/{c.pid}/tac-vu/{v['id']}/ap-dung", json={"phien": c.phien}).status_code == 200
    tv = [x for x in luu_tru.doc_duan(c.folder)["tac_vu"] if x["id"] == v["id"]][0]
    assert tv["da_ap_dung"] is True and tv["ket_qua"]["so_cau"] == 2


def test_ocr_can_vung_va_truyen_toa_do_pixel(c):
    r = c.post(f"/api/du-an/{c.pid}/ai/ocr", json={"phien": c.phien, "media": "m_01", "tham_so": {}})
    assert r.status_code == 400 and "vùng" in r.json()["detail"]
    v = _chay(c, "ocr", vung={"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.1}, vung_px={"x": 64, "y": 288, "w": 512, "h": 36})
    assert v["trang_thai"] == "xong" and v["ket_qua"]["vung"]["y"] == 0.8
    assert (c.pl.args[-1]["crop_y"], c.pl.args[-1]["crop_h"]) == (288, 36)


def test_ocr_truyen_so_khung_va_model(c):
    _chay(c, "ocr", vung={"x": 0.1, "y": 0.8, "w": 0.8, "h": 0.1}, vung_px={"x": 64, "y": 288, "w": 512, "h": 36},
          ocr_fps=15, ocr_model="small")
    assert (c.pl.args[-1]["ocr_fps"], c.pl.args[-1]["ocr_model"]) == (15.0, "small")


def test_bat_su_kien_long_tieng_bao_cau_va_loc_lenh_ffmpeg():
    """Lượt 24: thẻ Lồng tiếng hiện 'Đang đọc câu x/y' + %, dòng lệnh ffmpeg thô không đè lên thông điệp."""
    from orchestrator.editor import ai_bridge
    bao = []

    class Ctx:
        def bao(self, pct, msg):
            bao.append((pct, msg))
    sk = ai_bridge.BatSuKien(Ctx())
    sk('2026-09-29 | INFO | Extracting optimized audio track: F:\\x\\ffmpeg.exe -y -i v.mp4 -vn -ac 1 -ar 16000 -acodec pcm_s16le a.wav')
    sk('F:\\programfiles\\AIVoice\\ffmpeg.exe -y -i a.wav b.wav')
    sk('{"event": "autosub_progress", "message": "Đang đọc câu 11/1925", "percent": 10}')
    sk('Segment 12: Target duration = 2.00s, TTS actual = 1.50s')
    assert bao == [(10.0, "Đang đọc câu 11/1925"), (None, "Segment 12: Target duration = 2.00s, TTS actual = 1.50s")]


def test_lenh_pipeline_co_ocr_fps():
    from orchestrator import pipeline
    pl = pipeline.VideoPipeline.__new__(pipeline.VideoPipeline)      # chỉ cần dựng lệnh, không cần thư viện/tiến trình
    cmd = pl.build_translate_cmd({"video_path": "a.mp4", "output_dir": "o", "srt_dir": "o"},
                                 {"sub_source": "ocr", "llm_engine": "ollama", "ocr_fps": 15.0, "ocr_model": "small"}, {})
    assert cmd[cmd.index("--ocr-fps") + 1] == "15.0" and cmd[cmd.index("--ocr-model") + 1] == "small"


def test_dich_giu_thu_tu_id(c):
    v = _chay(c, "dich", target_lang="Vietnamese", ids=["c_7", "c_8"],
              cau=[{"t_vao": 1, "t_ra": 2, "text": "hello"}, {"t_vao": 3, "t_ra": 4, "text": "world"}])
    assert v["ket_qua"]["ids"] == ["c_7", "c_8"]
    assert [x["text"] for x in v["ket_qua"]["cau"]] == ["xin chào", "thế giới"]
    assert "cau" not in v["tham_so"], "không lưu cả loạt câu vào .duan.json"


def test_dich_khong_co_cau_bao_loi_ngay(c):
    r = c.post(f"/api/du-an/{c.pid}/ai/dich", json={"phien": c.phien, "media": "m_01", "tham_so": {"cau": []}})
    assert r.status_code == 400


def test_long_tieng_dang_ky_media_giong(c):
    v = _chay(c, "long-tieng", tts_engine="edge", cau=[{"t_vao": 1, "t_ra": 2, "text": "xin chào"}], ids=["c_1"])
    assert v["trang_thai"] == "xong", v.get("loi")
    mid = v["ket_qua"]["media_moi"]
    m = [x for x in luu_tru.doc_duan(c.folder)["media"] if x["id"] == mid][0]
    assert m["file"] == "long_tieng/a.vi.long_tieng.wav" and m["tu_media"] == "m_01" and m["loai"] == "audio"


def test_adapter_bao_loi_thi_tac_vu_loi_voi_thong_diep(c):
    v = _chay(c, "long-tieng", tts_engine="hong", cau=[{"t_vao": 1, "t_ra": 2, "text": "a"}], ids=["c_1"])
    assert v["trang_thai"] == "loi" and "CUDA" in v["loi"]


def test_xuat_video_that_qua_hang_doi(c, monkeypatch):
    exe = media.ffmpeg_exe()
    if not exe:
        pytest.skip("không có ffmpeg")
    video = os.path.join(c.folder, "media", "a.mp4")
    res = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                          "testsrc2=size=320x240:rate=25:duration=2", "-f", "lavfi", "-i", "sine=d=2",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", video], capture_output=True)
    if res.returncode:
        pytest.skip("không tạo được video mẫu")
    luu_tru.sua_duan(c.folder, lambda d: d["media"][0].update(co_am_thanh=True))
    tl = luu_tru.timeline_rong()
    tl["clips"] = [{"id": "c_1", "track": "V1", "media": "m_01", "bat_dau": 0, "vao": 0, "ra": 2, "toc_do": 1},
                   {"id": "c_2", "track": "S1", "loai": "phu_de", "tu_media": "m_01", "t_vao": 0.2, "t_ra": 1, "text": "chào"}]
    c.put(f"/api/du-an/{c.pid}/timeline", json={"phien": c.phien, "phien_ban": 0, "timeline": tl})
    r = c.post(f"/api/du-an/{c.pid}/xuat", json={"phien": c.phien, "tuy_chon": {
        "ten": "Bản: thử", "bo_ma_hoa": "x264", "preset": "ultrafast", "xuat_srt": True, "do_phan_giai": "720p"}})
    assert r.status_code == 200, r.text
    v = _cho(c, r.json()["viec"]["id"], 120)
    assert v["trang_thai"] == "xong", v
    kq = v["ket_qua"]
    assert kq["file"] == "xuat/Bản_ thử.mp4" and kq["srt"] == "xuat/Bản_ thử.srt"
    ts = media.do_thong_so.__wrapped__(os.path.join(c.folder, kq["file"])) if hasattr(media.do_thong_so, "__wrapped__") else None
    assert os.path.getsize(os.path.join(c.folder, kq["file"])) > 1000
    assert "chào" in open(os.path.join(c.folder, kq["srt"]), encoding="utf-8").read()
    assert kq["kich_thuoc"] == [1280, 720]
    _ = ts


def test_dam_bao_llm_bat_ollama(c, monkeypatch):
    cfg = {"editor": {"workspace": c.folder, "du_an_ngoai": []}, "translate": {"engine": "ollama", "autostart_ollama": True, "ollama_base_url": "http://lo2"}}
    monkeypatch.setattr(api, "load_global_config", lambda: cfg)
    goi = []
    from orchestrator import ollama_manager
    monkeypatch.setattr(ollama_manager, "ensure_ready", lambda m, u, autostart, progress_cb: goi.append(autostart) or {"ok": False, "reason": ""})
    r = c.post(f"/api/du-an/{c.pid}/ai/dich", json={"phien": c.phien, "media": "m_01", "tham_so": {"cau": [{"t_vao": 1, "t_ra": 2, "text": "hello"}]}})
    assert r.status_code == 200
    v = _cho(c, r.json()["viec"]["id"])
    assert v["trang_thai"] == "loi" and "chưa chạy ở http://lo2" in v["loi"]
    assert goi[0] is True



def test_whisper_bo_canh_bao_dich_trung(c):
    c.pl.build_translate_cmd_org = c.pl.build_translate_cmd
    def fake(job, args, g):
        cmd = c.pl.build_translate_cmd_org(job, args, g)
        if args.get("sub_source") == "whisper":
            cmd += ["--fake-dich-loi", "1"]
        return cmd
    c.pl.build_translate_cmd = fake
    script = c.pl.script
    src = open(script, "r", encoding="utf-8").read()
    open(script, "w", encoding="utf-8").write(src.replace('if a.get("--loi"):', 'if a.get("--loi"):\n    pass\nif "--fake-dich-loi" in sys.argv:\n    print("Translation attempt 1 failed: Connection error.", flush=True)\n    ev("autosub_warn", message="Bản dịch trùng bản gốc — kiểm tra API key / model / Base URL dịch!")\n    open(out + "/fake.srt", "w", encoding="utf-8").write("1\\n00:00:01,000 --> 00:00:02,000\\nhello\\n")\n    ev("autosub_done", srt_source=out + "/fake.srt")\n    sys.exit(0)\nif a.get("--loi"):'))
    
    v = _chay(c, "phu-de")
    assert v["trang_thai"] == "xong"
    assert not any("Bản dịch trùng bản gốc" in w for w in v["ket_qua"].get("canh_bao", []))

def test_ngon_ngu_nguon_auto_bao_loi(c):
    r = c.post(f"/api/du-an/{c.pid}/ai/dich", json={"phien": c.phien, "media": "m_01", "tham_so": {"source_lang": "auto", "cau": [{"t_vao": 1, "text": "a"}]}})
    assert r.status_code == 400 and "Chưa biết ngôn ngữ nguồn" in r.text


def test_tach_giong_dang_ky_media_ap_dung(c):
    v1 = _chay(c, "tach-giong", cau=[], ids=[])
    assert v1["trang_thai"] == "xong", v1.get("loi")
    mg1 = v1["ket_qua"].get("media_giong")
    mn1 = v1["ket_qua"].get("media_nhac")
    assert mg1 and mn1

    v2 = _chay(c, "tach-giong", cau=[], ids=[])
    assert v2["trang_thai"] == "xong", v2.get("loi")
    mg2 = v2["ket_qua"].get("media_giong")
    mn2 = v2["ket_qua"].get("media_nhac")
    assert mg2 != mg1 and mn2 != mn1
    assert "giong(2)" in luu_tru.doc_duan(c.folder)["media"][-2]["file"]
    
    tl = luu_tru.doc_timeline(c.folder)[0]
    import orchestrator.editor.hang_loat as hl
    hl.ap_dung("tach-giong", tl, v2["ket_qua"], "m_01", {}, luu_tru.doc_duan(c.folder)["media"])
    tl2 = tl
    assert len(tl2.get("tracks", [])) > 2

def test_lam_net_dang_ky_media_ap_dung(c):
    v1 = _chay(c, "lam-net", cau=[], ids=[], kieu="ai_video", do_phan_giai="720p (HD)", phong_to=True)
    assert v1["trang_thai"] == "xong", v1.get("loi")
    mm1 = v1["ket_qua"].get("media_moi")
    assert mm1
    cmd1 = open(os.path.join(c.folder, luu_tru.doc_duan(c.folder)["media"][-1]["file"] + ".cmd"), "r").read()
    assert cmd1 == "ai_video|720p (HD)"

    v2 = _chay(c, "lam-net", cau=[], ids=[], kieu="ai_video", do_phan_giai="720p (HD)", phong_to=False)
    assert v2["trang_thai"] == "xong", v2.get("loi")
    mm2 = v2["ket_qua"].get("media_moi")
    assert mm2 != mm1
    assert "net(2)" in luu_tru.doc_duan(c.folder)["media"][-1]["file"]
    cmd2 = open(os.path.join(c.folder, luu_tru.doc_duan(c.folder)["media"][-1]["file"] + ".cmd"), "r").read()
    assert cmd2 == "nhanh|Gốc"
    
    tl = luu_tru.doc_timeline(c.folder)[0]
    tl["clips"] = [{"id": "c1", "media": "m_01"}]
    import orchestrator.editor.hang_loat as hl
    hl.ap_dung("lam-net", tl, v2["ket_qua"], "m_01", {}, luu_tru.doc_duan(c.folder)["media"])
    tl2 = tl
    assert tl2["clips"][0]["media"] == mm2

def test_tao_anh_khong_can_media(c):
    # Route chạy khi không có media (truyền media="")
    r = c.post(f"/api/du-an/{c.pid}/ai/tao-anh", json={"phien": c.phien, "media": "", "tham_so": {
        "anh_model": "stablediffusionapi/anything-v5",
        "anh_prompt": "một con mèo đen",
        "anh_negative": "xấu",
        "anh_rong": 512,
        "anh_cao": 768,
        "anh_so": 2,
        "anh_steps": 25,
        "anh_guidance": 7.5,
        "anh_seed": 1234
    }})
    assert r.status_code == 200, r.text
    vid = r.json()["viec"]["id"]
    
    # Đợi tác vụ xong
    v = _cho(c, vid, 10)
    assert v["trang_thai"] == "xong", v.get("loi")
    
    # Kiểm tra truyền đúng cờ tới CLI adapter
    args = c.pl.args[-1]
    assert args.get("tao_anh_only") is True
    assert args.get("anh_model") == "stablediffusionapi/anything-v5"
    assert args.get("anh_prompt") == "một con mèo đen"
    assert args.get("anh_negative") == "xấu"
    assert args.get("anh_rong") == 512
    assert args.get("anh_cao") == 768
    assert args.get("anh_so") == 2
    assert args.get("anh_steps") == 25
    assert args.get("anh_guidance") == 7.5
    assert args.get("anh_seed") == 1234
    
    # adapter giả sinh 2 PNG → 2 media loại ảnh
    kq = v["ket_qua"]
    assert len(kq.get("media_moi", [])) == 2
    assert len(kq.get("seeds", [])) == 2
    
    # Kiểm tra file đã lưu thành dạng media trong project
    mids = kq["media_moi"]
    duan = luu_tru.doc_duan(c.folder)
    media_list = duan["media"]
    m1 = [m for m in media_list if m["id"] == mids[0]][0]
    m2 = [m for m in media_list if m["id"] == mids[1]][0]
    assert m1["loai"] == "anh"
    assert m1["file"].endswith(".png")
    assert m2["loai"] == "anh"
    assert m2["file"].endswith(".png")



def test_lenh_that_co_du_co_rieng_tung_loai(tmp_path, monkeypatch):
    """Kiểm LỆNH THẬT gửi adapter (dùng pipeline.build_translate_cmd thật): cờ riêng từng loại không được rơi.
    Chạy thật từng hỏng: tạo ảnh đi nhánh video vì `--tao-anh-only` bị rơi; Whisper model không tới adapter."""
    from orchestrator import pipeline as pl_mod
    from orchestrator.editor import ai_bridge
    monkeypatch.setattr(ai_bridge, "load_global_config", lambda: {}, raising=False)
    folder = str(tmp_path)
    os.makedirs(os.path.join(folder, "media"), exist_ok=True)
    open(os.path.join(folder, "media", "a.mp4"), "wb").write(b"x")
    xay = pl_mod.VideoPipeline.build_translate_cmd
    xay_lenh = lambda job, args, cfg: xay(pl_mod.VideoPipeline.__new__(pl_mod.VideoPipeline), job, args, cfg)
    anh = ai_bridge.dung_lenh(folder, "tao-anh", {}, {"anh_prompt": "mèo", "anh_model": "lykon/dreamshaper-8", "anh_rong": 512,
                                                      "anh_cao": 512, "anh_seed": 0}, {}, xay_lenh, "v1")["cmd"]
    assert "--tao-anh-only" in anh and anh[anh.index("--anh-prompt") + 1] == "mèo"
    assert anh[anh.index("--anh-seed") + 1] == "0", "seed 0 phải giữ nguyên"
    doc = ai_bridge.dung_lenh(folder, "doc-van-ban", {}, {"van_ban": "xin chào", "tts_engine": "edge"}, {}, xay_lenh, "v2")["cmd"]
    assert "--doc-van-ban-only" in doc and os.path.exists(doc[doc.index("--van-ban-file") + 1])
    m = {"id": "m_01", "loai": "video", "file": "media/a.mp4"}
    pd = ai_bridge.dung_lenh(folder, "phu-de", m, {"whisper_model": "medium", "whisper_device": "auto"}, {}, xay_lenh, "v3")["cmd"]
    assert pd[pd.index("--whisper-model") + 1] == "medium" and pd[pd.index("--whisper-device") + 1] == "auto"


def test_doc_van_ban_route_khong_can_media(c):
    """Route /ai/doc-van-ban với media rỗng không được báo "Không có media ''" (chạy thật từng trả 400)."""
    r = c.post(f"/api/du-an/{c.pid}/ai/doc-van-ban", json={"phien": c.phien, "media": "", "tham_so": {"van_ban": "xin chào", "tts_engine": "edge"}})
    assert r.status_code == 200, r.text


def test_minh_hoa(c):
    # Không có key → route từ chối NGAY (400) với lỗi rõ, không xếp việc
    r = c.post(f"/api/du-an/{c.pid}/ai/minh-hoa", json={"phien": c.phien, "media": "m_01", "tham_so": {"cau": [{"t_vao": 1.0, "t_ra": 2.0, "text": "hello"}]}})
    assert r.status_code == 400 and "Cần API key" in r.text, r.text

    # Co key -> pass
    from orchestrator.editor import api as editor_api
    editor_api.load_global_config()["api_keys"]["pexels"] = "test_key"
    r = c.post(f"/api/du-an/{c.pid}/ai/minh-hoa", json={"phien": c.phien, "media": "m_01", "tham_so": {"cau": [{"t_vao": 1.0, "t_ra": 2.0, "text": "hello"}]}})
    assert r.status_code == 200
    vid = r.json()["viec"]["id"]
    v = _cho(c, vid, 10)
    assert v["trang_thai"] == "xong", v.get("loi")
    
    # Kiem tra tra ve 2 doan => 2 media
    kq = v["ket_qua"]
    assert kq.get("so_doan") == 2
    assert len(kq.get("doan")) == 2
    
    # Ap dung ket qua len timeline
    tl = luu_tru.doc_timeline(c.folder)[0]
    tl["clips"] = [{"id": "c1", "media": "m_01", "bat_dau": 5.0, "vao": 0.0, "ra": 10.0, "track": "V1"}]
    import orchestrator.editor.hang_loat as hl
    hl.ap_dung("minh-hoa", tl, v["ket_qua"], "m_01", {}, luu_tru.doc_duan(c.folder)["media"])
    
    # 2 clip minh hoa dc them vao track moi
    assert len(tl["tracks"]) == 5
    assert len(tl["clips"]) == 3
    # Track moi nam tren (id track phai them vao timeline, ma id phai la cua clip minh hoa)
    minh_hoa_clips = [cl for cl in tl["clips"] if cl.get("am_luong") == 0]
    assert len(minh_hoa_clips) == 2
    assert minh_hoa_clips[0]["bat_dau"] == 5.0 + 1.0 # vi t_vao la 1.0, c1 bat_dau la 5.0
    assert minh_hoa_clips[1]["bat_dau"] == 5.0 + 3.0 # vi t_vao la 3.0

def test_gop_cau_minh_hoa():
    from orchestrator.editor.ai_bridge import gop_cau_minh_hoa
    cau = [
        {"t_vao": 0.0, "t_ra": 1.0, "text": "a"},
        {"t_vao": 1.0, "t_ra": 2.0, "text": "b"},
        {"t_vao": 2.0, "t_ra": 3.0, "text": "c"},
        {"t_vao": 3.0, "t_ra": 5.0, "text": "d"}
    ]
    kq = gop_cau_minh_hoa(cau, min_duration=3.0)
    assert len(kq) == 2
    assert kq[0]["t_vao"] == 0.0
    assert kq[0]["t_ra"] == 3.0
    assert kq[0]["text"] == "a b c"
    assert kq[1]["t_vao"] == 3.0
    assert kq[1]["t_ra"] == 5.0
    assert kq[1]["text"] == "d"












def test_minh_hoa_khong_key_bao_ro():
    """Không có API key nguồn đã chọn → lỗi tiếng Việt rõ ràng, không xếp việc (chạy thật từng in cả khối config)."""
    from orchestrator.editor import ai_bridge
    import tempfile
    goc = tempfile.mkdtemp()
    os.makedirs(os.path.join(goc, "media"))
    open(os.path.join(goc, "media", "a.mp4"), "wb").write(b"x")
    with pytest.raises(ValueError, match="Cần API key Pexels"):
        ai_bridge.dung_lenh(goc, "minh-hoa", {"id": "m", "loai": "video", "file": "media/a.mp4"},
                            {"cau": [{"t_vao": 0, "t_ra": 4, "text": "a"}], "minh_hoa_nguon": "pexels"},
                            {"api_keys": {}}, lambda j, a, g: [], "v")


def test_tham_so_edge_thu_cong():
    import importlib.util
    import sys
    # Import trực tiếp adapter_autosub_cli
    spec = importlib.util.spec_from_file_location("adapter_autosub_cli", "AIVoice/apps/MediaComposer/adapter_autosub_cli.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["adapter_autosub_cli"] = module
    spec.loader.exec_module(module)
    
    # Test tốc độ
    assert module.tinh_tham_so_edge(1.2, 0) == {"rate": "+20%"}
    assert module.tinh_tham_so_edge(0.8, 0) == {"rate": "-20%"}
    
    # Test cao độ
    assert module.tinh_tham_so_edge(1.0, 2) == {"pitch": "+50Hz"}
    assert module.tinh_tham_so_edge(1.0, -1) == {"pitch": "-25Hz"}
    
    # Test cả hai
    assert module.tinh_tham_so_edge(1.5, 4) == {"rate": "+50%", "pitch": "+100Hz"}

def test_lenh_that_co_du_co_rieng_tung_loai_co_tts_speed_pitch(tmp_path):
    from orchestrator.editor import ai_bridge
    import os
    os.makedirs(os.path.join(str(tmp_path), "media"))
    open(os.path.join(str(tmp_path), "media", "a.mp4"), "wb").write(b"x")
    
    from orchestrator import pipeline as pl_mod
    xay = pl_mod.VideoPipeline.build_translate_cmd
    xay_lenh = lambda job, args, cfg: xay(pl_mod.VideoPipeline.__new__(pl_mod.VideoPipeline), job, args, cfg)
    
    # Lồng tiếng có speed / pitch
    res_lt = ai_bridge.dung_lenh(str(tmp_path), "long-tieng", {"id": "m", "loai": "video", "file": "media/a.mp4"},
        {"cau": [{"t_vao": 0, "t_ra": 2, "text": "a"}], "tts_engine": "edge", "tts_voice": "v", "tts_speed": 1.2, "tts_pitch": 2},
        {"translate": {"target_lang": "vi"}}, xay_lenh, "v_lt")
        
    assert "--tts-speed" in res_lt["cmd"]
    assert res_lt["cmd"][res_lt["cmd"].index("--tts-speed") + 1] == "1.2"
    assert "--tts-pitch" in res_lt["cmd"]
    assert res_lt["cmd"][res_lt["cmd"].index("--tts-pitch") + 1] == "2"

    # Đọc văn bản có speed / pitch
    res_dv = ai_bridge.dung_lenh(str(tmp_path), "doc-van-ban", None,
        {"van_ban": "xin chào", "tts_engine": "edge", "tts_voice": "v", "tts_speed": 0.8, "tts_pitch": -1},
        {}, xay_lenh, "v_dv")
        
    assert "--tts-speed" in res_dv["cmd"]
    assert res_dv["cmd"][res_dv["cmd"].index("--tts-speed") + 1] == "0.8"
    assert "--tts-pitch" in res_dv["cmd"]
    assert res_dv["cmd"][res_dv["cmd"].index("--tts-pitch") + 1] == "-1"
