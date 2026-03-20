[Setup]
; Info applicazione
AppName=PyLanShare
AppVersion=1.0.0
AppPublisher=AmMstools
AppPublisherURL=https://github.com/AmMstools
DefaultDirName={autopf}\PyLanShare
DefaultGroupName=PyLanShare
OutputDir=installer_output
OutputBaseFilename=PyLanShare_Setup_1.0.0
Compression=lzma2
SolidCompression=yes
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\PyLanShare.exe
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

; Permessi (installa senza admin se possibile)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia tutto il contenuto della cartella Nuitka standalone
Source: "dist\run.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Menu Start
Name: "{group}\PyLanShare"; Filename: "{app}\PyLanShare.exe"; IconFilename: "{app}\PyLanShare.exe"
Name: "{group}\Uninstall PyLanShare"; Filename: "{uninstallexe}"
; Desktop (opzionale)
Name: "{userdesktop}\PyLanShare"; Filename: "{app}\PyLanShare.exe"; IconFilename: "{app}\PyLanShare.exe"; Tasks: desktopicon

[Run]
; Lancia l'app dopo l'installazione (opzionale)
Filename: "{app}\PyLanShare.exe"; Description: "Launch PyLanShare"; Flags: nowait postinstall skipifsilent
