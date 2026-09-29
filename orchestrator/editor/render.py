"""Dựng lệnh ffmpeg xuất video từ `timeline.json` + `.duan.json` (docs/PLAN-editor.md mục 4).

Module THUẦN: chỉ dựng lệnh + nội dung file (filter script, .ass), không chạy ffmpeg — pytest
kiểm được từng loại clip. `api.py` ghi file vào `.duan/cache/xuat/` rồi chạy với cwd đó, nên
mọi đường dẫn TRONG filter là tên tương đối ASCII (`sub.ass`) — khỏi escape `C\\:` và dấu tiếng Việt.

Sơ đồ:
    V1: mỗi clip = 1 input (-ss vao -t dai), chuẩn hoá (che phụ đề → tốc độ → fps → khung dự án);
        khoảng trống = khung màu nền. Ghép bằng concat (nhanh, không chồng overlay dài).
    Âm thanh: tiếng của clip V1 (im lặng nếu ảnh/không tiếng/tắt tiếng) đi cùng concat;
        clip ở các track âm thanh = input riêng, adelay tới đúng chỗ, amix.
        Track lồng tiếng (vai=long_tieng): nhạc nền tự giảm khi có lời (sidechaincompress).
    Phụ đề: .ass sinh từ track phụ đề (giờ đã quy đổi theo clip) → subtitles=sub.ass.
Bản xuất luôn dùng file GỐC, không dùng proxy.
"""
import os
from typing import Any, Dict, List, Optional, Tuple

from orchestrator.editor import hieu_ung, luu_tru, quy_doi, srt, chu_hinh

SR = 48000
DO_PHAN_GIAI = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}

# Giải thích: Danh sách kiểu chuyển cảnh xfade mà ffmpeg hỗ trợ — liệt kê cố định,
# test Python kiểm mỗi kiểu có trong `ffmpeg -h filter=xfade`.
CAC_KIEU_XFADE = [
    "fade", "fadeblack", "fadewhite", "distance", "wipeleft", "wiperight",
    "wipeup", "wipedown", "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circlecrop", "circleopen", "circleclose", "vertopen", "vertclose",
    "horzopen", "horzclose", "dissolve", "pixelize", "diagtl", "diagtr",
    "diagbl", "diagbr", "hlslice", "hrslice", "vuslice", "vdslice",
    "radial", "zoomin", "wipetl", "wipetr", "wipebl", "wipebr",
    "squeezeh", "squeezev",
]


def tinh_xfade(clips, chuyen_canh, media_info=None):
    """Hàm thuần tính thông tin offset/tpad cho chuỗi clip track nền có chuyển cảnh.

    Tham số:
        clips: danh sách clip dict, ĐÃ SẮP theo bat_dau, chỉ track nền.
        chuyen_canh: danh sách chuyển cảnh [{truoc, sau, loai, dai}].
        media_info: dict {media_id: {loai, thoi_luong, ...}}, None nếu bỏ qua tpad.

    Trả về: danh sách dict cho mỗi clip:
        {vao_moi, ra_moi, pad_truoc, pad_sau, truoc_cc, sau_cc, original_dai}

    Giải thích quy ước: chuyển cảnh nằm GIỮA điểm cắt, chiếm dai/2 cuối clip trước
    và dai/2 đầu clip sau. Timeline KHÔNG đổi khi thêm chuyển cảnh.
    """
    cc_map = {(cc.get("truoc"), cc.get("sau")): cc for cc in chuyen_canh or []}
    co_media = media_info is not None
    media_info = media_info or {}
    ket_qua = []

    for i, c in enumerate(clips):
        vao = float(c.get("vao") or 0)
        ra = float(c.get("ra") or 0)
        toc = float(c.get("toc_do") or 1)
        original_dai = (ra - vao) / toc

        # Giải thích: Tìm chuyển cảnh ở hai đầu, chỉ giữa 2 clip kề nhau (sai số ≤ 0.05s).
        truoc_cc = None
        sau_cc = None
        if i > 0:
            c_prev = clips[i - 1]
            kt_prev = float(c_prev.get("bat_dau", 0)) + (float(c_prev.get("ra", 0)) - float(c_prev.get("vao", 0))) / float(c_prev.get("toc_do", 1))
            if abs(kt_prev - float(c.get("bat_dau", 0))) <= 0.05:
                truoc_cc = cc_map.get((c_prev["id"], c["id"]))
        if i < len(clips) - 1:
            c_next = clips[i + 1]
            kt_cur = float(c.get("bat_dau", 0)) + original_dai
            if abs(kt_cur - float(c_next.get("bat_dau", 0))) <= 0.05:
                sau_cc = cc_map.get((c["id"], c_next["id"]))

        dai_truoc = float(truoc_cc["dai"]) / 2 if truoc_cc else 0
        dai_sau = float(sau_cc["dai"]) / 2 if sau_cc else 0

        vao_moi = vao - dai_truoc * toc
        ra_moi = ra + dai_sau * toc

        pad_truoc = 0.0
        pad_sau = 0.0
        m = media_info.get(c.get("media")) or {}
        dai_media = float(m.get("thoi_luong") or 1e9)
        is_anh = m.get("loai") == "anh"

        # Không có media_info (gọi thuần để tính offset) thì giữ nguyên vao/ra mở rộng, không quy ra tpad.
        if co_media and not is_anh:
            if vao_moi < 0:
                pad_truoc = -vao_moi / toc
                vao_moi = 0
            if ra_moi > dai_media:
                pad_sau = (ra_moi - dai_media) / toc
                ra_moi = dai_media

        ket_qua.append({
            "vao_moi": vao_moi, "ra_moi": ra_moi,
            "pad_truoc": pad_truoc, "pad_sau": pad_sau,
            "truoc_cc": truoc_cc, "sau_cc": sau_cc,
            "original_dai": original_dai,
        })

    return ket_qua


def tong_thoi_luong_xfade(clips, chuyen_canh):
    """Tổng thời lượng của chuỗi clip: phải bằng tổng timeline gốc (vì timeline không đổi)."""
    thong_tin = tinh_xfade(clips, chuyen_canh)
    if not thong_tin:
        return 0.0
    return sum(tt["original_dai"] for tt in thong_tin)


def _chan(x: float) -> int:
    x = int(round(x))
    return max(2, x - x % 2)


def kich_thuoc_xuat(thong_so: Dict[str, Any], lua_chon: str = "") -> Tuple[int, int]:
    """Khung xuất: theo dự án, hoặc đổi cạnh NGẮN về 720/1080/1440/2160 (giữ tỉ lệ)."""
    rong, cao = int(thong_so.get("rong") or 1920), int(thong_so.get("cao") or 1080)
    dich = DO_PHAN_GIAI.get((lua_chon or "").lower())
    if not dich:
        return _chan(rong), _chan(cao)
    k = dich / min(rong, cao)
    return _chan(rong * k), _chan(cao * k)


def _so(x: float) -> str:
    return f"{float(x):.5f}".rstrip("0").rstrip(".") or "0"


def bieu_thuc(ds: List[Dict[str, Any]], bien: str = 't', lech: float = 0.0) -> str:
    if not ds:
        return ""
    diem = sorted(ds, key=lambda x: float(x["t"]))
    if len(diem) == 1:
        return _so(diem[0]["v"])
        
    expr = _so(diem[-1]["v"])
    for i in range(len(diem) - 2, -1, -1):
        d1, d2 = diem[i], diem[i + 1]
        t1, t2 = float(d1["t"]) + lech, float(d2["t"]) + lech
        v1, v2 = float(d1["v"]), float(d2["v"])
        em = d1.get("em", "tuyen_tinh")
        
        if abs(t2 - t1) < 1e-4:
            continue
            
        dt = t2 - t1
        tl = f"(({bien}-{_so(t1)})/{_so(dt)})"
        
        if em == "giu":
            val = _so(v1)
        else:
            f = tl
            if em == "vao_ra":
                f = f"({tl}*{tl}*(3-2*{tl}))"
            dv = v2 - v1
            if dv >= 0:
                val = f"({_so(v1)}+{_so(dv)}*{f})"
            else:
                val = f"({_so(v1)}-{_so(-dv)}*{f})"
                
        expr = f"if(lt({bien}\\,{_so(t2)})\\,{val}\\,{expr})"
        
    t0 = float(diem[0]["t"]) + lech
    expr = f"if(lt({bien}\\,{_so(t0)})\\,{_so(diem[0]['v'])}\\,{expr})"
    return expr


def _atempo(toc: float) -> str:
    """atempo chỉ nhận 0.5–2 mỗi tầng → xâu chuỗi cho tốc độ ngoài khoảng đó."""
    toc = float(toc or 1)
    if abs(toc - 1) < 1e-6:
        return ""
    phan = []
    while toc > 2.0:
        phan.append("atempo=2.0")
        toc /= 2.0
    while toc < 0.5:
        phan.append("atempo=0.5")
        toc /= 0.5
    phan.append(f"atempo={toc:.6f}")
    return "," + ",".join(phan)


def _mau(hex_mau: str) -> str:
    h = (hex_mau or "#000000").lstrip("#")
    return "0x" + ((h * 2 if len(h) == 3 else h) + "000000")[:6]


def la_lop_mac_dinh(c: Dict[str, Any]) -> bool:
    kf = c.get("keyframes") or {}
    for d in ["bien_doi.x", "bien_doi.y", "bien_doi.ti_le", "bien_doi.xoay", "hien_thi.do_mo", "hien_thi.bo_goc"]:
        if d in kf and kf[d]:
            return False
    b, k, h = c.get("bien_doi") or {}, c.get("cat_khung") or {}, c.get("hien_thi") or {}
    return (float(b.get("x", 0.5)) == 0.5 and float(b.get("y", 0.5)) == 0.5 and float(b.get("ti_le", 1)) == 1
            and not float(b.get("xoay") or 0) and not any(float(k.get(x) or 0) for x in ("trai", "phai", "tren", "duoi"))
            and float(h.get("do_mo", 1)) == 1 and not float(h.get("bo_goc") or 0))


def hop_lop(c: Dict[str, Any], m: Dict[str, Any], W: int, H: int) -> Dict[str, float]:
    """Hộp của lớp trong khung W×H — khớp `store.hopLop` bên JS (xem trước)."""
    b = {"x": 0.5, "y": 0.5, "ti_le": 1, "xoay": 0, **(c.get("bien_doi") or {})}
    mw, mh = float(m.get("rong") or W), float(m.get("cao") or H)
    k = min(W / mw, H / mh) * float(b.get("ti_le") or 1)
    return {"cx": float(b["x"]) * W, "cy": float(b["y"]) * H, "w": mw * k, "h": mh * k, "xoay": float(b.get("xoay") or 0)}


def _loc_che(c: Dict[str, Any], a: float, b: float, m: Dict[str, Any], nhan: str) -> List[str]:
    """Chuỗi filter che một vùng (tỉ lệ 0–1 theo khung media) từ giây a tới b (giờ cục bộ của clip)."""
    v = c.get("vung") or {}
    x, y = max(0.0, float(v.get("x", 0))), max(0.0, float(v.get("y", 0)))
    w, h = min(1.0 - x, float(v.get("w", 0.1))), min(1.0 - y, float(v.get("h", 0.1)))
    if w <= 0.002 or h <= 0.002:
        return []
    bat = f"enable='between(t,{_so(a)},{_so(b)})'"
    kieu = c.get("kieu") or "blur"
    manh = max(1.0, float(c.get("do_manh") or 20))
    if kieu == "mau":
        return [f"drawbox=x=iw*{x:.4f}:y=ih*{y:.4f}:w=iw*{w:.4f}:h=ih*{h:.4f}:color={_mau(c.get('mau'))}@1:t=fill:{bat}"]
    if kieu == "delogo" and m.get("rong") and m.get("cao"):
        W, H = int(m["rong"]), int(m["cao"])
        dx, dy = max(1, int(x * W)), max(1, int(y * H))
        dw, dh = min(W - dx - 1, max(2, int(w * W))), min(H - dy - 1, max(2, int(h * H)))
        if dw > 1 and dh > 1:
            return [f"delogo=x={dx}:y={dy}:w={dw}:h={dh}:{bat}"]
    if kieu == "mosaic":
        k = max(2, int(manh / 2))
        mo = f"scale=trunc(iw/{k}/2)*2+2:trunc(ih/{k}/2)*2+2:flags=area,scale=iw*{k}:ih*{k}:flags=neighbor"
    else:
        mo = f"gblur=sigma={manh / 2:.1f}"
    return [f"split[{nhan}a][{nhan}b]",
            f"[{nhan}b]crop=iw*{w:.4f}:ih*{h:.4f}:iw*{x:.4f}:ih*{y:.4f},{mo}[{nhan}c]",
            f"[{nhan}a][{nhan}c]overlay=x=main_w*{x:.4f}:y=main_h*{y:.4f}:{bat}"]


class DungLenh:
    def __init__(self, folder: str, du_an: Dict[str, Any], tl: Dict[str, Any], tuy_chon: Dict[str, Any],
                 ffmpeg: str = "ffmpeg"):
        self.folder = os.path.abspath(folder)
        self.du_an = du_an
        self.tl = tl
        self.tc = tuy_chon or {}
        self.ffmpeg = ffmpeg
        self.media = {m["id"]: m for m in du_an.get("media") or []}
        ts = du_an.get("thong_so") or {}
        self.W, self.H = kich_thuoc_xuat(ts, self.tc.get("do_phan_giai") or "")
        self.fps = float(self.tc.get("fps") or ts.get("fps") or 30)
        self.nen = _mau(ts.get("mau_nen") or "#000000")
        self.vao: List[List[str]] = []      # các nhóm tham số đầu vào
        self.loc: List[str] = []            # các dòng filter_complex
        self.tracks = {t["id"]: t for t in tl.get("tracks") or []}

    # ------------------------------------------------------------ tiện ích
    def _input(self, *tham_so: str) -> int:
        self.vao.append(list(tham_so))
        return len(self.vao) - 1

    def _file(self, m: Dict[str, Any]) -> str:
        return luu_tru.duong_dan_media(self.folder, m["file"])

    def thoi_luong(self) -> float:
        dai = 0.0
        for c in self.tl.get("clips") or []:
            if quy_doi.la_neo(c) or c.get("loai") == "phu_de":
                continue
            tr = self.tracks.get(c.get("track")) or {}
            if tr.get("loai") in ("video", "audio"):
                dai = max(dai, quy_doi.ket_thuc(c))
        return round(dai, 3)

    def _clip_track(self, loai: str, bo_an: bool = True) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        out = []
        for c in self.tl.get("clips") or []:
            tr = self.tracks.get(c.get("track")) or {}
            if tr.get("loai") != loai or c.get("loai") or not c.get("media"):
                continue
            if bo_an and tr.get("an"):
                continue
            if c.get("media") not in self.media:
                continue
            out.append((c, tr))
        return sorted(out, key=lambda x: float(x[0].get("bat_dau") or 0))

    # ------------------------------------------------------------ hình (V1)
    def _doan_video(self, c: Dict[str, Any], tr: Dict[str, Any], i: int, chi_video: bool = False) -> Tuple[str, str, float]:
        """Một clip của track NỀN → đoạn hình W×H (+ tiếng) đúng độ dài cho concat."""
        k, nhan, dai = self._nguon_lop(c, str(i))
        nv = f"v{i}"
        if la_lop_mac_dinh(c):
            m = self.media[c["media"]]
            mr, mc = float(m.get("rong") or self.W), float(m.get("cao") or self.H)
            ratio = min(self.W / mr, self.H / mc)
            cw, ch = _chan(mr * ratio), _chan(mc * ratio)
            
            cac_loc = hieu_ung.loc_mau(c.get("mau") or {}) + hieu_ung.loc_hieu_ung(c.get("hieu_ung") or [], cw, ch)
            if not cac_loc and abs(mr - self.W) < 1e-3 and abs(mc - self.H) < 1e-3:
                chuoi_loc = f"setsar=1,format=yuv420p,fps={_so(self.fps)}"
            else:
                chuoi_loc = f"scale={self.W}:{self.H}:force_original_aspect_ratio=decrease:flags=bicubic"
                if cac_loc:
                    chuoi_loc += "," + ",".join(cac_loc)
                # fps= ở cuối: setpts phía trước làm luồng mất tốc độ khung (1/0) — xfade từ chối đầu vào như vậy.
                chuoi_loc += f",pad={self.W}:{self.H}:(ow-iw)/2:(oh-ih)/2:color={self.nen},setsar=1,format=yuv420p,fps={_so(self.fps)}"
            self.loc.append(f"[{nhan}]{chuoi_loc}[{nv}]")
        else:
            lop, x, y = self._lop(c, nhan, str(i), lech_t=0.0)
            self.loc.append(f"color=c={self.nen}:s={self.W}x{self.H}:r={_so(self.fps)}:d={_so(dai)},format=yuv420p[nn{i}]")
            hoa_tron = c.get("hien_thi", {}).get("hoa_tron", "normal")
            if hoa_tron != "normal":
                self.loc.append(f"color=c=black@0:s={self.W}x{self.H}:r={_so(self.fps)}:d={_so(dai)},format=yuva420p[tr{i}]")
                self.loc.append(f"[tr{i}][{lop}]overlay=x='{x}':y='{y}':eof_action=pass:eval=frame[pd{i}]")
                self.loc.append(f"[nn{i}][pd{i}]blend=all_mode={hoa_tron},format=yuv420p,setsar=1,fps={_so(self.fps)}[{nv}]")
            else:
                self.loc.append(f"[nn{i}][{lop}]overlay=x='{x}':y='{y}':eof_action=pass:format=auto:eval=frame,format=yuv420p,setsar=1,fps={_so(self.fps)}[{nv}]")
        
        if chi_video:
            return nv, "", dai
            
        na = f"a{i}"
        if not self._tieng_clip(c, k, tr, dai, na):
            self.loc.append(f"anullsrc=r={SR}:cl=stereo,atrim=duration={_so(dai)}[{na}]")
        return nv, na, dai

    def _nguon_lop(self, c: Dict[str, Any], i: str) -> Tuple[int, str, float]:
        """Đầu vào + che phụ đề + tốc độ + fps cho MỘT clip → (chỉ số input, nhãn luồng hình, độ dài)."""
        m = self.media[c["media"]]
        vao, ra = float(c.get("vao") or 0), float(c.get("ra") or 0)
        toc = float(c.get("toc_do") or 1)
        dai = (ra - vao) / toc
        pad_truoc = float(c.get("pad_truoc") or 0)
        pad_sau = float(c.get("pad_sau") or 0)
        dai_xuat = dai + pad_truoc + pad_sau
        
        cur = f"s{i}"
        if m.get("loai") == "anh":
            k = self._input("-loop", "1", "-framerate", _so(self.fps), "-t", _so(dai_xuat), "-i", self._file(m))
            self.loc.append(f"[{k}:v]setpts=PTS-STARTPTS[{cur}]")
        else:
            if self.tc.get("bo_ma_hoa") == "nvenc":
                k = self._input("-hwaccel", "cuda", "-ss", _so(vao), "-t", _so(ra - vao), "-i", self._file(m))
            else:
                k = self._input("-ss", _so(vao), "-t", _so(ra - vao), "-i", self._file(m))
            self.loc.append(f"[{k}:v]setpts=PTS-STARTPTS[{cur}]")
            for j, che in enumerate(self._che_cho(m["id"])):
                a, b = max(0.0, float(che["t_vao"]) - vao), min(float(che["t_ra"]) - vao, ra - vao)
                if b <= a:
                    continue
                nhan = f"ch{i}_{j}"
                cac = _loc_che(che, a, b, m, nhan)
                if not cac:
                    continue
                sau = f"s{i}_{j}"
                if len(cac) == 1:
                    self.loc.append(f"[{cur}]{cac[0]}[{sau}]")
                else:
                    self.loc.append(f"[{cur}]{cac[0]}")
                    self.loc.append(cac[1])
                    self.loc.append(f"{cac[2]}[{sau}]")
                cur = sau
        
        toc_s = f"setpts=PTS/{toc:.6f}," if abs(toc - 1) > 1e-6 else ""
        tpad_str = ""
        if pad_truoc > 0 or pad_sau > 0:
            parts = []
            if pad_truoc > 0:
                parts.append(f"start_mode=clone:start_duration={_so(pad_truoc)}")
            if pad_sau > 0:
                parts.append(f"stop_mode=clone:stop_duration={_so(pad_sau)}")
            tpad_str = f"tpad={':'.join(parts)},"
            
        sau = f"f{i}"
        # fps TRƯỚC tpad: sau setpts luồng mất tốc độ khung, tpad khi đó không nhân được khung nào (đo: 90 khung thay vì 105).
        self.loc.append(f"[{cur}]{toc_s}fps={_so(self.fps)},{tpad_str}trim=duration={_so(dai_xuat)},setpts=PTS-STARTPTS[{sau}]")
        return k, sau, dai_xuat

    def _lop(self, c: Dict[str, Any], vao_nhan: str, i: str, lech_t: float = 0.0) -> Tuple[str, str, str]:
        """Biến một luồng thành LỚP RGBA theo biến đổi/cắt khung/độ mờ/bo góc/xoay → (nhãn, x_expr, y_expr)."""
        m = self.media[c["media"]]
        mw, mh = float(m.get("rong") or self.W), float(m.get("cao") or self.H)
        K = min(self.W / mw, self.H / mh)
        k = c.get("cat_khung") or {}
        tr_, ph, tr2, du = (float(k.get(x) or 0) for x in ("trai", "phai", "tren", "duoi"))
        tr_, ph = min(tr_, 0.95), min(ph, 0.95 - tr_)
        tr2, du = min(tr2, 0.95), min(du, 0.95 - tr2)
        
        kf = c.get("keyframes") or {}
        
        if "bien_doi.ti_le" in kf and kf["bien_doi.ti_le"]:
            ti_le_expr = bieu_thuc(kf["bien_doi.ti_le"], lech=lech_t)
        else:
            ti_le_expr = _so(float(c.get("bien_doi", {}).get("ti_le", 1)))
            
        w_expr = f"({_so(mw * K * (1 - tr_ - ph))}*{ti_le_expr})"
        h_expr = f"({_so(mh * K * (1 - tr2 - du))}*{ti_le_expr})"
        wc, hc = _chan(mw * K * (1 - tr_ - ph) * float(c.get("bien_doi", {}).get("ti_le", 1))), _chan(mh * K * (1 - tr2 - du) * float(c.get("bien_doi", {}).get("ti_le", 1)))
        
        loc = []
        if tr_ or ph or tr2 or du:
            loc.append(f"crop=iw*{1 - tr_ - ph:.4f}:ih*{1 - tr2 - du:.4f}:iw*{tr_:.4f}:ih*{tr2:.4f}")
            
        if "bien_doi.ti_le" in kf and kf["bien_doi.ti_le"]:
            loc.append(f"scale=w='trunc({w_expr}/2)*2':h='trunc({h_expr}/2)*2':eval=frame:flags=bicubic,setsar=1")
        else:
            loc.append(f"scale={wc}:{hc}:flags=bicubic,setsar=1")
            
        cac_loc = hieu_ung.loc_mau(c.get("mau") or {}) + hieu_ung.loc_hieu_ung(c.get("hieu_ung") or [], wc, hc)
        if cac_loc:
            loc.extend(cac_loc)
        loc.append("format=yuva420p")
        
        hien = c.get("hien_thi") or {}
        r = float(hien.get("bo_goc") or 0) * self.H / 1080
        if r > 0.5:
            r = min(r, wc / 2, hc / 2)
            a = (f"if(gt(pow(max(0\\,abs(X-W/2)-(W/2-{r:.1f}))\\,2)+pow(max(0\\,abs(Y-H/2)-(H/2-{r:.1f}))\\,2)\\,{r * r:.1f})\\,0\\,alpha(X\\,Y))")
            loc.append(f"geq=lum='p(X,Y)':cb='p(X,Y)':cr='p(X,Y)':a='{a}'")
            
        if "hien_thi.do_mo" in kf and kf["hien_thi.do_mo"]:
            do_mo_expr = bieu_thuc(kf["hien_thi.do_mo"], bien='T', lech=lech_t)
            loc.append(f"geq=lum='p(X\\,Y)':cb='p(X\\,Y)':cr='p(X\\,Y)':a='alpha(X\\,Y)*{do_mo_expr}'")
        else:
            mo = float(hien.get("do_mo", 1))
            if mo < 0.999:
                loc.append(f"colorchannelmixer=aa={max(0.0, mo):.3f}")
                
        if "bien_doi.x" in kf and kf["bien_doi.x"]:
            x_expr = bieu_thuc(kf["bien_doi.x"], lech=lech_t)
        else:
            x_expr = _so(float(c.get("bien_doi", {}).get("x", 0.5)))
            
        if "bien_doi.y" in kf and kf["bien_doi.y"]:
            y_expr = bieu_thuc(kf["bien_doi.y"], lech=lech_t)
        else:
            y_expr = _so(float(c.get("bien_doi", {}).get("y", 0.5)))
            
        cx_expr = f"({x_expr}*{self.W}+{_so((tr_ - ph)/2)}*{w_expr})"
        cy_expr = f"({y_expr}*{self.H}+{_so((tr2 - du)/2)}*{h_expr})"
        
        ow_expr = f"({w_expr})"
        oh_expr = f"({h_expr})"
        
        if "bien_doi.xoay" in kf and kf["bien_doi.xoay"]:
            xoay_expr = bieu_thuc(kf["bien_doi.xoay"], lech=lech_t)
            rad_expr = f"(({xoay_expr})*PI/180)"
            loc.append(f"rotate='{rad_expr}':ow='hypot(iw,ih)':oh='hypot(iw,ih)':c=none")
            ow_expr = f"hypot({w_expr},{h_expr})"
            oh_expr = f"hypot({w_expr},{h_expr})"
        else:
            xoay = float(c.get("bien_doi", {}).get("xoay", 0))
            if abs(xoay) > 0.01:
                import math
                a = math.radians(xoay)
                loc.append(f"rotate={a:.6f}:ow=rotw({a:.6f}):oh=roth({a:.6f}):c=none")
                ow_expr = f"({w_expr}*{_so(abs(math.cos(a)))}+{h_expr}*{_so(abs(math.sin(a)))})"
                oh_expr = f"({w_expr}*{_so(abs(math.sin(a)))}+{h_expr}*{_so(abs(math.cos(a)))})"
        
        ra = f"l{i}"
        self.loc.append(f"[{vao_nhan}]" + ",".join(loc) + f"[{ra}]")
        
        out_x = f"({cx_expr}-{ow_expr}/2)"
        out_y = f"({cy_expr}-{oh_expr}/2)"
        return ra, out_x, out_y

    def _tieng_clip(self, c: Dict[str, Any], k: int, tr: Dict[str, Any], dai: float, ten: str, tre: float = 0) -> bool:
        """Tiếng của một clip (tốc độ, âm lượng, fade) → nhãn `ten`. False nếu clip không có tiếng."""
        m = self.media[c["media"]]
        if m.get("loai") == "anh" or not m.get("co_am_thanh", m.get("loai") == "audio") or tr.get("tat_tieng") or c.get("tat_am"):
            return False
        kf = c.get("keyframes") or {}
        if "am_luong" in kf and kf["am_luong"]:
            vol_expr = bieu_thuc(kf["am_luong"], lech=0.0)
            vol_filter = f"volume=volume='{vol_expr}':eval=frame"
        else:
            vol = float(c.get("am_luong") if c.get("am_luong") is not None else 1)
            vol_filter = f"volume={vol:.3f}"
            
        fade = ""
        fi, fo = float(c.get("am_vao") or 0), float(c.get("am_ra") or 0)
        if fi > 0:
            fade += f",afade=t=in:st=0:d={_so(min(fi, dai))}"
        if fo > 0:
            fade += f",afade=t=out:st={_so(max(0.0, dai - fo))}:d={_so(min(fo, dai))}"
        dem = ""
        if tre > 0:
            ms = int(round(tre * 1000))
            dem = f",adelay={ms}|{ms}"
        self.loc.append(f"[{k}:a]asetpts=PTS-STARTPTS{_atempo(float(c.get('toc_do') or 1))},{vol_filter},aresample={SR},"
                        f"aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={_so(dai)}{fade}{dem}[{ten}]")
        return True

    def _phu(self, vc: str, T: float) -> Tuple[str, List[str]]:
        """Các track video PHỦ (trên nền) → overlay lần lượt từ dưới lên. Trả (nhãn hình, [nhãn tiếng])."""
        v_tracks = [t for t in self.tl.get("tracks") or [] if t.get("loai") == "video"]
        tren = [t for t in reversed(v_tracks[:-1]) if not t.get("an")]    # dưới → trên
        tieng: List[str] = []
        n = 0
        for tr in tren:
            for c, _ in [(c, t) for c, t in self._clip_track("video") if c["track"] == tr["id"]]:
                bd = float(c.get("bat_dau") or 0)
                if bd >= T:
                    continue
                n += 1
                i = f"p{n}"
                k, nhan, dai = self._nguon_lop(c, i)
                lop, x, y = self._lop(c, nhan, i, lech_t=bd)
                dich = f"lp{n}"
                self.loc.append(f"[{lop}]setpts=PTS+{_so(bd)}/TB[{dich}]")
                sau = f"vp{n}"
                hoa_tron = c.get("hien_thi", {}).get("hoa_tron", "normal")
                if hoa_tron != "normal":
                    self.loc.append(f"color=c=black@0:s={self.W}x{self.H}:r={_so(self.fps)}:d={_so(dai)},format=yuva420p[tr_{n}]")
                    self.loc.append(f"[tr_{n}][{dich}]overlay=x='{x}':y='{y}':eof_action=pass:eval=frame[pd_{n}]")
                    self.loc.append(f"[{vc}][pd_{n}]blend=all_mode={hoa_tron}:enable='between(t,{_so(bd)},{_so(bd + dai)})'[{sau}]")
                else:
                    self.loc.append(f"[{vc}][{dich}]overlay=x='{x}':y='{y}':eof_action=pass:repeatlast=0:eval=frame:"
                                    f"enable='between(t,{_so(bd)},{_so(bd + dai)})'[{sau}]")
                vc = sau
                if self._tieng_clip(c, k, tr, dai, f"pa{n}", tre=bd):
                    tieng.append(f"pa{n}")
        return vc, tieng

    def _che_cho(self, mid: str) -> List[Dict[str, Any]]:
        an = {t["id"] for t in self.tracks.values() if t.get("an")}
        return [c for c in self.tl.get("clips") or []
                if c.get("loai") == "che_phu_de" and c.get("tu_media") == mid and quy_doi.la_neo(c)
                and c.get("track") not in an]

    def _khoang(self, dai: float, i: int) -> Tuple[str, str]:
        self.loc.append(f"color=c={self.nen}:s={self.W}x{self.H}:r={_so(self.fps)}:d={_so(dai)},format=yuv420p,setsar=1[g{i}]")
        self.loc.append(f"anullsrc=r={SR}:cl=stereo,atrim=duration={_so(dai)}[ga{i}]")
        return f"g{i}", f"ga{i}"

    def _hinh(self, T: float) -> Tuple[str, str]:
        """Track video chính (track video đầu tiên) → [vc][ac] bằng concat và xfade."""
        v_tracks = [t for t in self.tl.get("tracks") or [] if t.get("loai") == "video"]
        chinh = v_tracks[-1]["id"] if v_tracks else "V1"   # track video dưới cùng = nền
        clips = [(c, tr) for c, tr in self._clip_track("video") if c["track"] == chinh]

        # Mở rộng hai đầu clip cho chuyển cảnh (xem tinh_xfade). Tiếng giữ nguyên độ dài gốc (cắt thẳng).
        con = [(c, tr) for c, tr in clips if float(c.get("bat_dau") or 0) < T]
        thong_tin = []
        for (c, tr), tt in zip(con, tinh_xfade([c for c, _ in con], self.tl.get("chuyen_canh") or [], self.media)):
            thong_tin.append({**tt, "c": c, "tr": tr, "orig_vao": float(c.get("vao") or 0), "orig_ra": float(c.get("ra") or 0)})

        t = 0.0
        v_items = []
        a_segments = []
        for i, info in enumerate(thong_tin):
            c = info["c"]
            bd = float(c.get("bat_dau") or 0)
            if bd - t > 1e-3:
                v_k, a_k = self._khoang(bd - t, len(v_items))
                v_items.append((v_k, bd - t, None))
                a_segments.append(a_k)

            c_mod = {**c, "vao": info["vao_moi"], "ra": info["ra_moi"], 
                     "pad_truoc": info["pad_truoc"], "pad_sau": info["pad_sau"]}
            nv, _, _ = self._doan_video(c_mod, info["tr"], i, chi_video=True)
            v_items.append((nv, info["original_dai"], info["sau_cc"]))
            
            na = f"a{i}"
            m = self.media[c["media"]]
            if m.get("loai") == "anh" or not m.get("co_am_thanh", m.get("loai") == "audio"):
                self.loc.append(f"anullsrc=r={SR}:cl=stereo,atrim=duration={_so(info['original_dai'])}[{na}]")
            else:
                k_a = self._input("-ss", _so(info["orig_vao"]), "-t", _so(info["orig_ra"] - info["orig_vao"]), "-i", self._file(m))
                if not self._tieng_clip(c, k_a, info["tr"], info["original_dai"], na):
                    self.loc.append(f"anullsrc=r={SR}:cl=stereo,atrim=duration={_so(info['original_dai'])}[{na}]")
            a_segments.append(na)
            
            t = bd + info["original_dai"]

        if T - t > 1e-3:
            v_k, a_k = self._khoang(T - t, len(v_items))
            v_items.append((v_k, T - t, None))
            a_segments.append(a_k)

        if a_segments:
            a_in = "".join(f"[{a}]" for a in a_segments)
            self.loc.append(f"{a_in}concat=n={len(a_segments)}:v=0:a=1[ac]")
        else:
            self.loc.append(f"anullsrc=r={SR}:cl=stereo,atrim=duration={_so(T)}[ac]")

        if v_items:
            segments_to_concat = []
            current_v = v_items[0][0]
            current_duration = v_items[0][1]
            
            for i in range(len(v_items) - 1):
                cc = v_items[i][2]
                next_v = v_items[i+1][0]
                next_dur = v_items[i+1][1]
                if cc:
                    dai_cc = float(cc["dai"])
                    offset = current_duration - dai_cc / 2
                    out_v = f"xf_{i}"
                    self.loc.append(f"[{current_v}][{next_v}]xfade=transition={cc['loai']}:duration={_so(dai_cc)}:offset={_so(offset)}[{out_v}]")
                    current_v = out_v
                    current_duration += next_dur
                else:
                    segments_to_concat.append(current_v)
                    current_v = next_v
                    current_duration = next_dur
            segments_to_concat.append(current_v)
            
            if len(segments_to_concat) > 1:
                concat_in = "".join(f"[{v}]" for v in segments_to_concat)
                self.loc.append(f"{concat_in}concat=n={len(segments_to_concat)}:v=1:a=0[vc]")
            else:
                self.loc.append(f"[{segments_to_concat[0]}]copy[vc]")
        else:
            self.loc.append(f"color=c={self.nen}:s={self.W}x{self.H}:r={_so(self.fps)}:d={_so(T)},format=yuv420p[vc]")

        return "vc", "ac"

    # ------------------------------------------------------------ tiếng (A*)
    def _tieng(self, ac: str, T: float, them: Optional[List[str]] = None) -> str:
        nen, giong = [ac] + list(them or []), []
        for n, (c, tr) in enumerate(self._clip_track("audio", bo_an=False)):
            if tr.get("tat_tieng"):
                continue
            m = self.media[c["media"]]
            vao, ra = float(c.get("vao") or 0), float(c.get("ra") or 0)
            toc = float(c.get("toc_do") or 1)
            bd = float(c.get("bat_dau") or 0)
            if bd >= T:
                continue
            k = self._input("-ss", _so(vao), "-t", _so(ra - vao), "-i", self._file(m))
            ten = f"x{n}"
            if self._tieng_clip(c, k, tr, (ra - vao) / toc, ten, tre=bd):
                (giong if tr.get("vai") == "long_tieng" else nen).append(ten)
        dau = f"amix=inputs={{n}}:duration=longest:dropout_transition=0:normalize=0"
        if len(nen) > 1:
            self.loc.append("".join(f"[{x}]" for x in nen) + dau.format(n=len(nen)) + "[nen]")
            nen_ra = "nen"
        else:
            nen_ra = nen[0]
        if not giong:
            self.loc.append(f"[{nen_ra}]apad,atrim=duration={_so(T)}[aout]")
            return "aout"
        if len(giong) > 1:
            self.loc.append("".join(f"[{x}]" for x in giong) + dau.format(n=len(giong)) + "[giong]")
        else:
            self.loc.append(f"[{giong[0]}]anull[giong]")
        giam = float(self.tc.get("giam_nhac_nen") or 90)
        ti_le = max(2.0, min(20.0, 1 + giam / 10))
        self.loc.append("[giong]asplit=2[g_sc][g_tron]")
        self.loc.append(f"[{nen_ra}][g_sc]sidechaincompress=threshold=0.02:ratio={ti_le:.1f}:attack=20:release=400[nen_giam]")
        self.loc.append(f"[nen_giam][g_tron]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                        f"apad,atrim=duration={_so(T)}[aout]")
        return "aout"

    # ------------------------------------------------------------ dựng
    def dung(self, ten_ra: str, co_ass: bool) -> Dict[str, Any]:
        T = self.thoi_luong()
        if T <= 0:
            raise ValueError("Timeline trống — chưa có clip video/âm thanh nào để xuất.")
        chi_tieng = bool(self.tc.get("chi_am_thanh"))
        vc, ac = self._hinh(T)
        vc, tieng_phu = self._phu(vc, T)
        aout = self._tieng(ac, T, tieng_phu)
        dong_pd = quy_doi.phu_de_tren_timeline(self.tl)
        co_chu_hinh = any(c.get("loai") in ("chu", "hinh") for c in self.tl.get("clips") or [])
        ass = ""
        if (dong_pd or co_chu_hinh) and not chi_tieng and co_ass:
            ass = chu_hinh.tao_ass(self.tl, self.W, self.H)
            self.loc.append(f"[{vc}]subtitles=sub.ass:fontsdir=fonts[vout]")
            vc = "vout"
        cmd = [self.ffmpeg, "-hide_banner", "-y", "-nostats", "-progress", "pipe:1"]
        for nhom in self.vao:
            cmd += nhom
        cmd += ["-filter_complex_script", "loc.txt"]
        if chi_tieng:
            cmd += ["-map", f"[{aout}]", "-c:a", "aac", "-b:a", "192k"]
        else:
            # Giữ -r: mỗi clip đã qua fps= nên -r gần như không tốn; bản lượt 24 bỏ -r theo c["loai"] (clip không có khoá này) → không bao giờ thêm.
            cmd += ["-map", f"[{vc}]", "-map", f"[{aout}]"] + self._ma_hoa() + [
                "-r", _so(self.fps), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
        # Vùng xuất [ ]: cắt sau cùng (seek đầu ra) — timeline vẫn dựng đủ để giờ mọi thứ khớp.
        vao_x = self.tc.get("vung_vao")
        ra_x = self.tc.get("vung_ra")
        if vao_x is not None and ra_x is not None and 0 <= float(vao_x) < float(ra_x):
            vao_x, ra_x = float(vao_x), min(float(ra_x), T)
            i_t = cmd.index("-filter_complex_script")
            cmd += ["-ss", _so(vao_x), "-t", _so(ra_x - vao_x), ten_ra]
            T_ra = ra_x - vao_x
        else:
            cmd += ["-t", _so(T), ten_ra]
            T_ra = T
        return {"cmd": cmd, "loc": ";\n".join(self.loc), "ass": ass, "thoi_luong": T_ra, "so_phu_de": len(dong_pd),
                "kich_thuoc": [self.W, self.H]}

    def _ma_hoa(self) -> List[str]:
        crf = int(self.tc.get("crf") or 20)
        if self.tc.get("bo_ma_hoa") == "nvenc":
            return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(crf + 2), "-b:v", "0"]
        return ["-c:v", "libx264", "-preset", self.tc.get("preset") or "medium", "-crf", str(crf)]


def dung_lenh_xuat(folder: str, du_an: Dict[str, Any], tl: Dict[str, Any], tuy_chon: Dict[str, Any],
                   ten_ra: str, ffmpeg: str = "ffmpeg", co_ass: bool = True) -> Dict[str, Any]:
    return DungLenh(folder, du_an, tl, tuy_chon, ffmpeg).dung(ten_ra, co_ass)


def co_nvenc(ffmpeg: str) -> bool:
    """Máy có GPU NVIDIA + ffmpeg hỗ trợ NVENC không (thử mã hoá 1 khung, ~1 giây)."""
    import subprocess
    try:
        res = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                              "color=c=black:s=256x256:d=0.1", "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                             capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return res.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def ten_file_ra(folder: str, ten: str, duoi: str = ".mp4") -> str:
    """xuat/<ten>.mp4 — trùng thì thêm (2), (3)… (không đè bản xuất cũ)."""
    import re
    ten = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (ten or "video").strip())[:80].strip(" .") or "video"
    thu_muc = os.path.join(os.path.abspath(folder), luu_tru.XUAT_DIR)
    os.makedirs(thu_muc, exist_ok=True)
    path, n = os.path.join(thu_muc, ten + duoi), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(thu_muc, f"{ten} ({n}){duoi}")
    return path


def xuat_srt(tl: Dict[str, Any]) -> Optional[str]:
    dong = quy_doi.phu_de_tren_timeline(tl)
    if not dong:
        return None
    return srt.ghi_srt(dong, "bd", "kt")
