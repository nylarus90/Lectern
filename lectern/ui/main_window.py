"""The application window: menus, docks, view switching and reading state."""

from __future__ import annotations

import bisect
import os

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QTabWidget,
    QToolBar,
)

from .. import formats
from ..formats.base import Book, BookKind, LoadError, file_id
from ..i18n import tr
from ..render import theme as theming
from ..storage.db import Library
from ..storage.settings import DEFAULTS, Settings
from ..version import APP_NAME, __version__
from .comic_view import ComicView
from .licences_dialog import LicencesDialog
from .loader import BookLoader
from .panels import AnnotationPanel, BookmarkPanel, SearchPanel, TocPanel
from .pdf_view import PdfView
from .reader_view import ReaderView
from .welcome import WelcomeView

#: Reading position is written at most this often, to spare the disk.
SAVE_INTERVAL_MS = 4000


class MainWindow(QMainWindow):
    bookOpened = Signal(object)

    def __init__(self, settings: Settings, library: Library) -> None:
        super().__init__()
        self.settings = settings
        self.library = library
        self.book: Book | None = None
        self.book_id = ""
        self._search_matches: list[tuple[int, int]] = []
        self._search_index = -1
        self._restoring_position = 0
        #: (character position, TOC target) pairs, sorted, so the outline can
        #: follow along while reading.  Empty for page-based views.
        self._toc_positions: list[tuple[int, object]] = []
        #: Guards the storage-failure dialog; the save timer fires every
        #: four seconds and must not produce a dialog each time.
        self._storage_warned = False

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(560, 420)
        self.setAcceptDrops(True)

        self._build_views()
        self._build_docks()
        self._build_actions()
        self._build_statusbar()

        self.loader = BookLoader(self)
        self.loader.progress.connect(self._on_load_progress)
        self.loader.finished.connect(self._on_load_finished)
        self.loader.failed.connect(self._on_load_failed)

        self._save_timer = QTimer(self)
        self._save_timer.setInterval(SAVE_INTERVAL_MS)
        self._save_timer.timeout.connect(self._persist_position)

        self.apply_theme(self.settings["theme"])
        self._restore_window_state()
        self._update_actions()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_views(self) -> None:
        self.stack = QStackedWidget(self)
        self.welcome = WelcomeView(self.library, self)
        self.welcome.openRequested.connect(self.open_path)
        self.welcome.browseRequested.connect(self.open_dialog)
        self.welcome.forgetRequested.connect(self._forget_book)

        self.reader = ReaderView(self.settings, self)
        self.reader.positionChanged.connect(self._on_text_position)
        self.reader.externalLinkActivated.connect(self._confirm_external_link)
        self.reader.selectionAvailable.connect(lambda _on: self._update_actions())

        self.comic = ComicView(self.settings, self)
        self.comic.positionChanged.connect(self._on_page_position)

        self.pdf = PdfView(self.settings, self)
        self.pdf.positionChanged.connect(self._on_page_position)
        self.pdf.outlineReady.connect(self.toc_panel_populate)

        for widget in (self.welcome, self.reader, self.comic, self.pdf):
            self.stack.addWidget(widget)
        self.setCentralWidget(self.stack)
        self.stack.setCurrentWidget(self.welcome)

    def _build_docks(self) -> None:
        self.sidebar = QDockWidget("Navigation", self)
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.tabs = QTabWidget(self.sidebar)
        self.tabs.setDocumentMode(True)

        self.toc_panel = TocPanel(self.tabs)
        self.toc_panel.targetChosen.connect(self.go_to_target)

        self.bookmark_panel = BookmarkPanel(self.tabs)
        self.bookmark_panel.bookmarkChosen.connect(self._go_to_position)
        self.bookmark_panel.bookmarkRemoved.connect(self._remove_bookmark)

        self.annotation_panel = AnnotationPanel(self.tabs)
        self.annotation_panel.highlightChosen.connect(self._go_to_position)
        self.annotation_panel.highlightRemoved.connect(self._remove_highlight)
        self.annotation_panel.noteRequested.connect(self._edit_note)
        self.annotation_panel.colourChanged.connect(self._recolour_highlight)
        self.annotation_panel.exportRequested.connect(self.export_annotations)

        self.search_panel = SearchPanel(self.tabs)
        self.search_panel.searchRequested.connect(self.run_search)
        self.search_panel.resultChosen.connect(self.show_search_result)
        self.search_panel.closed.connect(lambda: self.tabs.setCurrentIndex(0))

        self.tabs.addTab(self.toc_panel, tr("Contents"))
        self.tabs.addTab(self.bookmark_panel, tr("Bookmarks"))
        self.tabs.addTab(self.annotation_panel, tr("Notes"))
        self.tabs.addTab(self.search_panel, tr("Search"))
        self.sidebar.setWidget(self.tabs)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar)
        self.sidebar.setVisible(bool(self.settings["sidebar_visible"]))

    def _build_actions(self) -> None:
        menubar = self.menuBar()

        # -- file --------------------------------------------------------
        file_menu = menubar.addMenu(tr("&File"))
        self.action_open = _action(self, tr("Open…"), QKeySequence.Open, self.open_dialog)
        file_menu.addAction(self.action_open)
        self.recent_menu = QMenu(tr("Recently opened"), self)
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        file_menu.addMenu(self.recent_menu)
        file_menu.addSeparator()
        self.action_close_book = _action(self, tr("Close book"), QKeySequence.Close,
                                         self.close_book)
        file_menu.addAction(self.action_close_book)
        self.action_export = _action(self, tr("Export annotations…"), None,
                                     self.export_annotations)
        file_menu.addAction(self.action_export)
        file_menu.addSeparator()
        file_menu.addAction(_action(self, tr("Quit"), QKeySequence.Quit, self.close))

        # -- navigation ---------------------------------------------------
        nav_menu = menubar.addMenu(tr("&Navigation"))
        self.action_next = _action(self, tr("Next page"), QKeySequence(Qt.Key_PageDown),
                                   self.next_page)
        self.action_previous = _action(self, tr("Previous page"), QKeySequence(Qt.Key_PageUp),
                                       self.previous_page)
        nav_menu.addAction(self.action_next)
        nav_menu.addAction(self.action_previous)
        nav_menu.addSeparator()
        nav_menu.addAction(_action(self, tr("Beginning"), QKeySequence(Qt.CTRL | Qt.Key_Home),
                                   self.go_to_start))
        nav_menu.addAction(_action(self, tr("End"), QKeySequence(Qt.CTRL | Qt.Key_End),
                                   self.go_to_end))
        nav_menu.addSeparator()
        self.action_goto = _action(self, tr("Go to…"), QKeySequence(Qt.CTRL | Qt.Key_G),
                                   self.go_to_dialog)
        nav_menu.addAction(self.action_goto)
        self.action_search = _action(self, tr("Find…"), QKeySequence.Find, self.focus_search)
        nav_menu.addAction(self.action_search)
        self.action_next_match = _action(self, tr("Next match"),
                                         QKeySequence.FindNext, self.next_match)
        self.action_previous_match = _action(self, tr("Previous match"),
                                             QKeySequence.FindPrevious, self.previous_match)
        nav_menu.addAction(self.action_next_match)
        nav_menu.addAction(self.action_previous_match)

        # -- annotations ---------------------------------------------------
        annotate_menu = menubar.addMenu(tr("&Annotations"))
        self.action_bookmark = _action(self, tr("Add bookmark"),
                                       QKeySequence(Qt.CTRL | Qt.Key_B), self.add_bookmark)
        annotate_menu.addAction(self.action_bookmark)
        self.action_highlight = _action(self, tr("Highlight selection"),
                                        QKeySequence(Qt.CTRL | Qt.Key_H), self.add_highlight)
        annotate_menu.addAction(self.action_highlight)
        colour_menu = annotate_menu.addMenu(tr("Highlight in colour"))
        for key, (label, _hexcolour) in theming.HIGHLIGHT_COLOURS.items():
            colour_menu.addAction(
                _action(self, label, None, lambda _checked=False, k=key: self.add_highlight(k))
            )
        annotate_menu.addSeparator()
        self.action_copy = _action(self, tr("Copy selection"), QKeySequence.Copy,
                                   lambda: self.reader.copy_selection())
        annotate_menu.addAction(self.action_copy)

        # -- view ----------------------------------------------------------
        view_menu = menubar.addMenu(tr("&View"))
        theme_menu = view_menu.addMenu(tr("Colour scheme"))
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for key in theming.THEMES:
            action = _action(self, theming.THEMES[key].label, None,
                             lambda _checked=False, k=key: self.apply_theme(k))
            action.setCheckable(True)
            action.setChecked(key == self.settings["theme"])
            action.setData(key)
            self._theme_group.addAction(action)
            theme_menu.addAction(action)

        view_menu.addSeparator()
        view_menu.addAction(_action(self, tr("Zoom in"), QKeySequence.ZoomIn,
                                    lambda: self.zoom_in()))
        view_menu.addAction(_action(self, tr("Zoom out"), QKeySequence.ZoomOut,
                                    lambda: self.zoom_out()))
        view_menu.addAction(_action(self, tr("Reset zoom"),
                                    QKeySequence(Qt.CTRL | Qt.Key_0), self.zoom_reset))
        view_menu.addSeparator()

        self.action_sidebar = _action(self, tr("Sidebar"), QKeySequence(Qt.Key_F9),
                                      self.toggle_sidebar)
        self.action_sidebar.setCheckable(True)
        self.action_sidebar.setChecked(self.sidebar.isVisible())
        view_menu.addAction(self.action_sidebar)

        self.action_fullscreen = _action(self, tr("Full screen"), QKeySequence(Qt.Key_F11),
                                         self.toggle_fullscreen)
        self.action_fullscreen.setCheckable(True)
        view_menu.addAction(self.action_fullscreen)
        view_menu.addSeparator()
        view_menu.addAction(_action(self, tr("Settings…"),
                                    QKeySequence(Qt.CTRL | Qt.Key_Comma), self.open_settings))

        # -- help ----------------------------------------------------------
        help_menu = menubar.addMenu(tr("&Help"))
        help_menu.addAction(_action(self, tr("Keyboard shortcuts"), QKeySequence.HelpContents,
                                    self.show_shortcuts))
        help_menu.addAction(_action(self, tr("Licences…"), None, self.show_licences))
        help_menu.addAction(_action(self, tr("About %s") % APP_NAME, None, self.show_about))

        # -- toolbar --------------------------------------------------------
        toolbar = QToolBar("Werkzeugleiste", self)
        toolbar.setObjectName("toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.action_open)
        toolbar.addAction(self.action_sidebar)
        toolbar.addSeparator()
        toolbar.addAction(self.action_previous)
        toolbar.addAction(self.action_next)
        toolbar.addSeparator()
        toolbar.addAction(self.action_bookmark)
        toolbar.addAction(self.action_highlight)
        toolbar.addAction(self.action_search)
        self.addToolBar(toolbar)
        self.toolbar = toolbar

        # Keys that must work even when the menu bar is hidden in fullscreen.
        for action in (self.action_next, self.action_previous):
            action.setShortcutContext(Qt.ApplicationShortcut)
        self._extra_shortcuts()

    def _extra_shortcuts(self) -> None:
        """Reading keys that have no place in a menu."""

        for key, slot in (
            (Qt.Key_Space, self.next_page),
            (Qt.Key_Backspace, self.previous_page),
            (Qt.Key_Right, self.next_page),
            (Qt.Key_Left, self.previous_page),
            (Qt.Key_Escape, self._on_escape),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.setShortcutContext(Qt.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)

    def _build_statusbar(self) -> None:
        bar = self.statusBar()
        self.status_title = QLabel("", self)
        self.status_position = QLabel("", self)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximumWidth(180)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        bar.addWidget(self.status_title, 1)
        bar.addPermanentWidget(self.progress_bar)
        bar.addPermanentWidget(self.status_position)

    # ------------------------------------------------------------------
    # Opening books
    # ------------------------------------------------------------------
    def open_dialog(self) -> None:
        start = os.path.dirname(self.book.path) if self.book else ""
        path, _chosen = QFileDialog.getOpenFileName(
            self, tr("Open e-book"), start, formats.dialog_filter()
        )
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        if self.loader.busy:
            self.loader.cancel()
        self._persist_position()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_title.setText(tr("Opening %s…") % os.path.basename(path))
        self.loader.start(path)

    def _on_load_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        if message:
            self.status_title.setText(message)

    def _on_load_finished(self, book: Book, html: str) -> None:
        self.progress_bar.setVisible(False)
        previous_id = self.book_id
        self.book = book
        try:
            self.book_id = file_id(book.path)
        except OSError:
            self.book_id = book.path

        self.library.remember_book(
            self.book_id, book.path, book.display_title,
            book.meta.author_line, book.format_key,
        )
        state = self.library.state(self.book_id)

        if book.kind is BookKind.PDF:
            shown = self._show_pdf(book, state)
        elif book.kind is BookKind.COMIC:
            shown = self._show_comic(book, state)
        else:
            shown = self._show_text(book, html, state)

        if not shown:
            # The view refused the file after we had already recorded it.  Undo
            # that, or the application would sit there claiming a book is open.
            self.library.forget_book(self.book_id)
            self.book = None
            self.book_id = previous_id
            self._update_actions()
            return

        self.setWindowTitle("%s — %s" % (book.display_title, APP_NAME))
        self._show_warnings(book)
        self._save_timer.start()
        self._update_actions()
        self.bookOpened.emit(book)

    def _show_text(self, book: Book, html: str, state) -> bool:
        self.reader.set_book(book, html)
        self.reader.set_highlights(state.highlights)
        self.stack.setCurrentWidget(self.reader)
        self.toc_panel.populate(book.toc)
        self.bookmark_panel.populate(state.bookmarks)
        self.annotation_panel.populate(state.highlights)
        # Restoring has to wait for Qt to lay the document out, otherwise the
        # cursor rectangle we scroll to is still empty.
        self._restoring_position = state.position
        QTimer.singleShot(0, self._restore_position)
        self._index_toc_positions(book)
        self.reader.setFocus()
        return True

    def _show_pdf(self, book: Book, state) -> bool:
        if not self._open_pdf_with_password(book.path):
            return False
        self.pdf.fill_metadata(book)
        self.pdf.set_zoom_mode(self.settings["pdf_zoom_mode"])
        if self.settings["pdf_zoom_mode"] == "custom":
            # The factor was already being stored; it just was never read back.
            self.pdf.setZoomFactor(float(self.settings["pdf_zoom"]))
        self.stack.setCurrentWidget(self.pdf)
        self.bookmark_panel.populate(state.bookmarks)
        self.annotation_panel.populate([])
        if state.position:
            self.pdf.go_to_page(state.position)
        self.pdf.setFocus()
        return True

    def _open_pdf_with_password(self, path: str) -> bool:
        """Open a PDF, asking for its password if it turns out to need one.

        ``PdfView.open_file`` has always accepted a password, but nothing ever
        supplied one, so an encrypted PDF was simply unopenable while the code
        looked as though it handled the case.
        """

        password = ""
        for attempt in range(4):
            try:
                self.pdf.open_file(path, password)
                return True
            except LoadError as exc:
                if not self.pdf.needs_password():
                    self._on_load_failed(str(exc), "")
                    return False
            prompt = (tr("This PDF is password protected.\nPassword:") if attempt == 0
                      else tr("Wrong password. Please try again:"))
            password, accepted = QInputDialog.getText(
                self, tr("Password required"), prompt, QLineEdit.Password
            )
            if not accepted:
                self.progress_bar.setVisible(False)
                self.status_title.setText("")
                return False
        self._on_load_failed(tr("The PDF could not be opened with this password."), "")
        return False

    def _show_comic(self, book: Book, state) -> bool:
        self.comic.set_book(book)
        self.stack.setCurrentWidget(self.comic)
        self.toc_panel.populate(book.toc)
        self.bookmark_panel.populate(state.bookmarks)
        self.annotation_panel.populate([])
        if state.position:
            self.comic.go_to_page(state.position)
        self.comic.setFocus()
        return True

    def _index_toc_positions(self, book: Book) -> None:
        """Work out where each outline entry sits in the assembled document.

        Anchors inside a chapter are frequently dropped by Qt, so an entry that
        cannot be located exactly falls back to the start of its chapter — which
        for the usual one-entry-per-chapter outline is the same place.
        """

        anchors = self.reader.anchor_positions()
        found: list[tuple[int, object]] = []
        for _level, entry in _walk_toc(book.toc):
            target = entry.target
            if not isinstance(target, str):
                continue
            name = target.lstrip("#")
            position = anchors.get(name)
            if position is None:
                position = anchors.get(name.split("__")[0])
            if position is not None:
                found.append((position, entry.target))
        found.sort(key=lambda pair: pair[0])
        self._toc_positions = found

    def _sync_toc_to_position(self, position: int) -> None:
        if not self._toc_positions:
            return
        index = bisect.bisect_right(
            [start for start, _target in self._toc_positions], position
        ) - 1
        if index >= 0:
            self.toc_panel.mark_current(self._toc_positions[index][1])

    def toc_panel_populate(self, entries) -> None:
        self.toc_panel.populate(entries)

    def _restore_position(self) -> None:
        if self._restoring_position:
            self.reader.set_text_position(self._restoring_position)
            self._restoring_position = 0

    def _show_warnings(self, book: Book) -> None:
        if book.warnings:
            self.statusBar().showMessage(" · ".join(book.warnings[:3]), 8000)

    def _on_load_failed(self, message: str, detail: str) -> None:
        self.progress_bar.setVisible(False)
        self.status_title.setText("")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        # Carries file names and parser output, so it must not read markup.
        box.setTextFormat(Qt.PlainText)
        box.setWindowTitle(tr("The book could not be opened"))
        box.setText(message)
        if detail:
            box.setDetailedText(detail)
        box.exec()

    def close_book(self) -> None:
        self._toc_positions = []
        self._persist_position()
        self._save_timer.stop()
        self.book = None
        self.book_id = ""
        self.welcome.refresh()
        self.stack.setCurrentWidget(self.welcome)
        self.toc_panel.clear()
        self.bookmark_panel.populate([])
        self.annotation_panel.populate([])
        self.setWindowTitle(APP_NAME)
        self.status_title.setText("")
        self.status_position.setText("")
        self._update_actions()

    def _forget_book(self, ident: str) -> None:
        self.library.forget_book(ident)
        self.welcome.refresh()

    # ------------------------------------------------------------------
    # Current view helpers
    # ------------------------------------------------------------------
    @property
    def active_view(self):
        return self.stack.currentWidget()

    @property
    def is_text_book(self) -> bool:
        return self.active_view is self.reader and self.book is not None

    def next_page(self) -> None:
        view = self.active_view
        if hasattr(view, "next_page"):
            view.next_page()

    def previous_page(self) -> None:
        view = self.active_view
        if hasattr(view, "previous_page"):
            view.previous_page()

    def go_to_start(self) -> None:
        view = self.active_view
        if hasattr(view, "go_to_start"):
            view.go_to_start()

    def go_to_end(self) -> None:
        view = self.active_view
        if hasattr(view, "go_to_end"):
            view.go_to_end()

    def go_to_target(self, target) -> None:
        """Follow a TOC entry: an anchor for text, a page index otherwise."""

        if isinstance(target, int):
            if self.active_view is self.pdf:
                self.pdf.go_to_page(target)
            elif self.active_view is self.comic:
                self.comic.go_to_page(target)
        elif self.is_text_book:
            self.reader.scroll_to_anchor(str(target))

    def _go_to_position(self, position: int) -> None:
        if self.is_text_book:
            self.reader.set_text_position(position)
        elif self.active_view is self.pdf:
            self.pdf.go_to_page(position)
        elif self.active_view is self.comic:
            self.comic.go_to_page(position)

    def go_to_dialog(self) -> None:
        if self.active_view in (self.pdf, self.comic):
            total = self.active_view.page_count
            page, ok = QInputDialog.getInt(
                self, tr("Go to page"), tr("Page (1–%d):") % total,
                self.active_view.current_page, 1, total,
            )
            if ok:
                self.active_view.go_to_page(page - 1)
        elif self.is_text_book:
            percent, ok = QInputDialog.getInt(
                self, "Gehe zu Position", tr("Position in the book (%):"), 0, 0, 100
            )
            if ok:
                total = self.reader.document().characterCount()
                self.reader.set_text_position(int(total * percent / 100))

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------
    def _on_text_position(self, position: int, total: int) -> None:
        percent = int(100 * position / total) if total else 0
        self.status_position.setText(
            tr("Page %d/%d · %d %%") % (self.reader.current_page, self.reader.page_count, percent)
        )
        if self.book:
            self.status_title.setText(self._title_line())
        self._sync_toc_to_position(position)

    def _on_page_position(self, page: int, total: int) -> None:
        self.status_position.setText(tr("Page %d/%d · %d %%")
                                     % (page, total, int(100 * page / total) if total else 0))
        if self.book:
            self.status_title.setText(self._title_line())
        # PDF and comic outlines address pages directly, so no index is needed.
        self.toc_panel.mark_current(page - 1)

    def _title_line(self) -> str:
        assert self.book is not None
        if self.book.meta.author_line:
            return "%s — %s" % (self.book.meta.author_line, self.book.display_title)
        return self.book.display_title

    def _persist_position(self) -> None:
        if not self.book or not self.book_id:
            return
        if self.active_view is self.reader:
            document = self.reader.document()
            total = document.characterCount() if document else 0
            saved = self.library.save_position(
                self.book_id, self.reader.text_position(), total
            )
        elif self.active_view in (self.pdf, self.comic):
            view = self.active_view
            saved = self.library.save_position(
                self.book_id, view.current_page - 1, view.page_count
            )
        else:
            return
        if not saved:
            self._report_storage_failure()

    def _report_storage_failure(self) -> None:
        """Say once that the reading position is no longer being stored.

        Losing the position quietly is the worst outcome: the reader keeps
        working and the loss only surfaces on the next launch.  Reported once
        per session, because this runs on a four-second timer.
        """

        if self._storage_warned:
            return
        self._storage_warned = True
        self.status_title.setText(
            tr("Reading position cannot be saved — the library is not writable.")
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setTextFormat(Qt.PlainText)
        box.setWindowTitle(tr("Cannot save"))
        box.setText(
            tr("The reading position cannot be saved.\n\n"
               "The library file is locked or read-only:\n%s\n\n"
               "Reading still works, but positions, bookmarks and highlights "
               "from this session will be lost.") % self.library.path
        )
        box.exec()

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------
    def add_bookmark(self) -> None:
        if not self.book_id:
            return
        if self.active_view is self.reader:
            position = self.reader.text_position()
            suggestion = self.reader.context_around(position, position + 60, 0)[:60]
        elif self.active_view in (self.pdf, self.comic):
            position = self.active_view.current_page - 1
            suggestion = tr("Page %d") % self.active_view.current_page
        else:
            return

        label, ok = QInputDialog.getText(self, tr("Bookmarks"), tr("Label:"),
                                         text=suggestion.strip())
        if not ok:
            return
        self.library.add_bookmark(self.book_id, position, label.strip())
        self.bookmark_panel.populate(self.library.bookmarks(self.book_id))
        self.statusBar().showMessage(tr("Bookmark added."), 2500)

    def _remove_bookmark(self, ident: int) -> None:
        self.library.remove_bookmark(ident)
        self.bookmark_panel.populate(self.library.bookmarks(self.book_id))

    def add_highlight(self, colour: str = "yellow") -> None:
        if not self.is_text_book or not self.book_id:
            return
        start, end, text = self.reader.selected_range()
        if not text.strip():
            self.statusBar().showMessage(tr("Select text first, then highlight."), 3000)
            return
        excerpt = text.replace(" ", "\n")
        self.library.add_highlight(self.book_id, start, end, colour, excerpt)
        self._reload_highlights()
        self.statusBar().showMessage(tr("Highlight saved."), 2500)

    def _remove_highlight(self, ident: int) -> None:
        self.library.remove_highlight(ident)
        self._reload_highlights()

    def _recolour_highlight(self, ident: int, colour: str) -> None:
        self.library.update_highlight(ident, colour=colour)
        self._reload_highlights()

    def _edit_note(self, ident: int) -> None:
        existing = next((h for h in self.library.highlights(self.book_id) if h.ident == ident), None)
        if existing is None:
            return
        note, ok = QInputDialog.getMultiLineText(
            self, "Notiz", existing.excerpt[:200], existing.note
        )
        if ok:
            self.library.update_highlight(ident, note=note.strip())
            self._reload_highlights()

    def _reload_highlights(self) -> None:
        highlights = self.library.highlights(self.book_id)
        self.reader.set_highlights(highlights)
        self.annotation_panel.populate(highlights)

    def export_annotations(self) -> None:
        if not self.book_id or not self.book:
            return
        markdown = self.library.export_markdown(self.book_id, self.book.display_title)
        suggestion = os.path.join(
            os.path.dirname(self.book.path),
            _safe_filename(self.book.display_title) + " — Notizen.md",
        )
        path, _chosen = QFileDialog.getSaveFileName(
            self, tr("Export annotations"), suggestion, tr("Markdown (*.md);;All files (*)")
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(markdown)
        except OSError as exc:
            QMessageBox.warning(self, tr("Export failed"), str(exc))
            return
        self.statusBar().showMessage(tr("Annotations saved: %s") % path, 5000)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def focus_search(self) -> None:
        self.sidebar.setVisible(True)
        self.action_sidebar.setChecked(True)
        self.tabs.setCurrentWidget(self.search_panel)
        self.search_panel.focus_input()

    def run_search(self, needle: str, case_sensitive: bool, whole_words: bool) -> None:
        if self.active_view is self.pdf:
            count = self.pdf.search(needle)
            snippets = []
            for index in range(min(count, 500)):
                page, text = self.pdf.match_context(index)
                snippets.append(tr("p. %d — %s") % (page + 1, text))
            self._search_matches = [(i, i) for i in range(count)]
            self.search_panel.show_results(snippets, needle)
            self._search_index = -1
            if count:
                self.show_search_result(0)
            return

        if not self.is_text_book:
            return
        self._search_matches = self.reader.find_all(
            needle, case_sensitive=case_sensitive, whole_words=whole_words
        )
        snippets = [
            "…%s…" % self.reader.context_around(start, end)
            for start, end in self._search_matches[:500]
        ]
        self.search_panel.show_results(snippets, needle)
        self.reader.set_search_matches(self._search_matches)
        self._search_index = -1
        if self._search_matches:
            self.show_search_result(0)

    def show_search_result(self, index: int) -> None:
        if not 0 <= index < len(self._search_matches):
            return
        self._search_index = index
        self.search_panel.select_result(index)
        if self.active_view is self.pdf:
            self.pdf.show_match(index)
            return
        start, end = self._search_matches[index]
        self.reader.set_search_matches(self._search_matches, index)
        self.reader.select_range(start, end)

    def next_match(self) -> None:
        if self._search_matches:
            self.show_search_result((self._search_index + 1) % len(self._search_matches))

    def previous_match(self) -> None:
        if self._search_matches:
            self.show_search_result((self._search_index - 1) % len(self._search_matches))

    def _clear_search(self) -> None:
        self._search_matches = []
        self._search_index = -1
        self.reader.set_search_matches([])
        # The side panel keeps its own copy of the hits, so it has to be told;
        # otherwise stale results stay listed after the search is dismissed.
        self.search_panel.clear_results()
        if self.active_view is self.pdf:
            self.pdf.clear_search()

    def _on_escape(self) -> None:
        if self.isFullScreen():
            self.toggle_fullscreen()
        elif self._search_matches:
            self._clear_search()

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------
    def apply_theme(self, key: str) -> None:
        self.settings["theme"] = key
        active = theming.theme(key)
        QApplication.instance().setStyleSheet(theming.widget_stylesheet(active))
        self.reader.apply_theme(key)
        self.pdf.apply_theme(key)
        self.comic.apply_theme(key)
        self.welcome.apply_theme(key)
        for action in self._theme_group.actions():
            action.setChecked(action.data() == key)

    def zoom_in(self) -> None:
        self._zoom(1)

    def zoom_out(self) -> None:
        self._zoom(-1)

    def zoom_reset(self) -> None:
        if self.active_view is self.pdf:
            self.pdf.set_zoom_mode("width")
            self.statusBar().showMessage(tr("Zoom: fit to width"), 1800)
        else:
            self.set_font_size(DEFAULTS["font_size"])

    def _zoom(self, direction: int) -> None:
        """Route the zoom keys to whatever is actually on screen.

        In a PDF the page is a fixed layout, so changing the reading font does
        nothing visible — Ctrl+Plus appeared broken.  The same keys now scale
        the page there and the type everywhere else.
        """

        if self.active_view is self.pdf:
            self.pdf.zoom_by(1.25 if direction > 0 else 1 / 1.25)
            self.statusBar().showMessage(
                tr("Zoom: %d %%") % round(self.pdf.zoomFactor() * 100), 1800)
        else:
            self.change_font_size(direction)

    def change_font_size(self, delta: int) -> None:
        self.set_font_size(int(self.settings["font_size"]) + delta)

    def set_font_size(self, size: int) -> None:
        self.settings["font_size"] = max(8, min(48, size))
        self.reader.restyle()
        self.statusBar().showMessage(tr("Font size: %d pt") % self.settings["font_size"], 1800)

    def toggle_sidebar(self) -> None:
        visible = not self.sidebar.isVisible()
        self.sidebar.setVisible(visible)
        self.action_sidebar.setChecked(visible)
        self.settings["sidebar_visible"] = visible

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.menuBar().setVisible(True)
            self.toolbar.setVisible(True)
        else:
            self.showFullScreen()
            self.menuBar().setVisible(False)
            self.toolbar.setVisible(False)
        self.action_fullscreen.setChecked(self.isFullScreen())

    def open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.settings, self)
        dialog.settingsChanged.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self) -> None:
        self.settings.save()
        self.reader.restyle()
        if self.active_view is self.comic:
            self.comic.set_fit_mode(self.settings["comic_fit"])

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        entries = self.library.recent(int(self.settings["recent_limit"]))
        if not entries:
            action = self.recent_menu.addAction(tr("(nothing opened yet)"))
            action.setEnabled(False)
            return
        for entry in entries:
            label = "%s — %d %%" % (entry.title or os.path.basename(entry.path), entry.percent)
            action = self.recent_menu.addAction(label)
            action.setToolTip(entry.path)
            action.triggered.connect(lambda _checked=False, p=entry.path: self.open_path(p))
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(tr("Clear list"), self._clear_recent)

    def _clear_recent(self) -> None:
        answer = QMessageBox.question(
            self, tr("Clear list"),
            tr("Remove all recently opened books?\n\n"
               "Reading positions, bookmarks and highlights will be lost."),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.library.clear_recent()
            self.welcome.refresh()

    def _confirm_external_link(self, target: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        # The whole point of this dialog is showing the real destination, so it
        # must never interpret the address as markup.  Qt's AutoText would let a
        # crafted link disguise itself as something else.
        box.setTextFormat(Qt.PlainText)
        box.setWindowTitle(tr("Open link"))
        box.setText(tr("Open this link in the browser?\n\n%s") % target)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        if box.exec() == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(target))

    def show_shortcuts(self) -> None:
        QMessageBox.information(self, tr("Keyboard shortcuts"), shortcut_help())

    def show_licences(self) -> None:
        LicencesDialog(self).exec()

    def show_about(self) -> None:
        QMessageBox.about(
            self, tr("About %s") % APP_NAME,
            tr("<h3>%s %s</h3>"
               "<p>A free e-book reader for EPUB, Kindle formats, FB2, PDF, "
               "comics, text, Markdown, HTML and RTF.</p>"
               "<p>Licence: GNU GPL v3 or later.<br>"
               "Interface: Qt (PySide6, LGPL v3).</p>"
               "<p>The full texts are under Help → Licences.</p>")
            % (APP_NAME, __version__),
        )

    def _update_actions(self) -> None:
        has_book = self.book is not None
        text_book = self.is_text_book
        for action in (self.action_close_book, self.action_next, self.action_previous,
                       self.action_goto, self.action_bookmark, self.action_search):
            action.setEnabled(has_book)
        self.action_highlight.setEnabled(text_book)
        self.action_copy.setEnabled(text_book)
        self.action_export.setEnabled(has_book)
        self.action_next_match.setEnabled(bool(self._search_matches))
        self.action_previous_match.setEnabled(bool(self._search_matches))

    # -- drag and drop ----------------------------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt naming
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.open_path(url.toLocalFile())
                break

    # -- window state -----------------------------------------------------
    def _restore_window_state(self) -> None:
        geometry = self.settings["window_geometry"]
        state = self.settings["window_state"]
        if geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
        else:
            self.resize(1080, 780)
        if state:
            self.restoreState(QByteArray.fromBase64(state.encode("ascii")))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        # Stop the timer first: a tick after the library is closed would raise
        # from inside Qt's event loop, where nothing can handle it.
        self._save_timer.stop()
        self._persist_position()
        self.settings["window_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings["window_state"] = bytes(self.saveState().toBase64()).decode("ascii")
        self.settings["sidebar_visible"] = self.sidebar.isVisible()
        self.settings.save()
        # Waiting is right at exit and wrong anywhere else: a worker thread that
        # outlives the interpreter is worse than a brief pause here.
        self.loader.shutdown()
        super().closeEvent(event)


def shortcut_help() -> str:
    """The keyboard reference, translated when it is asked for.

    A function rather than a constant on purpose: a module-level ``tr()`` runs
    at import time, before the translator is installed, and would freeze the
    English text into the module for the life of the process.
    """

    # No backslash continuation after the opening quotes: Python would drop the
    # first newline while lupdate keeps it, and the two strings would then no
    # longer be the same one.
    return tr("""Reading
    Space / Page Down / →        Next page
    Backspace / Page Up / ←      Previous page
    Ctrl+Home / Ctrl+End         Beginning / end
    Ctrl+G                       Go to page or position

Searching
    Ctrl+F                       Open search
    F3 / Shift+F3                Next / previous match
    Esc                          Leave search, leave full screen

Annotations
    Ctrl+B                       Add bookmark
    Ctrl+H                       Highlight selection
    Ctrl+C                       Copy selection

View
    Ctrl++ / Ctrl+−              Larger / smaller type
    Ctrl+0                       Reset font size
    F9                           Show/hide the sidebar
    F11                          Full screen
    Ctrl+,                       Settings

Files
    Ctrl+O                       Open book
    Ctrl+W                       Close book
""")


def _walk_toc(entries):
    """Yield ``(depth, entry)`` for a nested table of contents."""

    for entry in entries:
        yield from entry.flatten()


def _action(parent, text: str, shortcut, slot) -> QAction:
    action = QAction(text, parent)
    if shortcut is not None:
        action.setShortcut(shortcut)
    action.triggered.connect(slot)
    return action


def _safe_filename(name: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in " -_." else "_" for ch in name)
    return keep.strip()[:80] or tr("Notes")
