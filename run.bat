@echo off
setlocal
set PYTHONUTF8=1
pushd "%~dp0"

:: May moi vua "git clone" ve chua co moi truong -> tu chay setup.bat luon,
:: de nguoi dung chi can nhay dup MOT file duy nhat la run.bat.
if not exist "AIVoice\.venv\Scripts\python.exe" goto :need_setup
goto :ready

:need_setup
echo ============================================================
echo  Lan dau chay tren may nay - dang cai dat tu dong.
echo  Viec nay can Internet va co the mat 30-60 phut.
echo  Cu de cua so nay chay, khong tat giua chung.
echo ============================================================
echo.
:: Bao cho setup.bat biet la dang duoc run.bat goi: khoi dung lai cho bam phim
:: o cuoi, cai xong la mo app luon.
set CALLED_FROM_RUN=1
call "%~dp0setup.bat"
if errorlevel 1 goto :setup_failed
if not exist "AIVoice\.venv\Scripts\python.exe" goto :setup_failed
echo.
echo [OK] Cai dat xong. Dang mo ung dung...
echo.

:ready
:: Set PYTHONPATH so that orchestrator modules can be resolved
set PYTHONPATH=%CD%
:: Log tieng Viet tren console Windows can UTF-8
set PYTHONIOENCODING=utf-8

:: Kiem tra nhanh thu vien toi thieu TRUOC khi mo bang pythonw.
:: pythonw khong co cua so console: thieu thu vien la app chet ngay tu luc
:: import, nguoi dung nhay dup xong khong thay gi va cung khong co log de tra.
"AIVoice\.venv\Scripts\python.exe" -c "import fastapi, uvicorn, webview" >nul 2>&1
if errorlevel 1 goto :missing_libs

:: QUAN TRONG: sau khi di chuyen thu muc du an, cac file .exe trong venv
:: (uvicorn.exe, pip.exe...) deu HONG vi chua duong dan tuyet doi cu.
:: Chi python.exe/pythonw.exe con chay dung -> luon goi module qua "-m ..."
::
:: orchestrator.desktop = cua so ung dung WebView2 + uvicorn :8100.
:: Dong cua so app se tu diet het tien trinh con.

if /I "%~1"=="debug" goto :debug

:: Che do thuong: khong hien console nao - log ghi vao logs\app.log
start "" "AIVoice\.venv\Scripts\pythonw.exe" -m orchestrator.desktop
exit /b 0

:debug
echo ============================================================
echo  Cao ^& Dich Video - DEBUG MODE (log hien truc tiep)
echo ============================================================
"AIVoice\.venv\Scripts\python.exe" -m orchestrator.desktop
pause
exit /b 0

:setup_failed
echo.
echo [LOI] Cai dat chua hoan tat - xem thong bao loi o tren.
echo       Sua xong thi nhay dup lai run.bat, no se cai tiep phan con thieu.
pause
exit /b 1

:missing_libs
echo ============================================================
echo  [LOI] Moi truong Python thieu thu vien - lan cai truoc chua xong.
echo ============================================================
echo  Cach sua: nhay dup setup.bat de cai bu, roi mo lai run.bat.
echo.
echo  Chi tiet loi:
"AIVoice\.venv\Scripts\python.exe" -c "import fastapi, uvicorn, webview"
echo.
pause
exit /b 1
