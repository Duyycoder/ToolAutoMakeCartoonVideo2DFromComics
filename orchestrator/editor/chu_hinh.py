import math
from typing import Any, Dict, List
from orchestrator.editor import quy_doi, srt

def _ass_mau(hex_mau: str, do_mo: float = 1.0) -> str:
    h = (hex_mau or "#ffffff").lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    h = (h + "000000")[:6]
    r, g, b = h[0:2], h[2:4], h[4:6]
    alpha = int((1.0 - max(0.0, min(1.0, float(do_mo)))) * 255)
    return f"&H{alpha:02X}{b}{g}{r}".upper()

def _ve_da_giac(canh: int, rw: float, rh: float, sao: bool = False) -> str:
    canh = max(3, canh)
    pts = []
    points = canh * 2 if sao else canh
    rx, ry = rw / 2, rh / 2
    for i in range(points):
        a = -math.pi / 2 + i * 2 * math.pi / points
        r = 1.0 if (not sao or i % 2 == 0) else 0.4
        pts.append((int(rx + math.cos(a) * rx * r), int(ry + math.sin(a) * ry * r)))
    ve = f"m {pts[0][0]} {pts[0][1]}"
    for p in pts[1:]:
        ve += f" l {p[0]} {p[1]}"
    ve += f" l {pts[0][0]} {pts[0][1]}"
    return ve

def _ve_tim(rw: float, rh: float) -> str:
    # Shifted to fit in [0, rw]x[0, rh]
    # Original:
    # m 0 {int(-rh*0.2)} b {int(rw*0.5)} {int(-rh*0.7)} {int(rw*0.6)} 0 0 {int(rh*0.5)} b {int(-rw*0.6)} 0 {int(-rw*0.5)} {int(-rh*0.7)} 0 {int(-rh*0.2)}
    # Now top-left is 0,0
    # Original max range was x: [-0.6*rw, 0.6*rw] -> width ~ 1.2*rw
    # Let's just scale and shift properly. Heart typically fits in 0..W, 0..H.
    # Center x is rw/2. Top y is about rh*0.3 (actually the arc goes higher).
    # Let's map it:
    cx, cy = rw/2, rh/2
    return f"m {int(cx)} {int(rh*0.3)} b {int(cx+rw*0.5)} {int(-rh*0.2)} {int(cx+rw*0.6)} {int(cy)} {int(cx)} {int(rh*0.9)} b {int(cx-rw*0.6)} {int(cy)} {int(cx-rw*0.5)} {int(-rh*0.2)} {int(cx)} {int(rh*0.3)}"

def _ve_mui_ten(rw: float, rh: float) -> str:
    # Arrow shifted to 0,0
    cx, cy = int(rw/2), int(rh/2)
    h3 = int(rh*0.3)
    # Original: m -w2 -h3 l 0 -h3 l 0 -h2 l w2 0 l 0 h2 l 0 h3 l -w2 h3
    # Shift x by +w2, y by +h2
    # w2 is rw/2, h2 is rh/2
    return f"m 0 {int(cy-h3)} l {cx} {int(cy-h3)} l {cx} 0 l {int(rw)} {cy} l {cx} {int(rh)} l {cx} {int(cy+h3)} l 0 {int(cy+h3)}"

def tao_ass(tl: Dict[str, Any], W: int, H: int) -> str:
    dong_pd = quy_doi.phu_de_tren_timeline(tl)
    kieu_pd = tl.get("kieu_phu_de") or {"k_mac_dinh": {}}
    ass_goc = srt.ghi_ass(dong_pd, kieu_pd, W, H)

    tracks = tl.get("tracks", [])
    tong_tracks = len(tracks)
    track_layers = {t["id"]: tong_tracks - i for i, t in enumerate(tracks)}
    su_kien = []
    
    for c in tl.get("clips", []):
        if c.get("loai") not in ("chu", "hinh"):
            continue
        layer = track_layers.get(c.get("track"), 0)
        bd = float(c.get("bat_dau", 0))
        kt = quy_doi.ket_thuc(c)
        if kt <= bd:
            continue
            
        b = c.get("bien_doi", {})
        cx, cy = float(b.get("x", 0.5)) * W, float(b.get("y", 0.5)) * H
        xoay = float(b.get("xoay", 0))
        do_mo = float(c.get("hien_thi", {}).get("do_mo", 1.0))
        
        tags_co_ban = [f"\\pos({cx:.1f},{cy:.1f})"]
        if xoay:
            tags_co_ban.append(f"\\frz{-xoay:.2f}")
            
        hv = c.get("hieu_ung_vao")
        hr = c.get("hieu_ung_ra")
        fad_vao, fad_ra = 0, 0
        if hv == "mo_dan":
            fad_vao = 500
        elif hv == "truot_len":
            tags_co_ban.append(f"\\move({cx:.1f},{cy+100:.1f},{cx:.1f},{cy:.1f})")
        if hr == "mo_dan":
            fad_ra = 500
        if fad_vao or fad_ra:
            tags_co_ban.append(f"\\fad({fad_vao},{fad_ra})")
            
        if c["loai"] == "chu":
            tags = tags_co_ban[:]
            ti_le = float(b.get("ti_le", 1.0)) * 100
            tags.append(f"\\fscx{ti_le:.1f}\\fscy{ti_le:.1f}")
            
            k = c.get("kieu", {})
            font = k.get("font") or "Arial"
            co = float(k.get("co", 48)) * H / 1080.0
            tags.append(f"\\fn{font}\\fs{co:.1f}")
            
            tags.append(f"\\1c&H{_ass_mau(k.get('mau', '#ffffff'))[4:]}&")
            tags.append(f"\\alpha&H{int((1-do_mo)*255):02X}&")
            
            if k.get("dam"): tags.append("\\b1")
            if k.get("nghieng"): tags.append("\\i1")
            
            vien_day = float(k.get("vien_day", 0)) * H / 1080.0
            if vien_day > 0:
                tags.append(f"\\bord{vien_day:.1f}")
                tags.append(f"\\3c&H{_ass_mau(k.get('vien_mau', '#000000'))[4:]}&")
            else:
                tags.append("\\bord0")
                
            if k.get("bong"):
                tags.append("\\shad2\\4c&H80000000")
                
            can = k.get("can", "giua")
            an = {"trai": 4, "giua": 5, "phai": 6}.get(can, 5)
            tags.append(f"\\an{an}")
            
            chu = str(c.get("noi_dung", "")).replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            chu_lines = chu.split("\n")
            if hv == "danh_may" and chu:
                thoi_gian_danh = min(1.0, kt - bd)
                so_ky_tu = len(chu)
                tg_moi_ky_tu = thoi_gian_danh / max(1, so_ky_tu)
                
                chu_tich_luy = ""
                for i, char in enumerate(chu):
                    t_hien = bd + i * tg_moi_ky_tu
                    t_bien_mat = t_hien + tg_moi_ky_tu
                    if char == "\n":
                        chu_tich_luy += "\\N"
                        continue
                    
                    if i < so_ky_tu - 1:
                        su_kien.append(f"Dialogue: {layer},{srt._ass_gio(t_hien)},{srt._ass_gio(t_bien_mat)},k_mac_dinh,,0,0,0,,{{{ ''.join(tags) }}}{chu_tich_luy + char}")
                    else:
                        su_kien.append(f"Dialogue: {layer},{srt._ass_gio(t_hien)},{srt._ass_gio(kt)},k_mac_dinh,,0,0,0,,{{{ ''.join(tags) }}}{chu_tich_luy + char}")
                    chu_tich_luy += char
            else:
                chu = chu.replace("\n", "\\N")
                su_kien.append(f"Dialogue: {layer},{srt._ass_gio(bd)},{srt._ass_gio(kt)},k_mac_dinh,,0,0,0,,{{{ ''.join(tags) }}}{chu}")
            
        elif c["loai"] == "hinh":
            tags = tags_co_ban[:]
            rw = float(b.get("rong", 0.2)) * W
            rh = float(b.get("cao", 0.2)) * H
            tags.append("\\an5\\fscx100\\fscy100")
            
            tags.append(f"\\1c&H{_ass_mau(c.get('mau', '#ffffff'))[4:]}&")
            tags.append(f"\\alpha&H{int((1-float(c.get('do_mo', 1.0)))*255):02X}&")
            
            vien_day = float(c.get("vien_day", 0)) * H / 1080.0
            if vien_day > 0:
                tags.append(f"\\bord{vien_day:.1f}")
                tags.append(f"\\3c&H{_ass_mau(c.get('vien_mau', '#000000'))[4:]}&")
            else:
                tags.append("\\bord0")
                
            dang = c.get("dang", "chu_nhat")
            ve = ""
            if dang == "chu_nhat":
                x1, y1 = 0, 0
                x2, y2 = int(rw), int(rh)
                ve = f"m {x1} {y1} l {x2} {y1} l {x2} {y2} l {x1} {y2} l {x1} {y1}"
            elif dang in ("tron", "elip"):
                rx, ry = rw/2, rh/2
                kappa = 0.552284749831 * rx
                kappay = 0.552284749831 * ry
                ve = (f"m {int(rx)} 0 "
                      f"b {int(rx+kappa)} 0 {int(rw)} {int(ry-kappay)} {int(rw)} {int(ry)} "
                      f"b {int(rw)} {int(ry+kappay)} {int(rx+kappa)} {int(rh)} {int(rx)} {int(rh)} "
                      f"b {int(rx-kappa)} {int(rh)} 0 {int(ry+kappay)} 0 {int(ry)} "
                      f"b 0 {int(ry-kappay)} {int(rx-kappa)} 0 {int(rx)} 0")
            elif dang == "sao":
                ve = _ve_da_giac(5, rw, rh, sao=True)
            elif dang == "da_giac":
                ve = _ve_da_giac(int(c.get("so_canh", 5)), rw, rh)
            elif dang == "tim":
                ve = _ve_tim(rw, rh)
            elif dang == "mui_ten":
                ve = _ve_mui_ten(rw, rh)
                
            tags.append("\\p1")
            su_kien.append(f"Dialogue: {layer},{srt._ass_gio(bd)},{srt._ass_gio(kt)},k_mac_dinh,,0,0,0,,{{{ ''.join(tags) }}}{ve}{{\\p0}}")

    ass_lines = ass_goc.split("\n")
    max_layer = tong_tracks + 1
    for i in range(len(ass_lines)):
        if ass_lines[i].startswith("Dialogue: 0,"):
            ass_lines[i] = ass_lines[i].replace("Dialogue: 0,", f"Dialogue: {max_layer},", 1)
            
    try:
        idx_events = ass_lines.index("[Events]")
        idx_format = idx_events + 1
        while idx_format < len(ass_lines) and not ass_lines[idx_format].startswith("Format:"):
            idx_format += 1
        idx_insert = idx_format + 1
        ass_lines = ass_lines[:idx_insert] + su_kien + ass_lines[idx_insert:]
    except ValueError:
        pass
        
    return "\n".join(ass_lines)
