"""Per-platform locations for the database and the settings file.

Deliberately hand-rolled rather than taken from ``QStandardPaths`` so that the
storage layer can be used and tested without a running ``QApplication``.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys

from ..version import APP_ID, LEGACY_APP_ID, LEGACY_ENV


def _platform_dir(name: str) -> str:
    """The conventional per-user data location for ``name`` on this platform."""

    if sys.platform == "win32":
        return os.path.join(
            os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming"), name
        )
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/%s" % name)
    return os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), name
    )


def adopt_legacy(current: str, legacy: str) -> str:
    """Return ``current``, taking over the legacy directory if only that exists.

    Up to 1.1.1 the program had another name, and reading positions, bookmarks
    and notes from that time live in a directory named after it. The directory
    is renamed rather than copied: one move, nothing to reconcile, no second
    copy of someone's reading history left lying around.

    If the move fails — the old version still running with its database open,
    a folder on a read-only stick — the legacy directory is used as it is and
    the move is simply tried again on the next start. A failed migration must
    never cost anyone their notes.
    """

    if os.path.exists(current) or not os.path.isdir(legacy):
        return current
    try:
        os.rename(legacy, current)
    except OSError:
        return legacy
    return current


def portable_dir(base: str) -> str:
    """The data directory beside a portable executable living in ``base``."""

    return adopt_legacy(os.path.join(base, "%s-data" % APP_ID),
                        os.path.join(base, "%s-data" % LEGACY_APP_ID))


def data_dir() -> str:
    """Directory for the reading database, created on first use.

    Honours ``LECTERN_DATA_DIR``, which is what makes the portable build
    portable: point it next to the executable and nothing is written to the
    user profile at all. The legacy variable is still read, so a script or a
    shortcut written for an older version keeps working.
    """

    # ``or`` short-circuits: with an override, no legacy directory is touched.
    base = (os.environ.get("LECTERN_DATA_DIR") or os.environ.get(LEGACY_ENV)
            or adopt_legacy(_platform_dir(APP_ID), _platform_dir(LEGACY_APP_ID)))
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

    Measured on Windows 11: ``%APPDATA%\\lectern`` is created with SYSTEM,
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
