"""PDF loader.

PDF is a fixed-layout format, so there is nothing to reflow and no HTML to
build.  The loader only validates the file and lifts what metadata it can from
the trailer; page rendering, the outline and text search are all handled by
Qt's own PDF engine in :mod:`openreader.ui.pdf_view`, which keeps the heavy
document object on the GUI thread where it belongs.
"""

from __future__ import annotations

import re
from typing import Callable

from .base import Book, BookKind, LoadError, TocEntry, noop_progress

_TITLE_RE = re.compile(rb"/Title\s*\((?P<literal>(?:\\.|[^\\)])*)\)|/Title\s*<(?P<hexed>[0-9A-Fa-f\s]+)>")
_AUTHOR_RE = re.compile(rb"/Author\s*\((?P<literal>(?:\\.|[^\\)])*)\)|/Author\s*<(?P<hexed>[0-9A-Fa-f\s]+)>")
_ENCRYPT_RE = re.compile(rb"/Encrypt\s+\d+\s+\d+\s+R")


def _decode_pdf_string(literal: bytes | None, hexed: bytes | None) -> str:
    if hexed is not None:
        try:
            raw = bytes.fromhex(hexed.decode("ascii").replace(" ", "").replace("\n", ""))
        except ValueError:
            return ""
    elif literal is not None:
        raw = re.sub(rb"\\(.)", rb"\1", literal)
    else:
        return ""
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", "replace").lstrip("﻿").strip()
    return raw.decode("latin-1", "replace").strip()


def load(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(10, "PDF wird geprüft…")
    with open(path, "rb") as handle:
        head = handle.read(1024)
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 65536))
        tail = handle.read()

    # Some files carry junk before the header; accept those as long as the
    # signature appears near the start, which is what every PDF reader does.
    if b"%PDF-" not in head:
        raise LoadError("Die Datei beginnt nicht mit einer PDF-Signatur.")

    book = Book(path=path, kind=BookKind.PDF)

    progress(50, "Metadaten werden gelesen…")
    blob = head + tail
    match = _TITLE_RE.search(blob)
    if match:
        book.meta.title = _decode_pdf_string(match.group("literal"), match.group("hexed"))
    match = _AUTHOR_RE.search(blob)
    if match:
        author = _decode_pdf_string(match.group("literal"), match.group("hexed"))
        if author:
            book.meta.authors = [author]

    if _ENCRYPT_RE.search(blob):
        # Qt can still open PDFs with an empty owner password, so this is a
        # warning rather than a hard failure.
        book.warnings.append("Das PDF ist verschlüsselt; ggf. wird ein Passwort verlangt.")

    # The real outline comes from Qt once the document is open.
    book.toc = [TocEntry("Dokument", 0)]
    progress(100, "Fertig")
    return book
