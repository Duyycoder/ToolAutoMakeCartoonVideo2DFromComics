"""Chuan hoa ten tep chuong — quy tac ma buoc dich/TTS/ghep video dung de
nhan dien chuong. Tep sai quy tac bi bo qua lang le nen day la diem de vo.
"""
import pytest

from orchestrator import chapter_naming as cn


def mk(d, names, content="# Tieu de trong file\n\nNoi dung"):
    for n in names:
        (d / n).write_text(content, encoding="utf-8")


@pytest.mark.parametrize("fname,expected", [
    ("chuong_0012.md", 12),
    ("Chuong 12.md", 12),
    ("chương 12 - Co nhi London.md", 12),
    ("Chapter 12 - The Return.md", 12),
    ("Chap.12.txt", 12),
    ("Ch 7 - Hoi ket.md", 7),
    ("c15.md", 15),
    ("truyen_abc_c15.md", 15),
    ("012.md", 12),
    ("Truyen ABC - 12.md", 12),
    ("第12章 伦敦孤儿.md", 12),
    ("Chương 0012 - [VI] Co nhi London.md", 12),
    ("khong-co-so.md", None),
])
def test_parse_chapter_index(fname, expected):
    assert cn.parse_chapter_index(fname) == expected


@pytest.mark.parametrize("fname,expected", [
    ("chương 12 - Co nhi London.md", "Co nhi London"),
    ("Chapter 12 - The Return.md", "The Return"),
    ("chuong_0012.md", ""),
    ("第12章 伦敦孤儿.md", "伦敦孤儿"),
    ("Chương 0012 - [VI] Co nhi London.md", "Co nhi London"),
])
def test_title_from_filename(fname, expected):
    assert cn.title_from_filename(fname) == expected


def test_chapter_filename_bo_ky_tu_cam_va_cat_do_dai():
    name = cn.chapter_filename(3, 'Ban an: "cuoi cung" / muon mang')
    assert name == "Chương 0003 - [VI] Ban an cuoi cung muon mang.md"
    assert "/" not in name and ":" not in name

    dai = cn.chapter_filename(3, "x" * 200)
    assert len(dai) < 120

    # Tieu de rong -> van co ten dung quy tac
    assert cn.chapter_filename(5, "  ") == "Chương 0005 - [VI] Chương 5.md"


def test_chua_dich_thi_khong_gan_nhan_vi():
    assert cn.chapter_filename(1, "X", translated=False) == "Chương 0001 - X.md"


def test_normalize_giu_thu_tu_so_va_doi_txt_sang_md(tmp_path):
    src = tmp_path / "tai_ve"
    dst = tmp_path / "raw"
    src.mkdir()
    mk(src, ["Chuong 1.txt", "Chuong 2.txt", "Chuong 9.txt", "Chuong 10.txt"])

    assert cn.normalize_dir(str(src), str(dst), translated=True) == 4
    ten = sorted(p.name for p in dst.iterdir())
    assert ten[0].startswith("Chương 0001 - [VI] ")
    assert ten[-1].startswith("Chương 0010 - [VI] ")
    assert all(n.endswith(".md") for n in ten)
    # Thu muc nguon khong bi dong vao
    assert len(list(src.iterdir())) == 4


def test_normalize_lay_tieu_de_tu_noi_dung_khi_ten_chi_co_so(tmp_path):
    src = tmp_path / "tai_ve"
    src.mkdir()
    (src / "chuong_0001.md").write_text(
        "## Chương 1: Buoc chan vao coi sang\n\nNoi dung", encoding="utf-8")

    cn.normalize_dir(str(src), None, translated=True)
    assert [p.name for p in src.iterdir()] == [
        "Chương 0001 - [VI] Buoc chan vao coi sang.md"]


def test_normalize_danh_so_lai_khi_ten_khong_co_so(tmp_path):
    src = tmp_path / "tai_ve"
    src.mkdir()
    mk(src, ["mo dau.md", "phan hai.md", "ket thuc.md"])

    cn.normalize_dir(str(src), None, translated=True)
    so = sorted(p.name.split(" - ")[0] for p in src.iterdir())
    assert so == ["Chương 0001", "Chương 0002", "Chương 0003"]


def test_normalize_danh_so_lai_khi_so_bi_trung(tmp_path):
    src = tmp_path / "tai_ve"
    src.mkdir()
    mk(src, ["tap 1 phan a.md", "tap 1 phan b.md"])

    cn.normalize_dir(str(src), None, translated=True)
    so = sorted(p.name.split(" - ")[0] for p in src.iterdir())
    assert so == ["Chương 0001", "Chương 0002"]


def test_normalize_khong_dung_den_tep_da_dung_quy_tac(tmp_path):
    """raw/ cua truyen da cao co ca ban goc lan ban [VI] trung so chuong —
    chay chuan hoa len do khong duoc xao tron gi."""
    src = tmp_path / "raw"
    src.mkdir()
    mk(src, [
        "Chương 0001 - 第1章 伦敦孤儿.md",
        "Chương 0001 - [VI] Co nhi London.md",
        "Chương 0002 - 第2章 奖学金.md",
        "Chương 0002 - [VI] Che do hoc bong.md",
    ])
    truoc = sorted(p.name for p in src.iterdir())

    assert cn.normalize_dir(str(src), None, translated=True) == 0
    assert sorted(p.name for p in src.iterdir()) == truoc


def test_normalize_chay_lai_khong_doi_gi_them(tmp_path):
    src = tmp_path / "tai_ve"
    src.mkdir()
    mk(src, ["Chuong 1.txt", "Chuong 2.txt"])

    cn.normalize_dir(str(src), None, translated=True)
    truoc = sorted(p.name for p in src.iterdir())
    assert cn.normalize_dir(str(src), None, translated=True) == 0
    assert sorted(p.name for p in src.iterdir()) == truoc


def test_dry_run_khong_dong_vao_dia(tmp_path):
    src = tmp_path / "tai_ve"
    src.mkdir()
    mk(src, ["chuong_0001.md"])

    assert cn.normalize_dir(str(src), None, translated=True, dry_run=True) == 1
    assert [p.name for p in src.iterdir()] == ["chuong_0001.md"]


def test_chep_sang_thu_muc_khac_van_lay_tep_da_dung_quy_tac(tmp_path):
    """Truyen tai ve san co ten dung chuan: khong duoc coi la "khong co gi de chep"."""
    src = tmp_path / "tai_ve"
    src.mkdir()
    mk(src, ["Chương 0001 - [VI] Mo dau.md", "Chương 0002 - [VI] Tiep theo.md"])
    dst = tmp_path / "raw"

    assert cn.normalize_dir(str(src), str(dst), translated=True) == 2
    assert sorted(p.name for p in dst.iterdir()) == [
        "Chương 0001 - [VI] Mo dau.md",
        "Chương 0002 - [VI] Tiep theo.md",
    ]


def test_chep_thu_muc_tron_ca_tep_chuan_lan_tep_lech(tmp_path):
    src = tmp_path / "tai_ve"
    src.mkdir()
    mk(src, ["Chương 0001 - [VI] Mo dau.md", "chuong_0002.txt"])
    dst = tmp_path / "raw"

    assert cn.normalize_dir(str(src), str(dst), translated=True) == 2
    assert sorted(p.name for p in dst.iterdir()) == [
        "Chương 0001 - [VI] Mo dau.md",
        "Chương 0002 - [VI] Tieu de trong file.md",
    ]
    # Thu muc nguon giu nguyen
    assert sorted(p.name for p in src.iterdir()) == [
        "Chương 0001 - [VI] Mo dau.md", "chuong_0002.txt"]
