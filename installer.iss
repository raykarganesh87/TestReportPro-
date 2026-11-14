; Inno Setup script - builds LabReportPro_Setup.exe (a normal Windows installer with an uninstall entry)
#define MyAppName "LabReport Pro"
#define MyAppVersion "3.1"
#define MyAppExe "LabReportPro.exe"

[Setup]
AppId={{8F3A5C21-7B64-4D0E-9A1B-3C5D6E7F8A90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Mr. Ganesh Raykar
DefaultDirName={autopf}\LabReportPro
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=LabReportPro_Setup
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\LabReportPro"; Permissions: users-modify
Name: "{commonappdata}\LabReportPro\LabData"; Permissions: users-modify

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Start {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Uninstall keeps your data unless you say Yes.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if not UninstallSilent then
      if MsgBox('Also delete ALL LabReport Pro data (jobs, reports, audit trail, backups)?' + #13#10 + #13#10 +
                'Choose No to keep your data (recommended).', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(ExpandConstant('{commonappdata}\LabReportPro'), True, True, True);
  end;
end;
