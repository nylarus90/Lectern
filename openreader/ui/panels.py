"""Side panels: table of contents, bookmarks, annotations and search results."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..formats.base import TocEntry
from ..render import theme as theming


class TocPanel(QTreeWidget):
    """Table of contents; ``targetChosen`` carries an anchor or a page index."""

    targetChosen = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(14)
        self.setAnimated(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextElideMode(Qt.ElideRight)
        self.itemActivated.connect(self._activate)
        self.itemClicked.connect(self._activate)

    def populate(self, entries: list[TocEntry]) -> None:
        self.clear()

        def add(parent, entry: TocEntry) -> None:
            item = QTreeWidgetItem(parent, [entry.title])
            item.setData(0, Qt.UserRole, entry.target)
            item.setToolTip(0, entry.title)
            for child in entry.children:
                add(item, child)

        for entry in entries:
            add(self, entry)
        # Only a very deep TOC benefits from starting collapsed.
        if sum(1 for _ in self._walk()) < 60:
            self.expandAll()

    def _walk(self):
        stack = [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
        while stack:
            item = stack.pop()
            yield item
            stack.extend(item.child(i) for i in range(item.childCount()))

    def _activate(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        target = item.data(0, Qt.UserRole)
        if target is not None:
            self.targetChosen.emit(target)

    def mark_current(self, target) -> None:
        """Select the entry matching ``target`` without emitting a signal."""

        for item in self._walk():
            if item.data(0, Qt.UserRole) == target:
                self.blockSignals(True)
                self.setCurrentItem(item)
                self.blockSignals(False)
                return


class BookmarkPanel(QWidget):
    bookmarkChosen = Signal(int)
    bookmarkRemoved = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemActivated.connect(self._activate)
        self.list.itemClicked.connect(self._activate)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        layout.addWidget(self.list)

        self.empty = QLabel("Noch keine Lesezeichen.\nMit Strg+B setzen.", self)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

    def populate(self, bookmarks) -> None:
        self.list.clear()
        for mark in bookmarks:
            label = mark.label or "Lesezeichen"
            item = QListWidgetItem("%s\n%s" % (label, _when(mark.created)))
            item.setData(Qt.UserRole, mark.position)
            item.setData(Qt.UserRole + 1, mark.ident)
            self.list.addItem(item)
        self.list.setVisible(bool(bookmarks))
        self.empty.setVisible(not bookmarks)

    def _activate(self, item: QListWidgetItem) -> None:
        self.bookmarkChosen.emit(int(item.data(Qt.UserRole)))

    def _menu(self, point) -> None:
        item = self.list.itemAt(point)
        if item is None:
            return
        menu = QMenu(self)
        remove = menu.addAction("Lesezeichen löschen")
        if menu.exec(self.list.mapToGlobal(point)) is remove:
            self.bookmarkRemoved.emit(int(item.data(Qt.UserRole + 1)))


class AnnotationPanel(QWidget):
    highlightChosen = Signal(int)          # character position
    highlightRemoved = Signal(int)         # highlight id
    noteRequested = Signal(int)            # highlight id
    colourChanged = Signal(int, str)       # highlight id, colour key
    exportRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.list = QListWidget(self)
        self.list.setWordWrap(True)
        self.list.itemActivated.connect(self._activate)
        self.list.itemClicked.connect(self._activate)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        layout.addWidget(self.list)

        self.empty = QLabel(
            "Noch keine Markierungen.\n\nText auswählen und Strg+H drücken.", self)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

        self.export_button = QPushButton("Als Markdown exportieren…", self)
        self.export_button.clicked.connect(self.exportRequested)
        layout.addWidget(self.export_button)

    def populate(self, highlights) -> None:
        self.list.clear()
        for mark in highlights:
            excerpt = mark.excerpt.strip().replace("\n", " ")
            if len(excerpt) > 160:
                excerpt = excerpt[:157] + "…"
            text = excerpt
            if mark.note:
                text += "\n📝 " + mark.note.split("\n")[0][:80]
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, mark.start)
            item.setData(Qt.UserRole + 1, mark.ident)
            item.setIcon(_colour_icon(mark.colour))
            item.setToolTip("%s\n\n%s" % (mark.excerpt, mark.note) if mark.note else mark.excerpt)
            self.list.addItem(item)
        self.list.setVisible(bool(highlights))
        self.empty.setVisible(not highlights)
        self.export_button.setEnabled(bool(highlights))

    def _activate(self, item: QListWidgetItem) -> None:
        self.highlightChosen.emit(int(item.data(Qt.UserRole)))

    def _menu(self, point) -> None:
        item = self.list.itemAt(point)
        if item is None:
            return
        ident = int(item.data(Qt.UserRole + 1))
        menu = QMenu(self)
        note = menu.addAction("Notiz bearbeiten…")
        colours = menu.addMenu("Farbe")
        colour_actions = {}
        for key, (label, _hexcolour) in theming.HIGHLIGHT_COLOURS.items():
            action = colours.addAction(_colour_icon(key), label)
            colour_actions[action] = key
        menu.addSeparator()
        remove = menu.addAction("Markierung löschen")

        chosen = menu.exec(self.list.mapToGlobal(point))
        if chosen is note:
            self.noteRequested.emit(ident)
        elif chosen is remove:
            self.highlightRemoved.emit(ident)
        elif chosen in colour_actions:
            self.colourChanged.emit(ident, colour_actions[chosen])


class SearchPanel(QWidget):
    """Search box plus results; works for both text books and PDFs."""

    searchRequested = Signal(str, bool, bool)   # needle, case sensitive, whole words
    resultChosen = Signal(int)                  # index into the result list
    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Im Buch suchen…")
        self.input.setClearButtonEnabled(True)
        self.input.returnPressed.connect(self._search)
        row.addWidget(self.input)

        close = QToolButton(self)
        close.setText("✕")
        close.setToolTip("Suche schließen (Esc)")
        close.clicked.connect(self.closed)
        row.addWidget(close)
        layout.addLayout(row)

        options = QHBoxLayout()
        self.case_box = QCheckBox("Groß/klein", self)
        self.words_box = QCheckBox("Ganzes Wort", self)
        self.case_box.toggled.connect(self._search)
        self.words_box.toggled.connect(self._search)
        options.addWidget(self.case_box)
        options.addWidget(self.words_box)
        options.addStretch(1)
        layout.addLayout(options)

        self.status = QLabel("", self)
        layout.addWidget(self.status)

        self.results = QListWidget(self)
        self.results.setWordWrap(True)
        self.results.itemActivated.connect(self._choose)
        self.results.itemClicked.connect(self._choose)
        layout.addWidget(self.results, 1)

    def focus_input(self) -> None:
        self.input.setFocus()
        self.input.selectAll()

    def _search(self) -> None:
        needle = self.input.text().strip()
        if needle:
            self.searchRequested.emit(needle, self.case_box.isChecked(),
                                      self.words_box.isChecked())
        else:
            self.results.clear()
            self.status.setText("")

    def show_results(self, snippets: list[str], needle: str) -> None:
        self.results.clear()
        for index, snippet in enumerate(snippets):
            item = QListWidgetItem(snippet)
            item.setData(Qt.UserRole, index)
            self.results.addItem(item)
        if not snippets:
            self.status.setText("Keine Treffer für „%s“." % needle)
        else:
            self.status.setText("%d Treffer für „%s“." % (len(snippets), needle))

    def select_result(self, index: int) -> None:
        if 0 <= index < self.results.count():
            self.results.blockSignals(True)
            self.results.setCurrentRow(index)
            self.results.blockSignals(False)

    def _choose(self, item: QListWidgetItem) -> None:
        self.resultChosen.emit(int(item.data(Qt.UserRole)))


def _colour_icon(key: str, size: int = 12) -> QIcon:
    _label, hexcolour = theming.HIGHLIGHT_COLOURS.get(
        key, theming.HIGHLIGHT_COLOURS["yellow"]
    )
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(hexcolour))
    return QIcon(pixmap)


def _when(stamp: float) -> str:
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(stamp))
