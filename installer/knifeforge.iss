; Installer of the desktop build. Built by CI (.github/workflows/ci.yml, job "windows"):
;   iscc /DAppVersion=0.9.0 /DSourceDir="..\backend\dist\KnifeForge Pro" installer\knifeforge.iss
; Installs for the current user only (no administrator rights), in
; %LOCALAPPDATA%\Programs\KnifeForge Pro. The workshop's data lives elsewhere
; (%LOCALAPPDATA%\KnifeForge Pro) and is never removed by an update or an uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\backend\dist\KnifeForge Pro"
#endif

[Setup]
AppId={{6E2B7C1A-4F4D-4C61-9A1E-5B0C2D7F3A10}
AppName=KnifeForge Pro
AppVersion={#AppVersion}
AppVerName=KnifeForge Pro {#AppVersion}
AppPublisher=Philogone Quénette
DefaultDirName={localappdata}\Programs\KnifeForge Pro
DefaultGroupName=KnifeForge Pro
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=KnifeForge-Pro-{#AppVersion}-installation
SetupIconFile=..\backend\desktop\icon.ico
UninstallDisplayIcon={app}\KnifeForge Pro.exe
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; a running KnifeForge is closed before files are replaced
CloseApplications=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\KnifeForge Pro"; Filename: "{app}\KnifeForge Pro.exe"
Name: "{group}\Dossier des données KnifeForge"; Filename: "{localappdata}\KnifeForge Pro"
Name: "{autodesktop}\KnifeForge Pro"; Filename: "{app}\KnifeForge Pro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KnifeForge Pro.exe"; Description: "{cm:LaunchProgram,KnifeForge Pro}"; Flags: nowait postinstall skipifsilent
