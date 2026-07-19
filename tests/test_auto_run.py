"""Unit tests cho chuỗi Chạy tự động Bước 1→4 (orchestrator/auto_run.py).

Không GPU, không tiến trình thật: pipeline + process_mgr là fake điều khiển được.
"""
import time

import pytest

from orchestrator.auto_run import AutoRunManager, CHAIN_STEPS
from tests.test_pipeline_llm import StubStorage

SLUG = "test-story"


class FakeProcess:
    def __init__(self):
        self.status = {}          # task_key -> {"running","completed","exit_code"}
        self.user_stopped = set()
        self.stopped_keys = []

    def is_running(self, key):
        return self.status.get(key, {}).get("running", False)

    def get_task_status(self, key):
        st = self.status.get(key, {})
        return {
            "task_key": key,
            "running": st.get("running", False),
            "completed": st.get("completed", False),
            "exit_code": st.get("exit_code"),
        }

    def stop_process(self, key):
        if not self.status.get(key, {}).get("running"):
            return False
        self.stopped_keys.append(key)
        self.user_stopped.add(key)
        self.status[key] = {"running": False, "completed": True, "exit_code": 1}
        return True

    def was_user_stopped(self, key):
        return key in self.user_stopped


class FakePipeline:
    """results: step_no -> exit_code; None = starter trả False; "hang" = chạy mãi."""

    def __init__(self, proc, results=None):
        self.proc = proc
        self.results = results or {}
        self.calls = []

    def _start(self, n):
        self.calls.append(n)
        res = self.results.get(n, 0)
        if res is None:
            return False
        key = f"{SLUG}_step{n}"
        if res == "hang":
            self.proc.status[key] = {"running": True, "completed": False, "exit_code": None}
        else:
            self.proc.status[key] = {"running": False, "completed": True, "exit_code": res}
        return True

    def start_step_1_crawl_translate(self, name, crawl_args, trans_args):
        return self._start(1)

    def start_step_2_tts(self, name, args):
        return self._start(2)

    def start_step_3_video(self, name, args):
        return self._start(3)

    def start_step_5_merge(self, name, files):
        return self._start(5)


def make_mgr(results=None):
    proc = FakeProcess()
    pipe = FakePipeline(proc, results)
    mgr = AutoRunManager(StubStorage(), proc, pipe)
    mgr.poll_interval = 0.01
    return mgr, pipe, proc


def wait_finished(mgr, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = mgr.status("Test")
        if st["finished"]:
            return st
        time.sleep(0.02)
    pytest.fail("chuỗi không kết thúc trong thời gian chờ")


STEP1_ARGS = {"crawl_args": {"source": "local"}, "trans_args": {}}


def test_chain_runs_all_steps_in_order():
    mgr, pipe, _ = make_mgr()
    ok, _msg = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    st = wait_finished(mgr)
    assert st["error"] is None
    assert pipe.calls == [n for n, _ in CHAIN_STEPS] == [1, 2, 3, 5]


def test_chain_aborts_when_step_fails():
    mgr, pipe, _ = make_mgr(results={2: 7})
    ok, _ = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    st = wait_finished(mgr)
    assert "Bước 2" in st["error"] and "7" in st["error"]
    assert pipe.calls == [1, 2]          # bước 3 và 5 không được chạy


def test_chain_aborts_when_starter_returns_false():
    mgr, pipe, _ = make_mgr(results={3: None})
    ok, _ = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    st = wait_finished(mgr)
    assert "Bước 3" in st["error"]
    assert pipe.calls == [1, 2, 3]


def test_stop_mid_chain_cancels_and_skips_rest():
    mgr, pipe, proc = make_mgr(results={2: "hang"})
    ok, _ = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    # chờ chuỗi vào bước 2 (đang treo)
    deadline = time.time() + 5
    while time.time() < deadline and 2 not in pipe.calls:
        time.sleep(0.02)
    assert 2 in pipe.calls
    assert mgr.is_chain_running(SLUG)

    assert mgr.stop("Test")
    st = wait_finished(mgr)
    assert "hủy" in st["error"].lower()
    assert f"{SLUG}_step2" in proc.stopped_keys
    assert pipe.calls == [1, 2]


def test_start_rejected_while_running():
    mgr, pipe, _ = make_mgr(results={1: "hang"})
    ok, _ = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    ok2, msg = mgr.start("Test", STEP1_ARGS, {}, {})
    assert not ok2 and "đang chạy" in msg
    mgr.stop("Test")
    wait_finished(mgr)


def test_start_rejected_when_manual_task_running():
    mgr, _, proc = make_mgr()
    proc.status[f"{SLUG}_step3"] = {"running": True, "completed": False, "exit_code": None}
    ok, msg = mgr.start("Test", STEP1_ARGS, {}, {})
    assert not ok and "Bước 3" in msg


def test_status_reports_display_numbering():
    mgr, _, _ = make_mgr(results={5: "hang"})
    ok, _ = mgr.start("Test", STEP1_ARGS, {}, {})
    assert ok
    deadline = time.time() + 5
    while time.time() < deadline:
        st = mgr.status("Test")
        if st["current_step"] == 4:      # step5 nội bộ hiển thị là Bước 4
            assert st["step_label"] == "Ghép Video"
            break
        time.sleep(0.02)
    else:
        pytest.fail("không thấy Bước 4 trong trạng thái")
    mgr.stop("Test")
    wait_finished(mgr)
