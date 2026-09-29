"""GĐ 3 — chạy video CỦA DỰ ÁN: sub từng video → ghép đúng thứ tự → đánh dấu đã ghép.

Trước đây lựa chọn ở thư viện dự án chỉ mở khoá nút "Tinh chỉnh"; sang tab Dịch
thì báo "Chưa chọn video nào" vì tab đó đọc lựa chọn của thư viện CŨ
(storage/videos, theo entry_id) — video trong thư mục dự án không có entry_id.

Không spawn tiến trình thật: StubPM ghi lại lệnh, test tự gọi `on_completed`
để giả một video chạy xong.
"""
import os
import queue
import time

import pytest
from fastapi import HTTPException

import orchestrator.main as main
import orchestrator.pipeline as pipeline_mod
from orchestrator import project
from orchestrator.pipeline import VideoPipeline
from orchestrator.process_manager import ProcessManager
from orchestrator.storage import VideoLibrary


class StubPM:
    """ProcessManager giả: đếm số lần đóng SSE, ghi lại tiến trình được khởi động."""

    def __init__(self):
        self.lines, self.finished, self.started = [], [], []
        self.stopped = False

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
        return True

    def log(self):
        return "\n".join(self.lines)


def _tao_du_an(folder, ten_files=("tap 1.mp4", "tap 2.mp4", "tap 10.mp4"), ten="Phim ABC"):
    os.makedirs(folder, exist_ok=True)
    for ten_file in ten_files:
        with open(os.path.join(folder, ten_file), "wb") as fh:
            fh.write(b"0" * 64)
    project.init(folder, ten, True)
    return [v["file"] for v in project.danh_sach_video(folder)]


class Harness:
    def __init__(self, tmp_path, monkeypatch):
        self.folder = str(tmp_path / "du_an")
        self.files = _tao_du_an(self.folder)   # 001_tap_1, 002_tap_2, 003_tap_10
        self.pm = StubPM()
        self.pipe = VideoPipeline(VideoLibrary(str(tmp_path / "storage")), self.pm)
        self.merges = []

        monkeypatch.setattr(pipeline_mod, "load_global_config", lambda: {})
        # Lệnh giả mang theo đường dẫn video để test đọc được thứ tự chạy.
        monkeypatch.setattr(self.pipe, "build_translate_cmd",
                            lambda job, args, cfg: ["adapter", job["video_path"]])
        monkeypatch.setattr("orchestrator.video_merger.probe_sizes",
                            lambda files: [(1280, 720)] * len(files))

        def fake_merge(task_key, files, out, sizes=None, normalize="auto",
                       prev_code=0, on_success=None):
            self.merges.append({"files": files, "out": out, "sizes": sizes,
                                "normalize": normalize})
            # Giống _merge_in_thread thật: ghép OK → on_success → đóng SSE một lần.
            if on_success:
                on_success()
            self.pm.finish_manual(task_key, prev_code)

        monkeypatch.setattr(self.pipe, "_merge_in_thread", fake_merge)

    def chay(self, files, merge=True, args=None, ten_ghep=""):
        opts = {"enabled": True, "output_name": ten_ghep, "prefer": "output",
                "normalize": True} if merge else None
        return self.pipe.start_translate_project("translate", self.folder, list(files),
                                                 args or {}, opts)

    def video_dang_chay(self, i):
        return os.path.basename(self.pm.started[i]["cmd"][1])

    def xong(self, i, code=0, xuat_ban_sub=True):
        """Giả video thứ i chạy xong; mặc định adapter có xuất bản đã sub."""
        if code == 0 and xuat_ban_sub:
            ten = self.video_dang_chay(i)
            stem = os.path.splitext(ten)[0]
            out = os.path.join(self.folder, project.OUT_DIR,
                               f"{stem}_autosub_20260924_10000{i}.mp4")
            with open(out, "wb") as fh:
                fh.write(b"1" * 32)
        self.pm.started[i]["on_completed"](code)


@pytest.fixture
def h(tmp_path, monkeypatch):
    return Harness(tmp_path, monkeypatch)


# ------------------------------------------------------------------ Thứ tự chạy
def test_chay_dung_thu_tu_nguoi_dung_sap_khong_phai_thu_tu_danh_so(h):
    assert h.chay([h.files[2], h.files[0]]) is True
    assert h.video_dang_chay(0) == h.files[2]
    h.xong(0)
    assert h.video_dang_chay(1) == h.files[0]


def test_dau_ra_nam_ngay_trong_du_an(h):
    job = VideoPipeline.make_project_job(h.folder, h.files[0])
    assert job["video_path"] == os.path.join(os.path.abspath(h.folder), h.files[0])
    assert job["output_dir"] == os.path.join(os.path.abspath(h.folder), "da_sub")
    assert job["srt_dir"] == os.path.join(os.path.abspath(h.folder), "phu_de")


# ------------------------------------------------------------- Bản đã sub
def test_ban_da_sub_duoc_doi_ve_ten_co_dinh(h):
    h.chay([h.files[0]], merge=False)
    h.xong(0)
    da_sub = os.path.join(h.folder, "da_sub")
    assert os.listdir(da_sub) == ["001_tap_1.mp4"]


def test_ban_cu_tu_luot_truoc_khong_bi_nhan_nham_la_ban_moi(h):
    da_sub = os.path.join(h.folder, "da_sub")
    cu = os.path.join(da_sub, "001_tap_1_autosub_20200101_000000.mp4")
    with open(cu, "wb") as fh:
        fh.write(b"cu")
    mot_tieng_truoc = time.time() - 3600
    os.utime(cu, (mot_tieng_truoc, mot_tieng_truoc))

    h.chay([h.files[0]], merge=False)
    h.xong(0, xuat_ban_sub=False)   # lượt này adapter không xuất video (vd chỉ .srt)

    assert os.path.exists(cu), "bản cũ phải giữ nguyên tên"
    assert not os.path.exists(os.path.join(da_sub, "001_tap_1.mp4"))


# ------------------------------------------------------------------ Ghép
def test_ghep_dung_thu_tu_roi_danh_dau_da_ghep(h):
    h.chay([h.files[1], h.files[0]], ten_ghep="Tong hop tap 1-2")
    h.xong(0)
    h.xong(1)

    assert len(h.merges) == 1
    ghep = h.merges[0]
    assert [os.path.basename(f) for f in ghep["files"]] == [h.files[1], h.files[0]]
    assert all(os.sep + "da_sub" + os.sep in f for f in ghep["files"]), "phải ghép bản đã sub"
    assert ghep["out"] == os.path.join(os.path.abspath(h.folder), "ban_ghep", "tong_hop_tap_1_2.mp4")
    assert ghep["sizes"] == [(1280, 720), (1280, 720)], "phải đo kích thước thật để chuẩn hoá"

    con_lai = [v["file"] for v in project.danh_sach_video(h.folder)]
    assert con_lai == [h.files[2]], "video đã ghép phải biến khỏi danh sách"
    lich_su = project.doc(h.folder)["merges"]
    assert lich_su[0]["videos"] == [h.files[1], h.files[0]], "lịch sử giữ đúng thứ tự ghép"
    assert h.pm.finished == [0], "SSE đóng đúng MỘT lần"


def test_co_video_loi_thi_khong_ghep_va_khong_giau_video_loi(h):
    h.chay([h.files[0], h.files[1]])
    h.xong(0)
    h.xong(1, code=1)

    assert h.merges == []
    assert len(project.danh_sach_video(h.folder)) == 3, "không đánh dấu gì cả"
    assert "BỎ QUA bước ghép" in h.pm.log()
    assert h.pm.finished == [1]


def test_khong_bat_ghep_thi_chi_dong_sse(h):
    h.chay([h.files[0], h.files[1]], merge=False)
    h.xong(0)
    h.xong(1)
    assert h.merges == []
    assert h.pm.finished == [0]


def test_mot_video_thi_khong_ghep(h):
    h.chay([h.files[0]])
    h.xong(0)
    assert h.merges == []
    assert "ít nhất 2 video" in h.pm.log()
    assert h.pm.finished == [0]


def test_nguoi_dung_bam_dung_thi_khong_ghep(h):
    h.chay([h.files[0], h.files[1]])
    h.pm.stopped = True
    h.xong(0)
    assert h.merges == []
    assert h.pm.finished == [1]


def test_che_do_chi_xuat_srt_thi_khong_ghep(h):
    h.chay([h.files[0], h.files[1]], args={"translate_only": True})
    h.xong(0, xuat_ban_sub=False)
    h.xong(1, xuat_ban_sub=False)
    assert h.merges == []
    assert "chỉ xuất .srt" in h.pm.log()
    assert h.pm.finished == [0]


def test_thieu_ban_da_sub_thi_ghep_ban_goc_cua_video_do(h):
    h.chay([h.files[0], h.files[1]])
    h.xong(0)
    h.xong(1, xuat_ban_sub=False)
    files = h.merges[0]["files"]
    assert files[0].endswith(os.path.join("da_sub", h.files[0]))
    assert files[1] == os.path.join(os.path.abspath(h.folder), h.files[1])


# ------------------------------------------------ Nhả task khi hỏng từ đầu
def test_thieu_api_key_thi_nha_task_khong_ket_trang_thai_dang_chay(tmp_path, monkeypatch):
    """Trước đây ValueError (thiếu key) bay ra sau khi đã đăng ký task → task kẹt
    "đang chạy" mãi, mọi lần bấm dịch sau đều bị từ chối."""
    folder = str(tmp_path / "du_an")
    files = _tao_du_an(folder)
    pm = ProcessManager()
    pipe = VideoPipeline(VideoLibrary(str(tmp_path / "storage")), pm)
    monkeypatch.setattr(pipeline_mod, "load_global_config", lambda: {})

    def thieu_key(job, args, cfg):
        raise ValueError("Chưa cấu hình API key")

    monkeypatch.setattr(pipe, "build_translate_cmd", thieu_key)

    with pytest.raises(ValueError):
        pipe.start_translate_project("translate", folder, files[:1], {}, None)
    assert not pm.is_running("translate")

    # Đường dịch thư viện cũ dùng chung cơ chế — cũng không được kẹt.
    job = VideoPipeline.make_project_job(folder, files[0])
    with pytest.raises(ValueError):
        pipe.start_translate("translate", [job], {})
    assert not pm.is_running("translate")


# ------------------------------------------------------------ project.py thuần
def test_file_de_ghep_uu_tien_ban_da_sub_va_bao_file_thieu(tmp_path):
    folder = str(tmp_path / "du_an")
    files = _tao_du_an(folder)
    with open(project.duong_dan_da_sub(folder, files[1]), "wb") as fh:
        fh.write(b"1")
    os.remove(os.path.join(folder, files[2]))

    ghep, thieu = project.file_de_ghep(folder, files)
    assert [g["file"] for g in ghep] == files[:2]
    assert ghep[0]["path"] == os.path.join(os.path.abspath(folder), files[0])
    assert ghep[1]["path"] == project.duong_dan_da_sub(folder, files[1])
    assert thieu == [files[2]]

    ghep_goc, _ = project.file_de_ghep(folder, files[:2], prefer="source")
    assert ghep_goc[1]["path"] == os.path.join(os.path.abspath(folder), files[1])


def test_ban_ghep_moi_khong_bao_gio_de_ban_cu(tmp_path):
    folder = str(tmp_path / "du_an")
    _tao_du_an(folder, ten="Phim ABC")
    dau = project.duong_dan_ban_ghep(folder)
    assert os.path.basename(dau) == "phim_abc.mp4", "để trống tên thì lấy tên dự án"
    open(dau, "wb").close()
    assert os.path.basename(project.duong_dan_ban_ghep(folder)) == "phim_abc_2.mp4"


def test_ban_ghep_du_an_khong_ten_ra_tong_hop(tmp_path):
    folder = str(tmp_path / "du_an")
    _tao_du_an(folder, ten="")
    data = project.doc(folder)
    data["name"] = ""
    project.ghi(folder, data)
    assert os.path.basename(project.duong_dan_ban_ghep(folder)) == "tong_hop.mp4"


# ------------------------------------------------------------------ Endpoint
@pytest.fixture
def api(tmp_path, monkeypatch):
    folder = str(tmp_path / "du_an")
    files = _tao_du_an(folder)
    calls = []
    monkeypatch.setattr(main.pipeline, "start_translate_project",
                        lambda *a, **k: calls.append(a) or True)
    monkeypatch.setattr(main.process_mgr, "is_running", lambda key: False)
    return folder, files, calls


def _goi(folder, files, **kw):
    return main.project_translate(main.ProjectTranslateSchema(folder=folder, files=files, **kw))










