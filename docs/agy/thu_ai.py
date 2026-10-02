"""Chạy một việc AI THẬT qua API editor. Dùng: python thu_ai.py <loai> '<tham_so json>'
vd: thu_ai.py ocr '{"source_lang":"Vietnamese","vung_px":{"x":22,"y":1459,"w":1037,"h":192}}'
    thu_ai.py tach-giong '{}'   |   thu_ai.py lam-net '{}'"""
import json, sys, time, urllib.request

B, PID = "http://localhost:8110", "07ebfddc"
MEDIA = sys.argv[3] if len(sys.argv) > 3 else "m_01"   # tham số 3 (tuỳ chọn): mã media


def goi(path, body=None):
    req = urllib.request.Request(B + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


mo = goi(f"/api/du-an/{PID}")
phien = mo["khoa"]["phien"]
try:
    ts = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    v = goi(f"/api/du-an/{PID}/ai/{sys.argv[1]}", {"phien": phien, "media": MEDIA, "tham_so": ts})["viec"]
    t0 = time.time()
    while True:
        time.sleep(5)
        x = [y for y in goi("/api/hang-doi")["gpu"] if y["id"] == v["id"]][0]
        if x["trang_thai"] in ("xong", "loi", "bi_ngat", "da_huy"):
            break
    print(x["trang_thai"], round(time.time() - t0, 1), "s |", (x.get("loi") or "")[-800:])
    kq = x.get("ket_qua") or {}
    for c in (kq.get("cau") or [])[:40]:
        print(f'{c.get("t_vao"):>7} {c.get("t_ra"):>7}  {c.get("text")}')
    print(json.dumps({k: w for k, w in kq.items() if k != "cau"}, ensure_ascii=False)[:600])
finally:
    goi(f"/api/du-an/{PID}/dong", {"phien": phien})
