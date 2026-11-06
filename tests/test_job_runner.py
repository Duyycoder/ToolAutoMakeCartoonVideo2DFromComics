import sys
import time
from pathlib import Path

import pytest

from backend.job_runner import JobRunner

FAKE_WORKER = Path(__file__).parent / "fake_image_to_3d_worker.py"
PRESETS = {
    "fast": {"chunk_size": 4096, "mc_resolution": 128},
    "balanced": {"chunk_size": 4096, "mc_resolution": 192},
    "detailed": {"chunk_size": 2048, "mc_resolution": 256},
}


def make_runner(tmp_path, mode="ok", hook=None):
    return JobRunner(python_exe=Path(sys.executable), worker_script=FAKE_WORKER,
                     jobs_dir=tmp_path, presets=PRESETS, env={"FAKE_MODE": mode},
                     before_gpu_job=hook)


def wait_finished(job, timeout=20):
    deadline = time.time() + timeout
    while not job.finished and time.time() < deadline:
        time.sleep(0.05)
    assert job.finished, "job không kết thúc kịp"
    return job


def test_success_writes_result_and_calls_gpu_hook(tmp_path):
    calls = []
    runner = make_runner(tmp_path, hook=lambda: calls.append(1))
    job = wait_finished(runner.submit_image_to_3d(b"png", ".png", "balanced"))
    assert job.status == "done"
    assert job.result["tris"] == 123 and job.result["quality_used"] == "balanced"
    assert (job.work_dir / "mesh.glb").exists()
    assert calls == [1]
    assert any(e.get("msg") == "Đang tách nền ảnh..." for e in job.events)


def test_oom_retries_with_lighter_quality(tmp_path):
    job = wait_finished(make_runner(tmp_path).submit_image_to_3d(b"png", ".png", "detailed"))
    assert job.status == "done"
    assert job.result["quality_used"] == "balanced"
    assert any("thử lại" in e.get("msg", "") for e in job.events)


def test_crash_retries_then_fails_friendly(tmp_path):
    job = wait_finished(make_runner(tmp_path, mode="crash").submit_image_to_3d(b"png", ".png", "balanced"))
    assert job.status == "error"
    assert "dừng đột ngột" in job.error


def test_normal_error_does_not_retry(tmp_path):
    job = wait_finished(make_runner(tmp_path, mode="error").submit_image_to_3d(b"png", ".png", "balanced"))
    assert job.status == "error"
    assert "ảnh hỏng" in job.error
    assert not any("thử lại" in e.get("msg", "") for e in job.events)


def test_cancel_running_job(tmp_path):
    runner = make_runner(tmp_path, mode="slow")
    job = runner.submit_image_to_3d(b"png", ".png", "fast")
    deadline = time.time() + 10
    while job.proc is None and time.time() < deadline:
        time.sleep(0.05)
    assert runner.cancel(job.id)
    assert wait_finished(job).status == "cancelled"


def test_invalid_quality_rejected(tmp_path):
    with pytest.raises(ValueError):
        make_runner(tmp_path).submit_image_to_3d(b"png", ".png", "ultra")


def test_second_model_uses_own_worker_and_presets(tmp_path):
    hunyuan_presets = {"fast": {"steps": 20}, "balanced": {"steps": 30}, "detailed": {"steps": 50}}
    runner = JobRunner(python_exe=Path(sys.executable), worker_script=FAKE_WORKER, jobs_dir=tmp_path, presets=PRESETS,
                       env={"FAKE_MODE": "ok"},
                       extra_models={"hunyuan": {"python_exe": sys.executable, "worker_script": FAKE_WORKER,
                                                 "presets": hunyuan_presets}})
    job = wait_finished(runner.submit_image_to_3d(b"png", ".png", "balanced", model="hunyuan"))
    assert job.status == "done" and job.model == "hunyuan"
    assert job.result["steps"] == 30 and job.result["mc_resolution"] is None


def test_unknown_model_rejected(tmp_path):
    with pytest.raises(ValueError):
        make_runner(tmp_path).submit_image_to_3d(b"png", ".png", "fast", model="trellis")
