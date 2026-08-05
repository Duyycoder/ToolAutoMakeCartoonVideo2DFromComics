@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1

rem Tham so 1 = thu muc du an. Chi co khi dang chay ban sao trong TEMP.
if not "%~1"=="" goto :chay_that

rem ------------------------------------------------------------------
rem Dang chay TRUC TIEP trong thu muc du an. Tu nhan ban sang TEMP roi
rem chuyen quyen dieu khien sang do.
rem
rem Ly do: buoc cap nhat ben duoi se GHI DE chinh file nay (no cung nam
rem trong repo). cmd.exe doc file .bat theo vi tri byte, file bi thay
rem giua chung thi no nhay lung tung sang dong khac.
rem ------------------------------------------------------------------
copy /y "%~f0" "%TEMP%\CAP-NHAT-runner.bat" >nul 2>&1
if exist "%TEMP%\CAP-NHAT-runner.bat" goto :chuyen_sang_temp

rem Khong chep duoc thi chay tai cho - van hoat dong, chi kem an toan hon
set "PROJ=%~dp0"
goto :bat_dau

:chuyen_sang_temp
rem Goi KHONG kem "call" -> chuyen han quyen dieu khien, file nay duoc dong lai
"%TEMP%\CAP-NHAT-runner.bat" "%~dp0"
exit /b %errorlevel%

:chay_that
set "PROJ=%~1"

:bat_dau
pushd "%PROJ%"

echo ============================================================
echo   CAP NHAT PHAN MEM LEN BAN MOI NHAT
echo ============================================================
echo.

:: 1. Phai co Git thi moi tai ban moi ve duoc
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] May nay chua cai Git.
    echo       Tai va cai tai: https://git-scm.com/download/win
    echo       Cai xong chay lai file nay.
    echo.
    pause
    exit /b 1
)

:: 2. Phai dang dung trong thu muc du an
if not exist ".git" (
    echo [LOI] File nay dang nam ngoai thu muc du an.
    echo       Hay chep CAP-NHAT.bat vao thu muc
    echo       ToolAutoMakeCartoonVideo2DFromComics roi chay lai.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "NHANH=%%b"
if not defined NHANH set "NHANH=?"

echo [1/5] Ban dang dung phien ban:
git log -1 --pretty=format:"      %%h  %%ad  %%s" --date=short
echo.
echo       Nhanh hien tai: !NHANH!
echo.

echo [2/5] Dang tai ban moi tu GitHub...
git fetch origin --prune
if %errorlevel% neq 0 (
    echo.
    echo [LOI] Khong tai duoc. Kiem tra lai ket noi mang roi chay lai file nay.
    echo.
    pause
    exit /b 1
)
echo.

rem ------------------------------------------------------------------
rem Do rui ro TRUOC khi ghi de.
rem
rem Script nay von danh cho nguoi dung cuoi: reset thang ve main la dung
rem y do. Nhung neu ai do dang LAM VIEC tren nhanh khac, hoac dang co
rem commit chua day len GitHub, thi buoc reset ben duoi se keo ho ra khoi
rem nhanh dang lam ma khong noi gi. Da xay ra that.
rem ------------------------------------------------------------------
set "RUI_RO="
set "SO_COMMIT_CHUA_DAY=0"
set "SO_FILE_SUA=0"

for /f %%i in ('git status --porcelain 2^>nul ^| find /c /v ""') do set "SO_FILE_SUA=%%i"
for /f %%i in ('git rev-list --count origin/main..HEAD 2^>nul') do set "SO_COMMIT_CHUA_DAY=%%i"

if /I not "!NHANH!"=="main" set "RUI_RO=1"
if not "!SO_FILE_SUA!"=="0" set "RUI_RO=1"
if not "!SO_COMMIT_CHUA_DAY!"=="0" set "RUI_RO=1"

:: 3. Canh bao truoc khi ghi de - day la thao tac khong hoan tac duoc
echo ------------------------------------------------------------
echo  LUU Y TRUOC KHI CAP NHAT
echo ------------------------------------------------------------
echo  SE BI GHI DE:  moi chinh sua tay vao MA NGUON tren may nay
echo  DUOC GIU NGUYEN: truyen va video da tao  (thu muc storage)
echo                   file cau hinh + API key (configs)
echo                   thu vien va model AI da tai ve
echo ------------------------------------------------------------

if defined RUI_RO (
    echo.
    echo  [CANH BAO] MAY NAY DANG CO CONG VIEC DANG DO
    if /I not "!NHANH!"=="main" echo      - Dang o nhanh "!NHANH!", cap nhat se chuyen ban ve "main"
    if not "!SO_FILE_SUA!"=="0" echo      - Co !SO_FILE_SUA! file dang sua chua commit, se bi xoa sach
    if not "!SO_COMMIT_CHUA_DAY!"=="0" echo      - Co !SO_COMMIT_CHUA_DAY! commit chua day len GitHub
    echo.
    echo      Neu ban dang lap trinh: thoat ra, commit va push truoc da.
    echo      Cac commit se duoc sao luu vao mot nhanh rieng truoc khi ghi de.
    echo ------------------------------------------------------------
)

echo.
set CONFIRM=
set /p CONFIRM="Go chu Y roi bam Enter de cap nhat (bam Enter khong de thoat): "
if /I not "!CONFIRM!"=="Y" (
    echo.
    echo Da huy. Khong co gi thay doi.
    echo.
    pause
    exit /b 0
)
echo.

rem Sao luu truoc khi ghi de. Nhanh sao luu la cuu canh duy nhat cho commit
rem chua push - reset --hard ben duoi khong the hoan tac duoc.
if not "!SO_COMMIT_CHUA_DAY!"=="0" (
    for /f "tokens=1-3 delims=/: " %%a in ("%DATE% %TIME%") do set "DAU_THOI_GIAN=%%a%%b%%c"
    set "NHANH_SAO_LUU=sao-luu/truoc-cap-nhat-!RANDOM!"
    git branch "!NHANH_SAO_LUU!" HEAD >nul 2>&1
    if !errorlevel! equ 0 (
        echo [i] Da sao luu !SO_COMMIT_CHUA_DAY! commit vao nhanh: !NHANH_SAO_LUU!
        echo     Lay lai bang:  git checkout !NHANH_SAO_LUU!
        echo.
    )
)

echo [3/5] Dang chuyen sang ban chinh thuc - nhanh main...
rem -f  : ghi de ca file nguoi dung tu them vao ma ban moi cung co
rem       (vi du chinh CAP-NHAT.bat vua tai ve o Buoc 3 cua huong dan -
rem        khong co -f thi git tu choi va bao "would be overwritten")
rem -B  : tao moi hoac dat lai nhanh main bam thang vao ban tren GitHub,
rem       chay dung ca khi may dang o detached HEAD hay nhanh khac
git checkout -f -B main origin/main
if %errorlevel% neq 0 (
    echo [LOI] Khong chuyen duoc sang nhanh main.
    pause
    exit /b 1
)
git reset --hard origin/main
if %errorlevel% neq 0 (
    echo [LOI] Khong cap nhat duoc ma nguon.
    pause
    exit /b 1
)
echo.

echo [4/5] Dang cap nhat 2 bo phan di kem - AIVoice va toolCaoTruyen...
rem sync: dia chi tai ve co the da doi o ban moi
git submodule sync --recursive >nul 2>&1
rem --force: ghi de ca khi ban cu de lai file thua trong 2 thu muc nay
git submodule update --init --recursive --force
if %errorlevel% neq 0 (
    echo.
    echo [CANH BAO] Mot phan di kem chua cap nhat xong. Thu chay lai file nay.
    echo            Neu van loi, xem muc "Khi gap truc trac" trong huong dan.
    echo.
    pause
    exit /b 1
)
echo.

echo [5/5] Da cap nhat xong. Phien ban moi:
git log -1 --pretty=format:"      %%h  %%ad  %%s" --date=short
echo.
echo.
echo ============================================================
echo   XONG. Dang mo phan mem...
echo   Lan dau sau khi cap nhat co the cho lau hon binh thuong
echo   vi phan mem tu tai them phan con thieu.
echo ============================================================
echo.

call "%PROJ%run.bat"
exit /b 0
