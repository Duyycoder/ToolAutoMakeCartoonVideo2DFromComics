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


@pytest.fixture
def rig_folders(tmp_path, monkeypatch):
    monkeypatch.setitem(file_storage.FOLDERS, "rigs", tmp_path / "rigs")
    monkeypatch.setitem(file_storage.FOLDERS, "game", tmp_path / "game")
    return tmp_path


def test_rig_template_save_list_read(rig_folders):
    r = client.post("/api/files/save", params={"kind": "rigs", "name": "Golem.json"},
                    content=b'{"joints": []}', headers=WRITE_HEADERS)
    assert r.status_code == 200, r.text
    assert client.get("/api/files/list", params={"kind": "rigs"}).json() == {"files": ["Golem.json"]}
    assert client.get("/api/files/read", params={"kind": "rigs", "name": "../rigs/Golem.json"}).json() == {"joints": []}
    assert client.get("/api/files/read", params={"kind": "rigs", "name": "missing.json"}).status_code == 404


def test_rigs_folder_only_accepts_json_and_other_kinds_not_listable(rig_folders):
    r = client.post("/api/files/save", params={"kind": "rigs", "name": "x.glb"}, content=b"glTF", headers=WRITE_HEADERS)
    assert r.status_code == 400
    assert client.get("/api/files/list", params={"kind": "projects"}).status_code == 400
    assert client.get("/api/files/read", params={"kind": "output", "name": "a.glb"}).status_code == 404


def test_game_export_goes_to_own_subfolder(rig_folders):
    r = client.post("/api/files/save", params={"kind": "game", "name": "Golem.glb", "folder": "../../Golem"},
                    content=b"glTF", headers=WRITE_HEADERS)
    assert r.status_code == 200, r.text
    assert (rig_folders / "game" / "Golem" / "Golem.glb").read_bytes() == b"glTF"
    r = client.post("/api/files/save", params={"kind": "projects", "name": "a.glb", "folder": "x"},
                    content=b"glTF", headers=WRITE_HEADERS)
    assert r.status_code == 400


@pytest.mark.parametrize("name", ["Golem.fbx", "Golem_MetallicSmoothness.png", "texture_0.jpg"])
def test_game_folder_accepts_fbx_and_its_metallic_map(rig_folders, name):
    r = client.post("/api/files/save", params={"kind": "game", "name": name, "folder": "Golem"},
                    content=b"data", headers=WRITE_HEADERS)
    assert r.status_code == 200, r.text
    assert (rig_folders / "game" / "Golem" / name).read_bytes() == b"data"


def test_projects_folder_accepts_fbx_but_rigs_does_not(temp_folders, rig_folders):
    r = client.post("/api/files/save", params={"kind": "projects", "name": "a.fbx"}, content=b"FBX", headers=WRITE_HEADERS)
    assert r.status_code == 200, r.text
    r = client.post("/api/files/save", params={"kind": "rigs", "name": "a.fbx"}, content=b"FBX", headers=WRITE_HEADERS)
    assert r.status_code == 400
