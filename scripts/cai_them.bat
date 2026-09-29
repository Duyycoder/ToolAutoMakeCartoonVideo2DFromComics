@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  CAI THEM THANH PHAN - Cao ^& Dich Video
echo ============================================================
echo.

set "COMPS=loi"

set /p gpu="Co GPU NVIDIA khong? (Y/N) [Mac dinh: Y]: "
if /i not "!gpu!"=="n" set "COMPS=!COMPS!,gpu"

set /p ocr="Cai dat nhan dien phu de cung OCR (PaddleOCR)? (Y/N) [Mac dinh: Y]: "
if /i not "!ocr!"=="n" set "COMPS=!COMPS!,ocr"

set /p piper="Cai dat Piper TTS (offline nhanh)? (Y/N) [Mac dinh: Y]: "
if /i not "!piper!"=="n" set "COMPS=!COMPS!,piper"

set /p kokoro="Cai dat Kokoro TTS (tieng Viet)? (Y/N) [Mac dinh: Y]: "
if /i not "!kokoro!"=="n" set "COMPS=!COMPS!,kokoro"

set /p vieneu="Cai dat VieNeu TTS? (Y/N) [Mac dinh: Y]: "
if /i not "!vieneu!"=="n" set "COMPS=!COMPS!,vieneu"

set /p clone="Cai dat nhai giong XTTSv2 (Can GPU/RAM cao, tai them 5.2GB)? (Y/N) [Mac dinh: N]: "
if /i "!clone!"=="y" set "COMPS=!COMPS!,clone"

set /p demucs="Cai dat tach nhac nen Demucs? (Y/N) [Mac dinh: Y]: "
if /i not "!demucs!"=="n" set "COMPS=!COMPS!,demucs"

set /p lamnet="Cai dat lam net video (RealESRGAN)? (Y/N) [Mac dinh: Y]: "
if /i not "!lamnet!"=="n" set "COMPS=!COMPS!,lamnet"

set /p dichoffline="Cai dat dich offline (Ollama + model hy-mt2)? (Y/N) [Mac dinh: Y]: "
if /i not "!dichoffline!"=="n" set "COMPS=!COMPS!,dich_offline"

set /p whisper="Cai dat Whisper va PhoWhisper? (Y/N) [Mac dinh: Y]: "
if /i not "!whisper!"=="n" set "COMPS=!COMPS!,whisper"

set /p taoanh="Cai dat tao anh AI Dreamshaper? (Y/N) [Mac dinh: Y]: "
if /i not "!taoanh!"=="n" set "COMPS=!COMPS!,taoanh"

set /p minhhoa="Cai dat minh hoa Pexels? (Y/N) [Mac dinh: Y]: "
if /i not "!minhhoa!"=="n" set "COMPS=!COMPS!,minhhoa"

echo.
echo Dang goi setup.bat voi cac thanh phan: !COMPS!
echo.
:: Boc ngoac kep: cmd.exe coi dau phay la dau ngan tham so, --tp=a,b se bi cat thanh nhieu tham so.
call "%~dp0..\setup.bat" "--tp=!COMPS!"

echo.
echo Da hoan tat!
pause
