"""The Help → Licences window.

Deliberately plain: an overview naming what is used under which licence, and
one tab per full text. The addresses are shown as selectable text rather than
as links — the reader opens a browser only when the user clicks a link in a
book and confirms it, and a licence window is no place to make an exception.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..licensing import COMPONENTS, SOURCES, licence_text


class LicencesDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Licences"))
        self.resize(720, 540)

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        tabs.addTab(self._overview(), tr("Overview"))
        for _component, _licence, file_name in COMPONENTS:
            tabs.addTab(self._full_text(licence_text(file_name)),
                        file_name.removesuffix(".txt"))
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _overview(self) -> QWidget:
        lines = [tr("This program is made of the following parts:"), ""]
        for component, licence, _file_name in COMPONENTS:
            lines.append("  %s — %s" % (component, licence))
        lines += ["", tr("The unmodified sources of the libraries are available at:"), ""]
        for component, address in SOURCES:
            lines.append("  %s: %s" % (component, address))
        lines += ["", tr("The Qt libraries are shipped as separate files and may be "
                         "replaced. In the single-file build they are packed into the "
                         "executable; rebuilding from source is the way to substitute "
                         "them there.")]

        label = QLabel("\n".join(lines), self)
        label.setWordWrap(True)
        label.setMargin(14)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def _full_text(self, text: str) -> QWidget:
        view = QPlainTextEdit(text, self)
        view.setReadOnly(True)
        # Licence texts are hard-wrapped at 70-odd columns; a proportional font
        # would ruin the layout they were written for.
        view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        return view
