import math

def gia_tri_tai(clip: dict, duong_dan: str, t_cuc_bo: float):
    # Lấy giá trị tĩnh
    parts = duong_dan.split('.')
    tinh = clip
    for p in parts:
        if isinstance(tinh, dict) and p in tinh:
            tinh = tinh[p]
        else:
            tinh = None
            break
            
    keyframes = clip.get('keyframes', {})
    if not keyframes or duong_dan not in keyframes or not keyframes[duong_dan]:
        return tinh
        
    diem = sorted(keyframes[duong_dan], key=lambda x: x['t'])
    
    if t_cuc_bo <= diem[0]['t']:
        return diem[0]['v']
    if t_cuc_bo >= diem[-1]['t']:
        return diem[-1]['v']
        
    for i in range(len(diem) - 1):
        d1 = diem[i]
        d2 = diem[i + 1]
        
        if d1['t'] <= t_cuc_bo < d2['t']:
            tl = (t_cuc_bo - d1['t']) / (d2['t'] - d1['t'])
            em = d1.get('em', 'tuyen_tinh')
            
            if em == 'giu':
                return d1['v']
                
            f = tl
            if em == 'vao_ra':
                f = tl * tl * (3 - 2 * tl)
                
            return d1['v'] + (d2['v'] - d1['v']) * f
            
    return tinh
