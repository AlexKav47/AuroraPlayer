#define MyAppName "Aurora Player"
#define MyAppVersion "1.1.1"
#define MyAppPublisher "Aurora Player"
#define MyAppExeName "AuroraPlayer.exe"
#define MyAppId "{{8C9D7C2E-62D9-4F58-A247-568BBD25CF11}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Aurora Player
DefaultGroupName=Aurora Player
DisableProgramGroupPage=yes
UninstallDisplayName=Aurora Player
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
#ifdef TestInstall
PrivilegesRequired=lowest
CreateUninstallRegKey=no
OutputDir=..\..\..\work
OutputBaseFilename=AuroraPlayer-Setup-Test
#else
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
OutputDir=..\release
OutputBaseFilename=AuroraPlayer-v{#MyAppVersion}-Setup
#endif
SetupIconFile=..\aurora_player\assets\aurora-player.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
CloseApplications=yes
RestartApplications=no
ChangesAssociations=yes
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Aurora Player Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (c) 2026 Aurora Player contributors

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\release\AuroraPlayer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

#ifndef TestInstall
[Icons]
Name: "{autoprograms}\Aurora Player"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Aurora Player"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Aurora Player"; Flags: nowait postinstall skipifsilent
Filename: "ms-settings:defaultapps"; Description: "Choose Aurora Player as the default media player"; Flags: shellexec postinstall skipifsilent

#ifndef TestInstall
[Registry]
; Windows Registered Applications / Default Apps capabilities.
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Aurora Player"; ValueData: "Software\AuroraPlayer\Capabilities"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Aurora Player"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Play video and audio files with Aurora Player"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationIcon"; ValueData: "{app}\{#MyAppExeName},0"

; A single ProgID is shared by all supported media extensions.
Root: HKA; Subkey: "Software\Classes\AuroraPlayer.Media"; ValueType: string; ValueData: "Aurora Player media file"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\AuroraPlayer.Media\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\AuroraPlayer.Media\shell"; ValueType: string; ValueData: "open"
Root: HKA; Subkey: "Software\Classes\AuroraPlayer.Media\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; Explorer's Open With list and executable lookup.
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Aurora Player"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\AuroraPlayer.exe"; ValueType: string; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\AuroraPlayer.exe"; ValueType: string; ValueName: "Path"; ValueData: "{app}"

; Video capabilities.
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".3g2"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".3gp"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".asf"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".divx"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flv"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m2ts"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4v"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpeg"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mpg"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mts"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogm"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogv"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".rm"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".rmvb"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ts"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".vob"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "AuroraPlayer.Media"

; Audio capabilities.
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aac"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ac3"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aiff"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".alac"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ape"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".dts"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".eac3"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4a"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mka"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp2"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogg"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".opus"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wav"; ValueData: "AuroraPlayer.Media"
Root: HKA; Subkey: "Software\AuroraPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wma"; ValueData: "AuroraPlayer.Media"

; SupportedTypes controls the extensions shown under Explorer's Open With menu.
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".avi"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mov"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mpeg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mpg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".wmv"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".aac"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".flac"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".m4a"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".mp3"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".ogg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".opus"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\AuroraPlayer.exe\SupportedTypes"; ValueType: string; ValueName: ".wav"; ValueData: ""
#endif

[UninstallDelete]
; Remove any application-owned runtime assets left after tracked-file cleanup.
Type: filesandordirs; Name: "{app}\runtime"
Type: files; Name: "{app}\README.txt"

[Code]
var
  RemoveAuroraUserData: Boolean;

function HasCommandLineSwitch(const SwitchName: String): Boolean;
var
  Index: Integer;
begin
  Result := False;
  for Index := 1 to ParamCount do
    if CompareText(ParamStr(Index), SwitchName) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

function InitializeUninstall(): Boolean;
begin
  if UninstallSilent then
    RemoveAuroraUserData := not HasCommandLineSwitch('/KEEPUSERDATA')
  else
    RemoveAuroraUserData :=
      MsgBox(
        'Also remove Aurora Player settings, library data, custom themes, and extensions?'#13#10#13#10 +
        'Your original video and audio files will not be deleted.',
        mbConfirmation,
        MB_YESNO
      ) = IDYES;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and RemoveAuroraUserData then
  begin
    DelTree(ExpandConstant('{userappdata}\AuroraPlayer\Aurora Player'), True, True, True);
    DelTree(ExpandConstant('{localappdata}\AuroraPlayer\Aurora Player'), True, True, True);
    RegDeleteKeyIncludingSubkeys(HKCU, 'Software\AuroraPlayer');
  end;
end;
