"""Format registry and detection.

Detection looks at the file contents first and only falls back to the
extension, because renamed files are common — an ``.epub`` that is really an
AZW3, a ``.cbr`` that is really a ZIP.  Getting this right is what keeps the
error message honest when a file genuinely cannot be read.
"""

from __future__ import annotations

import os
import zipfile
from typing import Callable, NamedTuple

from .base import Book, BookKind, LoadError, noop_progress


class FormatInfo(NamedTuple):
    key: str
    label: str
    extensions: tuple[str, ...]


#: Everything the file dialog offers, in the order it is shown.
FORMATS = (
    FormatInfo("epub", "EPUB", (".epub",)),
    FormatInfo("mobi", "Kindle (MOBI/AZW/AZW3)", (".mobi", ".azw", ".azw3", ".azw4", ".prc", ".pdb")),
    FormatInfo("fb2", "FictionBook", (".fb2", ".fbz")),
    FormatInfo("pdf", "PDF", (".pdf",)),
    FormatInfo("comic", "Comic-Archiv", (".cbz", ".cbr", ".cb7", ".cbt", ".cba")),
    FormatInfo("txt", "Text", (".txt", ".text", ".log")),
    FormatInfo("markdown", "Markdown", (".md", ".markdown", ".mdown")),
    FormatInfo("html", "HTML", (".html", ".htm", ".xhtml")),
    FormatInfo("rtf", "Rich Text", (".rtf",)),
)

EXTENSION_MAP = {ext: fmt.key for fmt in FORMATS for ext in fmt.extensions}


def _loader(key: str) -> Callable[..., Book]:
    if key == "epub":
        from . import epub
        return epub.load
    if key == "mobi":
        from . import mobi
        return mobi.load
    if key == "fb2":
        from . import fb2
        return fb2.load
    if key == "pdf":
        from . import pdf
        return pdf.load
    if key == "comic":
        from . import comic
        return comic.load
    from . import plaintext
    return {
        "txt": plaintext.load_txt,
        "markdown": plaintext.load_markdown,
        "html": plaintext.load_html,
        "rtf": plaintext.load_rtf,
    }[key]


def detect(path: str) -> str:
    """Return the format key for ``path``, preferring content over extension."""

    extension = os.path.splitext(path)[1].lower()
    by_extension = EXTENSION_MAP.get(extension, "")

    try:
        with open(path, "rb") as handle:
            head = handle.read(2048)
    except OSError as exc:
        raise LoadError("Die Datei konnte nicht gelesen werden: %s" % exc) from exc

    if not head:
        raise LoadError("Die Datei ist leer.")

    if head.startswith(b"%PDF-") or head[:1024].find(b"%PDF-") >= 0:
        return "pdf"
    # PalmDB: the type/creator pair sits at offset 60.
    if len(head) > 68 and head[60:68] in (b"BOOKMOBI", b"TEXtREAd"):
        return "mobi"
    if head.startswith(b"{\\rtf"):
        return "rtf"
    if head.startswith(b"Rar!") or head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "comic" if by_extension in ("comic", "") else by_extension

    if head.startswith(b"PK\x03\x04"):
        return _detect_zip(path, by_extension)

    lowered = head.lstrip()[:400].lower()
    if b"<fictionbook" in lowered:
        return "fb2"
    if lowered.startswith((b"<!doctype html", b"<html", b"<?xml")) and b"<html" in lowered:
        return "html"

    if by_extension:
        return by_extension
    # Last resort: if it decodes as text, treat it as text.
    try:
        head.decode("utf-8")
        return "txt"
    except UnicodeDecodeError as exc:
        raise LoadError(
            "Das Format der Datei wurde nicht erkannt.\n\nUnterstützt werden: %s"
            % ", ".join(sorted(EXTENSION_MAP))
        ) from exc


def _detect_zip(path: str, by_extension: str) -> str:
    """Distinguish EPUB, FB2-in-ZIP and comic archives, all of which are ZIPs."""

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return by_extension or "comic"

    lowered = [n.lower() for n in names]
    if "mimetype" in lowered:
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.read("mimetype").strip() == b"application/epub+zip":
                    return "epub"
        except (KeyError, zipfile.BadZipFile, OSError):
            pass
    if any(n.endswith("container.xml") for n in lowered):
        return "epub"
    if any(n.endswith(".fb2") for n in lowered):
        return "fb2"

    images = sum(1 for n in lowered
                 if os.path.splitext(n)[1] in
                 (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif"))
    if images and images >= len([n for n in lowered if not n.endswith("/")]) * 0.6:
        return "comic"
    return by_extension or "comic"


def load(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    """Detect the format of ``path`` and load it into a :class:`Book`."""

    if not os.path.isfile(path):
        raise LoadError("Die Datei existiert nicht: %s" % path)
    key = detect(path)
    book = _loader(key)(path, progress)
    book.format_key = key
    return book


def dialog_filter() -> str:
    """Build the Qt file-dialog filter string, all-formats entry first."""

    every = sorted({ext for fmt in FORMATS for ext in fmt.extensions})
    parts = ["Alle E-Books (%s)" % " ".join("*" + e for e in every)]
    parts += ["%s (%s)" % (fmt.label, " ".join("*" + e for e in fmt.extensions))
              for fmt in FORMATS]
    parts.append("Alle Dateien (*)")
    return ";;".join(parts)


__all__ = ["Book", "BookKind", "LoadError", "FORMATS", "detect", "load", "dialog_filter"]
