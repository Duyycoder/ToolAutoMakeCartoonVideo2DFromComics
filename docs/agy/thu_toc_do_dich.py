"""Đo tốc độ dịch THẬT: N câu đầu của một media (mặc định dự án test AI 535dbff5, Anh→Việt). KHÔNG áp dụng vào timeline.
Dùng: python thu_toc_do_dich.py [so_cau=200] [pid=535dbff5]"""
import datetime as d, json, sys, time, urllib.request as u

B = "http://localhost:8110"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
PID = sys.argv[2] if len(sys.argv) > 2 else "535dbff5"


def goi(path, body=None):
    req = u.Request(B + path, json.dumps(body).encode() if body is not None else None,
                    {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with u.urlopen(req, timeout=120) as r:
        return json.load(r)


o = goi(f"/api/du-an/{PID}")
ph = o["khoa"]["phien"]
try:
    pd = sorted([c for c in o["timeline"]["clips"] if c.get("loai") == "phu_de" and (c.get("text") or "").strip()],
                key=lambda c: c.get("t_vao", 0))
    mid = pd[0]["tu_media"]
    cau = [{"id": c["id"], "t_vao": c["t_vao"], "t_ra": c["t_ra"], "text": c.get("text_goc") or c["text"], "text_goc": ""} for c in pd[:N]]
    ts = {"cau": cau, "ids": [c["id"] for c in cau], "source_lang": "English", "target_lang": "Vietnamese", "dich_lai_tat_ca": True}
    v = goi(f"/api/du-an/{PID}/ai/dich", {"phien": ph, "media": mid, "tham_so": ts})["viec"]
    while True:
        time.sleep(3)
        x = [y for y in goi("/api/hang-doi")["gpu"] if y["id"] == v["id"]][0]
        if x["trang_thai"] in ("xong", "loi", "bi_ngat", "da_huy"):
            break
    f = lambda s: d.datetime.fromisoformat(s)
    giay = (f(x["xong_luc"]) - f(x["bat_dau"])).total_seconds()
    b = (x.get("ket_qua") or {}).get("bao_cao") or {}
    print(f"{x['trang_thai']} | {len(cau)} câu | {giay:.0f} s | {giay / len(cau):.2f} s/câu | gọi model {b.get('so_lan_goi_model')} lần | "
          f"lọt {b.get('ti_le_lot_cuoi')} | dự phòng {b.get('model_du_phong_da_dung')} | {(x.get('loi') or '')[-200:]}")
    for c in (x.get("ket_qua") or {}).get("cau", [])[:6]:
        print("  ", c.get("text_goc", "")[:50], "→", c.get("text", "")[:60])
finally:
    goi(f"/api/du-an/{PID}/dong", {"phien": ph})
