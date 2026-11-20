; Inno Setup script for TrackDog (Windows). Built by build.py, which passes /DAppVersion.
; Per-user install (no administrator rights). The language picked on the first page becomes
; the language of the program (passed as --lang on the first start).

#define AppName "TrackDog"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppExe "TrackDog.exe"

[Setup]
AppId={{3F7C2B9A-5D1E-4C8B-9A6F-0E2D7B4C1A93}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=qbarteczek
AppPublisherURL=https://github.com/qbarteczek/trackdog
DefaultDirName={localappdata}\Programs\TrackDog
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ShowLanguageDialog=yes
UsePreviousLanguage=no
OutputDir=..\dist
OutputBaseFilename=TrackDog-Setup-{#AppVersion}
SetupIconFile=..\tdd\res\app.ico
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\TrackDog\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Parameters: "--lang {language}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
