import pytest

from lectern.formats import epub
from lectern.formats.base import BookKind, DRMError

from . import make_samples


@pytest.fixture(scope="module")
def epub3_book():
    return epub.load(make_samples.make_epub("sample.epub", epub3=True))


def test_metadata(epub3_book):
    meta = epub3_book.meta
    assert meta.title == "Des Kaisers neue Kleider"
    assert meta.authors == ["Hans Christian Andersen"]
    assert meta.language == "de"
    assert meta.publisher == "OpenReader Testsuite"
    assert meta.series == "Märchensammlung"
    assert "Märchen" in meta.subjects
    assert epub3_book.kind is BookKind.TEXT


def test_spine_order_and_content(epub3_book):
    assert len(epub3_book.chapters) == 3, "cover + two chapters"
    joined = "".join(c.html for c in epub3_book.chapters)
    assert "Kaiser" in joined and "Betrüger" in joined
    assert "<table" in joined and "<blockquote" in joined


def test_cover_and_resources(epub3_book):
    assert epub3_book.cover is not None
    assert epub3_book.cover.startswith(b"\x89PNG")
    assert "OEBPS/images/bild.png" in epub3_book.resources
    # The SVG cover wrapper must have produced a real image reference.
    assert 'src="OEBPS/images/bild.png"' in epub3_book.chapters[0].html


def test_internal_links_become_anchors(epub3_book):
    ch1 = epub3_book.chapters[1].html
    assert 'href="#ch2__kap2"' in ch1, "cross-chapter link must resolve"


def test_toc_from_nav_document(epub3_book):
    titles = [entry.title for _lvl, entry in _flat(epub3_book.toc)]
    assert titles[:2] == ["Erstes Kapitel", "Zweites Kapitel"]
    assert "Das Zitat" in titles, "nested TOC level must survive"
    assert epub3_book.toc[0].target == "#ch1__kap1"


def test_epub2_falls_back_to_ncx():
    book = epub.load(make_samples.make_epub("sample_epub2.epub", epub3=False))
    assert [e.title for e in book.toc] == ["Erstes Kapitel", "Zweites Kapitel"]
    assert book.meta.title == "Des Kaisers neue Kleider"


def test_publisher_css_is_collected(epub3_book):
    assert "text-indent" in epub3_book.publisher_css


def test_drm_is_reported_clearly():
    with pytest.raises(DRMError) as excinfo:
        epub.load(make_samples.make_drm_epub())
    assert "DRM" in str(excinfo.value)


def _flat(entries):
    for entry in entries:
        yield from entry.flatten()
