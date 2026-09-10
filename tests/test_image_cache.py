"""Regression tests for image handling in the reader view.

These lock in the fix for the worst performance defect the reader had: Qt only
caches a resource when its own ``loadResource`` runs, so an override that
returns book images from memory has to cache them itself.  Without that, every
repaint touching a picture decoded and rescaled it — 300 ms per frame on a
21 MB illustrated novel.
"""

from __future__ import annotations

import pytest

from . import make_samples
from .conftest import dispose

pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def book_with_plate(app):
    """A one-chapter book holding a single wide illustration."""

    from lectern.formats.base import Book, BookKind, Chapter

    book = Book(path="probe.epub", kind=BookKind.TEXT)
    book.resources["plate.png"] = make_samples._make_png(1600, 400)
    book.chapters = [Chapter(ident="ch0", title="Tafel",
                             html='<p>Text</p><p><img src="plate.png"/></p>')]
    return book


@pytest.fixture
def document(app, book_with_plate):
    from lectern.ui.reader_view import _BookDocument

    doc = _BookDocument(book_with_plate)
    doc.setTextWidth(600.0)
    yield doc
    dispose(app, doc)


def _image(document, key="plate.png"):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument

    return document.loadResource(QTextDocument.ImageResource, QUrl(key))


def test_repeated_requests_decode_only_once(document, monkeypatch):
    decodes = {"n": 0}
    original = type(document)._decode

    def counting(self, data, target):
        decodes["n"] += 1
        return original(self, data, target)

    monkeypatch.setattr(type(document), "_decode", counting)

    first = _image(document)
    assert first is not None and not first.isNull()
    for _ in range(20):
        _image(document)
    assert decodes["n"] == 1, "the picture must be decoded once, not on every repaint"


def test_oversized_image_is_scaled_to_the_column(document):
    image = _image(document)
    # 600 px column at the test display's ratio; never wider than that in
    # logical pixels, which is what keeps a horizontal scrollbar away.
    logical = image.width() / max(1.0, image.devicePixelRatio())
    assert logical <= 601, "a 1600 px plate must be scaled down to the column"
    assert image.height() > 0


def test_small_image_is_left_alone(app, book_with_plate):
    from lectern.ui.reader_view import _BookDocument

    book_with_plate.resources["small.png"] = make_samples._make_png(80, 60)
    doc = _BookDocument(book_with_plate)
    doc.setTextWidth(600.0)
    try:
        image = _image(doc, "small.png")
        assert (image.width(), image.height()) == (80, 60)
        assert image.devicePixelRatio() == 1.0, "an unscaled image must not be shrunk"
    finally:
        dispose(app, doc)


def test_unknown_resource_falls_through(document):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument

    result = document.loadResource(QTextDocument.ImageResource, QUrl("fehlt.png"))
    assert not result or (hasattr(result, "isNull") and result.isNull())


def test_cache_evicts_to_stay_within_budget(app, book_with_plate):
    from lectern.ui.reader_view import _BookDocument, _ImageCache

    doc = _BookDocument(book_with_plate)
    doc.setTextWidth(600.0)
    # Room for roughly one rendition, so the second must push the first out.
    doc._cache = _ImageCache(budget=1_500_000)
    try:
        for index in range(6):
            book_with_plate.resources["p%d.png" % index] = make_samples._make_png(1200, 300)
            assert _image(doc, "p%d.png" % index) is not None
        assert doc._cache._bytes <= doc._cache.budget
        assert len(doc._cache._entries) < 6, "the cache must not grow without bound"
    finally:
        dispose(app, doc)


def test_width_change_drops_stale_renditions(document):
    _image(document)
    assert len(document._cache._entries) == 1
    document.setTextWidth(900.0)
    _image(document)
    assert len(document._cache._entries) == 1, \
        "renditions for the old column width must not linger alongside the new"


def test_nearby_widths_share_one_rendition(document):
    """Dragging a window edge must not decode at every intermediate pixel."""

    _image(document)
    first = document._cached_width
    document.setTextWidth(600.0 + 8)
    _image(document)
    assert document._cached_width == first, "widths are bucketed, not exact"


def test_view_uses_the_caching_document(app, tmp_path):
    """The wiring, not just the class: a real book must get a caching document."""

    from lectern.formats import load
    from lectern.storage.settings import Settings
    from lectern.ui.loader import assemble
    from lectern.ui.reader_view import ReaderView, _BookDocument

    path = make_samples.make_epub("cache_probe.epub")
    book = load(path)
    view = ReaderView(Settings(str(tmp_path / "s.json")))
    view.resize(700, 500)
    try:
        view.set_book(book, assemble(book))
        assert isinstance(view.document(), _BookDocument)
        # The width must be settled before parsing, so images are sized once.
        assert view.document().textWidth() > 1
    finally:
        dispose(app, view)
