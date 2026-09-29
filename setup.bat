@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1
pushd "%~dp0"

set "COMPONENTS="
set "WORKSPACE="
set "DRY_RUN=0"
set "KHONG_GPU=0"

:parse_args
if "%~1"=="" goto done_args
if /I "%~1"=="--dry-run" (
    set "DRY_RUN=1"
    shift
    goto parse_args
)
if /I "%~1"=="--khong-gpu" (
    set "KHONG_GPU=1"
    shift
    goto parse_args
)
set "arg=%~1"
if /I "%arg:~0,5%"=="--tp=" (
    set "COMPONENTS=%arg:~5%"
    shift
    goto parse_args
)
if /I "%arg:~0,12%"=="--workspace=" (
    set "WORKSPACE=%arg:~12%"
    shift
    goto parse_args
)
shift
goto parse_args
:done_args

if "!COMPONENTS!"=="" (
    set "COMPONENTS=loi,gpu,ocr,piper,kokoro,vieneu,clone,demucs,lamnet,dich_offline,whisper,taoanh,minhhoa"
)

set "TEMP_COMPS=,!COMPONENTS!,"
set "HAS_OCR=0"
set "HAS_GPU=1"
set "HAS_PIPER=0"
set "HAS_KOKORO=0"
set "HAS_VIENEU=0"
set "HAS_CLONE=0"
set "HAS_DEMUCS=0"
set "HAS_LAMNET=0"
set "HAS_DICHOFFLINE=0"
set "HAS_WHISPER=0"
set "HAS_TAOANH=0"
set "HAS_MINHHOA=0"

echo !TEMP_COMPS! | findstr /i ",ocr," >nul && set "HAS_OCR=1"
echo !TEMP_COMPS! | findstr /i ",gpu," >nul || set "HAS_GPU=0"
echo !TEMP_COMPS! | findstr /i ",piper," >nul && set "HAS_PIPER=1"
echo !TEMP_COMPS! | findstr /i ",kokoro," >nul && set "HAS_KOKORO=1"
echo !TEMP_COMPS! | findstr /i ",vieneu," >nul && set "HAS_VIENEU=1"
echo !TEMP_COMPS! | findstr /i ",clone," >nul && set "HAS_CLONE=1"
echo !TEMP_COMPS! | findstr /i ",demucs," >nul && set "HAS_DEMUCS=1"
echo !TEMP_COMPS! | findstr /i ",lamnet," >nul && set "HAS_LAMNET=1"
echo !TEMP_COMPS! | findstr /i ",dich_offline," >nul && set "HAS_DICHOFFLINE=1"
echo !TEMP_COMPS! | findstr /i ",whisper," >nul && set "HAS_WHISPER=1"
echo !TEMP_COMPS! | findstr /i ",taoanh," >nul && set "HAS_TAOANH=1"
echo !TEMP_COMPS! | findstr /i ",minhhoa," >nul && set "HAS_MINHHOA=1"

if "!KHONG_GPU!"=="1" set "HAS_GPU=0"

if "!DRY_RUN!"=="1" (
    echo [DRY-RUN] Ke hoach cai dat:
    echo - loi: cai dat co ban
    if !HAS_OCR! equ 1 echo - ocr: paddleocr, videocr
    if !HAS_PIPER! equ 1 echo - piper: piper-tts
    if !HAS_KOKORO! equ 1 echo - kokoro: Kokoro-Vietnamese
    if !HAS_VIENEU! equ 1 echo - vieneu: vieneu, neucodec
    if !HAS_CLONE! equ 1 echo - clone: coqui-tts
    if !HAS_DEMUCS! equ 1 echo - demucs: demucs
    if !HAS_LAMNET! equ 1 echo - lamnet: RealESRGAN
    if !HAS_DICHOFFLINE! equ 1 echo - dich_offline: ollama, hy-mt2:1.8b-q4
    if !HAS_WHISPER! equ 1 echo - whisper: models whisper-medium, PhoWhisper-small
    if !HAS_TAOANH! equ 1 echo - taoanh: dreamshaper-8
    exit /b 0
)


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
:: Chi tai mo hinh giong Piper (vai chuc MB). XTTSv2 ~5.2 GB chi can khi nhai giong,
:: bat may moi tai no la chan ca buoi cai hang gio tren mang cham - da gap that.

set "AIVOICE_MODEL_ENGINES="
if !HAS_PIPER! equ 1 set "AIVOICE_MODEL_ENGINES=piper"
if !HAS_CLONE! equ 1 (
    if "!AIVOICE_MODEL_ENGINES!"=="" (
        set "AIVOICE_MODEL_ENGINES=coqui"
    ) else (
        set "AIVOICE_MODEL_ENGINES=!AIVOICE_MODEL_ENGINES!,coqui"
    )
)
if "!AIVOICE_MODEL_ENGINES!"=="" set "AIVOICE_MODEL_ENGINES=none"

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

if !HAS_PIPER! equ 1 call :cai_tuy_chon "Giong doc Piper - offline" "piper-tts>=1.2.0"
if !HAS_CLONE! equ 1 call :cai_tuy_chon "Giong doc XTTSv2 - nhai giong" "coqui-tts>=0.27.5" "coqui-tts[codec]"
if !HAS_VIENEU! equ 1 call :cai_tuy_chon "Giong doc VieNeu" "vieneu==3.0.9" "neucodec>=0.0.6" "torchao==0.16.0"
if !HAS_DEMUCS! equ 1 call :cai_tuy_chon "Tach nhac nen Demucs" "demucs"
call :cai_tuy_chon "Cong cu kiem thu pytest" "pytest"

if !HAS_OCR! equ 1 (
    "%VPY%" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
    if !errorlevel! equ 0 (
        call :cai_tuy_chon "Paddle GPU cho OCR" "paddlepaddle-gpu==3.3.1" "--extra-index-url" "https://www.paddlepaddle.org.cn/packages/stable/cu126/"
    ) else (
        call :cai_tuy_chon "Paddle CPU cho OCR" "paddlepaddle==3.3.1"
    )
    where git >nul 2>&1
    if !errorlevel! equ 0 (
        call :cai_tuy_chon "videocr-PaddleOCR" "videocr @ git+https://github.com/oliverfei/videocr-PaddleOCR.git@b56af756cd2fdcdb54c79037d507aa8aec3c23c5"
    ) else (
        echo [WARNING] Khong co Git - bo qua videocr-PaddleOCR, che do OCR se khong dung duoc.
        set "CAI_THIEU=!CAI_THIEU! videocr-PaddleOCR;"
    )
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
:: Tai model tuy chon
if !HAS_WHISPER! equ 1 (
    echo [INFO] Tai model Whisper medium va PhoWhisper-small...
    "AIVoice\.venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-medium'); snapshot_download(repo_id='qbsmlabs/PhoWhisper-small')"
)

if !HAS_TAOANH! equ 1 (
    echo [INFO] Tai model tao anh lykon/dreamshaper-8...
    "AIVoice\.venv\Scripts\python.exe" -c "from huggingface_hub import snapshot_download; import os; snapshot_download(repo_id='lykon/dreamshaper-8', allow_patterns=['*.safetensors', '*.json', '*.txt'], cache_dir=os.environ.get('HF_HOME') or os.path.join('AIVoice','apps','MediaComposer','storage','models'))"
)

if !HAS_LAMNET! equ 1 (
    echo [INFO] Tai model lam net RealESRGAN...
    if not exist "AIVoice\apps\MediaComposer\models\realesrgan" mkdir "AIVoice\apps\MediaComposer\models\realesrgan" >nul 2>&1
    if not exist "AIVoice\apps\MediaComposer\models\realesrgan\RealESRGAN_x4plus_anime_6B.pth" (
        curl -L -o "AIVoice\apps\MediaComposer\models\realesrgan\RealESRGAN_x4plus_anime_6B.pth" "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
    )
    if not exist "AIVoice\apps\MediaComposer\models\realesrgan\realesr-animevideov3.pth" (
        curl -L -o "AIVoice\apps\MediaComposer\models\realesrgan\realesr-animevideov3.pth" "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth"
    )
)

if !HAS_DICHOFFLINE! equ 1 (
    where ollama >nul 2>&1
    if !errorlevel! neq 0 (
        echo [INFO] Chua co Ollama, dang tai va cai dat...
        curl -L -o OllamaSetup.exe https://ollama.com/download/OllamaSetup.exe
        start "" /wait OllamaSetup.exe /quiet
        del OllamaSetup.exe
    )
    echo [INFO] Tai model dich hy-mt2:1.8b-q4 cho Ollama (GGUF HuggingFace + Modelfile)...
    rem hy-mt2 KHONG co tren kho Ollama - "ollama pull hy-mt2:1.8b" luon loi. ollama_manager pull GGUF tu HF roi create.
    "AIVoice\.venv\Scripts\python.exe" -c "from orchestrator import ollama_manager as o; r=o.ensure_ready('hy-mt2:1.8b-q4', progress_cb=lambda m,p=-1: print(m)); print(r)"
)

:: Ghi file thanh phan
echo !COMPONENTS! > configs\thanh_phan.json
if not "!WORKSPACE!"=="" (
    "AIVoice\.venv\Scripts\python.exe" -c "import json, os; p=r'configs\global_config.json'; d=json.load(open(p, 'r', encoding='utf-8')) if os.path.exists(p) else {}; d['editor.workspace']=r'!WORKSPACE!'; json.dump(d, open(p, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)"
)

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
