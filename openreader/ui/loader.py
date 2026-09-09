"""Background book loading.

Parsing a large EPUB or decompressing a MOBI takes long enough to freeze the
window, so it happens on a worker thread.  The assembled HTML is built here too
— string work, no Qt objects — and only handed to the view at the end, which is
what keeps every ``QTextDocument`` operation on the GUI thread.
"""

from __future__ import annotations

import contextlib
import threading
import traceback
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from ..formats import load as load_book
from ..formats.base import Book, LoadError
from ..i18n import tr


class _CancelledError(Exception):
    """Raised inside the worker to unwind a load the user no longer wants."""


class LoadWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object, str)   # Book, assembled HTML
    failed = Signal(str, str)        # short message, detail
    done = Signal()                  # always emitted, even when cancelled

    def __init__(self, path: str, cancelled: threading.Event) -> None:
        super().__init__()
        self.path = path
        self._cancelled = cancelled

    def run(self) -> None:
        try:
            book = load_book(self.path, self._report)
            self._raise_if_cancelled()
            self.progress.emit(96, tr("Assembling document…"))
            html = assemble(book)
            self._raise_if_cancelled()
            self.finished.emit(book, html)
        except _CancelledError:
            pass                     # the window has moved on; say nothing
        except LoadError as exc:
            self.failed.emit(str(exc), "")
        except Exception as exc:  # noqa: BLE001 - a broken file must not kill the app
            self.failed.emit(
                tr("An unexpected error occurred while opening:\n%s") % exc,
                traceback.format_exc(),
            )
        finally:
            # Tells the thread to leave its event loop.  It must fire on every
            # path, or the thread would linger and the window would wait for a
            # load that is never coming.
            self.done.emit()

    def _raise_if_cancelled(self) -> None:
        if self._cancelled.is_set():
            raise _CancelledError

    def _report(self, percent: int, message: str) -> None:
        # The parsers call this often, which makes it the natural place to
        # notice a cancellation and stop early instead of finishing work whose
        # result will be thrown away.
        self._raise_if_cancelled()
        self.progress.emit(max(0, min(95, percent)), message)


@dataclass
class _Job:
    thread: QThread
    worker: LoadWorker
    cancelled: threading.Event


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
        self._current: _Job | None = None
        #: Jobs that were abandoned but whose thread is still winding down.
        #: Holding the reference here is the whole point: dropping the last
        #: reference to a running QThread destroys the C++ object underneath it
        #: and Qt aborts the process.
        self._retiring: list[_Job] = []

    @property
    def busy(self) -> bool:
        return self._current is not None and self._current.thread.isRunning()

    def start(self, path: str) -> None:
        self.cancel()
        cancelled = threading.Event()
        thread = QThread()
        worker = LoadWorker(path, cancelled)
        worker.moveToThread(thread)
        job = _Job(thread, worker, cancelled)

        thread.started.connect(worker.run)
        worker.progress.connect(self.progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        # The worker asks its own thread to stop; the thread reports back once
        # it really has, and only then is it safe to let go of both objects.
        worker.done.connect(thread.quit)
        thread.finished.connect(lambda job=job: self._reap(job))

        self._current = job
        self._retiring.append(job)
        thread.start()

    def _on_finished(self, book, html) -> None:
        self._current = None
        self.finished.emit(book, html)

    def _on_failed(self, message, detail) -> None:
        self._current = None
        self.failed.emit(message, detail)

    def _reap(self, job: _Job) -> None:
        """Release a job whose thread has actually stopped."""

        if job in self._retiring:
            self._retiring.remove(job)
        job.worker.deleteLater()
        job.thread.deleteLater()

    def cancel(self) -> None:
        """Abandon a running load.

        Never waits on the worker thread.  ``wait()`` in the GUI thread froze
        the window for its full timeout and then, when the worker was still deep
        inside parsing, dropped the reference to a live QThread — which Qt turns
        into an immediate process abort.  Instead the worker is asked to stop at
        its next progress report and the job is left to clean itself up.
        """

        job = self._current
        self._current = None
        if job is None:
            return
        job.cancelled.set()
        for signal in (job.worker.finished, job.worker.failed, job.worker.progress):
            # Already disconnected, or the C++ side is gone: either way there is
            # nothing left to detach.
            with contextlib.suppress(RuntimeError, TypeError):
                signal.disconnect()
        job.thread.quit()

    def shutdown(self, timeout_ms: int = 4000) -> None:
        """Wait for abandoned threads at application exit.

        Blocking is correct here and nowhere else: the window is going away, and
        a thread that outlives the interpreter is far worse than a short pause.
        A job that refuses to stop keeps its reference for the life of the
        process rather than being destroyed while running.
        """

        self.cancel()
        deadline = max(0, timeout_ms)
        for job in list(self._retiring):
            job.cancelled.set()
            job.thread.quit()
            if job.thread.wait(deadline):
                self._retiring.remove(job)
            else:
                _ABANDONED.append(job)
                self._retiring.remove(job)


#: Threads that would not stop in time.  Parking them here deliberately leaks
#: the reference, which is harmless at exit and strictly better than the crash
#: that destroying a running QThread causes.
_ABANDONED: list[_Job] = []
