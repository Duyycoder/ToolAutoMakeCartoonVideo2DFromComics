@echo off
:: run.bat        -> mo Easy3D (khong console, log vao logs\app.log)
:: run.bat debug  -> mo kem console de xem log truc tiep
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    call setup.bat
    if errorlevel 1 (popd & exit /b 1)
)
if /i "%~1"=="debug" (
    ".venv\Scripts\python.exe" -m backend.desktop_launcher
) else (
    start "" ".venv\Scripts\pythonw.exe" -m backend.desktop_launcher
)
popd
