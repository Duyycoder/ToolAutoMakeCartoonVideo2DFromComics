; ============================================================================
;  Cao va Dich Video - Inno Setup script
; ============================================================================

#define MyAppName "Cao va Dich Video"
#define MyAppDirName "CaoVaDichVideo"
#define MyAppVersion "2.0.0"
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
PrivilegesRequired=lowest
DefaultDirName={userpf}\{#MyAppDirName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CaoVaDichVideo-Setup-{#MyAppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\app.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
InfoBeforeFile=huongdan.txt
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Cài đặt đầy đủ"
Name: "compact"; Description: "Gọn nhẹ (chỉ Whisper + dịch online + Edge TTS)"
Name: "custom"; Description: "Tuỳ chọn"; Flags: iscustom

[Components]
Name: "loi"; Description: "Lõi ứng dụng + Python + Whisper + Webview2 (~2GB)"; Types: full compact custom; Flags: fixed
Name: "gpu"; Description: "Tăng tốc NVIDIA CUDA (Bỏ chọn nếu không có card NVIDIA)"; Types: full
Name: "ocr"; Description: "Nhận diện phụ đề cứng OCR (PaddleOCR) (~500MB)"; Types: full
Name: "tts"; Description: "Giọng đọc (TTS)"; Types: full custom
Name: "tts\piper"; Description: "Piper TTS (offline nhanh) (~50MB)"; Types: full
Name: "tts\kokoro"; Description: "Kokoro TTS (tiếng Việt) (~200MB)"; Types: full
Name: "tts\vieneu"; Description: "VieNeu TTS (~300MB)"; Types: full
Name: "tts\clone"; Description: "Nhái giọng XTTSv2 (Cần GPU/RAM cao) (~5.2GB)"; Types: full
Name: "demucs"; Description: "Tách giọng/nhạc nền Demucs (~100MB)"; Types: full
Name: "lamnet"; Description: "Làm nét video/upscale RealESRGAN (~100MB)"; Types: full
Name: "dich_offline"; Description: "Dịch offline Ollama + model dịch chuyên dụng hy-mt2 Q4 (~1.1GB)"; Types: full
Name: "whisper"; Description: "Whisper Medium & PhoWhisper (~2.5GB)"; Types: full
Name: "taoanh"; Description: "Tạo ảnh AI Dreamshaper (Cần GPU >= 4GB) (~2GB)"; Types: full
Name: "minhhoa"; Description: "Minh họa video Pexels (Cần API Key miễn phí)"; Types: full

[Tasks]
Name: "desktopicon"; Description: "Tao bieu tuong ngoai man hinh Desktop"; GroupDescription: "Bieu tuong:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; \
    Flags: recursesubdirs createallsubdirs; \
    Excludes: ".git,.gitmodules,.gitattributes,.github,.claude,.agents,__pycache__,*.pyc,.pytest_cache,.ruff_cache,.mypy_cache,.venv,venv,scratch,logs,cookies.json,*cookies*,*.key,*.pem,.env,.env.*,Thumbs.db,desktop.ini,*.log,\installer,\storage,\models,\configs\global_config.json,\AIVoice\models,\AIVoice\storage,\AIVoice\data,\AIVoice\third_party,\AIVoice\apps\storage,\AIVoice\apps\MediaComposer\models,\AIVoice\apps\MediaComposer\storage,\AIVoice\MediaComposer\models,\AIVoice\MediaComposer\storage,\docs\agy,\docs\HANDOFF-*,\docs\PLAN-*,\tests"
Source: "app.ico"; DestDir: "{app}"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\run.bat"; \
    WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; \
    Comment: "Mo cong cu Cao va Dich Video"
Name: "{autoprograms}\{#MyAppName} - Cai dat moi truong"; Filename: "{app}\setup.bat"; \
    WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; \
    Comment: "Chay lai buoc cai Python/thu vien/model neu can"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\run.bat"; \
    WorkingDir: "{app}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "HF_HOME"; ValueData: "{code:GetModelsDir}\.cache\huggingface"; Flags: uninsdeletevalue; Check: IsModelsDirChanged and BienTrong('HF_HOME')
Root: HKCU; Subkey: "Environment"; ValueType: string; ValueName: "OLLAMA_MODELS"; ValueData: "{code:GetModelsDir}\ollama"; Flags: uninsdeletevalue; Check: IsModelsDirChangedOrDichOffline and BienTrong('OLLAMA_MODELS')

[Run]
Filename: "{cmd}"; \
    Parameters: "/c if not exist ""{app}\configs\global_config.json"" copy ""{app}\configs\config.example.json"" ""{app}\configs\global_config.json"""; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Dang tao file cau hinh mac dinh..."
Filename: "{app}\setup.bat"; WorkingDir: "{app}"; \
    Parameters: """--tp={code:GetSelectedComponents}"" --workspace=""{code:GetWorkspaceDir}"""; \
    Description: "Cai moi truong AI ngay (tai Python + thu vien + model, can Internet, 30-60 phut)"; \
    Flags: postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\AIVoice\.venv"
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\AIVoice\models"
Type: filesandordirs; Name: "{app}\AIVoice\storage"
Type: filesandordirs; Name: "{app}\AIVoice\data"
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\AIVoice\third_party"
Type: files; Name: "{app}\configs\global_config.json"

[Code]
var
  WorkspacePage: TInputDirWizardPage;
  WorkspaceDir: String;
  ModelsDir: String;

procedure InitializeWizard;
begin
  WorkspacePage := CreateInputDirPage(wpSelectComponents,
    'Chọn nơi làm việc và nơi lưu trữ Model', 'Chọn thư mục để lưu dự án và các model AI.',
    'Thư mục làm việc (Nơi lưu các dự án video):'#13#10 +
    'Khuyên dùng thư mục ngoài C:\ để tránh lỗi quyền.',
    False, 'New Folder');

  WorkspacePage.Add('Thư mục làm việc (Workspace):');
  // {userprofile} không phải hằng của Inno (bộ cài từng chết ngay khi mở) — đọc biến môi trường.
  WorkspacePage.Values[0] := AddBackslash(GetEnv('USERPROFILE')) + 'CaoDichVideo';

  WorkspacePage.Add('Thư mục lưu trữ Model AI (HF_HOME, OLLAMA_MODELS):');
  // {app} chưa có giá trị lúc này — mặc định đặt ở CurPageChanged / ThuMucModel.
  WorkspacePage.Values[1] := '';
end;

// Thư mục model mặc định = <thư mục cài>\models (chỉ gọi được SAU khi đã chọn thư mục cài).
function ThuMucModelMacDinh: String;
begin
  Result := AddBackslash(WizardDirValue) + 'models';
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = WorkspacePage.ID) and (WorkspacePage.Values[1] = '') then
    WorkspacePage.Values[1] := ThuMucModelMacDinh;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = WorkspacePage.ID then
  begin
    WorkspaceDir := WorkspacePage.Values[0];
    ModelsDir := WorkspacePage.Values[1];
    
    if (Pos(LowerCase(ExpandConstant('{userdocs}')), LowerCase(WorkspaceDir)) > 0) or
       (Pos(LowerCase(AddBackslash(GetEnv('USERPROFILE')) + 'Videos'), LowerCase(WorkspaceDir)) > 0) then
    begin
      if MsgBox('CẢNH BÁO: Thư mục bạn chọn nằm trong Documents hoặc Videos.'#13#10 +
                'Tính năng Controlled Folder Access (Ransomware Protection) của Windows Defender có thể chặn ứng dụng ghi file, gây lỗi.'#13#10#13#10 +
                'Khuyên dùng thư mục như C:\CaoDichVideo hoặc ổ D:\.'#13#10#13#10 +
                'Bạn có chắc chắn muốn dùng thư mục này không?', mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
      end;
    end;
  end;
end;

// Cài im lặng không hiện trang chọn chỗ lưu → biến rỗng; dùng giá trị trên trang (đã có mặc định) hoặc mặc định.
function GetWorkspaceDir(Param: String): String;
begin
  Result := WorkspaceDir;
  if Result = '' then Result := WorkspacePage.Values[0];
end;

function GetModelsDir(Param: String): String;
begin
  Result := ModelsDir;
  if Result = '' then Result := WorkspacePage.Values[1];
  if Result = '' then Result := ThuMucModelMacDinh;
end;

function IsModelsDirChanged: Boolean;
begin
  Result := CompareText(RemoveBackslash(GetModelsDir('')), RemoveBackslash(ThuMucModelMacDinh)) <> 0;
end;

// CHỈ đặt biến môi trường khi máy CHƯA có: máy đã có OLLAMA_MODELS (model Ollama ở ổ khác) mà ghi đè thì Ollama mất model,
// và gỡ cài (uninsdeletevalue) còn xoá luôn biến gốc (cài thử 29/09 đã làm mất OLLAMA_MODELS của máy dev).
function BienTrong(Ten: String): Boolean;
begin
  Result := GetEnv(Ten) = '';
end;

function IsModelsDirChangedOrDichOffline: Boolean;
begin
  Result := IsModelsDirChanged or WizardIsComponentSelected('dich_offline');
end;

function GetSelectedComponents(Param: String): String;
var
  S: String;
begin
  S := '';
  if WizardIsComponentSelected('loi') then S := S + 'loi,';
  if WizardIsComponentSelected('gpu') then S := S + 'gpu,';
  if WizardIsComponentSelected('ocr') then S := S + 'ocr,';
  if WizardIsComponentSelected('tts\piper') then S := S + 'piper,';
  if WizardIsComponentSelected('tts\kokoro') then S := S + 'kokoro,';
  if WizardIsComponentSelected('tts\vieneu') then S := S + 'vieneu,';
  if WizardIsComponentSelected('tts\clone') then S := S + 'clone,';
  if WizardIsComponentSelected('demucs') then S := S + 'demucs,';
  if WizardIsComponentSelected('lamnet') then S := S + 'lamnet,';
  if WizardIsComponentSelected('dich_offline') then S := S + 'dich_offline,';
  if WizardIsComponentSelected('whisper') then S := S + 'whisper,';
  if WizardIsComponentSelected('taoanh') then S := S + 'taoanh,';
  if WizardIsComponentSelected('minhhoa') then S := S + 'minhhoa,';
  
  if Length(S) > 0 then
    SetLength(S, Length(S) - 1);
  Result := S;
end;
