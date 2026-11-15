@echo off
setlocal
set PYTHONUTF8=1
pushd "%~dp0"

:: MAY XUAT VIDEO tren LAPTOP (GPU NVIDIA): editor o may khac gui viec xuat qua Tailscale.
:: Cua so se hien Dia chi + Ma bi mat - nhap vao hop Xuat video > May xuat > Laptop o may chinh.

if not exist "AIVoice\.venv\Scripts\python.exe" (
    echo [LOI] May nay chua cai dat. Nhay dup run.bat mot lan de cai, roi mo lai file nay.
    pause
    exit /b 1
)
set PYTHONPATH=%CD%
set PYTHONIOENCODING=utf-8
"AIVoice\.venv\Scripts\python.exe" -m orchestrator.may_xuat
pause
