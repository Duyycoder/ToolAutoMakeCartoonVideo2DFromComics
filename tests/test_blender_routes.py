"""API Blender: chỉ thao tác trong danh sách, tham số bị giới hạn, báo rõ khi chưa cài Blender; job lệnh chạy qua hàng đợi."""
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend import routes_blender
from backend.job_runner import JobRunner
from backend.main import app
from backend.routes_blender import clean_params

client = TestClient(app)
WRITE = {"X-Easy3D": "1"}
FAKE_WORKER = Path(__file__).parent / "fake_image_to_3d_worker.py"


def test_params_are_clamped_and_sanitized():
    p = clean_params("bevel", {"amount": 99, "segments": -5, "evil": "import os"})
    assert p == {"amount": 1.0, "segments": 1.0}
    r = clean_params("render", {"width": 99999, "samples": "x", "background": "red; rm -rf", "camera_position": [1, 2]})
    assert r["width"] == 4096 and r["samples"] == 96 and r["background"] == "#1c1e24"
    assert r["camera_position"] == [3.5, 2.6, 4.5]  # sai dạng -> mặc định
    assert isinstance(r["width"], int)


def test_unknown_op_404():
    assert client.post("/api/blender/python_exec", content=b"x", headers=WRITE).status_code == 404


def test_missing_blender_409(monkeypatch):
    monkeypatch.setattr(routes_blender, "find_blender", lambda: None)
    r = client.post("/api/blender/bevel", content=b"glTF", headers=WRITE)
    assert r.status_code == 409 and "setup-blender" in r.json()["detail"]


def test_bad_params_json_400(monkeypatch):
    monkeypatch.setattr(routes_blender, "find_blender", lambda: Path(sys.executable))
    r = client.post("/api/blender/bevel", params={"params": "{oops"}, content=b"glTF", headers=WRITE)
    assert r.status_code == 400


def test_command_job_runs_once_and_reports(tmp_path):
    runner = JobRunner(python_exe=Path(sys.executable), worker_script=FAKE_WORKER, jobs_dir=tmp_path, presets={},
                       env={"FAKE_MODE": "ok"})
    job = runner.submit_command(lambda wd, inp: [sys.executable, FAKE_WORKER, "--image", inp, "--out-dir", wd],
                                b"glTF", "input.glb")
    for _ in range(200):
        if job.finished:
            break
        time.sleep(0.05)
    assert job.status == "done" and job.model == "blender"
    assert (job.work_dir / "input.glb").read_bytes() == b"glTF" and (job.work_dir / "mesh.glb").exists()
