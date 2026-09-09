"""Per-platform locations for the database and the settings file.

Deliberately hand-rolled rather than taken from ``QStandardPaths`` so that the
storage layer can be used and tested without a running ``QApplication``.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys

from ..version import APP_ID


def data_dir() -> str:
    """Directory for the reading database, created on first use.

    Honours ``OPENREADER_DATA_DIR``, which is what makes the portable build
    portable: point it next to the executable and nothing is written to the
    user profile at all.
    """

    override = os.environ.get("OPENREADER_DATA_DIR")
    if override:
        base = override
    elif sys.platform == "win32":
        base = os.path.join(
            os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming"), APP_ID
        )
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/%s" % APP_ID)
    else:
        base = os.path.join(
            os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), APP_ID
        )
    # A reading history is a precise profile of someone's interests, so the
    # directory belongs to its user alone.  ``makedirs`` applies the mode only
    # when it creates the directory, hence the explicit chmod for one that
    # already exists.
    os.makedirs(base, mode=0o700, exist_ok=True)
    if sys.platform == "win32":
        _restrict_windows_directory(base)
    else:
        with contextlib.suppress(OSError):
            os.chmod(base, 0o700)
    return base


#: Written once a directory's permissions have been tightened, so the check
#: costs a ``stat`` on every later start instead of launching a process.
_SECURED_MARKER = ".permissions-set"


def _restrict_windows_directory(path: str) -> None:
    """Restrict a data directory to its owner on Windows.

    Measured on Windows 11: ``%APPDATA%\\openreader`` is created with SYSTEM,
    Administrators and the owner and no Users group, so the default location is
    already private.  A directory chosen with ``--portable`` or ``--data-dir``
    is not — it inherits wherever the user put it, and a plain ``mkdir`` inside
    a shared folder was measured inheriting ``Users: FullControl``.

    CPython 3.13 and newer translate ``mode=0o700`` into exactly the right
    security descriptor, which covers the shipped build.  On 3.10 to 3.12 the
    mode is ignored on Windows, so ``icacls`` has to do it — which is the only
    reason this exists.  Running from source on an older interpreter is a
    supported configuration, and a reading history is not something to leave
    readable by accident.

    Failure is expected and ignored on a file system that has no permissions to
    begin with: a FAT-formatted USB stick is a perfectly normal home for a
    portable library, and there is simply nothing to enforce there.
    """

    marker = os.path.join(path, _SECURED_MARKER)
    if os.path.exists(marker):
        return
    account = os.environ.get("USERNAME")
    if account:
        try:
            subprocess.run(
                ["icacls", path, "/inheritance:r",
                 "/grant:r", "%s:(OI)(CI)F" % account,
                 "/grant:r", "*S-1-5-18:(OI)(CI)F"],      # SYSTEM, by SID
                capture_output=True, timeout=20, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return
    with contextlib.suppress(OSError), open(marker, "w", encoding="utf-8") as handle:
        handle.write("Permissions have been set. Do not delete this file.\n")


def secure_file(path: str) -> None:
    """Restrict an existing data file to its owner.

    Called after creating the database and the settings file; failures are
    ignored because a file system without POSIX permissions (a FAT-formatted
    USB stick in portable mode) is a legitimate place to keep a library.
    """

    if sys.platform == "win32":
        return
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def database_path() -> str:
    return os.path.join(data_dir(), "library.sqlite3")


def settings_path() -> str:
    return os.path.join(data_dir(), "settings.json")
