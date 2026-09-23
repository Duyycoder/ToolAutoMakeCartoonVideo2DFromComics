"""Hop thoai chon file cua he dieu hanh.

Khong mo hop thoai that: tien trinh con bi monkeypatch, chi kiem tra phan doc
ket qua va phan quet thu muc.
"""
import json
import os
import subprocess
import types

import pytest
from fastapi import HTTPException

import orchestrator.main as main
from orchestrator.storage import natural_key, scan_video_files


def fake_run(stdout="", stderr="", raises=None):
    def _run(*args, **kwargs):
        if raises:
            raise raises
        return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)
    return _run


# ------------------------------------------------------------ Quet thu muc
def test_sap_tu_nhien_tap2_truoc_tap10():
    names = ["tap10.mp4", "tap2.mp4", "tap1.mp4"]
    assert sorted(names, key=natural_key) == ["tap1.mp4", "tap2.mp4", "tap10.mp4"]
    # Sap theo chu thi tap10 chen len truoc tap2 -> ghep ra video lon tap.
    assert sorted(names) == ["tap1.mp4", "tap10.mp4", "tap2.mp4"]


def test_quet_thu_muc_chi_lay_video_va_khong_de_quy(tmp_path):
    for name in ("tap10.mp4", "tap2.MKV", "ghi_chu.txt", "anh.jpg"):
        (tmp_path / name).write_bytes(b"0")
    sub = tmp_path / "con"
    sub.mkdir()
    (sub / "tap1.mp4").write_bytes(b"0")

    found = [os.path.basename(p) for p in scan_video_files(str(tmp_path))]
    assert found == ["tap2.MKV", "tap10.mp4"]


def test_quet_thu_muc_khong_ton_tai_tra_ve_rong():
    assert scan_video_files("Z:/khong/co") == []
    assert scan_video_files("") == []


# ------------------------------------------------------------- Endpoint
def test_chon_nhieu_file_tra_ve_duong_dan(monkeypatch):
    out = json.dumps({"paths": ["D:/phim/tap1.mp4", "D:/phim/tap2.mp4"], "cancelled": False})
    monkeypatch.setattr(main.subprocess, "run", fake_run(stdout=out + "\n"))
    res = main.pick_files(main.PickFilesSchema(mode="files"))
    assert res["paths"] == ["D:/phim/tap1.mp4", "D:/phim/tap2.mp4"]
    assert res["cancelled"] is False


def test_nguoi_dung_bam_huy(monkeypatch):
    out = json.dumps({"paths": [], "cancelled": True})
    monkeypatch.setattr(main.subprocess, "run", fake_run(stdout=out))
    res = main.pick_files(main.PickFilesSchema(mode="files"))
    assert res["paths"] == [] and res["cancelled"] is True


def test_chon_ca_thu_muc_thi_quet_ra_danh_sach_dung_thu_tu(monkeypatch, tmp_path):
    for name in ("tap10.mp4", "tap2.mp4", "doc.pdf"):
        (tmp_path / name).write_bytes(b"0")
    out = json.dumps({"paths": [str(tmp_path)], "cancelled": False})
    monkeypatch.setattr(main.subprocess, "run", fake_run(stdout=out))

    res = main.pick_files(main.PickFilesSchema(mode="folder"))
    assert [os.path.basename(p) for p in res["paths"]] == ["tap2.mp4", "tap10.mp4"]
    assert res["folder"] == str(tmp_path)


def test_thu_muc_khong_co_video_van_tra_ve_thu_muc(monkeypatch, tmp_path):
    # Khong phai loi: luc tao du an trong de tai video ve, thu muc cha duong
    # nhien chua co video nao. Ben goi tu quyet dinh bao gi.
    (tmp_path / "doc.pdf").write_bytes(b"0")
    out = json.dumps({"paths": [str(tmp_path)], "cancelled": False})
    monkeypatch.setattr(main.subprocess, "run", fake_run(stdout=out))

    res = main.pick_files(main.PickFilesSchema(mode="folder"))

    assert res["folder"] == str(tmp_path)
    assert res["paths"] == []
    assert res["cancelled"] is False


def test_bo_quen_hop_thoai_bao_504(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run",
                        fake_run(raises=subprocess.TimeoutExpired("picker", 600)))
    with pytest.raises(HTTPException) as e:
        main.pick_files(main.PickFilesSchema(mode="files"))
    assert e.value.status_code == 504


def test_tien_trinh_con_khong_in_json_bao_500(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run",
                        fake_run(stdout="", stderr="ModuleNotFoundError: tkinter"))
    with pytest.raises(HTTPException) as e:
        main.pick_files(main.PickFilesSchema(mode="files"))
    assert e.value.status_code == 500
    assert "tkinter" in e.value.detail


def test_hop_thoai_bao_loi_thi_noi_ro_loi(monkeypatch):
    out = json.dumps({"paths": [], "cancelled": True, "error": "no display name"})
    monkeypatch.setattr(main.subprocess, "run", fake_run(stdout=out))
    with pytest.raises(HTTPException) as e:
        main.pick_files(main.PickFilesSchema(mode="files"))
    assert e.value.status_code == 500 and "no display name" in e.value.detail
