; Instalador de CobbleverseMMO Launcher (Inno Setup)
; Compilar:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss

#define MyAppName "CobbleverseMMO Launcher"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "CobbleverseMMO"
#define MyAppExe "CobbleverseMMO Launcher.exe"

[Setup]
AppId={{8F3B2A10-C0BB-4EFA-9E55-COBBLEVERSE01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL=https://cobbleversemmo.net
; Instalación por usuario (sin pedir permisos de administrador → menos avisos)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\CobbleverseMMO Launcher
DisableProgramGroupPage=yes
DefaultGroupName=CobbleverseMMO
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
SetupIconFile=app.ico
OutputDir=C:\Users\Acer\Downloads
OutputBaseFilename=CobbleverseMMO-Launcher-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\CobbleverseMMO Launcher\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\CobbleverseMMO Launcher"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Desinstalar CobbleverseMMO Launcher"; Filename: "{uninstallexe}"
Name: "{userdesktop}\CobbleverseMMO Launcher"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Abrir CobbleverseMMO Launcher ahora"; Flags: nowait postinstall skipifsilent

[Code]
{ Desinstala cualquier versión anterior antes de instalar la nueva.
  Busca por NOMBRE en el registro (robusto: no depende del AppId). }
const
  UNINST_BASE = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\';

function FindUninstallInRoot(RootKey: Integer): String;
var
  names: TArrayOfString;
  i: Integer;
  dn, us: String;
begin
  Result := '';
  if RegGetSubkeyNames(RootKey, 'Software\Microsoft\Windows\CurrentVersion\Uninstall', names) then
  begin
    for i := 0 to GetArrayLength(names) - 1 do
    begin
      if RegQueryStringValue(RootKey, UNINST_BASE + names[i], 'DisplayName', dn) then
      begin
        if dn = '{#MyAppName}' then
        begin
          if RegQueryStringValue(RootKey, UNINST_BASE + names[i], 'UninstallString', us) then
          begin
            Result := us;
            Exit;
          end;
        end;
      end;
    end;
  end;
end;

function GetUninstallString(): String;
begin
  Result := FindUninstallInRoot(HKCU);
  if Result = '' then
    Result := FindUninstallInRoot(HKLM);
end;

procedure UnInstallOldVersion();
var
  s: String;
  iResultCode: Integer;
begin
  s := GetUninstallString();
  Log('CVDEBUG UninstallString=[' + s + ']');
  if s <> '' then
  begin
    s := RemoveQuotes(s);
    Exec(s, '/VERYSILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, iResultCode);
    Log('CVDEBUG desinstalador ejecutado, code=' + IntToStr(iResultCode));
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    UnInstallOldVersion();
end;
