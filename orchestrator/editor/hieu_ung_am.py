"""Hiệu ứng âm thanh của clip (clip["hieu_ung_am"]) → bộ lọc ffmpeg lúc xuất.

    cao_do     -12..12   nửa cung (đổi cao độ giọng, giữ tốc độ)
    robot      bool      giọng robot (giữ biên độ phổ, bỏ pha)
    loc_bang   ""|dien_thoai|radio|loa      lọc dải tần như qua điện thoại / radio / loa phóng thanh
    meo        0..100    méo tiếng (atan soft-clip)
    bit        0|4..12   bitcrush (lượng tử hoá còn N bit) — 0 = tắt
    rung       0..100    tremolo (độ sâu) · rung_tan 1..20 Hz
    nen        0..100    nén dải động (compressor) + bù âm lượng
    doi        0..100    tiếng dội (echo 3 lần lặp) · doi_tre 80..1000 ms
    vang       0..100    tiếng vang (reverb tích chập IR) · phong: phong_nho|phong_lon|nha_tho|hang
    dao_nguoc  bool      phát ngược
    chuan_hoa  bool      chuẩn hoá độ to (EBU R128, -16 LUFS)

Xem trước: webui/editor/am_hieu_ung.js dựng cùng công thức bằng Web Audio (méo, bit, rung, nén, dội, vang, lọc dải);
cao độ, robot, phát ngược và chuẩn hoá chỉ nghe ở bản xuất / "Xem chính xác".
"""
import functools
import math
import os
import random
import struct
import wave
from typing import Any, Dict, List, Optional, Tuple

SR_IR = 48000
# Phòng: (RT60 giây, trễ đầu ms, độ tối — hệ số lọc thông thấp 0..1, càng lớn càng tối)
PHONG = {"phong_nho": (0.5, 4, 0.25), "phong_lon": (1.4, 14, 0.4), "nha_tho": (3.2, 28, 0.55), "hang": (2.2, 20, 0.3)}
LOC_BANG = {"dien_thoai": (300, 3400), "radio": (450, 4500), "loa": (600, 3000)}


def _so(x: float) -> str:
    return f"{x:.6f}".rstrip("0").rstrip(".")


def _kep(x: Any, a: float, b: float) -> float:
    try:
        v = float(x or 0)
    except (TypeError, ValueError):
        return 0.0
    return a if v < a else b if v > b else v


def co_hieu_ung(h: Optional[Dict[str, Any]]) -> bool:
    h = h or {}
    return any(_kep(h.get(k), -100, 100) for k in ("cao_do", "meo", "bit", "rung", "nen", "doi", "vang")) \
        or any(bool(h.get(k)) for k in ("robot", "loc_bang", "dao_nguoc", "chuan_hoa"))


def _atempo(k: float) -> List[str]:
    out = []
    while k > 2.0:
        out.append("atempo=2.0")
        k /= 2.0
    while k < 0.5:
        out.append("atempo=0.5")
        k /= 0.5
    out.append(f"atempo={k:.6f}")
    return out


def loc_truoc_vang(h: Dict[str, Any], sr: int) -> List[str]:
    """Các bộ lọc trước tiếng vang (một chuỗi thẳng)."""
    h = h or {}
    loc: List[str] = []
    if h.get("dao_nguoc"):
        loc.append("areverse")
    st = _kep(h.get("cao_do"), -12, 12)
    if abs(st) >= 0.05:
        k = 2 ** (st / 12)
        loc += [f"aresample={sr}", f"asetrate={round(sr * k)}", f"aresample={sr}"] + _atempo(1 / k)
    if h.get("robot"):
        loc.append("afftfilt=real='hypot(re,im)':imag='0':win_size=512:overlap=0.75")
    if h.get("loc_bang") in LOC_BANG:
        thap, cao = LOC_BANG[h["loc_bang"]]
        loc += [f"highpass=f={thap}", f"highpass=f={thap}", f"lowpass=f={cao}", f"lowpass=f={cao}"]
    meo = _kep(h.get("meo"), 0, 100) + (25 if h.get("loc_bang") == "loa" else 0)
    if meo > 0:
        g = 1 + 19 * min(meo, 100) / 100
        bt = f"atan({_so(g)}*val(ch))/{_so(math.atan(g))}"
        loc.append(f"aeval='{bt}':c=same")
    bit = int(_kep(h.get("bit"), 0, 12))
    if bit >= 2:
        q = 2 ** (bit - 1)
        loc.append(f"aeval='round(val(ch)*{q})/{q}':c=same")
    rung = _kep(h.get("rung"), 0, 100)
    if rung > 0:
        loc.append(f"tremolo=f={_so(_kep(h.get('rung_tan') or 6, 1, 20))}:d={_so(rung / 100)}")
    nen = _kep(h.get("nen"), 0, 100)
    if nen > 0:
        a = nen / 100
        nguong_db = -10 - 20 * a
        bu_db = -nguong_db * (1 - 1 / (1 + 7 * a)) * 0.5
        loc.append(f"acompressor=threshold={_so(10 ** (nguong_db / 20))}:ratio={_so(1 + 7 * a)}:attack=10:release=200"
                   f":makeup={_so(10 ** (bu_db / 20))}")
    doi = _kep(h.get("doi"), 0, 100)
    if doi > 0:
        tre = _kep(h.get("doi_tre") or 350, 80, 1000)
        a = 0.2 + 0.5 * doi / 100
        loc.append(f"aecho=1:1:{_so(tre)}|{_so(2 * tre)}|{_so(3 * tre)}:{_so(a)}|{_so(a * a)}|{_so(a ** 3)}")
    return loc


def tron_vang(h: Dict[str, Any]) -> float:
    return _kep((h or {}).get("vang"), 0, 100) / 100


def loc_sau_vang(h: Dict[str, Any]) -> List[str]:
    return ["loudnorm=I=-16:TP=-1.5:LRA=11"] if (h or {}).get("chuan_hoa") else []


@functools.lru_cache(maxsize=8)
def ir_phong(phong: str) -> Tuple[Tuple[Tuple[float, float], ...], float]:
    """Đáp ứng xung stereo của phòng: nhiễu trắng tắt dần theo RT60, lọc tối dần; năng lượng mỗi kênh = 1.
    Trả (mẫu đã chia đỉnh về ±1 để ghi int16, hệ số đỉnh — nhân lại sau afir cho đúng năng lượng)."""
    rt, tre_ms, toi = PHONG.get(phong, PHONG["phong_lon"])
    n = int(SR_IR * (rt + tre_ms / 1000))
    tre = int(SR_IR * tre_ms / 1000)
    kenh = []
    for seed in (1, 2):
        r = random.Random(f"{phong}-{seed}")
        y, out = 0.0, [0.0] * tre
        for i in range(tre, n):
            y = y * toi + (r.random() * 2 - 1) * (1 - toi)
            out.append(y * math.exp(-6.9078 * (i - tre) / SR_IR / rt))
        e = math.sqrt(sum(v * v for v in out)) or 1.0
        kenh.append([v / e for v in out])
    dinh = max(max(abs(v) for v in k) for k in kenh) or 1.0
    return tuple(zip((v / dinh for v in kenh[0]), (v / dinh for v in kenh[1]))), dinh


def file_ir(thu_muc: str, phong: str) -> Tuple[str, float]:
    """Ghi IR .wav int16 vào thư mục cache (dùng lại nếu đã có) → (đường dẫn, hệ số đỉnh)."""
    phong = phong if phong in PHONG else "phong_lon"
    du, dinh = ir_phong(phong)
    p = os.path.join(thu_muc, f"ir_{phong}_v1.wav")
    if not os.path.exists(p):
        os.makedirs(thu_muc, exist_ok=True)
        tam = p + ".tam"
        with wave.open(tam, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR_IR)
            w.writeframes(b"".join(struct.pack("<hh", round(a * 32767), round(b * 32767)) for a, b in du))
        os.replace(tam, p)
    return p, dinh