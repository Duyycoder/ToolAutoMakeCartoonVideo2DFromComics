"""Chạy THẬT "Video minh hoạ theo phụ đề" trên 4 câu đầu của m_01 (dự án thử 07ebfddc, server 8110).
Dùng: python thu_minh_hoa.py [pexels|pixabay|coverr]  — không có API key thì phải báo lỗi RÕ."""
import json, sys, time, urllib.request as u

B, P = "http://localhost:8110", "07ebfddc"


def goi(path, body=None):
    req = u.Request(B + path, json.dumps(body).encode() if body is not None else None,
                    {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    try:
        with u.urlopen(req, timeout=60) as r:
            return json.load(r)
    except u.HTTPError as e:
        return {"HTTP": e.code, "detail": e.read().decode()[:300]}


o = goi(f"/api/du-an/{P}")
ph = o["khoa"]["phien"]
try:
    cau = [{"t_vao": c["t_vao"], "t_ra": c["t_ra"], "text": c["text"]} for c in o["timeline"]["clips"]
           if c.get("loai") == "phu_de" and c.get("tu_media") == "m_01"][:4]
    r = goi(f"/api/du-an/{P}/ai/minh-hoa", {"phien": ph, "media": "m_01",
                                            "tham_so": {"cau": cau, "minh_hoa_nguon": sys.argv[1] if len(sys.argv) > 1 else "pexels"}})
    if "viec" not in r:
        print(r)
    else:
        for _ in range(100):
            time.sleep(3)
            x = [y for y in goi("/api/hang-doi")["gpu"] if y["id"] == r["viec"]["id"]][0]
            if x["trang_thai"] in ("xong", "loi", "bi_ngat", "da_huy"):
                print(x["trang_thai"], "|", (x.get("loi") or "")[-400:])
                print(json.dumps(x.get("ket_qua"), ensure_ascii=False)[:600])
                break
finally:
    goi(f"/api/du-an/{P}/dong", {"phien": ph})
