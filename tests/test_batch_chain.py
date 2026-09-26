"""Chuoi tai/nhap -> dich -> ghep chay duoi MOT task_key.

Diem de vo nhat: SSE chi duoc dong (finish_manual) dung MOT lan o cuoi chuoi.
Dong som la nguoi dung mat sach log cua khuc sau ma tuong app treo.
"""
import os

import pytest

from orchestrator.pipeline import VideoPipeline
from orchestrator.storage import VideoLibrary


class StubPM:
    """ProcessManager gia: dem so lan dong SSE va ghi lai tien trinh duoc khoi dong."""

    def __init__(self):
        self.lines, self.finished, self.started = [], [], []
        self.stopped = False
        self.can_start = True

    def emit(self, task_key, line):
        self.lines.append(line)

    def finish_manual(self, task_key, code):
        self.finished.append(code)

    def was_user_stopped(self, task_key):
        return self.stopped

    def register_manual_task(self, task_key, log_queue):
        return True

    def start_process(self, **kwargs):
        self.started.append(kwargs)
        return self.can_start

    def log(self):
        return "\n".join(self.lines)


class Harness:
    def __init__(self, tmp_path, monkeypatch):
        self.library = VideoLibrary(str(tmp_path / "storage"))
        self.pm = StubPM()
        self.pipe = VideoPipeline(self.library, self.pm)
        self.merges = []

        def fake_merge(task_key, files, out, sizes=None, normalize="auto", prev_code=0):
            self.merges.append({"files": files, "out": out, "sizes": sizes,
                                "normalize": normalize, "prev_code": prev_code})

        monkeypatch.setattr(self.pipe, "_merge_in_thread", fake_merge)

    def add(self, entry_id, index, batch_id="lo_1", output=False, size=(1920, 1080)):
        entry_dir = self.library.entry_dir(entry_id)
        os.makedirs(entry_dir, exist_ok=True)
        goc = os.path.join(entry_dir, "goc.mp4")
        with open(goc, "wb") as fh:
            fh.write(b"0" * 16)
        if output:
            os.makedirs(self.library.output_dir(entry_id), exist_ok=True)
            with open(os.path.join(self.library.output_dir(entry_id), "ban_dich.mp4"), "wb") as fh:
                fh.write(b"0" * 16)
        self.library.write_entry(entry_id, {
            "entry_id": entry_id, "title": entry_id, "file": goc,
            "created_at": f"2026-01-01T00:00:{index:02d}",
            "batch_id": batch_id, "batch_index": index,
            "width": size[0], "height": size[1],
        })
        return entry_id


@pytest.fixture
def h(tmp_path, monkeypatch):
    return Harness(tmp_path, monkeypatch)


# --------------------------------------------------------------- Dong lenh
def test_lenh_tai_gui_kem_ma_lo_va_so_thu_tu_cho_tung_link(h):
    cmd = h.pipe.build_download_cmd(
        ["https://a/1", "https://a/2"],
        {"batch_id": "lo_x", "batch_index": [3, 7]}, {})

    assert cmd.count("--url") == cmd.count("--batch-index") == 2
    assert cmd[cmd.index("--batch-id") + 1] == "lo_x"
    # Phai di theo cap dung thu tu, khong duoc don het --url roi moi den so.
    assert cmd[cmd.index("--url") + 2:cmd.index("--url") + 4] == ["--batch-index", "3.0"]


def test_khong_co_lo_thi_khong_gui_ma_lo(h):
    cmd = h.pipe.build_download_cmd(["https://a/1"], {}, {})
    assert "--batch-id" not in cmd
    assert cmd[cmd.index("--batch-index") + 1] == "1.0"   # van danh so theo vi tri


# ------------------------------------------------------------------ Chuoi
def test_khong_dich_khong_ghep_thi_dong_sse_dung_mot_lan(h):
    h.pipe.chain_after_entries("download", [], 0, None, None, "lo_1")
    assert h.pm.finished == [0]
    assert h.merges == []


def test_tai_xong_ghep_luon_thi_chua_dong_sse_vao_luc_do(h):
    h.add("v1", 1)
    h.add("v2", 2)
    h.pipe.chain_after_entries("download", [], 0, None, {"enabled": True}, "lo_1")

    # Khuc ghep tu dong SSE khi xong -> o day khong duoc dong.
    assert h.pm.finished == []
    assert [os.path.basename(os.path.dirname(f)) for f in h.merges[0]["files"]] == ["v1", "v2"]


def test_nguoi_dung_bam_dung_thi_khong_ghep_nua(h):
    h.add("v1", 1)
    h.add("v2", 2)
    h.pm.stopped = True
    h.pipe.chain_after_entries("download", [], 1, None, {"enabled": True}, "lo_1")

    assert h.merges == []
    assert h.pm.finished == [1]


def test_lo_it_hon_hai_video_thi_dong_sse_chu_khong_treo(h):
    h.add("v1", 1)
    h.pipe.chain_after_entries("download", [], 0, None, {"enabled": True}, "lo_1")

    assert h.merges == []
    assert h.pm.finished == [0]
    assert "Không đủ video" in h.pm.log()


def test_dich_truoc_roi_moi_ghep(h):
    entry = h.library.read_entry(h.add("v1", 1))
    h.pipe.chain_after_entries("download", [entry], 0, {"target_lang": "Vietnamese"},
                               {"enabled": True}, "lo_1")

    assert len(h.pm.started) == 1          # da khoi dong tien trinh dich
    assert h.pm.finished == []             # va chua dong SSE
    assert h.merges == []                  # ghep chi chay sau khi dich xong


def test_dich_khong_khoi_dong_duoc_thi_van_dong_sse(h):
    entry = h.library.read_entry(h.add("v1", 1))
    h.pm.can_start = False
    h.pipe.chain_after_entries("download", [entry], 0, {"target_lang": "Vietnamese"}, None, "lo_1")

    assert h.pm.finished == [1]


# ------------------------------------------------------------ Chon file ghep
def test_uu_tien_ban_da_gan_phu_de(h):
    h.add("v1", 1, output=True)
    h.add("v2", 2)

    h.pipe.start_merge_batch("download", "lo_1", {"enabled": True})

    files = h.merges[0]["files"]
    assert os.path.basename(files[0]) == "ban_dich.mp4"   # co ban dich thi dung ban dich
    assert os.path.basename(files[1]) == "goc.mp4"        # khong co thi dung ban goc


def test_chon_ban_goc_khi_duoc_yeu_cau(h):
    h.add("v1", 1, output=True)
    h.add("v2", 2, output=True)

    h.pipe.start_merge_batch("download", "lo_1", {"enabled": True, "prefer": "source"})

    assert all(os.path.basename(f) == "goc.mp4" for f in h.merges[0]["files"])


def test_ghep_theo_so_thu_tu_chu_khong_theo_thu_tu_them_vao(h):
    h.add("sau", 9)
    h.add("truoc", 2)

    h.pipe.start_merge_batch("download", "lo_1", {"enabled": True})

    assert [os.path.basename(os.path.dirname(f)) for f in h.merges[0]["files"]] == ["truoc", "sau"]


def test_gui_kem_kich_thuoc_va_co_chuan_hoa(h):
    h.add("v1", 1, size=(1080, 1920))
    h.add("v2", 2, size=(1920, 1080))

    h.pipe.start_merge_batch("download", "lo_1", {"enabled": True, "normalize": False}, prev_code=1)

    assert h.merges[0]["sizes"] == [(1080, 1920), (1920, 1080)]
    assert h.merges[0]["normalize"] == "never"
    # Khuc truoc co video loi thi ca luot van phai tinh la loi.
    assert h.merges[0]["prev_code"] == 1


def test_bo_qua_video_mat_file_nhung_van_ghep_phan_con_lai(h):
    h.add("v1", 1)
    h.add("v2", 2)
    h.add("v3", 3)
    os.remove(h.library.read_entry("v2")["file"])

    h.pipe.start_merge_batch("download", "lo_1", {"enabled": True})

    assert len(h.merges[0]["files"]) == 2
    assert "BỎ QUA" in h.pm.log()


def test_thieu_api_key_luc_chuyen_sang_dich_van_dong_sse(h, monkeypatch):
    """Tai xong -> dich luon, nhung engine thieu key: build_translate_cmd nem
    ValueError ngay trong callback cua khuc tai. Truoc day exception bay ra,
    khong ai goi finish_manual -> giao dien treo 'dang chay' mai."""
    import orchestrator.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "load_global_config", lambda: {})

    def thieu_key(job, args, cfg):
        raise ValueError("thieu API key")

    monkeypatch.setattr(h.pipe, "build_translate_cmd", thieu_key)
    entry = h.library.read_entry(h.add("v1", 1))

    h.pipe.chain_after_entries("download", [entry], 0, {"llm_engine": "gemini"}, None, "lo_1")

    assert h.pm.finished == [1]
    assert "thieu API key" in h.pm.log()
