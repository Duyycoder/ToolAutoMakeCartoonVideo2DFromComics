@echo off
setlocal
pushd "%~dp0"
echo ============================================================
echo  AutoCartoon Video Maker - Running Application
echo ============================================================
echo.

if not exist "AIVoice\.venv\Scripts\python.exe" (
    echo [ERROR] setup.bat has not been run or virtualenv is missing.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

:: Set PYTHONPATH so that orchestrator modules can be resolved
set PYTHONPATH=%CD%
:: Log tieng Viet tren console Windows can UTF-8
set PYTHONIOENCODING=utf-8

echo [INFO] Starting Gemini-API Server...
start "Gemini-API Server" cmd /c "cd /d %CD%\toolCaoTruyen\Gemini-API && start_server.bat"

echo [INFO] Starting Orchestrator Backend ^& Web UI...
start "" http://127.0.0.1:8100/

:: QUAN TRONG: sau khi di chuyen thu muc du an, cac file .exe trong venv
:: (uvicorn.exe, pip.exe, streamlit.exe...) deu HONG vi chua duong dan tuyet doi cu.
:: Chi python.exe con chay dung -> luon goi module qua "python -m ..."
"AIVoice\.venv\Scripts\python.exe" -m uvicorn orchestrator.main:app --host 127.0.0.1 --port 8100
pause
