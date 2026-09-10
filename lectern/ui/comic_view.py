"""Comic viewer: one page image at a time, scaled to fit.

Kept deliberately simple — a scroll area with a scaled pixmap — because for
comics the only things that matter are fill mode, fast page turns and not
running out of memory on a 400-page archive.  Pages are decoded on demand and
kept in a small cache around the current position.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy

from ..formats.base import Book
from ..render import theme as theming

#: How many decoded pages to keep either side of the current one.
CACHE_RADIUS = 2


class ComicView(QScrollArea):
    positionChanged = Signal(int, int)   # current page (1-based), page count

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.book: Book | None = None
        self._index = 0
        self._cache: dict[int, QImage] = {}

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setWidget(self._label)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignCenter)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setFocusPolicy(Qt.StrongFocus)

    # -- document ---------------------------------------------------------
    def set_book(self, book: Book) -> None:
        self.book = book
        self._cache.clear()
        self._index = 0
        self.show_page(0)

    @property
    def page_count(self) -> int:
        return len(self.book.images) if self.book else 0

    @property
    def current_page(self) -> int:
        return self._index + 1

    def show_page(self, index: int) -> None:
        if not self.book or not self.book.images:
            return
        self._index = max(0, min(index, self.page_count - 1))
        self._evict()
        image = self._image(self._index)
        if image is not None:
            self._render(image)
        self.verticalScrollBar().setValue(0)
        self.positionChanged.emit(self.current_page, self.page_count)

    def _image(self, index: int) -> QImage | None:
        if index in self._cache:
            return self._cache[index]
        if not self.book or not 0 <= index < self.page_count:
            return None
        data = self.book.resource(self.book.images[index])
        if data is None:
            return None
        image = QImage()
        if not image.loadFromData(data):
            return None
        self._cache[index] = image
        return image

    def _evict(self) -> None:
        keep = range(self._index - CACHE_RADIUS, self._index + CACHE_RADIUS + 1)
        for key in [k for k in self._cache if k not in keep]:
            del self._cache[key]

    # -- rendering --------------------------------------------------------
    def _render(self, image: QImage) -> None:
        mode = self.settings["comic_fit"]
        available = self.viewport().size()
        if mode == "original" or available.width() < 10:
            scaled = image
        elif mode == "width":
            scaled = image.scaledToWidth(available.width(), Qt.SmoothTransformation)
        elif mode == "height":
            scaled = image.scaledToHeight(available.height(), Qt.SmoothTransformation)
        else:
            scaled = image.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(QPixmap.fromImage(scaled))
        self._label.setMinimumSize(QSize(1, 1))
        self._label.resize(scaled.size())

    def set_fit_mode(self, mode: str) -> None:
        self.settings["comic_fit"] = mode
        self.show_page(self._index)

    #: What a pinch steps through, from the whole page to full detail.
    ZOOM_ORDER = ("page", "width", "original")

    def zoom_step(self, direction: int) -> None:
        """Pinching out shows more detail, pinching in more of the page."""

        current = self.settings["comic_fit"]
        index = self.ZOOM_ORDER.index(current) if current in self.ZOOM_ORDER else 1
        index = max(0, min(len(self.ZOOM_ORDER) - 1, index + direction))
        if self.ZOOM_ORDER[index] != current:
            self.set_fit_mode(self.ZOOM_ORDER[index])

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        image = self._cache.get(self._index)
        if image is not None and self.settings["comic_fit"] != "original":
            self._render(image)

    # -- navigation -------------------------------------------------------
    def next_page(self) -> None:
        bar = self.verticalScrollBar()
        # Scroll through a tall page first, then flip.
        if bar.value() < bar.maximum():
            bar.setValue(min(bar.maximum(), bar.value() + max(40, self.viewport().height() - 18)))
        elif self._index + 1 < self.page_count:
            self.show_page(self._index + 1)

    def previous_page(self) -> None:
        bar = self.verticalScrollBar()
        if bar.value() > bar.minimum():
            bar.setValue(max(bar.minimum(), bar.value() - max(40, self.viewport().height() - 18)))
        elif self._index > 0:
            self.show_page(self._index - 1)
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def go_to_page(self, index: int) -> None:
        self.show_page(index)

    def go_to_start(self) -> None:
        self.show_page(0)

    def go_to_end(self) -> None:
        self.show_page(self.page_count - 1)

    # -- appearance -------------------------------------------------------
    def apply_theme(self, key: str) -> None:
        active = theming.theme(key)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(active.surface))
        palette.setColor(QPalette.ColorRole.Base, QColor(active.surface))
        self.setPalette(palette)
        self.setBackgroundRole(QPalette.ColorRole.Window)
        self.setAutoFillBackground(True)
        self._label.setPalette(palette)
