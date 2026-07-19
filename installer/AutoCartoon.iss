; ============================================================================
;  AutoCartoon Video Maker - Inno Setup script
;  Build:  installer\build_installer.bat   (can cai Inno Setup 6 tren may build)
;  Output: installer\Output\AutoCartoonVideoMaker-Setup-<version>.exe
;
;  Bo cai kieu "web installer": chi dong goi MA NGUON (~vai chuc MB).
;  Buoc [Run] cuoi se chay setup.bat de tai Python 3.11 + thu vien AI + model
;  (can Internet; may trang khong can cai san Python hay Git).
; ============================================================================

#define MyAppName "AutoCartoon Video Maker"
#define MyAppDirName "AutoCartoonVideoMaker"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Duyycoder"
#define MyAppURL "https://github.com/Duyycoder/ToolAutoMakeCartoonVideo2DFromComics"
#define SourceDir ".."

[Setup]
AppId={{F1351DC0-C1A7-4518-8ABD-512C6C60FD29}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
; Cai theo user (khong can quyen Admin) vao %LocalAppData%\Programs\...
; Ly do: app tu ghi vao thu muc cai dat (venv, storage, logs, config) nen
; KHONG duoc nam trong Program Files; duong dan co chu "Programs" khong dau cach.
PrivilegesRequired=lowest
DefaultDirName={userpf}\{#MyAppDirName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=AutoCartoonVideoMaker-Setup-{#MyAppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile=huongdan.txt
; Nguoi dung co the doi thu muc cai
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tao bieu tuong ngoai man hinh Desktop"; GroupDescription: "Bieu tuong:"

[Files]
; --- Ma nguon du an (bao gom ca 2 submodule da co san file) ---
; Loai tru: rac build/cache, venv, model AI, du lieu nguoi dung va MOI BI MAT
; (global_config.json, cookies.json, .env, *.key). Danh sach nay bam theo
; .gitignore cua repo: payload xap xi ket qua "git clone --recursive".
Source: "{#SourceDir}\*"; DestDir: "{app}"; \
    Flags: recursesubdirs createallsubdirs; \
    Excludes: ".git,.gitmodules,.gitattributes,.github,.claude,.agents,__pycache__,*.pyc,.pytest_cache,.ruff_cache,.mypy_cache,.venv,venv,scratch,logs,cookies.json,*cookies*,*.key,*.pem,.env,.env.*,Thumbs.db,desktop.ini,*.log,\installer,\storage,\models,\configs\global_config.json,\AIVoice\models,\AIVoice\storage,\AIVoice\data,\AIVoice\third_party,\AIVoice\apps\storage,\AIVoice\apps\MediaComposer\models,\AIVoice\apps\MediaComposer\storage,\AIVoice\MediaComposer\models,\AIVoice\MediaComposer\storage,\toolCaoTruyen\truyen_tai_ve,\toolCaoTruyen\test_output,\toolCaoTruyen\Gemini-API\models"
; --- Icon rieng cho shortcut ---
Source: "app.ico"; DestDir: "{app}"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\run.bat"; \
    WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; \
    Comment: "Mo AutoCartoon Video Maker"
Name: "{autoprograms}\{#MyAppName} - Cai dat moi truong"; Filename: "{app}\setup.bat"; \
    WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; \
    Comment: "Chay lai buoc cai Python/thu vien/model neu can"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\run.bat"; \
    WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Run]
; Tao san global_config.json tu file mau neu chua co (de app chay duoc ngay)
Filename: "{cmd}"; \
    Parameters: "/c if not exist ""{app}\configs\global_config.json"" copy ""{app}\configs\config.example.json"" ""{app}\configs\global_config.json"""; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Dang tao file cau hinh mac dinh..."
; Buoc cai moi truong: BAT BUOC lan dau, nguoi dung thay console de theo doi
Filename: "{app}\setup.bat"; WorkingDir: "{app}"; \
    Description: "Cai moi truong AI ngay (tai Python + thu vien + model, can Internet, 30-60 phut)"; \
    Flags: postinstall skipifsilent

[UninstallDelete]
; Xoa nhung thu setup.bat sinh ra sau khi cai (khong nam trong danh sach file
; cua installer). GIU LAI {app}\storage - truyen va video nguoi dung da tao.
Type: filesandordirs; Name: "{app}\AIVoice\.venv"
Type: filesandordirs; Name: "{app}\toolCaoTruyen\.venv"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\AIVoice\models"
Type: filesandordirs; Name: "{app}\AIVoice\storage"
Type: filesandordirs; Name: "{app}\AIVoice\data"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\AIVoice\third_party"
; File config sinh boi buoc [Run] sau cai (khong nam trong file list cua installer)
Type: files; Name: "{app}\configs\global_config.json"
