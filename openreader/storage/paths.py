"""Per-platform locations for the database and the settings file.

Deliberately hand-rolled rather than taken from ``QStandardPaths`` so that the
storage layer can be used and tested without a running ``QApplication``.
"""

from __future__ import annotations

import contextlib
import os
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
    # directory is owned by its user alone.  ``makedirs`` applies the mode only
    # when it creates the directory, hence the explicit chmod for one that
    # already exists — and both are skipped on Windows, where POSIX bits mean
    # nothing and the ACL inherited from the profile already restricts access.
    os.makedirs(base, mode=0o700, exist_ok=True)
    if sys.platform != "win32":
        with contextlib.suppress(OSError):
            os.chmod(base, 0o700)
    return base


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
