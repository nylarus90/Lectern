; Inno Setup script for the OpenReader Windows installer.
;
; Built from the *onedir* PyInstaller output, not the single-file one: the
; single file unpacks itself into a temporary directory on every launch, which
; measured 854 ms to the first window against 351 ms for the directory build.
; The single file stays the portable download; an installed copy should not pay
; that price.
;
; File associations get their own wizard page listing every supported extension
; individually, so the user decides rather than the installer.  E-books and
; comics start ticked because Windows usually has no handler for them at all;
; PDF, text and HTML start unticked because those already have well-established
; handlers and quietly taking them over would be rude.
;
; Requires Inno Setup 6.3 or newer.
;
;   ISCC.exe /DSourceDir="...\dist-onedir\OpenReader" /DAppVersion=1.0.0 openreader.iss

#define AppName        "OpenReader"
#define AppPublisher   "OpenReader"
; The project has no public home yet.  Set this once it does and the
; wizard, the "Programs and Features" entry and the support links all
; pick it up; left empty, those fields are simply omitted.
#define AppUrl         ""
#define ExeName        "OpenReader.exe"
#define ProgIdPrefix   "OpenReader"

#ifndef AppVersion
  #define AppVersion   "0.0.0"
#endif
#ifndef SourceDir
  #error SourceDir muss gesetzt sein (Ordner mit OpenReader.exe)
#endif
#ifndef OutputDir
  #define OutputDir    "."
#endif
#ifndef LicenseFile
  #define LicenseFile  ""
#endif

[Setup]
; Never change AppId: it is how Windows recognises an existing installation and
; what makes an upgrade replace rather than duplicate it.
AppId={{7B3F1A64-2C58-4E1D-9A77-0F2E5C8D41B6}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
#if AppUrl != ""
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
AppUpdatesURL={#AppUrl}
#endif
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#ExeName}
OutputDir={#OutputDir}
OutputBaseFilename=OpenReader-{#AppVersion}-windows-x86_64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
; Two languages would otherwise open with a language prompt before anything
; else.  "auto" takes the system language when it matches one of them and only
; asks when it does not, which spares most people a pointless first click.
ShowLanguageDialog=auto
; Installing for the current user needs no administrator and is the friendlier
; default; the wizard still offers a machine-wide install.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Offer to close a running copy instead of failing on a locked file.
CloseApplications=yes
RestartApplications=no
#if LicenseFile != ""
LicenseFile={#LicenseFile}
#endif

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
de.DesktopIcon=Symbol auf dem Desktop anlegen
en.DesktopIcon=Create a desktop icon
de.AssocTitle=Dateiverknüpfungen
en.AssocTitle=File associations
de.AssocSubtitle=Welche Dateien soll OpenReader öffnen können?
en.AssocSubtitle=Which files should OpenReader be able to open?
de.AssocIntro=Wählen Sie die Dateitypen aus, die mit OpenReader verknüpft werden sollen. Nicht ausgewählte Typen lassen sich weiterhin über „Öffnen mit“ mit OpenReader öffnen.
en.AssocIntro=Choose the file types to associate with OpenReader. Types you leave out can still be opened with OpenReader through "Open with".
de.AssocAll=&Alle
en.AssocAll=&All
de.AssocNone=&Keine
en.AssocNone=&None
de.AssocRecommended=&Empfohlene
en.AssocRecommended=&Recommended
de.GroupBooks=E-Books — Windows hat dafür meist kein Programm
en.GroupBooks=E-books — Windows usually has no handler for these
de.GroupComics=Comic-Archive
en.GroupComics=Comic archives
de.GroupPdf=PDF — dafür ist meist schon ein Programm eingerichtet
en.GroupPdf=PDF — you probably already have a handler
de.GroupText=Text und HTML — konkurriert mit Editor und Browser
en.GroupText=Text and HTML — competes with your editor and browser
de.AssocHint=Hinweis: Windows 10 und 11 lassen ein Setup-Programm den Standard nicht erzwingen. Für Typen, die noch kein Programm haben, wird OpenReader zum Standard; sonst erscheint es unter „Öffnen mit“ und in den Windows-Standard-Apps.
en.AssocHint=Note: Windows 10 and 11 do not let an installer force the default handler. For types with no handler yet OpenReader becomes the default; otherwise it appears under "Open with" and in the Windows default apps settings.
de.RemoveDataPrompt=Sollen auch Leseposition, Lesezeichen und Notizen gelöscht werden?%n%nWählen Sie „Nein“, wenn Sie OpenReader später erneut installieren möchten.
en.RemoveDataPrompt=Also delete reading positions, bookmarks and notes?%n%nChoose "No" if you intend to install OpenReader again later.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\{#ExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "{#ExeName}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

; The application's own registration.  Per-extension entries are written from
; [Code] instead, because the user picks them one by one on a custom page and a
; static section cannot express that.  Deleting Software\OpenReader on uninstall
; takes the capability list with it.
[Registry]
Root: HKA; Subkey: "Software\Classes\Applications\{#ExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#ExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeName}"" ""%1"""
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Freier E-Book-Reader für EPUB, Kindle, FB2, PDF, Comics und Text"
Root: HKA; Subkey: "Software\{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "Software\{#AppName}\Capabilities"; Flags: uninsdeletevalue

[Code]
const
  SHCNE_ASSOCCHANGED = $08000000;
  SHCNF_IDLIST       = $0000;
  ASSOC_COUNT        = 22;

type
  TAssociation = record
    Ext:      String;    { file extension, with the dot }
    ProgId:   String;    { shared by extensions that are one and the same type }
    Desc:     String;    { the type's name, as Explorer will show it }
    Group:    Integer;   { 0 books, 1 comics, 2 pdf, 3 text }
    Suggest:  Boolean;   { ticked when the page first appears }
  end;

var
  Assoc: array[0..ASSOC_COUNT - 1] of TAssociation;
  AssocPage: TWizardPage;
  AssocList: TNewCheckListBox;
  ItemOf: array[0..ASSOC_COUNT - 1] of Integer;   { index in AssocList }

procedure SHChangeNotify(wEventId, uFlags: Integer; dwItem1, dwItem2: Cardinal);
  external 'SHChangeNotify@shell32.dll stdcall';

procedure RefreshShell;
begin
  { Without this Explorer keeps showing the old icons and the old "Open with"
    list until the next sign-in. }
  SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0);
end;

procedure Define(Index: Integer; const Ext, ProgId, Desc: String;
                 Group: Integer; Suggest: Boolean);
begin
  Assoc[Index].Ext := Ext;
  Assoc[Index].ProgId := '{#ProgIdPrefix}' + ProgId;
  Assoc[Index].Desc := Desc;
  Assoc[Index].Group := Group;
  Assoc[Index].Suggest := Suggest;
end;

function ListCaption(Index: Integer): String;
begin
  { The wizard wants the extension in front of the name; Explorer wants the
    name alone, or the file type reads ".epub — EPUB-E-Book". }
  Result := Assoc[Index].Ext + '  —  ' + Assoc[Index].Desc;
end;

procedure BuildTable;
begin
  { E-books: Windows ships no handler for any of these, so associating them is
    pure gain and they are suggested. }
  Define( 0, '.epub', '.epub', 'EPUB-E-Book',            0, True);
  Define( 1, '.mobi', '.mobi', 'Kindle-E-Book (MOBI)',   0, True);
  Define( 2, '.azw',  '.azw',  'Kindle-E-Book (AZW)',    0, True);
  Define( 3, '.azw3', '.azw3', 'Kindle-E-Book (AZW3)',   0, True);
  Define( 4, '.prc',  '.prc',  'Palm-E-Book (PRC)',      0, True);
  Define( 5, '.pdb',  '.pdb',  'Palm-E-Book (PDB)',      0, False);
  Define( 6, '.fb2',  '.fb2',  'FictionBook',            0, True);
  Define( 7, '.fbz',  '.fbz',  'FictionBook-Archiv',     0, True);

  Define( 8, '.cbz',  '.cbz',  'Comic-Archiv (ZIP)',     1, True);
  Define( 9, '.cbr',  '.cbr',  'Comic-Archiv (RAR)',     1, True);
  Define(10, '.cb7',  '.cb7',  'Comic-Archiv (7z)',      1, True);
  Define(11, '.cbt',  '.cbt',  'Comic-Archiv (TAR)',     1, True);
  Define(12, '.cba',  '.cba',  'Comic-Archiv (ACE)',     1, True);

  Define(13, '.pdf',  '.pdf',  'PDF-Dokument',           2, False);

  Define(14, '.txt',  '.txt',  'Textdatei',              3, False);
  Define(15, '.log',  '.txt',  'Protokolldatei',         3, False);
  Define(16, '.md',   '.md',   'Markdown-Dokument',      3, False);
  Define(17, '.markdown', '.md', 'Markdown-Dokument',    3, False);
  Define(18, '.rtf',  '.rtf',  'Rich-Text-Dokument',     3, False);
  Define(19, '.html', '.html', 'HTML-Dokument',          3, False);
  Define(20, '.htm',  '.html', 'HTML-Dokument',          3, False);
  Define(21, '.xhtml','.html', 'XHTML-Dokument',         3, False);
end;

function GroupCaption(Group: Integer): String;
begin
  case Group of
    0: Result := ExpandConstant('{cm:GroupBooks}');
    1: Result := ExpandConstant('{cm:GroupComics}');
    2: Result := ExpandConstant('{cm:GroupPdf}');
  else
    Result := ExpandConstant('{cm:GroupText}');
  end;
end;

procedure SetAll(Checked: Boolean);
var
  I: Integer;
begin
  for I := 0 to ASSOC_COUNT - 1 do
    AssocList.Checked[ItemOf[I]] := Checked;
end;

procedure SelectAllClick(Sender: TObject);
begin
  SetAll(True);
end;

procedure SelectNoneClick(Sender: TObject);
begin
  SetAll(False);
end;

procedure SelectSuggestedClick(Sender: TObject);
var
  I: Integer;
begin
  for I := 0 to ASSOC_COUNT - 1 do
    AssocList.Checked[ItemOf[I]] := Assoc[I].Suggest;
end;

procedure CreateAssocPage;
var
  Intro, Hint: TNewStaticText;
  ButtonAll, ButtonNone, ButtonSuggested: TNewButton;
  Group, I: Integer;
begin
  AssocPage := CreateCustomPage(wpSelectTasks,
    ExpandConstant('{cm:AssocTitle}'), ExpandConstant('{cm:AssocSubtitle}'));

  Intro := TNewStaticText.Create(AssocPage);
  Intro.Parent := AssocPage.Surface;
  Intro.Left := 0;
  Intro.Top := 0;
  Intro.Width := AssocPage.SurfaceWidth;
  Intro.AutoSize := False;
  Intro.WordWrap := True;
  Intro.Height := ScaleY(28);
  Intro.Caption := ExpandConstant('{cm:AssocIntro}');

  AssocList := TNewCheckListBox.Create(AssocPage);
  AssocList.Parent := AssocPage.Surface;
  AssocList.Left := 0;
  AssocList.Top := Intro.Top + Intro.Height + ScaleY(6);
  AssocList.Width := AssocPage.SurfaceWidth;
  { Room below the list for the buttons plus a three-line note; at two
    lines the note was cut off mid-sentence. }
  AssocList.Height := AssocPage.SurfaceHeight - AssocList.Top - ScaleY(88);
  AssocList.Flat := True;
  AssocList.WantTabs := True;
  AssocList.MinItemHeight := ScaleY(16);

  { A checkable group header toggles its whole section, which is what most
    people want, while every single extension stays individually selectable. }
  for Group := 0 to 3 do
  begin
    AssocList.AddCheckBox(GroupCaption(Group), '', 0, False, True, False, True, nil);
    for I := 0 to ASSOC_COUNT - 1 do
      if Assoc[I].Group = Group then
        ItemOf[I] := AssocList.AddCheckBox(
          ListCaption(I), '', 1, Assoc[I].Suggest, True, False, False, nil);
  end;

  ButtonSuggested := TNewButton.Create(AssocPage);
  ButtonSuggested.Parent := AssocPage.Surface;
  ButtonSuggested.Top := AssocList.Top + AssocList.Height + ScaleY(8);
  ButtonSuggested.Left := 0;
  ButtonSuggested.Width := ScaleX(90);
  ButtonSuggested.Height := ScaleY(23);
  ButtonSuggested.Caption := ExpandConstant('{cm:AssocRecommended}');
  ButtonSuggested.OnClick := @SelectSuggestedClick;

  ButtonAll := TNewButton.Create(AssocPage);
  ButtonAll.Parent := AssocPage.Surface;
  ButtonAll.Top := ButtonSuggested.Top;
  ButtonAll.Left := ButtonSuggested.Left + ButtonSuggested.Width + ScaleX(8);
  ButtonAll.Width := ScaleX(70);
  ButtonAll.Height := ButtonSuggested.Height;
  ButtonAll.Caption := ExpandConstant('{cm:AssocAll}');
  ButtonAll.OnClick := @SelectAllClick;

  ButtonNone := TNewButton.Create(AssocPage);
  ButtonNone.Parent := AssocPage.Surface;
  ButtonNone.Top := ButtonSuggested.Top;
  ButtonNone.Left := ButtonAll.Left + ButtonAll.Width + ScaleX(8);
  ButtonNone.Width := ScaleX(70);
  ButtonNone.Height := ButtonSuggested.Height;
  ButtonNone.Caption := ExpandConstant('{cm:AssocNone}');
  ButtonNone.OnClick := @SelectNoneClick;

  Hint := TNewStaticText.Create(AssocPage);
  Hint.Parent := AssocPage.Surface;
  Hint.Left := 0;
  Hint.Top := ButtonSuggested.Top + ButtonSuggested.Height + ScaleY(6);
  Hint.Width := AssocPage.SurfaceWidth;
  Hint.AutoSize := False;
  Hint.WordWrap := True;
  Hint.Height := ScaleY(48);
  Hint.Caption := ExpandConstant('{cm:AssocHint}');
end;

procedure InitializeWizard;
begin
  BuildTable;
  CreateAssocPage;
end;

function RootKey: Integer;
begin
  { HKA in [Registry] resolves this automatically; in code it has to be said. }
  if IsAdminInstallMode then
    Result := HKEY_LOCAL_MACHINE
  else
    Result := HKEY_CURRENT_USER;
end;

function Wanted(Index: Integer): Boolean;
var
  Chosen: String;
begin
  { An unattended install has no page to read, so /ASSOC= drives it instead:
      /ASSOC=none        nothing
      /ASSOC=all         every supported type
      /ASSOC=suggested   the same set the page starts with (the default)
      /ASSOC=.epub,.cbz  exactly these }
  if WizardSilent then
  begin
    Chosen := LowerCase(ExpandConstant('{param:ASSOC|suggested}'));
    if Chosen = 'none' then
      Result := False
    else if Chosen = 'all' then
      Result := True
    else if Chosen = 'suggested' then
      Result := Assoc[Index].Suggest
    else
      Result := Pos(Assoc[Index].Ext + ',', Chosen + ',') > 0;
  end
  else
    Result := AssocList.Checked[ItemOf[Index]];
end;

procedure WriteAssociation(Index: Integer);
var
  Root: Integer;
  Exe, ProgId: String;
begin
  Root := RootKey;
  Exe := ExpandConstant('{app}\{#ExeName}');
  ProgId := Assoc[Index].ProgId;

  { The type itself, plus its icon and its open command. }
  RegWriteStringValue(Root, 'Software\Classes\' + ProgId, '', Assoc[Index].Desc);
  RegWriteStringValue(Root, 'Software\Classes\' + ProgId + '\DefaultIcon', '', Exe + ',0');
  RegWriteStringValue(Root, 'Software\Classes\' + ProgId + '\shell\open\command', '',
                      '"' + Exe + '" "%1"');

  { OpenWithProgids adds OpenReader to the "Open with" list without taking the
    extension away from whatever already owns it; SupportedTypes makes Explorer
    offer it at all; Capabilities lists it under Windows' default apps, which on
    Windows 10 and 11 is the only supported way for the user to make it the
    default.  The installer deliberately never writes the extension's default
    handler: Windows ignores that once the user has ever chosen one, and
    overwriting it where it still works is exactly the behaviour people hate. }
  RegWriteStringValue(Root, 'Software\Classes\' + Assoc[Index].Ext + '\OpenWithProgids',
                      ProgId, '');
  RegWriteStringValue(Root, 'Software\Classes\Applications\{#ExeName}\SupportedTypes',
                      Assoc[Index].Ext, '');
  RegWriteStringValue(Root, 'Software\{#AppName}\Capabilities\FileAssociations',
                      Assoc[Index].Ext, ProgId);

  { An extension nobody handles yet gets OpenReader as its default -- this is
    the case Windows still permits, and the whole point for .epub and friends. }
  if not RegValueExists(HKEY_CLASSES_ROOT, Assoc[Index].Ext, '') then
    RegWriteStringValue(Root, 'Software\Classes\' + Assoc[Index].Ext, '', ProgId);
end;

procedure RememberChoice;
var
  I: Integer;
  Written: String;
begin
  { The uninstaller cannot ask the wizard what was picked, so the list is kept
    where it can read it back. }
  Written := '';
  for I := 0 to ASSOC_COUNT - 1 do
    if Wanted(I) then
    begin
      WriteAssociation(I);
      Written := Written + Assoc[I].Ext + ';';
    end;
  RegWriteStringValue(RootKey, 'Software\{#AppName}', 'Associations', Written);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    RememberChoice;
    RefreshShell;
  end;
end;

procedure RemoveAssociations;
var
  Root, I: Integer;
  Written, Ext, ProgId: String;
begin
  Root := RootKey;
  if not RegQueryStringValue(Root, 'Software\{#AppName}', 'Associations', Written) then
    Written := '';
  for I := 0 to ASSOC_COUNT - 1 do
  begin
    Ext := Assoc[I].Ext;
    if Pos(Ext + ';', Written) = 0 then
      Continue;
    ProgId := Assoc[I].ProgId;
    { Only give the extension back if it is still ours -- the user may have
      pointed it somewhere else since, and that choice must survive. }
    if RegQueryStringValue(Root, 'Software\Classes\' + Ext, '', ProgId) and
       (ProgId = Assoc[I].ProgId) then
      RegDeleteValue(Root, 'Software\Classes\' + Ext, '');
    RegDeleteValue(Root, 'Software\Classes\' + Ext + '\OpenWithProgids', Assoc[I].ProgId);
    RegDeleteKeyIncludingSubkeys(Root, 'Software\Classes\' + Assoc[I].ProgId);
  end;
  RegDeleteKeyIncludingSubkeys(Root, 'Software\Classes\Applications\{#ExeName}');
end;

function DataDirectory: String;
begin
  Result := ExpandConstant('{userappdata}\openreader');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    BuildTable;
    RemoveAssociations;
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    { Reading positions and notes are the user's work, not ours, so they are
      never removed without being asked -- and the default answer is to keep
      them, because reinstalling is far more common than leaving for good. }
    if DirExists(DataDirectory) then
      if SuppressibleMsgBox(ExpandConstant('{cm:RemoveDataPrompt}'),
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(DataDirectory, True, True, True);
    RefreshShell;
  end;
end;
