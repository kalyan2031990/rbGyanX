; rbGyanX 1.0 (Qt6 edition) — Inno Setup installer script
; Build: ISCC.exe packaging\rbGyanX-qt.iss /DMyAppSource="full\path\to\build_qt\dist\rbGyanX-Qt"
;
; Separate from packaging\rbGyanX.iss (the Tkinter build): distinct AppId, exe and output
; filename, so the Qt edition installs and upgrades independently.

#ifndef MyAppSource
  #define MyAppSource "..\build_qt\dist\rbGyanX-Qt"
#endif

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#ifndef MyAppName
  #define MyAppName "rbGyanX"
#endif

#define MyAppPublisher "rbGyanX Team"
#define MyAppURL "https://github.com/kalyan2031990/rbGyanX"
#define MyAppExeName "rbGyanX-Qt.exe"

[Setup]
; Fixed AppId — DIFFERENT from the Tkinter installer so the two editions never collide.
AppId={{B8F5CA31-4A2D-4E9B-AF73-6D1E4A5B6C71}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} (Qt)
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}-Qt
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
LicenseFile=installer_license.txt
InfoBeforeFile=..\docs\RBGYANX_1.0_DESKTOP.md
OutputDir=..\build_qt\dist
OutputBaseFilename=rbGyanX-{#MyAppVersion}-Qt-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#MyAppName} {#MyAppVersion} (Qt)
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Radiobiological CDSS (Qt6)
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller one-folder distribution of the Qt app (includes QtWebEngine + engine).
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Ship the quick-start guide so the Start-menu "User guide" shortcut resolves.
Source: "..\docs\RBGYANX_1.0_DESKTOP.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName} (Qt)"; Filename: "{app}\{#MyAppExeName}"; Comment: "rbGyanX Clinical Decision Support (Qt6)"
Name: "{group}\User guide"; Filename: "{app}\RBGYANX_1.0_DESKTOP.md"; Comment: "Quick start"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName} (Qt)"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked
