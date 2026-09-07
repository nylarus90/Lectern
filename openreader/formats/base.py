"""Common data model that every format backend produces.

A loader turns a file on disk into exactly one :class:`Book`.  The UI only ever
sees this model, never a format-specific structure, which is what keeps the
viewer widgets free of per-format special cases.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterable


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


#: Signature of a loader: ``(path, progress) -> Book``.
Loader = Callable[[str, Callable[[int, str], None]], Book]


def noop_progress(percent: int, message: str) -> None:  # pragma: no cover - trivial
    pass
