"""Common data model that every format backend produces.

A loader turns a file on disk into exactly one :class:`Book`.  The UI only ever
sees this model, never a format-specific structure, which is what keeps the
viewer widgets free of per-format special cases.
"""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable

from ..i18n import tr


class BookKind(str, Enum):
    """Determines which viewer widget the main window shows."""

    TEXT = "text"      # reflowable prose -> PagedReaderView
    COMIC = "comic"    # ordered bitmaps -> ComicView
    PDF = "pdf"        # fixed layout   -> PdfView


class LoadError(Exception):
    """A file could not be opened; ``message`` is shown to the user verbatim."""


class DRMError(LoadError):
    """File is encrypted with DRM we neither can nor may remove."""


@dataclass(slots=True)
class TocEntry:
    """One line in the table of contents.

    ``target`` is a resolved anchor name inside the assembled document (text
    books), a page index (PDF), or an image index (comics).
    """

    title: str
    target: str | int
    children: list[TocEntry] = field(default_factory=list)

    def flatten(self, level: int = 0) -> Iterable[tuple[int, TocEntry]]:
        yield level, self
        for child in self.children:
            yield from child.flatten(level + 1)


@dataclass(slots=True)
class Chapter:
    """A spine item.  ``html`` is already normalised for Qt's rich text engine."""

    ident: str
    title: str
    html: str


@dataclass(slots=True)
class Metadata:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    language: str = ""
    publisher: str = ""
    date: str = ""
    description: str = ""
    identifier: str = ""
    series: str = ""
    series_index: str = ""
    subjects: list[str] = field(default_factory=list)

    @property
    def author_line(self) -> str:
        return ", ".join(self.authors)


@dataclass
class Book:
    """Everything the viewers need, fully decoded and in memory.

    Resources are kept as raw bytes and resolved lazily by the view, so a book
    with 300 illustrations does not pay decode cost until a page shows one.
    """

    path: str
    kind: BookKind = BookKind.TEXT
    #: Registry key of the loader that produced this book, e.g. ``"epub"``.
    format_key: str = ""
    meta: Metadata = field(default_factory=Metadata)
    chapters: list[Chapter] = field(default_factory=list)
    toc: list[TocEntry] = field(default_factory=list)
    resources: dict[str, bytes] = field(default_factory=dict)
    cover: bytes | None = None
    #: Ordered resource keys, only used by :data:`BookKind.COMIC`.
    images: list[str] = field(default_factory=list)
    #: Publisher stylesheet, merged only when the user opts in.
    publisher_css: str = ""
    #: Non-fatal problems worth surfacing in the status bar.
    warnings: list[str] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        return self.meta.title or os.path.splitext(os.path.basename(self.path))[0]

    def resource(self, key: str) -> bytes | None:
        data = self.resources.get(key)
        if data is not None:
            return data
        # Tolerate case differences and stray leading slashes produced by
        # sloppy authoring tools.
        probe = key.lstrip("/").lower()
        for name, blob in self.resources.items():
            if name.lstrip("/").lower() == probe:
                return blob
        return None


def file_id(path: str) -> str:
    """Stable identity for a book: content-derived, so moving a file keeps notes.

    Hashing the whole file would stall on a 700 MB comic archive, so we hash the
    size plus the first and last megabyte, which is more than enough to tell two
    real books apart.
    """

    size = os.path.getsize(path)
    digest = hashlib.sha256(str(size).encode("ascii"))
    chunk = 1 << 20
    with open(path, "rb") as handle:
        digest.update(handle.read(chunk))
        if size > 2 * chunk:
            handle.seek(-chunk, os.SEEK_END)
            digest.update(handle.read(chunk))
    return digest.hexdigest()


#: Upper bound on how much a single book may expand to in memory.  A 40 MB
#: archive of nothing but zeroes decompresses to about 40 GB, so without a
#: ceiling a merely damaged — let alone deliberately crafted — file drives the
#: machine into swap.  The limit is generous: the largest real illustrated books
#: measured here stay under 200 MB.
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


class ExpansionBudget:
    """Caps how much uncompressed data one book may produce.

    Declared sizes in archive headers are attacker-controlled and may lie, so
    entries are checked twice: against the declared size before reading, and
    against reality afterwards.
    """

    def __init__(self, limit: int = MAX_UNCOMPRESSED_BYTES) -> None:
        self.limit = limit
        self.used = 0

    def _fail(self, what: str) -> None:
        raise LoadError(
            tr("The file expands to more than %d MB and was refused (at: %s).\n\n"
               "That points to a damaged or deliberately crafted file.")
            % (self.limit // (1024 * 1024), what)
        )

    def check(self, declared: int, what: str) -> None:
        """Reject an entry before reading it, based on its declared size."""

        if declared < 0 or self.used + declared > self.limit:
            self._fail(what)

    def spend(self, actual: int, what: str) -> None:
        """Account for data actually read, in case the declared size lied."""

        self.used += actual
        if self.used > self.limit:
            self._fail(what)

    def read_zip(self, archive, name: str) -> bytes:
        """Read one ZIP entry within budget."""

        self.check(archive.getinfo(name).file_size, name)
        data = archive.read(name)
        self.spend(len(data), name)
        return data


#: Signature of a loader: ``(path, progress) -> Book``.
Loader = Callable[[str, Callable[[int, str], None]], Book]


def noop_progress(percent: int, message: str) -> None:  # pragma: no cover - trivial
    pass


def _doctype_span(data: bytes) -> bytes:
    """The document's DOCTYPE declaration, internal subset included.

    Entity declarations can only live here, so this is the only region that has
    to be examined — scanning the whole file would flag the words in ordinary
    prose or in a code sample.
    """

    start = data.find(b"<!DOCTYPE")
    if start < 0:
        start = data.find(b"<!doctype")
    if start < 0:
        return b""
    subset_start = data.find(b"[", start)
    end = data.find(b">", start)
    if subset_start >= 0 and (end < 0 or subset_start < end):
        subset_end = data.find(b"]", subset_start)
        end = data.find(b">", subset_end) if subset_end >= 0 else -1
    return data[start:end + 1] if end > start else data[start:]


def parse_xml(data: bytes | str) -> ET.Element:
    """Parse book XML, refusing documents that declare entities.

    EPUB and FB2 are XML, and a few hundred bytes of nested entity definitions
    expand to gigabytes on a parser that allows them.  libexpat 2.6 caps the
    amplification factor, but the supported Python versions do not all ship it,
    and a system interpreter can be new while its libexpat is old — so the
    protection cannot be assumed.  Books have no legitimate use for entity
    declarations, and refusing them also closes external entity references
    (XXE), on every version.
    """

    raw = data.encode("utf-8", "replace") if isinstance(data, str) else data
    if b"<!ENTITY" in _doctype_span(raw).upper():
        raise LoadError(
            tr("The file declares XML entities and was refused. Books have no use for "
               "these; they almost always serve to exhaust the reader's memory.")
        )
    return ET.fromstring(data)
