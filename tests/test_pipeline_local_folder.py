"""Nguon "Thu muc cuc bo": truyen nguoi dung tu tai ve co ten tep tuy y,
phai duoc chuan hoa khi chep vao raw/ — neu khong buoc TTS/ghep video se bo qua.
"""
import time

from orchestrator.pipeline import NovelPipeline
from tests.test_pipeline_llm import StubProcess


class _TmpStorage:
    def __init__(self, root):
        self.root = root
        self.meta = {"story_slug": "test-story", "status": "READY"}

    def read_story_meta(self, _name):
        return dict(self.meta)

    def get_story_dir(self, _name):
        return str(self.root)

    def write_story_meta(self, _name, meta):
        self.meta = dict(meta)


def _wait(proc, task_key, timeout=5.0):
    deadline = time.time() + timeout
    while proc.completed_exit_codes.get(task_key) is None and time.time() < deadline:
        time.sleep(0.02)
    return proc.completed_exit_codes.get(task_key)


def _chuan_bi(tmp_path, names):
    src = tmp_path / "tai_ve"
    src.mkdir()
    for i, n in enumerate(names, 1):
        (src / n).write_text(f"# Tieu de {i}\n\nNoi dung chuong", encoding="utf-8")
    return src


def test_chep_va_doi_ten_khi_khong_dich(tmp_path, monkeypatch):
    """Noi dung da la tieng Viet (bo qua dich) -> gan luon nhan [VI] cho TTS."""
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    src = _chuan_bi(tmp_path, ["Chuong 1.txt", "Chuong 2.txt", "chuong_0003.md"])
    story = tmp_path / "story"
    proc = StubProcess()
    p = NovelPipeline(_TmpStorage(story), proc)

    assert p.start_step_1_crawl_translate(
        "Test",
        {"source": "local", "local_folder": str(src)},
        {"auto_translate": False},
    ) is True
    assert _wait(proc, "test-story_step1") == 0

    # Ten tep khong co tieu de -> lay tu dong dau noi dung; .txt doi thanh .md
    ten = sorted(f.name for f in (story / "raw").iterdir())
    assert ten == [
        "Chương 0001 - [VI] Tieu de 1.md",
        "Chương 0002 - [VI] Tieu de 2.md",
        "Chương 0003 - [VI] Tieu de 3.md",
    ]
    # Thu muc nguon cua nguoi dung khong bi dong vao
    assert len(list(src.iterdir())) == 3


def test_chua_dich_thi_chua_gan_nhan_vi(tmp_path, monkeypatch):
    """Con phai dich -> de ten khong nhan [VI], buoc dich se tu gan."""
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    src = _chuan_bi(tmp_path, ["第1章 伦敦孤儿.md", "第2章 奖学金.md"])
    story = tmp_path / "story"
    proc = StubProcess()
    p = NovelPipeline(_TmpStorage(story), proc)

    p.start_step_1_crawl_translate(
        "Test",
        {"source": "local", "local_folder": str(src)},
        {"auto_translate": True},
    )
    # auto_translate=True -> sau khi chep se chay lenh dich
    deadline = time.time() + 5.0
    while proc.captured_cmd is None and time.time() < deadline:
        time.sleep(0.02)

    ten = sorted(f.name for f in (story / "raw").iterdir())
    assert ten == ["Chương 0001 - 伦敦孤儿.md", "Chương 0002 - 奖学金.md"]
    assert all("[VI]" not in n for n in ten)
    assert "translate" in proc.captured_cmd


def test_thu_muc_khong_ton_tai_thi_bao_loi(tmp_path, monkeypatch):
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    proc = StubProcess()
    p = NovelPipeline(_TmpStorage(tmp_path / "story"), proc)
    p.start_step_1_crawl_translate(
        "Test", {"source": "local", "local_folder": str(tmp_path / "khong-co")}, {})
    assert _wait(proc, "test-story_step1") == 1


def _log(proc, task_key="test-story_step1"):
    q = proc.log_queues[task_key]
    out = []
    while not q.empty():
        item = q.get_nowait()
        if item:
            out.append(item)
    return "".join(out)


def test_ten_tep_da_dung_chuan_van_nap_duoc(tmp_path, monkeypatch):
    """Truyen tai ve san co ten dung quy tac tung bi bao "khong tim thay file"."""
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    src = _chuan_bi(tmp_path, [
        "Chương 0001 - [VI] Mo dau.md", "Chương 0002 - [VI] Tiep theo.md"])
    story = tmp_path / "story"
    proc = StubProcess()
    p = NovelPipeline(_TmpStorage(story), proc)

    p.start_step_1_crawl_translate(
        "Test", {"source": "local", "local_folder": str(src)},
        {"auto_translate": False})
    assert _wait(proc, "test-story_step1") == 0
    assert sorted(f.name for f in (story / "raw").iterdir()) == [
        "Chương 0001 - [VI] Mo dau.md", "Chương 0002 - [VI] Tiep theo.md"]


def test_nap_lai_thu_muc_da_nap_thi_khong_bao_loi(tmp_path, monkeypatch):
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    src = _chuan_bi(tmp_path, ["Chuong 1.txt", "Chuong 2.txt"])
    story = tmp_path / "story"
    args = ({"source": "local", "local_folder": str(src)}, {"auto_translate": False})

    proc = StubProcess()
    NovelPipeline(_TmpStorage(story), proc).start_step_1_crawl_translate("Test", *args)
    assert _wait(proc, "test-story_step1") == 0

    proc2 = StubProcess()
    NovelPipeline(_TmpStorage(story), proc2).start_step_1_crawl_translate("Test", *args)
    assert _wait(proc2, "test-story_step1") == 0
    assert "đã có sẵn 2 chương" in _log(proc2)


def test_chuong_nam_trong_thu_muc_con_thi_chi_duong(tmp_path, monkeypatch):
    """Tro nham vao thu muc cha la loi hay gap — phai noi ro thay vi bao chung."""
    import orchestrator.config as config_mod
    monkeypatch.setattr(config_mod, "load_global_config", lambda: {})

    cha = tmp_path / "tai_ve"
    (cha / "Truyen ABC").mkdir(parents=True)
    (cha / "Truyen ABC" / "chuong_0001.md").write_text("noi dung", encoding="utf-8")

    proc = StubProcess()
    p = NovelPipeline(_TmpStorage(tmp_path / "story"), proc)
    p.start_step_1_crawl_translate(
        "Test", {"source": "local", "local_folder": str(cha)}, {})
    assert _wait(proc, "test-story_step1") == 1

    log = _log(proc)
    assert "thư mục con" in log
    assert str(cha / "Truyen ABC") in log
