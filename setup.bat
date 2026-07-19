@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1
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

:: Tu dong sua loi ki tu dac biet & trong file setup cua submodules neu co
powershell -Command "(gc toolCaoTruyen\setup.bat) -replace 'CAU HINH OLLAMA & MODEL AI', 'CAU HINH OLLAMA ^& MODEL AI' | Out-File -encoding utf8 toolCaoTruyen\setup.bat"
powershell -Command "(gc AIVoice\setup.bat) -replace 'Piper & XTTSv2', 'Piper ^& XTTSv2' | Out-File -encoding utf8 AIVoice\setup.bat"

echo.

:: 0.5. Kiem tra va cai dat Python 3.11.9
set "PYTHON_EXE="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%i in ('python --version') do (
        set py_ver=%%i
    )
    echo [INFO] Phat hien Python !py_ver! trong PATH.
    if "!py_ver:~0,4!"=="3.11" (
        set "PYTHON_EXE=python"
        goto :python_ok
    ) else (
        echo [WARNING] He thong phat hien Python version khac 3.11.
    )
)

:: Check via Python Launcher (py -3.11)
py -3.11 -c "import sys" >nul 2>&1
if %errorlevel% equ 0 (
    for /f "delims=" %%i in ('py -3.11 -c "import sys; print(sys.executable)"') do (
        set "PYTHON_EXE=%%i"
    )
    echo [INFO] Tim thay Python 3.11 thong qua Python Launcher tai: !PYTHON_EXE!
    goto :python_ok
)

:: Check if installed in default Local AppData folder for User
set "LOCAL_PY_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if exist "%LOCAL_PY_EXE%" (
    set "PYTHON_EXE=%LOCAL_PY_EXE%"
    echo [INFO] Tim thay Python 3.11 tai: %LOCAL_PY_EXE%
    goto :python_ok
)

:: Check in default Program Files (for all users installation)
set "SYSTEM_PY_EXE=%ProgramFiles%\Python311\python.exe"
if exist "%SYSTEM_PY_EXE%" (
    set "PYTHON_EXE=%SYSTEM_PY_EXE%"
    echo [INFO] Tim thay Python 3.11 tai: %SYSTEM_PY_EXE%
    goto :python_ok
)

:: If Python 3.11 is not found, download and install it silently
echo.
echo ----------------------------------------------------------------------
echo [INFO] Khong tim thay Python 3.11 tren may tinh nay.
echo Dang tu dong tai xuong Python 3.11.9 tu python.org...
echo ----------------------------------------------------------------------
echo.

curl -L -o python-3.11.9-amd64.exe https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
if %errorlevel% neq 0 (
    echo [ERROR] Tai xuong Python that bai. Vui long kiem tra ket noi mang hoac tai thu cong tai python.org.
    pause
    exit /b 1
)

echo [INFO] Dang cai dat Python 3.11.9 chay ngam (Silent Mode)...
echo Vui long cho 1-2 phut...
start /wait python-3.11.9-amd64.exe /quiet PrependPath=1 Include_test=0
del python-3.11.9-amd64.exe

:: Verify silent install
if exist "%LOCAL_PY_EXE%" (
    set "PYTHON_EXE=%LOCAL_PY_EXE%"
    echo [INFO] Cai dat Python 3.11.9 thanh cong!
    goto :python_ok
) else if exist "%SYSTEM_PY_EXE%" (
    set "PYTHON_EXE=%SYSTEM_PY_EXE%"
    echo [INFO] Cai dat Python 3.11.9 thanh cong!
    goto :python_ok
) else (
    echo [ERROR] Cai dat Python tu dong that bai.
    echo Vui long tai va cai dat Python 3.11.9 thu cong tu: https://www.python.org/downloads/
    echo Nho tich chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

:python_ok
:: Cap nhat PATH cho cmd session hien tai neu can thiet
if not "%PYTHON_EXE%"=="python" (
    for /f "delims=" %%A in ("%PYTHON_EXE%") do set "PY_DIR=%%~dpA"
    if "!PY_DIR:~-1!"=="\" set "PY_DIR=!PY_DIR:~0,-1!"
    set "PATH=!PY_DIR!;!PY_DIR!\Scripts;!PATH!"
    echo [INFO] Da cap nhat PATH tam thoi voi: !PY_DIR!
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
"AIVoice\.venv\Scripts\python.exe" -m pip install -r orchestrator\requirements.txt
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
