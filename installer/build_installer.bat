@echo off
setlocal
pushd "%~dp0"
echo ============================================================
echo  Build bo cai AutoCartoon Video Maker (Inno Setup 6)
echo ============================================================

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [ERROR] Chua cai Inno Setup 6 tren may build.
    echo         Cai bang:  winget install -e --id JRSoftware.InnoSetup
    echo         hoac tai:  https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

if not exist "app.ico" (
    echo [INFO] Chua co app.ico - dang tao icon...
    "..\AIVoice\.venv\Scripts\python.exe" make_icon.py
)

echo [INFO] Dang bien dich installer...
"%ISCC%" AutoCartoon.iss
if %errorlevel% neq 0 (
    echo [ERROR] Bien dich that bai.
    pause
    exit /b 1
)

echo.
echo [OK] Xong! File bo cai nam o: %~dp0Output\
dir /b Output\*.exe
pause
