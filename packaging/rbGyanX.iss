; rbGyanX 1.0 — Inno Setup installer script
; Build: ISCC.exe packaging\rbGyanX.iss /DMyAppSource="full\path\to\dist\rbGyanX"

#ifndef MyAppSource
  #define MyAppSource "..\dist\rbGyanX"
#endif

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#ifndef MyAppName
  #define MyAppName "rbGyanX"
#endif

#define MyAppPublisher "rbGyanX Team"
#define MyAppURL "https://github.com/kalyan2031990/rbGyanX_cdss"
#define MyAppExeName "rbGyanX.exe"

[Setup]
; Fixed AppId — keep unchanged across releases so upgrades replace the same install
AppId={{A7E4B920-3F1C-4D8A-9E62-5C0D3F4A5B60}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
LicenseFile=installer_license.txt
InfoBeforeFile=..\docs\RBGYANX_1.0_DESKTOP.md
OutputDir=..\dist
OutputBaseFilename=rbGyanX-{#MyAppVersion}-full-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Radiobiological CDSS
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller one-folder distribution + engine_bundle
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "rbGyanX Clinical Decision Support"
Name: "{group}\User guide"; Filename: "{app}\RBGYANX_1.0_DESKTOP.md"; Comment: "Quick start"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked
