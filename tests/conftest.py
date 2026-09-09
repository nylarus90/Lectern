"""Shared fixtures, and the one thing that keeps Qt from crashing on exit.

Every test passed on Linux and macOS and the process still died with a
segmentation fault afterwards (exit code 139). The cause was ownership, not any
test: the ``QApplication`` was built inside a *module*-scoped fixture, so the
last Python reference to it disappeared when that module finished. PySide6 then
destroyed the C++ application object while widgets from earlier tests were still
alive, and finalising those at interpreter shutdown reached into freed memory.

Two rules follow, and both are enforced here:

1. The application is created once per session and parked in a module-level
   variable that is never cleared, so it outlives everything else.
2. Widgets are deleted while the application is still running — ``deleteLater``
   followed by a turn of the event loop — instead of being left to Python's
   garbage collector at shutdown.
"""

from __future__ import annotations

import gc
import os

import pytest

#: Deliberately never released; see the module docstring. A fixture return
#: value would be dropped at teardown, which is exactly what caused the crash.
_APPLICATION = None


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    """The one ``QApplication`` for the whole test session."""

    global _APPLICATION

    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    os.environ.setdefault(
        "OPENREADER_DATA_DIR", str(tmp_path_factory.mktemp("openreader-data"))
    )
    if _APPLICATION is None:
        _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


@pytest.fixture(scope="session", autouse=True)
def _drain_qt_objects(request):
    """Let Qt finish deleting everything before the interpreter goes away.

    Runs after the last test but while the application still exists, so
    ``deleteLater`` calls are actually carried out rather than being finalised
    from under a destroyed application.
    """

    yield
    if _APPLICATION is None:
        return
    for _ in range(3):
        gc.collect()
        _APPLICATION.sendPostedEvents(None, 0)   # includes DeferredDelete
        _APPLICATION.processEvents()


def spin(app, milliseconds: int = 200) -> None:
    """Run the event loop for a while, so Qt can lay out and repaint."""

    from PySide6.QtCore import QElapsedTimer

    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < milliseconds:
        app.processEvents()


def dispose(app, *objects) -> None:
    """Destroy Qt objects now, while the application is still alive."""

    for obj in objects:
        if obj is None:
            continue
        close = getattr(obj, "close", None)
        if close is not None:
            close()
        obj.deleteLater()
    app.sendPostedEvents(None, 0)
    app.processEvents()
