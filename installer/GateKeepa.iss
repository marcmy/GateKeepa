#ifndef MyAppVersion
  #define MyAppVersion "0.2.3"
#endif
#ifndef RepoRoot
  #define RepoRoot ".."
#endif

[Setup]
AppId={{7F9336DE-808D-4C26-B91F-71B77E6AD86A}
AppName=Gate Keepa
AppVersion={#MyAppVersion}
AppPublisher=marcmy
DefaultDirName={localappdata}\Programs\GateKeepa
DefaultGroupName=Gate Keepa
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#RepoRoot}\dist\installer
OutputBaseFilename=GateKeepa-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\GateKeepa.exe
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "startup"; Description: "Start Gate Keepa automatically when I sign in"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "{#RepoRoot}\dist\GateKeepa.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\dist\GateKeepaNativeHost.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\native-messaging\com.marcmy.gatekeepa.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\build\firefox\GateKeepa.xpi"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Registry]
Root: HKCU; Subkey: "Software\Mozilla\NativeMessagingHosts\com.marcmy.gatekeepa"; ValueType: string; ValueName: ""; ValueData: "{app}\com.marcmy.gatekeepa.json"; Flags: uninsdeletekey

[Icons]
Name: "{group}\Gate Keepa"; Filename: "{app}\GateKeepa.exe"; Parameters: "--configure"
Name: "{userstartup}\Gate Keepa"; Filename: "{app}\GateKeepa.exe"; Parameters: "--background"; Tasks: startup

[Run]
Filename: "{app}\GateKeepa.exe"; Parameters: "--configure"; Description: "Configure Gate Keepa"; Flags: nowait postinstall skipifsilent
Filename: "{app}\GateKeepa.xpi"; Description: "Install the Firefox extension"; Flags: shellexec postinstall skipifsilent; Check: SignedXpiPresent

[Code]
function SignedXpiPresent(): Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\GateKeepa.xpi'));
end;

[InstallDelete]
Type: files; Name: "{app}\SourcingCockpitHelper.exe"
Type: files; Name: "{app}\SourcingCockpit.xpi"
Type: files; Name: "{userstartup}\Sourcing Cockpit.lnk"
