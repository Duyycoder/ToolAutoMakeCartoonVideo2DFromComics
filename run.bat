@echo off
setlocal
set PYTHONUTF8=1
pushd "%~dp0"

:: May moi vua "git clone" ve chua co moi truong -> tu chay setup.bat luon,
:: de nguoi dung chi can nhay dup MOT file duy nhat la run.bat.
if not exist "AIVoice\.venv\Scripts\python.exe" goto :need_setup
if not exist "toolCaoTruyen\.venv\Scripts\python.exe" goto :need_setup
goto :ready

:need_setup
echo ============================================================
echo  Lan dau chay tren may nay - dang cai dat tu dong.
echo  Viec nay can Internet va co the mat 30-60 phut.
echo  Cu de cua so nay chay, khong tat giua chung.
echo ============================================================
echo.
call "%~dp0setup.bat"
if not exist "AIVoice\.venv\Scripts\python.exe" (
    echo.
    echo [LOI] Cai dat chua hoan tat - thieu moi truong AIVoice.
    echo       Xem thong bao loi o tren, sua roi chay lai file nay.
    pause
    exit /b 1
)
if not exist "toolCaoTruyen\.venv\Scripts\python.exe" (
    echo.
    echo [LOI] Cai dat chua hoan tat - thieu moi truong toolCaoTruyen.
    echo       Xem thong bao loi o tren, sua roi chay lai file nay.
    pause
    exit /b 1
)
echo.
echo [OK] Cai dat xong. Dang mo ung dung...
echo.

:ready

:: Set PYTHONPATH so that orchestrator modules can be resolved
set PYTHONPATH=%CD%
:: Log tieng Viet tren console Windows can UTF-8
set PYTHONIOENCODING=utf-8

:: QUAN TRONG: sau khi di chuyen thu muc du an, cac file .exe trong venv
:: (uvicorn.exe, pip.exe...) deu HONG vi chua duong dan tuyet doi cu.
:: Chi python.exe/pythonw.exe con chay dung -> luon goi module qua "-m ..."
::
:: orchestrator.desktop = cua so ung dung WebView2 + uvicorn :8100 + tu bat
:: Gemini proxy (an). Dong cua so app se tu diet het tien trinh con.

if /I "%~1"=="debug" goto :debug

:: Che do thuong: khong hien console nao - log ghi vao logs\app.log
start "" "AIVoice\.venv\Scripts\pythonw.exe" -m orchestrator.desktop
exit /b 0

:debug
echo ============================================================
echo  AutoCartoon Video Maker - DEBUG MODE (log hien truc tiep)
echo ============================================================
"AIVoice\.venv\Scripts\python.exe" -m orchestrator.desktop
pause
