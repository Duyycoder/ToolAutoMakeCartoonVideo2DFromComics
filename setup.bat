@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"
echo ============================================================
echo  AutoCartoon Video Maker - Global Setup Wizard
echo ============================================================
echo.

set NON_INTERACTIVE=1

:: 0. Dong bo submodule (clone khong --recursive se de lai 2 thu muc rong)
where git >nul 2>&1
if %errorlevel% equ 0 if exist ".gitmodules" (
    echo [INFO] Dang dong bo git submodule - AIVoice, toolCaoTruyen...
    git submodule update --init --recursive
)
if not exist "toolCaoTruyen\setup.bat" (
    echo [ERROR] Thieu ma nguon submodule toolCaoTruyen.
    echo         Hay cai Git for Windows roi chay lai setup.bat, hoac clone lai bang:
    echo         git clone --recursive https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
    pause
    exit /b 1
)
if not exist "AIVoice\setup.bat" (
    echo [ERROR] Thieu ma nguon submodule AIVoice.
    echo         Hay cai Git for Windows roi chay lai setup.bat, hoac clone lai bang:
    echo         git clone --recursive https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
    pause
    exit /b 1
)
echo.

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
echo [LUU Y] Neu dung engine dich "Gemini API (Offline/Local)":
echo         phai dien cookies vao file toolCaoTruyen\Gemini-API\cookies.json
echo         truoc khi chay run.bat (xem huong dan trong toolCaoTruyen\Gemini-API\README.md).
pause
