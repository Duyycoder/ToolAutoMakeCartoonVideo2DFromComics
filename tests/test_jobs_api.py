"""Luồng ảnh -> 3D qua HTTP: upload -> SSE tiến độ -> tải GLB. Worker AI thay bằng worker giả."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import routes_jobs
from backend.job_runner import JobRunner
from backend.main import app

WRITE_HEADERS = {"X-Easy3D": "1"}
FAKE_WORKER = Path(__file__).parent / "fake_image_to_3d_worker.py"


@pytest.fixture
def client(tmp_path, monkeypatch):
    runner = JobRunner(python_exe=Path(sys.executable), worker_script=FAKE_WORKER, jobs_dir=tmp_path,
                       presets=routes_jobs._config["quality_presets"], env={"FAKE_MODE": "ok"})
    monkeypatch.setattr(routes_jobs, "runner", runner)
    ready = {"ready": True, "message": "Sẵn sàng."}
    monkeypatch.setattr(routes_jobs, "get_ai_status", lambda: {"models": {"triposr": ready, "hunyuan": ready}})
    return TestClient(app)


def test_upload_stream_and_download(client):
    r = client.post("/api/image-to-3d", params={"filename": "meo.png", "quality": "balanced"},
                    content=b"\x89PNG", headers=WRITE_HEADERS)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    assert events[-1]["type"] == "status" and events[-1]["status"] == "done"
    assert any(e.get("msg") == "Đang tách nền ảnh..." for e in events)

    glb = client.get(f"/api/jobs/{job_id}/result.glb")
    assert glb.status_code == 200 and glb.content == b"glTF-fake"


def test_ai_not_ready_returns_409(client, monkeypatch):
    not_ready = {"ready": False, "message": "Chưa cài"}
    monkeypatch.setattr(routes_jobs, "get_ai_status", lambda: {"models": {"triposr": not_ready, "hunyuan": not_ready}})
    r = client.post("/api/image-to-3d", params={"filename": "a.png"}, content=b"x", headers=WRITE_HEADERS)
    assert r.status_code == 409 and r.json()["detail"] == "Chưa cài"


def test_unknown_job_404(client):
    assert client.get("/api/jobs/khongco").status_code == 404
