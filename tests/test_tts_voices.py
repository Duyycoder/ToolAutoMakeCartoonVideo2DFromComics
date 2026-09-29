import pytest
from fastapi.testclient import TestClient
from orchestrator.main import app

client = TestClient(app)

def test_tts_voices_kokoro():
    res = client.get("/api/tts/giong?engine=kokoro")
    assert res.status_code == 200
    giong = res.json()["giong"]
    assert "diem_trinh" in giong
    assert len(giong) == 14

def test_tts_voices_vieneu():
    res = client.get("/api/tts/giong?engine=vieneu")
    assert res.status_code == 200
    giong = res.json()["giong"]
    assert "Ngọc Lan" in giong
    assert len(giong) == 10

def test_tts_voices_edge(monkeypatch):
    async def mock_list_voices():
        return [{"ShortName": "vi-VN-NamMinhNeural"}, {"ShortName": "en-US-JennyNeural"}]
    
    import edge_tts
    monkeypatch.setattr(edge_tts, "list_voices", mock_list_voices)
    
    res = client.get("/api/tts/giong?engine=edge&lang=Vietnamese")
    assert res.status_code == 200
    giong = res.json()["giong"]
    assert "vi-VN-NamMinhNeural" in giong
    assert "en-US-JennyNeural" not in giong
    
    res = client.get("/api/tts/giong?engine=edge&lang=English")
    assert res.status_code == 200
    giong = res.json()["giong"]
    assert "en-US-JennyNeural" in giong

def test_tts_voices_piper(monkeypatch):
    import os
    def mock_listdir(path):
        return ["voice1.onnx", "voice2.onnx", "other.txt"]
    monkeypatch.setattr(os, "listdir", mock_listdir)
    def mock_exists(path):
        return True
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    res = client.get("/api/tts/giong?engine=piper")
    assert res.status_code == 200
    giong = res.json()["giong"]
    assert "voice1.onnx" in giong
    assert "voice2.onnx" in giong
    assert "other.txt" not in giong
