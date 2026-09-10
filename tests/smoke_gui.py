"""Drive the real window offscreen and capture screenshots.

This is the check that matters most: every view is constructed, a book of each
kind is opened through the real loading path, and the result is rendered to a
PNG that can be looked at.  Run it directly:

    python tests/smoke_gui.py [--visible] [--out DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run(out_dir: str, visible: bool) -> int:
    if not visible:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    data_dir = tempfile.mkdtemp(prefix="lectern-smoke-")
    os.environ["LECTERN_DATA_DIR"] = data_dir

    from PySide6.QtWidgets import QApplication

    from lectern.storage.db import Library
    from lectern.storage.settings import Settings
    from lectern.ui.main_window import MainWindow
    from tests import make_samples

    os.makedirs(out_dir, exist_ok=True)
    samples = make_samples.make_all()

    app = QApplication.instance() or QApplication([])
    window = MainWindow(Settings(), Library())
    window.resize(1180, 820)
    window.show()
    _spin(app, 200)
    _shot(window, out_dir, "00-welcome")

    failures = []
    for name, key in [
        ("01-epub", "epub3"), ("02-mobi", "mobi"), ("03-azw3", "azw3"),
        ("04-fb2", "fb2"), ("05-pdf", "pdf"), ("06-cbz", "cbz"),
        ("07-markdown", "md"), ("08-rtf", "rtf"), ("09-txt", "txt"),
    ]:
        window.open_path(samples[key])
        if not _wait_for_book(app, window, samples[key]):
            failures.append("%s wurde nicht geladen" % key)
            continue
        _spin(app, 350)
        _shot(window, out_dir, name)
        print("  %-12s %-9s %s" % (key, window.book.kind.value, window.book.display_title))

    # -- exercise the interactive paths on the EPUB ----------------------
    window.open_path(samples["epub3"])
    _wait_for_book(app, window, samples["epub3"])
    _spin(app, 300)

    window.run_search("Kaiser", False, False)
    _spin(app, 250)
    if not window._search_matches:
        failures.append("Suche fand nichts")
    _shot(window, out_dir, "10-search")

    window.reader.select_range(60, 140)
    window.add_highlight("green")
    _spin(app, 150)
    if not window.library.highlights(window.book_id):
        failures.append("Markierung wurde nicht gespeichert")
    window.tabs.setCurrentWidget(window.annotation_panel)
    _spin(app, 150)
    _shot(window, out_dir, "11-highlight")

    for theme in ("sepia", "dark"):
        window.apply_theme(theme)
        _spin(app, 300)
        _shot(window, out_dir, "12-theme-%s" % theme)
    window.apply_theme("light")

    # Reading position must survive a close/open cycle.
    window.reader.set_text_position(400)
    _spin(app, 120)
    window._persist_position()
    saved = window.library.state(window.book_id).position
    window.close_book()
    _spin(app, 120)
    window.open_path(samples["epub3"])
    _wait_for_book(app, window, samples["epub3"])
    _spin(app, 400)
    restored = window.reader.text_position()
    if abs(restored - saved) > 40:
        failures.append("Leseposition nicht wiederhergestellt (%d statt %d)" % (restored, saved))

    window.close()
    _spin(app, 100)

    print()
    if failures:
        for problem in failures:
            print("FEHLER:", problem)
        return 1
    print("Alle GUI-Prüfungen bestanden. Screenshots in", out_dir)
    return 0


def _wait_for_book(app, window, path: str, timeout_ms: int = 15000) -> bool:
    from PySide6.QtCore import QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < timeout_ms:
        app.processEvents()
        if window.book is not None and os.path.samefile(window.book.path, path):
            return True
    return False


def _spin(app, milliseconds: int) -> None:
    from PySide6.QtCore import QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < milliseconds:
        app.processEvents()


def _shot(window, out_dir: str, name: str) -> None:
    pixmap = window.grab()
    pixmap.save(os.path.join(out_dir, name + ".png"), "PNG")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "shots"))
    parser.add_argument("--visible", action="store_true")
    options = parser.parse_args()
    raise SystemExit(run(options.out, options.visible))
