"""Dựng thư viện âm thanh có sẵn của editor: assets/thu_vien_am/ (SFX + nhạc nền, CHỈ giấy phép CC0).

Chạy lại được (bỏ qua file đã có). Kết quả commit vào git để app dùng offline:
    python scripts/xay_thu_vien_am.py [--tam <thư mục tải tạm>] [--bo-sfx-kit] [--bo-freesound] [--bo-nhac]

Nguồn (mỗi mục đều kiểm tra giấy phép CC0 ngay trên trang trước khi tải):
  - wyzowl/sfx-kit  (GitHub, CC0-1.0)          — 320 SFX cho video/motion (whoosh, pop, UI, impact…)
  - Freesound       (lọc license CC0, nhiều lượt tải nhất) — SFX hay dùng khi edit (cười, vỗ tay, boing…)
  - Freesound       (CC0, bài dài ≥ 15 giây)   — nhạc nền hài, kịch tính, buồn, lãng mạn (FREESOUND_NHAC)
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
    ("Giọng người & cảm xúc", "Cười to", "laugh", 3, 8), ("Giọng người & cảm xúc", "Em bé cười", "baby laugh", 2, 8),
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
    ("Đời thường", "Bong bóng", "bubble pop", 3, 3), ("Giọng người & cảm xúc", "Hắt xì", "sneeze", 2, 3),
    ("Thiên nhiên", "Mưa", "rain", 3, 20), ("Thiên nhiên", "Sấm", "thunder", 3, 12), ("Thiên nhiên", "Gió", "wind", 3, 20),
    ("Thiên nhiên", "Chim hót", "birds chirping", 3, 20),
    ("Động vật", "Chó sủa", "dog bark", 3, 4), ("Động vật", "Mèo kêu", "cat meow", 3, 4), ("Động vật", "Gà gáy", "rooster", 2, 6),
    ("Kinh dị & hồi hộp", "Hét", "scream", 3, 5), ("Kinh dị & hồi hộp", "Kịch tính (dun dun dun)", "dramatic sting", 3, 8),
    ("Kinh dị & hồi hộp", "Ma quái", "ghost", 3, 10), ("Kinh dị & hồi hộp", "Hồi hộp", "suspense", 3, 10),
    ("Lấp lánh & phép thuật", "Phép thuật", "magic wand", 3, 5), ("Lấp lánh & phép thuật", "Dịch chuyển", "teleport", 2, 4),
    # ---- Bổ sung: SFX hay gặp trong video ngắn / recap / hoạt hình gần đây
    ("Tua băng & nhiễu hình", "Tua ngược băng (rewind)", "tape rewind", 4, 6),
    ("Tua băng & nhiễu hình", "Tua ngược thời gian (rewind)", "rewind", 3, 8),
    ("Tua băng & nhiễu hình", "Tua băng cassette", "cassette rewind", 3, 6), ("Tua băng & nhiễu hình", "Tua nhanh (fast forward)", "fast forward", 3, 6), ("Tua băng & nhiễu hình", "Nhiễu TV (static)", "tv static", 3, 8),
    ("Tua băng & nhiễu hình", "Glitch lỗi hình", "glitch", 4, 4), ("Tua băng & nhiễu hình", "Tắt TV", "tv turn off", 2, 4),
    ("Tua băng & nhiễu hình", "Máy chiếu phim cũ", "film projector", 2, 12), ("Tua băng & nhiễu hình", "Chậm lại (slow motion)", "slow motion", 3, 6),
    ("Tua băng & nhiễu hình", "Hồi tưởng (flashback)", "flashback", 2, 6), ("Tua băng & nhiễu hình", "Dừng thời gian", "time stop", 2, 5),
    ("Tua băng & nhiễu hình", "Đĩa than lạo xạo", "vinyl crackle", 2, 15), ("Tua băng & nhiễu hình", "Nhiễu radio", "radio static", 2, 8),
    ("Động vật", "Quạ kêu", "crow caw", 4, 6), ("Động vật", "Cú kêu đêm", "owl hoot", 3, 6), ("Động vật", "Sói hú", "wolf howl", 3, 10),
    ("Động vật", "Bò kêu", "cow moo", 3, 5), ("Động vật", "Vịt kêu", "duck quack", 3, 4), ("Động vật", "Cừu kêu", "sheep baa", 2, 4),
    ("Động vật", "Dê kêu", "goat bleat", 2, 4), ("Động vật", "Ngựa hí", "horse neigh", 3, 5), ("Động vật", "Ngựa phi", "horse gallop", 2, 8),
    ("Động vật", "Lợn kêu", "pig oink", 2, 4), ("Động vật", "Ếch kêu", "frog croak", 3, 6), ("Động vật", "Ve kêu mùa hè", "cicadas", 3, 15),
    ("Động vật", "Muỗi vo ve", "mosquito buzz", 2, 6), ("Động vật", "Ruồi bay", "fly buzz", 2, 6), ("Động vật", "Sư tử gầm", "lion roar", 2, 6),
    ("Động vật", "Khỉ kêu", "monkey", 2, 5), ("Động vật", "Voi rống", "elephant trumpet", 2, 6), ("Động vật", "Mèo gừ gừ", "cat purr", 2, 8),
    ("Động vật", "Mèo khè", "cat hiss", 2, 4), ("Động vật", "Gà mái cục tác", "chicken cluck", 2, 6),
    ("Động vật", "Diều hâu rít", "hawk", 2, 5), ("Động vật", "Hải âu", "seagulls", 2, 10), ("Động vật", "Chó gầm gừ", "dog growl", 2, 5),
    ("Động vật", "Chó rên", "dog whine", 2, 5), ("Động vật", "Rắn rít", "snake hiss", 2, 5),
    ("Giọng người & cảm xúc", "Hít hà kinh ngạc (gasp)", "gasp", 3, 3), ("Giọng người & cảm xúc", "Thở dài", "sigh", 3, 4),
    ("Giọng người & cảm xúc", "Ngáp", "yawn", 2, 5), ("Giọng người & cảm xúc", "Ngáy", "snore", 3, 8),
    ("Giọng người & cảm xúc", "Ho", "cough", 2, 4), ("Giọng người & cảm xúc", "Nuốt nước bọt (gulp)", "gulp", 3, 3),
    ("Giọng người & cảm xúc", "Khóc", "crying", 3, 8), ("Giọng người & cảm xúc", "Em bé khóc", "baby crying", 2, 8),
    ("Giọng người & cảm xúc", "Cười gian ác", "evil laugh", 3, 6), ("Giọng người & cảm xúc", "Cười khúc khích", "giggle", 3, 5),
    ("Giọng người & cảm xúc", "Huýt sáo trêu", "wolf whistle", 2, 4), ("Giọng người & cảm xúc", "Suỵt", "shh", 2, 3),
    ("Giọng người & cảm xúc", "Trẻ con reo yay", "kids yay", 3, 6), ("Giọng người & cảm xúc", "Wow", "wow", 3, 3),
    ("Giọng người & cảm xúc", "Uh oh", "uh oh", 2, 3), ("Giọng người & cảm xúc", "Hmm", "hmm", 2, 3),
    ("Giọng người & cảm xúc", "Hả? (huh)", "huh", 2, 2), ("Giọng người & cảm xúc", "Ui da (ouch)", "ouch", 2, 3),
    ("Giọng người & cảm xúc", "Thở dốc", "heavy breathing", 2, 10), ("Giọng người & cảm xúc", "Hắng giọng", "clearing throat", 2, 3),
    ("Hài hước", "Còi hơi (air horn)", "air horn", 3, 5), ("Hài hước", "Kèn hề (honk)", "clown horn", 3, 3),
    ("Hài hước", "Bíp che chữ (censor beep)", "censor beep", 2, 3), ("Hài hước", "Lò xo", "spring boing", 2, 4),
    ("Hài hước", "Trượt vỏ chuối", "cartoon slip", 2, 4), ("Hài hước", "Đồng hồ cúc cu", "cuckoo clock", 2, 6),
    ("Hài hước", "Kèn kazoo", "kazoo", 2, 6), ("Hài hước", "Chớp mắt", "cartoon blink", 2, 2),
    ("Hài hước", "Đi rón rén (pizzicato)", "pizzicato", 2, 8), ("Hài hước", "Bẹp (splat)", "splat", 3, 3),
    ("Hài hước", "Lắc lư (wobble)", "wobble", 2, 4), ("Hài hước", "Dây đàn bật (twang)", "twang", 2, 3),
    ("Hài hước", "Cắn / táp", "cartoon bite", 2, 3),
    ("Kinh dị & hồi hộp", "Hù doạ (jumpscare)", "jumpscare", 3, 5), ("Kinh dị & hồi hộp", "Ù tai", "ear ringing", 2, 10),
    ("Kinh dị & hồi hộp", "Thì thầm rợn người", "creepy whisper", 2, 8), ("Kinh dị & hồi hộp", "Nền kinh dị", "horror ambience", 3, 15),
    ("Kinh dị & hồi hộp", "Chuông nhà thờ", "church bell", 3, 10), ("Kinh dị & hồi hộp", "Bẻ xương răng rắc", "bone crack", 3, 3),
    ("Kinh dị & hồi hộp", "Hộp nhạc ma quái", "creepy music box", 2, 15), ("Kinh dị & hồi hộp", "Quái vật gầm", "monster growl", 3, 6),
    ("Kinh dị & hồi hộp", "Zombie", "zombie", 2, 6), ("Kinh dị & hồi hộp", "Xích sắt", "chains", 2, 6),
    ("Kinh dị & hồi hộp", "Phù thuỷ cười", "witch laugh", 2, 6), ("Kinh dị & hồi hộp", "Dao đâm", "knife stab", 2, 3),
    ("Hành động", "Tát", "slap", 3, 3), ("Hành động", "Tát vào mặt", "face slap", 3, 3), ("Hành động", "Rút kiếm", "sword unsheathe", 3, 3),
    ("Hành động", "Kiếm chạm nhau", "sword clash", 3, 3), ("Hành động", "Bắn cung", "bow arrow", 3, 4),
    ("Hành động", "Súng máy", "machine gun", 2, 6), ("Hành động", "Lên đạn", "gun reload", 3, 4),
    ("Hành động", "Đạn sượt (ricochet)", "ricochet", 2, 3), ("Hành động", "Kim loại va (clang)", "metal clang", 3, 4),
    ("Hành động", "Gỗ gãy", "wood break", 2, 4), ("Hành động", "Đá lở", "rock fall", 2, 6), ("Hành động", "Bom rơi (rít)", "bomb falling", 2, 6),
    ("Hành động", "Đại bác", "cannon", 2, 5), ("Hành động", "Đổ vỡ loảng xoảng", "crash debris", 3, 5),
    ("Xe cộ & còi", "Còi ô tô", "car horn", 3, 4), ("Xe cộ & còi", "Phanh gấp / rít lốp", "tire screech", 3, 5),
    ("Xe cộ & còi", "Tai nạn xe", "car crash", 3, 6), ("Xe cộ & còi", "Nổ máy xe", "car start", 2, 8),
    ("Xe cộ & còi", "Xe chạy vụt qua", "car pass by", 2, 8), ("Xe cộ & còi", "Đóng cửa xe", "car door", 2, 3),
    ("Xe cộ & còi", "Còi cảnh sát", "police siren", 3, 10), ("Xe cộ & còi", "Còi cứu thương", "ambulance siren", 2, 10),
    ("Xe cộ & còi", "Còi tàu hoả", "train horn", 2, 8), ("Xe cộ & còi", "Máy bay", "airplane", 2, 15), ("Xe cộ & còi", "Xe máy", "motorcycle", 3, 8),
    ("Xe cộ & còi", "Chuông xe đạp", "bicycle bell", 2, 3), ("Xe cộ & còi", "Trực thăng", "helicopter", 2, 12),
    ("Xe cộ & còi", "Còi tàu thuỷ", "ship horn", 2, 8),
    ("Đời thường", "Đóng sầm cửa", "door slam", 3, 3), ("Đời thường", "Mở cửa", "door open", 2, 4), ("Đời thường", "Chuông cửa", "doorbell", 3, 4),
    ("Đời thường", "Công tắc đèn", "light switch", 2, 2), ("Đời thường", "Chùm chìa khoá", "keys jingle", 2, 4),
    ("Đời thường", "Vò giấy", "paper crumple", 2, 4), ("Đời thường", "Lật trang sách", "page turn", 3, 3), ("Đời thường", "Kéo khoá", "zipper", 2, 3),
    ("Đời thường", "Xả bồn cầu", "toilet flush", 2, 10), ("Đời thường", "Đồng hồ báo thức", "alarm clock", 3, 8),
    ("Đời thường", "Chuông trường", "school bell", 2, 8), ("Đời thường", "Nước nhỏ giọt", "water drip", 2, 6),
    ("Đời thường", "Vòi sen", "shower", 2, 12), ("Đời thường", "Kéo cắt", "scissors", 2, 3), ("Đời thường", "Quẹt diêm", "match strike", 2, 4),
    ("Đời thường", "Bật lửa", "lighter", 2, 3), ("Đời thường", "Vỗ tay 1 cái", "hand clap", 2, 2), ("Đời thường", "Búng tay", "finger snap", 3, 2),
    ("Đời thường", "Điện thoại rung", "phone vibrate", 3, 5), ("Đời thường", "Ấm nước reo", "kettle whistle", 2, 10),
    ("Đời thường", "Lò vi sóng", "microwave", 2, 8), ("Đời thường", "Lò vi sóng kêu ting", "microwave beep", 2, 4), ("Đời thường", "Búa đóng", "hammer nail", 2, 4),
    ("Đời thường", "Xé vải / giấy", "ripping", 2, 3), ("Đời thường", "Máy đánh chữ", "typewriter", 2, 5),
    ("Đời thường", "Xịt (spray)", "spray", 2, 3),
    ("Ăn uống", "Nhai rộp rộp", "crunch", 3, 4), ("Ăn uống", "Húp sùm sụp", "slurp", 3, 3), ("Ăn uống", "Uống ừng ực", "drinking", 2, 5),
    ("Ăn uống", "Nhai", "chewing", 2, 6), ("Ăn uống", "Chiên xèo xèo", "sizzle", 3, 10), ("Ăn uống", "Bật nút chai", "cork pop", 2, 3),
    ("Ăn uống", "Mở lon nước", "can open", 3, 3), ("Ăn uống", "Rót nước", "pouring water", 2, 8), ("Ăn uống", "Đá lanh canh", "ice cubes", 2, 4),
    ("Ăn uống", "Bụng réo", "stomach growl", 3, 5), ("Ăn uống", "Nước sôi", "boiling water", 2, 10), ("Ăn uống", "Thái rau", "chopping", 2, 6),
    ("Ăn uống", "Bát đĩa", "dishes", 2, 5),
    ("Thiên nhiên", "Lửa cháy tí tách", "fire crackling", 3, 15),
    ("Thiên nhiên", "Suối chảy", "stream", 2, 20), ("Thiên nhiên", "Đêm khuya", "night ambience", 2, 20), ("Thiên nhiên", "Rừng", "forest ambience", 2, 20),
    ("Thiên nhiên", "Động đất", "earthquake", 2, 15),
    ("Thiên nhiên", "Thác nước", "waterfall", 2, 15), ("Thiên nhiên", "Lá xào xạc", "leaves rustling", 2, 10),
    ("Thiên nhiên", "Dưới nước", "underwater", 2, 12),
    ("Gameshow", "Thua (fail)", "fail", 3, 4), ("Gameshow", "Chiến thắng", "victory", 3, 6), ("Gameshow", "Máy đánh bạc", "slot machine", 2, 6),
    ("Gameshow", "Đồng hồ đếm giờ", "timer", 2, 10), ("Gameshow", "Quay vòng quay", "wheel spin", 2, 8),
    ("Gameshow", "Còi trọng tài", "referee whistle", 3, 3),
    ("Gameshow", "Búa toà", "gavel", 2, 3),
    ("Game 8-bit", "Nhặt xu", "coin pickup", 3, 2), ("Game 8-bit", "Nhảy", "retro jump", 3, 2),
    ("Game 8-bit", "Tăng sức mạnh (power up)", "power up", 3, 4), ("Game 8-bit", "Game over", "game over", 3, 5),
    ("Game 8-bit", "Nổ 8-bit", "8bit explosion", 2, 3), ("Game 8-bit", "Trúng đòn", "retro hit", 2, 2), ("Game 8-bit", "Máy arcade", "arcade", 2, 5),
    ("Game 8-bit", "Chọn menu", "menu select", 2, 2),
    ("Khoa học viễn tưởng", "Súng laser", "laser", 4, 3), ("Khoa học viễn tưởng", "Robot", "robot", 3, 5),
    ("Khoa học viễn tưởng", "Phi thuyền", "spaceship", 3, 10), ("Khoa học viễn tưởng", "Điện giật / tia lửa điện", "electric zap", 3, 4),
    ("Khoa học viễn tưởng", "Sập nguồn (power down)", "power down", 3, 5), ("Khoa học viễn tưởng", "Sonar", "sonar", 2, 5),
    ("Khoa học viễn tưởng", "Máy tính bíp", "computer beeps", 2, 5), ("Khoa học viễn tưởng", "Người ngoài hành tinh", "alien", 2, 6),
    ("Khoa học viễn tưởng", "Còi báo động", "alarm", 3, 8), ("Khoa học viễn tưởng", "Bước nhảy không gian (warp)", "warp", 2, 5),
    ("Lấp lánh & phép thuật", "Lấp lánh", "sparkle", 3, 4), ("Lấp lánh & phép thuật", "Chuông gió (mơ màng)", "wind chimes", 3, 10),
    ("Lấp lánh & phép thuật", "Đàn hạc lướt (giấc mơ)", "harp glissando", 3, 8), ("Lấp lánh & phép thuật", "Niệm phép", "magic spell", 3, 5),
    ("Lấp lánh & phép thuật", "Hồi máu", "heal", 2, 4), ("Lấp lánh & phép thuật", "Bụp khói (poof)", "poof", 2, 3),
    ("Lấp lánh & phép thuật", "Cầu lửa", "fireball", 3, 4), ("Lấp lánh & phép thuật", "Hợp xướng thiên thần", "choir", 3, 10),
    ("Nhạc cụ & điểm nhấn", "Cồng (gong)", "gong", 3, 8), ("Nhạc cụ & điểm nhấn", "Trống timpani", "timpani", 2, 6),
    ("Nhạc cụ & điểm nhấn", "Chũm choẹ", "cymbal crash", 3, 5), ("Nhạc cụ & điểm nhấn", "Dàn nhạc đánh mạnh", "orchestra hit", 3, 4),
    ("Nhạc cụ & điểm nhấn", "Violin buồn", "sad violin", 2, 15), ("Nhạc cụ & điểm nhấn", "Piano buồn", "sad piano", 2, 20),
    ("Nhạc cụ & điểm nhấn", "Kèn hiệu (fanfare)", "trumpet fanfare", 3, 6), ("Nhạc cụ & điểm nhấn", "Trống taiko", "taiko", 3, 6),
    ("Nhạc cụ & điểm nhấn", "Bass drop", "bass drop", 3, 6), ("Nhạc cụ & điểm nhấn", "Gảy guitar", "guitar strum", 2, 5),
    ("Nhạc cụ & điểm nhấn", "Trống bongo", "bongo", 2, 6), ("Nhạc cụ & điểm nhấn", "Sáo trúc Nhật (kiếm hiệp)", "shakuhachi", 2, 10),
    ("Nhạc cụ & điểm nhấn", "Mõ gỗ (anime)", "woodblock", 2, 2), ("Nhạc cụ & điểm nhấn", "Tù và xung trận", "war horn", 2, 8),
    ("Nhạc cụ & điểm nhấn", "Organ nhà thờ", "organ chord", 2, 10), ("Nhạc cụ & điểm nhấn", "Kẻng tam giác (ting)", "triangle", 2, 3),
    ("Tiền & mua bán", "Xu rơi", "coin drop", 3, 3),
    # ---- Kiểu tiểu phẩm hài / drama ngắn: bùm trầm, thịch, riser, chốt hài
    ("Hài hước", "Bùm trầm (boom meme)", "bass boom", 3, 4), ("Hài hước", "Thịch (thud)", "thud", 3, 2),
    ("Hài hước", "Nhạc chốt hài (comedy sting)", "comedy sting", 3, 6),
    ("Hài hước", "Ting (loé sáng)", "ting", 2, 2),
    ("Điện ảnh", "Riser căng dần", "riser", 3, 8), ("Điện ảnh", "Cú giật kịch tính (cinematic hit)", "cinematic hit", 3, 5),
    ("Điện ảnh", "Braam", "braam", 2, 6), ("Điện ảnh", "Âm trầm rung (sub drop)", "sub drop", 2, 5),
    ("Kinh dị & hồi hộp", "Violin căng thẳng (tremolo)", "violin tremolo", 2, 8),
    ("Kinh dị & hồi hộp", "Dây đàn giật mình (string stab)", "string stab", 2, 4),
    # ---- Đợt 3: mạng xã hội, không gian nền, đời thường Việt Nam
    ("Hài hước", "Trống bongo dạo", "bongo fill", 2, 6), ("Hài hước", "Đi rón rén (tiptoe)", "tiptoe", 2, 6), ("Hài hước", "Oof", "oof", 2, 2),
    ("Hài hước", "Nope", "nope", 2, 2), ("Hài hước", "Bloop", "bloop", 3, 2), ("Hài hước", "Chíp chíp (cute squeak)", "squeak", 3, 2),
    ("Hài hước", "Tiếng chuông loé ý tưởng", "idea bell", 2, 3), ("Hài hước", "Kèn trumpet thua cuộc", "fail trumpet", 2, 5),
    ("Hài hước", "Tiếng lắc đầu (cartoon shake)", "cartoon shake", 2, 3), ("Hài hước", "Vút lên (cartoon zip)", "cartoon zip", 3, 2),
    ("Hài hước", "Trượt phanh hoạt hình", "cartoon skid", 2, 3), ("Hài hước", "Nháy mắt lấp lánh (bling)", "bling", 3, 2),
    ("Mạng xã hội & điện thoại", "Tin nhắn đến", "message notification", 3, 3),
    ("Mạng xã hội & điện thoại", "Gửi tin (swoosh)", "message sent", 2, 2),
    ("Mạng xã hội & điện thoại", "Pop-up hiện ra", "pop up", 3, 2), ("Mạng xã hội & điện thoại", "Gõ phím điện thoại", "phone typing", 2, 5),
    ("Mạng xã hội & điện thoại", "Bắt đầu quay (record beep)", "record beep", 2, 3),
    ("Mạng xã hội & điện thoại", "Chuông đăng ký (bell)", "notification bell", 3, 3),
    ("Mạng xã hội & điện thoại", "Thành công (success)", "success", 3, 3), ("Mạng xã hội & điện thoại", "Lỗi (error)", "error", 3, 3),
    ("Mạng xã hội & điện thoại", "Mở khoá", "unlock", 2, 2), ("Mạng xã hội & điện thoại", "Click chuột", "mouse click", 3, 1),
    ("Mạng xã hội & điện thoại", "Cuộc gọi tút tút", "phone dial tone", 2, 6),
    ("Mạng xã hội & điện thoại", "Cúp máy", "phone hang up", 2, 4),
    ("Không gian & nền", "Phố xá xe cộ", "street ambience", 2, 20), ("Không gian & nền", "Chợ / đông người", "market ambience", 2, 20),
    ("Không gian & nền", "Quán cà phê", "cafe ambience", 2, 20), ("Không gian & nền", "Nhà hàng", "restaurant ambience", 2, 20),
    ("Không gian & nền", "Văn phòng", "office ambience", 2, 20), ("Không gian & nền", "Sân trường", "playground", 2, 20),
    ("Không gian & nền", "Đám đông rì rầm", "crowd talking", 2, 20), ("Không gian & nền", "Kẹt xe", "traffic", 2, 20),
    ("Không gian & nền", "Thành phố về đêm", "city night", 2, 20),
    ("Không gian & nền", "Mưa ngoài cửa sổ", "rain window", 2, 20),
    ("Không gian & nền", "Siêu thị", "supermarket", 2, 20), ("Không gian & nền", "Phòng yên tĩnh (room tone)", "room tone", 2, 15),
    ("Đời thường", "Túi ni lông sột soạt", "plastic bag", 3, 4), ("Đời thường", "Đặt cốc xuống bàn", "cup down", 2, 2),
    ("Đời thường", "Đếm tiền", "counting money", 2, 5), ("Đời thường", "Chuông thang máy", "elevator ding", 2, 3),
    ("Đời thường", "Ghế kẽo kẹt", "chair creak", 2, 4), ("Đời thường", "Bước chân chạy", "running footsteps", 3, 6),
    ("Đời thường", "Giày cao gót", "high heels", 2, 6), ("Đời thường", "Dép lê", "flip flops", 2, 5), ("Đời thường", "Quạt máy", "fan", 2, 10),
    ("Đời thường", "Rửa bát", "washing dishes", 2, 8), ("Đời thường", "Quét nhà", "sweeping", 2, 6), ("Đời thường", "Bấm bút", "pen click", 2, 2),
    ("Đời thường", "Viết bút chì", "pencil writing", 2, 5), ("Đời thường", "Mở ngăn kéo", "drawer", 2, 3),
    ("Đời thường", "Vải sột soạt", "cloth rustle", 2, 3), ("Đời thường", "Rơi đồ xuống sàn", "drop", 3, 2),
    ("Đời thường", "Gõ bàn", "table knock", 2, 2), ("Đời thường", "Hút ống hút", "straw", 2, 4), ("Đời thường", "Lắc đá trong ly", "ice shake", 2, 4),
    ("Xe cộ & còi", "Còi xe máy", "motorbike horn", 3, 3), ("Xe cộ & còi", "Xe tay ga", "scooter", 2, 8), ("Xe cộ & còi", "Xe tải", "truck", 2, 10),
    ("Xe cộ & còi", "Xe buýt", "bus", 2, 10), ("Xe cộ & còi", "Xe đạp", "bicycle", 2, 6),
    ("Xe cộ & còi", "Đề máy không nổ", "engine fail start", 2, 5),
    ("Kinh dị & hồi hộp", "Tim đập nhanh", "heartbeat fast", 2, 8), ("Kinh dị & hồi hộp", "Máy đo tim (ECG)", "ecg beep", 2, 8),
    ("Kinh dị & hồi hộp", "Tim ngừng đập (flatline)", "flatline", 2, 6), ("Kinh dị & hồi hộp", "Tiếng thở sợ hãi", "scared breathing", 2, 8),
    ("Kinh dị & hồi hộp", "Cửa sắt đóng sầm", "metal door", 2, 5), ("Kinh dị & hồi hộp", "Gió hú", "howling wind", 2, 15),
    ("Kinh dị & hồi hộp", "Quạ bay", "crows", 2, 10),
    ("Lấp lánh & phép thuật", "Hé lộ (magic reveal)", "magic reveal", 3, 5), ("Lấp lánh & phép thuật", "Thiên thần (angel)", "angel", 2, 6),
    ("Lấp lánh & phép thuật", "Chuông ngân (chime)", "chime", 3, 5), ("Lấp lánh & phép thuật", "Bùa sáng (shine)", "shine", 3, 3),
    ("Thiên nhiên", "Sóng biển", "ocean waves", 2, 40), ("Thiên nhiên", "Sấm sét", "lightning thunder", 2, 12),
    ("Thiên nhiên", "Mưa to", "heavy rain", 2, 20), ("Thiên nhiên", "Gió giật", "wind gust", 2, 8),
    ("Thiên nhiên", "Dế đêm", "night crickets", 2, 20), ("Thiên nhiên", "Ếch đêm mưa", "frogs night", 2, 20),
    ("Đám đông", "Đám đông cười", "crowd laugh", 3, 8), ("Đám đông", "Đám đông ồ lên (ooh)", "crowd ooh", 2, 6),
    ("Đám đông", "Đám đông hét", "crowd scream", 2, 8), ("Đám đông", "Trẻ con cười", "children laughing", 2, 8),
    ("Đám đông", "Vỗ tay ít người", "small applause", 2, 8), ("Đám đông", "Huýt sáo cổ vũ", "cheer whistle", 2, 5),
    ("Gameshow", "Đếm 3-2-1", "countdown", 3, 6), ("Gameshow", "Hết giờ", "time up", 2, 4), ("Gameshow", "Tích tắc hồi hộp", "ticking clock", 2, 10),
    ("Gameshow", "Trúng thưởng (jackpot)", "jackpot", 2, 6), ("Gameshow", "Hoàn thành màn", "level complete", 3, 5),
]

# Nhạc nền Freesound (CC0) — (nhóm, tên, từ khoá, số file, thời lượng tối đa); chỉ lấy bài dài từ NHAC_FS_TOI_THIEU giây.
NHAC_FS_TOI_THIEU = 15
FREESOUND_NHAC = [
    ("Hài hước", "Nhạc hài", "comedy music", 4, 120), ("Hài hước", "Nhạc vui nhộn", "funny music", 3, 120),
    ("Hài hước", "Nhạc lén lút", "sneaky music", 3, 120), ("Hài hước", "Nhạc hoạt hình", "cartoon music", 3, 120),
    ("Kịch tính & drama", "Nhạc kịch tính", "dramatic music", 4, 120), ("Kịch tính & drama", "Nhạc hồi hộp", "suspense music", 3, 120),
    ("Kịch tính & drama", "Nhạc căng thẳng", "tension music", 3, 120), ("Kịch tính & drama", "Dàn nhạc hùng tráng", "epic orchestral", 3, 120),
    ("Kịch tính & drama", "Nhạc violin", "violin music", 2, 120),
    ("Buồn & cảm xúc", "Nhạc buồn", "sad music", 3, 120), ("Buồn & cảm xúc", "Piano cảm xúc", "emotional piano", 3, 120),
    ("Lãng mạn", "Nhạc lãng mạn", "romantic music", 3, 120),
    ("Vui tươi", "Nhạc vui", "happy music", 3, 120), ("Vui tươi", "Nhạc sôi nổi", "upbeat music", 3, 120), ("Vui tươi", "Ukulele", "ukulele music", 2, 120),
    ("Hành động", "Nhạc rượt đuổi", "chase music", 2, 120), ("Hành động", "Nhạc hành động", "action music", 3, 120),
    ("Hồi hộp", "Nhạc bí ẩn", "mysterious music", 2, 120), ("Hồi hộp", "Nhạc kinh dị", "horror music", 2, 120),
    ("Hài hước", "Nhạc xiếc", "circus music", 2, 90), ("Hài hước", "Nhạc ngớ ngẩn", "silly music", 3, 90),
    ("Hài hước", "Nhạc kazoo / tuba", "tuba music", 2, 90),
    ("Kịch tính & drama", "Nhạc trailer", "trailer music", 3, 90), ("Kịch tính & drama", "Nhạc đấu trí", "intense music", 3, 90),
    ("Kịch tính & drama", "Nhạc hùng tráng", "heroic music", 2, 90),
    ("Buồn & cảm xúc", "Piano buồn", "sad piano music", 3, 90), ("Buồn & cảm xúc", "Guitar buồn", "sad guitar", 2, 90),
    ("Buồn & cảm xúc", "Nhạc nhớ nhung", "nostalgic music", 2, 90),
    ("Lãng mạn", "Nhạc tình yêu", "love music", 2, 90), ("Lãng mạn", "Guitar mộc", "acoustic guitar music", 3, 90),
   
    ("Vui tươi", "Nhạc dễ thương", "cute music", 3, 90), ("Vui tươi", "Nhạc thiếu nhi", "kids music", 3, 90),
    ("Vui tươi", "Nhạc tươi sáng", "cheerful music", 3, 90),
    ("Cổ trang & Á Đông", "Nhạc Trung Hoa", "chinese music", 3, 90), ("Cổ trang & Á Đông", "Đàn tranh (guzheng)", "guzheng", 3, 90),
    ("Cổ trang & Á Đông", "Đàn nhị (erhu)", "erhu", 2, 90), ("Cổ trang & Á Đông", "Sáo trúc", "bamboo flute", 3, 90),
    ("Cổ trang & Á Đông", "Nhạc châu Á", "asian music", 2, 90),
    ("Beat & hiện đại", "Hip hop beat", "hip hop beat", 3, 90), ("Beat & hiện đại", "Trap beat", "trap beat", 3, 90),
    ("Beat & hiện đại", "Lo-fi", "lofi music", 3, 90), ("Beat & hiện đại", "EDM", "edm music", 2, 90),
    ("Beat & hiện đại", "Funk", "funk music", 2, 90), ("Beat & hiện đại", "Rock", "rock music", 2, 90), ("Beat & hiện đại", "Phonk", "phonk", 2, 90),
    ("Nhẹ nhàng", "Nhạc thư giãn", "relaxing music", 3, 90), ("Nhẹ nhàng", "Ambient", "ambient music", 2, 90),
    ("Nhẹ nhàng", "Jazz nhẹ", "jazz music", 3, 90), ("Nhẹ nhàng", "Bossa nova", "bossa nova", 2, 90), ("Nhẹ nhàng", "Hộp nhạc", "music box", 2, 90),
    ("Hồi hộp", "Nhạc thám tử", "detective music", 2, 90), ("Hồi hộp", "Nhạc điệp viên", "spy music", 2, 90),
    ("Hồi hộp", "Nhạc ma quái", "creepy music", 2, 90),
    ("Game & 8-bit", "Nhạc 8-bit", "8bit music", 3, 90), ("Game & 8-bit", "Nhạc đánh trùm", "boss battle music", 2, 90),
    ("Game & 8-bit", "Nhạc chiến thắng", "victory music", 2, 90),
    ("Mở đầu & tin tức", "Nhạc mở đầu", "intro music", 3, 60), ("Mở đầu & tin tức", "Nhạc tin tức", "news music", 2, 60),
    ("Mở đầu & tin tức", "Nhạc quảng cáo", "corporate music", 2, 90),
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


def freesound(tam: str, ds: list, cu: list, danh_sach: list = FREESOUND, loai: str = "sfx", toi_thieu: float = 0.1) -> None:
    da_co: dict = {}          # từ khoá đã tải lần trước → giữ nguyên file (kết quả tìm đổi theo thời gian)
    for m in cu:
        if m["id"].startswith("fs-") and m.get("the"):
            da_co.setdefault(m["the"][0], []).append(m)
    for nhom, ten, q, so, toi_da in danh_sach:
        if q in da_co:
            ds += [{**m, "nhom": nhom} for m in da_co[q]]
            continue
        url = ("https://freesound.org/search/?q=" + urllib.parse.quote_plus(q)
               + "&f=license%3A%22Creative+Commons+0%22&s=Num+downloads+desc")
        try:
            trang = tai(url).decode("utf-8", "replace")
        except Exception as e:  # Freesound chập chờn: bỏ từ khoá này, lần chạy sau tự tải lại
            print(f"  freesound '{q}': LỖI {e}")
            continue
        time.sleep(1)
        lay = 0
        for khoi in trang.split('class="bw-search__result"')[1:]:
            if lay >= so:
                break
            if "Creative Commons 0" not in khoi and "cc0" not in khoi.lower():
                continue
            g = lambda k: (re.search(rf'data-{k}="([^"]*)"', khoi) or [None, ""])[1]  # noqa: E731
            sid, dai = g("sound-id"), float(g("duration") or 0)
            if not sid or not toi_thieu < dai <= toi_da:
                continue
            mp3 = g("mp3").replace("-lq.mp3", "-hq.mp3")
            rel = f"{loai}/freesound/{ten_file(q)}/{sid}.m4a"
            dich = os.path.join(RA, rel)
            if not os.path.exists(dich):
                p = os.path.join(tam, "fs", sid + ".mp3")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                try:
                    open(p, "wb").write(tai(mp3))
                    chuyen(p, dich, 128 if loai == "sfx" else 96, chuan_hoa=True)
                except Exception as e:  # một file hỏng/502: bỏ qua, lấy kết quả kế tiếp
                    print(f"  bỏ {sid}: {e}")
                    continue
                time.sleep(0.5)
            lay += 1
            ds.append({"id": "fs-" + sid, "loai": loai, "nhom": nhom, "ten": f"{ten} {lay}", "file": rel,
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
    for bo, ham, tien_to in ((a.bo_sfx_kit, sfx_kit, "kit-"), (a.bo_freesound, lambda t, d: (freesound(t, d, cu), freesound(t, d, cu, FREESOUND_NHAC, "nhac", NHAC_FS_TOI_THIEU)), "fs-"),
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
