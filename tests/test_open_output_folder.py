"""Nut "Mo thu muc dau ra": chon dung thu muc theo tung buoc + endpoint tra ve
duong dan that (khong goi File Explorer that trong test).
"""
import os

import pytest

import orchestrator.main as main


@pytest.fixture
def story(tmp_path, monkeypatch):
    """Mot truyen gia lap voi cay thu muc chuan, gan vao storage_mgr cua app."""
    root = tmp_path / "truyen" / "test_story"
    (root / "raw").mkdir(parents=True)
    (root / "video").mkdir()

    monkeypatch.setattr(main.storage_mgr, "get_story_dir", lambda _n: str(root))
    monkeypatch.setattr(main.storage_mgr, "read_story_meta",
                        lambda _n: {"story_name": "Test", "story_slug": "test_story"})
    return root


def test_step1_tro_ve_raw_khi_chua_dich(story):
    assert main._step_output_dir("Test", "step1") == str(story / "raw")


def test_step1_uu_tien_translated_khi_da_dich(story):
    (story / "translated").mkdir()
    (story / "translated" / "chuong_0001.md").write_text("x", encoding="utf-8")
    assert main._step_output_dir("Test", "step1") == str(story / "translated")


def test_translated_rong_van_dung_raw(story):
    """Thu muc translated ton tai nhung khong co .md -> van la raw."""
    (story / "translated").mkdir()
    assert main._step_output_dir("Test", "step1") == str(story / "raw")


def test_step2_dung_chung_thu_muc_voi_step1(story):
    """File .wav nam CANH file .md chu khong co thu muc audio rieng."""
    assert main._step_output_dir("Test", "step2") == main._step_output_dir("Test", "step1")


@pytest.mark.parametrize("step", ["step3", "step5"])
def test_cac_buoc_video_tro_ve_thu_muc_video(story, step):
    assert main._step_output_dir("Test", step) == str(story / "video")


def test_step4_theo_cau_hinh_autosub(story, monkeypatch, tmp_path):
    custom = tmp_path / "sub_out"
    monkeypatch.setattr(main, "load_global_config",
                        lambda: {"autosub": {"output_dir": str(custom)}})
    assert main._step_output_dir("Test", "step4") == str(custom)

    monkeypatch.setattr(main, "load_global_config", lambda: {})
    assert main._step_output_dir("Test", "step4") == str(story / "video")


def test_endpoint_tra_ve_duong_dan_va_so_file(story, monkeypatch):
    opened = []
    monkeypatch.setattr(main, "_reveal_in_file_manager", opened.append)
    (story / "raw" / "chuong_0001.md").write_text("x", encoding="utf-8")
    (story / "raw" / "chuong_0002.md").write_text("x", encoding="utf-8")

    res = main.open_story_folder("Test", step="step1")

    assert res["path"] == str(story / "raw")
    assert res["file_count"] == 2
    assert opened == [str(story / "raw")]


def test_endpoint_tao_thu_muc_neu_chua_co(story, monkeypatch):
    """Buoc chua chay -> thu muc chua ton tai, van mo duoc va bao 0 file."""
    monkeypatch.setattr(main, "_reveal_in_file_manager", lambda _p: None)
    import shutil
    shutil.rmtree(story / "video")

    res = main.open_story_folder("Test", step="step3")

    assert res["file_count"] == 0
    assert os.path.isdir(res["path"])


def test_endpoint_404_khi_khong_co_truyen(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(main.storage_mgr, "read_story_meta", lambda _n: None)
    with pytest.raises(HTTPException) as e:
        main.open_story_folder("Khong Ton Tai", step="step1")
    assert e.value.status_code == 404


def test_chi_tiet_truyen_kem_duong_dan_va_so_chuong(story, monkeypatch):
    """Truoc day giao dien hien 'Thu muc luu tru: undefined'."""
    monkeypatch.setattr(main.storage_mgr, "scan_chapters", lambda _n: [{"idx": 1}, {"idx": 2}])
    meta = main.get_story_details("Test")
    assert meta["story_dir"] == str(story)
    assert meta["raw_chapters_count"] == 2
