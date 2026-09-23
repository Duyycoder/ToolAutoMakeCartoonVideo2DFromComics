@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1
pushd "%~dp0"
echo ============================================================
echo  Cao ^& Dich Video - Setup Wizard
echo ============================================================
echo.

set NON_INTERACTIVE=1

:: 0. Dong bo submodule (clone khong --recursive se de lai 2 thu muc rong)
where git >nul 2>&1
if %errorlevel% equ 0 if exist ".gitmodules" (
    echo [INFO] Dang dong bo git submodule - AIVoice...
    git submodule update --init --recursive
)
if not exist "AIVoice\setup.bat" (
    echo [ERROR] Thieu ma nguon submodule AIVoice.
    echo         Hay cai Git for Windows roi chay lai setup.bat, hoac clone lai bang:
    echo         git clone --recursive https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics.git
    pause
    exit /b 1
)

:: (Da bo) Truoc day co 2 lenh powershell ghi de setup.bat cua submodule de escape
:: dau "&". Ca hai file nguon nay DA escape san, nen viec ghi de chi lam 2 dieu xau:
:: doi encoding sang UTF-8 co BOM va lam ban working tree cua submodule sau moi lan
:: chay setup (git status luon bao modified). Da xoa.

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
:: Goi bang duong dan day du: may nao bat NoDefaultCurrentDirectoryInExePath
:: (chinh sach bao mat) thi cmd KHONG tim file o thu muc hien tai nua.
start "" /wait "%CD%\python-3.11.9-amd64.exe" /quiet PrependPath=1 Include_test=0
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

:: 2. Setup AIVoice
:: --skip-models: KHONG tai mo hinh ve anh cua luong truyen tranh (RealESRGAN,
:: IP-Adapter, CLIP ViT-H ~2.5 GB, Hyper-SD). Cong cu video khong dung toi -
:: da kiem adapter_autosub/adapter_download khong goi cai nao. Mo hinh giong doc
:: (Piper/XTTS) van tai vi tab Dich co dung de long tieng.
:: Goi bang duong dan day du (xem ghi chu NoDefaultCurrentDirectoryInExePath o
:: tren) - "call setup.bat" tran se bao "not recognized" tren may bat bien do.
:: Van phai dung TRONG thu muc AIVoice vi setup cua no dung duong dan tuong doi.
:: Cai bo thu vien GON cua cong cu video thay vi requirements.txt day du: ban day
:: du keo theo ca luong ve truyen tranh (diffusers, insightface, rembg, basicsr...)
:: va lam pip giai phu thuoc ket hang gio - da thu that tren may sach.
set "AIVOICE_REQUIREMENTS=requirements-video.txt"
echo [INFO] Setting up TTS ^& Video Engines (AIVoice)...
cd /d "%~dp0AIVoice"
call "%~dp0AIVoice\setup.bat" --skip-models
if %errorlevel% neq 0 (
    echo [ERROR] Failed to setup AIVoice.
    pause
    exit /b 1
)
cd /d "%~dp0"
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

:: 3a. Tinh nang TUY CHON - cai duoc thi tot, loi thi chi canh bao.
::     Tach khoi requirements-video.txt vi day la nhung goi hay vo tren may moi
::     (can trinh bien dich C++, chi muc rieng, Git). Hong mot goi KHONG duoc keo
::     ca buoi cai dat chet theo - thieu goi nao thi rieng tinh nang do bao loi.
echo ----------------------------------------------------------------------
echo [INFO] Cai cac tinh nang tuy chon - giong doc offline, tach nhac nen, OCR...
echo ----------------------------------------------------------------------
set "VPY=%~dp0AIVoice\.venv\Scripts\python.exe"
set "CAI_THIEU="
:: Khoa PyTorch dang co: goi tuy chon nao doi torch khac thi pip bao loi (chi mat
:: goi do) thay vi am tham thay torch CUDA bang ban CPU tu PyPI - hong ca Whisper.
set "RANG_BUOC=%~dp0AIVoice\.venv\rang_buoc_torch.txt"
"%VPY%" -m pip freeze | findstr /b /i "torch== torchaudio== torchvision==" > "%RANG_BUOC%"

call :cai_tuy_chon "Giong doc Piper - offline" "piper-tts>=1.2.0"
call :cai_tuy_chon "Giong doc XTTSv2 - nhai giong" "coqui-tts>=0.27.5"
call :cai_tuy_chon "Giong doc VieNeu" "vieneu==3.0.9" "neucodec>=0.0.6" "torchao==0.16.0"
call :cai_tuy_chon "Tach nhac nen Demucs" "demucs"
call :cai_tuy_chon "Cong cu kiem thu pytest" "pytest"

:: OCR doc chu chay tren hinh. PyPI chi co paddlepaddle-gpu toi 2.6.2 - ban 3.x
:: GPU nam o chi muc rieng cua Paddle. May khong co GPU CUDA thi dung ban CPU.
"%VPY%" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    call :cai_tuy_chon "Paddle GPU cho OCR" "paddlepaddle-gpu==3.3.1" "--extra-index-url" "https://www.paddlepaddle.org.cn/packages/stable/cu126/"
) else (
    call :cai_tuy_chon "Paddle CPU cho OCR" "paddlepaddle==3.3.1"
)
:: videocr tren PyPI la ban GOC dung Tesseract - ma nguon goi API cua fork
:: oliverfei/videocr-PaddleOCR nen phai cai tu Git, ghim commit da chay on.
where git >nul 2>&1
if !errorlevel! equ 0 (
    call :cai_tuy_chon "videocr-PaddleOCR" "videocr @ git+https://github.com/oliverfei/videocr-PaddleOCR.git@b56af756cd2fdcdb54c79037d507aa8aec3c23c5"
) else (
    echo [WARNING] Khong co Git - bo qua videocr-PaddleOCR, che do OCR se khong dung duoc.
    set "CAI_THIEU=!CAI_THIEU! videocr-PaddleOCR;"
)

if defined CAI_THIEU (
    echo.
    echo [WARNING] Chua cai duoc:!CAI_THIEU!
    echo           Cac tinh nang con lai van dung binh thuong. Chay lai setup.bat de thu lai.
) else (
    echo [INFO] Da cai du cac tinh nang tuy chon.
)
echo.

:: 3b. WebView2 Runtime - thu vien Windows de ve cua so ung dung.
::     Thieu no thi run.bat chi mo duoc giao dien trong trinh duyet.
if exist "scripts\cai_webview2.bat" call "scripts\cai_webview2.bat"
echo.

:: 4. Tao configs\global_config.json neu chua co.
:: Sinh bang chinh orchestrator/config.py de gia tri mac dinh chi co MOT nguon su
:: that (khong copy config.example.json - file mau chua key gia
:: "YOUR_GEMINI_API_KEY_HERE" se lot qua buoc kiem tra roi chet luc goi API).
echo [INFO] Kiem tra file cau hinh configs\global_config.json...
set "PYTHONPATH=%CD%"
"AIVoice\.venv\Scripts\python.exe" -c "from orchestrator.config import load_global_config; load_global_config(); print('[INFO] Cau hinh da san sang.')"
if %errorlevel% neq 0 (
    echo [WARNING] Chua tao duoc file cau hinh - ung dung se tu tao khi chay lan dau.
)
echo.

echo ============================================================
echo  [OK] Cai dat xong - Cao ^& Dich Video da san sang.
echo ============================================================
echo [LUU Y] Engine dich mac dinh la Ollama (chay tren may, khong can API key).
echo         Cai Ollama tai https://ollama.com roi chay: ollama pull qwen2.5:3b-instruct
echo.

:: Duoc run.bat goi thi quay ve ngay de no mo app - khong bat bam phim.
:: Phai "exit /b 0" ro rang: buoc tao cau hinh o tren co the de lai errorlevel 1
:: (chi la canh bao), run.bat se tuong cai dat hong va dung lai.
if defined CALLED_FROM_RUN exit /b 0

echo  Bam phim bat ky de mo cong cu. Lan sau chi can nhay dup run.bat.
pause >nul
call "%~dp0run.bat"
exit /b 0


:: ---------------------------------------------------------------------------
:: cai_tuy_chon "<mo ta>" "<goi 1>" ["<goi hoac tham so 2>" ...]
:: Cai mot tinh nang tuy chon; loi thi ghi ten vao CAI_THIEU roi di tiep.
:: Mo ta KHONG duoc chua dau ngoac tron: no bi mo rong ben trong khoi if (...)
:: ben duoi, dau ")" se dong khoi som va lam hong ca file.
:cai_tuy_chon
echo [INFO] - %~1...
"%VPY%" -m pip install --default-timeout=1000 --prefer-binary -c "%RANG_BUOC%" %2 %3 %4 %5 %6
if errorlevel 1 (
    echo [WARNING] Chua cai duoc: %~1
    set "CAI_THIEU=!CAI_THIEU! %~1;"
)
exit /b 0
