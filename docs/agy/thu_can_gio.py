"""Chạy THẬT Tự căn giờ: lấy câu S1 của m_01, cố ý dời +1.5 s, gửi căn giờ, so kết quả với giờ gốc (Whisper đã đúng giờ).
Dùng: python thu_can_gio.py   (server 8110, dự án thử 07ebfddc, không có tab editor nào mở dự án)"""
import json, time, urllib.request

B, PID, MEDIA, LECH = "http://localhost:8110", "07ebfddc", "m_01", 1.5


def goi(path, body=None):
    req = urllib.request.Request(B + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


mo = goi(f"/api/du-an/{PID}")
phien = mo["khoa"]["phien"]
try:
    goc = [c for c in mo["timeline"]["clips"] if c.get("loai") == "phu_de" and c.get("tu_media") == MEDIA and (c.get("text") or "").strip()]
    goc.sort(key=lambda c: c["t_vao"])
    cau = [{"id": c["id"], "t_vao": c["t_vao"] + LECH, "t_ra": c["t_ra"] + LECH, "text": c["text"], "text_goc": c.get("text_goc") or c["text"]} for c in goc]
    ts = {"source_lang": "Vietnamese", "cau": cau, "ids": [c["id"] for c in cau]}
    v = goi(f"/api/du-an/{PID}/ai/can-gio", {"phien": phien, "media": MEDIA, "tham_so": ts})["viec"]
    t0 = time.time()
    while True:
        time.sleep(3)
        x = [y for y in goi("/api/hang-doi")["gpu"] if y["id"] == v["id"]][0]
        if x["trang_thai"] in ("xong", "loi", "bi_ngat", "da_huy"):
            break
    print(x["trang_thai"], round(time.time() - t0, 1), "s |", (x.get("loi") or "")[-600:])
    kq = x.get("ket_qua") or {}
    moi = {c["id"]: c for c in kq.get("cau") or []}
    lech = []
    for c in goc:
        m = moi.get(c["id"])
        if m:
            lech.append(abs(m["t_vao"] - c["t_vao"]))
            print(f'{c["t_vao"]:7.2f} -> gui {c["t_vao"] + LECH:7.2f} -> can {m["t_vao"]:7.2f}  {c["text"][:40]}')
    print("so_cau", kq.get("so_cau"), "khong_khop", kq.get("khong_khop"))
    if lech:
        print(f"lech trung binh sau can: {sum(lech) / len(lech):.2f} s (truoc can: {LECH} s)")
finally:
    goi(f"/api/du-an/{PID}/dong", {"phien": phien})
