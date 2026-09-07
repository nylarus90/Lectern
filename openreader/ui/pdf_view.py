"""PDF viewer built on Qt's own PDF engine.

``QPdfView`` handles rendering, scrolling and zoom; this wrapper adds the
outline, page navigation and text search that the reader UI expects from every
view, so the main window can treat PDF like any other book.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QPointF, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtPdf import QPdfBookmarkModel, QPdfDocument, QPdfSearchModel
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QWidget

from ..formats.base import Book, LoadError, TocEntry
from ..render import theme as theming


class PdfView(QPdfView):
    """A ``QPdfView`` that speaks the same language as the reflowable view."""

    positionChanged = Signal(int, int)   # current page (1-based), page count
    outlineReady = Signal(list)          # list[TocEntry]

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._document = QPdfDocument(self)
        self._bookmarks = QPdfBookmarkModel(self)
        self._bookmarks.setDocument(self._document)
        self._search = QPdfSearchModel(self)
        self._search.setDocument(self._document)

        self.setDocument(self._document)
        self.setSearchModel(self._search)
        self.setPageMode(QPdfView.PageMode.MultiPage)
        self.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.setPageSpacing(10)
        self.pageNavigator().currentPageChanged.connect(self._emit_position)

    # -- document ---------------------------------------------------------
    def open_file(self, path: str, password: str = "") -> None:
        if password:
            self._document.setPassword(password)
        error = self._document.load(path)
        if error == QPdfDocument.Error.IncorrectPassword:
            raise LoadError("Das PDF ist passwortgeschützt.")
        if error != QPdfDocument.Error.None_:
            raise LoadError("Das PDF konnte nicht geöffnet werden (%s)." % error.name)
        self.outlineReady.emit(self.outline())
        self._emit_position()

    def fill_metadata(self, book: Book) -> None:
        """Complete the book's metadata from the opened document."""

        field = QPdfDocument.MetaDataField
        title = str(self._document.metaData(field.Title) or "").strip()
        author = str(self._document.metaData(field.Author) or "").strip()
        subject = str(self._document.metaData(field.Subject) or "").strip()
        if title:
            book.meta.title = title
        if author and not book.meta.authors:
            book.meta.authors = [author]
        if subject and not book.meta.description:
            book.meta.description = subject

    @property
    def page_count(self) -> int:
        return max(1, self._document.pageCount())

    @property
    def current_page(self) -> int:
        return self.pageNavigator().currentPage() + 1

    def _emit_position(self, *_args) -> None:
        self.positionChanged.emit(self.current_page, self.page_count)

    def outline(self) -> list[TocEntry]:
        """Convert Qt's bookmark model into our own TOC structure.

        Documents without an outline still get one entry per page, because an
        empty sidebar is worse than a plain page list.
        """

        role = QPdfBookmarkModel.Role

        def walk(parent: QModelIndex) -> list[TocEntry]:
            entries: list[TocEntry] = []
            for row in range(self._bookmarks.rowCount(parent)):
                index = self._bookmarks.index(row, 0, parent)
                title = str(self._bookmarks.data(index, role.Title.value) or "").strip()
                page = self._bookmarks.data(index, role.Page.value)
                if title:
                    entries.append(TocEntry(title, int(page or 0), walk(index)))
            return entries

        entries = walk(QModelIndex())
        if entries:
            return entries
        return [TocEntry("Seite %d" % (i + 1), i) for i in range(min(self.page_count, 2000))]

    # -- navigation -------------------------------------------------------
    def go_to_page(self, page: int) -> None:
        """Jump to a zero-based page index."""

        self.pageNavigator().jump(max(0, min(page, self.page_count - 1)), QPointF(0, 0))

    def next_page(self) -> None:
        bar = self.verticalScrollBar()
        step = max(40, self.viewport().height() - 18)
        if bar.value() < bar.maximum():
            bar.setValue(min(bar.maximum(), bar.value() + step))
        else:
            self.go_to_page(self.current_page)

    def previous_page(self) -> None:
        bar = self.verticalScrollBar()
        step = max(40, self.viewport().height() - 18)
        if bar.value() > bar.minimum():
            bar.setValue(max(bar.minimum(), bar.value() - step))
        else:
            self.go_to_page(self.current_page - 2)

    def go_to_start(self) -> None:
        self.go_to_page(0)

    def go_to_end(self) -> None:
        self.go_to_page(self.page_count - 1)

    # -- zoom -------------------------------------------------------------
    ZOOM_MODES = {
        "width": QPdfView.ZoomMode.FitToWidth,
        "page": QPdfView.ZoomMode.FitInView,
        "custom": QPdfView.ZoomMode.Custom,
    }

    def set_zoom_mode(self, mode: str) -> None:
        self.setZoomMode(self.ZOOM_MODES.get(mode, QPdfView.ZoomMode.FitToWidth))
        self.settings["pdf_zoom_mode"] = mode

    def zoom_by(self, factor: float) -> None:
        self.setZoomMode(QPdfView.ZoomMode.Custom)
        self.setZoomFactor(max(0.15, min(8.0, self.zoomFactor() * factor)))
        self.settings["pdf_zoom_mode"] = "custom"
        self.settings["pdf_zoom"] = self.zoomFactor()

    # -- search -----------------------------------------------------------
    def search(self, needle: str) -> int:
        self._search.setSearchString(needle)
        return self._search.rowCount()

    def match_count(self) -> int:
        return self._search.rowCount()

    def show_match(self, index: int) -> None:
        """Highlight and scroll to one search result."""

        if 0 <= index < self._search.rowCount():
            self.setCurrentSearchResultIndex(index)
            link = self._search.resultAtIndex(index)
            if link.isValid():
                self.pageNavigator().jump(link.page(), link.location())

    def match_context(self, index: int) -> tuple[int, str]:
        """Return ``(page, surrounding text)`` for one search result."""

        if not 0 <= index < self._search.rowCount():
            return (0, "")
        link = self._search.resultAtIndex(index)
        text = ("%s %s" % (link.contextBefore(), link.contextAfter())).strip()
        return link.page(), text

    def clear_search(self) -> None:
        self._search.setSearchString("")
        self.setCurrentSearchResultIndex(-1)

    # -- appearance -------------------------------------------------------
    def apply_theme(self, key: str) -> None:
        """Tint the surround; the page itself stays as its author made it."""

        active = theming.theme(key)
        palette = self.palette()
        for role in (QPalette.ColorRole.Dark, QPalette.ColorRole.Base,
                     QPalette.ColorRole.Window):
            palette.setColor(role, QColor(active.surface))
        self.setPalette(palette)
        self.setBackgroundRole(QPalette.ColorRole.Dark)
        self.setAutoFillBackground(True)
