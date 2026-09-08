"""Quantify the remaining stutter, to decide whether prefetching is worth it.

After the image cache landed, one cost remains: the very first time a picture
comes into view it still has to be decoded, on the main thread, inside the
frame that reveals it.  Prefetching in a background thread could remove that —
but only if the stutter is actually worth removing.

This measures the ceiling of that benefit on three realistic patterns:

1. Reading the whole book by page turns, which is what a reader really does.
2. Scrolling back and forth across an illustrated stretch, where a bounded
   cache may evict a picture and have to decode it again.
3. Jumping through the table of contents, which lands on fresh pages with no
   locality at all.

The verdict is deliberately expressed in what a reader would notice: how many
stutters over a full book, and how long each one lasts.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.bench_reader import _spin, rss_mb  # noqa: E402

#: A frame this long is where a reader starts to feel a hitch rather than see
#: a smooth turn.  One dropped frame at 60 Hz is 16.7 ms.
NOTICEABLE_MS = 20.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True)
    options = parser.parse_args()
    os.environ["OPENREADER_DATA_DIR"] = tempfile.mkdtemp(prefix="openreader-prefetch-")

    from PySide6.QtWidgets import QApplication

    from openreader.storage.db import Library
    from openreader.storage.settings import Settings
    from openreader.ui import reader_view
    from openreader.ui.main_window import MainWindow

    decodes = {"count": 0, "ms": 0.0, "sizes": []}
    original_decode = reader_view._BookDocument._decode

    def counting_decode(self, data, target):
        start = time.perf_counter()
        result = original_decode(self, data, target)
        elapsed = (time.perf_counter() - start) * 1000
        decodes["count"] += 1
        decodes["ms"] += elapsed
        decodes["sizes"].append((len(data) / 1e6, elapsed))
        return result

    reader_view._BookDocument._decode = counting_decode

    app = QApplication.instance() or QApplication([])
    window = MainWindow(Settings(), Library())
    window.showMaximized()
    _spin(app, 400)

    window.open_path(options.book)
    started = time.perf_counter()
    while window.book is None and time.perf_counter() - started < 300:
        app.processEvents()
    _spin(app, 1500)

    reader = window.reader
    bar = reader.verticalScrollBar()
    viewport = reader.viewport()
    book = window.book
    pictures = [key for key in book.resources
                if key.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))]

    print("Buch: %s (%.1f MB)" % (os.path.basename(options.book),
                                  os.path.getsize(options.book) / 1e6))
    print("Bilder im Buch: %d, Cache-Budget %d MB"
          % (len(pictures), reader_view.IMAGE_CACHE_BUDGET / 1024 / 1024))
    print("Dokument %.0f px, Seitenhöhe %d px -> %d Seiten\n"
          % (reader.document().size().height(), viewport.height(),
             max(1, int(reader.document().size().height() // max(1, viewport.height())))))

    def sweep(label: str, positions: list[int]) -> dict:
        decodes["count"] = 0
        decodes["ms"] = 0.0
        frames: list[float] = []
        cold: list[float] = []
        for value in positions:
            before = decodes["count"]
            begin = time.perf_counter()
            bar.setValue(value)
            viewport.repaint()
            app.processEvents()
            elapsed = (time.perf_counter() - begin) * 1000
            frames.append(elapsed)
            if decodes["count"] > before:
                cold.append(elapsed)
        warm = [f for f in frames if f not in cold]
        result = {
            "frames": frames, "cold": cold, "warm": warm,
            "decodes": decodes["count"], "decode_ms": decodes["ms"],
        }
        print("%s (%d Schritte)" % (label, len(positions)))
        print("  warme Frames : Median %6.2f ms   95%% %6.2f ms"
              % (statistics.median(warm) if warm else 0, _percentile(warm, 0.95)))
        if cold:
            print("  KALTE Frames : %d Stück, Median %6.2f ms, Max %6.2f ms"
                  % (len(cold), statistics.median(cold), max(cold)))
        else:
            print("  KALTE Frames : keine")
        print("  Dekodierungen: %d (%.0f ms gesamt)" % (decodes["count"], decodes["ms"]))
        print("  spürbar (>%.0f ms): %d von %d Frames\n"
              % (NOTICEABLE_MS, len([f for f in frames if f > NOTICEABLE_MS]), len(frames)))
        return result

    page = max(1, viewport.height() - 18)
    maximum = bar.maximum()

    # 1. read the whole book, page by page
    bar.setValue(0)
    _spin(app, 300)
    forward = sweep("1. Ganzes Buch vorwärts blättern",
                    list(range(0, maximum + 1, page)))

    # 2. back and forth over the illustrated opening, where plates sit together
    dense_end = min(maximum, page * 12)
    positions = []
    for _ in range(4):
        positions += list(range(0, dense_end, page))
        positions += list(range(dense_end, 0, -page))
    shuttle = sweep("2. Vor und zurück im Bildteil", positions)

    # 3. jump around via the table of contents
    targets = []
    for index in range(len(book.toc)):
        entry = book.toc[index]
        targets.append(entry)
    jumps = []
    for round_trip in range(3):
        for offset, _entry in enumerate(targets):
            jumps.append(int(maximum * ((offset * 7 + round_trip * 3) % max(1, len(targets)))
                             / max(1, len(targets))))
    toc = sweep("3. Über das Inhaltsverzeichnis springen", jumps)

    # 4. continuous wheel scrolling through the whole book.  This is the case
    #    the original complaint came from, and the one where a hitch is most
    #    visible: it interrupts motion rather than a discrete page turn.
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    centre = QPointF(viewport.width() / 2, viewport.height() / 2)
    global_pos = QPointF(viewport.mapToGlobal(QPoint(int(centre.x()), int(centre.y()))))
    bar.setValue(0)
    _spin(app, 300)
    decodes["count"] = 0
    decodes["ms"] = 0.0

    wheel_frames: list[float] = []
    wheel_cold: list[float] = []
    guard = 0
    while bar.value() < maximum and guard < 20000:
        guard += 1
        before = decodes["count"]
        event = QWheelEvent(centre, global_pos, QPoint(0, -120), QPoint(0, -120),
                            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
        begin = time.perf_counter()
        app.sendEvent(viewport, event)
        viewport.repaint()
        app.processEvents()
        elapsed = (time.perf_counter() - begin) * 1000
        wheel_frames.append(elapsed)
        if decodes["count"] > before:
            wheel_cold.append(elapsed)

    warm_wheel = [f for f in wheel_frames if f not in wheel_cold]
    print("4. Ganzes Buch durchscrollen (%d Rasten)" % len(wheel_frames))
    print("  warme Frames : Median %6.2f ms   95%% %6.2f ms"
          % (statistics.median(warm_wheel) if warm_wheel else 0,
             _percentile(warm_wheel, 0.95)))
    if wheel_cold:
        print("  KALTE Frames : %d Stück, Median %6.2f ms, Max %6.2f ms"
              % (len(wheel_cold), statistics.median(wheel_cold), max(wheel_cold)))
    print("  spürbar (>%.0f ms): %d von %d Frames  (%.2f %%)\n"
          % (NOTICEABLE_MS, len([f for f in wheel_frames if f > NOTICEABLE_MS]),
             len(wheel_frames),
             100 * len([f for f in wheel_frames if f > NOTICEABLE_MS]) / len(wheel_frames)))

    # -- what a prefetcher could actually save -----------------------------
    print("=" * 68)
    all_cold = forward["cold"] + shuttle["cold"] + toc["cold"]
    warm_median = statistics.median(forward["warm"]) if forward["warm"] else 0.0
    print("Kalte Frames insgesamt: %d" % len(all_cold))
    if all_cold:
        overhead = [c - warm_median for c in all_cold]
        print("Aufschlag je kaltem Frame: Median %.1f ms, Max %.1f ms"
              % (statistics.median(overhead), max(overhead)))
        print("Davon spürbar (>%.0f ms): %d"
              % (NOTICEABLE_MS, len([c for c in all_cold if c > NOTICEABLE_MS])))

    print("\nEinmal ganz durchlesen (%d Seiten):" % len(forward["frames"]))
    print("  %d Ruckler, zusammen %.0f ms verlorene Zeit"
          % (len(forward["cold"]), sum(forward["cold"]) - warm_median * len(forward["cold"])))

    print("\nWiederholtes Blättern im Bildteil:")
    print("  %d Dekodierungen bei %d Bildern im Buch -> %s"
          % (shuttle["decodes"], len(pictures),
             "Cache wirft Bilder wieder raus" if shuttle["decodes"] > len(pictures)
             else "Cache hält, keine Doppelarbeit"))

    if decodes["sizes"]:
        largest = max(decodes["sizes"])
        print("\nTeuerste einzelne Dekodierung: %.1f MB Quelldatei -> %.0f ms"
              % largest)
    print("Speicher am Ende: %.0f MB" % rss_mb())

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
