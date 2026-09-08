"""Regression tests for the findings of the 2026-09-08 audit.

One test class per finding, named so a failure points straight back at the
report.  Most of these guard against silent misbehaviour — content that
disappears, a position that stops being saved, a limit that stops applying —
which is exactly the kind of defect that returns unnoticed.
"""

from __future__ import annotations

import os
import struct
import sys
import zipfile

import pytest

from openreader.formats.base import ExpansionBudget, LoadError, parse_xml
from openreader.render.html_clean import normalize_ex

from . import make_samples


# -- F-02: a hidden empty element swallowed the rest of the chapter ---------
class TestHiddenElementsDoNotSwallowContent:
    @pytest.mark.parametrize("markup", [
        '<img src="a.png" style="display:none" />',
        '<br style="display:none" />',
        '<hr style="display:none">',
        '<meta charset="utf-8">',
        '<link rel="stylesheet" href="x.css">',
        '<input type="text">',
        '<area shape="rect">',
        '<source src="x">',
    ])
    def test_void_element_drops_only_itself(self, markup):
        body, _title, truncated = normalize_ex(
            "<p>vorher</p>%s<p>NACHHER</p>" % markup, anchor_prefix="c0"
        )
        assert "NACHHER" in body, "content after %s was lost" % markup
        assert not truncated

    def test_hidden_container_still_hides_its_contents(self):
        body, _title, truncated = normalize_ex(
            '<p>vorher</p><div style="display:none"><p>geheim</p></div><p>NACHHER</p>',
            anchor_prefix="c0",
        )
        assert "geheim" not in body
        assert "vorher" in body and "NACHHER" in body
        assert not truncated

    def test_unclosed_hidden_container_is_reported(self):
        """Losing the rest of a chapter is acceptable only if we say so."""

        body, _title, truncated = normalize_ex(
            '<p>vorher</p><div style="display:none"><p>NACHHER', anchor_prefix="c0"
        )
        assert "NACHHER" not in body
        assert truncated, "truncation must be reported, not silent"

    def test_truncation_reaches_the_book_as_a_warning(self, tmp_path):
        from openreader.formats import load

        source = make_samples.make_epub("truncation.epub")
        target = str(tmp_path / "truncated.epub")
        with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith("ch1.xhtml"):
                    data = data.replace(b"<body>", b'<body><div style="display:none">')
                zout.writestr(item, data)
        book = load(target)
        assert any("unvollständig" in warning for warning in book.warnings)


# -- F-03: resource exhaustion from a small file ----------------------------
class TestExpansionBudget:
    def test_declared_size_is_rejected_before_reading(self):
        budget = ExpansionBudget(limit=1000)
        with pytest.raises(LoadError, match="entpackt"):
            budget.check(5000, "bombe.png")

    def test_actual_size_is_caught_when_the_header_lied(self):
        budget = ExpansionBudget(limit=1000)
        budget.check(10, "klein.png")          # header claims it is tiny
        with pytest.raises(LoadError):
            budget.spend(5000, "klein.png")    # reality differs

    def test_a_zip_bomb_is_refused(self, tmp_path):
        from openreader.formats import comic

        path = str(tmp_path / "bombe.cbz")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for index in range(4):
                zf.writestr("page%02d.png" % index, b"\0" * (200 * 1024 * 1024))
        with pytest.raises(LoadError, match="entpackt"):
            comic.load(path)

    def test_a_normal_comic_still_opens(self, tmp_path):
        from openreader.formats import comic

        book = comic.load(make_samples.make_cbz("normal.cbz"))
        assert len(book.images) >= 1

    def test_forged_huff_count_is_refused(self):
        """A 300-byte file claimed 0x0FFFFFFF table entries and ate 2 GB."""

        from openreader.formats.mobi import _make_decompressor

        class FakeDb:
            count = 12

            def record(self, index):
                return b"\0" * 16

        with pytest.raises(LoadError, match="widersprüchlich"):
            _make_decompressor(FakeDb(), 17480, huff_offset=2, huff_count=0x0FFFFFFF)


# -- F-04: DRM detection must not be disabled by font obfuscation -----------
class TestDrmDetection:
    FONT = ('<EncryptedData xmlns="http://www.w3.org/2001/04/xmlenc#">'
            '<EncryptionMethod Algorithm="http://www.idpf.org/2008/embedding"/>'
            '<CipherData><CipherReference URI="OEBPS/f.otf"/></CipherData></EncryptedData>')
    DRM = ('<EncryptedData xmlns="http://www.w3.org/2001/04/xmlenc#">'
           '<EncryptionMethod Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/>'
           '<CipherData><CipherReference URI="OEBPS/ch0.xhtml"/></CipherData></EncryptedData>')

    def _build(self, tmp_path, inner):
        from openreader.formats import load

        source = make_samples.make_epub("drm_base.epub")
        target = str(tmp_path / "probe.epub")
        with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, "w") as zout:
            for item in zin.infolist():
                zout.writestr(item, zin.read(item.filename))
            zout.writestr(
                "META-INF/encryption.xml",
                '<?xml version="1.0"?><encryption '
                'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">%s</encryption>'
                % inner,
            )
        return load, target

    def test_font_obfuscation_alone_is_not_drm(self, tmp_path):
        load, path = self._build(tmp_path, self.FONT)
        assert load(path).chapters, "an obfuscated font must not block reading"

    @pytest.mark.parametrize("inner_name", ["DRM", "FONT+DRM", "DRM+FONT"])
    def test_content_encryption_is_always_detected(self, tmp_path, inner_name):
        from openreader.formats.base import DRMError

        inner = {"DRM": self.DRM,
                 "FONT+DRM": self.FONT + self.DRM,
                 "DRM+FONT": self.DRM + self.FONT}[inner_name]
        load, path = self._build(tmp_path, inner)
        with pytest.raises(DRMError):
            load(path)


# -- F-05: damaged files must produce sentences, not tracebacks -------------
class TestDamagedFilesFailGracefully:
    @pytest.mark.parametrize("size", [4, 8, 12, 20, 40, 78, 100])
    def test_truncated_mobi_headers(self, tmp_path, size):
        from openreader.formats import mobi

        raw = bytearray(b"\0" * 78)
        raw[60:68] = b"BOOKMOBI"
        struct.pack_into(">H", raw, 76, 1)
        path = str(tmp_path / "kurz.mobi")
        with open(path, "wb") as handle:
            handle.write(bytes(raw[:size]))
        with pytest.raises(LoadError):
            mobi.load(path)          # a LoadError, never struct.error

    @pytest.mark.parametrize("source", [
        r"{\rtf1\ansi 香999 x}",
        r"{\rtf1\ansi\ansicpg99999 Hallo}",
        r"{\rtf1\ansi \u-3 x}",
        r"{\rtf1\ansi\ansicpg0 x}",
    ])
    def test_rtf_edge_cases(self, source):
        from openreader.formats.plaintext import rtf_to_html

        body, _title, _author = rtf_to_html(source)
        assert isinstance(body, str)


# -- F-09: an image path must not escape the book's directory ---------------
class TestImagePathsStayInsideTheBook:
    def test_sibling_directory_with_a_shared_prefix_is_refused(self, tmp_path):
        from openreader.formats import plaintext

        book_dir = tmp_path / "buch"
        secret_dir = tmp_path / "buch_geheim"
        book_dir.mkdir()
        secret_dir.mkdir()
        (secret_dir / "privat.png").write_bytes(make_samples.PNG)
        page = book_dir / "b.html"
        page.write_text('<html><body><img src="../buch_geheim/privat.png"></body></html>',
                        encoding="utf-8")

        book = plaintext.load_html(str(page))
        assert not book.resources, "a neighbouring directory must stay out of reach"

    def test_traversal_is_refused(self, tmp_path):
        from openreader.formats import plaintext

        book_dir = tmp_path / "buch"
        book_dir.mkdir()
        page = book_dir / "b.html"
        page.write_text('<html><body><img src="../../../../etc/passwd"></body></html>',
                        encoding="utf-8")
        assert not plaintext.load_html(str(page)).resources

    def test_an_image_beside_the_book_still_loads(self, tmp_path):
        from openreader.formats import plaintext

        (tmp_path / "bild.png").write_bytes(make_samples.PNG)
        page = tmp_path / "b.html"
        page.write_text('<html><body><img src="bild.png"></body></html>', encoding="utf-8")
        assert plaintext.load_html(str(page)).resources


# -- F-11: XML entity bombs and XXE -----------------------------------------
class TestXmlEntitiesAreRefused:
    def test_entity_bomb(self):
        bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [\n'
                b'<!ENTITY a "aaaaaaaaaa">\n<!ENTITY b "&a;&a;&a;&a;&a;">\n]>\n'
                b'<FictionBook><body>&b;</body></FictionBook>')
        with pytest.raises(LoadError, match="Entity"):
            parse_xml(bomb)

    def test_external_entity(self):
        xxe = (b'<?xml version="1.0"?><!DOCTYPE r ['
               b'<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>')
        with pytest.raises(LoadError, match="Entity"):
            parse_xml(xxe)

    def test_ordinary_doctype_is_fine(self):
        assert parse_xml(b'<!DOCTYPE html><html><body>Text</body></html>') is not None

    def test_the_word_entity_in_prose_is_fine(self):
        element = parse_xml(b"<r><p>Hier steht &lt;!ENTITY im Flie\xc3\x9ftext</p></r>")
        assert element is not None


# -- F-15: settings must be range-checked, not merely type-coerced ----------
class TestSettingsAreClamped:
    @pytest.mark.parametrize("key,value,expected", [
        ("font_size", 1000000, 96),
        ("font_size", -5, 6),
        ("page_margin", -50, 0),
        ("line_height", 99, 4.0),
        ("pdf_zoom", 0, 0.05),
        ("theme", "neon", "light"),
        ("comic_fit", "bogus", "width"),
    ])
    def test_out_of_range_values_are_clamped(self, tmp_path, key, value, expected):
        import json

        from openreader.storage.settings import Settings

        path = tmp_path / "settings.json"
        path.write_text(json.dumps({key: value}), encoding="utf-8")
        assert Settings(str(path))[key] == expected

    def test_assignment_is_clamped_too(self, tmp_path):
        from openreader.storage.settings import Settings

        settings = Settings(str(tmp_path / "s.json"))
        settings["font_size"] = 99999
        assert settings["font_size"] == 96


# -- F-07: a failed write must be reported, not swallowed -------------------
class TestStorageFailureIsVisible:
    def test_save_position_reports_failure(self, tmp_path):
        from openreader.storage.db import Library

        library = Library(str(tmp_path / "lib.sqlite3"))
        library.remember_book("id1", "/pfad/b.epub", "Titel", "Autor", "epub")
        assert library.save_position("id1", 10, 100) is True
        assert library.degraded is False

        library.connection.close()          # simulate a broken database
        assert library.save_position("id1", 20, 100) is False
        assert library.degraded is True

    def test_connection_has_a_busy_timeout(self, tmp_path):
        from openreader.storage.db import Library

        library = Library(str(tmp_path / "lib.sqlite3"))
        timeout = library.connection.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout >= 1000, "a second instance must wait, not fail instantly"
        library.close()


# -- F-08: the data directory belongs to its owner alone --------------------
@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions do not apply on Windows")
def test_data_directory_is_private(tmp_path, monkeypatch):
    from openreader.storage import paths

    target = tmp_path / "daten"
    monkeypatch.setenv("OPENREADER_DATA_DIR", str(target))
    created = paths.data_dir()
    assert oct(os.stat(created).st_mode & 0o777) == "0o700"


# -- F-16: the image cache must honour its budget ---------------------------
def test_image_cache_never_exceeds_its_budget():
    from PySide6.QtGui import QImage

    from openreader.ui.reader_view import _ImageCache

    cache = _ImageCache(budget=4 * 1024 * 1024)
    for index in range(12):
        image = QImage(512, 512, QImage.Format_ARGB32)
        cache.put(("bild%d.png" % index, 600), image)
        assert cache._bytes <= cache.budget, "the last entry must not blow the budget"


def test_mobi_anchor_insertion_is_linear():
    """The quadratic version rebuilt the whole buffer per footnote target."""

    import time

    from openreader.formats.base import Book
    from openreader.formats.mobi import _build_document

    def run(count: int) -> float:
        body = b"".join(b'<a filepos=%08d>x</a><p>Text</p>' % (i * 40) for i in range(count))
        book = Book(path="x.mobi")
        start = time.perf_counter()
        _build_document(book, body, "utf-8", {}, is_kf8=False)
        return time.perf_counter() - start

    small = run(500)
    large = run(4000)
    # Eight times the work; quadratic behaviour would be ~64x, so anything
    # under 20x proves the loop is no longer rebuilding the buffer each time.
    assert large < max(0.05, small * 20), "anchor insertion looks quadratic again"


# -- F-01: cancelling a running load must not abort the process -------------
def test_cancelling_a_running_load_does_not_crash():
    """Runs in its own process: the old failure was a Qt fatal, not an exception.

    Before the fix this exited with 0xC0000409 — Qt aborting because the last
    reference to a still-running QThread had been dropped — which would have
    taken the whole test session with it.
    """

    import subprocess

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_cancel_crash.py")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, timeout=300, check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, (
        "Abbruch eines laufenden Ladevorgangs endete mit %s (0x%08X)\n%s"
        % (result.returncode, result.returncode & 0xFFFFFFFF,
           result.stdout.decode("utf-8", "replace")[-800:])
    )
