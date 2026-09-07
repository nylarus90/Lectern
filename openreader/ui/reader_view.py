"""The reflowable text view: pagination, selection, highlights and search.

Built on ``QTextBrowser`` rather than a hand-rolled layout so that selection,
accessibility, link handling and text shaping all come from Qt.  Pagination is
achieved by driving the scroll bar in exact viewport steps, which turns pages
crisply without ever splitting the document into separate widgets.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QImage,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextOption,
)
from PySide6.QtWidgets import QApplication, QTextBrowser, QTextEdit

from ..formats.base import Book
from ..render import theme as theming

#: Overlap kept between consecutive pages so the eye can pick up the thread.
PAGE_OVERLAP_PX = 18


class ReaderView(QTextBrowser):
    """Displays one assembled book document."""

    positionChanged = Signal(int, int)      # character position, document length
    selectionAvailable = Signal(bool)
    externalLinkActivated = Signal(str)

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.book: Book | None = None
        self._html = ""
        self._theme = theming.theme(settings["theme"])
        self._highlights: list = []
        self._search_selections: list[QTextEdit.ExtraSelection] = []
        self._laying_out = False

        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setUndoRedoEnabled(False)
        self.setFrameShape(QTextBrowser.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard | Qt.LinksAccessibleByMouse
        )
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)

        self.anchorClicked.connect(self._on_anchor_clicked)
        self.copyAvailable.connect(self.selectionAvailable)
        self.verticalScrollBar().valueChanged.connect(self._emit_position)

    # -- document ---------------------------------------------------------
    def set_book(self, book: Book, html: str) -> None:
        """Install a pre-assembled document; ``html`` comes from a worker thread."""

        self.book = book
        self._html = html
        document = _BookDocument(book, self)
        document.setDefaultStyleSheet(self._stylesheet())
        document.setDocumentMargin(0)
        document.setHtml(html)
        _fix_image_blocks(document)
        self.setDocument(document)
        self.apply_typography()
        self._highlights = []
        self._search_selections = []
        self._refresh_selections()

    def _stylesheet(self) -> str:
        css = theming.document_stylesheet(self.settings, self._theme)
        if self.settings["use_publisher_css"] and self.book and self.book.publisher_css:
            # Publisher CSS goes first so our own rules still win on conflict.
            css = self.book.publisher_css + "\n" + css
        return css

    # -- appearance -------------------------------------------------------
    def apply_theme(self, key: str) -> None:
        self._theme = theming.theme(key)
        self.restyle()
        palette = self.palette()
        palette.setColor(palette.ColorRole.Base, QColor(self._theme.background))
        palette.setColor(palette.ColorRole.Text, QColor(self._theme.text))
        palette.setColor(palette.ColorRole.Highlight, QColor(self._theme.selection))
        palette.setColor(palette.ColorRole.HighlightedText, QColor(self._theme.text))
        self.setPalette(palette)
        self.apply_typography()
        self._refresh_selections()

    def restyle(self) -> None:
        """Re-apply the stylesheet after a typography or theme change.

        Qt only re-reads the default stylesheet while parsing HTML, so the
        document has to be rebuilt from the source we kept rather than from
        ``toHtml()``, which would bake the old rules in permanently.
        """

        document = self.document()
        if document is None or not self._html:
            return
        position = self.text_position()
        document.setDefaultStyleSheet(self._stylesheet())
        document.setHtml(self._html)
        _fix_image_blocks(document)
        self.apply_typography()
        self.set_text_position(position)
        self._refresh_selections()

    def apply_typography(self) -> None:
        """Apply font, margins and the maximum line length.

        Changing the viewport margins resizes the viewport, which would call
        this method again, so the re-entrance guard is what stops the layout
        from oscillating.
        """

        if self._laying_out:
            return
        self._laying_out = True
        try:
            self._apply_typography()
        finally:
            self._laying_out = False

    def _apply_typography(self) -> None:
        family = self.settings["font_family"]
        font = QFont(family) if family else QFont()
        if not family:
            font.setStyleHint(QFont.Serif)
            font.setFamily(font.defaultFamily())
        font.setPointSize(int(self.settings["font_size"]))
        self.setFont(font)

        document = self.document()
        if document is not None:
            document.setDefaultFont(font)

        margin = int(self.settings["page_margin"])
        # Cap the measure: long lines are the single biggest readability loss on
        # a wide window, so grow the side margins instead of the line length.
        max_em = int(self.settings["text_width"])
        if max_em > 0:
            metrics = self.fontMetrics()
            ideal = metrics.horizontalAdvance("m") * max_em
            available = self.viewport().width() - 2 * margin
            if available > ideal:
                margin += (available - ideal) // 2
        self.setViewportMargins(margin, int(self.settings["page_margin"]) // 2,
                                margin, int(self.settings["page_margin"]) // 2)
        self._reflow()
        # The page count depends on the freshly computed scroll range, so the
        # status line has to be told even when nothing scrolled.
        self._emit_position()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self.apply_typography()

    def _reflow(self) -> None:
        document = self.document()
        if document is not None:
            document.setTextWidth(self.viewport().width())

    # -- pagination -------------------------------------------------------
    @property
    def page_step(self) -> int:
        return max(40, self.viewport().height() - PAGE_OVERLAP_PX)

    def next_page(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(min(bar.maximum(), bar.value() + self.page_step))

    def previous_page(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(max(bar.minimum(), bar.value() - self.page_step))

    def go_to_start(self) -> None:
        self.verticalScrollBar().setValue(0)

    def go_to_end(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    @property
    def page_count(self) -> int:
        bar = self.verticalScrollBar()
        return max(1, (bar.maximum() + self.page_step - 1) // self.page_step + 1)

    @property
    def current_page(self) -> int:
        bar = self.verticalScrollBar()
        return min(self.page_count, bar.value() // self.page_step + 1)

    # -- position ---------------------------------------------------------
    def text_position(self) -> int:
        """Character offset of the first visible character."""

        cursor = self.cursorForPosition(QPoint(2, 2))
        return cursor.position()

    def set_text_position(self, position: int) -> None:
        document = self.document()
        if document is None:
            return
        position = max(0, min(position, document.characterCount() - 1))
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        self.setTextCursor(cursor)
        self._scroll_cursor_to_top(cursor)

    def _scroll_cursor_to_top(self, cursor: QTextCursor) -> None:
        """Put the cursor's line at the top of the viewport, not merely in view."""

        rect = self.cursorRect(cursor)
        bar = self.verticalScrollBar()
        bar.setValue(min(bar.maximum(), max(0, bar.value() + rect.top())))

    def scroll_to_anchor(self, anchor: str) -> None:
        self.scrollToAnchor(anchor.lstrip("#"))
        self._emit_position()

    def _emit_position(self) -> None:
        document = self.document()
        if document is None:
            return
        self.positionChanged.emit(self.text_position(), document.characterCount())

    # -- links ------------------------------------------------------------
    def _on_anchor_clicked(self, url: QUrl) -> None:
        target = url.toString()
        if target.startswith("#"):
            self.scroll_to_anchor(target)
        elif url.scheme() in ("http", "https", "mailto"):
            self.externalLinkActivated.emit(target)

    def open_external(self, target: str) -> None:
        QDesktopServices.openUrl(QUrl(target))

    # -- selection --------------------------------------------------------
    def selected_range(self) -> tuple[int, int, str]:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return (0, 0, "")
        return (cursor.selectionStart(), cursor.selectionEnd(), cursor.selectedText())

    def select_range(self, start: int, end: int) -> None:
        document = self.document()
        if document is None:
            return
        cursor = QTextCursor(document)
        cursor.setPosition(max(0, start))
        cursor.setPosition(min(end, document.characterCount() - 1), QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def copy_selection(self) -> None:
        clipboard = QGuiApplication.clipboard()
        _start, _end, text = self.selected_range()
        if text:
            clipboard.setText(text.replace(" ", "\n"))

    # -- highlights and search --------------------------------------------
    def set_highlights(self, highlights) -> None:
        self._highlights = list(highlights)
        self._refresh_selections()

    def set_search_matches(self, ranges: list[tuple[int, int]], current: int = -1) -> None:
        document = self.document()
        self._search_selections = []
        if document is None:
            return
        for index, (start, end) in enumerate(ranges):
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(document)
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            selection.cursor = cursor
            fmt = QTextCharFormat()
            colour = QColor(self._theme.accent if index == current else self._theme.selection)
            colour.setAlpha(255 if index == current else 140)
            fmt.setBackground(colour)
            if index == current:
                fmt.setForeground(QColor(self._theme.background))
            selection.format = fmt
            self._search_selections.append(selection)
        self._refresh_selections()

    def _refresh_selections(self) -> None:
        document = self.document()
        if document is None:
            return
        selections: list[QTextEdit.ExtraSelection] = []
        limit = document.characterCount() - 1
        for highlight in self._highlights:
            if highlight.start >= limit:
                continue
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(document)
            cursor.setPosition(max(0, highlight.start))
            cursor.setPosition(min(highlight.end, limit), QTextCursor.KeepAnchor)
            selection.cursor = cursor
            fmt = QTextCharFormat()
            _label, hexcolour = theming.HIGHLIGHT_COLOURS.get(
                highlight.colour, theming.HIGHLIGHT_COLOURS["yellow"]
            )
            colour = QColor(hexcolour)
            if self._theme.is_dark:
                # A pastel wash would wipe out the text on a dark page, so keep
                # the hue but let the page show through.
                colour.setAlpha(90)
            fmt.setBackground(colour)
            if not self._theme.is_dark:
                # On a light page the pastel needs dark text over it; on a dark
                # page the existing light text already reads fine.
                fmt.setForeground(QColor("#1a1a1a"))
            if highlight.note:
                fmt.setFontUnderline(True)
                fmt.setUnderlineStyle(QTextCharFormat.DotLine)
            selection.format = fmt
            selections.append(selection)
        self.setExtraSelections(selections + self._search_selections)

    def find_all(self, needle: str, *, case_sensitive: bool, whole_words: bool) -> list[tuple[int, int]]:
        """Return every match as a character range, in document order."""

        document = self.document()
        if document is None or not needle:
            return []
        flags = QTextDocument.FindFlags()
        if case_sensitive:
            flags |= QTextDocument.FindCaseSensitively
        if whole_words:
            flags |= QTextDocument.FindWholeWords

        matches: list[tuple[int, int]] = []
        cursor = QTextCursor(document)
        while True:
            cursor = document.find(needle, cursor, flags)
            if cursor.isNull():
                break
            matches.append((cursor.selectionStart(), cursor.selectionEnd()))
            if len(matches) >= 5000:  # a runaway search helps nobody
                break
        return matches

    def context_around(self, start: int, end: int, width: int = 40) -> str:
        document = self.document()
        if document is None:
            return ""
        cursor = QTextCursor(document)
        cursor.setPosition(max(0, start - width))
        cursor.setPosition(min(document.characterCount() - 1, end + width),
                           QTextCursor.KeepAnchor)
        return cursor.selectedText().replace(" ", " ").strip()


#: Qt substitutes this character for an embedded object such as an image.
OBJECT_CHAR = "￼"


def _fix_image_blocks(document: QTextDocument) -> None:
    """Undo proportional line spacing on lines that contain an image.

    A relative ``line-height`` multiplies the height of the tallest item on the
    line, so a 320 px illustration in a 155 % block reserves 496 px and leaves a
    gaping hole underneath it.  Blocks whose only content is an image also get
    centred, which is what a full-width plate wants in every real book.
    """

    block = document.begin()
    while block.isValid():
        text = block.text()
        if OBJECT_CHAR in text:
            cursor = QTextCursor(block)
            fmt = block.blockFormat()
            fmt.setLineHeight(100.0, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            if not text.replace(OBJECT_CHAR, "").strip():
                fmt.setAlignment(Qt.AlignHCenter)
            cursor.setBlockFormat(fmt)
        block = block.next()


class _BookDocument(QTextDocument):
    """Resolves ``<img src=...>`` against the book's in-memory resources."""

    def __init__(self, book: Book, parent=None) -> None:
        super().__init__(parent)
        self._book = book

    def loadResource(self, kind: int, name: QUrl):  # noqa: N802 - Qt naming
        if kind == QTextDocument.ImageResource:
            key = name.toString()
            data = self._book.resource(key)
            if data is not None:
                image = QImage()
                if image.loadFromData(data):
                    return self._fit(image)
        return super().loadResource(kind, name)

    def _fit(self, image: QImage) -> QImage:
        """Scale oversized illustrations down to the text column.

        Qt does not scale images to fit, so a 3000 px plate would otherwise
        force a horizontal scroll bar across the whole book.
        """

        available = int(self.textWidth()) or 800
        ratio = QApplication.instance().devicePixelRatio() if QApplication.instance() else 1.0
        limit = max(200, int(available * max(1.0, ratio)))
        if image.width() > limit:
            image = image.scaledToWidth(limit, Qt.SmoothTransformation)
            image.setDevicePixelRatio(ratio)
        return image
