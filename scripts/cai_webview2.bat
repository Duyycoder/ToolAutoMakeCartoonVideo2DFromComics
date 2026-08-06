@echo off
setlocal enabledelayedexpansion

rem ======================================================================
rem  Bao dam co WebView2 Runtime - thu vien Windows dung de ve cua so app.
rem
rem  Thieu no thi orchestrator/desktop.py khong tao duoc cua so va tu lui ve
rem  mo trinh duyet. Nguoi dung thay "hien ban web chu khong phai app".
rem  Windows 11 thuong co san; Windows 10 doi cu thi khong.
rem
rem  Goi tu setup.bat va CAP-NHAT.bat. Luon tra ve 0 - thieu WebView2 chi lam
rem  giao dien chay trong trinh duyet chu khong chan ung dung hoat dong.
rem ======================================================================

set "GUID={F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
set "CO_ROI="

rem Runtime dang ky o 1 trong 3 cho tuy ban cai may/nguoi dung
for %%K in (
    "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\%GUID%"
    "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\%GUID%"
    "HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\%GUID%"
) do (
    for /f "tokens=3" %%V in ('reg query %%K /v pv 2^>nul ^| find "pv"') do (
        rem pv = 0.0.0.0 nghia la co khoa nhung chua cai that
        if not "%%V"=="0.0.0.0" set "CO_ROI=%%V"
    )
)

if defined CO_ROI (
    echo [OK] Da co WebView2 Runtime - phien ban !CO_ROI!
    exit /b 0
)

echo [INFO] Chua co WebView2 Runtime - dang tai va cai dat...
echo        Day la thu vien Windows de mo cua so ung dung.

set "BOOT=%TEMP%\MicrosoftEdgeWebview2Setup.exe"
curl -L -o "%BOOT%" https://go.microsoft.com/fwlink/p/?LinkId=2124703
if %errorlevel% neq 0 (
    echo [CANH BAO] Tai WebView2 that bai - ung dung se hien trong trinh duyet.
    echo            Cai tay tai: https://developer.microsoft.com/microsoft-edge/webview2/
    exit /b 0
)

"%BOOT%" /silent /install
del "%BOOT%" >nul 2>&1

rem Kiem tra lai sau khi cai
set "CO_ROI="
for %%K in (
    "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\%GUID%"
    "HKLM\SOFTWARE\Microsoft\EdgeUpdate\Clients\%GUID%"
    "HKCU\SOFTWARE\Microsoft\EdgeUpdate\Clients\%GUID%"
) do (
    for /f "tokens=3" %%V in ('reg query %%K /v pv 2^>nul ^| find "pv"') do (
        if not "%%V"=="0.0.0.0" set "CO_ROI=%%V"
    )
)

if defined CO_ROI (
    echo [OK] Cai WebView2 Runtime thanh cong - phien ban !CO_ROI!
) else (
    echo [CANH BAO] Chua xac nhan duoc WebView2 - ung dung se hien trong trinh duyet.
    echo            Cai tay tai: https://developer.microsoft.com/microsoft-edge/webview2/
)
exit /b 0
