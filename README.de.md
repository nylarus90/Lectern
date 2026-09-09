# OpenReader

**Deutsch** · [English](README.md)

Ein freier E-Book-Reader — keine Laufzeitumgebung, kein Browser, keine
Abhängigkeiten. Als **portable Einzeldatei** zum Herunterladen und Starten,
für Windows wahlweise als **Installer** mit frei wählbaren Dateiverknüpfungen.

![Lizenz](https://img.shields.io/badge/Lizenz-GPL--3.0--or--later-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Qt](https://img.shields.io/badge/Oberfl%C3%A4che-Qt%20Widgets-41cd52)

---

## Unterstützte Formate

| Format | Dateiendungen | Umfang |
|---|---|---|
| **EPUB 2 / EPUB 3** | `.epub` | Spine, NCX- und Nav-Inhaltsverzeichnis, Cover, Bilder, interne Links, Metadaten inkl. Reihe |
| **Kindle KF7** | `.mobi` `.azw` `.prc` `.pdb` | PalmDOC- und HUFF/CDIC-Dekompression, EXTH-Metadaten, `recindex`-Bilder, `filepos`-Links |
| **Kindle KF8** | `.azw3` `.azw` | Haupt-Flow, `kindle:embed:`-Bilder, kombinierte MOBI/KF8-Dateien |
| **FictionBook** | `.fb2` `.fb2.zip` `.fbz` | Verschachtelte Abschnitte, Gedichte, Zitate, eingebettete Bilder |
| **PDF** | `.pdf` | Natives Rendering über Qt PDF, Gliederung, Volltextsuche, Zoom |
| **Comics** | `.cbz` `.cbt` `.cb7` `.cba` `.cbr` | Natürliche Seitensortierung, Anpassungsmodi |
| **Text** | `.txt` `.log` | Kodierungserkennung, automatische Kapitelerkennung |
| **Markdown** | `.md` `.markdown` | CommonMark |
| **HTML** | `.html` `.htm` `.xhtml` | Mit Bildern aus dem Nachbarordner |
| **Rich Text** | `.rtf` | Formatierung, Kodierungen, Unicode-Escapes |

Das Format wird **am Inhalt** erkannt, nicht an der Endung — eine als `.epub`
benannte AZW3-Datei wird trotzdem korrekt geöffnet.

### Was bewusst nicht geht

| | Warum |
|---|---|
| **DRM-geschützte Bücher** (Adobe ADEPT, Kindle) | Rechtlich und technisch außerhalb des Projekts. Solche Dateien werden erkannt und mit klarer Meldung abgelehnt, statt Buchstabensalat anzuzeigen. |
| **KFX** (neues Kindle-Format) | Undokumentiert und in der Praxis stets DRM-behaftet. |
| **`.cbr` ohne Systemwerkzeug** | Für RAR5 existiert kein freier Entpacker in Python, und die unrar-Lizenz verbietet das Mitliefern. Sind `unrar`, `bsdtar` oder `7z` installiert, werden sie genutzt; sonst gibt es eine Erklärung statt eines stummen Fehlers. |
| **DjVu** | Bräuchte eine C-Bibliothek und damit einen Compiler in der Build-Kette. |

---

## Installation

Für Windows gibt es beides — für alles andere reicht die Programmdatei.

| Plattform | Datei | Hinweis |
|---|---|---|
| Windows 10/11 (x64) | `OpenReader-*-windows-x86_64-setup.exe` | Installer mit wählbaren Dateiverknüpfungen |
| Windows 10/11 (x64) | `OpenReader-*-windows-x86_64.exe` | portabel, Doppelklick, keine Installation |
| macOS (Apple Silicon) | `OpenReader-*-macos-arm64.zip` | Entpacken, dann Rechtsklick → „Öffnen“ (nicht signiert) |
| Linux (x64, glibc ≥ 2.35) | `OpenReader-*-linux-x86_64` | `chmod +x` und starten |

### Beim ersten Start warnt Windows

Beide Windows-Dateien sind **nicht signiert**, deshalb zeigt SmartScreen beim
ersten Start „Der Computer wurde durch Windows geschützt“. Über
**Weitere Informationen → Trotzdem ausführen** geht es weiter.

Das ist kein Hinweis auf ein Problem mit der Datei, sondern schlicht die
Abwesenheit eines Zertifikats: Ein Code-Signing-Zertifikat kostet laufend Geld,
ist seit März 2026 auf 460 Tage Laufzeit begrenzt und würde die Warnung nicht
einmal sofort beseitigen — SmartScreen baut Vertrauen erst über Downloadzahlen
auf. Für ein Hobbyprojekt steht das in keinem Verhältnis.

Wer die Datei prüfen möchte, vergleicht sie mit `SHA256SUMS.txt` aus demselben
Release:

```powershell
Get-FileHash .\OpenReader-1.0.0-windows-x86_64-setup.exe -Algorithm SHA256
```

### Installer oder portabel?

| | Installer | Portable Datei |
|---|---|---|
| Start bis zum Fenster | **351 ms** | 854 ms |
| Download | 28 MB | 36 MB |
| Dateiverknüpfungen | ja, frei wählbar | nein |
| Startmenü, Deinstallation | ja | nein |
| Administratorrechte | nicht nötig (wahlweise) | nicht nötig |
| Hinterlässt Spuren | ja, deinstallierbar | keine |

Die portable Datei ist langsamer, weil sie sich bei **jedem** Start in ein
temporäres Verzeichnis entpackt — genau das macht sie ja portabel. Der
Installer legt die Dateien einmal ab und spart sich das.

### Dateiverknüpfungen

Der Installer zeigt eine eigene Seite, auf der **jeder Dateityp einzeln**
an- und abwählbar ist, mit Schaltflächen für „Empfohlene“, „Alle“ und „Keine“.
Vorausgewählt sind E-Books und Comic-Archive, weil Windows dafür meist gar
kein Programm hat. PDF, Text und HTML sind bewusst nicht vorausgewählt — dort
gibt es fast immer schon ein eingerichtetes Programm.

Was der Installer dabei tut, hängt vom Dateityp ab, und das ist keine
Willkür, sondern die Grenze, die Windows zieht:

- **Typ hatte noch kein Programm** (`.mobi`, `.azw3`, `.fb2`, `.cbz` …) →
  OpenReader wird der Standard.
- **Typ hat bereits ein Programm** (`.pdf`, `.txt`, oft `.epub`) → OpenReader
  kommt zu „Öffnen mit“ und in die Windows-Standard-Apps hinzu; der
  vorhandene Standard bleibt unangetastet.

Windows 10 und 11 lassen ein Setup-Programm den Standard nicht erzwingen, und
das ist gut so. Zum Umstellen: **Einstellungen → Apps → Standard-Apps →
OpenReader**.

Die Deinstallation nimmt die Verknüpfungen wieder zurück — aber nur die
eigenen. Haben Sie einen Dateityp inzwischen einem anderen Programm
zugewiesen, bleibt diese Zuweisung bestehen.

Für unbeaufsichtigte Installationen:

```bat
OpenReader-1.0.0-windows-x86_64-setup.exe /VERYSILENT /ASSOC=.epub,.cbz
```

`/ASSOC=` versteht `none`, `all`, `suggested` (Vorgabe) oder eine Liste von
Endungen. Mit `/CURRENTUSER` beziehungsweise `/ALLUSERS` lässt sich der
Installationsumfang festlegen, mit `/DIR=` das Zielverzeichnis.

### Portabel auf USB-Stick

Standardmäßig liegen Leseposition und Einstellungen im Benutzerprofil. Für einen
vollständig portablen Betrieb, der nichts auf dem Rechner hinterlässt, eine
leere Datei `portable.txt` neben die Programmdatei legen — oder starten mit:

```bash
OpenReader --portable
```

Alternativ ein beliebiger Ablageort:

```bash
OpenReader --data-dir /pfad/zu/meinen/daten
```

---

## Bedienung

| Taste | Wirkung |
|---|---|
| `Leertaste` · `Bild ab` · `→` | Nächste Seite |
| `Rücktaste` · `Bild auf` · `←` | Vorherige Seite |
| `Strg+O` / `Strg+W` | Buch öffnen / schließen |
| `Strg+F` · `F3` · `Umschalt+F3` | Suchen · nächster · vorheriger Treffer |
| `Strg+B` | Lesezeichen setzen |
| `Strg+H` | Auswahl markieren |
| `Strg+G` | Gehe zu Seite oder Position |
| `Strg++` / `Strg+−` / `Strg+0` | Schrift größer / kleiner / zurücksetzen |
| `F9` / `F11` | Seitenleiste / Vollbild |
| `Strg+,` | Einstellungen |
| `Esc` | Suche beenden, Vollbild verlassen |

Bücher lassen sich auch per Drag & Drop ins Fenster ziehen.

**Weiteres:** vier Farbschemata (Hell, Sepia, Dunkel, OLED-Schwarz), einstellbare
Schriftart, -größe, Zeilen- und Absatzabstand, Seitenrand und maximale
Zeilenbreite; Lesezeichen und farbige Markierungen mit Notizen, exportierbar
als Markdown; die Leseposition wird pro Buch gemerkt und überlebt das
Verschieben der Datei, weil Bücher am Inhalt und nicht am Pfad erkannt werden.

---

## Aus dem Quelltext

```bash
python -m pip install -r requirements-dev.txt
python -m openreader                     # starten
python -m pytest                         # 174 Tests
python tests/smoke_gui.py --visible      # Screenshots aller Ansichten
python tests/bench_reader.py             # Scroll-Leistung messen
python tests/bench_prefetch.py --book X  # Restruckler beziffern
pyinstaller build/openreader.spec --noconfirm --distpath build/dist
python build/make_installer.py           # Windows-Installer (braucht Inno Setup 6)
```

Benötigt Python 3.10 oder neuer.

---

## Aufbau

```
openreader/
├── formats/     Ein Parser je Format → ein gemeinsames Book-Modell
├── render/      HTML5→Qt-Normalisierung, Farbschemata, Typografie
├── storage/     SQLite (Position, Lesezeichen, Markierungen) und Einstellungen
└── ui/          Hauptfenster, Text-/PDF-/Comic-Ansicht, Panels, Ladethread
```

Alle Format-Parser liefern dasselbe `Book`-Objekt, weshalb die Ansichten
keinerlei formatspezifische Sonderfälle enthalten. Das Laden läuft in einem
Arbeitsthread; nur das fertige Dokument wird an die Oberfläche übergeben.

### Technische Entscheidungen

**Warum Qts eigene Rich-Text-Engine statt einer eingebetteten Browser-Engine?**
Ein eingebettetes Chromium würde die Programmdatei von 36 MB auf über 250 MB
aufblähen und wäre faktisch ein Browser. Qts Engine versteht dafür nur einen
Teil von CSS 2.1 — für Belletristik und normale Sachbücher ist das
ausgezeichnet, bei mehrspaltigen oder aufwendig gestalteten EPUB-3-Layouts
werden Feinheiten vereinfacht dargestellt. Verlags-Stylesheets lassen sich in
den Einstellungen zuschalten; standardmäßig sind sie aus, weil ein zur Hälfte
angewandtes Stylesheet meist schlechter aussieht als ein sauberes eigenes.

**Warum ein einziges Dokument statt eines pro Kapitel?**
Nur so funktionieren durchgehendes Scrollen, buchweite Suche und stabile
Positionen für Markierungen. Weil das Dokument deterministisch aus der Datei
entsteht, zeigt eine gespeicherte Markierung auch nach Monaten noch auf
dieselben Wörter.

**Warum cacht der Reader Bilder selbst?**
Qt legt eine Ressource erst dann in seinen Cache, wenn die *Basisimplementierung*
von `loadResource` durchläuft. Da Buchbilder im Speicher liegen und nicht auf der
Platte, muss der Reader vorher zurückkehren — und damit auch selbst cachen. Ohne
das wurde jede Abbildung bei **jedem einzelnen Neuzeichnen** neu dekodiert und
geglättet skaliert. Auf einem 21-MB-Roman mit 15 ganzseitigen Tafeln kostete das
303 ms pro Frame; die Hälfte aller Frames lag unter 30 fps. Gemessen und behoben:
siehe [Scroll-Leistung](#scroll-leistung).

**Warum werden Bilder nicht im Hintergrund vorausgeladen?**
Weil gemessen wurde, was es brächte. Nach dem Cache bleibt ein Restaufwand: Ein
Bild muss beim allerersten Erscheinen einmal dekodiert werden. Über das
vollständige Durchscrollen eines 21-MB-Bilderbuchs sind das **11 spürbare Frames
von 7.426** — 0,15 %, je rund 17 ms über dem Normalwert, also ein bis zwei
ausgelassene Bilder bei 60 Hz. Einmal komplett durchblättern kostet insgesamt
0,26 Sekunden. Im ungünstigsten Fall, einem Sprung über das Inhaltsverzeichnis,
entfallen von etwa 59 ms nur ~25 ms aufs Dekodieren; ein Vorauslader könnte also
nicht einmal die Hälfte davon einsparen. Dem stünden ein Hintergrund-Thread, ein
gesperrter Cache, Vorhersagelogik für den sichtbaren Bereich und eine
schwer testbare Klasse von Wettlauffehlern gegenüber. Nachrechnen mit
`tests/bench_prefetch.py`.

**Warum wird die Zeilenhöhe bei Bildern zurückgesetzt?**
Ein relativer `line-height` multipliziert die Höhe des größten Elements einer
Zeile. Eine 320 px hohe Abbildung in einem 155-%-Absatz belegt sonst 496 px und
hinterlässt ein Loch. Blöcke mit Bildern bekommen deshalb nachträglich 100 %
Zeilenhöhe — und werden gleich mittig gesetzt.

### Welche Daten wo gespeichert werden

OpenReader sendet nichts ins Netz. Lokal gespeichert werden Dateipfad, Titel,
Autor, Zeitpunkt des Öffnens, Leseposition sowie Lesezeichen, Markierungen und
Notizen — in `library.sqlite3` und `settings.json`:

| Plattform | Ort |
|---|---|
| Windows | `%APPDATA%\openreader` |
| macOS | `~/Library/Application Support/openreader` |
| Linux | `$XDG_DATA_HOME/openreader` bzw. `~/.local/share/openreader` |

Das Verzeichnis gehört dem eigenen Konto: unter Linux und macOS mit `0700`
beziehungsweise `0600` für die Dateien, unter Windows über eine ACL, die nur
den Eigentümer und SYSTEM einträgt. Das ist vor allem für den portablen Modus
wichtig — ein Datenordner in einem freigegebenen Verzeichnis würde dessen
Rechte sonst erben. Auf Dateisystemen ganz ohne Rechteverwaltung, etwa einem
FAT-formatierten USB-Stick, lässt sich nichts durchsetzen; dort liegen die
Daten offen.

**Verschlüsselt sind sie nicht.** Wer das braucht, legt sie per `--data-dir`
auf einen verschlüsselten Datenträger. **Datei → Zuletzt geöffnet → Liste
leeren** löscht den gesamten Verlauf einschließlich Lesezeichen und Notizen.

---

## Scroll-Leistung

Gemessen mit `tests/bench_reader.py` an einem echten 21-MB-Roman mit 15
ganzseitigen JPEG-Tafeln, Fenster maximiert, 150 Mausrad-Rasten,
150-%-Skalierung:

| | vorher | nachher |
|---|---|---|
| Frame über einer Abbildung (Median) | 303 ms | **4 ms** |
| schlechtester Frame | 453 ms | **31 ms** |
| Frames unter 30 fps | 77 von 150 | **0 von 150** |
| Bilddekodierungen beim Scrollen | 939 | **2** |
| Ladezeit | 2,85 s | **0,47 s** |
| Speicher | 199 MB | 249 MB |

Reine Textpassagen lagen vorher wie nachher bei rund 5 ms — das Textlayout war
nie das Problem, und es wächst auch nicht mit der Position im Buch.

Die 50 MB Mehrverbrauch sind der Bildcache. Sein Budget wurde nicht geschätzt,
sondern gemessen: bei 48 MB brach kein Frame ein, bei 24 MB waren es 39 und bei
12 MB wieder 75. Mehr als 48 MB brachte keine weitere Glätte.

Zwei kleinere Korrekturen kamen aus derselben Messung: Bilder werden über
`QImageReader.setScaledSize` gleich in Zielgröße dekodiert statt voll und dann
skaliert (das allein macht das Laden sechsmal schneller), und `apply_typography`
erzwingt kein vollständiges Neulayout mehr, wenn sich weder Schrift noch Breite
geändert haben.

```bash
python tests/bench_reader.py --book "mein-buch.epub"
```

Das Werkzeug meldet Frame-Zeiten getrennt nach Passagen mit und ohne Abbildung
und beendet sich mit Rückgabewert 1, sobald ein Frame ruckelt.

---

## Tests

174 automatisierte Tests, davon 34 auf Widget-Ebene, die das echte Fenster
steuern: jedes Format wird über den realen Ladeweg geöffnet, Suche, Markierungen
und Wiederherstellung der Leseposition werden durchgespielt, und beschädigte
sowie DRM-geschützte Dateien müssen eine verständliche Meldung erzeugen statt
abzustürzen.

Die Testbücher sind **echte Dateien** — ein gültiges ZIP-EPUB, ein
byteweise korrektes PalmDB-MOBI, ein PDF mit stimmiger xref-Tabelle —, damit
die Parser genauso beansprucht werden wie von einem Buch aus dem Handel.

### Prüfstand

Was auf welcher Grundlage geprüft ist:

| | Stand |
|---|---|
| EPUB 2/3, MOBI (KF7), FB2, PDF, CBZ, TXT, MD, HTML, RTF | Automatisiert getestet und von Hand angesehen |
| Windows-Programmdatei | Gebaut, gestartet, öffnet Bücher — geprüft |
| **HUFF/CDIC-Dekompression** | Gegen eine selbstgebaute, formatkonforme Huffman-Tabelle getestet, einschließlich verschachtelter Phrasen. Damit sind Bit-Leser, Tabellenzugriff und Rekursion abgedeckt — **nicht** aber die variablen Codelängen eines echten Verlagsbuchs. |
| **AZW3 / KF8** | Gegen eine selbst erzeugte KF8-Datei getestet (Flow-Schnitt, `kindle:embed`, Anker, TOC). Es lag **keine echte AZW3-Datei aus dem Handel** vor; besonders die Skeleton-/Fragment-Rekonstruktion ist bewusst vereinfacht. Bitte mit einem echten Buch gegenprüfen. |
| macOS- und Linux-Programmdatei | Von der CI auf der jeweiligen Plattform gebaut **und gestartet**. Dort aber nie zum Lesen benutzt — entwickelt wurde auf Windows, alles jenseits von „startet“ ist auf diesen beiden ungeprüft. |
| CBR | Pfad über externe Werkzeuge implementiert; getestet ist die Fehlermeldung, wenn keines vorhanden ist |

---

## Projektdokumente

| Dokument | Sprache |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) — was sich je Version geändert hat | Englisch |
| [SECURITY.md](SECURITY.md) — Bedrohungsmodell und Meldeweg für Sicherheitslücken | Englisch |
| [docs/RELEASING.md](docs/RELEASING.md) — wie ein Release entsteht | Englisch |
| [docs/audit-2026-09-08.md](docs/audit-2026-09-08.md) — Sicherheits- und Qualitätsaudit, 16 Befunde samt Behebung | Deutsch |

---

## Lizenz

GNU General Public License v3.0 oder später — siehe [LICENSE](LICENSE).

Die Oberfläche nutzt Qt über PySide6 unter der LGPL v3. Weil PySide6 dynamisch
gebunden wird, sind die LGPL-Auflagen erfüllt; die Qt-Bibliotheken liegen als
eigene Dateien im Bündel und lassen sich austauschen.
