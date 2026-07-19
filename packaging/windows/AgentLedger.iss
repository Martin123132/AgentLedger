#ifndef AppVersion
  #error AppVersion must be provided
#endif
#ifndef SourceExe
  #error SourceExe must be provided
#endif
#ifndef OutputDir
  #error OutputDir must be provided
#endif
#ifndef RepoRoot
  #error RepoRoot must be provided
#endif

[Setup]
AppId={{AF634F0E-D967-4BE7-B840-F8DD4A874D97}
AppName=AgentLedger
AppVersion={#AppVersion}
AppPublisher=Martin Ollett
AppPublisherURL=https://github.com/Martin123132/AgentLedger
AppSupportURL=https://github.com/Martin123132/AgentLedger/issues
DefaultDirName={localappdata}\Programs\AgentLedger
DefaultGroupName=AgentLedger
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=AgentLedger-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\AgentLedger.exe
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "AgentLedger.exe"; Flags: ignoreversion
Source: "{#RepoRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\COMMERCIAL.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AgentLedger"; Filename: "{app}\AgentLedger.exe"
Name: "{group}\Uninstall AgentLedger"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AgentLedger"; Filename: "{app}\AgentLedger.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AgentLedger.exe"; Description: "Launch AgentLedger"; Flags: nowait postinstall skipifsilent
