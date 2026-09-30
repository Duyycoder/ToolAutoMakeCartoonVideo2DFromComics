import pytest
import os
import queue
from orchestrator.pipeline import NovelPipeline
from orchestrator.process_manager import ProcessManager

class StubStorage:
    tasks_dir = "storage/tasks"

    def read_story_meta(self, name):
        return {"story_slug": "test-story", "status": "READY"}

    def get_story_dir(self, name):
        return "storage/truyen/test-story"

    def write_story_meta(self, name, meta):
        pass


@pytest.fixture(autouse=True)
def _khong_goi_ollama_va_ghep_that(monkeypatch):
    # Không hỏi Ollama thật; bước ghép video coi như thành công khi và chỉ khi
    # tiến trình thoát 0 (thư mục video giả không có gì để ghép).
    import orchestrator.llm as llm_mod
    monkeypatch.setattr(llm_mod, "danh_sach_model_ollama", lambda *a, **k: None)
    monkeypatch.setattr(NovelPipeline, "_finalize_video_task",
                        lambda self, story, out_dir, key, code: code == 0)


def test_finalize_that_bai_khong_bao_ma_0(monkeypatch):
    """Tiến trình thoát 0 nhưng ghép video thất bại → trạng thái KHÔNG được là 0."""
    monkeypatch.setattr(NovelPipeline, "_finalize_video_task",
                        lambda self, story, out_dir, key, code: False)
    monkeypatch.setattr("orchestrator.config.load_global_config", lambda: {})
    import sys, time
    proc = ProcessManager()
    pipeline = NovelPipeline(StubStorage(), proc)
    original = proc.start_process

    def fake(task_key, cmd, cwd, env_override=None, on_completed=None,
             close_queue_on_exit=True, reuse_queue=False):
        return original(task_key, [sys.executable, "-c", "pass"], cwd, env_override,
                        on_completed, close_queue_on_exit, reuse_queue)

    monkeypatch.setattr(proc, "start_process", fake)
    assert pipeline.start_step_3_video("Test", {"llm_engine": "ollama"}) is True
    key = "test-story_step3"
    t0 = time.time()
    while proc.is_running(key) and time.time() - t0 < 10:
        time.sleep(0.05)
    assert proc.get_task_status(key)["exit_code"] == 1

def test_step3_crash_retry(tmp_path, monkeypatch):
    proc = ProcessManager()
    pipeline = NovelPipeline(StubStorage(), proc)
    
    monkeypatch.setattr("orchestrator.config.load_global_config", lambda: {})

    # We monkeypatch start_process to capture cmd, but actually use ProcessManager THẬT
    # The requirement: "dùng ProcessManager THẬT với lệnh con THẬT là python giả, lần 1 thoát bằng ExitProcess(0xC0000005)"
    
    python_script = tmp_path / "fake_step3.py"
    flag_file = tmp_path / "run_count.txt"
    flag_file.write_text("0")

    code = """
import sys
import os
import ctypes

flag_file = r"{}"
with open(flag_file, "r") as f:
    count = int(f.read())
with open(flag_file, "w") as f:
    f.write(str(count + 1))

print(f"Run count: {{count+1}}", flush=True)

if count == 0:
    if os.name == 'nt':
        ctypes.windll.kernel32.ExitProcess(0xC0000005)
    else:
        sys.exit(3221225477 - 2**32) # simulate negative exit code if possible, or just skip if not win
else:
    print("Success!", flush=True)
    sys.exit(0)
""".format(str(flag_file).replace('\\', '\\\\'))
    python_script.write_text(code)

    import sys
    
    original_start_process = proc.start_process
    def mock_start_process(task_key, cmd, cwd, env_override=None, on_completed=None, close_queue_on_exit=True, reuse_queue=False):
        # replace the cmd with our fake python script
        fake_cmd = [sys.executable, str(python_script)]
        return original_start_process(task_key, fake_cmd, cwd, env_override, on_completed, close_queue_on_exit, reuse_queue)

    monkeypatch.setattr(proc, "start_process", mock_start_process)

    # run Step 3
    started = pipeline.start_step_3_video("Test", {"llm_engine": "ollama"})
    assert started is True

    # wait for completion
    task_key = "test-story_step3"
    
    import time
    timeout = 10
    start_t = time.time()
    while proc.is_running(task_key) and time.time() - start_t < timeout:
        time.sleep(0.1)

    assert not proc.is_running(task_key)
    status = proc.get_task_status(task_key)
    assert status["completed"] is True
    assert status["exit_code"] == 0 # because the 2nd run succeeds

    # check log queue for retry message
    q = proc.log_queues.get(task_key)
    logs = ""
    while not q.empty():
        item = q.get()
        if item is not None:
            logs += item
    
    assert "Tự chạy lại lần 1/1" in logs
    assert "Success!" in logs
    
    # check count
    assert flag_file.read_text() == "2"

def test_step3_crash_retry_fails_both(tmp_path, monkeypatch):
    proc = ProcessManager()
    pipeline = NovelPipeline(StubStorage(), proc)
    monkeypatch.setattr("orchestrator.config.load_global_config", lambda: {})

    python_script = tmp_path / "fake_step3.py"
    
    code = """
import os, sys, ctypes
if os.name == 'nt':
    ctypes.windll.kernel32.ExitProcess(0xC0000005)
else:
    sys.exit(-1073741819)
"""
    python_script.write_text(code)

    import sys
    original_start_process = proc.start_process
    def mock_start_process(task_key, cmd, cwd, env_override=None, on_completed=None, close_queue_on_exit=True, reuse_queue=False):
        fake_cmd = [sys.executable, str(python_script)]
        return original_start_process(task_key, fake_cmd, cwd, env_override, on_completed, close_queue_on_exit, reuse_queue)

    monkeypatch.setattr(proc, "start_process", mock_start_process)

    pipeline.start_step_3_video("Test", {"llm_engine": "ollama"})
    task_key = "test-story_step3"
    
    import time
    timeout = 10
    start_t = time.time()
    while proc.is_running(task_key) and time.time() - start_t < timeout:
        time.sleep(0.1)

    status = proc.get_task_status(task_key)
    assert status["completed"] is True
    
    # Python ctypes.windll.kernel32.ExitProcess gives exit code that might be read as unsigned or signed.
    # We check if it is non-zero
    assert status["exit_code"] != 0

def test_step3_crash_user_stopped(tmp_path, monkeypatch):
    proc = ProcessManager()
    pipeline = NovelPipeline(StubStorage(), proc)
    monkeypatch.setattr("orchestrator.config.load_global_config", lambda: {})

    python_script = tmp_path / "fake_step3.py"
    flag_file = tmp_path / "run_count.txt"
    flag_file.write_text("0")
    
    code = """
import os, sys, ctypes
flag_file = r"{}"
with open(flag_file, "r") as f:
    count = int(f.read())
with open(flag_file, "w") as f:
    f.write(str(count + 1))
if os.name == 'nt':
    ctypes.windll.kernel32.ExitProcess(0xC0000005)
else:
    sys.exit(-1073741819)
""".format(str(flag_file).replace('\\', '\\\\'))
    python_script.write_text(code)

    import sys
    original_start_process = proc.start_process
    def mock_start_process(task_key, cmd, cwd, env_override=None, on_completed=None, close_queue_on_exit=True, reuse_queue=False):
        fake_cmd = [sys.executable, str(python_script)]
        return original_start_process(task_key, fake_cmd, cwd, env_override, on_completed, close_queue_on_exit, reuse_queue)

    monkeypatch.setattr(proc, "start_process", mock_start_process)

    task_key = "test-story_step3"
    
    # Start and immediately stop
    pipeline.start_step_3_video("Test", {"llm_engine": "ollama"})
    proc.user_stopped_tasks.add(task_key)
    
    import time
    timeout = 10
    start_t = time.time()
    while proc.is_running(task_key) and time.time() - start_t < timeout:
        time.sleep(0.1)

    assert flag_file.read_text() == "1" # Should only run once
