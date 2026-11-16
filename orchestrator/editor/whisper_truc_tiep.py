"""Tạo phụ đề bằng faster-whisper chạy THẲNG trong Python của server — dùng khi không có AIVoice
(server Linux: AIVoice chỉ có bản Windows `.venv/Scripts/python.exe`).

- CPU int8 (server không có GPU dùng được cho CTranslate2); model giữ trong RAM giữa các việc → tạo phụ đề
  hàng loạt nhiều video nhỏ không nạp lại model mỗi video. Hàng đợi GPU chạy tuần tự nên không cần khoá.
- PhoWhisper (transformers) không có ở đây → đổi sang model Whisper đa ngôn ngữ cùng cỡ.
- Không có Demucs → bỏ qua tách giọng, báo cảnh báo.
Trả `ket_qua` cùng dạng `ai_bridge.chay` (cau = [{t_vao, t_ra, text}]) để client áp vào timeline như cũ.
"""
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from orchestrator.editor import hang_doi, luu_tru, media as media_mod

MA_NGON_NGU = {"English": "en", "Chinese": "zh", "Japanese": "ja", "Korean": "ko", "Vietnamese": "vi",
               "Thai": "th", "Indonesian": "id", "Spanish": "es"}
MODEL_HOP_LE = ("tiny", "base", "small", "medium", "large-v3")
_model: Optional[Tuple[str, Any]] = None   # (tên, WhisperModel) đang nạp


def co_san() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def chon_model(ten: str) -> str:
    """Tên model client gửi → model faster-whisper. PhoWhisper-small/không rõ → small."""
    ten = (ten or "").strip()
    return ten if ten in MODEL_HOP_LE else "small"


def _nap_model(ten: str):
    global _model
    if _model and _model[0] == ten:
        return _model[1]
    from faster_whisper import WhisperModel
    _model = None   # nhả model cũ trước khi nạp model mới (RAM server có hạn)
    m = WhisperModel(ten, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    _model = (ten, m)
    return m


def tach_tieng_16k(video: str, ra: str) -> None:
    ff = media_mod.ffmpeg_exe()
    if not ff:
        raise RuntimeError("Không tìm thấy ffmpeg trên máy chủ.")
    r = subprocess.run([ff, "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", ra],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(ra):
        raise RuntimeError("Không tách được tiếng: " + (r.stderr or "").strip()[-300:])


def chay(ctx: hang_doi.NguCanh, folder: str, m: Dict[str, Any], tham_so: Dict[str, Any]) -> Dict[str, Any]:
    """Thân việc 'phu-de' trong hàng đợi GPU."""
    video = luu_tru.duong_dan_media(folder, m["file"])
    if not os.path.isfile(video):
        raise ValueError(f"Không còn file media: {m['file']}")
    canh_bao: List[str] = []
    yeu_cau = str(tham_so.get("whisper_model") or "")
    ten = chon_model(yeu_cau)
    if yeu_cau and yeu_cau != ten:
        canh_bao.append(f"Máy chủ không có {yeu_cau} — dùng Whisper {ten}.")
    if tham_so.get("clean_audio"):
        canh_bao.append("Máy chủ không có Demucs — bỏ qua bước tách giọng.")
    ngon_ngu = MA_NGON_NGU.get(str(tham_so.get("source_lang") or ""))
    ctx.bao(0, "Đang tách tiếng…")
    with tempfile.TemporaryDirectory(prefix="whisper_") as tmp:
        wav = os.path.join(tmp, "a.wav")
        tach_tieng_16k(video, wav)
        ctx.kiem_tra_huy()
        ctx.bao(2, f"Đang nạp model Whisper {ten} (lần đầu sẽ tải về)…")
        model = _nap_model(ten)
        ctx.kiem_tra_huy()
        doan, info = model.transcribe(wav, language=ngon_ngu, vad_filter=True, beam_size=5)
        tong = float(getattr(info, "duration", 0) or m.get("thoi_luong") or 0)
        cau: List[Dict[str, Any]] = []
        for d in doan:   # generator: nhận giọng chạy dần theo vòng lặp này
            ctx.kiem_tra_huy()
            text = (d.text or "").strip()
            if text:
                cau.append({"t_vao": round(float(d.start), 3), "t_ra": round(float(d.end), 3), "text": text})
            if tong > 0:
                ctx.bao(min(99.0, 5 + 94 * float(d.end) / tong), f"{len(cau)} câu…")
    if not cau:
        raise RuntimeError("Không nhận ra câu nào (video không có lời, hoặc sai ngôn ngữ nói).")
    return {"loai": "phu-de", "media": m.get("id"), "canh_bao": canh_bao, "cau": cau, "so_cau": len(cau)}
