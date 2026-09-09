"""Cross-format tests: detection, and the loaders without their own module."""

import pytest

from openreader import formats
from openreader.formats import comic, fb2, pdf, plaintext
from openreader.formats.base import BookKind, LoadError

from . import make_samples


@pytest.fixture(scope="module")
def samples():
    return make_samples.make_all()


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind,expected",
    [
        ("epub3", "epub"), ("epub2", "epub"), ("fb2", "fb2"), ("fb2zip", "fb2"),
        ("mobi", "mobi"), ("cbz", "comic"), ("txt", "txt"), ("html", "html"),
        ("md", "markdown"), ("rtf", "rtf"), ("pdf", "pdf"),
    ],
)
def test_detection(samples, kind, expected):
    assert formats.detect(samples[kind]) == expected


def test_detection_ignores_a_wrong_extension(samples, tmp_path):
    """A renamed file must still be recognised by its contents."""

    misnamed = tmp_path / "buch.epub"
    misnamed.write_bytes(open(samples["mobi"], "rb").read())
    assert formats.detect(str(misnamed)) == "mobi"
    assert formats.load(str(misnamed)).meta.authors == ["Hans Christian Andersen"]


def test_empty_and_unknown_files_are_rejected(tmp_path):
    empty = tmp_path / "leer.bin"
    empty.write_bytes(b"")
    with pytest.raises(LoadError, match="empty"):
        formats.detect(str(empty))

    binary = tmp_path / "rauschen.bin"
    binary.write_bytes(bytes(range(256)) * 8)
    with pytest.raises(LoadError, match="not recognised"):
        formats.detect(str(binary))


def test_missing_file(tmp_path):
    with pytest.raises(LoadError, match="does not exist"):
        formats.load(str(tmp_path / "gibtsnicht.epub"))


def test_dialog_filter_lists_every_extension():
    text = formats.dialog_filter()
    for fmt in formats.FORMATS:
        for extension in fmt.extensions:
            assert "*" + extension in text


def test_format_key_is_recorded(samples):
    assert formats.load(samples["epub3"]).format_key == "epub"


# --------------------------------------------------------------------------
# FB2
# --------------------------------------------------------------------------
def test_fb2_metadata_and_structure(samples):
    book = fb2.load(samples["fb2"])
    assert book.meta.title == "Des Kaisers neue Kleider (FB2)"
    assert book.meta.authors == ["Hans Christian Andersen"]
    assert book.meta.language == "de"
    assert book.cover is not None and book.cover.startswith(b"\x89PNG")

    html = book.chapters[0].html
    assert "<em>Betonung</em>" in html and "<strong>Nachdruck</strong>" in html
    assert "<blockquote>" in html, "<cite> must become a blockquote"
    assert 'class="or-poem"' in html
    assert [e.title for e in book.toc] == ["Erstes Kapitel", "Zweites Kapitel"]


def test_fb2_zip_is_transparent(samples):
    plain = fb2.load(samples["fb2"])
    zipped = fb2.load(samples["fb2zip"])
    assert plain.chapters[0].html == zipped.chapters[0].html


def test_fb2_rejects_broken_xml(tmp_path):
    broken = tmp_path / "kaputt.fb2"
    broken.write_text("<FictionBook><body><p>offen", encoding="utf-8")
    with pytest.raises(LoadError, match="XML"):
        fb2.load(str(broken))


# --------------------------------------------------------------------------
# Comics
# --------------------------------------------------------------------------
def test_cbz_pages_are_naturally_sorted(samples):
    book = comic.load(samples["cbz"])
    assert book.kind is BookKind.COMIC
    assert len(book.images) == 3, "the .txt entry must be ignored"
    assert book.cover is not None


def test_natural_sort_beats_lexicographic():
    names = ["p10.png", "p2.png", "p1.png", "P3.png"]
    assert sorted(names, key=comic.natural_key) == ["p1.png", "p2.png", "P3.png", "p10.png"]


def test_cbr_without_a_tool_explains_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(comic.shutil, "which", lambda _name: None)
    fake = tmp_path / "band.cbr"
    fake.write_bytes(b"Rar!\x1a\x07\x01\x00" + b"\0" * 64)
    with pytest.raises(LoadError) as excinfo:
        comic.load(str(fake))
    assert "unrar" in str(excinfo.value) and "licence" in str(excinfo.value)


# --------------------------------------------------------------------------
# Plain text family
# --------------------------------------------------------------------------
def test_txt_headings_and_paragraphs(samples):
    book = plaintext.load_txt(samples["txt"])
    assert [e.title for e in book.toc] == [
        "DES KAISERS NEUE KLEIDER", "Erstes Kapitel", "Zweites Kapitel",
    ]
    # Hard-wrapped lines inside a paragraph must be joined, not broken.
    assert "<br" not in book.chapters[0].html


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252", "utf-16"])
def test_encoding_detection_roundtrip(tmp_path, encoding):
    path = tmp_path / ("probe_%s.txt" % encoding)
    original = "Größenwahn, Übermut und Straßenfeger.\n\nZweiter Absatz."
    path.write_text(original, encoding=encoding)
    assert "Größenwahn" in plaintext.read_text(str(path))


def test_looks_like_heading():
    assert plaintext.looks_like_heading("KAPITEL EINS")
    assert plaintext.looks_like_heading("Erstes Kapitel")
    assert plaintext.looks_like_heading("Der Wald")
    assert not plaintext.looks_like_heading("Er ging in den Wald hinein.")
    assert not plaintext.looks_like_heading("zwei\nzeilen")
    assert not plaintext.looks_like_heading("x" * 100)


def test_html_loader(samples):
    book = plaintext.load_html(samples["html"])
    assert book.meta.title == "Ein HTML-Buch"
    assert [e.title for e in book.toc] == ["Erstes Kapitel", "Zweites Kapitel"]


def test_rtf_conversion(samples):
    book = plaintext.load_rtf(samples["rtf"])
    assert book.meta.title == "Des Kaisers neue Kleider (RTF)"
    assert book.meta.authors == ["Andersen"]
    html = book.chapters[0].html
    assert "<i>Betonung</i>" in html
    assert "über alles" in html, r"\'fc must decode through the code page"
    assert "überall" in html, r"\u252 must decode as a unicode escape"
    assert [e.title for e in book.toc] == ["Erstes Kapitel", "Zweites Kapitel"]


def test_rtf_drops_metadata_groups():
    html, title, author = plaintext.rtf_to_html(
        r"{\rtf1\ansi{\fonttbl{\f0 Arial;}}{\colortbl;\red0\green0\blue0;}"
        r"{\info{\title T}{\author A}}Sichtbar\par}"
    )
    assert "Arial" not in html and "red0" not in html
    assert "Sichtbar" in html
    assert (title, author) == ("T", "A")


def test_rtf_rejects_non_rtf(tmp_path):
    path = tmp_path / "kein.rtf"
    path.write_text("nur text", encoding="utf-8")
    with pytest.raises(LoadError, match="RTF signature"):
        plaintext.load_rtf(str(path))


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def test_pdf_metadata_and_kind(samples):
    book = pdf.load(samples["pdf"])
    assert book.kind is BookKind.PDF
    assert book.meta.title == "OpenReader PDF-Beispiel"
    assert book.chapters == [], "a PDF is rendered by Qt, not converted to HTML"


def test_pdf_rejects_non_pdf(tmp_path):
    path = tmp_path / "kein.pdf"
    path.write_bytes(b"not a pdf at all" * 4)
    with pytest.raises(LoadError, match="PDF signature"):
        pdf.load(str(path))


def test_file_id_is_stable_and_distinct(samples, tmp_path):
    from openreader.formats.base import file_id

    first = file_id(samples["epub3"])
    copy = tmp_path / "verschoben.epub"
    copy.write_bytes(open(samples["epub3"], "rb").read())
    assert file_id(str(copy)) == first, "moving a file must keep its identity"
    assert file_id(samples["fb2"]) != first
