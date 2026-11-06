@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1
pushd "%~dp0"
set "HF_HOME=%~dp0models\hf"
echo ============================================================
echo  Easy3D - Cai dat moi truong
echo ============================================================

:: 1. Python 3.11
set "PY="
py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [LOI] Can Python 3.11: https://www.python.org/downloads/release/python-3119/
    goto :fail
)
echo [OK] Python: !PY!

:: 2. Git (de tai TripoSR)
where git >nul 2>&1 || (echo [LOI] Can Git for Windows: https://git-scm.com/download/win & goto :fail)

:: 3. .venv backend (nhe, khong torch)
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Tao .venv backend...
    !PY! -m venv .venv || goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt || goto :fail

:: 4. Nhan GPU NVIDIA theo nvidia-smi (dung chung logic backend\gpu_info.py)
set "TORCH_INDEX=https://download.pytorch.org/whl/cpu"
".venv\Scripts\python.exe" -c "import sys; from backend.gpu_info import query_nvidia_gpus as q; sys.exit(0 if q() else 1)"
if !errorlevel! equ 0 (
    set "TORCH_INDEX=https://download.pytorch.org/whl/cu121"
    echo [OK] Co GPU NVIDIA - cai PyTorch CUDA 12.1.
) else (
    echo [CANH BAO] Khong thay GPU NVIDIA - cai PyTorch CPU. Tao 3D se RAT cham.
)

:: 5. .venv-ai (torch + TripoSR + rembg)
if not exist ".venv-ai\Scripts\python.exe" (
    echo [INFO] Tao .venv-ai...
    !PY! -m venv .venv-ai || goto :fail
)
set "AIPY=.venv-ai\Scripts\python.exe"
"%AIPY%" -m pip install --upgrade pip >nul
"%AIPY%" -m pip install --default-timeout=1000 torch==2.4.1 --index-url !TORCH_INDEX! || goto :fail

if not exist "third_party\TripoSR\tsr" (
    echo [INFO] Tai ma nguon TripoSR...
    git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git third_party\TripoSR || goto :fail
)
"%AIPY%" -m pip install --default-timeout=1000 -r workers\requirements-ai.txt || goto :fail
"%AIPY%" scripts\fix_onnxruntime_gpu.py

:: 6. Tai truoc trong so TripoSR (~1.7 GB) vao models\hf
echo [INFO] Tai trong so TripoSR (lan dau mat vai phut)...
"%AIPY%" -c "from huggingface_hub import hf_hub_download as d; d('stabilityai/TripoSR','config.yaml'); d('stabilityai/TripoSR','model.ckpt')" || goto :fail

:: 7. Cau hinh ca nhan
if not exist "configs\config.json" copy /y "configs\config.example.json" "configs\config.json" >nul

:: 8. Ollama (cho tro ly AI - Phase 06, khong bat buoc luc nay)
where ollama >nul 2>&1 || echo [CANH BAO] Chua cai Ollama - tro ly AI se khong dung duoc: https://ollama.com/download

echo.
echo [OK] Cai dat xong. Chay run.bat de mo Easy3D.
popd
exit /b 0

:fail
echo.
echo [LOI] Cai dat that bai - xem thong bao phia tren.
if not defined NON_INTERACTIVE pause
popd
exit /b 1
