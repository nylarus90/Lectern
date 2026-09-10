"""Finger input: scrolling, momentum, taps, swipes, pinch and long press.

Driven with simulated touch sequences, so it runs everywhere, CI included.
What a simulation cannot say is how any of it feels on glass — the thresholds
in ``lectern/ui/touch.py`` are there to be tuned on a real device.
"""

from __future__ import annotations

import os

import pytest

from . import make_samples
from .conftest import dispose, spin

pytest.importorskip("PySide6.QtWidgets")

#: On a real desktop Qt dropped simulated touches for seconds at a time, so
#: these tests run in their own offscreen process; see test_touch_runner.py.
pytestmark = pytest.mark.skipif(
    os.environ.get("QT_QPA_PLATFORM") != "offscreen",
    reason="runs in its own offscreen process (tests/test_touch_runner.py)",
)


@pytest.fixture(scope="module")
def samples():
    return make_samples.make_all()


@pytest.fixture
def device(app):
    """A fresh touch screen for every test.

    Qt tracks the fingers that are down per device, so a sequence cut short by
    a failing assertion cannot leave a finger down for the next test.
    """

    from PySide6.QtGui import QInputDevice
    from PySide6.QtTest import QTest

    return QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)


def _close_popups(app) -> None:
    """An open menu takes every touch and click until it closes."""

    from PySide6.QtWidgets import QApplication

    for _ in range(5):
        popup = QApplication.activePopupWidget()
        if popup is None:
            return
        popup.close()
        spin(app, 30)


def _place_on_screen(widget, width: int, height: int) -> None:
    """Put a test window at the top left of the screen, and entirely on it.

    Qt drops a touch at a point that lies on no screen, before any window
    sees it. The offscreen platform's screen is 800 pixels wide and the test
    window was 1000, so every tap on the right third and every swipe starting
    there vanished -- measured: a tap at x = 903 was lost, one at x = 303 on
    the same device arrived. That made exactly the edge-tap and swipe tests
    fail, and only those.
    """

    from PySide6.QtGui import QGuiApplication

    area = QGuiApplication.primaryScreen().availableGeometry()
    widget.resize(min(width, area.width()), min(height, area.height()))
    widget.move(area.topLeft())


@pytest.fixture
def window(app, tmp_path):
    from lectern.storage.db import Library
    from lectern.storage.settings import Settings
    from lectern.ui.main_window import MainWindow

    settings = Settings(str(tmp_path / "settings.json"))
    library = Library(str(tmp_path / "library.sqlite3"))
    win = MainWindow(settings, library)
    _place_on_screen(win, 1000, 720)
    win.show()
    spin(app, 120)
    yield win
    _close_popups(app)
    dispose(app, win)
    library.close()


def _open(app, window, path: str) -> None:
    import os

    from PySide6.QtCore import QElapsedTimer

    window.open_path(path)
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < 15000:
        app.processEvents()
        if window.book is not None and os.path.samefile(window.book.path, path):
            spin(app, 250)
            return
    raise AssertionError("book did not load: %s" % path)


# -- simulated fingers ------------------------------------------------------
class _Fingers:
    """A touch sequence whose points are in the target widget's coordinates.

    ``QTouchEventSequence.press(id, point)`` without its widget argument reads
    the point relative to the *window*, not to the widget the sequence was
    created for. On a view that does not start at the window's corner every
    touch then lands somewhere else -- in the sidebar, as the first version of
    these tests found out.
    """

    def __init__(self, device, widget) -> None:
        from PySide6.QtTest import QTest

        self._sequence = QTest.touchEvent(widget, device, False)
        self._widget = widget

    def press(self, touch_id, point):
        self._sequence.press(touch_id, point, self._widget)
        return self

    def move(self, touch_id, point):
        self._sequence.move(touch_id, point, self._widget)
        return self

    def release(self, touch_id, point):
        self._sequence.release(touch_id, point, self._widget)
        return self

    def commit(self):
        self._sequence.commit()
        return self


def _sequence(device, widget):
    return _Fingers(device, widget)


def _point(x, y):
    from PySide6.QtCore import QPoint

    return QPoint(int(x), int(y))


def drag(app, device, widget, start, end, steps=10, pause=15):
    _sequence(device, widget).press(0, start).commit()
    spin(app, pause)
    for i in range(1, steps + 1):
        x = start.x() + (end.x() - start.x()) * i / steps
        y = start.y() + (end.y() - start.y()) * i / steps
        _sequence(device, widget).move(0, _point(x, y)).commit()
        spin(app, pause)
    _sequence(device, widget).release(0, end).commit()


def tap(app, device, widget, point):
    _sequence(device, widget).press(0, point).commit()
    spin(app, 30)
    _sequence(device, widget).release(0, point).commit()
    spin(app, 120)


def hold(app, device, widget, point, then=None):
    _sequence(device, widget).press(0, point).commit()
    spin(app, 800)                       # longer than LONG_PRESS_MS
    if then is not None:
        _sequence(device, widget).move(0, then).commit()
        spin(app, 60)
    _sequence(device, widget).release(0, then or point).commit()
    spin(app, 120)


def pinch(app, device, widget, centre, start_gap, end_gap, steps=8):
    half = start_gap / 2
    _sequence(device, widget).press(0, _point(centre.x() - half, centre.y())) \
        .press(1, _point(centre.x() + half, centre.y())).commit()
    spin(app, 20)
    for i in range(1, steps + 1):
        half = (start_gap + (end_gap - start_gap) * i / steps) / 2
        _sequence(device, widget).move(0, _point(centre.x() - half, centre.y())) \
            .move(1, _point(centre.x() + half, centre.y())).commit()
        spin(app, 20)
    _sequence(device, widget).release(0, _point(centre.x() - half, centre.y())) \
        .release(1, _point(centre.x() + half, centre.y())).commit()
    spin(app, 120)


def _text_point(window, position):
    """Viewport coordinates of a character, a little inside it."""

    from PySide6.QtGui import QTextCursor

    cursor = QTextCursor(window.reader.document())
    cursor.setPosition(position)
    rect = window.reader.cursorRect(cursor)
    return _point(rect.center().x() + 3, rect.center().y())


@pytest.fixture
def long_text(app, window, samples):
    """An open book, set large enough that there is plenty to scroll."""

    _open(app, window, samples["epub3"])
    window.set_font_size(40)
    spin(app, 250)
    window.reader.go_to_start()
    spin(app)
    return window.reader


# -- scrolling --------------------------------------------------------------
def test_drag_scrolls_with_the_finger(app, window, device, long_text):
    viewport = long_text.viewport()
    bar = long_text.verticalScrollBar()
    before = bar.value()
    height = viewport.height()
    drag(app, device, viewport, _point(viewport.width() / 2, height * 0.8),
         _point(viewport.width() / 2, height * 0.3), pause=40)
    spin(app, 50)
    assert bar.value() - before >= height * 0.4, "content must follow the finger"
    assert not long_text.textCursor().hasSelection(), "a finger drag must not select"


def test_a_flick_keeps_coasting(app, window, device, long_text):
    viewport = long_text.viewport()
    bar = long_text.verticalScrollBar()
    drag(app, device, viewport, _point(viewport.width() / 2, viewport.height() * 0.8),
         _point(viewport.width() / 2, viewport.height() * 0.5), steps=5, pause=8)
    at_release = bar.value()
    spin(app, 350)
    assert bar.value() > at_release, "a fast flick keeps moving after the finger lifts"


def test_catching_a_coasting_page_does_not_turn_it(app, window, device, long_text):
    viewport = long_text.viewport()
    bar = long_text.verticalScrollBar()
    drag(app, device, viewport, _point(viewport.width() / 2, viewport.height() * 0.8),
         _point(viewport.width() / 2, viewport.height() * 0.5), steps=5, pause=8)
    assert window.touch_text.coasting
    caught = bar.value()
    tap(app, device, viewport, _point(viewport.width() * 0.9, viewport.height() / 2))
    assert not window.touch_text.coasting
    assert bar.value() - caught < long_text.page_step / 2, "the catch must not also page"


# -- taps -------------------------------------------------------------------
def test_tapping_the_edges_turns_pages(app, window, device, long_text):
    viewport = long_text.viewport()
    bar = long_text.verticalScrollBar()
    start = bar.value()
    tap(app, device, viewport, _point(viewport.width() * 0.9, viewport.height() / 2))
    assert bar.value() == min(bar.maximum(), start + long_text.page_step)
    tap(app, device, viewport, _point(viewport.width() * 0.1, viewport.height() / 2))
    assert bar.value() == start


def test_tapping_the_middle_brings_the_toolbar_back_in_full_screen(app, window, device,
                                                                    long_text):
    viewport = long_text.viewport()
    window.toggle_fullscreen()
    spin(app, 200)
    try:
        assert not window.toolbar.isVisible()
        tap(app, device, viewport, _point(viewport.width() / 2, viewport.height() / 2))
        assert window.toolbar.isVisible()
        tap(app, device, viewport, _point(viewport.width() / 2, viewport.height() / 2))
        assert not window.toolbar.isVisible()
    finally:
        window.toggle_fullscreen()
        spin(app, 200)


def test_tapping_a_link_follows_it(app, window, device, long_text):
    document = long_text.document()
    found = document.find("Kapitel 2")
    assert not found.isNull(), "the sample book links to chapter 2"
    long_text.set_text_position(max(0, found.selectionStart() - 5))
    spin(app, 150)
    point = _text_point(window, found.selectionStart() + 2)
    assert long_text.has_link_at(point)
    before = long_text.text_position()
    tap(app, device, long_text.viewport(), point)
    spin(app, 150)
    assert long_text.text_position() > before + 20, "the link leads further into the book"


# -- swipes and pinches -----------------------------------------------------
def test_swiping_turns_comic_pages(app, window, device, samples):
    _open(app, window, samples["cbz"])
    viewport = window.comic.viewport()
    y = viewport.height() / 2
    drag(app, device, viewport, _point(viewport.width() * 0.8, y), _point(viewport.width() * 0.2, y))
    spin(app, 150)
    assert window.comic.current_page == 2
    drag(app, device, viewport, _point(viewport.width() * 0.2, y), _point(viewport.width() * 0.8, y))
    spin(app, 150)
    assert window.comic.current_page == 1


def test_pinching_changes_the_font_size(app, window, device, long_text):
    viewport = long_text.viewport()
    centre = _point(viewport.width() / 2, viewport.height() / 2)
    before = window.settings["font_size"]
    pinch(app, device, viewport, centre, 100, 300)
    grown = window.settings["font_size"]
    assert grown > before
    pinch(app, device, viewport, centre, 300, 100)
    assert window.settings["font_size"] < grown


def test_pinching_zooms_a_pdf(app, window, device, samples):
    _open(app, window, samples["pdf"])
    viewport = window.pdf.viewport()
    before = window.pdf.zoomFactor()
    pinch(app, device, viewport, _point(viewport.width() / 2, viewport.height() / 2), 100, 260)
    assert window.pdf.zoomFactor() > before


# -- long press -------------------------------------------------------------
def test_long_press_selects_a_word_and_offers_the_menu(app, window, device, long_text):
    long_text.set_text_position(300)
    spin(app, 150)
    hold(app, device, long_text.viewport(), _text_point(window, 305))
    cursor = long_text.textCursor()
    assert cursor.hasSelection() and cursor.selectedText().strip()
    menu = window._selection_menu
    assert menu is not None and menu.isVisible()
    menu.close()
    spin(app, 50)


def test_moving_after_a_long_press_extends_the_selection(app, window, device, long_text):
    long_text.set_text_position(300)
    spin(app, 150)
    start = _text_point(window, 305)
    hold(app, device, long_text.viewport(), start, then=_text_point(window, 360))
    assert len(long_text.textCursor().selectedText()) > 30
    if window._selection_menu is not None:
        window._selection_menu.close()
        spin(app, 50)


def test_the_mouse_and_the_pen_still_select(app, window, long_text):
    """A pen arrives as synthesised mouse events; those must keep selecting."""

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    long_text.set_text_position(300)
    spin(app, 150)
    before = long_text.verticalScrollBar().value()
    QTest.mouseDClick(long_text.viewport(), Qt.LeftButton, pos=_text_point(window, 305))
    spin(app, 80)
    assert long_text.textCursor().hasSelection()
    assert long_text.verticalScrollBar().value() == before


def test_long_press_opens_list_context_menus(app, device):
    """A resting finger opens the menu, and the lift is not also a click.

    Tested on a list of its own: the welcome screen hides its list while there
    is nothing in it, and a finger on a hidden widget lands on whatever is
    behind it.
    """

    from PySide6.QtWidgets import QListWidget

    from lectern.ui.touch import LongPressMenu

    view = QListWidget()
    view.addItems(["Book A", "Book B"])
    _place_on_screen(view, 300, 200)
    view.show()
    spin(app, 80)
    LongPressMenu(view)
    requested, clicked = [], []
    view.customContextMenuRequested.connect(requested.append)
    view.itemClicked.connect(lambda item: clicked.append(item.text()))

    hold(app, device, view.viewport(), _point(30, 12))
    assert requested, "a resting finger must open the list's context menu"
    assert not clicked, "the lift after a long press must not open the item as well"
    dispose(app, view)


def test_the_window_offers_long_press_on_its_lists(window):
    watched = {menu.parent() for menu in window._long_press_menus}
    assert watched == {window.welcome.list, window.bookmark_panel.list,
                       window.annotation_panel.list}


# -- touch mode -------------------------------------------------------------
def test_touch_mode_enlarges_the_controls(app, window, monkeypatch):
    from lectern.ui import touch

    window.settings["touch_mode"] = "on"
    window.apply_touch_mode()
    assert window.toolbar.iconSize().width() >= touch.TOUCH_ICON_PX
    assert window.action_fullscreen_touch.isVisible()
    assert "padding" in window.welcome.list.styleSheet()

    window.settings["touch_mode"] = "off"
    window.apply_touch_mode()
    assert window.toolbar.iconSize().width() < touch.TOUCH_ICON_PX
    assert not window.action_fullscreen_touch.isVisible()
    assert window.welcome.list.styleSheet() == ""

    window.settings["touch_mode"] = "auto"
    monkeypatch.setattr(touch, "touch_screen_present", lambda: True)
    window.apply_touch_mode()
    assert window.touch_active
    monkeypatch.setattr(touch, "touch_screen_present", lambda: False)
    window.apply_touch_mode()
    assert not window.touch_active


def test_touch_mode_setting_is_validated():
    from lectern.storage.settings import DEFAULTS, sanitise

    assert DEFAULTS["touch_mode"] == "auto"
    assert sanitise("touch_mode", "sometimes") == "auto"
    assert sanitise("touch_mode", "on") == "on"
