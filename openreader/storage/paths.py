"""Per-platform locations for the database and the settings file.

Deliberately hand-rolled rather than taken from ``QStandardPaths`` so that the
storage layer can be used and tested without a running ``QApplication``.
"""

from __future__ import annotations

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
    os.makedirs(base, exist_ok=True)
    return base


def database_path() -> str:
    return os.path.join(data_dir(), "library.sqlite3")


def settings_path() -> str:
    return os.path.join(data_dir(), "settings.json")
