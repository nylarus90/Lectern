"""Reproduce F-01: cancelling a running load used to abort the process.

Run as a separate process, because the failure mode is a Qt fatal — it takes
the whole interpreter with it and would abort the test suite rather than fail
a test.  ``tests/test_audit_fixes.py`` invokes this and checks the exit code.

    python tests/check_cancel_crash.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["OPENREADER_DATA_DIR"] = tempfile.mkdtemp(prefix="openreader-cancel-")

    from PySide6.QtWidgets import QApplication

    from openreader.storage.db import Library
    from openreader.storage.settings import Settings
    from openreader.ui import loader as loader_module
    from openreader.ui.main_window import MainWindow

    # A loader that blocks far longer than the old three-second wait, so the
    # worker is guaranteed to still be running when cancel() arrives.
    original_load = loader_module.load_book

    def slow_load(path, progress):
        for step in range(60):
            progress(step, "künstlich langsam")
            time.sleep(0.1)
        return original_load(path, progress)

    loader_module.load_book = slow_load

    from tests import make_samples

    book = make_samples.make_epub("cancel_probe.epub")

    app = QApplication.instance() or QApplication([])
    window = MainWindow(Settings(), Library())
    window.show()
    app.processEvents()

    window.open_path(book)
    app.processEvents()
    time.sleep(0.4)                       # let the worker get well underway
    app.processEvents()
    assert window.loader.busy, "der Ladevorgang läuft nicht"

    # 1. Cancelling must return promptly and must not abort the process.
    start = time.perf_counter()
    window.loader.cancel()
    blocked = time.perf_counter() - start
    print("cancel() blockierte die Oberfläche: %.2f s" % blocked)
    if blocked > 1.0:
        print("FEHLER: cancel() blockiert die Oberfläche")
        return 2

    # 2. The window must stay usable, and a second book must still open.
    loader_module.load_book = original_load
    window.open_path(book)
    deadline = time.perf_counter() + 30
    while window.book is None and time.perf_counter() < deadline:
        app.processEvents()
    if window.book is None:
        print("FEHLER: nach dem Abbruch ließ sich kein Buch mehr öffnen")
        return 3
    print("nach dem Abbruch geöffnet:", window.book.display_title)

    # 3. Closing waits for the abandoned thread rather than destroying it.
    window.close()
    app.processEvents()
    print("sauber beendet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
