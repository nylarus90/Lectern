"""Render the application icon to build/icon.ico and build/icon.png."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from lectern.app import _icon  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

app = QApplication([])
icon = _icon()
icon.pixmap(256, 256).save(os.path.join(HERE, "icon.png"), "PNG")
icon.pixmap(256, 256).save(os.path.join(HERE, "icon.ico"), "ICO")
print("icon.png und icon.ico geschrieben")
