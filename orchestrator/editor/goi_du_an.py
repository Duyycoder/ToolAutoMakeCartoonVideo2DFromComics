"""Đóng gói dự án thành MỘT file .zip để mang sang máy khác, và mở gói đó thành dự án mới.

Gói chứa nguyên thư mục dự án (`.duan.json`, `.duan/timeline.json`…, `media/`, `phu_de/`, `long_tieng/`, `luts/`) trừ:
khoá cửa sổ (`.duan/lock`), bộ đệm dựng lại được (`.duan/cache`: proxy, thumbnail, sóng âm) và — mặc định — video đã
xuất (`xuat/`). Không nén (ZIP_STORED): video/âm thanh vốn đã nén, nén lại chỉ tốn CPU của server yếu.

Module chỉ đụng hệ thống tệp nên kiểm thử trọn vẹn (tests/test_editor_goi_du_an.py).
"""
import os
import shutil
import uuid
import zipfile
from typing import Any, Callable, Dict, List, Optional, Tuple

from orchestrator.editor import luu_tru, quy_doi
from orchestrator.storage import slugify

DUOI = ".duan.zip"
KHUC = 4 * 1024 * 1024


def _bo_qua(rel: str, kem_xuat: bool) -> bool:
    p = rel.replace("\\", "/")
    if p in (f"{luu_tru.THU_MUC_EDITOR}/lock",) or p.startswith(f"{luu_tru.THU_MUC_EDITOR}/{luu_tru.CACHE}/"):
        return True
    if not kem_xuat and p.startswith(f"{luu_tru.XUAT_DIR}/"):
        return True
    return p.endswith((".tmp", ".part"))


def liet_ke(folder: str, kem_xuat: bool = False) -> List[Tuple[str, str, int]]:
    """[(đường dẫn thật, tên trong gói, kích thước)] của mọi file sẽ vào gói."""
    folder = os.path.abspath(folder)
    out = []
    for goc, _, files in os.walk(folder):
        for f in files:
            p = os.path.join(goc, f)
            rel = os.path.relpath(p, folder).replace("\\", "/")
            if not _bo_qua(rel, kem_xuat) and os.path.isfile(p):
                out.append((p, rel, os.path.getsize(p)))
    return out


def dong_goi(folder: str, dich: str, bao: Optional[Callable[[float], None]] = None, kem_xuat: bool = False) -> int:
    """Ghi gói dự án ra `dich`; `bao(0..1)` báo tiến độ. Trả kích thước gói (byte)."""
    if not os.path.isfile(luu_tru.duong_dan_duan(folder)):
        raise ValueError("Thư mục này không phải dự án.")
    ds = liet_ke(folder, kem_xuat)
    tong = sum(k for _, _, k in ds) or 1
    os.makedirs(os.path.dirname(dich), exist_ok=True)
    tam = dich + ".part"
    xong = 0
    try:
        with zipfile.ZipFile(tam, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for p, rel, _ in ds:
                with open(p, "rb") as f, z.open(zipfile.ZipInfo.from_file(p, rel), "w", force_zip64=True) as g:
                    while True:
                        b = f.read(KHUC)
                        if not b:
                            break
                        g.write(b)
                        xong += len(b)
                        if bao:
                            bao(min(1.0, xong / tong))
        os.replace(tam, dich)
    finally:
        if os.path.exists(tam):
            os.remove(tam)
    return os.path.getsize(dich)


def mo_goi(zip_path: str, workspace: str) -> str:
    """Giải gói vào `workspace/<tên dự án>` (trùng tên thì thêm _2, _3…), trả thư mục dự án mới.

    Dự án nhận id mới nếu id trong gói đã có ở `workspace`… — đơn giản hơn: LUÔN cấp id mới, để nhập cùng một gói hai
    lần vẫn ra hai dự án độc lập. Từ chối gói có đường dẫn thoát ra ngoài thư mục đích (zip-slip).
    """
    try:
        z = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError):
        raise ValueError("File không phải gói dự án (.zip) hợp lệ.")
    with z:
        ten = z.namelist()
        if luu_tru.MARKER not in ten:
            raise ValueError("Gói này không chứa dự án (thiếu .duan.json ở gốc).")
        for n in ten:
            chuan = os.path.normpath(n)
            if os.path.isabs(n) or chuan.startswith("..") or ":" in n or n.startswith(("/", "\\")):
                raise ValueError(f"Gói có đường dẫn không an toàn: {n}")
        import json
        try:
            da = json.loads(z.read(luu_tru.MARKER).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ValueError("File .duan.json trong gói bị hỏng.")
        slug = slugify(str(da.get("name") or "")) or "du-an-nhap"
        folder = os.path.join(workspace, slug)
        lan = 2
        while os.path.exists(folder):
            folder = os.path.join(workspace, f"{slug}_{lan}")
            lan += 1
        os.makedirs(folder)
        try:
            z.extractall(folder)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def sua(d):
        d["id"] = uuid.uuid4().hex[:8]
        d["tac_vu"] = [t for t in d.get("tac_vu", []) if t.get("trang_thai") not in ("cho", "dang_chay")]
        return True
    luu_tru.sua_duan(folder, sua)
    khoa = os.path.join(luu_tru.thu_muc_editor(folder), "lock")
    if os.path.exists(khoa):
        os.remove(khoa)
    return folder


# ------------------------------------------------ Xuất sang Videoedit (concat.json)
CONCAT_VERSION = 2
CONCAT_SCHEMA = "0.1.0"
_FPS_CHUAN = ((23.976, 24000, 1001), (29.97, 30000, 1001), (59.94, 60000, 1001))


def _chuyen_fps(fps_raw: Any) -> Tuple[int, int]:
    try:
        fps = float(fps_raw or 30)
    except (TypeError, ValueError):
        return 30, 1
    if fps <= 0:
        return 30, 1
    for moc, num, den in _FPS_CHUAN:
        if abs(fps - moc) < 0.02:
            return num, den
    if abs(fps - round(fps)) < 1e-3:
        return max(1, int(round(fps))), 1
    return max(1, int(round(fps * 1000))), 1000


def _tim_nguon_media(folder: str, m: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Trả (đường dẫn nguồn trên đĩa hoặc None, đường dẫn tương đối đích trong dự án Videoedit)."""
    rel_raw = str(m.get("file") or "").replace("\\", "/").strip("/")
    if rel_raw:
        try:
            p = luu_tru.duong_dan_media(folder, rel_raw)
            if os.path.isfile(p):
                return p, rel_raw
        except ValueError:
            if os.path.isfile(rel_raw):
                return os.path.abspath(rel_raw), f"media/{os.path.basename(rel_raw)}"
    nguon = str(m.get("nguon") or "").strip()
    if nguon and os.path.isfile(nguon):
        return os.path.abspath(nguon), rel_raw or f"media/{os.path.basename(nguon)}"
    return None, rel_raw or f"media/{m.get('id', 'file')}"


def _chep_file(src: str, dst: str, bao_byte: Callable[[int], None]) -> None:
    if os.path.normcase(os.path.abspath(src)) == os.path.normcase(os.path.abspath(dst)):
        bao_byte(os.path.getsize(src))
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tam = dst + ".part"
    try:
        with open(src, "rb") as f, open(tam, "wb") as g:
            while True:
                b = f.read(KHUC)
                if not b:
                    break
                g.write(b)
                bao_byte(len(b))
        os.replace(tam, dst)
    finally:
        if os.path.exists(tam):
            try:
                os.remove(tam)
            except OSError:
                pass


def _text_mac_dinh(content: str, **overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "align": "center",
        "background": "",
        "backgroundPaddingX": 0.0315,
        "backgroundPaddingY": 0.018,
        "backgroundRadius": 0.0135,
        "color": "#ffffff",
        "content": content,
        "fontFamily": "Hanken Grotesk",
        "fontSize": 0.045,
        "fontWeight": 700.0,
        "italic": False,
        "lineHeight": 1.2,
        "maxHeight": 0.0,
        "maxWidth": 0.0,
        "opacity": 1.0,
        "shadow": True,
        "strikethrough": False,
        "strokeColor": "#000000",
        "strokeWidth": 0.004,
        "textCase": "original",
        "tracking": 0.0,
        "underline": False,
    }
    base.update(overrides)
    return base


def _clip_text(cid: str, track_id: str, start: float, duration: float, offset_x: float,
               offset_y: float, scale: float, rotation: float, opacity: float,
               text_obj: Dict[str, Any]) -> Dict[str, Any]:
    first_line = next((ln.strip() for ln in str(text_obj.get("content") or "").splitlines() if ln.strip()), "Text")
    return {
        "id": cid,
        "kind": "text",
        "mediaId": "",
        "name": first_line[:60],
        "trackId": track_id,
        "start": round(max(0.0, start), 6),
        "duration": round(max(0.01, duration), 6),
        "sourceStart": 0.0,
        "speed": 1.0,
        "volume": 1.0,
        "preservePitch": True,
        "fadeIn": 0.0,
        "fadeOut": 0.0,
        "offsetX": round(offset_x, 6),
        "offsetY": round(offset_y, 6),
        "scale": round(scale, 6),
        "rotation": round(rotation, 6),
        "opacity": round(opacity, 6),
        "filters": [],
        "videoEffects": [],
        "text": text_obj,
    }


def _chuyen_keyframes(kf_raw: Any, duration: float) -> Dict[str, List[Dict[str, Any]]]:
    if not isinstance(kf_raw, dict) or duration <= 0:
        return {}
    anh_xa = {
        "bien_doi.x": ("offsetX", lambda v: float(v) - 0.5),
        "bien_doi.y": ("offsetY", lambda v: float(v) - 0.5),
        "bien_doi.ti_le": ("scale", float),
        "bien_doi.xoay": ("rotation", float),
        "hien_thi.do_mo": ("opacity", float),
        "am_luong": ("volume", float),
    }
    ease_map = {
        "tuyen_tinh": [0.0, 0.0, 1.0, 1.0],
        "vao": [0.42, 0.0, 1.0, 1.0],
        "ra": [0.0, 0.0, 0.58, 1.0],
        "vao_ra": [0.42, 0.0, 0.58, 1.0],
    }
    out: Dict[str, List[Dict[str, Any]]] = {}
    for src_k, (dst_k, fn) in anh_xa.items():
        pts = kf_raw.get(src_k)
        if not isinstance(pts, list) or not pts:
            continue
        ds = []
        for p in sorted(pts, key=lambda x: float(x.get("t") or 0)):
            at = max(0.0, min(1.0, float(p.get("t") or 0) / duration))
            ds.append({
                "at": round(at, 6),
                "value": round(fn(p.get("v") or 0), 6),
                "ease": ease_map.get(p.get("em"), [0.0, 0.0, 1.0, 1.0]),
            })
        if ds:
            out[dst_k] = ds
    return out


def chuyen_sang_concat(da: Dict[str, Any], tl: Dict[str, Any],
                       media_paths: Dict[str, str]) -> Dict[str, Any]:
    """Chuyển dữ liệu `.duan.json` + `.duan/timeline.json` sang cấu trúc `concat.json` của Videoedit."""
    ts = da.get("thong_so") or {}
    w = int(ts.get("rong") or 1920)
    h = int(ts.get("cao") or 1080)
    rate_num, rate_den = _chuyen_fps(ts.get("fps"))
    video_obj = {"width": w, "height": h, "rateNum": rate_num, "rateDen": rate_den}

    media_list: List[Dict[str, Any]] = []
    media_map: Dict[str, Dict[str, Any]] = {}
    for m in da.get("media") or []:
        loai = m.get("loai") or "video"
        if loai not in ("video", "audio", "anh"):
            continue
        kind = "image" if loai == "anh" else loai
        mid = str(m.get("id") or "")
        dst_path = media_paths.get(mid) or ""
        fps_m = m.get("fps")
        item: Dict[str, Any] = {
            "id": mid,
            "kind": kind,
            "name": str(m.get("ten") or os.path.basename(dst_path) or mid),
            "path": dst_path,
            "duration": 0.04 if kind == "image" else float(m.get("thoi_luong") or 0.0),
            "width": int(m["rong"]) if m.get("rong") else None,
            "height": int(m["cao"]) if m.get("cao") else None,
            "frameRate": float(fps_m) if fps_m else (25.0 if kind == "image" else None),
            "frameRateFraction": f"{int(round(float(fps_m)))}/1" if fps_m else ("25/1" if kind == "image" else None),
            "hasAudio": bool(m.get("co_am_thanh", kind == "audio")),
            "videoCodec": m.get("codec") or None,
            "audioCodec": m.get("codec_am") or None,
        }
        media_list.append(item)
        media_map[mid] = m

    # Videoedit vẽ track sau đè lên track trước; editor bên này track đầu đè lên track sau -> đảo ngược.
    # Nhưng phụ đề và chữ/hình bên này được đốt bằng ASS đè lên MỌI video (chu_hinh.tao_ass), nên các
    # track đó phải nằm trên mọi track hình, không thì Videoedit vẽ video che mất phụ đề.
    loai_tren_track: Dict[str, set] = {}
    for c in tl.get("clips") or []:
        loai_tren_track.setdefault(str(c.get("track") or ""), set()).add(c.get("loai"))

    def _ve_bang_ass(t: Dict[str, Any]) -> bool:
        loai = loai_tren_track.get(str(t["id"]))
        return t.get("loai") == "phu_de" or bool(loai) and loai <= {"chu", "hinh"}

    tracks_dao = [t for t in reversed(tl.get("tracks") or []) if t.get("id")]
    tracks_out = [
        {
            "id": str(t["id"]),
            "muted": bool(t.get("tat_tieng", False)),
            "visible": not bool(t.get("an", False)),
        }
        for t in sorted(tracks_dao, key=_ve_bang_ass)  # sorted giữ thứ tự: track hình dưới, track ASS trên
    ]

    kieu_pd_map = tl.get("kieu_phu_de") or {}
    mac_dinh_pd = luu_tru.kieu_phu_de_mac_dinh()
    clips_out: List[Dict[str, Any]] = []
    used_ids = set()

    def _unique_id(base_id: str) -> str:
        cid = base_id
        n = 2
        while cid in used_ids:
            cid = f"{base_id}_{n}"
            n += 1
        used_ids.add(cid)
        return cid

    for c in tl.get("clips") or []:
        loai_c = c.get("loai") or ""
        track_id = str(c.get("track") or "")
        if not track_id:
            continue

        if loai_c == "phu_de":
            noi_dung = str(c.get("text") or "").strip()
            if not noi_dung:
                continue
            st = {**mac_dinh_pd, **(kieu_pd_map.get(c.get("kieu") or "k_mac_dinh") or {})}
            co = float(st.get("co") or 48)
            vy = float(st.get("vi_tri_y") if st.get("vi_tri_y") is not None else 0.9)
            nen_raw = str(st.get("nen") or "")
            bg = "" if nen_raw in ("", "None", "none") else nen_raw
            do_day = float(st.get("do_day_vien") if st.get("do_day_vien") is not None else 2)
            text_obj = _text_mac_dinh(
                noi_dung,
                fontFamily=str(st.get("font") or "") or "Hanken Grotesk",
                fontSize=round(co / 1080.0, 6),
                color=str(st.get("mau") or "#ffffff"),
                strokeColor=str(st.get("vien") or "#000000"),
                strokeWidth=round(do_day / 1080.0, 6),
                background=bg,
            )
            for k in quy_doi.hien_thi(tl, c):
                dur = k["kt"] - k["bd"]
                if dur <= 1e-4:
                    continue
                clips_out.append(_clip_text(
                    _unique_id(str(c.get("id") or "txt")), track_id,
                    k["bd"], dur, 0.0, vy - 0.5, 1.0, 0.0, 1.0, dict(text_obj),
                ))
            continue

        if loai_c == "chu":
            noi_dung = str(c.get("text") or "").strip()
            if not noi_dung:
                continue
            bd = float(c.get("bat_dau") or 0.0)
            dur = quy_doi.ket_thuc(c) - bd
            if dur <= 1e-4:
                continue
            b = c.get("bien_doi") or {}
            h_thi = c.get("hien_thi") or {}
            k = c.get("kieu") or {}
            co = float(k.get("co") or 48)
            nen_mau = str(k.get("nen_mau") or "#00000099") if k.get("nen") else ""
            vien_day = float(k.get("vien_day") or 0)
            text_obj = _text_mac_dinh(
                noi_dung,
                fontFamily=str(k.get("font") or "") or "Hanken Grotesk",
                fontSize=round(co / 1080.0, 6),
                fontWeight=700.0 if k.get("dam", True) else 400.0,
                italic=bool(k.get("nghieng", False)),
                color=str(k.get("mau") or "#ffffff"),
                strokeColor=str(k.get("vien_mau") or "#000000"),
                strokeWidth=round(vien_day / 1080.0, 6) if vien_day > 0 else 0.0,
                background=nen_mau,
                shadow=bool(k.get("bong", True)),
            )
            clips_out.append(_clip_text(
                _unique_id(str(c.get("id") or "chu")), track_id,
                bd, dur,
                float(b.get("x", 0.5)) - 0.5,
                float(b.get("y", 0.5)) - 0.5,
                float(b.get("ti_le", 1.0)),
                float(b.get("xoay", 0.0)),
                float(h_thi.get("do_mo", 1.0)),
                text_obj,
            ))
            continue

        mid = str(c.get("media") or "")
        m = media_map.get(mid)
        if not m:
            continue
        kind = "image" if m.get("loai") == "anh" else str(m.get("loai") or "video")
        bd = float(c.get("bat_dau") or 0.0)
        vao = float(c.get("vao") or 0.0)
        toc_do = float(c.get("toc_do") or 1.0)
        if toc_do <= 0:
            toc_do = 1.0
        if c.get("ra") is not None:
            dur = max(0.01, (float(c["ra"]) - vao) / toc_do)
        else:
            dur = max(0.01, quy_doi.ket_thuc(c) - bd)
        b = c.get("bien_doi") or {}
        h_thi = c.get("hien_thi") or {}
        clip_obj: Dict[str, Any] = {
            "id": _unique_id(str(c.get("id") or "c")),
            "kind": kind,
            "mediaId": mid,
            "name": str(m.get("ten") or os.path.basename(media_paths.get(mid) or "") or mid),
            "trackId": track_id,
            "start": round(max(0.0, bd), 6),
            "duration": round(dur, 6),
            "sourceStart": round(max(0.0, vao), 6),
            "speed": round(toc_do, 6),
            "volume": round(float(c.get("am_luong") if c.get("am_luong") is not None else 1.0), 6),
            "preservePitch": True,
            "fadeIn": round(float(c.get("am_vao") or 0.0), 6),
            "fadeOut": round(float(c.get("am_ra") or 0.0), 6),
            "offsetX": round(float(b.get("x", 0.5)) - 0.5, 6),
            "offsetY": round(float(b.get("y", 0.5)) - 0.5, 6),
            "scale": round(float(b.get("ti_le", 1.0)), 6),
            "rotation": round(float(b.get("xoay", 0.0)), 6),
            "opacity": round(float(h_thi.get("do_mo", 1.0)), 6),
            "filters": [],
            "videoEffects": [],
        }
        if c.get("tat_am"):
            clip_obj["muted"] = True
        kfs = _chuyen_keyframes(c.get("keyframes"), dur)
        if kfs:
            clip_obj["keyframes"] = kfs
        clips_out.append(clip_obj)

    ten = str(da.get("name") or "Du an").strip() or "Du an"
    return {
        "version": CONCAT_VERSION,
        "concat": CONCAT_SCHEMA,
        "name": ten,
        "activeTimelineId": "TL1",
        "video": video_obj,
        "fonts": [],
        "media": media_list,
        "tracks": tracks_out,
        "clips": clips_out,
        "timelines": [
            {
                "id": "TL1",
                "name": "Timeline 1",
                "video": dict(video_obj),
                "tracks": list(tracks_out),
                "clips": list(clips_out),
            }
        ],
    }


def xuat_videoedit(folder: str, dich_dir: str,
                   bao: Optional[Callable[[float], None]] = None) -> Dict[str, Any]:
    """Xuất dự án ra thư mục định dạng Videoedit (`concat.json` + các file media)."""
    if not os.path.isfile(luu_tru.duong_dan_duan(folder)):
        raise ValueError("Thư mục này không phải dự án.")
    dich_text = (dich_dir or "").strip()
    if not dich_text:
        raise ValueError("Phải chọn hoặc nhập đường dẫn thư mục đích.")
    folder_abs = os.path.abspath(folder)
    dich_abs = os.path.abspath(dich_text)
    if os.path.normcase(folder_abs) == os.path.normcase(dich_abs):
        raise ValueError("Thư mục đích không được trùng với thư mục dự án gốc.")

    da = luu_tru.doc_duan(folder_abs)
    if da is None:
        raise ValueError("Không đọc được file .duan.json.")
    tl, _ = luu_tru.doc_timeline(folder_abs)

    os.makedirs(dich_abs, exist_ok=True)
    ke_hoach: List[Tuple[str, str, int, str]] = []
    media_paths: Dict[str, str] = {}
    for m in da.get("media") or []:
        mid = str(m.get("id") or "")
        src, rel = _tim_nguon_media(folder_abs, m)
        dst = os.path.abspath(os.path.join(dich_abs, *rel.split("/")))
        media_paths[mid] = dst
        if src and os.path.isfile(src):
            ke_hoach.append((src, dst, os.path.getsize(src), mid))

    tong = sum(k for _, _, k, _ in ke_hoach) or 1
    xong = 0

    def _bao(n: int) -> None:
        nonlocal xong
        xong += n
        if bao:
            bao(min(0.99, xong / tong))

    for src, dst, _, _ in ke_hoach:
        _chep_file(src, dst, _bao)

    concat_data = chuyen_sang_concat(da, tl, media_paths)
    luu_tru.ghi_nguyen_tu(os.path.join(dich_abs, "concat.json"), concat_data)
    if bao:
        bao(1.0)
    return {
        "thu_muc": dich_abs,
        "concat_json": os.path.join(dich_abs, "concat.json"),
        "so_media": len(concat_data["media"]),
        "so_clip": len(concat_data["clips"]),
        "kich_thuoc": xong,
    }
