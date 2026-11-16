"""Bật từng phần AI theo EDITOR_AI_MODE + chọn model cho Whisper chạy thẳng trên server (không AIVoice)."""
from orchestrator.editor import api, whisper_truc_tiep


def test_tinh_nang_ai_theo_che_do():
    assert api.tinh_nang_ai("all") == api.TAT_CA_AI
    assert api.tinh_nang_ai("off") == []
    assert api.tinh_nang_ai("translate") == ["dich"]
    # Thứ tự theo danh sách chuẩn, bỏ tên lạ, chấp nhận khoảng trắng.
    assert api.tinh_nang_ai("translate, phu-de, khong-co") == ["phu-de", "dich"]


def test_chon_model_whisper():
    assert whisper_truc_tiep.chon_model("medium") == "medium"
    assert whisper_truc_tiep.chon_model("large-v3") == "large-v3"
    # PhoWhisper là model transformers — server không chạy được → Whisper small đa ngôn ngữ.
    assert whisper_truc_tiep.chon_model("qbsmlabs/PhoWhisper-small") == "small"
    assert whisper_truc_tiep.chon_model("") == "small"


def test_doc_wav_16k(tmp_path):
    import wave
    p = str(tmp_path / "a.wav")
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x40" * 16000)   # 1 s, biên độ 0x4000 = 0.5
    a = whisper_truc_tiep.doc_wav_16k(p)
    assert a.shape == (16000,) and str(a.dtype) == "float32" and abs(float(a[0]) - 0.5) < 1e-6


def test_ma_ngon_ngu_du_cho_moi_lua_chon_giao_dien():
    for ten in ("English", "Chinese", "Japanese", "Korean", "Vietnamese", "Thai", "Indonesian", "Spanish"):
        assert whisper_truc_tiep.MA_NGON_NGU[ten]
