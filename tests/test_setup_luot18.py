import os
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def test_bat_files_crlf_ascii():
    bat_dirs = [REPO_ROOT, os.path.join(REPO_ROOT, "scripts"), os.path.join(REPO_ROOT, "installer")]
    
    for d in bat_dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".bat"):
                file_path = os.path.join(d, f)
                with open(file_path, "rb") as file:
                    content = file.read()
                    
                    try:
                        content.decode("ascii")
                    except UnicodeDecodeError:
                        assert False, f"File {file_path} chua ky tu khong phai ASCII."
                    
                    content_str = content.decode("ascii")
                    if "\n" in content_str:
                        lines = content_str.split("\n")
                        for i, line in enumerate(lines[:-1]):
                            if len(line) == 0 or line[-1] != "\r":
                                assert False, f"File {file_path} chua dong khong phai CRLF (co LF ma khong co CR)."

def test_setup_dry_run_args():
    setup_path = os.path.join(REPO_ROOT, "setup.bat")
    
    res = subprocess.run(f'cmd /c ""{setup_path}" --dry-run"', shell=True, capture_output=True, text=True, cwd=REPO_ROOT)
    out = res.stdout.lower()
    
    assert "ocr:" in out
    assert "piper:" in out
    assert "kokoro:" in out
    assert "vieneu:" in out
    assert "clone:" in out
    
    res2 = subprocess.run(f'cmd /c ""{setup_path}" --dry-run "--tp=loi,ocr""', shell=True, capture_output=True, text=True, cwd=REPO_ROOT)
    out2 = res2.stdout.lower()
    
    assert "ocr:" in out2
    assert "piper:" not in out2
    assert "kokoro:" not in out2
    assert "vieneu:" not in out2
    assert "clone:" not in out2

def test_iss_components_and_run():
    iss_path = os.path.join(REPO_ROOT, "installer", "AutoCartoon.iss")
    with open(iss_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert 'Name: "loi";' in content
    assert 'Name: "gpu";' in content
    assert 'Name: "ocr";' in content
    assert 'Name: "tts\\piper";' in content
    assert 'Name: "tts\\kokoro";' in content
    assert 'Name: "tts\\vieneu";' in content
    assert 'Name: "tts\\clone";' in content
    assert 'Name: "demucs";' in content
    assert 'Name: "lamnet";' in content
    assert 'Name: "dich_offline";' in content
    assert 'Name: "whisper";' in content
    assert 'Name: "taoanh";' in content
    assert 'Name: "minhhoa";' in content
    
    assert '--tp={code:GetSelectedComponents}' in content



def test_noi_goi_setup_boc_ngoac_tham_so_tp():
    """cmd.exe cắt `--tp=loi,ocr` tại dấu phẩy → setup.bat cài ĐỦ mọi thứ. Bộ cài và cai_them.bat phải bọc ngoặc kép."""
    iss = open(os.path.join(REPO_ROOT, "installer", "AutoCartoon.iss"), encoding="utf-8", errors="replace").read()
    assert '"""--tp={code:GetSelectedComponents}""' in iss
    them = open(os.path.join(REPO_ROOT, "scripts", "cai_them.bat"), encoding="ascii").read()
    assert '"--tp=!COMPS!"' in them


def test_dry_run_khong_ngoac_thi_cat_dau_phay():
    """Ghi lại hành vi cmd.exe: không ngoặc thì thấy đủ thành phần (lý do phải bọc ngoặc ở nơi gọi)."""
    setup_path = os.path.join(REPO_ROOT, "setup.bat")
    res = subprocess.run(f'cmd /c ""{setup_path}" --dry-run "--tp=loi,ocr""', shell=True, capture_output=True, text=True, cwd=REPO_ROOT)
    assert "- ocr:" in res.stdout and "- kokoro:" not in res.stdout and "- taoanh:" not in res.stdout



def test_bo_cai_khong_ghi_de_bien_moi_truong_co_san():
    """Bộ cài chỉ đặt HF_HOME/OLLAMA_MODELS khi máy CHƯA có (ghi đè làm Ollama mất model; gỡ cài còn xoá biến gốc)."""
    iss = open(os.path.join(REPO_ROOT, "installer", "AutoCartoon.iss"), encoding="utf-8-sig").read()
    assert "BienTrong('HF_HOME')" in iss and "BienTrong('OLLAMA_MODELS')" in iss
