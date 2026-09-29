import json

import os

import pytest

from orchestrator.editor import dich, hang_doi, hang_loat, luu_tru



def test_do_lot_tu_cjk():

    # Hán lọt

    tn = {}

    assert dich.do_lot_tu("筑基期", "Trúc Cơ kỳ", "Chinese", "Vietnamese", tn)["lot"] == []

    lot = dich.do_lot_tu("林凡 筑基", "Lâm Phàm 筑基", "Chinese", "Vietnamese", tn)

    assert len(lot["lot"]) > 0

    assert lot["lot"][0] == "筑" or "筑" in lot["lot"]



def test_do_lot_tu_latin():

    tn = {"TikTok": "TikTok", "OK": "OK"}

    # Lọt nguyên câu

    assert len(dich.do_lot_tu("hello", "hello", "English", "Vietnamese", tn)["lot"]) > 0

    # Câu rỗng hoặc giữ nguyên

    assert dich.do_lot_tu("hello", "", "English", "Vietnamese", tn)["lot"] == ["TOÀN_BỘ"]

    # Tên riêng

    assert dich.do_lot_tu("I love New York", "Tôi yêu New York", "English", "Vietnamese", tn)["lot"] == []

    # Từ hợp lệ của tiếng Việt

    assert dich.do_lot_tu("He is a tam", "Anh ấy là một tam", "English", "Vietnamese", tn)["lot"] == []

    # Từ giữ nguyên

    assert dich.do_lot_tu("Use TikTok now", "Dùng TikTok ngay", "English", "Vietnamese", tn)["lot"] == []

    

    # Lọt từ tiếng Anh vào bản dịch tiếng Việt

    lot1 = dich.do_lot_tu("I love psychology", "Tôi yêu psychology", "English", "Vietnamese", tn)["lot"]

    assert "psychology" in [l.lower() for l in lot1]

    

    # Từ "the" bị coi là lọt nếu nguồn tiếng Anh (trùng với chữ "the" tiếng Việt)

    lot2 = dich.do_lot_tu("The dog", "The chó", "English", "Vietnamese", tn)["lot"]

    assert "The" in lot2

    

    # "an" không bị bắt lọt vì nằm trong OVERLAPPING_VN_SYLLABLES

    lot3 = dich.do_lot_tu("an apple", "một an apple", "English", "Vietnamese", tn)["lot"]

    assert "an" not in [l.lower() for l in lot3]



    # Đích tiếng Anh: Từ tiếng Việt (không dấu) lọt

    lot4 = dich.do_lot_tu("Tôi yêu anh", "I love anh", "Vietnamese", "English", tn)["lot"]

    assert "anh" in [l.lower() for l in lot4]



def test_lam_sach_ban_dich():

    assert dich.lam_sach_ban_dich("Bản dịch: Xin chào", 0) == "Xin chào"

    assert dich.lam_sach_ban_dich('Translation: "Xin chào"', 0) == "Xin chào"

    assert dich.lam_sach_ban_dich("Hello\nWorld", 1) == "Hello\nWorld"



@pytest.fixture

def fake_ollama(monkeypatch):

    calls = []

    def mock_post(url, json, timeout):

        calls.append(json)

        class Resp:

            def raise_for_status(self): pass

            def json(self):

                # Fake response based on prompt

                prompt = json["prompt"]

                if "success" in prompt:

                    return {"response": "thành công " + prompt[-1]}

                if "thiếu" in prompt:

                    if len(calls) == 1: return {"response": "bản dịch không có thuật ngữ"}

                    return {"response": "bản dịch có thuật ngữ thiếu Lâm Phàm"}

                if "ngữ cảnh" in prompt:

                    return {"response": "câu trước đó. Xin chào"}

                if "林凡 筑基" in prompt:

                    if "Dùng các thuật ngữ sau" in prompt:

                        return {"response": "Lâm Phàm Trúc Cơ"}

                    if len(calls) == 1:

                        return {"response": "Lâm Phàm Trúc Cơ 筑基"}

                    return {"response": "Lâm Phàm Trúc Cơ"}

                if prompt.endswith("筑") or prompt.endswith("基"):

                    return {"response": "Trúc"}

                return {"response": "dịch xong"}

        return Resp()

    monkeypatch.setattr(dich.requests, "post", mock_post)

    return calls



def test_dich_vong_sua(fake_ollama, tmp_path, monkeypatch):

    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {"林凡": "Lâm Phàm"})

    

    class FakeViec:

        def __init__(self):

            self.huy_event = hang_doi.threading.Event()

            self.ket_qua = None

    

    ctx = hang_doi.NguCanh(FakeViec(), None)

    ctx.bao = lambda *a, **k: None

    

    # Ca 1: Dịch sạch ngay

    tham_so = {"cau": [{"id": "1", "text_goc": "success", "text": "success"}], "ids": ["1"], "source_lang": "English", "target_lang": "Vietnamese"}

    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    assert kq["cau"][0]["text"] == "thành công s"

    assert "options" in fake_ollama[0]

    assert fake_ollama[0]["options"]["temperature"] == 0.1

    assert "\\n" not in fake_ollama[0]["prompt"]

    assert "\n\nsuccess" in fake_ollama[0]["prompt"]

    

    # Ca 2: Lọt Hán lần đầu -> sửa bước a

    fake_ollama.clear()

    tham_so = {"cau": [{"id": "1", "text_goc": "林凡 筑基", "text": "林凡 筑基"}], "ids": ["1"]}

    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    assert kq["cau"][0]["text"] == "Lâm Phàm Trúc Cơ"

    assert len(fake_ollama) == 4

    

    # Ca 3: Thiếu thuật ngữ

    fake_ollama.clear()

    tham_so = {"cau": [{"id": "1", "text_goc": "thiếu Lâm Phàm", "text": ""}], "ids": ["1"], "thuat_ngu": {"thiếu": "thiếu", "Lâm Phàm": "Lâm Phàm"}}

    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    assert len(fake_ollama) == 2

    assert "Lâm Phàm" in kq["cau"][0]["text"]



def test_dich_loi_cuoi(fake_ollama, tmp_path, monkeypatch):

    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})

    class FakeViec:

        def __init__(self):

            self.huy_event = hang_doi.threading.Event()

            self.ket_qua = None

    ctx = hang_doi.NguCanh(FakeViec(), None)

    ctx.bao = lambda *a, **k: None

    

    def mock_post_fail(*a, **k):

        class Resp:

            def raise_for_status(self): pass

            def json(self): return {"response": "hello 筑基"}

        return Resp()

    monkeypatch.setattr(dich.requests, "post", mock_post_fail)

    

    tham_so = {"cau": [{"id": "1", "text_goc": "hello 筑基", "text": ""}], "ids": ["1"]}

    with pytest.raises(RuntimeError):

        dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

        

    # Check that ket_qua is set

    assert ctx.viec.ket_qua["bao_cao"]["ti_le_lot_cuoi"] > 0

    assert len(ctx.viec.ket_qua["bao_cao"]["loi_lot"]) == 1



def test_cau_dich_tay_bo_qua(fake_ollama, tmp_path, monkeypatch):

    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})

    class FakeViec:

        def __init__(self):

            self.huy_event = hang_doi.threading.Event()

            self.ket_qua = None

    ctx = hang_doi.NguCanh(FakeViec(), None)

    ctx.bao = lambda *a, **k: None

    

    tham_so = {"cau": [{"id": "1", "text_goc": "nguồn", "text": "đã dịch tay"}], "ids": ["1"]}

    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    assert len(fake_ollama) == 0 # Không gọi model

    assert kq["cau"][0]["text"] == "đã dịch tay"

    

    # Dịch lại tất cả

    tham_so = {"cau": [{"id": "1", "text_goc": "nguồn", "text": "đã dịch tay"}], "ids": ["1"], "dich_lai_tat_ca": True}

    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    assert len(fake_ollama) > 0



def test_api_thuat_ngu(tmp_path, monkeypatch):

    from orchestrator.editor import api

    from fastapi.testclient import TestClient

    from fastapi import FastAPI

    import json

    

    app = FastAPI()

    app.include_router(api.tao_router(None, None))

    client = TestClient(app)

    client.ws = str(tmp_path)

    from orchestrator.editor import workspace; monkeypatch.setattr(workspace, "quet", lambda ws, l: ([], {"123": client.ws}))

    

    client.put("/api/du-an/123/thuat-ngu", json={"text": "Lâm Phàm = Lâm Phàm\nTrúc Cơ = Trúc Cơ kỳ"})

    

    r = client.get("/api/du-an/123/thuat-ngu")

    assert r.status_code == 200

    assert "Lâm Phàm = Lâm Phàm" in r.json()["text"]

    assert "Trúc Cơ = Trúc Cơ kỳ" in r.json()["text"]



def test_kiem_do_dai():

    assert dich.kiem_do_dai("Thứ ra không mới", "I thought that relationships between men and women were actually just a form of exchange where one person gives something", "Vietnamese", "English") == True

    assert dich.kiem_do_dai("quan hệ với phụ nữ", "Psychology is also known as the theory of sexual psychology. It states that men actually always have to pretend", "Vietnamese", "English") == True

    assert dich.kiem_do_dai("Cô gái", "The girl", "Vietnamese", "English") == False

    assert dich.kiem_do_dai("滚！", "Cút đi!", "Chinese", "Vietnamese") == False



def test_do_lot_tu_tap_tu_nguon():

    tn = {}

    lot = dich.do_lot_tu("So according to the principles", "principles of kinh theory", "Vietnamese", "English", tn, {"so", "according", "to", "the", "principles", "of", "kinh", "theory"})["lot"]

    assert "kinh" in [l.lower() for l in lot]



def test_ngu_canh_prompt(fake_ollama, tmp_path, monkeypatch):

    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})

    class FakeViec:

        def __init__(self):

            self.huy_event = hang_doi.threading.Event()

            self.ket_qua = None

    ctx = hang_doi.NguCanh(FakeViec(), None)

    ctx.bao = lambda *a, **k: None

    

    # Kiểm luồng dịch TỪNG CÂU (câu sau không chứa câu trước) → tắt gộp lô cho rõ ý.
    monkeypatch.setattr(dich, "load_global_config", lambda: {"translate": {"so_cau_moi_lan": 1}})
    tham_so = {"cau": [{"id": "1", "text_goc": "success 1", "text": "success 1"}, {"id": "2", "text_goc": "success 2", "text": "success 2"}], "ids": ["1", "2"], "source_lang": "Chinese", "target_lang": "Vietnamese"}

    dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    # Chạy song song → thứ tự lần gọi không cố định: tìm prompt của câu 2 theo nội dung.
    p2 = [c["prompt"] for c in fake_ollama if "success 2" in c["prompt"]]
    assert p2 and all("success 1" not in p for p in p2)

    fake_ollama.clear()

    # Tiếng Trung + ngữ cảnh: prompt câu 2 có câu GỐC câu 1 (mẫu ngữ cảnh chính thức của hy-mt2).
    tham_so = {"cau": [{"id": "1", "text_goc": "success 1", "text": "success 1"}, {"id": "2", "text_goc": "success 2", "text": "success 2"}], "ids": ["1", "2"], "source_lang": "Chinese", "target_lang": "Vietnamese", "ngu_canh": True}

    dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    p2 = [c["prompt"] for c in fake_ollama if c["prompt"].endswith("success 2")]
    assert p2 and "success 1" in p2[0]

    fake_ollama.clear()

    # Tiếng Anh: hy-mt2 không có mẫu prompt ngữ cảnh → không đưa câu trước vào.
    tham_so = {"cau": [{"id": "1", "text_goc": "success 1", "text": "success 1"}, {"id": "2", "text_goc": "success 2", "text": "success 2"}], "ids": ["1", "2"], "source_lang": "English", "target_lang": "Vietnamese", "ngu_canh": True}

    dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, tham_so)

    p2 = [c["prompt"] for c in fake_ollama if "success 2" in c["prompt"]]
    assert p2 and all("success 1" not in p for p in p2)


def test_thuat_ngu_nguon(tmp_path, monkeypatch):
    from orchestrator.editor import api
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    import json
    import os
    
    # Create fake storage
    truyen_dir = tmp_path / "storage" / "truyen"
    truyen_dir.mkdir(parents=True)
    t1 = truyen_dir / "Truyen1" / "raw"
    t1.mkdir(parents=True)
    with open(t1 / "glossary.json", "w", encoding="utf-8") as f:
        json.dump({"A": "B", "C": "D"}, f)
        
    t2 = truyen_dir / "Truyen2" / "raw"
    t2.mkdir(parents=True)
    with open(t2 / "glossary.json", "w", encoding="utf-8") as f:
        json.dump({"E": "F"}, f)
        
    app = FastAPI()
    router = api.tao_router(None, None)
    router.storage_truyen_dir = str(truyen_dir)
    app.include_router(router)
    client = TestClient(app)
    
    # Monkeypatch workspace
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    dung_chung = ws_dir / "_dung_chung"
    dung_chung.mkdir()
    with open(dung_chung / "thuat_ngu.json", "w", encoding="utf-8") as f:
        json.dump({"X": "Y"}, f)
        
    monkeypatch.setattr(api, "_cfg_editor", lambda: {"workspace": str(ws_dir)})
    
    r = client.get("/api/thuat-ngu/nguon")
    assert r.status_code == 200
    data = r.json()["nguon"]
    assert len(data) == 3
    
    t1_res = next(x for x in data if x["id"] == "truyen_Truyen1")
    assert t1_res["ten"] == "Truyen1"
    assert t1_res["so_muc"] == 2
    assert t1_res["data"]["A"] == "B"
    
    t2_res = next(x for x in data if x["id"] == "truyen_Truyen2")
    assert t2_res["so_muc"] == 1
    
    dc_res = next(x for x in data if x["id"] == "dung_chung")
    assert dc_res["so_muc"] == 1
    assert dc_res["data"]["X"] == "Y"

def test_lot_tu_bo_dau():
    tn = {}
    nguon = "Thế nên đàn giải là đàn ông không thích môn truyện"
    ban_dich = 'So, a "dan gi" is a man who doesn’t like stories at all.'
    
    # English dest -> not Vietnamese
    res = dich.do_lot_tu(nguon, ban_dich, "Vietnamese", "English", tn)
    lot = [x.lower() for x in res["lot"]]
    assert "dan" in lot
    assert "gi" in lot

def test_lot_tu_khong_bat():
    tn = {}
    nguon = "Dan đi học"
    ban_dich = "Dan is here"
    res = dich.do_lot_tu(nguon, ban_dich, "Vietnamese", "English", tn)
    lot = [x.lower() for x in res["lot"]]
    assert "dan" not in lot


def test_chu_han_lot_vao_ban_dich_tieng_anh():
    """Chạy thật vi→en: 'Therefore, the term "解" refers to…' — chữ Hán trong bản dịch tiếng Anh phải bị bắt."""
    assert dich.chu_la_trong_dich('Therefore, the term "解" refers to "文艺".', "English") == ["解", "文艺"]
    assert dich.chu_la_trong_dich("Xin chào các bạn", "Vietnamese") == []
    assert dich.chu_la_trong_dich("你好", "Chinese") == []          # đích là tiếng Trung thì chữ Hán là đúng



def test_dich_gop_lo_tach_theo_so_dong(tmp_path, monkeypatch):
    """Gộp nhiều câu một lần gọi: tách đúng theo số dòng; lô lệch số dòng → rơi xuống dịch từng câu (không mất câu)."""
    goi = []

    def post(url, json, timeout):
        goi.append(json["prompt"])
        class R:
            def raise_for_status(self): pass
            def json(self):
                p = json["prompt"]
                if "numbered line" in p:
                    so = [ln.split(".", 1)[0] for ln in p.splitlines() if ln[:1].isdigit()]
                    if "hỏng" in p:
                        return {"response": "1. chỉ một dòng"}                       # lệch số dòng
                    return {"response": "\n".join(f"{k}. câu {k} đã dịch" for k in so)}
                return {"response": "dịch riêng"}
        return R()

    monkeypatch.setattr(dich.requests, "post", post)
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    monkeypatch.setattr(dich, "load_global_config", lambda: {"translate": {"so_cau_moi_lan": 3, "so_cau_song_song": 1}})

    class FakeViec:
        def __init__(self):
            self.huy_event = hang_doi.threading.Event()
            self.ket_qua = None
    ctx = hang_doi.NguCanh(FakeViec(), None)
    ctx.bao = lambda *a, **k: None
    cau = [{"id": str(k), "text_goc": f"hello {k}", "text": f"hello {k}"} for k in range(1, 4)]
    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, {"cau": cau, "ids": [c["id"] for c in cau],
                                                              "source_lang": "English", "target_lang": "Vietnamese"})
    assert [c["text"] for c in kq["cau"]] == ["câu 1 đã dịch", "câu 2 đã dịch", "câu 3 đã dịch"]
    assert len(goi) == 1, "3 câu phải đi trong MỘT lần gọi"

    goi.clear()
    cau = [{"id": str(k), "text_goc": f"hỏng {k}", "text": f"hỏng {k}"} for k in range(1, 4)]
    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, {"cau": cau, "ids": [c["id"] for c in cau],
                                                              "source_lang": "English", "target_lang": "Vietnamese"})
    assert [c["text"] for c in kq["cau"]] == ["dịch riêng"] * 3, "lô lệch số dòng phải dịch lại từng câu"
    assert len(goi) == 4

    # Bật ngữ cảnh VẪN gộp lô (trước 29/09 ép từng câu, tuần tự → 1925 câu > 1,5 giờ).
    goi.clear()
    cau = [{"id": str(k), "text_goc": f"hello {k}", "text": f"hello {k}"} for k in range(1, 4)]
    kq = dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, {"cau": cau, "ids": [c["id"] for c in cau], "ngu_canh": True,
                                                              "source_lang": "English", "target_lang": "Vietnamese"})
    assert [c["text"] for c in kq["cau"]] == ["câu 1 đã dịch", "câu 2 đã dịch", "câu 3 đã dịch"]
    assert len(goi) == 1


def test_dich_huy_giua_chung_giu_cau_da_dich(tmp_path, monkeypatch):
    """Huỷ giữa chừng: các câu đã dịch đạt nằm lại trong viec.ket_qua (dang_do) để bảng AI cho áp dụng."""
    class FakeViec:
        def __init__(self):
            self.huy_event = hang_doi.threading.Event()
            self.ket_qua = None
    viec = FakeViec()

    def post(url, json, timeout):
        viec.huy_event.set()                      # người dùng bấm Huỷ khi lô đầu đang chạy
        class R:
            def raise_for_status(self): pass
            def json(self):
                so = [ln.split(".", 1)[0] for ln in json["prompt"].splitlines() if ln[:1].isdigit()]
                return {"response": "\n".join(f"{k}. câu {k} đã dịch" for k in so)}
        return R()

    monkeypatch.setattr(dich.requests, "post", post)
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    monkeypatch.setattr(dich, "load_global_config", lambda: {"translate": {"so_cau_moi_lan": 2, "so_cau_song_song": 1}})
    ctx = hang_doi.NguCanh(viec, None)
    ctx.bao = lambda *a, **k: None
    cau = [{"id": f"c{k}", "text_goc": f"hello {k}", "text": f"hello {k}"} for k in range(1, 5)]
    with pytest.raises(hang_doi.DaHuy):
        dich.dich(ctx, str(tmp_path), "dich", {"id": "m1"}, {"cau": cau, "ids": [c["id"] for c in cau],
                                                             "source_lang": "English", "target_lang": "Vietnamese"})
    kq = viec.ket_qua
    assert kq["dang_do"] and kq["tong_cau"] == 4
    assert kq["ids"] == ["c1", "c2"] and [c["text"] for c in kq["cau"]] == ["câu 1 đã dịch", "câu 2 đã dịch"]

def test_lot_tu_ten_rieng_that_29_09():
    """Ví dụ THẬT từ bảng AI 29/09. Danh sách lọt giữ nguyên hoa/thường → so chữ thường (assert 'skeppy' not in lot luôn đúng)."""
    from orchestrator.editor.dich import do_lot_tu
    cac_cau = ["Bob", "Skeppy's behind me", "Fernando", "Beverly like I'm kind of being camped", "Francis probably low here",
               "It's always an opi loot video with Bob", "The server is so glitched", "that sounds like scabby", "We're like homeless"]
    # dựng tập tên viết hoa GIỮA câu như dich() làm
    viet_hoa = {w.strip(".,!?'s").lower() for c in cac_cau for i, w in enumerate(c.split()) if i > 0 and w[:1].isupper()}
    lot = lambda n, d: [x.lower() for x in do_lot_tu(n, d, "English", "Vietnamese", {}, None, viet_hoa)["lot"]]
    assert lot("Bob", "Bob") == [], "câu chỉ có 1 tên riêng không phải TOÀN_BỘ"
    assert lot("Skeppy's behind me", "Skeppy ở phía sau tôi") == []
    assert lot("Fernando", "Fernando (Phát âm: Phân Đào)") == []
    assert lot("Beverly like I'm kind of being camped", "Beverly như đang bị canh gác") == []
    assert lot("Francis probably low here", "Francis có thể đang ở đây") == []
    assert lot("It's always an opi loot video with Bob", "Đó luôn là một đoạn video trộm cắp với Bob.") == []
    assert lot("The server is so glitched", "Server này quá lỗi.") == []
    # vẫn phải báo lọt
    assert {"sounds", "like"} <= set(lot("that sounds like scabby", "那听起来像是sounds like sẹo lở"))
    from orchestrator.editor.dich import chu_la_trong_dich          # dich() gọi ngay sau do_lot_tu
    assert chu_la_trong_dich("Chúng tôi giống như无家可归的人。", "Vietnamese") == ["无家可归的人"]
    assert lot("hello world", "hello world") == ["toàn_bộ"]
    assert "bucket" in lot("My boys lava bucket", "Cái bucket lava của các cậu")


def test_lot_tu_ten_rieng_luot24():
    from orchestrator.editor.dich import do_lot_tu
    tn = {}
    tap_tu_viet_hoa = {"bob", "skeppy", "fernando", "beverly", "francis"}
    # Không lọt
    # 1. Tên riêng đứng đầu câu, dịch viết hoa
    res = do_lot_tu("Bob", "Bob (bó bễ)", "English", "Vietnamese", tn, tap_tu_viet_hoa=tap_tu_viet_hoa)
    assert not res["lot"] 

    res = do_lot_tu("Skeppy's behind me", "Skeppy ở phía sau tôi", "English", "Vietnamese", tn, tap_tu_viet_hoa=tap_tu_viet_hoa)
    assert "skeppy" not in res["lot"]

    res = do_lot_tu("Fernando", "Fernando (Phát âm: Phân Đào)", "English", "Vietnamese", tn, tap_tu_viet_hoa=tap_tu_viet_hoa)
    assert "fernando" not in res["lot"]

    res = do_lot_tu("Beverly like I'm kind of being camped", "Beverly như đang bị canh gác...", "English", "Vietnamese", tn, tap_tu_viet_hoa=tap_tu_viet_hoa)
    assert "beverly" not in res["lot"]

    res = do_lot_tu("Francis probably low here", "Francis có thể...", "English", "Vietnamese", tn, tap_tu_viet_hoa=tap_tu_viet_hoa)
    assert "francis" not in res["lot"]

    # 2. Từ mượn keep_list
    res = do_lot_tu("The server is so glitched", "Server này quá lỗi lầm.", "English", "Vietnamese", tn)
    assert not res["lot"]

    # Vẫn lọt
    res = do_lot_tu("It's always an opi loot video with Bob", "Đó luôn là một đoạn video trộm cắp với Bob.", "English", "Vietnamese", tn, tap_tu_viet_hoa=tap_tu_viet_hoa)
    assert "video" not in res["lot"] # video trong keep_list
    assert "bob" not in res["lot"]   # bob là tên riêng

    # TOÀN_BỘ
    res = do_lot_tu("hello world", "hello world", "English", "Vietnamese", tn)
    assert res["lot"] == ["TOÀN_BỘ"]

    # Chữ Hán trong bản dịch Việt
    res = do_lot_tu("Chúng tôi giống như homeless people", "Chúng tôi giống như无家可归的人。", "English", "Vietnamese", tn)

    # Từ tiếng Anh thường (lọt do không phải tên riêng)
    res = do_lot_tu("sounds like", "sounds like", "English", "Vietnamese", tn)
    assert "sounds" in res["lot"] or res["lot"] == ["TOÀN_BỘ"]

    res = do_lot_tu("hey hopper", "này hopper", "English", "Vietnamese", tn)
    assert "hopper" in res["lot"]
