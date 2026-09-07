"""Widget-level tests driving the real window.

Run against the platform's own renderer when one is available so that text
shaping is exercised too; the offscreen plugin has no fonts and would make
every glyph a box, which is fine for layout maths but not for anything else.
"""

from __future__ import annotations

import os

import pytest

from . import make_samples

pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    os.environ["OPENREADER_DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture(scope="module")
def samples():
    return make_samples.make_all()


@pytest.fixture
def window(app, tmp_path):
    from openreader.storage.db import Library
    from openreader.storage.settings import Settings
    from openreader.ui.main_window import MainWindow

    settings = Settings(str(tmp_path / "settings.json"))
    library = Library(str(tmp_path / "library.sqlite3"))
    win = MainWindow(settings, library)
    win.resize(1000, 720)
    win.show()
    _spin(app, 120)
    yield win
    win.close()
    library.close()


def _spin(app, milliseconds: int = 200) -> None:
    from PySide6.QtCore import QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < milliseconds:
        app.processEvents()


def _open(app, window, path: str, timeout_ms: int = 15000) -> None:
    from PySide6.QtCore import QElapsedTimer

    window.open_path(path)
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < timeout_ms:
        app.processEvents()
        if window.book is not None and os.path.samefile(window.book.path, path):
            _spin(app, 250)
            return
    raise AssertionError("Buch wurde nicht geladen: %s" % path)


# --------------------------------------------------------------------------
def test_window_starts_on_the_welcome_screen(window):
    assert window.stack.currentWidget() is window.welcome
    assert window.book is None


@pytest.mark.parametrize("key,view", [
    ("epub3", "reader"), ("mobi", "reader"), ("azw3", "reader"), ("fb2", "reader"),
    ("txt", "reader"), ("md", "reader"), ("rtf", "reader"), ("html", "reader"),
    ("pdf", "pdf"), ("cbz", "comic"),
])
def test_every_format_opens_in_the_right_view(app, window, samples, key, view):
    _open(app, window, samples[key])
    assert window.stack.currentWidget() is getattr(window, view)
    assert window.toc_panel.topLevelItemCount() >= 1


def test_text_document_is_laid_out(app, window, samples):
    _open(app, window, samples["epub3"])
    document = window.reader.document()
    assert document.characterCount() > 200
    assert document.size().height() > 100, "the document must have real height"
    assert window.reader.page_count >= 1


def test_image_lines_do_not_inflate_the_layout(app, window, samples):
    """A tall image in a 155 % line-height block must not reserve 155 % of its height."""

    _open(app, window, samples["epub3"])
    document = window.reader.document()
    layout = document.documentLayout()

    block = document.begin()
    while block.isValid():
        if "￼" in block.text():
            rect = layout.blockBoundingRect(block)
            following = block.next()
            while following.isValid() and not following.text().strip():
                following = following.next()
            if following.isValid():
                gap = layout.blockBoundingRect(following).y() - (rect.y() + rect.height())
                assert gap < 100, "unexpected hole of %.0f px below an image" % gap
        block = block.next()


def test_toc_navigation_moves_the_view(app, window, samples):
    _open(app, window, samples["epub3"])
    window.reader.go_to_start()
    _spin(app)
    window.go_to_target("#ch2")
    _spin(app)
    assert window.reader.verticalScrollBar().value() > 0


def test_paging_moves_forward_and_back(app, window, samples):
    _open(app, window, samples["epub3"])
    window.reader.go_to_start()
    _spin(app)
    window.next_page()
    _spin(app)
    after = window.reader.verticalScrollBar().value()
    assert after > 0
    window.previous_page()
    _spin(app)
    assert window.reader.verticalScrollBar().value() < after


def test_search_finds_and_navigates(app, window, samples):
    _open(app, window, samples["epub3"])
    # "sein" occurs in both chapters, so it exercises cross-chapter search.
    window.run_search("sein", False, False)
    _spin(app)
    assert len(window._search_matches) >= 3
    assert window.search_panel.results.count() >= 3

    window.next_match()
    _spin(app)
    start, end = window._search_matches[window._search_index]
    cursor_start, cursor_end, _text = window.reader.selected_range()
    assert (cursor_start, cursor_end) == (start, end)


def test_search_is_case_and_word_sensitive(app, window, samples):
    _open(app, window, samples["epub3"])
    window.run_search("kaiser", True, False)
    _spin(app)
    exact = len(window._search_matches)
    window.run_search("kaiser", False, False)
    _spin(app)
    assert len(window._search_matches) > exact


def test_highlight_survives_reopening(app, window, samples):
    _open(app, window, samples["epub3"])
    window.reader.select_range(80, 130)
    window.add_highlight("blue")
    _spin(app)

    stored = window.library.highlights(window.book_id)
    assert len(stored) == 1
    assert stored[0].colour == "blue" and stored[0].excerpt.strip()
    assert window.annotation_panel.list.count() == 1

    window.close_book()
    _spin(app)
    _open(app, window, samples["epub3"])
    assert len(window.library.highlights(window.book_id)) == 1
    assert window.annotation_panel.list.count() == 1


def test_reading_position_is_restored(app, window, samples):
    _open(app, window, samples["epub3"])
    window.reader.set_text_position(300)
    _spin(app)
    window._persist_position()
    saved = window.library.state(window.book_id).position
    assert saved > 0

    window.close_book()
    _spin(app)
    _open(app, window, samples["epub3"])
    _spin(app, 400)
    assert abs(window.reader.text_position() - saved) < 60


def test_bookmarks_appear_in_the_panel(app, window, samples, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Mein Zeichen", True)))
    _open(app, window, samples["epub3"])
    window.add_bookmark()
    _spin(app)
    assert window.bookmark_panel.list.count() == 1
    assert len(window.library.bookmarks(window.book_id)) == 1


def test_theme_switch_keeps_the_document(app, window, samples):
    _open(app, window, samples["epub3"])
    before = window.reader.document().characterCount()
    for theme in ("sepia", "dark", "black", "light"):
        window.apply_theme(theme)
        _spin(app, 150)
        assert window.reader.document().characterCount() == before, \
            "restyling must not lose or duplicate content"
    assert window.settings["theme"] == "light"


def test_font_size_change_reflows(app, window, samples):
    _open(app, window, samples["epub3"])
    small_height = window.reader.document().size().height()
    window.set_font_size(30)
    _spin(app, 250)
    assert window.reader.document().size().height() > small_height


def test_pdf_pages_and_outline(app, window, samples):
    _open(app, window, samples["pdf"])
    assert window.pdf.page_count == 2
    window.pdf.go_to_page(1)
    _spin(app)
    assert window.pdf.current_page == 2


def test_comic_pages(app, window, samples):
    _open(app, window, samples["cbz"])
    assert window.comic.page_count == 3
    window.comic.go_to_page(2)
    _spin(app)
    assert window.comic.current_page == 3


def test_broken_file_reports_instead_of_crashing(app, window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self.text()))

    broken = tmp_path / "kaputt.epub"
    broken.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
    window.open_path(str(broken))
    _spin(app, 3000)
    assert shown, "the user must be told why a file could not be opened"
    assert window.book is None


def test_drm_file_is_explained(app, window, samples, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self.text()))
    window.open_path(samples["drm"])
    _spin(app, 3000)
    assert shown and "DRM" in shown[0]
