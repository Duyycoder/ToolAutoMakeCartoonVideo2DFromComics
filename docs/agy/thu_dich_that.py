"""Chạy DỊCH THẬT qua API editor (server thử 8110) trên dự án thử AI, in báo cáo lọt từ.

Dùng: python thu_dich_that.py vi-en | zh-vi
"""
import json, sys, time, urllib.request

B = "http://localhost:8110"
PID = "07ebfddc"


def goi(path, body=None, method=None):
    req = urllib.request.Request(B + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method=method or ("POST" if body is not None else "GET"))
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


mo = goi(f"/api/du-an/{PID}")
phien = mo["khoa"]["phien"]
try:
    if sys.argv[1] == "vi-en":
        cau = [c for c in mo["timeline"]["clips"] if c.get("loai") == "phu_de" and (c.get("text") or "").strip()]
        ts = {"source_lang": "Vietnamese", "target_lang": "English",
              "cau": [{"id": c["id"], "t_vao": c["t_vao"], "t_ra": c["t_ra"], "text": c["text"], "text_goc": c.get("text_goc", "")} for c in cau],
              "ids": [c["id"] for c in cau]}
    else:
        zh = ["师兄，你这一剑已经到了化境，整个宗门没人能接得住。", "他冷笑一声：“区区筑基期，也敢在我面前放肆？”",
              "林凡拿出储物戒指，里面装满了灵石和丹药。", "这就是传说中的九转金丹吗？", "长老们纷纷点头，认为此子将来必成大器。",
              "天道宗的圣女缓缓走来，引得众人侧目。", "你以为凭你元婴期的修为，就能挡住我的万剑归宗？", "滚！"]
        ts = {"source_lang": "Chinese", "target_lang": "Vietnamese",
              "thuat_ngu": {"筑基期": "Trúc Cơ kỳ", "林凡": "Lâm Phàm", "灵石": "linh thạch", "元婴期": "Nguyên Anh kỳ", "天道宗": "Thiên Đạo Tông"},
              "cau": [{"id": f"z{i}", "t_vao": i, "t_ra": i + 1, "text": t, "text_goc": t} for i, t in enumerate(zh)],
              "ids": [f"z{i}" for i in range(len(zh))]}
    v = goi(f"/api/du-an/{PID}/ai/dich", {"phien": phien, "media": "m_01", "tham_so": ts})["viec"]
    t0 = time.time()
    while True:
        time.sleep(2)
        x = [y for y in goi("/api/hang-doi")["gpu"] if y["id"] == v["id"]][0]
        if x["trang_thai"] in ("xong", "loi", "bi_ngat", "da_huy"):
            break
    kq = x.get("ket_qua") or {}
    print("trang_thai:", x["trang_thai"], "| loi:", x.get("loi"), "| thoi_gian:", round(time.time() - t0, 1), "s")
    print("bao_cao:", json.dumps({k: v for k, v in (kq.get("bao_cao") or {}).items() if k != "loi_lot"}, ensure_ascii=False))
    for l in (kq.get("bao_cao") or {}).get("loi_lot") or []:
        print("  LỌT:", json.dumps(l, ensure_ascii=False))
    goc = {c["id"]: c["text"] for c in ts["cau"]}
    for c in kq.get("cau") or []:
        print(f"  {goc.get(c.get('id'), '?')}\n    → {c.get('text')}")
finally:
    goi(f"/api/du-an/{PID}/dong", {"phien": phien})
