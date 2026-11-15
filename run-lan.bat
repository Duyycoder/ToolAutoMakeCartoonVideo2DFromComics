@echo off
setlocal
set PYTHONUTF8=1
pushd "%~dp0"

:: Ban chay tren LAPTOP/PC (GPU NVIDIA) de chinh sua tu DIEN THOAI cung Wi-Fi.
:: Khac run.bat: run.bat mo cua so app chi dung tren chinh may nay.
:: Xuat video bang NVENC, proxy bang NVDEC/NVENC, AI chay tren GPU cua may.

if not exist "AIVoice\.venv\Scripts\python.exe" (
    echo [LOI] May nay chua cai dat. Nhay dup run.bat mot lan de cai, roi mo lai file nay.
    pause
    exit /b 1
)
set PYTHONPATH=%CD%
set PYTHONIOENCODING=utf-8
"AIVoice\.venv\Scripts\python.exe" -m orchestrator.chay_mang_noi_bo
pause
