[Setup]
AppName=GameCode
AppVersion=0.1.0
DefaultDirName={autopf}\GameCode
DefaultGroupName=GameCode
OutputDir=..\installer_output
OutputBaseFilename=GameCode-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\GameCode.exe

[Files]
Source: "..\dist\GameCode\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\GameCode"; Filename: "{app}\GameCode.exe"
Name: "{group}\Uninstall GameCode"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\GameCode.exe"; Description: "Launch GameCode"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\GameCode"

[Code]
var
  KeyPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  KeyPage := CreateInputQueryPage(wpSelectDir,
    'API Key', 'Enter your OpenCode Zen API key',
    'Leave blank to run in Locked Mode (Build + Plan only).');
  KeyPage.Add('API key (starts with sk-):', True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Key, Dir: String;
begin
  if CurStep = ssPostInstall then
  begin
    Key := Trim(KeyPage.Values[0]);
    if Key <> '' then
    begin
      Dir := ExpandConstant('{userappdata}\GameCode');
      ForceDirectories(Dir);
      SaveStringToFile(Dir + '\config.json', '{"api_key": "' + Key + '"}', False);
    end;
  end;
end;