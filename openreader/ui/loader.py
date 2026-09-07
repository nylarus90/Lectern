"""Background book loading.

Parsing a large EPUB or decompressing a MOBI takes long enough to freeze the
window, so it happens on a worker thread.  The assembled HTML is built here too
— string work, no Qt objects — and only handed to the view at the end, which is
what keeps every ``QTextDocument`` operation on the GUI thread.
"""

from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QThread, Signal

from ..formats import load as load_book
from ..formats.base import Book, LoadError


class LoadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object, str)   # Book, assembled HTML
    failed = Signal(str, str)        # short message, detail

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            book = load_book(self.path, self._report)
            self.progress.emit(96, "Dokument wird zusammengesetzt…")
            self.finished.emit(book, assemble(book))
        except LoadError as exc:
            self.failed.emit(str(exc), "")
        except Exception as exc:  # noqa: BLE001 - a broken file must not kill the app
            self.failed.emit(
                "Beim Öffnen ist ein unerwarteter Fehler aufgetreten:\n%s" % exc,
                traceback.format_exc(),
            )

    def _report(self, percent: int, message: str) -> None:
        self.progress.emit(max(0, min(95, percent)), message)


def assemble(book: Book) -> str:
    """Concatenate the chapters into the single document the view displays.

    One document rather than one per chapter is what makes continuous scrolling,
    whole-book search and stable annotation offsets possible at all.
    """

    parts = ['<body>']
    for chapter in book.chapters:
        # The chapter anchor lets the TOC jump to a spine item with no id.
        parts.append('<a name="%s"></a>' % chapter.ident)
        parts.append(chapter.html)
    parts.append("</body>")
    return "".join(parts)


class BookLoader(QObject):
    """Owns the worker thread and re-emits its signals on the GUI thread."""

    progress = Signal(int, str)
    finished = Signal(object, str)
    failed = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: LoadWorker | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(self, path: str) -> None:
        self.cancel()
        self._thread = QThread()
        self._worker = LoadWorker(path)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_finished(self, book, html) -> None:
        self._teardown()
        self.finished.emit(book, html)

    def _on_failed(self, message, detail) -> None:
        self._teardown()
        self.failed.emit(message, detail)

    def _teardown(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None

    def cancel(self) -> None:
        """Abandon a running load; the worker finishes but its result is dropped."""

        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.failed.disconnect()
                self._worker.progress.disconnect()
            except (RuntimeError, TypeError):
                pass
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None
