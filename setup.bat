@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"
echo ============================================================
echo  AutoCartoon Video Maker - Global Setup Wizard
echo ============================================================
echo.

set NON_INTERACTIVE=1

:: 1. Setup toolCaoTruyen
echo [INFO] Setting up Crawler ^& Translator (toolCaoTruyen)...
cd toolCaoTruyen
call setup.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to setup toolCaoTruyen.
    pause
    exit /b 1
)
cd ..
echo.

:: 2. Setup AIVoice
echo [INFO] Setting up TTS ^& Video Engines (AIVoice)...
cd AIVoice
call setup.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to setup AIVoice.
    pause
    exit /b 1
)
cd ..
echo.

:: 3. Setup Orchestrator extra dependencies in AIVoice .venv
echo [INFO] Installing Orchestrator dependencies...
"AIVoice\.venv\Scripts\pip" install fastapi uvicorn sse-starlette pydantic requests
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Orchestrator dependencies.
    pause
    exit /b 1
)
echo.

echo [INFO] Global Setup Completed successfully!
pause
