#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif

[Setup]
AppId=electblake.AllTheSmallThings
AppName=All the Small Things
AppVersion={#AppVersion}
AppPublisher=electblake
AppPublisherURL=https://github.com/electblake/all-the-small-things
AppSupportURL=https://github.com/electblake/all-the-small-things/issues
DefaultDirName={localappdata}\Programs\All the Small Things
DefaultGroupName=All the Small Things
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist\installer
OutputBaseFilename=AllTheSmallThings-{#AppVersion}-windows-amd64-setup
UninstallDisplayIcon={app}\SmallThings.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Files]
Source: "..\dist\SmallThings\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Icons]
Name: "{autoprograms}\All the Small Things"; Filename: "{app}\SmallThings.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\All the Small Things"; Filename: "{app}\SmallThings.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\SmallThings.exe"; Description: "{cm:LaunchProgram,All the Small Things}"; Flags: nowait postinstall skipifsilent unchecked
