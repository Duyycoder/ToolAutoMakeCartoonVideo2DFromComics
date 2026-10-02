"""Chạy LỒNG TIẾNG THẬT qua API editor. Dùng: python thu_long_tieng.py <engine> <giong>"""
import json, sys, time, urllib.request

B, PID = "http://localhost:8110", "07ebfddc"


def goi(path, body=None):
    req = urllib.request.Request(B + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


mo = goi(f"/api/du-an/{PID}")
phien = mo["khoa"]["phien"]
try:
    cau = [c for c in mo["timeline"]["clips"] if c.get("loai") == "phu_de" and (c.get("text") or "").strip()][:8]
    ts = {"tts_engine": sys.argv[1], "tts_voice": sys.argv[2], "ducking_ratio": 90, "auto_clone": sys.argv[1] == "clone",
          "target_lang": "Vietnamese", "cau": [{"t_vao": c["t_vao"], "t_ra": c["t_ra"], "text": c["text"]} for c in cau],
          "ids": [c["id"] for c in cau]}
    v = goi(f"/api/du-an/{PID}/ai/long-tieng", {"phien": phien, "media": "m_01", "tham_so": ts})["viec"]
    t0 = time.time()
    while True:
        time.sleep(3)
        x = [y for y in goi("/api/hang-doi")["gpu"] if y["id"] == v["id"]][0]
        if x["trang_thai"] in ("xong", "loi", "bi_ngat", "da_huy"):
            break
    print(x["trang_thai"], round(time.time() - t0, 1), "s |", (x.get("loi") or "")[-600:])
    print(json.dumps(x.get("ket_qua"), ensure_ascii=False)[:400])
finally:
    goi(f"/api/du-an/{PID}/dong", {"phien": phien})
