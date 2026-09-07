"""Scrolling profiler for the reader view.

Separates the two things that can make scrolling slow, because they have
different fixes:

* text layout — how long the document takes to draw, and whether that gets
  worse further into a long book;
* image handling — whether pictures are decoded once or on every repaint.

Frames are reported separately for passages that show a picture and passages
that do not, which is what turned a vague "scrolling feels bad" into a precise
defect: 5 ms over text against 303 ms over an illustration.

    python tests/bench_reader.py                      # generated illustrated book
    python tests/bench_reader.py --kind plain         # generated plain novel
    python tests/bench_reader.py --book meins.epub    # a book of your own
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: A frame slower than this is visible as a stutter.
SLOW_FRAME_MS = 33.0


def rss_mb() -> float:
    """Resident set size, without pulling in a dependency for it."""

    if sys.platform == "win32":
        import ctypes.wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        function = ctypes.windll.kernel32.K32GetProcessMemoryInfo
        function.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(Counters),
                             ctypes.wintypes.DWORD]
        function.restype = ctypes.wintypes.BOOL
        if not function(ctypes.windll.kernel32.GetCurrentProcess(),
                        ctypes.byref(counters), counters.cb):
            return 0.0
        return counters.WorkingSetSize / 1e6
    try:
        with open("/proc/self/statm") as handle:
            return int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except OSError:
        return 0.0


def _spin(app, milliseconds: int) -> None:
    from PySide6.QtCore import QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < milliseconds:
        app.processEvents()


def _report(label: str, frames: list[float]) -> None:
    if not frames:
        return
    ordered = sorted(frames)
    print("  %-12s Median %7.2f ms  95%% %7.2f ms  Max %7.2f ms  (%d Frames)"
          % (label, statistics.median(ordered), ordered[int(len(ordered) * 0.95)],
             ordered[-1], len(frames)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", help="EPUB, das vermessen werden soll")
    parser.add_argument("--kind", choices=("illustrated", "plain"), default="illustrated",
                        help="welches Testbuch erzeugt wird, wenn --book fehlt")
    parser.add_argument("--notches", type=int, default=150)
    parser.add_argument("--cache-mb", type=int, default=0,
                        help="Bildcache-Budget überschreiben (0 = Vorgabe)")
    options = parser.parse_args()
    os.environ["OPENREADER_DATA_DIR"] = tempfile.mkdtemp(prefix="openreader-bench-")

    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    from openreader.storage.db import Library
    from openreader.storage.settings import Settings
    from openreader.ui import reader_view
    from openreader.ui.main_window import MainWindow

    book_path = options.book
    if not book_path:
        from tests.make_heavy_book import build_illustrated, build_plain

        book_path = os.path.join(tempfile.gettempdir(),
                                 "openreader-bench-%s.epub" % options.kind)
        if not os.path.exists(book_path):
            builder = build_illustrated if options.kind == "illustrated" else build_plain
            builder(book_path)

    if options.cache_mb:
        reader_view.IMAGE_CACHE_BUDGET = options.cache_mb * 1024 * 1024

    # -- instrumentation ---------------------------------------------------
    loads = {"count": 0, "ms": 0.0}
    original_load = reader_view._BookDocument.loadResource

    def counting_load(self, kind, name):
        start = time.perf_counter()
        result = original_load(self, kind, name)
        loads["ms"] += (time.perf_counter() - start) * 1000
        loads["count"] += 1
        return result

    reader_view._BookDocument.loadResource = counting_load

    decodes = {"count": 0}
    original_decode = reader_view._BookDocument._decode

    def counting_decode(self, data, target):
        decodes["count"] += 1
        return original_decode(self, data, target)

    reader_view._BookDocument._decode = counting_decode

    print("Buch: %s  (%.1f MB)" % (os.path.basename(book_path),
                                   os.path.getsize(book_path) / 1e6))
    print("Bildcache-Budget: %d MB\n" % (reader_view.IMAGE_CACHE_BUDGET / 1024 / 1024))

    app = QApplication.instance() or QApplication([])
    window = MainWindow(Settings(), Library())
    window.showMaximized()
    _spin(app, 400)
    before = rss_mb()

    started = time.perf_counter()
    window.open_path(book_path)
    while window.book is None and time.perf_counter() - started < 300:
        app.processEvents()
    load_seconds = time.perf_counter() - started
    _spin(app, 1500)

    reader = window.reader
    document = reader.document()
    bar = reader.verticalScrollBar()
    viewport = reader.viewport()

    print("--- Laden ---")
    print("  Dauer                %8.2f s" % load_seconds)
    print("  Bilder dekodiert     %8d  (%.0f ms)" % (decodes["count"], loads["ms"]))
    print("  Speicher             %8.0f MB  (+%.0f MB)" % (rss_mb(), rss_mb() - before))
    print("  Dokument: %.0f px hoch, %d Blöcke, %d Zeichen"
          % (document.size().height(), document.blockCount(), document.characterCount()))
    print("  Sichtbereich %dx%d, dpr %.2f"
          % (viewport.width(), viewport.height(), app.devicePixelRatio()))

    # -- wheel scroll from the start ---------------------------------------
    loads["count"] = loads["ms"] = 0
    decodes["count"] = 0
    bar.setValue(0)
    _spin(app, 300)

    centre = QPointF(viewport.width() / 2, viewport.height() / 2)
    global_pos = QPointF(viewport.mapToGlobal(QPoint(int(centre.x()), int(centre.y()))))

    frames: list[float] = []
    showed_image: list[bool] = []
    for _ in range(options.notches):
        before_loads = loads["count"]
        event = QWheelEvent(centre, global_pos, QPoint(0, -120), QPoint(0, -120),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        begin = time.perf_counter()
        app.sendEvent(viewport, event)
        viewport.repaint()
        app.processEvents()
        frames.append((time.perf_counter() - begin) * 1000)
        showed_image.append(loads["count"] > before_loads)

    print("\n--- Mausrad, %d Rasten ---" % options.notches)
    _report("alle", frames)
    _report("ohne Bild", [f for f, image in zip(frames, showed_image, strict=True) if not image])
    _report("mit Bild", [f for f, image in zip(frames, showed_image, strict=True) if image])

    slow = [f for f in frames if f > SLOW_FRAME_MS]
    print("  Frames über %.0f ms (unter 30 fps): %d von %d"
          % (SLOW_FRAME_MS, len(slow), len(frames)))
    print("  Bildanfragen %d, davon echte Dekodierungen %d  (%.0f ms)"
          % (loads["count"], decodes["count"], loads["ms"]))
    print("  Speicher nach dem Scrollen: %.0f MB" % rss_mb())

    verdict = "in Ordnung" if not slow else "AUFFÄLLIG: %d ruckelnde Frames" % len(slow)
    print("\nErgebnis: %s" % verdict)

    window.close()
    return 0 if not slow else 1


if __name__ == "__main__":
    raise SystemExit(main())
