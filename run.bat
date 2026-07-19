@echo off
setlocal
set PYTHONUTF8=1
pushd "%~dp0"

if not exist "AIVoice\.venv\Scripts\python.exe" (
    echo [ERROR] setup.bat has not been run or virtualenv for AIVoice is missing.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

if not exist "toolCaoTruyen\.venv\Scripts\python.exe" (
    echo [ERROR] setup.bat has not been run or virtualenv for toolCaoTruyen is missing.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

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
