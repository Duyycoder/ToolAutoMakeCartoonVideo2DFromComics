from typing import List, Dict, Any

def loc_mau(mau: Dict[str, Any]) -> List[str]:
    """Tạo chuỗi ffmpeg filter từ thông số chỉnh màu."""
    if not mau:
        return []
    
    filters = []
    
    sang = float(mau.get('sang', 0))
    tuong_phan = float(mau.get('tuong_phan', 0))
    bao_hoa = float(mau.get('bao_hoa', 0))
    
    if sang != 0 or tuong_phan != 0 or bao_hoa != 0:
        b = sang / 100.0
        c = 1.0 + tuong_phan / 100.0
        s = 1.0 + bao_hoa / 100.0
        # gamma giữ nguyên 1.0
        filters.append(f"eq=brightness={b}:contrast={c}:saturation={s}:gamma=1")
        
    hue_val = float(mau.get('hue', 0))
    if hue_val != 0:
        filters.append(f"hue=h={hue_val}")
        
    nhiet = float(mau.get('nhiet', 0))
    if nhiet != 0:
        # nhiet -100..100 -> colortemperature 10000..3000. 0 -> 6500
        temp = 6500 - (nhiet * 35)
        filters.append(f"colortemperature=temperature={temp}")
        
    phoi_sang = float(mau.get('phoi_sang', 0))
    if phoi_sang != 0:
        # exposure -3.0 to 3.0
        e = phoi_sang / 33.333
        filters.append(f"exposure=exposure={e}")
        
    vibrance = float(mau.get('vibrance', 0))
    if vibrance != 0:
        intensity = vibrance / 50.0
        filters.append(f"vibrance=intensity={intensity}")
        
    return filters

import os
import json

MAU_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "webui", "editor", "hieu_ung_mau.json")
try:
    with open(MAU_JSON_PATH, "r", encoding="utf-8") as f:
        MA_TRAN_MAU = json.load(f)
except Exception:
    MA_TRAN_MAU = {}

def loc_hieu_ung(ds: List[Dict[str, Any]], cw: int = 0, ch: int = 0) -> List[str]:
    """Tạo chuỗi ffmpeg filter từ danh sách hiệu ứng."""
    if not ds:
        return []
    
    filters = []
    for h in ds:
        if not h.get('bat', True):
            continue
        
        loai = h.get('loai')
        do_manh = float(h.get('do_manh', 100))
        m = do_manh / 100.0
        
        if loai in MA_TRAN_MAU:
            mat = MA_TRAN_MAU[loai]["matrix"]
            off = MA_TRAN_MAU[loai]["offset"]
            
            rr = 1.0 + m * (mat[0][0] - 1.0)
            rg = m * mat[0][1]
            rb = m * mat[0][2]
            gr = m * mat[1][0]
            gg = 1.0 + m * (mat[1][1] - 1.0)
            gb = m * mat[1][2]
            br = m * mat[2][0]
            bg = m * mat[2][1]
            bb = 1.0 + m * (mat[2][2] - 1.0)
            
            c_mix = f"colorchannelmixer=rr={rr:.3f}:rg={rg:.3f}:rb={rb:.3f}:gr={gr:.3f}:gg={gg:.3f}:gb={gb:.3f}:br={br:.3f}:bg={bg:.3f}:bb={bb:.3f}"
            
            o_r = m * off[0]
            o_g = m * off[1]
            o_b = m * off[2]
            
            if abs(o_r) > 0.001 or abs(o_g) > 0.001 or abs(o_b) > 0.001:
                if abs(o_r - o_g) < 0.001 and abs(o_r - o_b) < 0.001:
                    c_mix += f",eq=brightness={o_r:.3f}"
                else:
                    c_mix += f",lutrgb=r='clip(val+{o_r*255:.1f},0,255)':g='clip(val+{o_g*255:.1f},0,255)':b='clip(val+{o_b*255:.1f},0,255)'"
                    
            filters.append(c_mix)
        elif loai == 'grayscale':
            filters.append(f"hue=s={max(0.0, 1.0 - m):.3f}")
        elif loai == 'invert':
            # Invert: ma trận I + m*(-2I) với độ lệch m => c' = (1-2m)*c + m
            filters.append(f"lutrgb=r='clip((1-2*{m})*val+{m}*255,0,255)':g='clip((1-2*{m})*val+{m}*255,0,255)':b='clip((1-2*{m})*val+{m}*255,0,255)'")
        elif loai == 'mo_hop':
            r = max(1, int(do_manh / 5))
            filters.append(f"boxblur=lr={r}:cr={r}")
        elif loai == 'mo_gauss':
            sigma = max(0.1, do_manh / 5.0)
            filters.append(f"gblur=sigma={sigma:.1f}")
        elif loai == 'mosaic':
            k = max(2, int(do_manh / 2))
            if cw > 0 and ch > 0:
                filters.append(f"scale=iw/{k}:ih/{k},scale={cw}:{ch}:flags=neighbor")
            else:
                filters.append(f"scale=iw/{k}:ih/{k},scale=iw*{k}:ih*{k}:flags=neighbor")
            
    return filters

