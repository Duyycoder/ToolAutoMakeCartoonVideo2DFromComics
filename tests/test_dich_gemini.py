"""Dịch lô JSON qua Gemini (cookie/API key) + rơi về Ollama + đề xuất engine."""
import json

import pytest

from orchestrator.editor import dich, dich_lo_json as dl, hang_doi


class FakeViec:
    def __init__(self):
        self.huy_event = hang_doi.threading.Event()
        self.ket_qua = None


def _ctx():
    ctx = hang_doi.NguCanh(FakeViec(), None)
    ctx.bao = lambda *a, **k: None
    return ctx


def _tra_loi_dung(prompt):
    cau = json.loads(prompt[prompt.index("{"):])
    return "```json\n" + json.dumps({k: f"bản dịch {v.split()[-1]}" for k, v in cau.items()}, ensure_ascii=False) + "\n```\n\nGhi chú {thêm}."


def test_boc_json_bo_markdown_va_ghi_chu():
    assert dl.boc_json('Đây:\n```json\n{"1": "a", "2": "b"}\n```\n<Section> {x} </Section>') == {"1": "a", "2": "b"}


def test_boc_json_cuu_tung_cap_khi_hong_mot_cho():
    # Dấu " lọt giữa câu làm cả JSON hỏng: vẫn cứu được các cặp còn lại.
    assert dl.boc_json('{"1": "Ngươi nói "được" sao", "2": "Đi thôi", "3": "Hừ"}') == {"2": "Đi thôi", "3": "Hừ"}


def test_lo_bi_tu_choi_thi_chia_doi_gui_lai(monkeypatch):
    goi = []

    def chat(prompt, *a, **k):
        cau = json.loads(prompt[prompt.index("{"):])
        goi.append(len(cau))
        if len(cau) > 20:
            return "Tôi chỉ là một mô hình ngôn ngữ, nên không thể trợ giúp về điều đó."
        return _tra_loi_dung(prompt)

    monkeypatch.setattr(dl, "goi_chat", chat)
    monkeypatch.setattr(dl, "NGHI_SAU_TU_CHOI", 0)
    nguon = {i: f"câu {i}" for i in range(40)}
    kq = dl.dich_lo_json(nguon, lang_nguon="Chinese", lang_dich="Vietnamese", thuat_ngu={},
                         base_url="x", api_key="k", model="m", so_moi_lo=40, so_luong=1)
    assert len(kq["ban_dich"]) == 40 and kq["ban_dich"][7] == "bản dịch 7"
    assert goi == [40, 20, 20] and kq["so_tu_choi"] == 1 and not kq["bi_han_che"]


def test_tu_choi_lien_tiep_thi_dung_lai(monkeypatch):
    goi = []
    monkeypatch.setattr(dl, "goi_chat", lambda *a, **k: goi.append(1) or "Tôi không thể trợ giúp về điều đó.")
    monkeypatch.setattr(dl, "NGHI_SAU_TU_CHOI", 0)
    kq = dl.dich_lo_json({i: f"c{i}" for i in range(1000)}, lang_nguon="Chinese", lang_dich="Vietnamese", thuat_ngu={},
                         base_url="x", api_key="k", model="m", so_moi_lo=100, so_luong=1)
    assert kq["bi_han_che"] and not kq["ban_dich"]
    assert len(goi) == dl.NGUONG_HAN_CHE, "bị hạn chế thì phải ngừng gửi, không nện tiếp"


def test_cau_khong_qua_kiem_tra_bi_loai(monkeypatch):
    monkeypatch.setattr(dl, "goi_chat", lambda p, *a, **k: _tra_loi_dung(p))
    kq = dl.dich_lo_json({0: "a", 1: "b"}, lang_nguon="Chinese", lang_dich="Vietnamese", thuat_ngu={},
                         base_url="x", api_key="k", model="m", kiem_cau=lambda n, d: n != "b")
    assert kq["ban_dich"] == {0: "bản dịch a"}


def _cfg(engine):
    return {"translate": {"engine": engine, "so_cau_moi_lan": 1, "so_cau_song_song": 1},
            "api_keys": {"gemini": "key-that"}}


def test_engine_gemini_dich_het_khong_bat_ollama(monkeypatch, tmp_path):
    monkeypatch.setattr(dich, "load_global_config", lambda: _cfg("gemini"))
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    monkeypatch.setattr(dl, "goi_chat", lambda p, *a, **k: _tra_loi_dung(p))
    monkeypatch.setattr(dich, "goi_ollama", lambda *a, **k: pytest.fail("không được gọi Ollama"))
    bat = []
    cau = [{"id": str(k), "text_goc": f"hello {k}", "text": f"hello {k}"} for k in range(5)]
    kq = dich.dich(_ctx(), str(tmp_path), "dich", {"id": "m1"},
                   {"cau": cau, "ids": [c["id"] for c in cau], "source_lang": "English", "target_lang": "Vietnamese"},
                   dam_bao_ollama=lambda: bat.append(1))
    assert [c["text"] for c in kq["cau"]] == [f"bản dịch {k}" for k in range(5)]
    assert bat == [] and kq["bao_cao"]["engine"] == "gemini" and kq["bao_cao"]["so_cau_gemini"] == 5


def test_gemini_sot_cau_thi_ollama_dich_phan_con_lai(monkeypatch, tmp_path):
    monkeypatch.setattr(dich, "load_global_config", lambda: _cfg("gemini"))
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})

    def chat(prompt, *a, **k):
        cau = json.loads(prompt[prompt.index("{"):])
        return json.dumps({k: f"bản dịch {v.split()[-1]}" for k, v in cau.items() if v != "hello 2"})   # bỏ sót 1 câu

    monkeypatch.setattr(dl, "goi_chat", chat)
    monkeypatch.setattr(dich, "goi_ollama", lambda *a, **k: "ollama dịch")
    bat = []
    cau = [{"id": str(k), "text_goc": f"hello {k}", "text": f"hello {k}"} for k in range(4)]
    kq = dich.dich(_ctx(), str(tmp_path), "dich", {"id": "m1"},
                   {"cau": cau, "ids": [c["id"] for c in cau], "source_lang": "English", "target_lang": "Vietnamese"},
                   dam_bao_ollama=lambda: bat.append(1))
    assert [c["text"] for c in kq["cau"]] == ["bản dịch 0", "bản dịch 1", "ollama dịch", "bản dịch 3"]
    assert bat == [1]
    assert kq["bao_cao"]["so_cau_gemini"] == 3 and kq["bao_cao"]["so_cau_ollama"] == 1


def test_ollama_hong_van_giu_phan_gemini(monkeypatch, tmp_path):
    monkeypatch.setattr(dich, "load_global_config", lambda: _cfg("gemini"))
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    monkeypatch.setattr(dl, "goi_chat", lambda p, *a, **k: json.dumps({"1": "dịch một"}))

    def hong():
        raise RuntimeError("Ollama chưa chạy")

    cau = [{"id": str(k), "text_goc": f"hello {k}", "text": f"hello {k}"} for k in range(2)]
    kq = dich.dich(_ctx(), str(tmp_path), "dich", {"id": "m1"},
                   {"cau": cau, "ids": [c["id"] for c in cau], "source_lang": "English", "target_lang": "Vietnamese"},
                   dam_bao_ollama=hong)
    assert [c["text"] for c in kq["cau"]] == ["dịch một", "hello 1"]
    assert any("Ollama không chạy được" in x for x in kq["canh_bao"])


def test_cookie_het_han_tu_dich_bang_model_local(monkeypatch, tmp_path):
    from orchestrator import gemini_proxy
    monkeypatch.setattr(dich, "load_global_config", lambda: _cfg("gemini_api"))
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    monkeypatch.setattr(gemini_proxy, "trang_thai", lambda: {"ma": "cookie_het_han", "thong_bao": "Cookie hết hạn."})
    monkeypatch.setattr(dl, "goi_chat", lambda *a, **k: pytest.fail("cookie hết hạn thì không gửi Gemini"))
    monkeypatch.setattr(dich, "goi_ollama", lambda *a, **k: "ollama dịch")
    bat = []
    cau = [{"id": "1", "text_goc": "hello", "text": "hello"}]
    kq = dich.dich(_ctx(), str(tmp_path), "dich", {"id": "m1"},
                   {"cau": cau, "ids": ["1"], "source_lang": "English", "target_lang": "Vietnamese"},
                   dam_bao_ollama=lambda: bat.append(1))
    assert bat == [1] and kq["cau"][0]["text"] == "ollama dịch"
    assert kq["bao_cao"]["engine"] == "ollama" and "hết hạn" in kq["bao_cao"]["gemini_chuyen_local"]


def test_cookie_het_han_ma_ollama_hong_thi_bao_loi(monkeypatch, tmp_path):
    from orchestrator import gemini_proxy
    monkeypatch.setattr(dich, "load_global_config", lambda: _cfg("gemini_api"))
    monkeypatch.setattr(dich, "doc_thuat_ngu", lambda f: {})
    monkeypatch.setattr(gemini_proxy, "trang_thai", lambda: {"ma": "chua_co_cookie", "thong_bao": "Chưa có."})

    def hong():
        raise RuntimeError("Ollama chưa chạy")

    cau = [{"id": "1", "text_goc": "hello", "text": "hello"}]
    with pytest.raises(RuntimeError, match="model local không chạy được"):
        dich.dich(_ctx(), str(tmp_path), "dich", {"id": "m1"},
                  {"cau": cau, "ids": ["1"], "source_lang": "English", "target_lang": "Vietnamese"},
                  dam_bao_ollama=hong)


def test_tham_so_ghi_de_engine_mac_dinh():
    assert dich.chon_engine({"llm_engine": "gemini_api"}, {"engine": "ollama"}) == "gemini_api"
    assert dich.chon_engine({}, {"engine": "gemini"}) == "gemini"
    assert dich.chon_engine({}, {"engine": "la_hoac"}) == "ollama"


@pytest.mark.parametrize("cookie,key,n,mong", [
    (True, False, 500, "gemini_api"),
    (True, True, 500, "gemini_api"),     # ít câu: cookie miễn phí là đủ
    (True, True, 16000, "gemini"),       # nhiều câu: API key nhanh và không bị chặn
    (False, False, 500, "ollama"),
])
def test_de_xuat_engine(monkeypatch, cookie, key, n, mong):
    from orchestrator import gemini_proxy
    from orchestrator.editor import de_xuat_dich as dx
    monkeypatch.setattr(dx, "load_global_config", lambda: {"api_keys": {"gemini": "k" if key else ""}, "translate": {}})
    monkeypatch.setattr(gemini_proxy, "trang_thai", lambda: {"ma": "san_sang" if cookie else "chua_co_cookie", "thong_bao": ""})
    monkeypatch.setattr(gemini_proxy, "doc_cookie", lambda: ("psid" if cookie else "", ""))
    monkeypatch.setattr(dx, "_ollama", lambda g: {"san_sang": True, "trang_thai": "ok"})
    kq = dx.de_xuat(n)
    assert kq["de_xuat"] == mong and kq["giai_thich"]
    assert {e["id"] for e in kq["engines"]} == {"gemini_api", "gemini", "ollama"}
