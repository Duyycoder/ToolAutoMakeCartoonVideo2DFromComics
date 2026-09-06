"""Endpoint thu vien/tac vu: goi thang ham (khong dung TestClient) de test nhanh.

Khong mo File Explorer that, khong spawn tien trinh that - moi thu nang deu bi
monkeypatch. Muc tieu la kiem tra dieu kien dau vao va duong dan tra ve.
"""
import os

import pytest
from fastapi import HTTPException

import orchestrator.main as main
from orchestrator.storage import VideoLibrary


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """Thay thu vien that bang thu vien tam cho ca main lan pipeline."""
    fake = VideoLibrary(str(tmp_path / "storage"))
    monkeypatch.setattr(main, "library", fake)
    monkeypatch.setattr(main.pipeline, "library", fake)
    return fake


@pytest.fixture
def entry(lib, tmp_path):
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"0" * 512)
    return lib.register_local(str(src), title="Phim Mau")


def test_danh_sach_rong_khi_chua_co_gi(lib):
    assert main.list_videos() == []


def test_lay_chi_tiet_va_404(lib, entry):
    assert main.get_video(entry["entry_id"])["title"] == "Phim Mau"
    with pytest.raises(HTTPException) as e:
        main.get_video("khong_co")
    assert e.value.status_code == 404


def test_nhap_video_bao_loi_400_khi_duong_dan_sai(lib):
    with pytest.raises(HTTPException) as e:
        main.import_video(main.ImportSchema(path="Z:/khong/co/file.mp4"))
    assert e.value.status_code == 400


def test_xoa_video(lib, entry, monkeypatch):
    assert main.delete_video(entry["entry_id"])["status"] == "success"
    with pytest.raises(HTTPException):
        main.delete_video(entry["entry_id"])


def test_mo_thu_muc_tra_ve_duong_dan_dung(lib, entry, monkeypatch):
    opened = []
    monkeypatch.setattr(main, "_reveal_in_file_manager", opened.append)

    res = main.open_video_folder(entry["entry_id"], kind="output")

    assert res["path"] == lib.output_dir(entry["entry_id"])
    assert os.path.isdir(res["path"])          # tao san de nguoi dung khong thay loi
    assert opened == [res["path"]]


def test_mo_thu_muc_404_khi_khong_co_muc(lib):
    with pytest.raises(HTTPException) as e:
        main.open_video_folder("khong_co")
    assert e.value.status_code == 404


def test_mo_thu_muc_du_lieu_chung(lib, monkeypatch):
    monkeypatch.setattr(main, "_reveal_in_file_manager", lambda _p: None)
    assert main.open_storage_folder(kind="merged")["path"] == lib.merged_dir
    assert main.open_storage_folder(kind="videos")["path"] == lib.videos_dir


def test_luu_va_doc_phu_de(lib, entry):
    entry_id = entry["entry_id"]
    saved = main.save_sub(entry_id, main.SubSaveSchema(name="phim.vi.srt", content="noi dung"))
    assert saved["status"] == "success"
    assert main.read_sub(entry_id, name="phim.vi.srt").body.decode("utf-8") == "noi dung"


def test_doc_phu_de_khong_co_thi_404(lib, entry):
    with pytest.raises(HTTPException) as e:
        main.read_sub(entry["entry_id"], name="khong_co.srt")
    assert e.value.status_code == 404


def test_phat_video_chan_ten_file_bay(lib, entry):
    with pytest.raises(HTTPException) as e:
        main.play_video(entry["entry_id"], kind="output", name="../../video.json")
    assert e.value.status_code == 404


def test_tai_video_yeu_cau_it_nhat_mot_link(lib):
    with pytest.raises(HTTPException) as e:
        main.download_start(main.DownloadSchema(urls=["   "]))
    assert e.value.status_code == 400


def test_dich_yeu_cau_chon_video(lib):
    with pytest.raises(HTTPException) as e:
        main.translate_start(main.TranslateSchema(entry_ids=[]))
    assert e.value.status_code == 400


def test_dich_bao_loi_khi_video_khong_co_trong_thu_vien(lib):
    with pytest.raises(HTTPException) as e:
        main.translate_start(main.TranslateSchema(entry_ids=["khong_co"]))
    assert e.value.status_code == 404


def test_dich_bao_loi_khi_file_bien_mat(lib, entry, monkeypatch):
    os.remove(entry["file"])
    with pytest.raises(HTTPException) as e:
        main.translate_start(main.TranslateSchema(entry_ids=[entry["entry_id"]]))
    assert e.value.status_code == 400
    assert "khong con tren dia" in e.value.detail.lower().replace("ô", "o").replace("đ", "d") \
        or "không còn trên đĩa" in e.value.detail


def test_nap_srt_co_san_chi_cho_mot_video(lib, entry, tmp_path):
    src2 = tmp_path / "phim2.mp4"
    src2.write_bytes(b"0")
    other = lib.register_local(str(src2))
    body = main.TranslateSchema(entry_ids=[entry["entry_id"], other["entry_id"]],
                                sub_source="import", source_srt=str(tmp_path / "a.srt"))
    with pytest.raises(HTTPException) as e:
        main.translate_start(body)
    assert e.value.status_code == 400


def test_nap_srt_khong_ton_tai_thi_bao_ngay(lib, entry, tmp_path):
    body = main.TranslateSchema(entry_ids=[entry["entry_id"]], sub_source="import",
                                source_srt=str(tmp_path / "khong_co.srt"))
    with pytest.raises(HTTPException) as e:
        main.translate_start(body)
    assert e.value.status_code == 400


def test_dich_goi_pipeline_voi_dung_so_viec(lib, entry, monkeypatch):
    calls = {}

    def fake_start(task_key, jobs, args):
        calls["task_key"] = task_key
        calls["jobs"] = jobs
        return True

    monkeypatch.setattr(main.pipeline, "start_translate", fake_start)
    res = main.translate_start(main.TranslateSchema(entry_ids=[entry["entry_id"]]))

    assert res["count"] == 1
    assert calls["task_key"] == main.TASK_TRANSLATE
    assert calls["jobs"][0]["video_path"] == entry["file"]


def test_ghep_yeu_cau_it_nhat_mot_muc(lib):
    with pytest.raises(HTTPException) as e:
        main.merge_start(main.MergeSchema(items=[]))
    assert e.value.status_code == 400


def test_ghep_bao_loi_khi_file_khong_ton_tai(lib, entry):
    body = main.MergeSchema(items=[main.MergeItem(entry_id=entry["entry_id"],
                                                  kind="output", name="khong_co.mp4")])
    with pytest.raises(HTTPException) as e:
        main.merge_start(body)
    assert e.value.status_code == 400


def test_ghep_goi_pipeline_voi_duong_dan_that(lib, entry, monkeypatch):
    calls = {}
    monkeypatch.setattr(main.pipeline, "start_merge",
                        lambda task_key, files, name: calls.update(files=files, name=name) or True)
    body = main.MergeSchema(items=[main.MergeItem(entry_id=entry["entry_id"], kind="source")],
                            output_name="ban_ghep")
    res = main.merge_start(body)

    assert res["count"] == 1
    assert calls["files"] == [entry["file"]]
    assert calls["name"] == "ban_ghep"


def test_dung_tac_vu_khong_chay_thi_404(lib):
    with pytest.raises(HTTPException) as e:
        main.stop_task("translate")
    assert e.value.status_code == 404


def test_thong_ke_kem_tac_vu_dang_chay(lib, entry):
    stats = main.get_stats()
    assert stats["videos"] == 1
    assert stats["running_tasks"] == []
