"""Endpoint thu vien/tac vu: goi thang ham (khong dung TestClient) de test nhanh.

Khong mo File Explorer that, khong spawn tien trinh that - moi thu nang deu bi
monkeypatch. Muc tieu la kiem tra dieu kien dau vao va duong dan tra ve.
"""
import os

import pytest
from fastapi import HTTPException

import orchestrator.main as main
import orchestrator.pipeline as pipeline_mod
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


@pytest.fixture
def bat_ghep(monkeypatch):
    """Chan pipeline.start_merge lai de doc tham so gui xuong."""
    calls = {}

    def fake(task_key, files, name, sizes=None, normalize="auto"):
        calls.update(files=files, name=name, sizes=sizes, normalize=normalize)
        return True

    monkeypatch.setattr(main.pipeline, "start_merge", fake)
    return calls


def test_ghep_goi_pipeline_voi_duong_dan_that(lib, entry, bat_ghep):
    body = main.MergeSchema(items=[main.MergeItem(entry_id=entry["entry_id"], kind="source")],
                            output_name="ban_ghep")
    res = main.merge_start(body)

    assert res["count"] == 1
    assert bat_ghep["files"] == [entry["file"]]
    assert bat_ghep["name"] == "ban_ghep"


def test_ghep_gui_kem_kich_thuoc_doc_tu_video_json(lib, entry, bat_ghep):
    entry["width"], entry["height"] = 1080, 1920
    lib.write_entry(entry["entry_id"], entry)

    main.merge_start(main.MergeSchema(
        items=[main.MergeItem(entry_id=entry["entry_id"], kind="source")]))

    # Khong co ffprobe tren may dich -> W/H phai lay san tu video.json.
    assert bat_ghep["sizes"] == [(1080, 1920)]
    assert bat_ghep["normalize"] == "auto"


def test_tat_tu_chuan_hoa_thi_bao_xuong_pipeline(lib, entry, bat_ghep):
    main.merge_start(main.MergeSchema(
        items=[main.MergeItem(entry_id=entry["entry_id"], kind="source")], normalize=False))
    assert bat_ghep["normalize"] == "never"


def test_dung_tac_vu_khong_chay_thi_404(lib):
    with pytest.raises(HTTPException) as e:
        main.stop_task("translate")
    assert e.value.status_code == 404


# ------------------------------------------------------- Nhap hang loat (lo)
class SyncThread:
    """Chay thang target khi .start() — de test khoi phai cho thread that."""

    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target

    def start(self):
        self._target()


@pytest.fixture
def nhap_dong_bo(monkeypatch):
    """Nhap hang loat chay dong bo va khong doc W/H bang tien trinh con."""
    monkeypatch.setattr(pipeline_mod.threading, "Thread", SyncThread)
    monkeypatch.setattr(main.pipeline, "probe_media", lambda *a, **k: {})


def make_files(tmp_path, *names):
    out = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"0" * 64)
        out.append(main.ImportBatchItem(path=str(path)))
    return out


def test_nhap_hang_loat_yeu_cau_it_nhat_mot_file(lib):
    with pytest.raises(HTTPException) as e:
        main.import_batch(main.ImportBatchSchema(items=[main.ImportBatchItem(path="  ")]))
    assert e.value.status_code == 400


def test_nhap_hang_loat_giu_dung_thu_tu_da_sap(lib, tmp_path, nhap_dong_bo):
    items = make_files(tmp_path, "tap10.mp4", "tap2.mp4", "tap1.mp4")
    res = main.import_batch(main.ImportBatchSchema(items=items, batch_name="Phim Test"))

    assert res["count"] == 3 and res["batch_id"].startswith("lo_phim_test_")
    # Thu tu trong lo phai la thu tu NGUOI DUNG gui len, khong phai sap theo ten.
    titles = [e["title"] for e in lib.list_batch(res["batch_id"])]
    assert titles == ["tap10", "tap2", "tap1"]


def test_nhap_hang_loat_mot_file_hong_khong_giet_ca_lo(lib, tmp_path, nhap_dong_bo):
    items = make_files(tmp_path, "tap1.mp4")
    items.append(main.ImportBatchItem(path=str(tmp_path / "khong_co.mp4")))
    items += make_files(tmp_path, "tap3.mp4")

    res = main.import_batch(main.ImportBatchSchema(items=items))

    assert [e["title"] for e in lib.list_batch(res["batch_id"])] == ["tap1", "tap3"]


def test_nhap_them_vao_lo_co_san_thi_xep_theo_so_thu_tu_gui_kem(lib, tmp_path, nhap_dong_bo):
    first = main.import_batch(main.ImportBatchSchema(items=make_files(tmp_path, "b.mp4")))
    them = make_files(tmp_path, "a.mp4")
    them[0].index = 0.5   # chen len TRUOC file da nhap o luot dau

    main.import_batch(main.ImportBatchSchema(items=them, batch_id=first["batch_id"]))

    assert [e["title"] for e in lib.list_batch(first["batch_id"])] == ["a", "b"]


def test_dung_tac_vu_chay_bang_thread_thi_dat_co(lib):
    # Nut Dung truoc day khong co tac dung voi task thread (nhap/ghep).
    import queue as _queue
    assert main.process_mgr.register_manual_task("import", _queue.Queue())
    assert main.stop_task("import")["status"] == "success"
    assert main.process_mgr.was_user_stopped("import")
    main.process_mgr.finish_manual("import", 1)


def test_thong_ke_kem_tac_vu_dang_chay(lib, entry):
    stats = main.get_stats()
    assert stats["videos"] == 1
    assert stats["running_tasks"] == []
