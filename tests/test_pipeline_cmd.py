"""Dong lenh gui xuong adapter: sai mot co la ca luot chay hong ma log van "thanh cong"."""
import os

import pytest

from orchestrator.pipeline import VideoPipeline
from orchestrator.process_manager import ProcessManager
from orchestrator.storage import VideoLibrary


@pytest.fixture
def pipe(tmp_path):
    return VideoPipeline(VideoLibrary(str(tmp_path / "storage")), ProcessManager())


def arg_value(cmd, flag):
    """Gia tri dung sau mot co trong danh sach lenh (None neu khong co co do)."""
    return cmd[cmd.index(flag) + 1] if flag in cmd else None


# ------------------------------------------------------------------- CAO
def test_lenh_tai_gom_du_link_va_tuy_chon(pipe):
    cmd = pipe.build_download_cmd(
        ["https://a/1", "https://a/2"],
        {"platform": "tiktok", "max_items": 5, "skip_existing": True, "stop_on_error": True},
        {})
    assert cmd.count("--url") == 2
    assert arg_value(cmd, "--platform") == "tiktok"
    assert arg_value(cmd, "--max-items") == "5"
    assert "--skip-existing" in cmd and "--stop-on-error" in cmd
    assert arg_value(cmd, "--output-dir") == pipe.library.videos_dir


def test_lenh_tai_khong_bat_co_khi_khong_chon(pipe):
    cmd = pipe.build_download_cmd(["u"], {"skip_existing": False}, {})
    assert "--skip-existing" not in cmd
    assert "--stop-on-error" not in cmd
    assert "--max-items" not in cmd


def test_cookies_lay_tu_cau_hinh_chung_khi_form_de_trong(pipe):
    cmd = pipe.build_download_cmd(["u"], {}, {"video": {"downloader_cookies": "D:/ck.txt"}})
    assert arg_value(cmd, "--cookies-file") == "D:/ck.txt"


def test_cookies_tren_form_thang_cau_hinh_chung(pipe):
    cmd = pipe.build_download_cmd(["u"], {"cookies_file": "E:/rieng.txt"},
                                  {"video": {"downloader_cookies": "D:/ck.txt"}})
    assert arg_value(cmd, "--cookies-file") == "E:/rieng.txt"


# ------------------------------------------------------------------ DICH
BASE_JOB = {"entry_id": "phim", "title": "Phim", "video_path": "C:/v/phim.mp4",
            "output_dir": "C:/v/out", "srt_dir": "C:/v/subs"}

OLLAMA_CFG = {"translate": {"ollama_base_url": "http://localhost:11434/v1",
                            "ollama_model": "qwen2.5:3b-instruct"}}


def test_lenh_dich_mac_dinh(pipe):
    cmd = pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "ollama"}, OLLAMA_CFG)
    assert arg_value(cmd, "--video-path") == "C:/v/phim.mp4"
    assert arg_value(cmd, "--output-dir") == "C:/v/out"
    assert arg_value(cmd, "--srt-out-dir") == "C:/v/subs"
    assert arg_value(cmd, "--target-lang") == "Vietnamese"
    assert arg_value(cmd, "--sub-source") == "whisper"
    assert arg_value(cmd, "--llm-base-url") == "http://localhost:11434/v1"
    assert arg_value(cmd, "--llm-model") == "qwen2.5:3b-instruct"
    assert "--translate-only" not in cmd
    assert "--enable-voiceover" not in cmd


def test_ngon_ngu_dich_truyen_xuong_adapter(pipe):
    cmd = pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "ollama", "target_lang": "Japanese"},
                                   OLLAMA_CFG)
    assert arg_value(cmd, "--target-lang") == "Japanese"


def test_che_do_chi_xuat_srt(pipe):
    cmd = pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "ollama", "translate_only": True},
                                   OLLAMA_CFG)
    assert "--translate-only" in cmd


def test_nap_srt_co_san_va_bo_qua_dich(pipe):
    cmd = pipe.build_translate_cmd(
        BASE_JOB,
        {"llm_engine": "ollama", "sub_source": "import",
         "source_srt": "C:/v/subs/phim.en.srt", "no_translate": True},
        OLLAMA_CFG)
    assert arg_value(cmd, "--sub-source") == "import"
    assert arg_value(cmd, "--source-srt") == "C:/v/subs/phim.en.srt"
    assert "--no-translate" in cmd


def test_vung_ocr_chi_gui_khi_hop_le(pipe):
    args = {"llm_engine": "ollama", "sub_source": "ocr",
            "crop_x": 10, "crop_y": 20, "crop_w": 300, "crop_h": 60}
    cmd = pipe.build_translate_cmd(BASE_JOB, args, OLLAMA_CFG)
    assert arg_value(cmd, "--crop-x") == "10"
    assert arg_value(cmd, "--crop-h") == "60"

    args.update({"crop_w": 0, "crop_h": -1})
    cmd = pipe.build_translate_cmd(BASE_JOB, args, OLLAMA_CFG)
    assert "--crop-x" not in cmd


def test_kieu_chu_bo_qua_o_trong(pipe):
    cmd = pipe.build_translate_cmd(
        BASE_JOB,
        {"llm_engine": "ollama", "font_size": 45, "font_name": "", "text_color": "#ffffff"},
        OLLAMA_CFG)
    assert arg_value(cmd, "--font-size") == "45"
    assert arg_value(cmd, "--text-color") == "#ffffff"
    assert "--font-name" not in cmd


def test_long_tieng_bat_du_co(pipe):
    cmd = pipe.build_translate_cmd(
        BASE_JOB,
        {"llm_engine": "ollama", "enable_voiceover": True, "auto_clone": True,
         "tts_engine": "clone", "tts_voice": "giong_a", "ducking_ratio": 80},
        OLLAMA_CFG)
    assert "--enable-voiceover" in cmd and "--auto-clone" in cmd
    assert arg_value(cmd, "--tts-engine") == "clone"
    assert arg_value(cmd, "--ducking-ratio") == "80"


def test_gemini_online_thieu_key_thi_bao_loi_som(pipe):
    with pytest.raises(ValueError, match="API Key"):
        pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "gemini"}, {})


def test_gemini_online_dung_key_trong_cau_hinh(pipe):
    cmd = pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "gemini"},
                                   {"api_keys": {"gemini": "AIza-test"}})
    assert arg_value(cmd, "--llm-api-key") == "AIza-test"
    assert "generativelanguage.googleapis.com" in arg_value(cmd, "--llm-base-url")


def test_ocr_gpu_theo_cau_hinh_video(pipe):
    cmd = pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "ollama"},
                                   {**OLLAMA_CFG, "video": {"ocr_use_gpu": False}})
    assert "--use-gpu" not in cmd
    cmd = pipe.build_translate_cmd(BASE_JOB, {"llm_engine": "ollama", "ocr_use_gpu": True},
                                   {**OLLAMA_CFG, "video": {"ocr_use_gpu": False}})
    assert "--use-gpu" in cmd


def test_make_job_tro_dung_thu_muc_cua_muc_thu_vien(pipe):
    job = pipe.make_job({"entry_id": "phim_abc", "title": "Phim", "file": "C:/x.mp4"})
    assert job["output_dir"] == pipe.library.output_dir("phim_abc")
    assert job["srt_dir"] == pipe.library.subs_dir("phim_abc")


def test_khong_co_viec_thi_khong_chay(pipe):
    assert pipe.start_translate("translate", [], {}) is False
    assert pipe.start_merge("merge", [], "") is False


def test_duong_dan_adapter_ton_tai():
    """Sai duong dan adapter thi loi chi lo ra luc chay that (rat lau sau)."""
    from orchestrator import pipeline as pl
    assert os.path.exists(pl.DOWNLOAD_ADAPTER), pl.DOWNLOAD_ADAPTER
    assert os.path.exists(pl.AUTOSUB_ADAPTER), pl.AUTOSUB_ADAPTER
