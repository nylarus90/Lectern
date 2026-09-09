"""Licence texts, and where they live in each kind of build.

Both the GPL and the LGPL ask for a copy of the licence to accompany the
*binary*, not merely to sit in the repository. Three of the four release files
are a single executable, so "accompany" has to mean inside: the texts travel in
the bundle and Help → Licences shows them. The installer additionally copies
them next to the program, which is where a licence text is looked for.

The LGPL applies because Qt is shipped in combined form. It also asks that the
user be told where the unmodified library comes from, which is what the two
addresses below are for.
"""

from __future__ import annotations

import os
import sys

from .i18n import tr

#: Component, the licence it is used under, and the file holding that licence.
#: The application comes first; everything after it is somebody else's work.
COMPONENTS: tuple[tuple[str, str, str], ...] = (
    ("OpenReader", "GNU General Public License v3.0 or later", "GPL-3.0.txt"),
    ("Qt 6, PySide6, Shiboken6", "GNU Lesser General Public License v3.0",
     "LGPL-3.0.txt"),
)

#: Where the unmodified sources of the shipped libraries can be had. Required
#: by the LGPL, and useful to anyone who wants to rebuild with their own Qt.
SOURCES: tuple[tuple[str, str], ...] = (
    ("Qt 6", "https://download.qt.io/official_releases/qt/"),
    ("PySide6", "https://download.qt.io/official_releases/QtForPython/"),
)

_PACKAGE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PACKAGE)

#: In a source checkout the files have not been collected yet. The GPL is the
#: repository's own LICENSE — kept at the top level because that is where
#: GitHub and every other tool looks for it — and only the LGPL sits under
#: ``licenses/``. Duplicating 35 kB of licence text to make the two layouts
#: identical would be the kind of copy that quietly drifts apart.
_IN_CHECKOUT = {
    "GPL-3.0.txt": os.path.join(_ROOT, "LICENSE"),
    "LGPL-3.0.txt": os.path.join(_ROOT, "licenses", "LGPL-3.0.txt"),
}


def licences_dir() -> str:
    """Where the collected licence texts live, frozen or from source."""

    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "openreader", "resources", "licenses")
    return os.path.join(_PACKAGE, "resources", "licenses")


def licence_text(file_name: str) -> str:
    """Return one licence text.

    A missing file returns a note naming where the text can be had rather than
    an empty window, because an empty licence window looks like the licence
    itself is missing.
    """

    for path in (os.path.join(licences_dir(), file_name),
                 _IN_CHECKOUT.get(file_name, "")):
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    return handle.read()
            except OSError:
                break
    return tr("This build does not carry the licence text. It is available at "
              "https://www.gnu.org/licenses/.")
