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
