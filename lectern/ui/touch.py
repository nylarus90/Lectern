"""Finger input for the reading views.

Until 1.3 a finger on a touch screen reached Lectern only as a mouse that Qt
had made up from it: dragging selected text instead of scrolling, and a flick,
a pinch or a long press meant nothing at all.

:class:`TouchReader` takes the touch events of one view's viewport and decides
what the finger meant:

======================  =======================================================
drag                    scroll, and keep going with momentum after release
sideways swipe          ``swiped`` -- previous or next page, wherever nothing
                        scrolls sideways (a zoomed-in PDF pans instead)
tap, left third         ``pageRequested(-1)``
tap, right third        ``pageRequested(+1)``
tap, middle             ``centreTapped`` -- the window brings its toolbar back
tap on a link           ``linkTapped``
long press              ``longPressed``, then ``pressDragged``/``pressReleased``
two-finger pinch        ``pinched`` with a scale factor, in steps
======================  =======================================================

A pen never gets here. Qt reports it as tablet input and synthesises mouse
events from it, so on a Surface the pen keeps selecting text exactly as the
mouse does while the finger scrolls. That settles the one real conflict
between the two without a mode switch.

Everything is recognised in one place rather than with Qt's separate gesture
recognisers, because the gestures exclude each other -- a long press must not
also scroll, a pinch must not also turn a page -- and that is only dependable
when a single state machine owns the finger.
"""

from __future__ import annotations

import math
import time
from collections import deque

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QEventPoint, QInputDevice
from PySide6.QtWidgets import QAbstractScrollArea

#: How long a finger has to rest before it counts as a long press. Any shorter
#: and the slow start of an ordinary scroll turns into a selection.
LONG_PRESS_MS = 550
#: How far a finger may wander and still be tapping or pressing.
SLOP_PX = 12
#: Sideways travel that makes a swipe a page turn.
SWIPE_PX = 70
#: Relative change of the finger distance that makes one pinch step.
PINCH_STEP = 0.12
#: Momentum: frame interval, speed kept per frame, and the speed where it ends.
FRAME_MS = 16
FRICTION = 0.93
STOP_SPEED = 0.03          # px per ms
#: Only the end of a drag says how fast the finger left the glass.
VELOCITY_WINDOW_MS = 90

#: Touch mode: toolbar icon size, and the extra height given to list rows.
TOUCH_ICON_PX = 32
TOUCH_ROW_CSS = "QListWidget::item, QTreeWidget::item { padding: 7px 4px; }"

_TOUCH_EVENTS = (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd, QEvent.TouchCancel)


def touch_screen_present() -> bool:
    """Whether the system reports a touch screen. A touchpad does not count."""

    return any(device.type() == QInputDevice.DeviceType.TouchScreen
               for device in QInputDevice.devices())


def touch_mode_active(setting: str) -> bool:
    """Resolve the ``touch_mode`` setting: ``on``, ``off`` or ``auto``."""

    if setting == "on":
        return True
    if setting == "off":
        return False
    return touch_screen_present()


def _from_touch_screen(event) -> bool:
    """True for touch events and for mouse events Qt made up from a finger."""

    device = event.device()
    return device is not None and device.type() == QInputDevice.DeviceType.TouchScreen


def _now_ms() -> float:
    return time.monotonic() * 1000.0


class TouchReader(QObject):
    """Recognises finger gestures on one scrollable view."""

    pageRequested = Signal(int)          # -1 back, +1 forward (tap at an edge)
    swiped = Signal(int)                 # -1 back, +1 forward
    centreTapped = Signal()
    linkTapped = Signal(QPoint)
    longPressed = Signal(QPoint)
    pressDragged = Signal(QPoint)
    pressReleased = Signal(QPoint)
    pinched = Signal(float)

    def __init__(self, view: QAbstractScrollArea, *, has_link=None,
                 long_press: bool = False) -> None:
        super().__init__(view)
        self._view = view
        self._has_link = has_link
        self._long_press = long_press
        viewport = view.viewport()
        # Without this Qt delivers a finger as synthesised mouse events only.
        viewport.setAttribute(Qt.WA_AcceptTouchEvents, True)
        viewport.installEventFilter(self)

        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.setInterval(LONG_PRESS_MS)
        self._hold.timeout.connect(self._on_hold)

        self._coast = QTimer(self)
        self._coast.setInterval(FRAME_MS)
        self._coast.timeout.connect(self._on_frame)

        self._mode = "idle"
        self._start = QPointF()
        self._last = QPointF()
        self._samples: deque[tuple[float, QPointF]] = deque(maxlen=16)
        self._velocity = QPointF()
        self._carry = QPointF()
        self._pinch_base = 0.0
        self._stopped_coast = False

    # -- dispatch ---------------------------------------------------------
    def eventFilter(self, _watched, event) -> bool:  # noqa: N802 - Qt naming
        kind = event.type()
        if kind not in _TOUCH_EVENTS or not _from_touch_screen(event):
            return False
        if kind == QEvent.TouchCancel:
            self._cancel()
            event.accept()
            return True

        points = event.points()
        active = [p for p in points if p.state() != QEventPoint.State.Released]
        if kind == QEvent.TouchBegin:
            self._begin(points[0].position())
        elif len(active) >= 2 or self._mode == "pinch":
            # Stays a pinch until every finger has left: the finger that is
            # still down must not suddenly start scrolling.
            self._pinch(active)
            if kind == QEvent.TouchEnd:
                self._mode = "idle"
        elif kind == QEvent.TouchUpdate:
            self._move(points[0].position())
        elif kind == QEvent.TouchEnd:
            self._end(points[0].position())
        # Accepting the touch is what stops Qt from also synthesising mouse
        # events, which would select text under the scrolling finger.
        event.accept()
        return True

    # -- single finger ----------------------------------------------------
    def _begin(self, pos: QPointF) -> None:
        # A finger that lands on a coasting page stops it, and only stops it:
        # a reader catching the text must not turn the page by doing so.
        self._stopped_coast = self._coast.isActive()
        self._coast.stop()
        self._mode = "pending"
        self._start = self._last = pos
        self._carry = QPointF()
        self._pinch_base = 0.0
        self._samples.clear()
        self._samples.append((_now_ms(), pos))
        if self._long_press:
            self._hold.start()

    def _move(self, pos: QPointF) -> None:
        if self._mode == "pending":
            offset = pos - self._start
            if math.hypot(offset.x(), offset.y()) < SLOP_PX:
                return
            self._hold.stop()
            sideways = abs(offset.x()) > 1.5 * abs(offset.y())
            self._mode = "swipe" if sideways and not self._scrolls_sideways() else "drag"
        if self._mode == "drag":
            # From the previous point, not from where the slop was crossed, so
            # the first twelve pixels are not lost.
            self._scroll_by(pos - self._last)
            self._samples.append((_now_ms(), pos))
        elif self._mode == "select":
            self.pressDragged.emit(pos.toPoint())
        self._last = pos

    def _end(self, pos: QPointF) -> None:
        self._hold.stop()
        mode, self._mode = self._mode, "idle"
        if mode == "pending":
            self._tap(pos)
        elif mode == "swipe":
            travel = pos.x() - self._start.x()
            if abs(travel) >= SWIPE_PX:
                # Content follows the finger: swiping to the left brings the
                # next page in from the right.
                self.swiped.emit(-1 if travel > 0 else 1)
        elif mode == "drag":
            self._samples.append((_now_ms(), pos))
            self._start_momentum()
        elif mode == "select":
            self.pressReleased.emit(pos.toPoint())

    def _tap(self, pos: QPointF) -> None:
        if self._stopped_coast:
            return
        point = pos.toPoint()
        if self._has_link is not None and self._has_link(point):
            self.linkTapped.emit(point)
            return
        width = max(1, self._view.viewport().width())
        if pos.x() < width / 3:
            self.pageRequested.emit(-1)
        elif pos.x() > width * 2 / 3:
            self.pageRequested.emit(1)
        else:
            self.centreTapped.emit()

    def _on_hold(self) -> None:
        if self._mode == "pending":
            self._mode = "select"
            self.longPressed.emit(self._start.toPoint())

    def _cancel(self) -> None:
        self._hold.stop()
        self._mode = "idle"

    # -- two fingers ------------------------------------------------------
    def _pinch(self, active) -> None:
        if len(active) < 2:
            return
        self._hold.stop()
        self._coast.stop()
        first, second = active[0].position(), active[1].position()
        distance = math.hypot(first.x() - second.x(), first.y() - second.y())
        if self._mode != "pinch" or self._pinch_base <= 0:
            self._mode = "pinch"
            self._pinch_base = max(distance, 1.0)
            return
        factor = distance / self._pinch_base
        if abs(factor - 1.0) >= PINCH_STEP:
            self.pinched.emit(factor)
            self._pinch_base = distance

    # -- scrolling --------------------------------------------------------
    def _scrolls_sideways(self) -> bool:
        return self._view.horizontalScrollBar().maximum() > 0

    def _scroll_by(self, delta: QPointF) -> bool:
        """Move the content with the finger; return whether anything moved.

        Scroll bars only take whole pixels, so the fraction is carried over:
        without that a slow coast rounds to zero and stops dead.
        """

        total = delta + self._carry
        whole = QPointF(math.trunc(total.x()), math.trunc(total.y()))
        self._carry = total - whole
        moved = False
        for bar, step in ((self._view.horizontalScrollBar(), whole.x()),
                          (self._view.verticalScrollBar(), whole.y())):
            if step and bar.maximum() > bar.minimum():
                before = bar.value()
                bar.setValue(int(before - step))
                moved = moved or bar.value() != before
        return moved

    def _start_momentum(self) -> None:
        latest = self._samples[-1][0]
        recent = [(t, p) for t, p in self._samples if latest - t <= VELOCITY_WINDOW_MS]
        if len(recent) < 2:
            return
        (t0, p0), (t1, p1) = recent[0], recent[-1]
        elapsed = max(t1 - t0, 1.0)
        self._velocity = QPointF((p1.x() - p0.x()) / elapsed, (p1.y() - p0.y()) / elapsed)
        if math.hypot(self._velocity.x(), self._velocity.y()) > STOP_SPEED:
            self._coast.start()

    def _on_frame(self) -> None:
        self._velocity *= FRICTION
        speed = math.hypot(self._velocity.x(), self._velocity.y())
        if speed < STOP_SPEED or not self._scroll_by(self._velocity * FRAME_MS):
            self._coast.stop()

    @property
    def coasting(self) -> bool:
        return self._coast.isActive()


class LongPressMenu(QObject):
    """Long press opens the context menu of an item view.

    Lists keep ordinary taps -- a tap must stay a click that selects or opens
    an item -- so they do not take touch events. This watches the mouse events
    Qt synthesises from a finger instead, and fires the view's
    ``customContextMenuRequested`` once the finger has rested. The release that
    follows is swallowed; otherwise it would also count as a click and open
    the very item whose menu just appeared.
    """

    def __init__(self, view: QAbstractScrollArea) -> None:
        super().__init__(view)
        self._view = view
        self._position = QPoint()
        self._fired = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LONG_PRESS_MS)
        self._timer.timeout.connect(self._fire)
        view.viewport().installEventFilter(self)

    def eventFilter(self, _watched, event) -> bool:  # noqa: N802 - Qt naming
        kind = event.type()
        if kind == QEvent.MouseButtonPress and _from_touch_screen(event):
            self._position = event.position().toPoint()
            self._fired = False
            self._timer.start()
        elif kind == QEvent.MouseMove and self._timer.isActive():
            if (event.position().toPoint() - self._position).manhattanLength() > SLOP_PX:
                self._timer.stop()
        elif kind == QEvent.MouseButtonRelease:
            self._timer.stop()
            if self._fired:
                self._fired = False
                return True
        return False

    def _fire(self) -> None:
        self._fired = True
        self._view.customContextMenuRequested.emit(self._position)
