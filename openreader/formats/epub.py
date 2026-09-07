"""EPUB 2 and EPUB 3 loader.

Reads the OPF package to get metadata, the reading order (spine) and the
resources, then the NCX (EPUB 2) or the navigation document (EPUB 3) for the
table of contents.  Encrypted books are detected up front so the user gets an
honest message instead of a wall of mojibake.
"""

from __future__ import annotations

import contextlib
import posixpath
import zipfile
from typing import Callable
from xml.etree import ElementTree as ET

from ..render.html_clean import anchor_name, normalize, strip_tags
from .base import Book, BookKind, Chapter, DRMError, LoadError, Metadata, TocEntry, noop_progress

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "cnt": "urn:oasis:names:tc:opendocument:xmlns:container",
}

TEXT_MEDIA = {"application/xhtml+xml", "text/html", "application/x-dtbook+xml"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _norm(path: str) -> str:
    """Collapse ``..`` segments and strip the leading slash zip entries never have."""

    return posixpath.normpath(path).lstrip("/")


def _split_fragment(href: str) -> tuple[str, str]:
    raw = href.split("#", 1)
    return raw[0], (raw[1] if len(raw) > 1 else "")


class _Epub:
    def __init__(self, path: str) -> None:
        try:
            self.zf = zipfile.ZipFile(path)
        except zipfile.BadZipFile as exc:
            raise LoadError("Die Datei ist kein gültiges EPUB-Archiv.") from exc
        self.names = {name.lstrip("/"): name for name in self.zf.namelist()}

    def read(self, path: str) -> bytes:
        real = self.names.get(_norm(path))
        if real is None:
            # Some tools write percent-encoded entries, others do not.
            from urllib.parse import unquote

            real = self.names.get(_norm(unquote(path)))
        if real is None:
            raise KeyError(path)
        return self.zf.read(real)

    def xml(self, path: str) -> ET.Element:
        return ET.fromstring(self.read(path))


def _opf_path(epub: _Epub) -> str:
    try:
        container = epub.xml("META-INF/container.xml")
    except KeyError as exc:
        raise LoadError("Im EPUB fehlt META-INF/container.xml.") from exc
    for node in container.iter():
        if _local(node.tag) == "rootfile" and node.get("full-path"):
            return _norm(node.get("full-path", ""))
    raise LoadError("Im EPUB ist kein OPF-Dokument eingetragen.")


def _check_drm(epub: _Epub) -> None:
    if "META-INF/encryption.xml" not in epub.names:
        return
    data = epub.read("META-INF/encryption.xml").decode("utf-8", "replace")
    # Font obfuscation is legitimate and harmless; content encryption is DRM.
    obfuscated_fonts_only = (
        "embedding" in data.lower()
        or "http://www.idpf.org/2008/embedding" in data
    )
    if "EncryptedData" in data and not obfuscated_fonts_only:
        raise DRMError(
            "Dieses EPUB ist mit DRM geschützt und kann nicht geöffnet werden."
        )


def _metadata(package: ET.Element) -> tuple[Metadata, str]:
    meta = Metadata()
    cover_id = ""
    md = None
    for child in package:
        if _local(child.tag) == "metadata":
            md = child
            break
    if md is None:
        return meta, cover_id

    for node in md:
        name = _local(node.tag)
        text = (node.text or "").strip()
        if name == "title" and not meta.title:
            meta.title = text
        elif name == "creator" and text:
            meta.authors.append(text)
        elif name == "language" and not meta.language:
            meta.language = text
        elif name == "publisher":
            meta.publisher = text
        elif name == "date" and not meta.date:
            meta.date = text
        elif name == "description":
            meta.description = strip_tags(text)
        elif name == "identifier" and not meta.identifier:
            meta.identifier = text
        elif name == "subject" and text:
            meta.subjects.append(text)
        elif name == "meta":
            prop = node.get("property", "")
            if node.get("name") == "cover":
                cover_id = node.get("content", "")
            elif prop == "belongs-to-collection":
                meta.series = text
            elif prop == "group-position":
                meta.series_index = text
            elif node.get("name") == "calibre:series":
                meta.series = node.get("content", "")
            elif node.get("name") == "calibre:series_index":
                meta.series_index = node.get("content", "")
    return meta, cover_id


def _toc_from_ncx(root: ET.Element, resolve: Callable[[str], str]) -> list[TocEntry]:
    def walk(parent: ET.Element) -> list[TocEntry]:
        entries: list[TocEntry] = []
        for node in parent:
            if _local(node.tag) != "navPoint":
                continue
            label, src = "", ""
            for child in node:
                tag = _local(child.tag)
                if tag == "navLabel":
                    label = strip_tags("".join(child.itertext()))
                elif tag == "content":
                    src = child.get("src", "")
            target = resolve(src)
            if label and target:
                entries.append(TocEntry(label, target, walk(node)))
        return entries

    for node in root:
        if _local(node.tag) == "navMap":
            return walk(node)
    return []


def _toc_from_nav(root: ET.Element, resolve: Callable[[str], str]) -> list[TocEntry]:
    """Parse an EPUB 3 nav document, using the ``toc`` landmark if present."""

    nav = None
    for node in root.iter():
        if _local(node.tag) == "nav":
            epub_type = ""
            for key, value in node.attrib.items():
                if _local(key) == "type":
                    epub_type = value
            if epub_type == "toc" or nav is None:
                nav = node
                if epub_type == "toc":
                    break
    if nav is None:
        return []

    def walk(ol: ET.Element) -> list[TocEntry]:
        entries: list[TocEntry] = []
        for li in ol:
            if _local(li.tag) != "li":
                continue
            label, src, children = "", "", []
            for child in li:
                tag = _local(child.tag)
                if tag == "a":
                    label = strip_tags("".join(child.itertext()))
                    src = child.get("href", "")
                elif tag == "span":
                    label = strip_tags("".join(child.itertext()))
                elif tag == "ol":
                    children = walk(child)
            target = resolve(src) if src else ""
            if label:
                # A span-only entry is a heading; keep it by pointing at its
                # first child so clicking it still goes somewhere sensible.
                if not target and children:
                    target = children[0].target
                if target:
                    entries.append(TocEntry(label, target, children))
                else:
                    entries.extend(children)
        return entries

    for node in nav.iter():
        if _local(node.tag) == "ol":
            return walk(node)
    return []


def load(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(2, "EPUB wird geöffnet…")
    epub = _Epub(path)
    _check_drm(epub)

    opf_path = _opf_path(epub)
    opf_dir = posixpath.dirname(opf_path)
    package = epub.xml(opf_path)

    book = Book(path=path, kind=BookKind.TEXT)
    book.meta, cover_id = _metadata(package)

    # -- manifest --------------------------------------------------------
    manifest: dict[str, tuple[str, str, str]] = {}  # id -> (abs href, media, props)
    for child in package:
        if _local(child.tag) != "manifest":
            continue
        for item in child:
            if _local(item.tag) != "item":
                continue
            ident = item.get("id", "")
            href = item.get("href", "")
            if not ident or not href:
                continue
            manifest[ident] = (
                _norm(posixpath.join(opf_dir, href)),
                item.get("media-type", ""),
                item.get("properties", ""),
            )

    # -- spine -----------------------------------------------------------
    spine_ids: list[str] = []
    toc_ncx_id = ""
    for child in package:
        if _local(child.tag) != "spine":
            continue
        toc_ncx_id = child.get("toc", "")
        for ref in child:
            if _local(ref.tag) == "itemref" and ref.get("idref"):
                # linear="no" items are ancillary, but keeping them matches what
                # other readers do and avoids silently dropping content.
                spine_ids.append(ref.get("idref", ""))
    spine_ids = [i for i in spine_ids if i in manifest]

    if not spine_ids:
        raise LoadError("Das EPUB enthält keine lesbaren Kapitel (leerer Spine).")

    # Map absolute href -> chapter anchor prefix, needed for link rewriting.
    chapter_prefix: dict[str, str] = {}
    for index, ident in enumerate(spine_ids):
        chapter_prefix[manifest[ident][0]] = "ch%d" % index

    def resolve_target(href: str, base_dir: str) -> str:
        """Turn a book-internal href into an in-document anchor reference."""

        raw, fragment = _split_fragment(href)
        if not raw:
            return ""
        absolute = _norm(posixpath.join(base_dir, raw))
        prefix = chapter_prefix.get(absolute)
        if prefix is None:
            return ""
        return "#" + anchor_name(prefix, fragment)

    # -- resources -------------------------------------------------------
    progress(10, "Ressourcen werden gelesen…")
    for _ident, (href, media, _props) in manifest.items():
        if media in TEXT_MEDIA or media == "application/x-dtbncx+xml":
            continue
        if media.startswith(("image/", "font/")) or media in (
            "application/font-sfnt",
            "application/vnd.ms-opentype",
            "application/x-font-ttf",
        ):
            try:
                book.resources[href] = epub.read(href)
            except KeyError:
                book.warnings.append("Fehlende Ressource: %s" % href)
        elif media == "text/css":
            # A stylesheet the manifest promises but the archive lacks is
            # cosmetic only, so it does not deserve a warning.
            with contextlib.suppress(KeyError):
                book.publisher_css += epub.read(href).decode("utf-8", "replace") + "\n"

    # -- chapters --------------------------------------------------------
    total = len(spine_ids)
    for index, ident in enumerate(spine_ids):
        href, _media, _props = manifest[ident]
        base_dir = posixpath.dirname(href)
        progress(15 + int(70 * index / max(1, total)), "Kapitel %d/%d" % (index + 1, total))
        try:
            raw = epub.read(href).decode("utf-8", "replace")
        except KeyError:
            book.warnings.append("Kapitel fehlt im Archiv: %s" % href)
            continue

        body, title = normalize(
            raw,
            anchor_prefix="ch%d" % index,
            resolve_href=lambda h, d=base_dir: _external_or(h, d, resolve_target),
            resolve_src=lambda s, d=base_dir: _resource_key(s, d, book),
        )
        book.chapters.append(Chapter(ident="ch%d" % index, title=title, html=body))

    if not book.chapters:
        raise LoadError("Kein Kapitel des EPUBs konnte gelesen werden.")

    # -- table of contents -----------------------------------------------
    progress(90, "Inhaltsverzeichnis…")
    nav_id = next(
        (i for i, (_h, _m, props) in manifest.items() if "nav" in props.split()), ""
    )
    if nav_id:
        nav_href = manifest[nav_id][0]
        try:
            book.toc = _toc_from_nav(
                epub.xml(nav_href),
                lambda h: resolve_target(h, posixpath.dirname(nav_href)),
            )
        except (KeyError, ET.ParseError):
            book.toc = []
    if not book.toc and toc_ncx_id in manifest:
        ncx_href = manifest[toc_ncx_id][0]
        try:
            book.toc = _toc_from_ncx(
                epub.xml(ncx_href),
                lambda h: resolve_target(h, posixpath.dirname(ncx_href)),
            )
        except (KeyError, ET.ParseError):
            book.toc = []
    if not book.toc:
        book.toc = [
            TocEntry(chapter.title or "Abschnitt %d" % (i + 1), "#" + chapter.ident)
            for i, chapter in enumerate(book.chapters)
        ]

    # -- cover -----------------------------------------------------------
    cover_href = ""
    if cover_id in manifest:
        cover_href = manifest[cover_id][0]
    else:
        cover_href = next(
            (h for _i, (h, _m, props) in manifest.items() if "cover-image" in props), ""
        )
    if cover_href:
        book.cover = book.resources.get(cover_href)

    progress(100, "Fertig")
    return book


def _external_or(href: str, base_dir: str, resolve) -> str:
    """Keep web links intact, rewrite internal ones to document anchors."""

    lowered = href.strip().lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:")):
        return href.strip()
    return resolve(href, base_dir)


def _resource_key(src: str, base_dir: str, book: Book) -> str:
    if not src or src.strip().lower().startswith(("http://", "https://", "data:")):
        return ""
    key = _norm(posixpath.join(base_dir, src.split("#", 1)[0]))
    if key in book.resources:
        return key
    from urllib.parse import unquote

    alt = _norm(posixpath.join(base_dir, unquote(src.split("#", 1)[0])))
    return alt if alt in book.resources else ""
