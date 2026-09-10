"""The reflowable text view: pagination, selection, highlights and search.

Built on ``QTextBrowser`` rather than a hand-rolled layout so that selection,
accessibility, link handling and text shaping all come from Qt.  Pagination is
achieved by driving the scroll bar in exact viewport steps, which turns pages
crisply without ever splitting the document into separate widgets.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QPoint,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QGuiApplication,
    QImage,
    QImageReader,
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
        self._margins = (-1, -1)
        #: Word a long press started on. A finger selection never shrinks
        #: below it, so the first word stays selected while the finger moves.
        self._touch_span: tuple[int, int] | None = None

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
        # Fix the column width before parsing: the first layout pass already
        # asks for every image, and without a width it would size them for a
        # guessed column and then decode them all a second time.
        document.setTextWidth(self._text_width_hint())
        document.setHtml(html)
        _fix_image_blocks(document)
        self.setDocument(document)
        self.apply_typography()
        self._highlights = []
        self._search_selections = []
        self._refresh_selections()

    def _text_width_hint(self) -> float:
        """The column width a freshly built document should be laid out at.

        Mirrors what :meth:`_apply_typography` will settle on, so the first
        layout pass sizes images for their final column.
        """

        width = self.viewport().width()
        if width <= 1:
            width = max(1, self.width() - 2 * int(self.settings["page_margin"]))
        return float(width)

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
        document.setTextWidth(self._text_width_hint())
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

        document = self.document()
        # Setting the font re-lays out the whole document unconditionally — on a
        # long book that is tens of milliseconds — so only do it on a real
        # change.  Otherwise every resize event pays for a full relayout.
        if font != self.font():
            self.setFont(font)
        if document is not None and font != document.defaultFont():
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

        top = int(self.settings["page_margin"]) // 2
        if (margin, top) != self._margins:
            self._margins = (margin, top)
            self.setViewportMargins(margin, top, margin, top)
        self._reflow()
        # The page count depends on the freshly computed scroll range, so the
        # status line has to be told even when nothing scrolled.
        self._emit_position()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self.apply_typography()

    def _reflow(self) -> None:
        """Match the document width to the viewport, but only when it changed.

        ``setTextWidth`` relayouts the entire document, so calling it on every
        resize event — including the ones a vertical-only resize produces —
        would be pure waste on a long book.
        """

        document = self.document()
        if document is None:
            return
        width = float(self.viewport().width())
        if abs(document.textWidth() - width) >= 1.0:
            document.setTextWidth(width)

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

    def anchor_positions(self) -> dict[str, int]:
        """Character position of every anchor Qt kept in the document.

        Qt only records an anchor where it produced a text fragment, so the
        chapter markers survive while empty ``<a name=...>`` elements inside a
        chapter often do not.  Callers therefore fall back to the chapter an
        entry belongs to rather than expecting every id to be present.
        """

        document = self.document()
        positions: dict[str, int] = {}
        if document is None:
            return positions
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                for name in fragment.charFormat().anchorNames():
                    positions.setdefault(name, fragment.position())
                iterator += 1
            block = block.next()
        return positions
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

    # -- touch ------------------------------------------------------------
    def has_link_at(self, point: QPoint) -> bool:
        """Whether a tap at ``point`` (viewport coordinates) lands on a link."""

        return bool(self.anchorAt(point))

    def activate_link_at(self, point: QPoint) -> None:
        """Follow the link under a finger, as a click would."""

        target = self.anchorAt(point)
        if target:
            self._on_anchor_clicked(QUrl(target))

    def start_touch_selection(self, point: QPoint) -> None:
        """A long press selects the word under the finger."""

        cursor = self.cursorForPosition(point)
        cursor.select(QTextCursor.WordUnderCursor)
        self._touch_span = (cursor.selectionStart(), cursor.selectionEnd())
        self.setTextCursor(cursor)

    def extend_touch_selection(self, point: QPoint) -> None:
        """Grow the selection towards the finger, in either direction."""

        if self._touch_span is None:
            return
        position = self.cursorForPosition(point).position()
        first, last = self._touch_span
        cursor = self.textCursor()
        cursor.setPosition(min(first, position))
        cursor.setPosition(max(last, position), QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)

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


#: How much decoded image data to keep, in bytes.
#:
#: Measured on a 21 MB illustrated novel with fifteen full-page plates: at
#: 48 MB not one frame in a 150-notch scroll fell below 30 fps, while 24 MB
#: dropped 39 of them and 12 MB dropped 75.  Raising it to 96 MB bought no
#: further smoothness and cost another 51 MB, so this is the knee of the curve.
IMAGE_CACHE_BUDGET = 48 * 1024 * 1024

#: Target widths are rounded down to a multiple of this, so that dragging a
#: window edge reuses one cached rendition instead of decoding at every pixel.
WIDTH_BUCKET = 64


class _ImageCache:
    """A least-recently-used cache of decoded images, bounded by total bytes."""

    def __init__(self, budget: int | None = None) -> None:
        self.budget = IMAGE_CACHE_BUDGET if budget is None else budget
        self._entries: OrderedDict[tuple[str, int], QImage] = OrderedDict()
        self._bytes = 0

    def get(self, key: tuple[str, int]) -> QImage | None:
        image = self._entries.get(key)
        if image is not None:
            self._entries.move_to_end(key)
        return image

    def put(self, key: tuple[str, int], image: QImage) -> None:
        size = max(1, image.sizeInBytes())
        # A single picture larger than the whole budget would evict everything
        # and still not fit, so it is used but not kept.
        if size > self.budget:
            return
        if key in self._entries:
            self._bytes -= max(1, self._entries[key].sizeInBytes())
        self._entries[key] = image
        self._entries.move_to_end(key)
        self._bytes += size
        # Evict down to the budget, keeping the entry just inserted: it is the
        # one being drawn right now, and dropping it would decode it again on
        # the very next repaint.
        while self._bytes > self.budget and len(self._entries) > 1:
            oldest = next(iter(self._entries))
            if oldest == key:
                break
            self._bytes -= max(1, self._entries.pop(oldest).sizeInBytes())

    def clear(self) -> None:
        self._entries.clear()
        self._bytes = 0


class _BookDocument(QTextDocument):
    """Resolves ``<img src=...>`` against the book's in-memory resources.

    Qt only caches a resource when its own ``loadResource`` implementation runs.
    An override that returns early — as this one must, since book images live in
    memory rather than on disk — therefore has to do the caching itself, or every
    single repaint that touches a picture decodes and rescales it again.  On an
    illustrated book that is the difference between 5 ms and 32 ms per frame.
    """

    def __init__(self, book: Book, parent=None) -> None:
        super().__init__(parent)
        self._book = book
        self._cache = _ImageCache()
        self._cached_width = -1

    def loadResource(self, kind: int, name: QUrl):  # noqa: N802 - Qt naming
        if kind == QTextDocument.ImageResource:
            key = name.toString()
            target = self._target_width()
            if target != self._cached_width:
                # Renditions for a stale column width would otherwise sit in
                # the cache alongside the current ones, doubling the memory a
                # book's pictures cost after a resize.
                self._cache.clear()
                self._cached_width = target
            cached = self._cache.get((key, target))
            if cached is not None:
                return cached
            data = self._book.resource(key)
            if data is not None:
                image = self._decode(data, target)
                if image is not None:
                    self._cache.put((key, target), image)
                    return image
        return super().loadResource(kind, name)

    def _target_width(self) -> int:
        """Logical width available to an illustration, rounded to a bucket."""

        available = int(self.textWidth()) or 800
        return max(WIDTH_BUCKET, (available // WIDTH_BUCKET) * WIDTH_BUCKET)

    def _decode(self, data: bytes, target: int) -> QImage | None:
        """Decode at the size actually needed, not at full resolution.

        ``QImageReader.setScaledSize`` lets the codec do the work — for JPEG it
        scales during decoding rather than afterwards — which saves both time
        and the peak memory of holding a full-resolution copy.
        """

        ratio = self._device_ratio()
        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.ReadOnly)
        reader = QImageReader(buffer)
        reader.setAutoTransform(True)

        source = reader.size()
        limit = max(64, int(target * ratio))
        scaled = False
        if source.isValid() and source.width() > limit:
            height = max(1, round(source.height() * limit / source.width()))
            reader.setScaledSize(QSize(limit, height))
            scaled = True

        image = reader.read()
        buffer.close()
        if image.isNull():
            return None
        if scaled:
            # Report the rendition at its logical size so the layout reserves
            # column width, not device pixels, on a scaled display.
            image.setDevicePixelRatio(ratio)
        return image

    @staticmethod
    def _device_ratio() -> float:
        instance = QApplication.instance()
        return max(1.0, instance.devicePixelRatio()) if instance else 1.0
