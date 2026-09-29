"""GĐ 4 — lô video đổ thẳng vào DỰ ÁN (file trên máy + link), và vá lô trộn.

Trước đây tạo dự án mới xong, thư viện bảo "Tải video về ở tab Lô Video" — nhưng
tab đó luôn tải vào thư viện chung, không bao giờ vào dự án: ngõ cụt.

Kèm vá lỗi lô TRỘN ở thư viện chung: lô có cả file trên máy lẫn link chạy thành
hai khúc, chỉ khúc cuối mang phần dịch, và khúc đó chỉ dịch video VỪA TẢI — file
nhập ở khúc trước không được dịch mà vẫn bị đem ghép.
"""
import os
import time

import pytest
from fastapi import HTTPException

import orchestrator.main as main
import orchestrator.pipeline as pipeline_mod
from orchestrator import project
from orchestrator.pipeline import VideoPipeline
from orchestrator.storage import VideoLibrary


class StubPM:
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


def _file(path, noi_dung=b"0" * 64):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(noi_dung)
    return path


def _du_an_rong(tmp_path, ten="Phim Moi"):
    return project.tao_moi(str(tmp_path), ten)["folder"]


class Harness:
    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.library = VideoLibrary(str(tmp_path / "storage"))
        self.pm = StubPM()
        self.pipe = VideoPipeline(self.library, self.pm)
        self.merges = []
        monkeypatch.setattr(pipeline_mod, "load_global_config", lambda: {})
        monkeypatch.setattr(self.pipe, "build_download_cmd", lambda urls, args, cfg: ["tai"])
        monkeypatch.setattr(self.pipe, "build_translate_cmd",
                            lambda job, args, cfg: ["adapter", job["video_path"]])
        monkeypatch.setattr("orchestrator.video_merger.probe_sizes",
                            lambda files: [(1280, 720)] * len(files))

        def fake_merge(task_key, files, out, sizes=None, normalize="auto",
                       prev_code=0, on_success=None):
            self.merges.append({"files": files, "out": out})
            if on_success:
                on_success()
            self.pm.finish_manual(task_key, prev_code)

        monkeypatch.setattr(self.pipe, "_merge_in_thread", fake_merge)

    def gia_tai_ve(self, entry_id, index, batch_id, title):
        """Giả adapter tải: ghi một mục vào thư viện như adapter thật vẫn làm."""
        goc = _file(os.path.join(self.library.entry_dir(entry_id), "video.mp4"))
        self.library.write_entry(entry_id, {
            "entry_id": entry_id, "title": title, "file": goc,
            "created_at": f"2026-01-01T00:00:{index:02d}",
            "batch_id": batch_id, "batch_index": index,
        })
        return entry_id

    def cho_xong(self, so_lan=1, timeout=5.0):
        """Đợi thread nền (khúc chép) đóng SSE."""
        han = time.time() + timeout
        while len(self.pm.finished) < so_lan and time.time() < han:
            time.sleep(0.02)


@pytest.fixture
def h(tmp_path, monkeypatch):
    return Harness(tmp_path, monkeypatch)


# ------------------------------------------------------------ project.them_video
def test_them_video_danh_so_noi_tiep_va_khong_dong_ban_goc(tmp_path):
    folder = str(tmp_path / "du_an")
    for ten in ("tap 1.mp4", "tap 2.mp4"):
        _file(os.path.join(folder, ten))
    project.init(folder, "Phim", True)
    ngoai = _file(str(tmp_path / "ngoai" / "Tập đặc biệt.mkv"))

    video = project.them_video(folder, ngoai, chep=True, batch_id="lo_1", batch_index=5)

    assert video["file"] == "003_tap_dac_biet.mkv", "số nối tiếp, giữ đuôi gốc"
    assert os.path.exists(ngoai), "chép thì bản gốc ngoài dự án phải còn nguyên"
    assert os.path.exists(os.path.join(folder, "003_tap_dac_biet.mkv"))
    assert video["batch_id"] == "lo_1" and video["batch_index"] == 5.0
    assert [v["file"] for v in project.danh_sach_video(folder)][-1] == "003_tap_dac_biet.mkv"


def test_them_video_chuyen_han_khi_la_ban_tai_tam(tmp_path):
    folder = _du_an_rong(tmp_path)
    tam = _file(str(tmp_path / "tam" / "video.mp4"))
    video = project.them_video(folder, tam, title="Chương 1: Mở đầu", chep=False)
    assert video["file"] == "001_chuong_1_mo_dau.mp4", "tên lấy theo tiêu đề, không theo file tạm"
    assert not os.path.exists(tam)


def test_them_video_khong_de_file_co_san(tmp_path):
    folder = _du_an_rong(tmp_path)
    _file(os.path.join(folder, "001_tap.mp4"), b"cua nguoi dung")
    video = project.them_video(folder, _file(str(tmp_path / "x" / "tap.mp4")), chep=True)
    assert video["file"] == "001_tap_2.mp4"
    with open(os.path.join(folder, "001_tap.mp4"), "rb") as fh:
        assert fh.read() == b"cua nguoi dung"


def test_them_video_vao_thu_muc_chua_phai_du_an_bi_tu_choi(tmp_path):
    with pytest.raises(ValueError):
        project.them_video(str(tmp_path), _file(str(tmp_path / "a.mp4")))


def test_hoan_tac_khong_doi_ten_video_them_sau(tmp_path):
    folder = _du_an_rong(tmp_path)
    video = project.them_video(folder, _file(str(tmp_path / "x" / "tap.mp4")), chep=True)
    project.hoan_tac(folder)
    assert os.path.exists(os.path.join(folder, video["file"]))


def test_video_theo_lo_dung_thu_tu_hang_doi(tmp_path):
    folder = _du_an_rong(tmp_path)
    b = project.them_video(folder, _file(str(tmp_path / "x" / "b.mp4")), batch_id="lo", batch_index=2)
    a = project.them_video(folder, _file(str(tmp_path / "x" / "a.mp4")), batch_id="lo", batch_index=1)
    project.them_video(folder, _file(str(tmp_path / "x" / "c.mp4")), batch_id="lo_khac")
    assert project.video_theo_lo(folder, "lo") == [a["file"], b["file"]]


# ------------------------------------------------------------ Tải link vào dự án
def test_tai_xong_thi_chuyen_vao_du_an_dung_thu_tu_va_xoa_muc_tam(h):
    folder = _du_an_rong(h.tmp)
    h.pipe.start_download("download", ["u1", "u2"],
                          {"project_folder": folder, "batch_id": "lo_x"})
    h.gia_tai_ve("e2", 2, "lo_x", "Tap hai")
    h.gia_tai_ve("e1", 1, "lo_x", "Tap mot")
    h.pm.started[0]["on_completed"](0)

    assert project.video_theo_lo(folder, "lo_x") == ["001_tap_mot.mp4", "002_tap_hai.mp4"]
    assert h.library.list_entries() == [], "mục tạm trong thư viện chung phải được dọn"
    assert h.pm.finished == [0]


def test_tai_vao_du_an_roi_sub_va_ghep_ca_lo(h):
    folder = _du_an_rong(h.tmp)
    h.pipe.start_download("download", ["u1", "u2"], {"project_folder": folder, "batch_id": "lo_x"},
                          then_translate={"source_lang": "English"},
                          then_merge={"enabled": True, "prefer": "output"})
    h.gia_tai_ve("e1", 1, "lo_x", "Tap mot")
    h.gia_tai_ve("e2", 2, "lo_x", "Tap hai")
    h.pm.started[0]["on_completed"](0)

    # Khúc sub chạy trên video ĐÃ nằm trong dự án, đúng thứ tự hàng đợi.
    assert os.path.basename(h.pm.started[1]["cmd"][1]) == "001_tap_mot.mp4"
    h.pm.started[1]["on_completed"](0)
    assert os.path.basename(h.pm.started[2]["cmd"][1]) == "002_tap_hai.mp4"
    h.pm.started[2]["on_completed"](0)

    assert len(h.merges) == 1
    assert [os.path.basename(f) for f in h.merges[0]["files"]] == ["001_tap_mot.mp4", "002_tap_hai.mp4"]
    assert project.danh_sach_video(folder) == [], "ghép xong thì đánh dấu, danh sách trống"
    assert h.pm.finished == [0], "SSE đóng đúng MỘT lần cho cả chuỗi"


def test_lo_tron_du_an_sub_ca_file_da_chep_o_khuc_truoc(h):
    """Lô trộn: khúc 1 chép file trên máy (không mang phần dịch), khúc 2 tải link
    mang phần dịch — khúc 2 phải sub CẢ video của khúc 1."""
    folder = _du_an_rong(h.tmp)
    tren_may = _file(str(h.tmp / "may" / "Tap Mot.mp4"))
    assert h.pipe.start_import_project("import", folder,
                                       [{"path": tren_may, "index": 1}], "lo_m")
    h.cho_xong()
    assert h.pm.finished == [0]
    assert os.path.exists(tren_may), "file trên máy chỉ được chép"

    h.pipe.start_download("download", ["u2"], {"project_folder": folder, "batch_id": "lo_m"},
                          then_translate={"source_lang": "English"})
    h.gia_tai_ve("e2", 2, "lo_m", "Tap hai")
    h.pm.started[0]["on_completed"](0)

    sub = [os.path.basename(s["cmd"][1]) for s in h.pm.started[1:]]
    assert sub == ["001_tap_mot.mp4"], "video khúc nhập được sub trước, đúng thứ tự"
    h.pm.started[1]["on_completed"](0)
    assert os.path.basename(h.pm.started[2]["cmd"][1]) == "002_tap_hai.mp4"


def test_nhap_file_vao_du_an_khong_mang_tail_thi_tu_dong_sse(h):
    folder = _du_an_rong(h.tmp)
    f = _file(str(h.tmp / "may" / "a.mp4"))
    h.pipe.start_import_project("import", folder, [{"path": f}], "lo_1")
    h.cho_xong()
    assert h.pm.finished == [0]
    assert project.video_theo_lo(folder, "lo_1") == ["001_a.mp4"]


def test_nhap_file_hong_mot_cai_van_nhap_cai_con_lai(h):
    folder = _du_an_rong(h.tmp)
    ok = _file(str(h.tmp / "may" / "a.mp4"))
    h.pipe.start_import_project("import", folder,
                                [{"path": "Z:/khong/co.mp4", "index": 1}, {"path": ok, "index": 2}],
                                "lo_1")
    h.cho_xong()
    assert h.pm.finished == [1]
    assert project.video_theo_lo(folder, "lo_1") == ["001_a.mp4"]


# ----------------------------------------------------- Vá lô trộn ở thư viện chung
def test_lo_tron_thu_vien_chung_dich_ca_file_nhap_o_khuc_truoc(h):
    nhap = h.gia_tai_ve("nhap", 1, "lo_t", "Nhap tu may")   # đã nằm sẵn từ khúc nhập
    h.pipe.start_download("download", ["u"], {"batch_id": "lo_t"},
                          then_translate={"source_lang": "English"})
    h.gia_tai_ve("tai", 2, "lo_t", "Tai ve")
    h.pm.started[0]["on_completed"](0)

    assert h.pm.started[1]["cmd"][1] == h.library.read_entry(nhap)["file"], \
        "file nhập ở khúc trước phải được dịch, và dịch trước"


def test_lo_tron_khong_dich_lai_muc_da_co_ban_dich(h):
    da_dich = h.gia_tai_ve("cu", 1, "lo_t", "Da dich")
    entry = h.library.read_entry(da_dich)
    _file(os.path.join(h.library.output_dir(da_dich), "ban_dich.mp4"))
    h.library.write_entry(da_dich, entry)

    moi = h.gia_tai_ve("moi", 2, "lo_t", "Moi")
    chon = h.pipe._them_muc_lo_chua_dich("lo_t", [h.library.read_entry(moi)])
    assert [e["entry_id"] for e in chon] == ["moi"]


# ------------------------------------------------------------------- Endpoint






# ----------------------------------------------------------- Đóng dự án


# ------------------------------------------------------- Mở thư mục dự án


