import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "toolCaoTruyen")))
from translator.glossary_validator import loc_thuat_ngu

def test_glossary_validator_loai():
    # Tập hợp các trường hợp phải loại
    source_text = "恭喜你获得邀请函，即将成为新世界的玩家。罪人 第1章 一次测试 顾安 李慕生 阿生 张哥 俞震天 宛州 顺安城 俞家武馆 金盆洗手 林思之 请你设计一场游戏"
    
    terms = {
        "恭喜你获得邀请函，即将成为新世界的玩家。": "Chúc mừng bạn nhận được thư mời, sắp trở thành người chơi của thế giới mới.",
        "罪人": "罪犯",
        "一次测试": "一次测试",
        "第1章 一次测试": "Chương 1 Một lần thử nghiệm",
        "顾安": "Cố An", # Không có trong văn bản (test dưới sẽ dùng văn bản khác)
        "李慕生": "Li Mushi",
        "阿生": "A Sheng",
        "张哥": "Zhang Ge",
        "俞震天": "Yu Zhen Tian",
        "宛州": "Wan State",
        "顺安城": "Shun'an City",
        "俞家武馆": "Yu Family Martial Arts Academy",
        "金盆洗手": "Kim Phun Hau Sau (a term for retiring from one's profession)",
        "林思之": "Lin Si Zhi",
        "请你设计一场游戏": "Xin hãy thiết kế một trò chơi"
    }
    
    # 顾安 không có trong source_text này (vì mình sửa lại test_source không có 顾安)
    test_source_without_guan = source_text.replace("顾安", "")
    
    hop_le, bi_loai = loc_thuat_ngu(terms, test_source_without_guan)
    
    # MỖI ví dụ một assert
    assert "恭喜你获得邀请函，即将成为新世界的玩家。" in bi_loai
    assert bi_loai["恭喜你获得邀请函，即将成为新世界的玩家。"].startswith("key_")
    
    assert "罪人" in bi_loai
    assert bi_loai["罪人"].startswith("value_")
    
    assert "一次测试" in bi_loai
    assert bi_loai["一次测试"].startswith("value_")
    
    assert "第1章 一次测试" in bi_loai
    assert bi_loai["第1章 一次测试"].startswith("key_")
    
    assert "顾安" in bi_loai
    assert bi_loai["顾安"].startswith("key_")
    
    assert "李慕生" in bi_loai
    assert bi_loai["李慕生"].startswith("value_")
    
    assert "阿生" in bi_loai
    assert bi_loai["阿生"].startswith("value_")
    
    assert "张哥" in bi_loai
    assert bi_loai["张哥"].startswith("value_")
    
    assert "俞震天" in bi_loai
    assert bi_loai["俞震天"].startswith("value_")
    
    assert "宛州" in bi_loai
    assert bi_loai["宛州"].startswith("value_")
    
    assert "顺安城" in bi_loai
    assert bi_loai["顺安城"].startswith("value_")
    
    assert "俞家武馆" in bi_loai
    assert bi_loai["俞家武馆"].startswith("value_")
    
    assert "金盆洗手" in bi_loai
    assert bi_loai["金盆洗手"].startswith("value_")
    
    assert "林思之" in bi_loai
    assert bi_loai["林思之"].startswith("value_")
    
    assert "请你设计一场游戏" in bi_loai
    assert bi_loai["请你设计一场游戏"].startswith("key_")

def test_glossary_validator_giu():
    # Tập hợp các trường hợp phải giữ
    source_text = "李慕生 顾安 筑基 修为 宛州 林思之 游廊 赫敏 霍格沃茨 邓布利多 金手指"
    
    terms = {
        "李慕生": "Lý Mộ Sinh",
        "顾安": "Cố An",
        "筑基": "Trúc Cơ",
        "修为": "Tu vi",
        "宛州": "Uyển Châu",
        "林思之": "Lâm Tư Chi",
        "游廊": "Du Lang",
        "赫敏": "Hermione",
        "霍格沃茨": "Hogwarts",
        "邓布利多": "Dumbledore",
        "金手指": "Ngón tay vàng"
    }
    
    hop_le, bi_loai = loc_thuat_ngu(terms, source_text)
    
    # MỖI ví dụ một assert
    assert "李慕生" in hop_le
    assert "顾安" in hop_le
    assert "筑基" in hop_le
    assert "修为" in hop_le
    assert "宛州" in hop_le
    assert "林思之" in hop_le
    assert "游廊" in hop_le
    assert "赫敏" in hop_le
    assert "霍格沃茨" in hop_le
    assert "邓布利多" in hop_le
    assert "金手指" in hop_le


# Các cặp sai THẬT mà qwen2.5:7b-instruct trả về khi đo lượt 26 và bản lọc
# đầu tiên để lọt (chỉ soát pinyin khi cả chuỗi không có dấu Việt).
LOT_LUOT_26 = {
    "俞震天": "Yù Zhen Tian",
    "东厅": "Đông Halls",
    "后院": "Hậu Halls",
    "金盆洗手": "Kim Bát Xử Händig",
    "铁公鸡": "Thép Cocks Ông",
    "林思之": "Lâm Sīzhī",
    "金手指": "Ngón tay vàng / Hệ thống hack",
}


@pytest.mark.parametrize("key,value", list(LOT_LUOT_26.items()))
def test_loai_viet_lai_pinyin_tieng_anh(key, value):
    hop_le, bi_loai = loc_thuat_ngu({key: value}, "……" + key + "……")
    assert key not in hop_le, f"{key}->{value} phải bị loại"
    assert key in bi_loai


@pytest.mark.parametrize("key,value", [
    ("李慕生", "Lý Mộ Sinh"), ("张大壮", "Trương Đại Tráng"), ("青云宗", "Thanh Vân Tông"),
    ("江湖", "Giang Hồ"), ("内息", "Nội Tức"), ("顺安城", "Thuận An Thành"),
    ("修为", "Tu vi"), ("金手指", "Ngón tay vàng"), ("霍格沃茨", "Hogwarts"),
])
def test_giu_han_viet_hop_le(key, value):
    hop_le, _ = loc_thuat_ngu({key: value}, "……" + key + "……")
    assert hop_le.get(key) == value


# Sai âm Hán Việt THẬT do qwen2.5:7b-instruct trả về khi dịch lại (lượt 26b).
@pytest.mark.parametrize("key,value,dung", [
    ("俞震天", "Ý Trấn Thiên", "Du Chấn Thiên"),
    ("顺安城", "Thùy An Thành", "Thuận An Thành"),
    ("宛州", "Vạn Châu", "Uyển Châu"),
    ("郝深", "Hao Thâm", "Hác Thâm"),
])
def test_loai_sai_am_han_viet(key, value, dung):
    hop_le, bi_loai = loc_thuat_ngu({key: value}, "……" + key + "……")
    assert key not in hop_le
    assert bi_loai[key].startswith("value_") and dung in bi_loai[key]


def test_dich_lai_tra_bang_khong_goi_llm():
    from translator.glossary_validator import dich_lai_thuat_ngu

    class KhongDuocGoi:
        prompt_style = "chat"

        def call_ollama_api(self, **kw):
            raise AssertionError("đủ chữ trong bảng thì không được gọi LLM")

    ung_vien = ["俞震天", "宛州", "李慕生", "林思之"]
    kq = dich_lai_thuat_ngu(ung_vien, KhongDuocGoi(), "".join(ung_vien))
    assert kq == {"俞震天": "Du Chấn Thiên", "宛州": "Uyển Châu",
                  "李慕生": "Lý Mộ Sinh", "林思之": "Lâm Tư Chi"}


def test_dich_lai_chi_nhan_tu_da_hoi():
    from translator.glossary_validator import dich_lai_thuat_ngu

    class GiaLLM:
        prompt_style = "chat"

        def call_ollama_api(self, **kw):
            return '{"龘龘": "Đạp Đạp", "顾安": "Cố An"}'

    # 龘 không có trong bảng -> phải hỏi LLM; LLM trả thêm từ lạ thì bỏ
    kq = dich_lai_thuat_ngu(["龘龘"], GiaLLM(), "龘龘 顾安")
    assert "顾安" not in kq


def test_loai_key_co_chu_so():
    hop_le, bi_loai = loc_thuat_ngu({"2小时": "Hai Giờ"}, "等待2小时。")
    assert "2小时" not in hop_le and bi_loai["2小时"].startswith("key_")


def test_tra_bang_khong_bi_gioi_han_toi_da():
    from translator.glossary_validator import dich_lai_thuat_ngu

    class KhongDuocGoi:
        prompt_style = "chat"

        def call_ollama_api(self, **kw):
            raise AssertionError("không được gọi LLM")

    ung_vien = ["俞震天", "宛州", "李慕生", "林思之", "郝深"]
    kq = dich_lai_thuat_ngu(ung_vien, KhongDuocGoi(), "".join(ung_vien), toi_da=2)
    assert kq["郝深"] == "Hác Thâm" and len(kq) == 5
