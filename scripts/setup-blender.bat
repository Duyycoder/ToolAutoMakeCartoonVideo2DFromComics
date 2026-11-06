@echo off
:: Tai Blender 4.2 LTS ban portable (khong can cai) vao tools\blender\ cho cac tinh nang:
:: Bo tron canh, Lam luoi deu, Sua loi de in 3D, Render dep (Cycles). Tai ~383 MB, giai nen ~1 GB.
:: Phien ban + SHA256 ghim theo trang chinh thuc download.blender.org (file tai ve bi hong/bi trao -> dung lai).
setlocal
pushd "%~dp0.."
set "BL_VER=4.2.23"
set "BL_SHA256=82e791475779a7342424a480bdde9a20b43710da9264c60346125aa16cd910cb"
set "BL_ZIP=blender-%BL_VER%-windows-x64.zip"
set "BL_URL=https://download.blender.org/release/Blender4.2/%BL_ZIP%"

if exist "tools\blender\blender-%BL_VER%-windows-x64\blender.exe" (
    echo [OK] Da co Blender %BL_VER%.
    goto :done
)
if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua chay setup.bat - hay chay setup.bat truoc.
    goto :fail
)
mkdir "tools\blender" 2>nul
echo [INFO] Dang tai Blender %BL_VER% (~383 MB)...
curl -L --fail --retry 3 -o "tools\blender\%BL_ZIP%" "%BL_URL%" || goto :fail

echo [INFO] Kiem tra SHA256...
".venv\Scripts\python.exe" -c "import hashlib,sys; h=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(); sys.exit(0 if h==sys.argv[2] else 1)" "tools\blender\%BL_ZIP%" %BL_SHA256%
if errorlevel 1 (
    echo [LOI] File tai ve khong dung SHA256 - da xoa. Hay chay lai.
    del "tools\blender\%BL_ZIP%"
    goto :fail
)
echo [INFO] Dang giai nen...
tar -xf "tools\blender\%BL_ZIP%" -C "tools\blender" || goto :fail
del "tools\blender\%BL_ZIP%"

:done
echo [OK] Blender san sang. Mo Easy3D: muc "Sua hinh" va "Xuat anh" se dung duoc tinh nang Blender.
popd
exit /b 0

:fail
echo [LOI] Cai Blender that bai - xem thong bao phia tren.
if not defined NON_INTERACTIVE pause
popd
exit /b 1
