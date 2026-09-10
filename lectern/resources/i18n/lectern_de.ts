<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE TS>
<TS version="2.1" language="de_DE">
<context>
    <name>Lectern</name>
    <message>
        <location filename="../../app.py" line="95" />
        <source>The library could not be opened:

%s

Lectern starts with a temporary location. Books can be read, but reading positions, bookmarks and notes from this session will not be kept.</source>
        <translation>Die Bibliothek konnte nicht geöffnet werden:

%s

Lectern startet mit einem temporären Speicherort. Bücher lassen sich lesen, aber Leseposition, Lesezeichen und Notizen dieser Sitzung werden nicht dauerhaft gespeichert.</translation>
    </message>
    <message>
        <location filename="../../formats/__init__.py" line="76" />
        <source>The file could not be read: %s</source>
        <extracomment>Everything the file dialog offers, in the order it is shown.</extracomment>
        <translation>Die Datei konnte nicht gelesen werden: %s</translation>
    </message>
    <message>
        <location filename="../../formats/__init__.py" line="79" />
        <source>The file is empty.</source>
        <translation>Die Datei ist leer.</translation>
    </message>
    <message>
        <location filename="../../formats/__init__.py" line="108" />
        <source>The file format was not recognised.

Supported: %s</source>
        <translation>Das Format der Datei wurde nicht erkannt.

Unterstützt werden: %s</translation>
    </message>
    <message>
        <location filename="../../formats/__init__.py" line="147" />
        <source>The file does not exist: %s</source>
        <translation>Die Datei existiert nicht: %s</translation>
    </message>
    <message>
        <location filename="../../formats/__init__.py" line="161" />
        <source>All files (*)</source>
        <translation>Alle Dateien (*)</translation>
    </message>
    <message>
        <location filename="../../formats/base.py" line="163" />
        <source>The file expands to more than %d MB and was refused (at: %s).

That points to a damaged or deliberately crafted file.</source>
        <extracomment>Registry key of the loader that produced this book, e.g. ``"epub"``. Ordered resource keys, only used by :data:`BookKind.COMIC`. Publisher stylesheet, merged only when the user opts in. Non-fatal problems worth surfacing in the status bar. Upper bound on how much a single book may expand to in memory. A 40 MB archive of nothing but zeroes decompresses to about 40 GB, so without a ceiling a merely damaged — let alone deliberately crafted — file drives the machine into swap. The limit is generous: the largest real illustrated books measured here stay under 200 MB.</extracomment>
        <translation>Die Datei entpackt sich auf mehr als %d MB und wurde deshalb abgelehnt (bei: %s).

Das deutet auf eine beschädigte oder absichtlich präparierte Datei hin.</translation>
    </message>
    <message>
        <location filename="../../formats/base.py" line="234" />
        <source>The file declares XML entities and was refused. Books have no use for these; they almost always serve to exhaust the reader's memory.</source>
        <extracomment>Signature of a loader: ``(path, progress) -&gt; Book``.</extracomment>
        <translation>Die Datei enthält XML-Entity-Definitionen und wurde abgelehnt. Bücher brauchen diese nicht; sie dienen fast immer dazu, den Arbeitsspeicher des Lesegeräts zu erschöpfen.</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="44" />
        <source>Opening comic archive…</source>
        <translation>Comic-Archiv wird geöffnet…</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="57" />
        <source>The archive contains no images.</source>
        <translation>Im Archiv wurden keine Bilder gefunden.</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="66" />
        <location filename="../../formats/comic.py" line="77" />
        <location filename="../../formats/comic.py" line="89" />
        <location filename="../../formats/comic.py" line="179" />
        <location filename="../../ui/main_window.py" line="670" />
        <location filename="../../ui/pdf_view.py" line="111" />
        <source>Page %d</source>
        <translation>Seite %d</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="67" />
        <location filename="../../formats/pdf.py" line="72" />
        <source>Done</source>
        <translation>Fertig</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="104" />
        <source>Extracting 7z archive…</source>
        <translation>7z-Archiv wird entpackt…</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="135" />
        <source>This archive needs an external extractor (unrar, bsdtar or 7z), and none was found on this system.

RAR5 cannot be extracted with free software, and the unrar licence forbids shipping the tool.</source>
        <translation>Für dieses Archiv wird ein externes Entpackprogramm benötigt (unrar, bsdtar oder 7z), das auf diesem System nicht gefunden wurde.

Grund: RAR5 lässt sich nicht frei entpacken, und die unrar-Lizenz erlaubt es nicht, das Programm mitzuliefern.</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="140" />
        <source>Extracting archive with %s…</source>
        <translation>Archiv wird mit %s entpackt…</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="153" />
        <source>The extractor %s failed: %s</source>
        <translation>Das Entpackprogramm %s ist fehlgeschlagen: %s</translation>
    </message>
    <message>
        <location filename="../../formats/comic.py" line="156" />
        <source>%s could not extract the archive.
%s</source>
        <translation>%s konnte das Archiv nicht entpacken.
%s</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="63" />
        <source>The file is not a valid EPUB archive.</source>
        <translation>Die Datei ist kein gültiges EPUB-Archiv.</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="130" />
        <source>This EPUB is encrypted and cannot be opened.</source>
        <extracomment>The two font-obfuscation algorithms. Both scramble an embedded typeface so it cannot be lifted out of the book; neither restricts reading, so both are fine to ignore. Anything else in an encryption manifest is real DRM.</extracomment>
        <translation>Dieses EPUB ist verschlüsselt und kann nicht geöffnet werden.</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="144" />
        <source>This EPUB is protected by DRM and cannot be opened.</source>
        <translation>Dieses EPUB ist mit DRM geschützt und kann nicht geöffnet werden.</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="268" />
        <source>Opening EPUB…</source>
        <translation>EPUB wird geöffnet…</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="312" />
        <source>The EPUB contains no readable chapters (empty spine).</source>
        <translation>Das EPUB enthält keine lesbaren Kapitel (leerer Spine).</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="332" />
        <source>Reading resources…</source>
        <translation>Ressourcen werden gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="359" />
        <source>Chapter %d/%d</source>
        <translation>Kapitel %d/%d</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="363" />
        <source>Chapter missing from the archive: %s</source>
        <translation>Kapitel fehlt im Archiv: %s</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="374" />
        <source>Chapter incomplete: a hidden region was never closed: %s</source>
        <translation>Kapitel unvollständig, ein ausgeblendeter Bereich wurde nie geschlossen: %s</translation>
    </message>
    <message>
        <location filename="../../formats/epub.py" line="379" />
        <source>No chapter of the EPUB could be read.</source>
        <translation>Kein Kapitel des EPUBs konnte gelesen werden.</translation>
    </message>
    <message>
        <location filename="../../formats/fb2.py" line="208" />
        <source>Reading FB2…</source>
        <extracomment>FB2 element -&gt; (open tag, close tag). Anything not listed is passed through as a transparent container so no text is ever lost.</extracomment>
        <translation>FB2 wird gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/fb2.py" line="213" />
        <source>The FB2 file is not valid XML: %s</source>
        <translation>Die FB2-Datei ist kein gültiges XML: %s</translation>
    </message>
    <message>
        <location filename="../../formats/fb2.py" line="217" />
        <source>Decoding images…</source>
        <translation>Bilder werden dekodiert…</translation>
    </message>
    <message>
        <location filename="../../formats/fb2.py" line="227" />
        <source>Skipped a damaged image: %s</source>
        <translation>Beschädigtes Bild übersprungen: %s</translation>
    </message>
    <message>
        <location filename="../../formats/fb2.py" line="232" />
        <source>Converting text…</source>
        <translation>Text wird umgewandelt…</translation>
    </message>
    <message>
        <location filename="../../formats/fb2.py" line="236" />
        <source>The FB2 file contains no &lt;body&gt;.</source>
        <translation>Die FB2-Datei enthält keinen &lt;body&gt;.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="56" />
        <source>The file is too small to be a Kindle book.</source>
        <extracomment>Kindle's own base32 alphabet, used inside ``kindle:embed:`` URIs.</extracomment>
        <translation>Die Datei ist zu klein für ein Kindle-Buch.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="62" />
        <source>The Kindle archive contains no records.</source>
        <translation>Das Kindle-Archiv enthält keine Datensätze.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="67" />
        <source>The record table is damaged.</source>
        <translation>Die Datensatz-Tabelle ist beschädigt.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="154" />
        <source>The book's HUFF record is damaged.</source>
        <translation>Der HUFF-Datensatz des Buches ist beschädigt.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="163" />
        <source>Invalid HUFF table in the book.</source>
        <translation>Ungültige HUFF-Tabelle im Buch.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="177" />
        <source>A CDIC record of the book is damaged.</source>
        <translation>Ein CDIC-Datensatz des Buches ist beschädigt.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="192" />
        <source>The book's compression is damaged (recursion).</source>
        <translation>Die Kompression des Buches ist beschädigt (Rekursion).</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="311" />
        <source>The book uses HUFF/CDIC, but the table is missing.</source>
        <translation>Das Buch nutzt HUFF/CDIC, aber die Tabelle fehlt.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="318" />
        <source>The file's HUFF/CDIC table is inconsistent (%d entries announced, %d present).</source>
        <translation>Die HUFF/CDIC-Tabelle der Datei ist widersprüchlich (%d Einträge angekündigt, %d vorhanden).</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="323" />
        <source>Unknown compression method (%d) in the Kindle file.</source>
        <translation>Unbekanntes Kompressionsverfahren (%d) in der Kindle-Datei.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="338" />
        <source>Reading Kindle file…</source>
        <translation>Kindle-Datei wird gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="344" />
        <source>This is not a MOBI/AZW file (wrong PalmDB signature).</source>
        <translation>Das ist keine MOBI-/AZW-Datei (falsche PalmDB-Signatur).</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="351" />
        <source>The book's header record is incomplete.</source>
        <translation>Der Kopfdatensatz des Buches ist unvollständig.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="357" />
        <source>This Kindle file is protected by DRM and cannot be opened.</source>
        <translation>Diese Kindle-Datei ist DRM-geschützt und kann nicht geöffnet werden.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="408" />
        <source>Combined MOBI/KF8 file: the KF8 part was read.</source>
        <translation>Kombinierte MOBI/KF8-Datei: KF8-Teil gelesen.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="428" />
        <source>Decompressing text…</source>
        <translation>Text wird entpackt…</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="437" />
        <source>No readable text was found in the book.</source>
        <translation>Im Buch wurde kein lesbarer Text gefunden.</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="440" />
        <source>Reading images…</source>
        <translation>Bilder werden gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="457" />
        <location filename="../../formats/plaintext.py" line="207" />
        <location filename="../../formats/plaintext.py" line="400" />
        <source>Preparing text…</source>
        <translation>Text wird aufbereitet…</translation>
    </message>
    <message>
        <location filename="../../formats/mobi.py" line="546" />
        <source>The book is incomplete: a hidden region was never closed.</source>
        <translation>Das Buch ist unvollständig: ein ausgeblendeter Bereich wurde nie geschlossen.</translation>
    </message>
    <message>
        <location filename="../../formats/pdf.py" line="39" />
        <source>Checking PDF…</source>
        <translation>PDF wird geprüft…</translation>
    </message>
    <message>
        <location filename="../../formats/pdf.py" line="50" />
        <source>The file does not begin with a PDF signature.</source>
        <translation>Die Datei beginnt nicht mit einer PDF-Signatur.</translation>
    </message>
    <message>
        <location filename="../../formats/pdf.py" line="54" />
        <source>Reading metadata…</source>
        <translation>Metadaten werden gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/pdf.py" line="68" />
        <source>The PDF is encrypted; a password may be required.</source>
        <translation>Das PDF ist verschlüsselt; ggf. wird ein Passwort verlangt.</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="101" />
        <source>Reading text file…</source>
        <extracomment>Tried in order; the first that decodes without loss and without obvious mojibake wins. Explicit BOMs short-circuit the whole list. Lines that name a division outright, in the languages a reader is likely to meet. Matched case-insensitively and anywhere in a short line, because "Erstes Kapitel" puts the keyword second.</extracomment>
        <translation>Textdatei wird gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="139" />
        <source>Reading Markdown…</source>
        <translation>Markdown wird gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="154" />
        <source>Reading HTML…</source>
        <translation>HTML wird gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="167" />
        <source>Loading images…</source>
        <translation>Bilder werden geladen…</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="218" />
        <source>The document is incomplete: a hidden region was never closed.</source>
        <translation>Das Dokument ist unvollständig: ein ausgeblendeter Bereich wurde nie geschlossen.</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="388" />
        <source>Reading RTF…</source>
        <extracomment>Control words whose entire group is metadata rather than body text.</extracomment>
        <translation>RTF wird gelesen…</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="391" />
        <source>The file does not begin with an RTF signature.</source>
        <translation>Die Datei beginnt nicht mit einer RTF-Signatur.</translation>
    </message>
    <message>
        <location filename="../../formats/plaintext.py" line="394" />
        <source>No text could be recovered from the RTF file.</source>
        <translation>Aus der RTF-Datei konnte kein Text gewonnen werden.</translation>
    </message>
    <message>
        <location filename="../../i18n.py" line="130" />
        <source>Use system language</source>
        <extracomment>Translation context for strings outside a QObject. Qt would otherwise use the class name, which those modules do not have. Selectable languages: setting value, and the name shown in the settings dialog. Language names stay in their own language by convention — a German speaker looks for "Deutsch", not for "German". Languages an actual translation file exists for. English is the source and therefore needs none. Kept alive for the life of the process: Qt does not take ownership of an installed translator, and a garbage-collected one silently stops working. Short alias; the parsers and other non-widget modules use this.</extracomment>
        <translation>Systemsprache verwenden</translation>
    </message>
    <message>
        <location filename="../../licensing.py" line="75" />
        <source>This build does not carry the licence text. It is available at https://www.gnu.org/licenses/.</source>
        <extracomment>Component, the licence it is used under, and the file holding that licence. The application comes first; everything after it is somebody else's work. Where the unmodified sources of the shipped libraries can be had. Required by the LGPL, and useful to anyone who wants to rebuild with their own Qt. In a source checkout the files have not been collected yet. The GPL is the repository's own LICENSE — kept at the top level because that is where GitHub and every other tool looks for it — and only the LGPL sits under ``licenses/``. Duplicating 35 kB of licence text to make the two layouts identical would be the kind of copy that quietly drifts apart.</extracomment>
        <translation>Dieser Build trägt den Lizenztext nicht. Er steht unter https://www.gnu.org/licenses/ bereit.</translation>
    </message>
    <message>
        <location filename="../../storage/db.py" line="263" />
        <source># Notes on %s</source>
        <extracomment>Set once a write has failed, so the window can say so exactly once instead of losing the reading position without a word.</extracomment>
        <translation># Notizen zu %s</translation>
    </message>
    <message>
        <location filename="../../storage/db.py" line="266" />
        <source>## Bookmarks</source>
        <translation>## Lesezeichen</translation>
    </message>
    <message>
        <location filename="../../storage/db.py" line="269" />
        <source>Bookmark</source>
        <translation>Lesezeichen</translation>
    </message>
    <message>
        <location filename="../../storage/db.py" line="274" />
        <source>## Highlights</source>
        <translation>## Markierungen</translation>
    </message>
    <message>
        <location filename="../../storage/db.py" line="286" />
        <source>_No annotations yet._</source>
        <translation>_Keine Anmerkungen vorhanden._</translation>
    </message>
    <message>
        <location filename="../../ui/licences_dialog.py" line="30" />
        <source>Licences</source>
        <translation>Lizenzen</translation>
    </message>
    <message>
        <location filename="../../ui/licences_dialog.py" line="35" />
        <source>Overview</source>
        <translation>Überblick</translation>
    </message>
    <message>
        <location filename="../../ui/licences_dialog.py" line="46" />
        <source>This program is made of the following parts:</source>
        <translation>Dieses Programm besteht aus den folgenden Teilen:</translation>
    </message>
    <message>
        <location filename="../../ui/licences_dialog.py" line="49" />
        <source>The unmodified sources of the libraries are available at:</source>
        <translation>Die unveränderten Quellen der Bibliotheken liegen hier:</translation>
    </message>
    <message>
        <location filename="../../ui/licences_dialog.py" line="52" />
        <source>The Qt libraries are shipped as separate files and may be replaced. In the single-file build they are packed into the executable; rebuilding from source is the way to substitute them there.</source>
        <translation>Die Qt-Bibliotheken liegen als eigene Dateien vor und lassen sich austauschen. In der Einzeldatei stecken sie in der ausführbaren Datei; dort führt der Weg über einen Neubau aus dem Quelltext.</translation>
    </message>
    <message>
        <location filename="../../ui/loader.py" line="42" />
        <source>Assembling document…</source>
        <translation>Dokument wird zusammengesetzt…</translation>
    </message>
    <message>
        <location filename="../../ui/loader.py" line="52" />
        <source>An unexpected error occurred while opening:
%s</source>
        <translation>Beim Öffnen ist ein unerwarteter Fehler aufgetreten:
%s</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="146" />
        <source>Contents</source>
        <extracomment>Reading position is written at most this often, to spare the disk. (character position, TOC target) pairs, sorted, so the outline can follow along while reading. Empty for page-based views. Guards the storage-failure dialog; the save timer fires every four seconds and must not produce a dialog each time.</extracomment>
        <translation>Inhalt</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="147" />
        <location filename="../../ui/main_window.py" line="674" />
        <source>Bookmarks</source>
        <translation>Lesezeichen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="148" />
        <location filename="../../ui/main_window.py" line="1157" />
        <source>Notes</source>
        <translation>Notizen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="149" />
        <source>Search</source>
        <translation>Suche</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="158" />
        <source>&amp;File</source>
        <translation>&amp;Datei</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="159" />
        <source>Open…</source>
        <translation>Öffnen…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="161" />
        <location filename="../../ui/settings_dialog.py" line="156" />
        <source>Recently opened</source>
        <translation>Zuletzt geöffnet</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="165" />
        <source>Close book</source>
        <translation>Buch schließen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="168" />
        <source>Export annotations…</source>
        <translation>Anmerkungen exportieren…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="172" />
        <source>Quit</source>
        <translation>Beenden</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="175" />
        <source>&amp;Navigation</source>
        <translation>&amp;Navigation</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="176" />
        <source>Next page</source>
        <translation>Nächste Seite</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="178" />
        <source>Previous page</source>
        <translation>Vorherige Seite</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="183" />
        <source>Beginning</source>
        <translation>Anfang</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="185" />
        <source>End</source>
        <translation>Ende</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="188" />
        <source>Go to…</source>
        <translation>Gehe zu…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="191" />
        <source>Find…</source>
        <translation>Suchen…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="193" />
        <source>Next match</source>
        <translation>Nächster Treffer</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="195" />
        <source>Previous match</source>
        <translation>Vorheriger Treffer</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="201" />
        <source>&amp;Annotations</source>
        <translation>&amp;Anmerkungen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="202" />
        <source>Add bookmark</source>
        <translation>Lesezeichen setzen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="205" />
        <source>Highlight selection</source>
        <translation>Auswahl markieren</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="208" />
        <location filename="../../ui/main_window.py" line="965" />
        <source>Highlight in colour</source>
        <translation>Markieren in Farbe</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="214" />
        <source>Copy selection</source>
        <translation>Auswahl kopieren</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="219" />
        <source>&amp;View</source>
        <translation>&amp;Ansicht</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="220" />
        <location filename="../../ui/settings_dialog.py" line="130" />
        <source>Colour scheme</source>
        <translation>Farbschema</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="233" />
        <source>Zoom in</source>
        <translation>Vergrößern</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="235" />
        <source>Zoom out</source>
        <translation>Verkleinern</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="237" />
        <source>Reset zoom</source>
        <translation>Zoom zurücksetzen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="241" />
        <source>Sidebar</source>
        <translation>Seitenleiste</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="247" />
        <source>Full screen</source>
        <translation>Vollbild</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="252" />
        <source>Settings…</source>
        <translation>Einstellungen…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="256" />
        <source>&amp;Help</source>
        <translation>&amp;Hilfe</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="257" />
        <location filename="../../ui/main_window.py" line="1034" />
        <source>Keyboard shortcuts</source>
        <translation>Tastenkürzel</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="259" />
        <source>Licences…</source>
        <translation>Lizenzen…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="260" />
        <location filename="../../ui/main_window.py" line="1041" />
        <source>About %s</source>
        <translation>Über %s</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="317" />
        <source>Open e-book</source>
        <translation>E-Book öffnen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="328" />
        <source>Opening %s…</source>
        <translation>Öffne %s…</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="421" />
        <source>This PDF is password protected.
Password:</source>
        <translation>Dieses PDF ist passwortgeschützt.
Passwort:</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="422" />
        <source>Wrong password. Please try again:</source>
        <translation>Passwort falsch. Bitte erneut versuchen:</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="424" />
        <source>Password required</source>
        <translation>Passwort erforderlich</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="430" />
        <source>The PDF could not be opened with this password.</source>
        <translation>Das PDF konnte mit diesem Passwort nicht geöffnet werden.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="495" />
        <source>The book could not be opened</source>
        <translation>Buch konnte nicht geöffnet werden</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="575" />
        <source>Go to page</source>
        <translation>Gehe zu Seite</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="575" />
        <source>Page (1–%d):</source>
        <translation>Seite (1–%d):</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="582" />
        <source>Position in the book (%):</source>
        <translation>Position im Buch (%):</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="594" />
        <location filename="../../ui/main_window.py" line="601" />
        <source>Page %d/%d · %d %%</source>
        <translation>Seite %d/%d · %d %%</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="645" />
        <source>Reading position cannot be saved — the library is not writable.</source>
        <translation>Leseposition kann nicht gespeichert werden — Bibliothek nicht beschreibbar.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="650" />
        <source>Cannot save</source>
        <translation>Speichern nicht möglich</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="652" />
        <source>The reading position cannot be saved.

The library file is locked or read-only:
%s

Reading still works, but positions, bookmarks and highlights from this session will be lost.</source>
        <translation>Die Leseposition lässt sich nicht speichern.

Die Bibliotheksdatei ist gesperrt oder schreibgeschützt:
%s

Das Lesen funktioniert weiter, aber Positionen, Lesezeichen und Markierungen dieser Sitzung gehen verloren.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="674" />
        <source>Label:</source>
        <translation>Beschriftung:</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="680" />
        <source>Bookmark added.</source>
        <translation>Lesezeichen gesetzt.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="691" />
        <source>Select text first, then highlight.</source>
        <translation>Erst Text auswählen, dann markieren.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="696" />
        <source>Highlight saved.</source>
        <translation>Markierung gespeichert.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="731" />
        <source>Export annotations</source>
        <translation>Anmerkungen exportieren</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="731" />
        <source>Markdown (*.md);;All files (*)</source>
        <translation>Markdown (*.md);;Alle Dateien (*)</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="739" />
        <source>Export failed</source>
        <translation>Export fehlgeschlagen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="741" />
        <source>Annotations saved: %s</source>
        <translation>Anmerkungen gespeichert: %s</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="758" />
        <source>p. %d — %s</source>
        <translation>S. %d — %s</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="840" />
        <source>Zoom: fit to width</source>
        <translation>Zoom: an Breite angepasst</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="855" />
        <source>Zoom: %d %%</source>
        <translation>Zoom: %d %%</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="865" />
        <source>Font size: %d pt</source>
        <translation>Schriftgröße: %d pt</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="997" />
        <source>(nothing opened yet)</source>
        <translation>(noch nichts geöffnet)</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="1006" />
        <location filename="../../ui/main_window.py" line="1010" />
        <source>Clear list</source>
        <translation>Liste leeren</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="1011" />
        <source>Remove all recently opened books?

Reading positions, bookmarks and highlights will be lost.</source>
        <translation>Alle zuletzt geöffneten Bücher entfernen?

Lesepositionen, Lesezeichen und Markierungen gehen dabei verloren.</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="1026" />
        <source>Open link</source>
        <translation>Link öffnen</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="1027" />
        <source>Open this link in the browser?

%s</source>
        <translation>Diesen Link im Browser öffnen?

%s</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="1042" />
        <source>&lt;h3&gt;%s %s&lt;/h3&gt;&lt;p&gt;A free e-book reader for EPUB, Kindle formats, FB2, PDF, comics, text, Markdown, HTML and RTF.&lt;/p&gt;&lt;p&gt;Licence: GNU GPL v3 or later.&lt;br&gt;Interface: Qt (PySide6, LGPL v3).&lt;/p&gt;&lt;p&gt;The full texts are under Help → Licences.&lt;/p&gt;</source>
        <translation>&lt;h3&gt;%s %s&lt;/h3&gt;&lt;p&gt;Ein freier E-Book-Reader für EPUB, Kindle-Formate, FB2, PDF, Comics, Text, Markdown, HTML und RTF.&lt;/p&gt;&lt;p&gt;Lizenz: GNU GPL v3 oder später.&lt;br&gt;Oberfläche: Qt (PySide6, LGPL v3).&lt;/p&gt;&lt;p&gt;Die vollständigen Texte stehen unter Hilfe → Lizenzen.&lt;/p&gt;</translation>
    </message>
    <message>
        <location filename="../../ui/main_window.py" line="1111" />
        <source>Reading
    Space / Page Down / →        Next page
    Backspace / Page Up / ←      Previous page
    Ctrl+Home / Ctrl+End         Beginning / end
    Ctrl+G                       Go to page or position

Searching
    Ctrl+F                       Open search
    F3 / Shift+F3                Next / previous match
    Esc                          Leave search, leave full screen

Annotations
    Ctrl+B                       Add bookmark
    Ctrl+H                       Highlight selection
    Ctrl+C                       Copy selection

View
    Ctrl++ / Ctrl+−              Larger / smaller type
    Ctrl+0                       Reset font size
    F9                           Show/hide the sidebar
    F11                          Full screen
    Ctrl+,                       Settings

Files
    Ctrl+O                       Open book
    Ctrl+W                       Close book
</source>
        <translation>Lesen
    Leertaste / Bild ab / →      Nächste Seite
    Rücktaste / Bild auf / ←     Vorherige Seite
    Strg+Pos1 / Strg+Ende        Anfang / Ende
    Strg+G                       Gehe zu Seite oder Position

Suchen
    Strg+F                       Suche öffnen
    F3 / Umschalt+F3             Nächster / vorheriger Treffer
    Esc                          Suche beenden, Vollbild verlassen

Anmerkungen
    Strg+B                       Lesezeichen setzen
    Strg+H                       Auswahl markieren
    Strg+C                       Auswahl kopieren

Ansicht
    Strg++ / Strg+−              Schrift größer / kleiner
    Strg+0                       Schriftgröße zurücksetzen
    F9                           Seitenleiste ein-/ausblenden
    F11                          Vollbild
    Strg+,                       Einstellungen

Dateien
    Strg+O                       Buch öffnen
    Strg+W                       Buch schließen
</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="107" />
        <source>No bookmarks yet.
Add one with Ctrl+B.</source>
        <translation>Noch keine Lesezeichen.
Mit Strg+B setzen.</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="131" />
        <source>Delete bookmark</source>
        <translation>Lesezeichen löschen</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="158" />
        <source>No highlights yet.

Select text and press Ctrl+H.</source>
        <translation>Noch keine Markierungen.

Text auswählen und Strg+H drücken.</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="163" />
        <source>Export as Markdown…</source>
        <translation>Als Markdown exportieren…</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="197" />
        <source>Edit note…</source>
        <translation>Notiz bearbeiten…</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="198" />
        <source>Colour</source>
        <translation>Farbe</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="204" />
        <source>Delete highlight</source>
        <translation>Markierung löschen</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="230" />
        <source>Search in the book…</source>
        <translation>Im Buch suchen…</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="237" />
        <source>Close search (Esc)</source>
        <translation>Suche schließen (Esc)</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="243" />
        <source>Match case</source>
        <translation>Groß/klein</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="244" />
        <source>Whole word</source>
        <translation>Ganzes Wort</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="281" />
        <source>No matches for “%s”.</source>
        <translation>Keine Treffer für „%s“.</translation>
    </message>
    <message>
        <location filename="../../ui/panels.py" line="283" />
        <source>%d matches for “%s”.</source>
        <translation>%d Treffer für „%s“.</translation>
    </message>
    <message>
        <location filename="../../ui/pdf_view.py" line="53" />
        <source>The PDF is password protected.</source>
        <translation>Das PDF ist passwortgeschützt.</translation>
    </message>
    <message>
        <location filename="../../ui/pdf_view.py" line="55" />
        <source>The PDF could not be opened (%s).</source>
        <translation>Das PDF konnte nicht geöffnet werden (%s).</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="40" />
        <source>Settings</source>
        <translation>Einstellungen</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="45" />
        <source>Typography</source>
        <translation>Typografie</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="46" />
        <source>Reading</source>
        <translation>Lesen</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="67" />
        <source>Font</source>
        <translation>Schriftart</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="74" />
        <source>Font size</source>
        <translation>Schriftgröße</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="83" />
        <source>Line height</source>
        <translation>Zeilenabstand</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="92" />
        <source>Paragraph spacing</source>
        <translation>Absatzabstand</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="99" />
        <source>Page margin</source>
        <translation>Seitenrand</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="103" />
        <source> characters</source>
        <translation> Zeichen</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="104" />
        <source>unlimited</source>
        <translation>unbegrenzt</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="107" />
        <source>Maximum line length. Long lines are the commonest reason for the eye
losing its place at the end of a line.</source>
        <translation>Maximale Zeilenlänge. Lange Zeilen sind der häufigste Grund dafür,
dass die Augen beim Zeilenwechsel die Spur verlieren.</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="111" />
        <source>Line width</source>
        <translation>Zeilenbreite</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="113" />
        <source>Justify</source>
        <translation>Blocksatz</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="132" />
        <source>Use the publisher's stylesheet</source>
        <translation>Stylesheet des Verlags mitverwenden</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="135" />
        <source>Qt understands only part of CSS. Publisher stylesheets can make a book
look better — or considerably worse. When in doubt, leave this off.</source>
        <translation>Qt versteht nur einen Teil von CSS. Verlags-Stylesheets können damit
besser aussehen — oder deutlich schlechter. Im Zweifel ausgeschaltet lassen.</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="139" />
        <source>EPUB</source>
        <translation>EPUB</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="142" />
        <source>Fit width</source>
        <translation>Breite anpassen</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="142" />
        <source>Fit height</source>
        <translation>Höhe anpassen</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="143" />
        <source>Whole page</source>
        <translation>Ganze Seite</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="143" />
        <source>Original size</source>
        <translation>Originalgröße</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="150" />
        <source>Comics</source>
        <translation>Comics</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="159" />
        <source>Automatic</source>
        <translation>Automatisch</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="159" />
        <source>On</source>
        <translation>An</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="159" />
        <source>Off</source>
        <translation>Aus</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="163" />
        <source>Larger buttons and list rows for use with a finger.
Automatic switches this on when a touch screen is present.</source>
        <translation>Größere Schaltflächen und Listenzeilen für die Bedienung mit dem Finger.
Automatisch schaltet das ein, wenn ein Touchscreen vorhanden ist.</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="169" />
        <source>Touch operation</source>
        <translation>Touch-Bedienung</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="177" />
        <source>Language</source>
        <translation>Sprache</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="180" />
        <source>The language takes effect after restarting Lectern.</source>
        <translation>Die Sprache wirkt sich nach einem Neustart von Lectern aus.</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="187" />
        <source>Settings and reading progress live in:
%s</source>
        <translation>Einstellungen und Lesefortschritt liegen unter:
%s</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="221" />
        <source>Reset</source>
        <translation>Zurücksetzen</translation>
    </message>
    <message>
        <location filename="../../ui/settings_dialog.py" line="221" />
        <source>Reset all display settings?</source>
        <translation>Alle Anzeige-Einstellungen zurücksetzen?</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="53" />
        <source>Open book…</source>
        <translation>Buch öffnen…</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="60" />
        <source>Recently read</source>
        <translation>Zuletzt gelesen</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="76" />
        <source>Nothing read yet. Open a book, or drag a file into this window.</source>
        <translation>Noch nichts gelesen. Öffne ein Buch oder zieh eine Datei in dieses Fenster.</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="93" />
        <source>File missing</source>
        <translation>Datei fehlt</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="119" />
        <source>Open</source>
        <translation>Öffnen</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="120" />
        <source>Show folder</source>
        <translation>Ordner anzeigen</translation>
    </message>
    <message>
        <location filename="../../ui/welcome.py" line="122" />
        <source>Remove from the list</source>
        <translation>Aus der Liste entfernen</translation>
    </message>
</context>
</TS>