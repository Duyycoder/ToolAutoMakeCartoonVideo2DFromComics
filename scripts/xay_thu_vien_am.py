"""Dựng thư viện âm thanh có sẵn của editor: assets/thu_vien_am/ (SFX + nhạc nền, CHỈ giấy phép CC0).

Chạy lại được (bỏ qua file đã có). Kết quả commit vào git để app dùng offline:
    python scripts/xay_thu_vien_am.py [--tam <thư mục tải tạm>] [--bo-sfx-kit] [--bo-freesound] [--bo-nhac]

Nguồn (mỗi mục đều kiểm tra giấy phép CC0 ngay trên trang trước khi tải):
  - wyzowl/sfx-kit  (GitHub, CC0-1.0)          — 320 SFX cho video/motion (whoosh, pop, UI, impact…)
  - Freesound       (lọc license CC0, nhiều lượt tải nhất) — SFX hay dùng khi edit (cười, vỗ tay, boing…)
  - HoliznaCC0      (Free Music Archive, CC0)  — nhạc nền lo-fi / chill / vui
  - Komiku / Loyalty Freak Music (OpenGameArt, CC0) — nhạc nền vui, phiêu lưu, buồn
Mọi file chuyển sang .m4a (AAC) — trình duyệt nào cũng phát được, ffmpeg đọc thẳng khi xuất.
"""
import argparse
import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)
from orchestrator.editor import media  # noqa: E402

RA = os.path.join(GOC, "assets", "thu_vien_am")
UA = {"User-Agent": "Mozilla/5.0 (thu-vien-am builder)"}
FF = media.ffmpeg_exe()

NHOM_SFX_KIT = {
    "whooshes": "Whoosh", "reverse-whooshes": "Whoosh", "swishes-and-zips": "Whoosh", "swipes": "Whoosh",
    "pops": "Pop & nảy", "bounce-spin-zoom": "Pop & nảy", "shape-changes": "Pop & nảy", "appear-and-vanish": "Xuất hiện / biến mất",
    "impacts": "Va chạm & đấm", "cinematic-hits": "Điện ảnh", "booms-and-bass": "Điện ảnh", "risers-and-fallers": "Điện ảnh",
    "logo-stings": "Logo & mở đầu", "shimmers": "Lấp lánh & phép thuật", "celebration": "Chúc mừng",
    "interface": "Giao diện & click", "notifications": "Thông báo", "digital": "Kỹ thuật số", "data": "Kỹ thuật số",
    "keyboard": "Bàn phím & gõ", "writing-and-drawing": "Viết & vẽ", "mechanical": "Máy móc", "foley": "Đời thường",
    "everyday-props": "Đời thường", "money": "Tiền & mua bán", "time": "Đồng hồ & thời gian", "phone": "Điện thoại",
    "tones": "Âm báo",
}

# (nhóm, tên tiếng Việt, từ khoá Freesound, số file, thời lượng tối đa giây)
FREESOUND = [
    ("Hài hước", "Boing", "boing", 4, 6), ("Hài hước", "Huýt sáo trượt", "slide whistle", 3, 6),
    ("Hài hước", "Trống chốt câu (ba dum tss)", "rimshot", 3, 6), ("Hài hước", "Kèn buồn (wah wah)", "sad trombone", 3, 8),
    ("Hài hước", "Dế kêu (im lặng)", "crickets", 3, 15), ("Hài hước", "Bóp còi đồ chơi", "squeaky toy", 3, 4),
    ("Hài hước", "Cốc đầu (bonk)", "bonk", 3, 3), ("Hài hước", "Chạy kiểu hoạt hình", "cartoon run", 3, 6),
    ("Hài hước", "Xì hơi", "fart", 3, 4), ("Hài hước", "Hôn chụt", "kiss", 2, 3), ("Hài hước", "Ợ", "burp", 2, 4),
    ("Hài hước", "Đĩa nhạc rít (record scratch)", "record scratch", 3, 4), ("Hài hước", "Ngã / trượt chân", "cartoon fall", 3, 5),
    ("Đám đông", "Tiếng cười khán giả", "laugh track", 4, 12), ("Đám đông", "Vỗ tay", "applause", 4, 15),
    ("Đám đông", "Reo hò", "crowd cheer", 3, 15), ("Đám đông", "Ồ ngạc nhiên", "crowd gasp", 3, 6),
    ("Đám đông", "Aww dễ thương", "crowd aww", 2, 6), ("Đám đông", "La ó", "crowd boo", 2, 8),
    ("Đám đông", "Cười to", "laugh", 3, 8), ("Đám đông", "Em bé cười", "baby laugh", 2, 8),
    ("Gameshow", "Đúng (ding)", "correct answer", 3, 4), ("Gameshow", "Sai (buzzer)", "wrong buzzer", 3, 4),
    ("Gameshow", "Ta-da", "tada fanfare", 3, 6), ("Gameshow", "Trống dồn", "drum roll", 3, 10),
    ("Gameshow", "Máy tính tiền", "cash register", 3, 4), ("Gameshow", "Lên cấp", "level up", 3, 4),
    ("Gameshow", "Đếm ngược bíp", "countdown beep", 3, 8), ("Gameshow", "Chuông ding", "ding bell", 3, 4),
    ("Hành động", "Đấm", "punch", 4, 3), ("Hành động", "Nổ", "explosion", 4, 8), ("Hành động", "Kiếm", "sword slash", 3, 3),
    ("Hành động", "Súng", "gunshot", 3, 4), ("Hành động", "Vỡ kính", "glass break", 3, 5), ("Hành động", "Roi quất", "whip crack", 2, 3),
    ("Hành động", "Rơi bịch", "body fall thud", 2, 3),
    ("Đời thường", "Chụp ảnh", "camera shutter", 3, 3), ("Đời thường", "Gõ cửa", "door knock", 3, 4),
    ("Đời thường", "Cửa kẽo kẹt", "door creak", 3, 6), ("Đời thường", "Bước chân", "footsteps", 3, 10),
    ("Đời thường", "Chuông điện thoại", "phone ring", 3, 10), ("Đời thường", "Nhịp tim", "heartbeat", 3, 10),
    ("Đời thường", "Đồng hồ tích tắc", "clock ticking", 2, 10), ("Đời thường", "Nước bắn", "water splash", 3, 4),
    ("Đời thường", "Bong bóng", "bubble pop", 3, 3), ("Đời thường", "Hắt xì", "sneeze", 2, 3),
    ("Thiên nhiên", "Mưa", "rain", 3, 20), ("Thiên nhiên", "Sấm", "thunder", 3, 12), ("Thiên nhiên", "Gió", "wind", 3, 20),
    ("Thiên nhiên", "Chim hót", "birds chirping", 3, 20),
    ("Động vật", "Chó sủa", "dog bark", 3, 4), ("Động vật", "Mèo kêu", "cat meow", 3, 4), ("Động vật", "Gà gáy", "rooster", 2, 6),
    ("Kinh dị & hồi hộp", "Hét", "scream", 3, 5), ("Kinh dị & hồi hộp", "Kịch tính (dun dun dun)", "dramatic sting", 3, 8),
    ("Kinh dị & hồi hộp", "Ma quái", "ghost", 3, 10), ("Kinh dị & hồi hộp", "Hồi hộp", "suspense", 3, 10),
    ("Lấp lánh & phép thuật", "Phép thuật", "magic wand", 3, 5), ("Lấp lánh & phép thuật", "Dịch chuyển", "teleport", 2, 4),
]

# Album HoliznaCC0 (FMA) — lấy vài bài đầu mỗi album; nhóm tâm trạng.
FMA_ALBUM = [
    ("Lo-fi & chill", "https://freemusicarchive.org/music/holiznacc0/ocean-memory-lo-fi-chill", 3),
    ("Lo-fi & chill", "https://freemusicarchive.org/music/holiznacc0/summer-air-lo-fi", 3),
    ("Lo-fi & chill", "https://freemusicarchive.org/music/holiznacc0/public-domain-lofi", 3),
    ("Nhẹ nhàng", "https://freemusicarchive.org/music/holiznacc0/spring-woke-me-up", 2),
    ("Nhẹ nhàng", "https://freemusicarchive.org/music/holiznacc0/nature-spirit", 2),
    ("Sôi động", "https://freemusicarchive.org/music/holiznacc0/phonk-aura-farming", 2),
    ("Game & 8-bit", "https://freemusicarchive.org/music/holiznacc0/ruby-chiptunes", 2),
]
OGA_NGUOI = "https://opengameart.org/users/loyalty-freak-music"
NHAC_TOI_DA = 6 * 60


def tai(url: str, het_gio: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    for lan in range(3):
        try:
            with urllib.request.urlopen(req, timeout=het_gio) as r:
                return r.read()
        except Exception:  # mạng chập chờn: thử lại
            if lan == 2:
                raise
            time.sleep(2 + 3 * lan)
    return b""


def chuyen(nguon: str, dich: str, kbps: int, chuan_hoa: bool = False) -> float:
    """→ .m4a AAC; chuan_hoa=True thì đưa đỉnh về -1 dBFS (Freesound to nhỏ khác nhau). Trả thời lượng (s)."""
    os.makedirs(os.path.dirname(dich), exist_ok=True)
    loc = []
    if chuan_hoa:
        r = subprocess.run([FF, "-hide_banner", "-i", nguon, "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True, errors="replace")
        m = re.search(r"max_volume: (-?[\d.]+) dB", r.stderr)
        if m and abs(float(m.group(1)) + 1) > 0.5:
            loc = ["-af", f"volume={-1 - float(m.group(1)):.1f}dB"]
    tam = dich + ".tam.m4a"
    subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", nguon, "-vn", "-map_metadata", "-1", *loc,
                    "-c:a", "aac", "-b:a", f"{kbps}k", "-movflags", "+faststart", tam], check=True)
    os.replace(tam, dich)
    return thoi_luong(dich)


def thoi_luong(p: str) -> float:
    r = subprocess.run([FF, "-hide_banner", "-i", p], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3) if m else 0.0


def ten_file(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or "x"


# ---------------------------------------------------------------- nguồn
def sfx_kit(tam: str, ds: list) -> None:
    zip_p = os.path.join(tam, "sfx-kit.zip")
    if not os.path.exists(zip_p):
        print("Tải wyzowl/sfx-kit…")
        open(zip_p, "wb").write(tai("https://codeload.github.com/wyzowl/sfx-kit/zip/refs/heads/main", 300))
    z = zipfile.ZipFile(zip_p)
    goc = z.namelist()[0].split("/")[0]
    lic = z.read(f"{goc}/LICENSE").decode("utf-8", "replace")
    assert "CC0 1.0 Universal" in lic, "sfx-kit không còn là CC0 — dừng."
    meta = json.loads(z.read(f"{goc}/sounds.json"))
    for s in meta["sounds"]:
        nhom = NHOM_SFX_KIT.get(s["category"], "Khác")
        rel = f"sfx/kit/{s['category']}/{s['id']}.m4a"
        dich = os.path.join(RA, rel)
        if not os.path.exists(dich):
            wav = os.path.join(tam, "kit", s["id"] + ".wav")
            os.makedirs(os.path.dirname(wav), exist_ok=True)
            open(wav, "wb").write(z.read(f"{goc}/{s['file']}"))
            chuyen(wav, dich, 128)
        ds.append({"id": "kit-" + s["id"], "loai": "sfx", "nhom": nhom, "ten": s["name"], "file": rel,
                   "thoi_luong": round(float(s.get("duration") or thoi_luong(dich)), 3),
                   "the": s.get("tags", [])[:8], "mo_ta": s.get("description", ""),
                   "tac_gia": "Wyzowl SFX Kit", "giay_phep": "CC0-1.0", "nguon": "https://github.com/wyzowl/sfx-kit"})
    print(f"  sfx-kit: {len(meta['sounds'])} file")


def freesound(tam: str, ds: list) -> None:
    for nhom, ten, q, so, toi_da in FREESOUND:
        url = ("https://freesound.org/search/?q=" + urllib.parse.quote_plus(q)
               + "&f=license%3A%22Creative+Commons+0%22&s=Num+downloads+desc")
        trang = tai(url).decode("utf-8", "replace")
        time.sleep(1)
        lay = 0
        for khoi in trang.split('class="bw-search__result"')[1:]:
            if lay >= so:
                break
            if "Creative Commons 0" not in khoi and "cc0" not in khoi.lower():
                continue
            g = lambda k: (re.search(rf'data-{k}="([^"]*)"', khoi) or [None, ""])[1]  # noqa: E731
            sid, dai = g("sound-id"), float(g("duration") or 0)
            if not sid or not 0.1 < dai <= toi_da:
                continue
            mp3 = g("mp3").replace("-lq.mp3", "-hq.mp3")
            rel = f"sfx/freesound/{ten_file(q)}/{sid}.m4a"
            dich = os.path.join(RA, rel)
            if not os.path.exists(dich):
                p = os.path.join(tam, "fs", sid + ".mp3")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, "wb").write(tai(mp3))
                chuyen(p, dich, 128, chuan_hoa=True)
                time.sleep(0.5)
            lay += 1
            ds.append({"id": "fs-" + sid, "loai": "sfx", "nhom": nhom, "ten": f"{ten} {lay}", "file": rel,
                       "thoi_luong": round(dai, 3), "the": [q], "mo_ta": html.unescape(g("title")),
                       "tac_gia": g("username"), "giay_phep": "CC0-1.0",
                       "nguon": f"https://freesound.org/people/{g('username')}/sounds/{sid}/"})
        print(f"  freesound '{q}': {lay}")


def _fma_cc0(url_bai: str) -> bool:
    t = tai(url_bai).decode("utf-8", "replace")
    time.sleep(1)
    return "publicdomain/zero" in t or "CC0 1.0" in t


def nhac_fma(tam: str, ds: list) -> None:
    for nhom, album, so in FMA_ALBUM:
        t = tai(album).decode("utf-8", "replace")
        time.sleep(1)
        lay = 0
        for x in re.findall(r"data-track-info='([^']+)'", t):
            if lay >= so:
                break
            bai = json.loads(html.unescape(x))
            if "holiznacc0" not in bai["url"] or not _fma_cc0(bai["url"]):
                continue
            rel = f"nhac/holiznacc0/{ten_file(bai['title'])}.m4a"
            dich = os.path.join(RA, rel)
            if not os.path.exists(dich):
                p = os.path.join(tam, "fma", bai["fileName"])
                os.makedirs(os.path.dirname(p), exist_ok=True)
                if not os.path.exists(p):
                    open(p, "wb").write(tai(bai["fileUrl"], 300))
                if thoi_luong(p) > NHAC_TOI_DA:
                    continue
                chuyen(p, dich, 96)
            lay += 1
            ds.append({"id": "fma-" + str(bai["id"]), "loai": "nhac", "nhom": nhom, "ten": bai["title"], "file": rel,
                       "thoi_luong": thoi_luong(dich), "the": [bai.get("albumTitle", "")], "mo_ta": bai.get("albumTitle", ""),
                       "tac_gia": "HoliznaCC0", "giay_phep": "CC0-1.0", "nguon": bai["url"]})
        print(f"  FMA {album.rsplit('/', 1)[-1]}: {lay}")


def _nhom_theo_ten(ten: str) -> str:
    t = ten.lower()
    for tu, nhom in (("sad", "Buồn & cảm xúc"), ("battle", "Hành động"), ("boss", "Hành động"), ("fight", "Hành động"),
                     ("happy", "Vui tươi"), ("fun", "Vui tươi"), ("adventure", "Phiêu lưu"), ("mystery", "Hồi hộp"),
                     ("dark", "Hồi hộp"), ("calm", "Nhẹ nhàng"), ("relax", "Nhẹ nhàng")):
        if tu in t:
            return nhom
    return "Phiêu lưu"


def nhac_oga(tam: str, ds: list, toi_da: int = 10) -> None:
    trang = tai(OGA_NGUOI).decode("utf-8", "replace")
    lay = 0
    for duong in sorted(set(re.findall(r'href="(/content/[^"#?]+)"', trang))):
        if lay >= toi_da:
            break
        t = tai("https://opengameart.org" + duong).decode("utf-8", "replace")
        time.sleep(1)
        lic = re.findall(r"class=['\"]license-name['\"][^>]*>([^<]+)<", t)
        if not lic or any(x.strip() != "CC0" for x in lic):
            continue          # chỉ nhận trang ghi DUY NHẤT CC0
        for mp3 in sorted(set(re.findall(r"https://opengameart\.org/sites/default/files/[^\"'<>]+\.mp3", t))):
            if "/styles/" in mp3 or "/audio_preview/" in mp3 or lay >= toi_da:
                continue
            ten = urllib.parse.unquote(mp3.rsplit("/", 1)[-1])[:-4]
            ten = re.sub(r"^Komiku - |_\d+$", "", ten)
            rel = f"nhac/komiku/{ten_file(ten)}.m4a"
            dich = os.path.join(RA, rel)
            if not os.path.exists(dich):
                p = os.path.join(tam, "oga", ten_file(ten) + ".mp3")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                if not os.path.exists(p):
                    open(p, "wb").write(tai(mp3, 300))
                if not 20 < thoi_luong(p) <= NHAC_TOI_DA:
                    continue
                chuyen(p, dich, 96)
            lay += 1
            ds.append({"id": "oga-" + ten_file(ten), "loai": "nhac", "nhom": _nhom_theo_ten(ten), "ten": ten, "file": rel,
                       "thoi_luong": thoi_luong(dich), "the": [], "mo_ta": "",
                       "tac_gia": "Komiku (Loyalty Freak Music)", "giay_phep": "CC0-1.0",
                       "nguon": "https://opengameart.org" + duong})
            break             # mỗi trang một bài
    print(f"  OpenGameArt Komiku: {lay}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tam", default=os.path.join(tempfile.gettempdir(), "xay_thu_vien_am"))
    ap.add_argument("--bo-sfx-kit", action="store_true")
    ap.add_argument("--bo-freesound", action="store_true")
    ap.add_argument("--bo-nhac", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.tam, exist_ok=True)
    mf = os.path.join(RA, "thu_vien.json")
    cu = json.load(open(mf, encoding="utf-8"))["muc"] if os.path.exists(mf) else []
    ds: list = []
    for bo, ham, tien_to in ((a.bo_sfx_kit, sfx_kit, "kit-"), (a.bo_freesound, freesound, "fs-"),
                             (a.bo_nhac, lambda t, d: (nhac_fma(t, d), nhac_oga(t, d)), ("fma-", "oga-"))):
        if bo:
            ds += [m for m in cu if m["id"].startswith(tien_to)]
        else:
            ham(a.tam, ds)
    # Bỏ trùng id (cùng một file Freesound xuất hiện ở 2 từ khoá).
    thay, kq = set(), []
    for m in ds:
        if m["id"] not in thay:
            thay.add(m["id"])
            kq.append(m)
    with open(mf, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"phien_ban": 1, "ghi_chu": "Toàn bộ CC0 — dùng tự do, kể cả thương mại, không cần ghi nguồn.",
                   "muc": kq}, f, ensure_ascii=False, indent=1)
    tong = sum(os.path.getsize(os.path.join(RA, m["file"])) for m in kq)
    print(f"Xong: {sum(m['loai'] == 'sfx' for m in kq)} SFX, {sum(m['loai'] == 'nhac' for m in kq)} bài nhạc, {tong / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
