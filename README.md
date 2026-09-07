# OpenReader

Ein freier E-Book-Reader als **eine einzige Programmdatei** — kein Installer,
keine Laufzeitumgebung, kein Browser. Herunterladen, starten, lesen.

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
| **Comics** | `.cbz` `.cbt` `.cb7` `.cbr` | Natürliche Seitensortierung, Anpassungsmodi |
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

Es gibt keine. Datei herunterladen, ausführen.

| Plattform | Datei | Hinweis |
|---|---|---|
| Windows 10/11 (x64) | `OpenReader-*-windows-x86_64.exe` | Doppelklick |
| macOS (Apple Silicon) | `OpenReader-*-macos-arm64.zip` | Entpacken, dann Rechtsklick → „Öffnen“ (nicht signiert) |
| Linux (x64, glibc ≥ 2.35) | `OpenReader-*-linux-x86_64` | `chmod +x` und starten |

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
python -m pytest                         # 109 Tests
python tests/smoke_gui.py --visible      # Screenshots aller Ansichten
pyinstaller build/openreader.spec --noconfirm --distpath build/dist
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

**Warum wird die Zeilenhöhe bei Bildern zurückgesetzt?**
Ein relativer `line-height` multipliziert die Höhe des größten Elements einer
Zeile. Eine 320 px hohe Abbildung in einem 155-%-Absatz belegt sonst 496 px und
hinterlässt ein Loch. Blöcke mit Bildern bekommen deshalb nachträglich 100 %
Zeilenhöhe — und werden gleich mittig gesetzt.

---

## Tests

109 automatisierte Tests, davon 26 auf Widget-Ebene, die das echte Fenster
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
| macOS- und Linux-Programmdatei | Über CI-Workflow vorbereitet, **hier nicht ausgeführt** — es stand nur ein Windows-Rechner zur Verfügung |
| CBR | Pfad über externe Werkzeuge implementiert; getestet ist die Fehlermeldung, wenn keines vorhanden ist |

---

## Lizenz

GNU General Public License v3.0 oder später — siehe [LICENSE](LICENSE).

Die Oberfläche nutzt Qt über PySide6 unter der LGPL v3. Weil PySide6 dynamisch
gebunden wird, sind die LGPL-Auflagen erfüllt; die Qt-Bibliotheken liegen als
eigene Dateien im Bündel und lassen sich austauschen.
