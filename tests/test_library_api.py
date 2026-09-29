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














def test_mo_thu_muc_du_lieu_chung(lib, monkeypatch):
    monkeypatch.setattr(main, "_reveal_in_file_manager", lambda _p: None)
    assert main.open_storage_folder(kind="merged")["path"] == lib.merged_dir
    assert main.open_storage_folder(kind="videos")["path"] == lib.videos_dir


























@pytest.fixture
def bat_ghep(monkeypatch):
    """Chan pipeline.start_merge lai de doc tham so gui xuong."""
    calls = {}

    def fake(task_key, files, name, sizes=None, normalize="auto"):
        calls.update(files=files, name=name, sizes=sizes, normalize=normalize)
        return True

    monkeypatch.setattr(main.pipeline, "start_merge", fake)
    return calls








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










def test_dung_tac_vu_chay_bang_thread_thi_dat_co(lib):
    # Nut Dung truoc day khong co tac dung voi task thread (nhap/ghep).
    import queue as _queue
    assert main.process_mgr.register_manual_task("import", _queue.Queue())
    assert main.stop_task("import")["status"] == "success"
    assert main.process_mgr.was_user_stopped("import")
    main.process_mgr.finish_manual("import", 1)


