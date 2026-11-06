import pytest
from fastapi.testclient import TestClient

from backend import file_storage
from backend.file_storage import StorageError, safe_filename
from backend.main import app

client = TestClient(app)
WRITE_HEADERS = {"X-Easy3D": "1"}


@pytest.mark.parametrize("raw,expected", [
    ("Con mèo.glb", "Con mèo.glb"),
    ("..\\..\\Windows\\evil.glb", "evil.glb"),
    ("../../etc/passwd.stl", "passwd.stl"),
    ("a<b>:c|d?.obj", "abcd.obj"),
])
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_safe_filename_rejects_empty():
    with pytest.raises(StorageError):
        safe_filename("../..")


@pytest.fixture
def temp_folders(tmp_path, monkeypatch):
    monkeypatch.setitem(file_storage.FOLDERS, "projects", tmp_path / "projects")
    return tmp_path


def test_save_file_inside_folder(temp_folders):
    r = client.post("/api/files/save", params={"kind": "projects", "name": "../x/Dự án 1.glb"},
                    content=b"glTF", headers=WRITE_HEADERS)
    assert r.status_code == 200, r.text
    assert (temp_folders / "projects" / "Dự án 1.glb").read_bytes() == b"glTF"


def test_save_rejects_bad_extension_and_kind(temp_folders):
    r = client.post("/api/files/save", params={"kind": "projects", "name": "x.exe"},
                    content=b"MZ", headers=WRITE_HEADERS)
    assert r.status_code == 400
    r = client.post("/api/files/save", params={"kind": "C:/Windows", "name": "x.glb"},
                    content=b"glTF", headers=WRITE_HEADERS)
    assert r.status_code == 400


def test_post_without_custom_header_is_blocked():
    r = client.post("/api/files/save", params={"kind": "projects", "name": "x.glb"}, content=b"glTF")
    assert r.status_code == 403


def test_foreign_host_is_blocked():
    r = client.get("/api/health", headers={"Host": "evil.example.com"})
    assert r.status_code == 400


def test_image_upload_validation():
    r = client.post("/api/image-to-3d", params={"filename": "a.gif"}, content=b"x", headers=WRITE_HEADERS)
    assert r.status_code == 400
    r = client.post("/api/image-to-3d", params={"filename": "a.png", "quality": "ultra"},
                    content=b"x", headers=WRITE_HEADERS)
    assert r.status_code == 400


def test_ai_status_shape():
    data = client.get("/api/system/ai-status").json()
    assert set(data) == {"ready", "cuda", "checks", "message", "models"}
    assert set(data["models"]) == {"triposr", "hunyuan"}
    assert isinstance(data["message"], str) and data["message"]


def test_webui_served():
    r = client.get("/")
    assert r.status_code == 200 and "Easy3D" in r.text
