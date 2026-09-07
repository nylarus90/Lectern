"""The start screen: recently read books, or an invitation to open one."""

from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..render import theme as theming
from ..version import APP_NAME


class WelcomeView(QWidget):
    openRequested = Signal(str)      # path
    browseRequested = Signal()
    forgetRequested = Signal(str)    # book id

    def __init__(self, library, parent=None) -> None:
        super().__init__(parent)
        self.library = library

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(14)

        self.heading = QLabel(APP_NAME, self)
        font = self.heading.font()
        font.setPointSize(max(20, font.pointSize() + 12))
        font.setBold(True)
        self.heading.setFont(font)
        layout.addWidget(self.heading)

        self.subtitle = QLabel(
            "EPUB · Kindle · FB2 · PDF · Comics · Text · Markdown · HTML · RTF", self)
        layout.addWidget(self.subtitle)
        layout.addSpacing(12)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Buch öffnen…", self)
        self.open_button.clicked.connect(self.browseRequested)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addSpacing(10)

        self.recent_label = QLabel("Zuletzt gelesen", self)
        recent_font = self.recent_label.font()
        recent_font.setBold(True)
        self.recent_label.setFont(recent_font)
        layout.addWidget(self.recent_label)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setAlternatingRowColors(False)
        self.list.itemActivated.connect(self._open)
        self.list.itemClicked.connect(self._open)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        layout.addWidget(self.list, 1)

        self.hint = QLabel(
            "Noch nichts gelesen. Öffne ein Buch oder zieh eine Datei in dieses Fenster.",
            self)
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        entries = self.library.recent(20)
        for entry in entries:
            missing = not os.path.exists(entry.path)
            title = entry.title or os.path.basename(entry.path)
            detail = " · ".join(part for part in (
                entry.authors,
                "%d %%" % entry.percent if entry.percent else "",
                _ago(entry.last_opened),
                "Datei fehlt" if missing else "",
            ) if part)
            item = QListWidgetItem("%s\n%s" % (title, detail))
            item.setData(Qt.UserRole, entry.path)
            item.setData(Qt.UserRole + 1, entry.ident)
            item.setToolTip(entry.path)
            if missing:
                item.setForeground(QColor("#a04040"))
            self.list.addItem(item)

        self.list.setVisible(bool(entries))
        self.recent_label.setVisible(bool(entries))
        self.hint.setVisible(not entries)

    def _open(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.UserRole))
        if os.path.exists(path):
            self.openRequested.emit(path)
        else:
            item.setForeground(QColor("#a04040"))

    def _menu(self, point) -> None:
        item = self.list.itemAt(point)
        if item is None:
            return
        menu = QMenu(self)
        open_action = menu.addAction("Öffnen")
        folder_action = menu.addAction("Ordner anzeigen")
        menu.addSeparator()
        forget_action = menu.addAction("Aus der Liste entfernen")

        chosen = menu.exec(self.list.mapToGlobal(point))
        path = str(item.data(Qt.UserRole))
        if chosen is open_action:
            self._open(item)
        elif chosen is folder_action:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))
        elif chosen is forget_action:
            self.forgetRequested.emit(str(item.data(Qt.UserRole + 1)))

    def apply_theme(self, key: str) -> None:
        active = theming.theme(key)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(active.background))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(active.text))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.subtitle.setStyleSheet("color: %s;" % active.muted)
        self.hint.setStyleSheet("color: %s;" % active.muted)
        self.heading.setStyleSheet("color: %s;" % active.accent)


def _ago(stamp: float) -> str:
    seconds = max(0, time.time() - stamp)
    if seconds < 3600:
        return "vor %d Min." % max(1, seconds // 60)
    if seconds < 86400:
        return "vor %d Std." % (seconds // 3600)
    if seconds < 86400 * 30:
        return "vor %d Tagen" % (seconds // 86400)
    return time.strftime("%d.%m.%Y", time.localtime(stamp))
