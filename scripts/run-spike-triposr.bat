@echo off
:: Spike Phase 01: do VRAM TripoSR theo ma tran cau hinh, ghi report vao plans\reports\
:: run-spike-triposr.bat           -> chay du 9 cau hinh
:: run-spike-triposr.bat --quick   -> chi 1 cau hinh (kiem tra nhanh moi truong)
:: run-spike-triposr.bat --image duong\dan\anh.png
pushd "%~dp0.."
set PYTHONUTF8=1
set "HF_HOME=%CD%\models\hf"
if not exist ".venv-ai\Scripts\python.exe" (
    echo [LOI] Chua co .venv-ai - chay setup.bat truoc.
    popd & exit /b 1
)
".venv-ai\Scripts\python.exe" workers\spike_triposr_matrix.py %*
popd
