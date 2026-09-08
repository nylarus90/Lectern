"""FictionBook 2 loader, including the common ``.fb2.zip`` packaging.

FB2 is a single XML document with its own vocabulary and base64-encoded images
in trailing ``<binary>`` elements, so the work is a direct element-to-HTML
translation rather than a parse-then-clean pass.
"""

from __future__ import annotations

import base64
import binascii
import zipfile
from html import escape
from typing import Callable
from xml.etree import ElementTree as ET

from .base import (
    Book,
    BookKind,
    Chapter,
    LoadError,
    Metadata,
    TocEntry,
    noop_progress,
    parse_xml,
)

#: FB2 element -> (open tag, close tag).  Anything not listed is passed through
#: as a transparent container so no text is ever lost.
INLINE = {
    "emphasis": ("<em>", "</em>"),
    "strong": ("<strong>", "</strong>"),
    "strikethrough": ("<s>", "</s>"),
    "sub": ("<sub>", "</sub>"),
    "sup": ("<sup>", "</sup>"),
    "code": ("<code>", "</code>"),
    "style": ("<span>", "</span>"),
}

BLOCK = {
    "p": ("<p>", "</p>"),
    "subtitle": ("<h3>", "</h3>"),
    "cite": ("<blockquote>", "</blockquote>"),
    "epigraph": ('<blockquote class="or-epigraph">', "</blockquote>"),
    "poem": ('<div class="or-poem">', "</div>"),
    "stanza": ('<div class="or-stanza">', "</div>"),
    "v": ('<p class="or-verse">', "</p>"),
    "text-author": ('<p class="or-author">', "</p>"),
    "annotation": ('<div class="or-annotation">', "</div>"),
    "date": ('<p class="or-date">', "</p>"),
    "table": ("<table border='1'>", "</table>"),
    "tr": ("<tr>", "</tr>"),
    "td": ("<td>", "</td>"),
    "th": ("<th>", "</th>"),
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _href(node: ET.Element) -> str:
    for key, value in node.attrib.items():
        if _local(key) == "href":
            return value
    return ""


class _Converter:
    """Walks the FB2 tree and emits HTML plus a heading-based table of contents."""

    def __init__(self, book: Book) -> None:
        self.book = book
        self.out: list[str] = []
        self.toc: list[TocEntry] = []
        self._section_depth = 0
        self._counter = 0

    def emit(self, text: str) -> None:
        self.out.append(text)

    def convert_body(self, body: ET.Element) -> None:
        for child in body:
            self.node(child)

    def node(self, node: ET.Element) -> None:
        tag = _local(node.tag)

        if tag == "section":
            self._section_depth += 1
            self.section(node)
            self._section_depth -= 1
            return
        if tag == "title":
            self.title(node)
            return
        if tag == "image":
            key = _href(node).lstrip("#")
            if key in self.book.resources:
                self.emit('<p class="or-figure"><img src="%s" /></p>' % escape(key, quote=True))
            return
        if tag == "empty-line":
            self.emit("<p>&nbsp;</p>")
            return
        if tag == "a":
            target = _href(node)
            if target.startswith("#"):
                self.emit('<a href="#fb2%s">' % escape(target[1:], quote=True))
            else:
                self.emit('<a href="%s">' % escape(target, quote=True))
            self.children(node)
            self.emit("</a>")
            self.tail(node)
            return
        if tag == "binary":
            return

        open_tag, close_tag = BLOCK.get(tag) or INLINE.get(tag) or ("", "")
        ident = node.get("id", "")
        if ident:
            self.emit('<a name="fb2%s"></a>' % escape(ident, quote=True))
        self.emit(open_tag)
        if node.text:
            self.emit(escape(node.text))
        self.children(node)
        self.emit(close_tag)
        self.tail(node)

    def children(self, node: ET.Element) -> None:
        for child in node:
            self.node(child)

    def tail(self, node: ET.Element) -> None:
        if node.tail:
            self.emit(escape(node.tail))

    def section(self, node: ET.Element) -> None:
        ident = node.get("id") or "sec%d" % self._counter
        self._counter += 1
        self.emit('<a name="fb2%s"></a><div class="or-section">' % escape(ident, quote=True))
        self._pending_anchor = ident
        for child in node:
            self.node(child)
        self.emit("</div>")

    def title(self, node: ET.Element) -> None:
        level = min(6, max(1, self._section_depth))
        text = " ".join("".join(child.itertext()).strip() for child in node) or (node.text or "")
        text = text.strip()
        anchor = getattr(self, "_pending_anchor", "")
        self.emit("<h%d>%s</h%d>" % (level, escape(text), level))
        if text:
            entry = TocEntry(text, "#fb2%s" % anchor if anchor else "#top")
            self._place(entry, level)

    def _place(self, entry: TocEntry, level: int) -> None:
        """Attach a heading at the depth its section nesting implies."""

        if level <= 1 or not self.toc:
            self.toc.append(entry)
            return
        parent = self.toc[-1]
        for _ in range(level - 2):
            if parent.children:
                parent = parent.children[-1]
            else:
                break
        parent.children.append(entry)


def _metadata(root: ET.Element) -> tuple[Metadata, str]:
    meta = Metadata()
    cover = ""
    for info in root.iter():
        if _local(info.tag) != "title-info":
            continue
        for node in info:
            tag = _local(node.tag)
            if tag == "book-title":
                meta.title = (node.text or "").strip()
            elif tag == "author":
                parts = [(child.text or "").strip() for child in node
                         if _local(child.tag) in ("first-name", "middle-name", "last-name")]
                name = " ".join(p for p in parts if p)
                if name:
                    meta.authors.append(name)
            elif tag == "lang":
                meta.language = (node.text or "").strip()
            elif tag == "genre" and node.text:
                meta.subjects.append(node.text.strip())
            elif tag == "date":
                meta.date = (node.get("value") or node.text or "").strip()
            elif tag == "annotation":
                meta.description = " ".join(node.itertext()).strip()
            elif tag == "sequence":
                meta.series = node.get("name", "")
                meta.series_index = node.get("number", "")
            elif tag == "coverpage":
                for child in node:
                    if _local(child.tag) == "image":
                        cover = _href(child).lstrip("#")
        break
    return meta, cover


def load(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(5, "FB2 wird gelesen…")
    data = _read_bytes(path)
    try:
        root = parse_xml(data)
    except ET.ParseError as exc:
        raise LoadError("Die FB2-Datei ist kein gültiges XML: %s" % exc) from exc

    book = Book(path=path, kind=BookKind.TEXT)

    progress(25, "Bilder werden dekodiert…")
    for node in root.iter():
        if _local(node.tag) != "binary":
            continue
        ident = node.get("id", "")
        if not ident or not node.text:
            continue
        try:
            book.resources[ident] = base64.b64decode(node.text)
        except (binascii.Error, ValueError):
            book.warnings.append("Beschädigtes Bild übersprungen: %s" % ident)

    book.meta, cover_key = _metadata(root)
    book.cover = book.resources.get(cover_key)

    progress(55, "Text wird umgewandelt…")
    converter = _Converter(book)
    bodies = [n for n in root if _local(n.tag) == "body"]
    if not bodies:
        raise LoadError("Die FB2-Datei enthält keinen <body>.")
    for body in bodies:
        if body.get("name") == "notes":
            converter.emit('<hr /><h2 class="or-notes">Anmerkungen</h2>')
        converter.convert_body(body)

    book.chapters = [Chapter(ident="ch0", title=book.display_title,
                             html='<a name="ch0"></a>' + "".join(converter.out))]
    book.toc = converter.toc or [TocEntry(book.display_title, "#ch0")]
    progress(100, "Fertig")
    return book


def _read_bytes(path: str) -> bytes:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".fb2")]
            if not names:
                names = [n for n in archive.namelist() if not n.endswith("/")]
            if not names:
                raise LoadError("Das FB2-Archiv ist leer.")
            return archive.read(names[0])
    with open(path, "rb") as handle:
        return handle.read()
