"""Test cho bo chan doan loi tai video (video_downloader.diagnose_download_failure).

Module that nam trong AIVoice/apps/MediaComposer va import yt_dlp + app.utils.utils —
ca hai deu khong co trong moi truong CI. Nap file bang importlib voi stub cho 2
phu thuoc do, vi phan can test (phan loai loi) khong dung den chung.
"""
import importlib.util
import os
import sys
import types

import pytest

VD_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "AIVoice", "apps", "MediaComposer",
    "app", "services", "video_downloader.py"))


@pytest.fixture(scope="module")
def vd():
    saved = {k: sys.modules.get(k) for k in ("yt_dlp", "app", "app.utils", "app.utils.utils")}

    sys.modules["yt_dlp"] = types.ModuleType("yt_dlp")
    app = types.ModuleType("app")
    app_utils = types.ModuleType("app.utils")
    utils = types.ModuleType("app.utils.utils")
    utils.get_ffmpeg_binary = lambda: "ffmpeg"
    app_utils.utils = utils
    app.utils = app_utils
    sys.modules["app"] = app
    sys.modules["app.utils"] = app_utils
    sys.modules["app.utils.utils"] = utils

    spec = importlib.util.spec_from_file_location("_vd_under_test", VD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


NO_FORMATS = ("[TikTok] 7655814170499222785: No video formats found!; please report this "
              "issue on https://github.com/yt-dlp/yt-dlp/issues?q=")
TIKTOK_URL = "https://www.tiktok.com/@dramayaya_jp/video/7655814170499222785"


def test_ip_blocked(vd):
    err = "[TikTok] 123: Your IP address is blocked from accessing this post"
    msg = vd.diagnose_download_failure(TIKTOK_URL, "tiktok", err)
    assert "chặn IP" in msg
    assert "VPN" in msg


def test_private_post(vd):
    err = "[TikTok] 123: You do not have permission to view this post"
    msg = vd.diagnose_download_failure(TIKTOK_URL, "tiktok", err)
    assert "cookies" in msg
    assert "No video formats" not in msg


def test_unrelated_error_passes_through(vd):
    err = "HTTP Error 404: Not Found"
    assert vd.diagnose_download_failure(TIKTOK_URL, "tiktok", err) == err


def test_waf_403(vd):
    err = "[TikTok] 123: Unable to download webpage: HTTP Error 403: Forbidden"
    msg = vd.diagnose_download_failure(TIKTOK_URL, "tiktok", err)
    assert "_waftokenid" in msg


def test_tiktok_drama_episode(vd, monkeypatch):
    monkeypatch.setattr(vd, "_tiktok_drama_name", lambda *a, **k: "The Fallen Monk's Revenge")
    msg = vd.diagnose_download_failure(TIKTOK_URL, "tiktok", NO_FORMATS)
    assert "The Fallen Monk's Revenge" in msg
    assert "TikTok Series" in msg
    # Drama VAN tai duoc neu cookies la phien da dang nhap co quyen xem
    assert "Cookies file" in msg


def test_tiktok_no_play_url_suggests_cookies(vd, monkeypatch):
    monkeypatch.setattr(vd, "_tiktok_drama_name", lambda *a, **k: None)
    msg = vd.diagnose_download_failure(TIKTOK_URL, "tiktok", NO_FORMATS)
    assert "Cookies file" in msg
    assert "TikTok Series" not in msg


def test_non_tiktok_no_formats(vd):
    msg = vd.diagnose_download_failure("https://example.com/clip/1", "generic", NO_FORMATS)
    assert "Cookies file" in msg
    assert NO_FORMATS in msg  # giu lai loi goc de con debug


def _cookie_row(name, value="v"):
    return f".tiktok.com\tTRUE\t/\tTRUE\t9999999999\t{name}\t{value}"


def test_sanitize_drops_waf_cookies(vd, tmp_path):
    src = tmp_path / "cookies.txt"
    src.write_text("\n".join([
        "# Netscape HTTP Cookie File",
        _cookie_row("sessionid"),
        _cookie_row("_waftokenid"),
        "#HttpOnly_" + _cookie_row("ttwid"),
    ]) + "\n", encoding="utf-8")

    out, dropped = vd.sanitize_cookies_file(str(src), str(tmp_path / "work"))

    assert dropped == ["_waftokenid"]
    body = open(out, encoding="utf-8").read()
    assert "_waftokenid" not in body
    assert "sessionid" in body
    assert "ttwid" in body          # dong #HttpOnly_ phai duoc giu
    assert body.startswith("# Netscape HTTP Cookie File")
    assert src.read_text(encoding="utf-8").count("_waftokenid") == 1  # file goc khong bi sua


def test_sanitize_noop_when_no_waf_cookie(vd, tmp_path):
    src = tmp_path / "cookies.txt"
    src.write_text(_cookie_row("sessionid") + "\n", encoding="utf-8")
    assert vd.sanitize_cookies_file(str(src), str(tmp_path / "work")) == (None, [])


def test_sanitize_survives_unreadable_file(vd, tmp_path):
    assert vd.sanitize_cookies_file(str(tmp_path / "khong-ton-tai.txt"), str(tmp_path)) == (None, [])


def test_probe_never_raises(vd, monkeypatch):
    """_tiktok_drama_name nuot moi loi — chan doan hong khong duoc lam hong bao loi."""
    boom = types.ModuleType("yt_dlp")

    def explode(*a, **k):
        raise RuntimeError("yt-dlp doi API")

    boom.YoutubeDL = explode
    monkeypatch.setattr(vd, "yt_dlp", boom)
    assert vd._tiktok_drama_name(TIKTOK_URL) is None
    msg = vd.diagnose_download_failure(TIKTOK_URL, "tiktok", NO_FORMATS)
    assert "chống bot" in msg
