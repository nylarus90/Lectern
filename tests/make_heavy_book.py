"""Build a large, image-heavy EPUB that matches a real-world problem case.

A 20 MB illustrated book is a completely different load profile from a plain
novel: the pictures are large enough that decoding and scaling them dominates,
and there are enough of them that keeping every decoded copy costs hundreds of
megabytes.  The images here are photo-like (smooth gradient plus fine noise) so
they compress roughly the way real photographs do instead of being either
incompressible noise or a trivially flat colour.
"""

from __future__ import annotations

import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Filler prose, kept as a sentence rather than a word list so it stays legible.
WORDS = (
    "Es war einmal ein Kaiser der neue Kleider über alles liebte und all sein "
    "Geld dafür ausgab recht geputzt zu sein denn er kümmerte sich nicht um "
    "sein Heer noch um das Schauspiel oder die Jagd außer wenn er damit seine "
    "prächtigen Gewänder zeigen konnte für jede Stunde des Tages hatte er "
    "einen eigenen Rock und wie man von einem König sagt er ist im Rat"
).split()


def photo_png(width: int, height: int, seed: int) -> bytes:
    """A photo-like PNG: smooth gradients with fine grain over them."""

    noise = os.urandom(width * 3)
    rows = bytearray()
    for y in range(height):
        rows.append(0)                      # filter type: none
        base_r = (seed * 37 + y // 3) & 0xFF
        base_g = (seed * 11 + y // 5) & 0xFF
        base_b = (seed * 53 + y // 7) & 0xFF
        row = bytearray(width * 3)
        for x in range(width):
            index = x * 3
            grain = noise[(index + y * 3) % len(noise)] & 0x1F
            row[index] = (base_r + (x >> 4) + grain) & 0xFF
            row[index + 1] = (base_g + (x >> 5) + grain) & 0xFF
            row[index + 2] = (base_b + (x >> 6) + grain) & 0xFF
        rows += row

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 1))
            + chunk(b"IEND", b""))


def build_illustrated(path: str, *, images: int = 14,
                      image_size: tuple[int, int] = (1050, 800),
                      chapters: int = 40, words_per_chapter: int = 1500) -> str:
    import zipfile

    print("Bilder werden erzeugt (%d x %dx%d)…" % (images, *image_size))
    pictures = {}
    for index in range(images):
        blob = photo_png(image_size[0], image_size[1], index + 1)
        pictures["OEBPS/img%02d.png" % index] = blob
        print("  Bild %2d: %5.2f MB" % (index + 1, len(blob) / 1e6), flush=True)

    manifest = ['<item id="i%d" href="img%02d.png" media-type="image/png"/>' % (i, i)
                for i in range(images)]
    spine, nav, files = [], [], {}

    for index in range(chapters):
        parts = ["<h1>Kapitel %d</h1>" % (index + 1)]
        counter = index * 7919
        for _ in range(max(1, words_per_chapter // 90)):
            words = [WORDS[(counter + step) % len(WORDS)] for step in range(90)]
            counter += 90
            parts.append("<p>%s.</p>" % " ".join(words).capitalize())
        # Every chapter shows a picture, as an illustrated book would.
        parts.append(
            '<figure><img src="img%02d.png" alt="Tafel %d"/>'
            "<figcaption>Tafel %d</figcaption></figure>"
            % (index % images, index + 1, index + 1)
        )
        for _ in range(max(1, words_per_chapter // 90)):
            words = [WORDS[(counter + step) % len(WORDS)] for step in range(90)]
            counter += 90
            parts.append("<p>%s.</p>" % " ".join(words).capitalize())

        name = "ch%02d.xhtml" % index
        files["OEBPS/" + name] = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Kapitel %d</title>'
            '</head><body><section id="k%d">%s</section></body></html>'
            % (index + 1, index, "".join(parts))
        )
        manifest.append('<item id="c%d" href="%s" media-type="application/xhtml+xml"/>'
                        % (index, name))
        spine.append('<itemref idref="c%d"/>' % index)
        nav.append('<li><a href="%s#k%d">Kapitel %d</a></li>' % (name, index, index + 1))

    opf = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="b">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Illustrierter Prachtband</dc:title><dc:creator>Testsuite</dc:creator>"
        '<dc:language>de</dc:language><dc:identifier id="b">urn:uuid:heavy</dc:identifier>'
        "</metadata><manifest>"
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        + "".join(manifest)
        + "</manifest><spine>" + "".join(spine) + "</spine></package>"
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                    compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml",
                    '<container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                    '<rootfile full-path="OEBPS/content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles></container>')
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/nav.xhtml",
                    '<?xml version="1.0" encoding="utf-8"?>'
                    '<html xmlns="http://www.w3.org/1999/xhtml" '
                    'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Inhalt</title>'
                    '</head><body><nav epub:type="toc"><ol>%s</ol></nav></body></html>'
                    % "".join(nav))
        for name, blob in pictures.items():
            # Pictures are already compressed; storing them saves build time.
            zf.writestr(zipfile.ZipInfo(name), blob, compress_type=zipfile.ZIP_STORED)
        for name, text in files.items():
            zf.writestr(name, text)
    return path


def build_plain(path: str, *, chapters: int = 40, words_per_chapter: int = 3000) -> str:
    """The same book without real pictures, so text scrolling stays measurable."""

    return build_illustrated(path, images=1, image_size=(8, 8), chapters=chapters,
                             words_per_chapter=words_per_chapter)


if __name__ == "__main__":
    import tempfile

    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        tempfile.gettempdir(), "lectern-bench-illustrated.epub")
    build_illustrated(target)
    print("\n%s: %.1f MB" % (target, os.path.getsize(target) / 1e6))
