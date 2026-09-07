"""Generate real sample books for every supported format.

The samples are byte-level valid files (real ZIP containers, a real PalmDB
MOBI, a real PDF), so the loaders are exercised the same way they would be by a
book from a shop rather than by a mock.  Public-domain text only.
"""

from __future__ import annotations

import os
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "samples")

TEXT_1 = (
    "Es war einmal ein Kaiser, der neue Kleider über alles liebte. "
    "Er gab all sein Geld dafür aus, recht geputzt zu sein."
)
TEXT_2 = (
    "Eines Tages kamen zwei Betrüger in die Stadt. Sie gaben vor, Weber zu sein, "
    "und behaupteten, den schönsten Stoff weben zu können."
)


def _make_png(width: int = 240, height: int = 320, rgb: tuple = (74, 110, 155)) -> bytes:
    """Build a valid PNG without Pillow, CRCs included."""

    import struct as _struct
    import zlib

    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter type: none
        for column in range(width):
            # A soft diagonal gradient, so scaling artefacts stay visible.
            shade = (row + column) % 96
            raw += bytes((
                min(255, rgb[0] + shade), min(255, rgb[1] + shade), min(255, rgb[2] + shade),
            ))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (_struct.pack(">I", len(payload)) + tag + payload
                + _struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = _struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


#: A small but genuine PNG used wherever the samples need an image.
PNG = _make_png()


def _ensure_out() -> None:
    os.makedirs(OUT, exist_ok=True)


# --------------------------------------------------------------------------
# EPUB
# --------------------------------------------------------------------------
def make_epub(name: str = "sample.epub", *, epub3: bool = True) -> str:
    path = os.path.join(OUT, name)
    ch1 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Erstes Kapitel</title>
<link rel="stylesheet" href="style.css"/></head><body>
<section epub:type="chapter" id="kap1"><h1>Erstes Kapitel</h1>
<p>%s</p><figure><img src="images/bild.png" alt="Ein Bild"/>
<figcaption>Abbildung 1</figcaption></figure>
<p>Weiter zu <a href="ch2.xhtml#kap2">Kapitel 2</a>.</p></section></body></html>""" % TEXT_1
    ch2 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Zweites Kapitel</title></head>
<body><section id="kap2"><h1>Zweites Kapitel</h1><p>%s</p>
<blockquote><p>Ein Zitat mit <em>Betonung</em> und <strong>Nachdruck</strong>.</p></blockquote>
<table border="1"><tr><th>Spalte A</th><th>Spalte B</th></tr>
<tr><td>1</td><td>2</td></tr></table></section></body></html>""" % TEXT_2
    cover = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Cover</title></head><body>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
 viewBox="0 0 600 800"><image width="600" height="800" xlink:href="images/bild.png"/>
</svg></body></html>"""

    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="%s" unique-identifier="bid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Des Kaisers neue Kleider</dc:title>
<dc:creator>Hans Christian Andersen</dc:creator>
<dc:language>de</dc:language>
<dc:publisher>OpenReader Testsuite</dc:publisher>
<dc:date>1837-04-07</dc:date>
<dc:identifier id="bid">urn:uuid:openreader-sample-0001</dc:identifier>
<dc:subject>Märchen</dc:subject>
<meta name="cover" content="img"/>
%s
</metadata>
<manifest>
<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>
<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
<item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
<item id="img" href="images/bild.png" media-type="image/png" properties="cover-image"/>
<item id="css" href="style.css" media-type="text/css"/>
%s
</manifest>
<spine %s>
<itemref idref="cover"/><itemref idref="c1"/><itemref idref="c2"/>
</spine>
</package>"""

    ncx = """<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head/>
<docTitle><text>Des Kaisers neue Kleider</text></docTitle>
<navMap>
<navPoint id="n1" playOrder="1"><navLabel><text>Erstes Kapitel</text></navLabel>
<content src="ch1.xhtml#kap1"/></navPoint>
<navPoint id="n2" playOrder="2"><navLabel><text>Zweites Kapitel</text></navLabel>
<content src="ch2.xhtml#kap2"/></navPoint>
</navMap></ncx>"""

    nav = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Inhalt</title></head><body>
<nav epub:type="toc" id="toc"><h1>Inhalt</h1><ol>
<li><a href="ch1.xhtml#kap1">Erstes Kapitel</a></li>
<li><a href="ch2.xhtml#kap2">Zweites Kapitel</a>
<ol><li><a href="ch2.xhtml#kap2">Das Zitat</a></li></ol></li>
</ol></nav></body></html>"""

    if epub3:
        opf_text = opf % (
            "3.0",
            '<meta property="belongs-to-collection">Märchensammlung</meta>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            'toc="ncx"',
        )
    else:
        opf_text = opf % (
            "2.0",
            "",
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            'toc="ncx"',
        )

    _ensure_out()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # The mimetype entry must be first and stored uncompressed.
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                    compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml",
                    '<?xml version="1.0"?>\n'
                    '<container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles></container>')
        zf.writestr("OEBPS/content.opf", opf_text)
        zf.writestr("OEBPS/toc.ncx", ncx)
        if epub3:
            zf.writestr("OEBPS/nav.xhtml", nav)
        zf.writestr("OEBPS/cover.xhtml", cover)
        zf.writestr("OEBPS/ch1.xhtml", ch1)
        zf.writestr("OEBPS/ch2.xhtml", ch2)
        zf.writestr("OEBPS/style.css", "p { text-indent: 1.2em; } h1 { color: #333; }")
        zf.writestr("OEBPS/images/bild.png", PNG)
    return path


def make_drm_epub(name: str = "drm.epub") -> str:
    path = os.path.join(OUT, name)
    _ensure_out()
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                    compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml",
                    '<container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles></container>')
        zf.writestr("META-INF/encryption.xml",
                    '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<EncryptedData xmlns="http://www.w3.org/2001/04/xmlenc#">'
                    '<CipherData><CipherReference URI="ch1.xhtml"/></CipherData>'
                    '</EncryptedData></encryption>')
        zf.writestr("content.opf", "<package/>")
    return path


# --------------------------------------------------------------------------
# FB2
# --------------------------------------------------------------------------
def make_fb2(name: str = "sample.fb2") -> str:
    import base64

    path = os.path.join(OUT, name)
    doc = """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
             xmlns:l="http://www.w3.org/1999/xlink">
<description><title-info>
<genre>sf</genre>
<author><first-name>Hans Christian</first-name><last-name>Andersen</last-name></author>
<book-title>Des Kaisers neue Kleider (FB2)</book-title>
<annotation><p>Ein Testbuch im FB2-Format.</p></annotation>
<lang>de</lang>
<coverpage><image l:href="#cover.png"/></coverpage>
</title-info></description>
<body>
<section id="s1"><title><p>Erstes Kapitel</p></title>
<p>%s</p>
<empty-line/>
<p>Mit <emphasis>Betonung</emphasis> und <strong>Nachdruck</strong>.</p>
<image l:href="#cover.png"/>
</section>
<section id="s2"><title><p>Zweites Kapitel</p></title>
<p>%s</p>
<cite><p>Ein Zitat.</p></cite>
<poem><stanza><v>Erste Zeile</v><v>Zweite Zeile</v></stanza></poem>
</section>
</body>
<binary id="cover.png" content-type="image/png">%s</binary>
</FictionBook>""" % (TEXT_1, TEXT_2, base64.b64encode(PNG).decode("ascii"))
    _ensure_out()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(doc)
    return path


def make_fb2_zip(name: str = "sample.fb2.zip") -> str:
    path = os.path.join(OUT, name)
    inner = make_fb2("_tmp.fb2")
    _ensure_out()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(inner, "sample.fb2")
    os.remove(inner)
    return path


# --------------------------------------------------------------------------
# MOBI (PalmDOC compression, KF7)
# --------------------------------------------------------------------------
def _palmdoc_compress(data: bytes) -> bytes:
    """Minimal but valid PalmDOC LZ77: literals only, with the required escaping."""

    out = bytearray()
    for byte in data:
        if byte == 0 or 0x09 <= byte <= 0x7F:
            out.append(byte)
        else:
            # Escape: literal-run marker of length 1.
            out.append(1)
            out.append(byte)
    return bytes(out)


def make_azw3(name: str = "sample.azw3") -> str:
    """A KF8 file: MOBI file version 8, kindle:embed image URIs, trailing flows.

    Real AZW3 files reassemble the text from skeleton and fragment indices; the
    reader instead takes flow 0 up to ``</html>``, which is what this sample
    reproduces — main document first, then the CSS flow that must be discarded.
    """

    html = (
        "<html><head><title>Des Kaisers neue Kleider (KF8)</title></head><body>"
        '<div id="kap1"><h1>Erstes Kapitel</h1><p>' + TEXT_1 + "</p>"
        '<img src="kindle:embed:0001?mime=image/png"/></div>'
        '<div id="kap2"><h1>Zweites Kapitel</h1><p>' + TEXT_2 + "</p></div>"
        "</body></html>"
        # Everything past </html> is a separate flow and must not be shown.
        "body { font-family: serif; } .kapitel { page-break-before: always; }"
    ).encode("utf-8")

    return _write_palmdb(
        os.path.join(OUT, name), html,
        title=b"Des Kaisers neue Kleider (KF8)",
        author=b"Hans Christian Andersen",
        file_version=8,
    )


def _write_palmdb(
    path: str,
    html: bytes,
    *,
    title: bytes,
    author: bytes,
    file_version: int,
    publisher: bytes = b"OpenReader",
) -> str:
    """Assemble a complete PalmDB/MOBI container around ``html``.

    Header offsets are given relative to the MOBI magic, which sits 16 bytes
    into record 0, matching how the loader reads them back.
    """

    record_size = 4096
    chunks = [html[i:i + record_size] for i in range(0, len(html), record_size)]
    text_records = [_palmdoc_compress(chunk) for chunk in chunks]

    def exth_record(tag: int, value: bytes) -> bytes:
        return struct.pack(">II", tag, len(value) + 8) + value

    exth_body = (exth_record(100, author) + exth_record(503, title)
                 + exth_record(101, publisher))
    exth = b"EXTH" + struct.pack(">II", len(exth_body) + 12, 3) + exth_body
    exth += b"\0" * ((4 - len(exth) % 4) % 4)

    palmdoc = struct.pack(">HHIHHHH", 2, 0, len(html), len(chunks), record_size, 0, 0)
    mobi_header_len = 232
    full_name_offset = 16 + mobi_header_len + len(exth)

    mobi = bytearray(b"\0" * mobi_header_len)
    mobi[0:4] = b"MOBI"
    mobi[4:8] = struct.pack(">I", mobi_header_len)
    mobi[8:12] = struct.pack(">I", 2)                   # 0x08 book type: text
    mobi[12:16] = struct.pack(">I", 65001)              # 0x0C encoding: UTF-8
    mobi[16:20] = struct.pack(">I", 0x12345678)         # 0x10 unique id
    mobi[20:24] = struct.pack(">I", file_version)       # 0x14 file version
    mobi[64:68] = struct.pack(">I", 0xFFFFFFFF)         # 0x40 first non-book index
    mobi[68:72] = struct.pack(">I", full_name_offset)   # 0x44 full name offset
    mobi[72:76] = struct.pack(">I", len(title))         # 0x48 full name length
    mobi[76:80] = struct.pack(">I", 9)                  # 0x4C locale: de
    mobi[92:96] = struct.pack(">I", len(chunks) + 1)    # 0x5C first resource record
    mobi[112:116] = struct.pack(">I", 0x40)             # 0x70 EXTH present

    record0 = bytes(palmdoc) + bytes(mobi) + exth + title + b"\0" * 2
    records = [record0] + text_records + [PNG]

    count = len(records)
    header = bytearray(78)
    header[0:len(title[:31])] = title[:31]
    header[32:34] = struct.pack(">H", 0)   # attributes
    header[34:36] = struct.pack(">H", 1)   # version
    header[60:64] = b"BOOK"
    header[64:68] = b"MOBI"
    header[76:78] = struct.pack(">H", count)

    offset = 78 + count * 8 + 2
    entries = bytearray()
    for index, record in enumerate(records):
        entries += struct.pack(">IBBH", offset, 0, 0, index)
        offset += len(record)

    _ensure_out()
    with open(path, "wb") as handle:
        handle.write(bytes(header))
        handle.write(bytes(entries))
        handle.write(b"\0\0")
        for record in records:
            handle.write(record)
    return path


def make_mobi(name: str = "sample.mobi") -> str:
    html = (
        "<html><head><guide><reference type='toc' title='Inhalt' filepos='0'/></guide>"
        "</head><body>"
        "<h1>Erstes Kapitel</h1><p>" + TEXT_1 + "</p>"
        '<img recindex="00001" width="100"/>'
        "<mbp:pagebreak/>"
        "<h1>Zweites Kapitel</h1><p>" + TEXT_2 + "</p>"
        "</body></html>"
    ).encode("utf-8")

    return _write_palmdb(
        os.path.join(OUT, name), html,
        title=b"Des Kaisers neue Kleider (MOBI)",
        author=b"Hans Christian Andersen",
        file_version=6,
    )


# --------------------------------------------------------------------------
# Comics, plain text, HTML, RTF, PDF
# --------------------------------------------------------------------------
def make_cbz(name: str = "sample.cbz") -> str:
    path = os.path.join(OUT, name)
    _ensure_out()
    with zipfile.ZipFile(path, "w") as zf:
        # Deliberately unsorted and mixed-width to exercise natural sorting.
        for entry in ["page10.png", "page2.png", "page1.png", "cover.txt"]:
            zf.writestr(entry, PNG if entry.endswith(".png") else b"ignore me")
    return path


def make_txt(name: str = "sample.txt", encoding: str = "utf-8") -> str:
    path = os.path.join(OUT, name)
    _ensure_out()
    body = (
        "DES KAISERS NEUE KLEIDER\n\n\n"
        "Erstes Kapitel\n\n" + TEXT_1 + "\n\n"
        "Zweites Kapitel\n\n" + TEXT_2 + "\n"
    )
    with open(path, "w", encoding=encoding) as handle:
        handle.write(body)
    return path


def make_html(name: str = "sample.html") -> str:
    path = os.path.join(OUT, name)
    _ensure_out()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Ein HTML-Buch</title></head><body>"
            "<h1>Erstes Kapitel</h1><p>" + TEXT_1 + "</p>"
            "<h1>Zweites Kapitel</h1><p>" + TEXT_2 + "</p></body></html>"
        )
    return path


def make_markdown(name: str = "sample.md") -> str:
    path = os.path.join(OUT, name)
    _ensure_out()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(
            "# Des Kaisers neue Kleider\n\n## Erstes Kapitel\n\n" + TEXT_1 +
            "\n\n## Zweites Kapitel\n\n" + TEXT_2 + "\n\n"
            "> Ein Zitat\n\n- Punkt eins\n- Punkt zwei\n"
        )
    return path


def make_rtf(name: str = "sample.rtf") -> str:
    path = os.path.join(OUT, name)
    _ensure_out()
    body = (
        r"{\rtf1\ansi\ansicpg1252\deff0"
        r"{\fonttbl{\f0 Times New Roman;}}"
        r"{\info{\title Des Kaisers neue Kleider (RTF)}{\author Andersen}}"
        r"\f0\fs24 "
        r"{\b\fs32 Erstes Kapitel}\par\par "
        + TEXT_1.replace("ü", r"\'fc").replace("ä", r"\'e4").replace("ö", r"\'f6")
        + r"\par\par "
        r"{\b\fs32 Zweites Kapitel}\par\par "
        r"Mit {\i Betonung} und {\b Nachdruck}. Ein Umlaut: \u252?berall.\par"
        r"}"
    )
    with open(path, "w", encoding="ascii", errors="replace") as handle:
        handle.write(body)
    return path


def make_pdf(name: str = "sample.pdf") -> str:
    """A hand-built two-page PDF 1.4 - no dependency, byte-exact xref table."""

    path = os.path.join(OUT, name)
    _ensure_out()

    def stream(text: str) -> bytes:
        content = (
            "BT /F1 18 Tf 72 720 Td (%s) Tj ET\n"
            "BT /F1 12 Tf 72 690 Td (OpenReader PDF Testseite) Tj ET" % text
        ).encode("latin-1")
        return b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 7 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        stream("Seite 1 - Erstes Kapitel"),
        stream("Seite 2 - Zweites Kapitel"),
    ]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += (b"trailer\n<< /Size %d /Root 1 0 R "
            b"/Info << /Title (OpenReader PDF-Beispiel) >> >>\n"
            b"startxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_pos))

    with open(path, "wb") as handle:
        handle.write(bytes(out))
    return path


def make_all() -> dict[str, str]:
    return {
        "epub3": make_epub("sample.epub", epub3=True),
        "epub2": make_epub("sample_epub2.epub", epub3=False),
        "drm": make_drm_epub(),
        "fb2": make_fb2(),
        "fb2zip": make_fb2_zip(),
        "mobi": make_mobi(),
        "azw3": make_azw3(),
        "cbz": make_cbz(),
        "txt": make_txt(),
        "html": make_html(),
        "md": make_markdown(),
        "rtf": make_rtf(),
        "pdf": make_pdf(),
    }


if __name__ == "__main__":
    for kind, made in sorted(make_all().items()):
        print("%-7s %8d B  %s" % (kind, os.path.getsize(made), os.path.basename(made)))
