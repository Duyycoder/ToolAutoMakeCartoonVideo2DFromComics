@echo off
:: Cai Hunyuan3D-2mini (tao hinh 3D chat luong cao, cham hon TripoSR) vao .venv-hunyuan RIENG.
:: Chay SAU setup.bat. Tai khoang 4 GB (torch CUDA + trong so 3.8 GB). Can GPU NVIDIA (CPU chay duoc nhung rat cham).
:: License: Tencent Hunyuan Community License (khong ap dung tai EU, Anh, Han Quoc) - xem third_party\Hunyuan3D-2\LICENSE
setlocal enabledelayedexpansion
set PYTHONUTF8=1
pushd "%~dp0.."
set "HY3DGEN_MODELS=%CD%\models\hy3dgen"
set "HF_HOME=%CD%\models\hf"
set "HUNYUAN_COMMIT=f8db63096c8282cb27354314d896feba5ba6ff8a"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua chay setup.bat - hay chay setup.bat truoc.
    goto :fail
)
set "PY="
py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo [LOI] Can Python 3.11.
    goto :fail
)

set "TORCH_INDEX=https://download.pytorch.org/whl/cpu"
".venv\Scripts\python.exe" -c "import sys; from backend.gpu_info import query_nvidia_gpus as q; sys.exit(0 if q() else 1)"
if !errorlevel! equ 0 (
    set "TORCH_INDEX=https://download.pytorch.org/whl/cu121"
) else (
    echo [CANH BAO] Khong thay GPU NVIDIA - Hunyuan3D se chay CPU, moi mo hinh mat rat lau.
)

if not exist ".venv-hunyuan\Scripts\python.exe" (
    echo [INFO] Tao .venv-hunyuan...
    !PY! -m venv .venv-hunyuan || goto :fail
)
set "HPY=.venv-hunyuan\Scripts\python.exe"
"%HPY%" -m pip install --upgrade pip >nul
"%HPY%" -m pip install --default-timeout=1000 torch==2.4.1 torchvision==0.19.1 --index-url !TORCH_INDEX! || goto :fail

:: Ma nguon Hunyuan3D-2 ghim dung commit da kiem tra API
if not exist "third_party\Hunyuan3D-2\hy3dgen" (
    echo [INFO] Tai ma nguon Hunyuan3D-2...
    mkdir "third_party\Hunyuan3D-2" 2>nul
    pushd "third_party\Hunyuan3D-2"
    git init -q && git remote add origin https://github.com/Tencent/Hunyuan3D-2.git
    git fetch -q --depth 1 origin %HUNYUAN_COMMIT% && git checkout -q FETCH_HEAD
    set "GIT_ERR=!errorlevel!"
    popd
    if not "!GIT_ERR!"=="0" goto :fail
)
"%HPY%" -m pip install --default-timeout=1000 -r workers\requirements-hunyuan.txt || goto :fail
"%HPY%" scripts\fix_onnxruntime_gpu.py

:: Chi tai ban .safetensors fp16 (thu muc goc co ca ban .ckpt trung lap -> tiet kiem 3.8 GB)
echo [INFO] Tai trong so Hunyuan3D-2mini (~3.8 GB, lan dau mat vai phut)...
"%HPY%" -c "import os; from huggingface_hub import hf_hub_download as d; dst=os.path.join(os.environ['HY3DGEN_MODELS'],'tencent','Hunyuan3D-2mini'); [d('tencent/Hunyuan3D-2mini', f'hunyuan3d-dit-v2-mini/{f}', local_dir=dst) for f in ('config.yaml','model.fp16.safetensors')]" || goto :fail

echo.
echo [OK] Da cai Hunyuan3D-2mini. Mo Easy3D, bam "Tao tu anh" va chon "Chat luong cao".
popd
exit /b 0

:fail
echo.
echo [LOI] Cai Hunyuan3D that bai - xem thong bao phia tren. TripoSR van dung duoc binh thuong.
if not defined NON_INTERACTIVE pause
popd
exit /b 1
