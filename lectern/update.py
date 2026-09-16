"""Optional, privacy-conscious checks for newer GitHub releases.

Only release metadata is fetched.  Downloads stay in the browser because the
published executables are not code-signed; silently downloading and executing
one would promise more authenticity than a checksum from the same server can
provide.
"""

from __future__ import annotations

import contextlib
import json
import re
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal

from .version import __version__

LATEST_RELEASE_API = "https://api.github.com/repos/nylarus90/Lectern/releases/latest"
RELEASE_PAGE_PREFIX = "https://github.com/nylarus90/Lectern/releases/tag/"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
MAX_RESPONSE_BYTES = 256 * 1024
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    page_url: str


def version_tuple(value: str) -> tuple[int, int, int]:
    """Return a comparable release number, rejecting ambiguous tags."""

    match = _VERSION.fullmatch(value.strip())
    if match is None:
        raise ValueError("unsupported release version")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def fetch_update(current: str = __version__, *, timeout: float = 8.0,
                 opener=urllib.request.urlopen) -> UpdateInfo | None:
    """Fetch GitHub's latest stable release and return it when it is newer."""

    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Lectern/%s" % current,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with opener(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("release response is unexpectedly large")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("release response is not an object")

    tag = payload.get("tag_name")
    page_url = payload.get("html_url")
    if not isinstance(tag, str) or not isinstance(page_url, str):
        raise ValueError("release response is incomplete")
    latest = version_tuple(tag)
    installed = version_tuple(current)
    if latest <= installed:
        return None
    if not page_url.startswith(RELEASE_PAGE_PREFIX):
        raise ValueError("release page is outside the project")
    return UpdateInfo(".".join(str(part) for part in latest), page_url)


class _UpdateWorker(QObject):
    checked = Signal(object)
    failed = Signal(str)
    done = Signal()

    def run(self) -> None:
        try:
            self.checked.emit(fetch_update())
        except Exception as exc:  # noqa: BLE001 - a network failure must stay harmless
            self.failed.emit(str(exc))
        finally:
            self.done.emit()


class UpdateChecker(QObject):
    """Run one release check at a time without blocking the reader window."""

    checked = Signal(object, bool)  # UpdateInfo | None, manual
    failed = Signal(str, bool)      # message, manual

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _UpdateWorker | None = None
        self._manual = False

    @property
    def busy(self) -> bool:
        # Keep the job occupied until ``finished`` has been reaped. Otherwise a
        # second start in that tiny interval can replace the references while
        # the old thread's cleanup is still queued.
        return self._thread is not None

    def start(self, *, manual: bool) -> bool:
        if self.busy:
            return False
        self._manual = manual
        thread = QThread(self)
        worker = _UpdateWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.checked.connect(self._on_checked)
        worker.failed.connect(self._on_failed)
        worker.done.connect(thread.quit)
        thread.finished.connect(self._reap)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def _on_checked(self, info) -> None:
        self.checked.emit(info, self._manual)

    def _on_failed(self, message: str) -> None:
        self.failed.emit(message, self._manual)

    def _reap(self) -> None:
        worker, thread = self._worker, self._thread
        self._worker = None
        self._thread = None
        if worker is not None:
            worker.deleteLater()
        if thread is not None:
            thread.deleteLater()

    def shutdown(self) -> None:
        """Wait briefly for the bounded network request when the app exits."""

        thread = self._thread
        worker = self._worker
        if worker is not None:
            for signal in (worker.checked, worker.failed):
                with contextlib.suppress(RuntimeError, TypeError):
                    signal.disconnect()
        if thread is not None and thread.isRunning():
            thread.quit()
            if not thread.wait(9000):
                # DNS resolution can outlive a socket timeout on some systems.
                # Keep the objects alive rather than letting Qt destroy a
                # running QThread while the process is winding down.
                thread.setParent(None)
                _ABANDONED.append((thread, worker))
                self._thread = None
                self._worker = None


_ABANDONED: list[tuple[QThread, _UpdateWorker | None]] = []
