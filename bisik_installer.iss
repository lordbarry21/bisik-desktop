; Inno Setup Script for Bisik
; Developed by Bari Hartanto Achmad

#define MyAppName "Bisik"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Bari Hartanto Achmad"
#define MyAppURL "https://github.com/lordbarry21/bisik-desktop"
#define MyAppExeName "Bisik.exe"

[Setup]
AppId={{D81452D3-611F-4382-9694-0E8F94D290F1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Bisik-v1.1.0-Windows-Setup
SetupIconFile=bisik.ico
UninstallDisplayIcon={app}\bisik.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
DisableDirPage=no
DisableWelcomePage=no
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Launch Bisik automatically on Windows startup"; GroupDescription: "Startup Options:"

[Files]
Source: "dist\Bisik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut - enables Windows Search indexing (search "Bisik" in Windows Start)
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\bisik.ico"; Comment: "Bisik - AI Voice Typing & Dictation for Windows"

; Desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\bisik.ico"; Comment: "Bisik - AI Voice Typing & Dictation for Windows"; Tasks: desktopicon


[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"" --startup"; Flags: uninsdeletevalue; Tasks: startupicon

[InstallDelete]
Type: files; Name: "{userstartup}\{#MyAppName}.lnk"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
