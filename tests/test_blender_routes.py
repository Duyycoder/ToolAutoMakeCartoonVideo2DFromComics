"""API Blender: chỉ thao tác trong danh sách, tham số bị giới hạn, báo rõ khi chưa cài Blender; job lệnh chạy qua hàng đợi."""
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import routes_blender, routes_jobs
from backend.job_runner import JobRunner
from backend.main import app
from backend.routes_blender import clean_params

client = TestClient(app)
WRITE = {"X-Easy3D": "1"}
FAKE_WORKER = Path(__file__).parent / "fake_image_to_3d_worker.py"


def make_glb(doc: dict) -> bytes:
    body = json.dumps(doc).encode()
    return b"glTF" + (2).to_bytes(4, "little") + (20 + len(body)).to_bytes(4, "little") + len(body).to_bytes(4, "little") + b"JSON" + body


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


def test_import_blend_checks_file_header_and_disables_autoexec(monkeypatch):
    monkeypatch.setattr(routes_blender, "find_blender", lambda: Path(sys.executable))
    r = client.post("/api/blender/import_blend", content=b"not a blend file", headers=WRITE)
    assert r.status_code == 400 and ".blend" in r.json()["detail"]
    captured = {}

    def fake_submit(build, data, input_name):
        captured["argv"] = build(Path("w"), Path("w") / input_name)
        captured["input_name"] = input_name
        return type("J", (), {"public": lambda self: {"id": "x"}})()

    monkeypatch.setattr(routes_blender.runner, "submit_command", fake_submit)
    assert client.post("/api/blender/import_blend", content=b"BLENDER-v402....", headers=WRITE).status_code == 200
    assert captured["input_name"] == "input.blend"
    assert "--disable-autoexec" in captured["argv"]
    assert captured["argv"][captured["argv"].index("--op") + 1] == "import_blend"


def test_export_fbx_is_whitelisted_and_takes_glb(monkeypatch):
    assert clean_params("export_fbx", {"evil": 1}) == {}
    monkeypatch.setattr(routes_blender, "find_blender", lambda: Path(sys.executable))
    captured = {}

    def fake_submit(build, data, input_name):
        captured["argv"] = build(Path("w"), Path("w") / input_name)
        captured["input_name"] = input_name
        return type("J", (), {"public": lambda self: {"id": "x"}})()

    monkeypatch.setattr(routes_blender.runner, "submit_command", fake_submit)
    assert client.post("/api/blender/export_fbx", content=make_glb({"asset": {"version": "2.0"}}), headers=WRITE).status_code == 200
    assert captured["input_name"] == "input.glb"
    assert captured["argv"][captured["argv"].index("--op") + 1] == "export_fbx"


@pytest.mark.parametrize("op", ["export_fbx", "bevel", "render"])
@pytest.mark.parametrize("body", [
    make_glb({"images": [{"uri": "../../configs/global_config.json"}]}),
    make_glb({"buffers": [{"uri": "C:/secret.bin", "byteLength": 1}]}),
    make_glb({"images": 5}),
    b"not a glb",
])
def test_glb_ops_reject_external_files_and_bad_input(monkeypatch, op, body):
    monkeypatch.setattr(routes_blender, "find_blender", lambda: Path(sys.executable))
    monkeypatch.setattr(routes_blender.runner, "submit_command", lambda *a: pytest.fail("không được chạy Blender"))
    assert client.post(f"/api/blender/{op}", content=body, headers=WRITE).status_code == 400


def test_glb_with_embedded_data_is_accepted(monkeypatch):
    monkeypatch.setattr(routes_blender, "find_blender", lambda: Path(sys.executable))
    job = type("J", (), {"public": lambda self: {"id": "x"}})()
    monkeypatch.setattr(routes_blender.runner, "submit_command", lambda *a: job)
    body = make_glb({"images": [{"bufferView": 0}, {"uri": "data:image/png;base64,AA"}], "buffers": [{"byteLength": 1}]})
    assert client.post("/api/blender/export_fbx", content=body, headers=WRITE).status_code == 200


@pytest.mark.parametrize("url", ["/api/jobs/{}/result.fbx", "/api/jobs/{}/metallic-smoothness/0.png", "/api/jobs/{}/texture/0"])
def test_fbx_results_are_404_until_job_is_done(monkeypatch, tmp_path, url):
    assert client.get(url.format("missing")).status_code == 404
    (tmp_path / "model.fbx").write_bytes(b"FBX")
    (tmp_path / "texture_0.jpg").write_bytes(b"JPG")
    (tmp_path / "metallic-smoothness-0.png").write_bytes(b"PNG")
    job = type("J", (), {"status": "running", "work_dir": tmp_path})()
    monkeypatch.setattr(routes_jobs.runner, "get", lambda job_id: job)
    assert client.get(url.format("x")).status_code == 404
    job.status = "done"
    assert client.get(url.format("x")).status_code == 200


def test_find_blender_picks_highest_version_numerically(tmp_path, monkeypatch):
    from backend import blender_environment
    for name in ("blender-4.2.23-windows-x64", "blender-5.2.3-windows-x64", "blender-10.0.1-windows-x64"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "blender.exe").write_bytes(b"")
    monkeypatch.setattr(blender_environment, "BLENDER_DIR", tmp_path)
    assert blender_environment.find_blender().parent.name == "blender-10.0.1-windows-x64"
