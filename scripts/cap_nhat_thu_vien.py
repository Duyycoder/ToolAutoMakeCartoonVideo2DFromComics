"""Cai them thu vien KHI ban moi doi file requirements - dung cho cai de ban moi.

Luu dau sha256 cua tung file requirements vao AIVoice/.venv/dau_thu_vien.json.
Lan cap nhat sau: file nao doi dau moi chay pip; khong doi thi bo qua (vai giay
thay vi pip phai giai lai ca cay phu thuoc).

    python scripts/cap_nhat_thu_vien.py            # cai file doi, ghi dau moi
    python scripts/cap_nhat_thu_vien.py --chi-ghi  # chi ghi dau (sau khi setup.bat cai day du)
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV = os.path.join(ROOT, "AIVoice", ".venv")
DAU_PATH = os.path.join(VENV, "dau_thu_vien.json")
# Thu tu quan trong: thu vien loi cua AIVoice truoc, orchestrator sau (giong setup.bat)
FILES = [
    os.path.join("AIVoice", "requirements-video.txt"),
    os.path.join("orchestrator", "requirements.txt"),
]


def _dau(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _doc_dau() -> dict:
    try:
        with open(DAU_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _ghi_dau(dau: dict) -> None:
    with open(DAU_PATH, "w", encoding="utf-8") as f:
        json.dump(dau, f, indent=2)


def main() -> int:
    chi_ghi = "--chi-ghi" in sys.argv
    cu = _doc_dau()
    moi = dict(cu)
    loi = 0
    for rel in FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        d = _dau(path)
        if not chi_ghi and cu.get(rel) != d:
            print(f"[INFO] {rel} da doi - dang cai them thu vien...", flush=True)
            # Khoa torch dang co: ban moi khong duoc am tham thay torch CUDA bang ban CPU
            rang_buoc = os.path.join(VENV, "rang_buoc_torch.txt")
            cmd = [sys.executable, "-m", "pip", "install", "-q", "--default-timeout=1000",
                   "--prefer-binary", "-r", path]
            if os.path.exists(rang_buoc):
                cmd += ["-c", rang_buoc]
            if subprocess.call(cmd, cwd=ROOT) != 0:
                print(f"[WARNING] Chua cai xong thu vien trong {rel}.", flush=True)
                loi = 1
                continue  # khong ghi dau -> lan cap nhat sau thu lai
        elif not chi_ghi:
            print(f"[OK] {rel} khong doi - bo qua.", flush=True)
        moi[rel] = d
    _ghi_dau(moi)
    return loi


if __name__ == "__main__":
    sys.exit(main())
