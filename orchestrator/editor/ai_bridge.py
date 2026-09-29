"""Nối các tính năng AI có sẵn (adapter_autosub_cli.py) vào editor — docs/PLAN-editor.md mục 5.

Không đốt thẳng vào video nữa: mỗi tác vụ trả FILE RỜI để đưa lên timeline.
    phu-de    Whisper  → .srt nguồn   (--sub-source whisper --translate-only --no-translate)
    ocr       PaddleOCR theo vùng kéo trên xem trước → .srt nguồn  (+ vùng để tạo clip che phụ đề)
    dich      .srt xuất từ track phụ đề → LLM → .srt đã dịch  (--sub-source import --translate-only)
    long-tieng .srt đã dịch → TTS → .wav giọng riêng  (--voiceover-only) → media mới + track A2
Mọi tác vụ chạy ở `hang_gpu` (mỗi lúc một việc nặng), trạng thái ghi vào `.duan.json › tac_vu[]`.
Kết quả chỉ được ÁP vào timeline khi người dùng bấm [Áp dụng] (client dựng lệnh hoàn tác).
"""
import json
import os
from typing import Any, Callable, Dict, List, Optional

from orchestrator.editor import hang_doi, luu_tru, srt

LOAI = ("phu-de", "ocr", "dich", "long-tieng", "tach-giong", "lam-net", "can-gio", "tao-anh", "doc-van-ban", "minh-hoa")
TEN = {"phu-de": "Tạo phụ đề (Whisper)", "ocr": "Nhận diện sub cứng (OCR)",
       "dich": "Dịch phụ đề", "long-tieng": "Lồng tiếng",
       "tach-giong": "Tách giọng (Demucs)", "lam-net": "Làm nét (RealESRGAN)",
       "can-gio": "Tự căn giờ phụ đề", "tao-anh": "Tạo ảnh AI", "doc-van-ban": "Đọc văn bản thành giọng",
       "minh-hoa": "Video minh hoạ theo phụ đề"}


# Loại AI không cần media nguồn (dùng chung cho api.xep_ai — đừng lặp danh sách: doc-van-ban từng bị route báo "Không có media").
KHONG_CAN_MEDIA = ("tao-anh", "doc-van-ban")


def _rel(folder: str, path: str) -> str:
    return os.path.relpath(os.path.abspath(path), os.path.abspath(folder)).replace("\\", "/")


def dung_lenh(folder: str, loai: str, m: Dict[str, Any], tham_so: Dict[str, Any], g_config: Dict[str, Any],
              xay_lenh: Callable[[dict, dict, dict], list], viec_id: str) -> Dict[str, Any]:
    """{cmd, lam_viec, srt_vao?} cho một tác vụ AI trên media `m` (file GỐC, không dùng proxy)."""
    if loai not in LOAI:
        raise ValueError(f"Không có tác vụ AI '{loai}'.")
    if loai not in KHONG_CAN_MEDIA:
        if not m or m.get("loai") not in ("video", "audio"):
            raise ValueError("Tác vụ AI cần một media video hoặc âm thanh.")
        video = luu_tru.duong_dan_media(folder, m["file"])
        if not os.path.isfile(video):
            raise ValueError(f"Không còn file media: {m['file']}")
    else:
        video = ""
    lam_viec = luu_tru._p(folder, luu_tru.CACHE, "ai", viec_id)
    os.makedirs(lam_viec, exist_ok=True)
    autosub = g_config.get("autosub") or {}
    tr = g_config.get("translate") or {}
    video_cfg = g_config.get("video") or {}
    llm_engine = tham_so.get("llm_engine") or tr.get("engine") or autosub.get("llm_engine") or "gemini_api"
    from orchestrator.llm import resolve_llm
    llm_api_key, llm_base_url, llm_model = resolve_llm(
        llm_engine, tham_so, g_config,
        autosub.get("llm_model") or video_cfg.get("default_llm_model") or ""
    )
    
    source_lang = tham_so.get("source_lang")
    if loai == "dich" and not source_lang:
        duan = luu_tru.doc_duan(folder) or {}
        for tv in reversed(duan.get("tac_vu") or []):
            if tv.get("loai") in ("phu-de", "ocr") and tv.get("media") == m["id"]:
                ts = tv.get("tham_so") or {}
                if ts.get("source_lang"):
                    source_lang = ts.get("source_lang")
                    break
    if not source_lang:
        source_lang = autosub.get("source_lang") or "English"
    if loai == "dich" and source_lang.lower() == "auto":
        raise ValueError("Chưa biết ngôn ngữ nguồn của media này — hãy chọn 'Dịch từ' trên bảng AI.")

    args: Dict[str, Any] = {
        "source_lang": source_lang,
        "target_lang": tham_so.get("target_lang") or tr.get("target_lang") or "Vietnamese",
        "llm_engine": llm_engine,
        "llm_model": llm_model,
        "llm_base_url": llm_base_url,
        "llm_api_key": llm_api_key,
        "translate_only": True,
    }
    if "whisper_model" in tham_so:
        args["whisper_model"] = tham_so["whisper_model"]
    if "whisper_device" in tham_so:
        args["whisper_device"] = tham_so["whisper_device"]
    srt_vao = ""
    if loai == "phu-de":
        args.update(sub_source="whisper", no_translate=True, clean_audio=bool(tham_so.get("clean_audio")))
    elif loai == "ocr":
        vung = tham_so.get("vung_px") or {}
        if not all(k in vung for k in ("x", "y", "w", "h")) or int(vung["w"]) <= 0 or int(vung["h"]) <= 0:
            raise ValueError("Chưa kéo vùng chứa phụ đề trên khung xem trước.")
        args.update(sub_source="ocr", no_translate=True, crop_x=int(vung["x"]), crop_y=int(vung["y"]),
                    crop_w=int(vung["w"]), crop_h=int(vung["h"]))
        if tham_so.get("ocr_fps"):
            args["ocr_fps"] = float(tham_so["ocr_fps"])
        if tham_so.get("ocr_model"):
            args["ocr_model"] = str(tham_so["ocr_model"])
    elif loai in ("tach-giong", "lam-net"):
        pass
    elif loai == "can-gio":
        cau = tham_so.get("cau") or []
        if not cau:
            raise ValueError("Media này chưa có câu phụ đề nào trên timeline để tự căn giờ.")
        srt_vao = os.path.join(lam_viec, "vao.srt")
        with open(srt_vao, "w", encoding="utf-8") as fh:
            fh.write(srt.ghi_srt(cau))
        args.update(can_gio_only=True, sub_source="import", source_srt=srt_vao)
    elif loai == "tao-anh":
        if not tham_so.get("anh_prompt"):
            raise ValueError("Thiếu prompt tạo ảnh.")
        args.update(
            tao_anh_only=True,
            anh_prompt=tham_so.get("anh_prompt"),
            anh_negative=tham_so.get("anh_negative") or "",
            anh_model=tham_so.get("anh_model") or "",
            anh_rong=int(tham_so.get("anh_rong") or 1024),
            anh_cao=int(tham_so.get("anh_cao") or 1024),
            anh_so=int(tham_so.get("anh_so") or 1),
            anh_steps=int(tham_so.get("anh_steps") or 20),
            anh_guidance=float(tham_so.get("anh_guidance") or 7.0),
            # seed 0 là seed hợp lệ — `or -1` từng biến nó thành ngẫu nhiên
            anh_seed=int(tham_so["anh_seed"]) if tham_so.get("anh_seed") not in (None, "") else -1,
        )
    elif loai == "doc-van-ban":
        text = (tham_so.get("van_ban") or "").strip()
        if not text:
            raise ValueError("Vui lòng nhập văn bản để đọc.")
        van_ban_file = os.path.join(lam_viec, "van_ban.txt")
        with open(van_ban_file, "w", encoding="utf-8") as fh:
            fh.write(text)
        args.update(
            doc_van_ban_only=True,
            van_ban_file=van_ban_file,
            tts_engine=tham_so.get("tts_engine") or autosub.get("tts_engine"),
            tts_voice=tham_so.get("tts_voice") or autosub.get("tts_voice") or "",
            tts_speed=tham_so.get("tts_speed"),
            tts_pitch=tham_so.get("tts_pitch")
        )
    elif loai == "minh-hoa":
        cau = tham_so.get("cau") or []
        if not cau:
            raise ValueError("Media này chưa có câu phụ đề nào để minh hoạ.")
        # Kiểm key TRƯỚC khi xếp việc — không có thì material.py in cả khối config (lẫn key LLM) thành thông báo lỗi khó đọc.
        nguon_mh = tham_so.get("minh_hoa_nguon") or tham_so.get("nguon") or "pexels"
        if not ((g_config.get("api_keys") or {}).get(nguon_mh) or "").strip():
            raise ValueError(f"Cần API key {nguon_mh.capitalize()} (miễn phí) — nhập trong ⚙ Cấu hình › API key rồi chạy lại.")
        srt_vao = os.path.join(lam_viec, "vao.srt")
        # Gộp ở đây (không trong adapter): adapter chạy trong venv/cwd AIVoice, không import được gói `orchestrator`.
        with open(srt_vao, "w", encoding="utf-8") as fh:
            fh.write(srt.ghi_srt(gop_cau_minh_hoa(sorted(cau, key=lambda c: float(c.get("t_vao", 0))), min_duration=3.0)))
        args.update(sub_source="import", source_srt=srt_vao, minh_hoa_only=True)
        if "nguon" in tham_so:
            args["minh_hoa_nguon"] = tham_so["nguon"]
        if "ti_le" in tham_so:
            args["minh_hoa_ti_le"] = tham_so["ti_le"]
    else:
        cau = tham_so.get("cau") or []
        if not cau:
            raise ValueError("Media này chưa có câu phụ đề nào trên timeline để "
                             + ("dịch." if loai == "dich" else "lồng tiếng."))
        srt_vao = os.path.join(lam_viec, "vao.srt")
        with open(srt_vao, "w", encoding="utf-8") as fh:
            fh.write(srt.ghi_srt(cau))
        args.update(sub_source="import", source_srt=srt_vao)
        if loai == "long-tieng":
            args.update(no_translate=True, translate_only=False, tts_engine=tham_so.get("tts_engine") or autosub.get("tts_engine"),
                        tts_voice=tham_so.get("tts_voice") or autosub.get("tts_voice") or "",
                        auto_clone=bool(tham_so.get("auto_clone")),
                        tts_speed=tham_so.get("tts_speed"),
                        tts_pitch=tham_so.get("tts_pitch"),
                        ducking_ratio=float(tham_so.get("ducking_ratio") or autosub.get("ducking_ratio") or 90))
    job = {"video_path": video, "output_dir": lam_viec, "srt_dir": lam_viec}
    cmd = xay_lenh(job, args, g_config)
    # Model/thiết bị Whisper: build_translate_cmd không biết hai khoá này → thêm tường minh (phụ đề + tự căn giờ).
    if args.get("whisper_model"):
        cmd += ["--whisper-model", str(args["whisper_model"])]
    if args.get("whisper_device"):
        cmd += ["--whisper-device", str(args["whisper_device"])]
    if loai == "can-gio":
        cmd = [c for c in cmd if c != "--translate-only"] + ["--can-gio-only"]
    elif loai == "long-tieng":
        cmd = [c for c in cmd if c != "--translate-only"] + [
            "--voiceover-only", "--audio-out-dir", os.path.join(os.path.abspath(folder), luu_tru.LONG_TIENG_DIR)]
    elif loai == "tach-giong":
        cmd = [c for c in cmd if c != "--translate-only"] + [
            "--tach-giong-only", "--audio-out-dir", os.path.join(os.path.abspath(folder), luu_tru.LONG_TIENG_DIR)]
    elif loai == "tao-anh":
        # `xay_lenh` (pipeline.build_translate_cmd) chỉ chuyển các khoá nó biết → cờ tạo ảnh để trong `args` bị RƠI
        # (chạy thật: adapter đi nhánh video, "Không tìm thấy video"). Thêm tường minh.
        # Ảnh là media lâu dài → lưu thẳng vào media/ (cache có thể bị dọn làm media mất file); argparse lấy --output-dir sau cùng.
        cmd = [c for c in cmd if c != "--translate-only"] + ["--tao-anh-only", "--output-dir", os.path.join(os.path.abspath(folder), luu_tru.MEDIA_DIR)]
        for co, khoa in (("--anh-prompt", "anh_prompt"), ("--anh-negative", "anh_negative"), ("--anh-model", "anh_model"),
                         ("--anh-rong", "anh_rong"), ("--anh-cao", "anh_cao"), ("--anh-so", "anh_so"), ("--anh-steps", "anh_steps"),
                         ("--anh-guidance", "anh_guidance"), ("--anh-seed", "anh_seed")):
            if args.get(khoa) not in (None, ""):
                cmd += [co, str(args[khoa])]
    elif loai == "minh-hoa":
        cmd = [c for c in cmd if c != "--translate-only"] + [
            "--minh-hoa-only", "--output-dir", os.path.join(os.path.abspath(folder), luu_tru.MEDIA_DIR)]
        for co, khoa in (("--minh-hoa-nguon", "minh_hoa_nguon"), ("--minh-hoa-ti-le", "minh_hoa_ti_le")):
            if args.get(khoa):
                cmd += [co, str(args[khoa])]
        api_keys = g_config.get("api_keys") or {}
        if api_keys.get("pexels"): cmd += ["--pexels-api-key", str(api_keys["pexels"])]
        if api_keys.get("pixabay"): cmd += ["--pixabay-api-key", str(api_keys["pixabay"])]
        if api_keys.get("coverr"): cmd += ["--coverr-api-key", str(api_keys["coverr"])]
    elif loai == "doc-van-ban":
        cmd = [c for c in cmd if c != "--translate-only"] + [
            "--doc-van-ban-only", "--van-ban-file", args["van_ban_file"],
            "--audio-out-dir", os.path.join(os.path.abspath(folder), luu_tru.LONG_TIENG_DIR)]
    elif loai == "lam-net":
        phong_to = tham_so.get("phong_to", False)
        if not phong_to:
            kieu = "nhanh"
            dpg = "Gốc"
        else:
            kieu = tham_so.get("kieu") or "nhanh"
            dpg = tham_so.get("do_phan_giai") or "Gốc"
        cmd = [c for c in cmd if c != "--translate-only"] + [
            "--lam-net-only", "--lam-net-kieu", kieu, "--lam-net-do-phan-giai", dpg,
            "--output-dir", os.path.join(os.path.abspath(folder), luu_tru.MEDIA_DIR)]
    if loai in ("long-tieng", "doc-van-ban"):
        if args.get("tts_speed") is not None:
            cmd += ["--tts-speed", str(args["tts_speed"])]
        if args.get("tts_pitch") is not None:
            cmd += ["--tts-pitch", str(args["tts_pitch"])]
    return {"cmd": cmd, "lam_viec": lam_viec, "srt_vao": srt_vao}


class BatSuKien:
    """Đọc từng dòng output của adapter: tiến độ, cảnh báo, lỗi, kết quả `autosub_done`."""

    def __init__(self, ctx: hang_doi.NguCanh):
        self.ctx = ctx
        self.xong: Optional[dict] = None
        self.loi = ""
        self.canh_bao: List[str] = []
        self.log_loi_dich = ""

    def __call__(self, dong: str) -> None:
        dong = dong.strip()
        if dong.startswith("{"):
            try:
                ev = json.loads(dong)
            except ValueError:
                ev = None
            if isinstance(ev, dict):
                kind = ev.get("event")
                if kind == "autosub_progress":
                    pct = ev.get("percent")
                    self.ctx.bao(float(pct) if isinstance(pct, (int, float)) and pct >= 0 else None, ev.get("message"))
                elif kind == "autosub_done":
                    self.xong = ev
                elif kind == "autosub_error":
                    self.loi = ev.get("error") or "Lỗi không rõ"
                elif kind == "autosub_warn":
                    self.canh_bao.append(ev.get("message") or "")
                    self.ctx.bao(None, ev.get("message"))
                return
        if dong and not dong.startswith("[download]"):
            # Dòng log thường (loguru) — hiện dòng cuối cho người dùng biết còn đang chạy.
            if "Translation attempt" in dong and "failed" in dong:
                self.log_loi_dich = dong.split("failed:", 1)[-1].strip() if "failed:" in dong else dong
            self.ctx.bao(None, dong[-160:])


def chay(ctx: hang_doi.NguCanh, folder: str, loai: str, m: Dict[str, Any], ke_hoach: Dict[str, Any], cwd: str,
         tham_so: Dict[str, Any], dang_ky_media: Callable[..., Dict[str, Any]]) -> Dict[str, Any]:
    """Thân tác vụ chạy trong hàng đợi GPU. Trả `ket_qua` (JSON được) cho client áp vào timeline."""
    su_kien = BatSuKien(ctx)
    log = os.path.join(ke_hoach["lam_viec"], "log.txt")
    code = ctx.chay_doc_dong(ke_hoach["cmd"], cwd, su_kien, log=log)
    if not su_kien.xong:
        raise RuntimeError(su_kien.loi or f"Tác vụ dừng với mã {code} — xem log: {_rel(folder, log)}")
    ev = su_kien.xong
    
    canh_bao = su_kien.canh_bao
    if loai != "dich":
        canh_bao = [w for w in canh_bao if "Bản dịch trùng bản gốc" not in w]
        
    if loai == "dich":
        if any("Bản dịch trùng bản gốc" in w for w in su_kien.canh_bao) or su_kien.log_loi_dich:
            raise RuntimeError("Dịch thất bại: " + (su_kien.log_loi_dich or "Bản dịch giống hệt bản gốc (xem log)."))

    media_id = m.get("id") if m else None
    kq: Dict[str, Any] = {"loai": loai, "media": media_id, "canh_bao": canh_bao, "log": _rel(folder, log)}
    if loai in ("phu-de", "ocr"):
        path = ev.get("srt_source") or ev.get("output")
        cau = srt.phan_tich(srt.doc_file(path)) if path and os.path.exists(path) else []
        if loai == "ocr":
            def loc_cau_ocr(danh_sach: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                loc = []
                for c in danh_sach:
                    txt = str(c.get("text") or "").strip()
                    if not txt or txt.lower() in ("nan", "none"):
                        continue
                    dai = float(c.get("t_ra", 0)) - float(c.get("t_vao", 0))
                    if dai < 0.2:
                        continue
                    chuso = sum(1 for char in txt if char.isalnum())
                    if chuso <= 2 and dai < 0.5:
                        continue
                    
                    if loc:
                        truoc = loc[-1]
                        if truoc["text"] == txt and float(c.get("t_vao", 0)) - float(truoc.get("t_ra", 0)) < 0.3:
                            truoc["t_ra"] = c.get("t_ra")
                            continue
                    loc.append(dict(c))
                return loc
            cau = loc_cau_ocr(cau)

        if not cau:
            raise RuntimeError("Không nhận ra câu nào (video không có lời/chữ, hoặc sai vùng/ngôn ngữ).")
        kq.update(cau=cau, so_cau=len(cau))
        if loai == "ocr":
            kq["vung"] = tham_so.get("vung")
    elif loai == "dich":
        path = ev.get("srt_translated") or ev.get("output")
        cau = srt.phan_tich(srt.doc_file(path)) if path and os.path.exists(path) else []
        ids = tham_so.get("ids") or []
        if len(cau) != len(ids):
            # LLM gộp/tách câu thì không ánh xạ 1-1 được — vẫn trả để người dùng thay cả đợt.
            kq["lech_so_cau"] = True
        kq.update(cau=cau, ids=ids, so_cau=len(cau))
    elif loai == "tach-giong":
        giong = ev.get("vocals")
        nhac = ev.get("no_vocals")
        if not giong or not os.path.exists(giong):
            raise RuntimeError("Tách giọng xong nhưng không thấy file kết quả.")
        m1 = dang_ky_media(folder, giong, m["id"])
        kq.update(media_giong=m1["id"], file_giong=m1["file"])
        if nhac and os.path.exists(nhac):
            m2 = dang_ky_media(folder, nhac, m["id"])
            kq.update(media_nhac=m2["id"], file_nhac=m2["file"])
    elif loai == "lam-net":
        video_net = ev.get("output")
        if not video_net or not os.path.exists(video_net):
            raise RuntimeError("Làm nét xong nhưng không thấy file kết quả.")
        moi = dang_ky_media(folder, video_net, m["id"])
        kq.update(media_moi=moi["id"], file=moi["file"])
    elif loai == "can-gio":
        words_file = ev.get("words")
        if not words_file or not os.path.exists(words_file):
            raise RuntimeError("Căn giờ thất bại (không thấy file kết quả words).")
        with open(words_file, "r", encoding="utf-8") as f:
            words = json.load(f)
        from orchestrator.editor.can_gio import can_gio_phu_de
        cau_hien_tai = tham_so.get("cau", [])
        kq_cau, khong_khop = can_gio_phu_de(cau_hien_tai, words)
        kq.update(cau=kq_cau, so_cau=len(kq_cau), khong_khop=khong_khop)
    elif loai == "tao-anh":
        images = ev.get("images") or []
        seeds = ev.get("seeds") or []
        files = []
        media_moi = []
        for img in images:
            if img and os.path.exists(img):
                try:
                    # m["id"] is not valid because m can be None, so pass None as parent_id
                    parent_id = m.get("id") if m else None
                    moi = dang_ky_media(folder, img, parent_id)
                    media_moi.append(moi["id"])
                    files.append(moi["file"])
                except Exception as e:
                    canh_bao.append(f"Lỗi đăng ký ảnh: {e}")
        kq.update(media_moi=media_moi, files=files, seeds=seeds)
    elif loai == "doc-van-ban":
        wav = ev.get("voiceover")
        if not wav or not os.path.exists(wav):
            raise RuntimeError("Đọc văn bản xong nhưng không thấy file giọng.")
        moi = dang_ky_media(folder, wav, None)
        kq.update(media_moi=moi["id"], file=moi["file"])
    elif loai == "minh-hoa":
        doan = ev.get("doan") or []
        parent_id = m.get("id") if m else None
        kq_doan = []
        for d in doan:
            vid_file = d.get("file")
            if vid_file and os.path.exists(vid_file):
                try:
                    moi = dang_ky_media(folder, vid_file, parent_id)
                    d_moi = dict(d)
                    d_moi["media"] = moi["id"]
                    d_moi["file"] = moi["file"]
                    kq_doan.append(d_moi)
                except Exception as e:
                    canh_bao.append(f"Lỗi đăng ký video {vid_file}: {e}")
        kq.update(doan=kq_doan, so_doan=len(kq_doan))
    else:
        wav = ev.get("voiceover")
        if not wav or not os.path.exists(wav):
            raise RuntimeError("Lồng tiếng xong nhưng không thấy file giọng.")
        moi = dang_ky_media(folder, wav, m["id"])
        kq.update(media_moi=moi["id"], file=moi["file"])
    return kq

def gop_cau_minh_hoa(cau: List[Dict[str, Any]], min_duration: float = 3.0) -> List[Dict[str, Any]]:
    """Gộp các câu phụ đề liên tiếp thành đoạn >= min_duration."""
    if not cau:
        return []
    kq = []
    hien_tai = dict(cau[0])
    
    for c in cau[1:]:
        if float(hien_tai.get("t_ra", 0)) - float(hien_tai.get("t_vao", 0)) >= min_duration:
            kq.append(hien_tai)
            hien_tai = dict(c)
        else:
            hien_tai["t_ra"] = c.get("t_ra", 0)
            text_truoc = str(hien_tai.get("text", "")).strip()
            text_sau = str(c.get("text", "")).strip()
            if text_truoc and text_sau:
                hien_tai["text"] = f"{text_truoc} {text_sau}"
            elif text_sau:
                hien_tai["text"] = text_sau
    
    kq.append(hien_tai)
    return kq



