"""Thu vien video: dat ten thu muc an toan, quet thu muc, chan path traversal."""
import json
import os

import pytest

from orchestrator.storage import (
    VideoLibrary, batch_label, batch_order, human_size, new_batch_id, slugify,
)


def test_slugify_bo_dau_tieng_viet():
    assert slugify("Đắc Kỷ Trụ Vương") == "dac_ky_tru_vuong"


def test_slugify_bo_ky_tu_dac_biet():
    assert slugify("Hello @ World! - 123") == "hello_world_123"
    assert slugify("A   B___C- -D") == "a_b_c_d"
    assert slugify("_Hello_World_") == "hello_world"


def test_slugify_chuoi_rong_van_ra_ten_dung_duoc():
    # Ten thu muc khong duoc rong, neu khong os.makedirs se ghi de vao thu muc cha.
    assert slugify("") == "video"
    assert slugify("!@#$%^&*()") == "video"
    assert slugify("   ") == "video"


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(2048) == "2.0 KB"
    assert human_size(5 * 1024 * 1024) == "5.0 MB"


@pytest.fixture
def lib(tmp_path):
    return VideoLibrary(str(tmp_path / "storage"))


def make_entry(lib, entry_id="phim_abc", title="Phim ABC", with_file=True, **extra):
    entry_dir = lib.entry_dir(entry_id)
    os.makedirs(entry_dir, exist_ok=True)
    video_file = os.path.join(entry_dir, "phim.mp4")
    if with_file:
        with open(video_file, "wb") as fh:
            fh.write(b"0" * 1024)
    meta = {"entry_id": entry_id, "title": title, "file": video_file,
            "platform": "tiktok", "created_at": "2026-01-01T00:00:00", "duration": 61}
    meta.update(extra)
    with open(os.path.join(entry_dir, "video.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return entry_dir


def test_tao_thu_muc_con_khi_khoi_tao(lib):
    for path in (lib.videos_dir, lib.tasks_dir, lib.merged_dir):
        assert os.path.isdir(path)


@pytest.mark.parametrize("bad_id", ["..", "../secret", "a/b", "C:\\Windows", "", ".hidden"])
def test_entry_dir_chan_id_nguy_hiem(lib, bad_id):
    with pytest.raises(ValueError):
        lib.entry_dir(bad_id)


def test_doc_muc_va_bo_sung_thong_tin_quet_tu_dia(lib):
    make_entry(lib)
    entry = lib.read_entry("phim_abc")
    assert entry["title"] == "Phim ABC"
    assert entry["exists"] is True
    assert entry["size"] == 1024
    assert entry["size_human"] == "1.0 KB"
    assert entry["has_translation"] is False
    assert entry["subs"] == [] and entry["outputs"] == []


def test_muc_khong_ton_tai_tra_none(lib):
    assert lib.read_entry("khong_co") is None
    assert lib.read_entry("../../etc") is None


def test_co_ban_da_gan_sub_thi_danh_dau_da_dich(lib):
    make_entry(lib)
    out_dir = lib.output_dir("phim_abc")
    os.makedirs(out_dir)
    with open(os.path.join(out_dir, "phim_autosub.mp4"), "wb") as fh:
        fh.write(b"x")
    entry = lib.read_entry("phim_abc")
    assert entry["has_translation"] is True
    assert [o["name"] for o in entry["outputs"]] == ["phim_autosub.mp4"]


def test_list_entries_moi_nhat_truoc(lib):
    make_entry(lib, "cu", "Cu")
    make_entry(lib, "moi", "Moi")
    meta_path = lib.meta_path("moi")
    meta = json.load(open(meta_path, encoding="utf-8"))
    meta["created_at"] = "2026-06-01T00:00:00"
    json.dump(meta, open(meta_path, "w", encoding="utf-8"))
    assert [e["entry_id"] for e in lib.list_entries()] == ["moi", "cu"]


def test_them_va_doc_phu_de(lib):
    make_entry(lib)
    saved = lib.add_sub("phim_abc", "phim.vi.srt", "1\n00:00:00,000 --> 00:00:01,000\nXin chao\n")
    assert os.path.exists(saved["path"])
    assert [s["name"] for s in lib.read_entry("phim_abc")["subs"]] == ["phim.vi.srt"]


def test_them_phu_de_tu_dong_them_duoi_srt(lib):
    make_entry(lib)
    assert lib.add_sub("phim_abc", "khong_duoi", "x")["name"] == "khong_duoi.srt"


@pytest.mark.parametrize("bad_name", ["../video.json", "sub/../../x.srt", "C:\\a.srt"])
def test_find_file_chan_path_traversal(lib, bad_name):
    make_entry(lib)
    with pytest.raises((ValueError, FileNotFoundError)):
        lib.find_file("phim_abc", "sub", bad_name)


def test_find_file_source_tra_ve_file_goc(lib):
    entry_dir = make_entry(lib)
    assert lib.find_file("phim_abc", "source", "") == os.path.join(entry_dir, "phim.mp4")


def test_nhap_video_co_san_khong_chep_file(lib, tmp_path):
    src = tmp_path / "ngoai_thu_vien.mp4"
    src.write_bytes(b"abc")
    entry = lib.register_local(str(src))
    assert entry["file"] == str(src)          # chi tro toi, khong nhan doi file nang
    assert entry["source"] == "import"
    assert entry["title"] == "ngoai_thu_vien"


def test_nhap_video_co_chep_file(lib, tmp_path):
    src = tmp_path / "goc.mp4"
    src.write_bytes(b"abc")
    entry = lib.register_local(str(src), title="Ten Hien Thi", copy_file=True)
    assert entry["file"].startswith(lib.entry_dir(entry["entry_id"]))
    assert os.path.exists(src)                # ban goc van con


def test_nhap_video_bao_loi_ro_rang(lib, tmp_path):
    with pytest.raises(FileNotFoundError):
        lib.register_local(str(tmp_path / "khong_co.mp4"))
    txt = tmp_path / "a.txt"
    txt.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        lib.register_local(str(txt))


def test_id_trung_ten_duoc_danh_so(lib, tmp_path):
    src = tmp_path / "trung.mp4"
    src.write_bytes(b"a")
    first = lib.register_local(str(src))
    second = lib.register_local(str(src))
    assert first["entry_id"] != second["entry_id"]


def test_xoa_muc_giu_lai_file_goc_ben_ngoai(lib, tmp_path):
    src = tmp_path / "phim_ngoai.mp4"
    src.write_bytes(b"abc")
    entry = lib.register_local(str(src))
    assert lib.delete_entry(entry["entry_id"]) is True
    assert lib.read_entry(entry["entry_id"]) is None
    assert src.exists()


def test_don_thu_muc_tam(lib):
    tmp_dir = os.path.join(lib.tasks_dir, "prepare_abc")
    os.makedirs(tmp_dir)
    with open(os.path.join(tmp_dir, "preview.jpg"), "wb") as fh:
        fh.write(b"0" * 2048)

    preview = lib.cleanup_tasks(dry_run=True)
    assert preview["count"] == 1 and os.path.isdir(tmp_dir)

    done = lib.cleanup_tasks(dry_run=False)
    assert done["count"] == 1 and not os.path.exists(tmp_dir)


def test_dat_so_ngay_thi_giu_thu_muc_con_moi(lib):
    # keep_days=0 da bo so tuoi (tung chap chon tren Windows); nhung khi CO dat so
    # ngay thi van phai loc tuoi - thu muc vua tao chua du tuoi, khong duoc xoa.
    tmp_dir = os.path.join(lib.tasks_dir, "vua_tao")
    os.makedirs(tmp_dir)

    done = lib.cleanup_tasks(keep_days=1, dry_run=False)

    assert done["count"] == 0 and os.path.isdir(tmp_dir)


def test_thong_ke(lib):
    make_entry(lib)
    lib.add_sub("phim_abc", "phim.vi.srt", "x")
    stats = lib.stats()
    assert stats["videos"] == 1
    assert stats["subs"] == 1
    assert stats["duration_total"] == 61


# ------------------------------------------------------------------- LO VIDEO
# Ghep sai thu tu la loi nguoi dung chi phat hien khi xem het video da ghep,
# nen thu tu cua lo phai duoc kiem ky o day.
def test_nhap_file_ngoai_mang_theo_cho_dung_trong_lo(lib, tmp_path):
    src = tmp_path / "tap1.mp4"
    src.write_bytes(b"0" * 10)
    entry = lib.register_local(str(src), batch_id="lo_test", batch_index=3.5)
    assert (entry["batch_id"], entry["batch_index"]) == ("lo_test", 3.5)
    # Phai ghi xuong video.json chu khong chi nam trong RAM, neu khong tat app la mat thu tu.
    assert lib.read_entry(entry["entry_id"])["batch_index"] == 3.5


def test_lo_sap_theo_so_thu_tu_tang_dan(lib):
    make_entry(lib, "v_c", batch_id="lo_1", batch_index=3)
    make_entry(lib, "v_a", batch_id="lo_1", batch_index=1.002)
    make_entry(lib, "v_b", batch_id="lo_1", batch_index="1.001")  # adapter co the ghi dang chuoi
    make_entry(lib, "v_x", batch_id="lo_2", batch_index=1)

    assert [e["entry_id"] for e in lib.list_batch("lo_1")] == ["v_b", "v_a", "v_c"]
    assert [e["entry_id"] for e in lib.list_batch("lo_2")] == ["v_x"]


def test_lo_khong_dung_thu_tu_cua_thu_vien(lib):
    # list_entries tra ve MOI NHAT TRUOC; list_batch phai nguoc lai voi no.
    make_entry(lib, "v1", batch_id="lo_1", batch_index=1, created_at="2026-01-01T00:00:00")
    make_entry(lib, "v2", batch_id="lo_1", batch_index=2, created_at="2026-02-02T00:00:00")
    assert [e["entry_id"] for e in lib.list_entries()] == ["v2", "v1"]
    assert [e["entry_id"] for e in lib.list_batch("lo_1")] == ["v1", "v2"]


def test_muc_cu_khong_co_ma_lo_van_doc_duoc(lib):
    make_entry(lib, "phim_cu")
    assert lib.list_batch("") == []
    assert lib.list_batch("lo_khong_ton_tai") == []
    assert lib.list_batches() == []
    assert batch_order(lib.read_entry("phim_cu")) == 0.0


def test_tom_tat_cac_lo(lib):
    make_entry(lib, "v1", batch_id="lo_a_20260922_100000", batch_index=1,
               created_at="2026-09-22T10:00:05")
    make_entry(lib, "v2", batch_id="lo_a_20260922_100000", batch_index=2,
               created_at="2026-09-22T10:02:00")
    make_entry(lib, "v3", batch_id="lo_b_20260923_080000", batch_index=1,
               created_at="2026-09-23T08:00:10")
    lib.add_sub("v2", "phim.vi.srt", "x")

    batches = lib.list_batches()
    assert [g["batch_id"] for g in batches] == ["lo_b_20260923_080000", "lo_a_20260922_100000"]
    lo_a = batches[1]
    assert lo_a["count"] == 2 and lo_a["translated"] == 1
    # Moc cua lo la video DAU TIEN, khong phai video cuoi.
    assert lo_a["created_at"] == "2026-09-22T10:00:05"


def test_ma_lo_moi_va_nhan_de_doc():
    assert new_batch_id().startswith("lo_")
    assert new_batch_id("Phim Hay").startswith("lo_phim_hay_")
    assert batch_label("lo_phim_hay_20260922_154501") == "phim_hay (22/09 15:45)"
    assert batch_label("lo_20260922_154501") == "22/09 15:45"
    assert batch_label("linh_tinh") == "linh_tinh"
