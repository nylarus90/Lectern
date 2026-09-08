"""Application entry point."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile

from .version import APP_NAME, ORG_NAME, __version__


def _attach_console() -> None:
    """Reconnect stdio to the calling terminal in a windowed Windows build.

    A GUI executable is linked without a console, so ``--version`` and
    ``--help`` would have nowhere to write.  Attaching to the parent console
    makes those flags behave exactly as they do from source; when the program
    was started from Explorer there is no parent and nothing changes.
    """

    if sys.platform != "win32" or sys.stdout is not None:
        return
    try:
        import ctypes

        attach_parent_process = -1
        if not ctypes.windll.kernel32.AttachConsole(attach_parent_process):
            return
        # These streams must outlive this function, so no context manager.
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    except Exception:  # noqa: BLE001 - a missing console is not an error
        pass


class _Parser(argparse.ArgumentParser):
    """Argument parser that still works in a windowed build.

    A GUI executable on Windows has no console, so ``sys.stdout`` is ``None``
    and argparse's ``--help`` or ``--version`` would raise instead of printing.
    Routing the text to a message box keeps both flags useful.
    """

    def _print_message(self, message: str, file=None) -> None:
        if message and (file is None or file in (sys.stdout, sys.stderr)):
            if sys.stdout is not None and file is not sys.stderr:
                super()._print_message(message, file)
                return
            if sys.stderr is not None and file is sys.stderr:
                super()._print_message(message, file)
                return
            _message_box(message)
            return
        super()._print_message(message, file)


def _message_box(message: str) -> None:
    """Show text that would otherwise have gone to a missing console."""

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv[:1])
        box = QMessageBox()
        box.setWindowTitle(APP_NAME)
        box.setTextFormat(1)  # Qt.RichText, set numerically to avoid an import
        box.setText("<pre>%s</pre>" % message.replace("&", "&amp;").replace("<", "&lt;"))
        box.exec()
        del app
    except Exception:  # noqa: BLE001 - never fail while reporting
        pass


def _open_storage():
    """Open settings and library, falling back to a throwaway directory.

    An unwritable data directory — a read-only stick in portable mode, a bad
    ``--data-dir``, a locked roaming profile — used to raise before any window
    existed.  In the windowed build that meant the program simply never
    appeared: no window, no message, nothing.  Reading is still possible
    without persistence, so say what happened and carry on.
    """

    from .storage.db import Library
    from .storage.settings import Settings

    try:
        return Settings(), Library()
    except (OSError, sqlite3.Error) as exc:
        fallback = tempfile.mkdtemp(prefix="openreader-")
        _message_box(
            "Die Bibliothek konnte nicht geöffnet werden:\n\n%s\n\n"
            "OpenReader startet mit einem temporären Speicherort. Bücher lassen "
            "sich lesen, aber Leseposition, Lesezeichen und Notizen dieser "
            "Sitzung werden nicht dauerhaft gespeichert." % exc
        )
        os.environ["OPENREADER_DATA_DIR"] = fallback
        return Settings(), Library()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _Parser(
        prog="openreader",
        description="%s — freier E-Book-Reader für EPUB, Kindle, FB2, PDF, "
                    "Comics, Text, Markdown, HTML und RTF." % APP_NAME,
    )
    parser.add_argument("file", nargs="?", help="Buch, das beim Start geöffnet wird")
    parser.add_argument("--version", action="version", version="%s %s" % (APP_NAME, __version__))
    parser.add_argument(
        "--data-dir", metavar="PFAD",
        help="Verzeichnis für Einstellungen und Lesefortschritt "
             "(für portable Nutzung, z. B. auf einem USB-Stick)",
    )
    parser.add_argument(
        "--portable", action="store_true",
        help="Daten neben der Programmdatei ablegen statt im Benutzerprofil",
    )
    return parser.parse_args(argv)


def _resolve_data_dir(args: argparse.Namespace) -> None:
    if args.data_dir:
        os.environ["OPENREADER_DATA_DIR"] = os.path.abspath(args.data_dir)
        return
    if args.portable:
        # sys.frozen is set by PyInstaller; sys.executable is then the bundle.
        base = os.path.dirname(os.path.abspath(
            sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
        ))
        os.environ["OPENREADER_DATA_DIR"] = os.path.join(base, "openreader-data")
        return
    # A marker file next to the executable also switches on portable mode, which
    # is how a USB stick copy stays self-contained without any command line.
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.exists(os.path.join(base, "portable.txt")):
            os.environ["OPENREADER_DATA_DIR"] = os.path.join(base, "openreader-data")


def main(argv: list[str] | None = None) -> int:
    _attach_console()
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    _resolve_data_dir(args)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(_icon())

    from .ui.main_window import MainWindow

    settings, library = _open_storage()

    window = MainWindow(settings, library)
    window.show()

    if args.file:
        window.open_path(os.path.abspath(args.file))

    try:
        return app.exec()
    finally:
        library.close()


def _icon():
    """A generated book icon, so the app needs no binary asset."""

    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2f5d8a"))
    painter.drawRoundedRect(QRectF(28, 20, 200, 216), 18, 18)
    painter.setBrush(QColor("#f6f2e8"))
    painter.drawRoundedRect(QRectF(52, 40, 152, 176), 8, 8)
    painter.setBrush(QColor("#2f5d8a"))
    for index in range(5):
        painter.drawRoundedRect(QRectF(74, 70 + index * 28, 108 - index * 6, 10), 5, 5)
    painter.end()
    return QIcon(pixmap)


if __name__ == "__main__":
    raise SystemExit(main())
