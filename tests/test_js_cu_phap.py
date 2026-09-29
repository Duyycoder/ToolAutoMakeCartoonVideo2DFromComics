import os
import glob
import shutil
import subprocess
import pytest
from pathlib import Path
import re

def get_node_path():
    node = shutil.which("node")
    if node:
        return node
    
    appdata = os.environ.get("APPDATA")
    if appdata:
        fnm_path = Path(appdata) / "fnm" / "node-versions"
        if fnm_path.exists():
            versions = []
            for v_dir in fnm_path.iterdir():
                node_exe = v_dir / "installation" / "node.exe"
                if node_exe.exists():
                    versions.append((v_dir.name, node_exe))
            if versions:
                versions.sort(key=lambda x: x[0], reverse=True)
                return str(versions[0][1])
    return None

def test_js_syntax(tmp_path):
    node_exe = get_node_path()
    if not node_exe:
        pytest.skip("Không tìm thấy node.exe")
    
    base_dir = Path(__file__).parent.parent
    
    js_files = []
    # webui/editor/*.js
    for f in (base_dir / "webui" / "editor").glob("*.js"):
        js_files.append(f)
    # tests/js/*.mjs
    for f in (base_dir / "tests" / "js").glob("*.mjs"):
        js_files.append(f)
        
    for js_file in js_files:
        with open(js_file, "rb") as f:
            content = f.read()
        
        # Kiểm tra BOM
        assert not content.startswith(b'\xef\xbb\xbf'), f"Lỗi BOM: File {js_file.name} chứa BOM"
        
        tmp_mjs = tmp_path / f"{js_file.stem}_{js_file.parent.name}.mjs"
        with open(tmp_mjs, "wb") as f:
            f.write(content)
            
        res = subprocess.run([node_exe, "--check", str(tmp_mjs)], capture_output=True, text=True)
        assert res.returncode == 0, f"Lỗi cú pháp JS trong file {js_file.relative_to(base_dir)}:\n{res.stderr}"
        
    # webui/*.html inline scripts
    for html_file in (base_dir / "webui").rglob("*.html"):
        with open(html_file, "r", encoding="utf-8-sig") as f:
            html_content = f.read()
        
        # Extract <script> and <script type="module">
        scripts = re.finditer(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL | re.IGNORECASE)
        for i, match in enumerate(scripts):
            script_content = match.group(1).strip()
            if not script_content:
                continue
            
            tmp_mjs = tmp_path / f"{html_file.stem}_inline_{i}.mjs"
            with open(tmp_mjs, "w", encoding="utf-8") as f:
                f.write(script_content)
                
            res = subprocess.run([node_exe, "--check", str(tmp_mjs)], capture_output=True, text=True)
            assert res.returncode == 0, f"Lỗi cú pháp JS trong script nội tuyến thứ {i+1} của {html_file.relative_to(base_dir)}:\n{res.stderr}"

def test_js_store():
    node_exe = get_node_path()
    if not node_exe:
        pytest.skip("Không tìm thấy node.exe")
    
    base_dir = Path(__file__).parent.parent
    test_file = base_dir / "tests" / "js" / "store.test.mjs"
    if test_file.exists():
        res = subprocess.run([node_exe, "--test", str(test_file)], capture_output=True, text=True, cwd=str(base_dir / "tests" / "js"))
        assert res.returncode == 0, f"test_js_store failed:\n{res.stdout}\n{res.stderr}"
    else:
        pytest.skip("File test không tồn tại")

def test_js_chon_giong():
    node_exe = get_node_path()
    if not node_exe:
        pytest.skip("Không tìm thấy node.exe")
    
    base_dir = Path(__file__).parent.parent
    test_file = base_dir / "tests" / "js" / "chon_giong.test.mjs"
    if test_file.exists():
        res = subprocess.run([node_exe, "--test", str(test_file)], capture_output=True, text=True, cwd=str(base_dir / "tests" / "js"))
        assert res.returncode == 0, f"test_js_chon_giong failed:\n{res.stdout}\n{res.stderr}"
    else:
        pytest.skip("File test không tồn tại")

def test_js_bang_ai():
    node_exe = get_node_path()
    if not node_exe:
        pytest.skip("Không tìm thấy node.exe")
    
    base_dir = Path(__file__).parent.parent
    test_file = base_dir / "tests" / "js" / "bang_ai.test.mjs"
    if test_file.exists():
        res = subprocess.run([node_exe, "--test", str(test_file)], capture_output=True, text=True, cwd=str(base_dir / "tests" / "js"))
        assert res.returncode == 0, f"test_js_bang_ai failed:\n{res.stdout}\n{res.stderr}"
    else:
        pytest.skip("File test không tồn tại")

