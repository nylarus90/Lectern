"""Reading preferences.

Every control writes straight into the settings object and emits
``settingsChanged``, so the page behind the dialog updates as you drag a slider
rather than only after pressing OK.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import i18n
from ..i18n import tr
from ..render import theme as theming
from ..storage.settings import DEFAULTS


class SettingsDialog(QDialog):
    settingsChanged = Signal()

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Settings"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        tabs.addTab(self._typography_tab(), tr("Typography"))
        tabs.addTab(self._reading_tab(), tr("Reading"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Close | QDialogButtonBox.RestoreDefaults, self)
        buttons.rejected.connect(self.accept)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _typography_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self.font_box = QFontComboBox(page)
        current = self.settings["font_family"]
        if current:
            self.font_box.setCurrentFont(self.font_box.currentFont().__class__(current))
        self.font_box.currentFontChanged.connect(
            lambda font: self._set("font_family", font.family())
        )
        form.addRow(tr("Font"), self.font_box)

        self.size_box = QSpinBox(page)
        self.size_box.setRange(8, 48)
        self.size_box.setSuffix(" pt")
        self.size_box.setValue(int(self.settings["font_size"]))
        self.size_box.valueChanged.connect(lambda value: self._set("font_size", value))
        form.addRow(tr("Font size"), self.size_box)

        self.line_slider = _slider(page, 100, 250, int(float(self.settings["line_height"]) * 100))
        self.line_label = QLabel("", page)
        self.line_slider.valueChanged.connect(
            lambda value: (self._set("line_height", value / 100),
                           self.line_label.setText("%.2f" % (value / 100)))
        )
        self.line_label.setText("%.2f" % float(self.settings["line_height"]))
        form.addRow(tr("Line height"), _with_label(self.line_slider, self.line_label))

        self.spacing_slider = _slider(page, 0, 200,
                                      int(float(self.settings["paragraph_spacing"]) * 100))
        self.spacing_label = QLabel("%.2f" % float(self.settings["paragraph_spacing"]), page)
        self.spacing_slider.valueChanged.connect(
            lambda value: (self._set("paragraph_spacing", value / 100),
                           self.spacing_label.setText("%.2f" % (value / 100)))
        )
        form.addRow(tr("Paragraph spacing"), _with_label(self.spacing_slider, self.spacing_label))

        self.margin_box = QSpinBox(page)
        self.margin_box.setRange(0, 200)
        self.margin_box.setSuffix(" px")
        self.margin_box.setValue(int(self.settings["page_margin"]))
        self.margin_box.valueChanged.connect(lambda value: self._set("page_margin", value))
        form.addRow(tr("Page margin"), self.margin_box)

        self.width_box = QSpinBox(page)
        self.width_box.setRange(0, 120)
        self.width_box.setSuffix(tr(" characters"))
        self.width_box.setSpecialValueText(tr("unlimited"))
        self.width_box.setValue(int(self.settings["text_width"]))
        self.width_box.setToolTip(
            tr("Maximum line length. Long lines are the commonest reason for the eye\n"
               "losing its place at the end of a line.")
        )
        self.width_box.valueChanged.connect(lambda value: self._set("text_width", value))
        form.addRow(tr("Line width"), self.width_box)

        self.justify_box = QCheckBox(tr("Justify"), page)
        self.justify_box.setChecked(bool(self.settings["justify"]))
        self.justify_box.toggled.connect(lambda on: self._set("justify", on))
        form.addRow("", self.justify_box)

        return page

    def _reading_tab(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)

        self.theme_box = QComboBox(page)
        for key, active in theming.THEMES.items():
            self.theme_box.addItem(active.label, key)
        index = self.theme_box.findData(self.settings["theme"])
        self.theme_box.setCurrentIndex(max(0, index))
        self.theme_box.currentIndexChanged.connect(self._theme_changed)
        form.addRow(tr("Colour scheme"), self.theme_box)

        self.publisher_box = QCheckBox(tr("Use the publisher's stylesheet"), page)
        self.publisher_box.setChecked(bool(self.settings["use_publisher_css"]))
        self.publisher_box.setToolTip(
            tr("Qt understands only part of CSS. Publisher stylesheets can make a book\n"
               "look better — or considerably worse. When in doubt, leave this off.")
        )
        self.publisher_box.toggled.connect(lambda on: self._set("use_publisher_css", on))
        form.addRow(tr("EPUB"), self.publisher_box)

        self.comic_box = QComboBox(page)
        for key, label in (("width", tr("Fit width")), ("height", tr("Fit height")),
                           ("page", tr("Whole page")), ("original", tr("Original size"))):
            self.comic_box.addItem(label, key)
        index = self.comic_box.findData(self.settings["comic_fit"])
        self.comic_box.setCurrentIndex(max(0, index))
        self.comic_box.currentIndexChanged.connect(
            lambda _index: self._set("comic_fit", self.comic_box.currentData())
        )
        form.addRow(tr("Comics"), self.comic_box)

        self.recent_box = QSpinBox(page)
        self.recent_box.setRange(0, 100)
        self.recent_box.setValue(int(self.settings["recent_limit"]))
        self.recent_box.valueChanged.connect(lambda value: self._set("recent_limit", value))
        form.addRow(tr("Recently opened"), self.recent_box)

        self.language_box = QComboBox(page)
        for code, _label in i18n.LANGUAGES:
            self.language_box.addItem(i18n.language_label(code), code)
        current = self.language_box.findData(self.settings["language"])
        self.language_box.setCurrentIndex(max(0, current))
        self.language_box.currentIndexChanged.connect(self._language_changed)
        form.addRow(tr("Language"), self.language_box)

        self.language_note = QLabel(
            tr("The language takes effect after restarting OpenReader."), page)
        self.language_note.setWordWrap(True)
        # Only worth saying once the user has actually changed something.
        self.language_note.setVisible(False)
        form.addRow("", self.language_note)

        note = QLabel(
            tr("Settings and reading progress live in:\n%s") % _data_location(), page)
        note.setWordWrap(True)
        note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow("", note)
        return page

    def _language_changed(self, _index: int) -> None:
        """Store the language and say that it needs a restart.

        Rebuilding every widget in place would be the nicer behaviour, but Qt
        only re-reads translated text when a widget is created, so half the
        window would change and half would not — worse than an honest note.
        """

        self.settings["language"] = self.language_box.currentData()
        self.language_note.setVisible(True)
        self.settingsChanged.emit()

    # ------------------------------------------------------------------
    def _set(self, key: str, value) -> None:
        self.settings[key] = value
        self.settingsChanged.emit()

    def _theme_changed(self, _index: int) -> None:
        key = self.theme_box.currentData()
        self.settings["theme"] = key
        # Without this the theme only reached the disk when the window closed.
        self.settingsChanged.emit()
        parent = self.parent()
        if parent is not None and hasattr(parent, "apply_theme"):
            parent.apply_theme(key)

    def _restore(self) -> None:
        answer = QMessageBox.question(
            self, tr("Reset"), tr("Reset all display settings?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        # Window geometry is not a display preference; keep it.
        geometry = self.settings["window_geometry"]
        state = self.settings["window_state"]
        self.settings.reset()
        self.settings["window_geometry"] = geometry
        self.settings["window_state"] = state

        self.size_box.setValue(DEFAULTS["font_size"])
        self.line_slider.setValue(int(DEFAULTS["line_height"] * 100))
        self.spacing_slider.setValue(int(DEFAULTS["paragraph_spacing"] * 100))
        self.margin_box.setValue(DEFAULTS["page_margin"])
        self.width_box.setValue(DEFAULTS["text_width"])
        self.justify_box.setChecked(DEFAULTS["justify"])
        self.publisher_box.setChecked(DEFAULTS["use_publisher_css"])
        self.theme_box.setCurrentIndex(max(0, self.theme_box.findData(DEFAULTS["theme"])))
        # The font box was left showing the old family while the setting behind
        # it had already been reset, so dialog and state disagreed.
        self.font_box.blockSignals(True)
        self.font_box.setCurrentFont(QFont())
        self.font_box.blockSignals(False)
        self.settingsChanged.emit()


def _slider(parent, minimum: int, maximum: int, value: int) -> QSlider:
    slider = QSlider(Qt.Horizontal, parent)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    return slider


def _with_label(slider: QSlider, label: QLabel) -> QWidget:
    from PySide6.QtWidgets import QHBoxLayout

    box = QWidget(slider.parent())
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(slider, 1)
    label.setMinimumWidth(42)
    row.addWidget(label)
    return box


def _data_location() -> str:
    from ..storage.paths import data_dir

    return data_dir()
