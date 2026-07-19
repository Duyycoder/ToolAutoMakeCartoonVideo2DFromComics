import queue
import sys
import threading

from orchestrator.process_manager import ProcessManager


def test_callback_logs_arrive_before_terminal_event(tmp_path):
    manager = ProcessManager()
    key = "video-step3"

    def completed(exit_code):
        manager.log_queues[key].put(f"callback:{exit_code}\n")

    assert manager.start_process(
        key,
        [sys.executable, "-c", "print('child-log', flush=True)"],
        str(tmp_path),
        on_completed=completed,
    )

    events = list(manager.get_logs_generator(key))
    joined = "".join(events)

    assert joined.index("child-log") < joined.index("callback:0")
    assert joined.index("callback:0") < joined.index("Process completed")
    assert manager.get_task_status(key)["completed"] is True


def test_reconnect_after_terminal_does_not_ping_forever(tmp_path):
    manager = ProcessManager()
    key = "finished-task"
    assert manager.start_process(
        key, [sys.executable, "-c", "pass"], str(tmp_path))

    list(manager.get_logs_generator(key))  # consume sentinel lần đầu
    reconnect_events = list(manager.get_logs_generator(key))

    assert len(reconnect_events) == 1
    assert "Process completed" in reconnect_events[0]


def test_callback_false_overrides_zero_child_exit_code(tmp_path):
    manager = ProcessManager()
    key = "failed-postprocess"
    assert manager.start_process(
        key,
        [sys.executable, "-c", "pass"],
        str(tmp_path),
        on_completed=lambda _exit_code: False,
    )

    events = list(manager.get_logs_generator(key))

    assert "exit_code=1" in "".join(events)
    assert manager.get_task_status(key)["exit_code"] == 1


def test_task_stays_reserved_while_callback_is_finalizing(tmp_path):
    manager = ProcessManager()
    key = "slow-finalize"
    callback_started = threading.Event()
    allow_callback_to_finish = threading.Event()

    def completed(_exit_code):
        callback_started.set()
        assert allow_callback_to_finish.wait(timeout=5)
        return True

    assert manager.start_process(
        key, [sys.executable, "-c", "pass"], str(tmp_path),
        on_completed=completed)
    assert callback_started.wait(timeout=5)

    assert manager.get_task_status(key)["running"] is True
    assert manager.start_process(
        key, [sys.executable, "-c", "pass"], str(tmp_path)) is False

    allow_callback_to_finish.set()
    assert "exit_code=0" in "".join(manager.get_logs_generator(key))


def test_reuse_queue_can_chain_process_during_callback(tmp_path):
    manager = ProcessManager()
    key = "crawl-translate"

    def start_second(_exit_code):
        assert manager.start_process(
            key,
            [sys.executable, "-c", "print('second', flush=True)"],
            str(tmp_path),
            reuse_queue=True,
        )

    assert manager.start_process(
        key,
        [sys.executable, "-c", "print('first', flush=True)"],
        str(tmp_path),
        on_completed=start_second,
        close_queue_on_exit=False,
    )

    joined = "".join(manager.get_logs_generator(key))

    assert "first" in joined
    assert "second" in joined
    assert "Process completed" in joined


def test_manual_task_has_reconnectable_terminal_state():
    manager = ProcessManager()
    key = "thread-merge"
    logs = queue.Queue()

    assert manager.register_manual_task(key, logs)
    assert manager.is_running(key) is True
    manager.mark_completed(key, 0)
    logs.put(None)

    assert "Process completed" in "".join(manager.get_logs_generator(key))
    assert "Process completed" in "".join(manager.get_logs_generator(key))


def test_multiline_and_legacy_dict_logs_are_valid_sse():
    manager = ProcessManager()
    key = "legacy-log"
    manager.log_queues[key] = queue.Queue()
    manager.log_queues[key].put({"type": "stderr", "line": "first\nsecond\n"})
    manager.log_queues[key].put(None)
    manager.completed_exit_codes[key] = 1

    first = next(manager.get_logs_generator(key))

    assert first == "data: first\ndata: second\n\n"
