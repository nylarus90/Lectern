"""Reading themes and the typographic stylesheet handed to ``QTextDocument``.

The stylesheet is deliberately opinionated: publisher CSS is off by default
because Qt supports only a fraction of CSS 2.1, and a half-applied publisher
sheet looks worse than a clean one applied fully.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    background: str
    text: str
    #: Background of the surrounding window, a shade off the page itself.
    surface: str
    accent: str
    muted: str
    selection: str
    link: str

    @property
    def is_dark(self) -> bool:
        return self.key in ("dark", "black")


THEMES: dict[str, Theme] = {
    "light": Theme("light", "Hell", "#fdfdfb", "#1a1a1a", "#e8e8e4",
                   "#2f5d8a", "#6b6b66", "#bcd6f0", "#1d4f7c"),
    "sepia": Theme("sepia", "Sepia", "#f6ecd9", "#3b3227", "#e6d9be",
                   "#8a5a2f", "#7a6a54", "#e2c89a", "#7a4a1f"),
    "dark": Theme("dark", "Dunkel", "#22262b", "#d6d3cd", "#191c20",
                  "#7fb2e0", "#8b8b86", "#3d5878", "#8fc0ee"),
    "black": Theme("black", "Schwarz (OLED)", "#000000", "#c9c6c1", "#0a0a0a",
                   "#7fb2e0", "#7a7a76", "#2c4260", "#8fc0ee"),
}

#: Highlight colours offered in the annotation menu, tuned to stay readable on
#: every theme rather than being pure saturated hues.
HIGHLIGHT_COLOURS = {
    "yellow": ("Yellow", "#f5e07a"),
    "green": ("Green", "#a8dda0"),
    "blue": ("Blue", "#a3c9ea"),
    "pink": ("Pink", "#f0b0c8"),
    "orange": ("Orange", "#f3c08a"),
}


def theme(key: str) -> Theme:
    return THEMES.get(key, THEMES["light"])


def document_stylesheet(settings, active: Theme) -> str:
    """Build the CSS applied to the book document.

    Only properties Qt's rich text engine actually honours are emitted; adding
    the rest would be noise that silently does nothing.
    """

    size = int(settings["font_size"])
    line_height = float(settings["line_height"])
    spacing = float(settings["paragraph_spacing"])
    align = "justify" if settings["justify"] else "left"
    small = max(10, int(size * 0.82))

    return """
    body, p, div, li, td, th, blockquote {{
        color: {text};
        line-height: {line}%;
    }}
    p {{
        text-align: {align};
        margin-top: {space}em;
        margin-bottom: {space}em;
        text-indent: 0;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: {text};
        font-weight: bold;
        text-align: left;
        margin-top: 1.4em;
        margin-bottom: 0.6em;
        line-height: 120%;
    }}
    h1 {{ font-size: {h1}pt; }}
    h2 {{ font-size: {h2}pt; }}
    h3 {{ font-size: {h3}pt; }}
    h4, h5, h6 {{ font-size: {size}pt; }}
    a {{ color: {link}; text-decoration: none; }}
    blockquote {{
        margin-left: 2em;
        margin-right: 1.2em;
        color: {muted};
        font-style: italic;
    }}
    pre, code {{
        font-family: "Cascadia Mono", "DejaVu Sans Mono", "Courier New", monospace;
        font-size: {small}pt;
    }}
    pre {{ background-color: {surface}; }}
    table {{ margin: 1em 0; }}
    th, td {{ padding: 4px 8px; }}
    th {{ font-weight: bold; background-color: {surface}; }}
    img {{ margin: 0.6em 0; }}
    hr {{ color: {muted}; }}
    .or-figure, .or-figure p {{ text-align: center; }}
    .or-figcaption, .or-alttext {{
        font-size: {small}pt;
        color: {muted};
        text-align: center;
        font-style: italic;
    }}
    .or-poem, .or-stanza {{ margin-left: 2em; }}
    .or-verse {{ margin-top: 0; margin-bottom: 0; text-align: left; }}
    .or-author {{ text-align: right; color: {muted}; font-style: italic; }}
    .or-epigraph {{ color: {muted}; }}
    .or-annotation {{ color: {muted}; font-size: {small}pt; }}
    .or-notes {{ color: {muted}; }}
    .or-pagebreak {{ margin-top: 1.4em; }}
    """.format(
        text=active.text,
        muted=active.muted,
        link=active.link,
        surface=active.surface,
        line=int(line_height * 100),
        align=align,
        space=round(spacing, 2),
        size=size,
        small=small,
        h1=int(size * 1.7),
        h2=int(size * 1.4),
        h3=int(size * 1.18),
    )


def widget_stylesheet(active: Theme) -> str:
    """Qt Widgets stylesheet for the surrounding chrome."""

    return f"""
    QMainWindow, QDialog {{ background-color: {active.surface}; }}
    QDockWidget {{ color: {active.text}; titlebar-close-icon: none; }}
    QDockWidget::title {{
        background-color: {active.surface};
        color: {active.muted};
        padding: 6px 10px;
        border: none;
    }}
    QTreeWidget, QListWidget, QTextBrowser, QPlainTextEdit {{
        background-color: {active.background};
        color: {active.text};
        border: none;
        selection-background-color: {active.selection};
        selection-color: {active.text};
    }}
    QTreeWidget::item, QListWidget::item {{ padding: 5px 4px; }}
    QTreeWidget::item:selected, QListWidget::item:selected {{
        background-color: {active.selection};
        color: {active.text};
    }}
    QTabWidget::pane {{ border: none; background-color: {active.background}; }}
    QTabBar {{ background-color: {active.surface}; }}
    QTabBar::tab {{
        background-color: {active.surface};
        color: {active.muted};
        padding: 7px 12px;
        border: none;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: {active.text};
        background-color: {active.background};
        border-bottom: 2px solid {active.accent};
    }}
    QTabBar::tab:hover:!selected {{ color: {active.text}; }}
    QToolBar {{
        background-color: {active.surface};
        border: none;
        spacing: 3px;
        padding: 3px;
    }}
    QToolButton {{ color: {active.text}; padding: 5px 8px; border-radius: 4px; }}
    QToolButton:hover {{ background-color: {active.selection}; }}
    QToolButton:checked {{ background-color: {active.selection}; }}
    QStatusBar {{ background-color: {active.surface}; color: {active.muted}; }}
    QStatusBar::item {{ border: none; }}
    QMenuBar {{ background-color: {active.surface}; color: {active.text}; }}
    QMenuBar::item:selected {{ background-color: {active.selection}; }}
    QMenu {{ background-color: {active.background}; color: {active.text}; border: 1px solid {active.surface}; }}
    QMenu::item:selected {{ background-color: {active.selection}; }}
    QLabel {{ color: {active.text}; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {active.background};
        color: {active.text};
        border: 1px solid {active.selection};
        border-radius: 4px;
        padding: 4px 6px;
    }}
    QPushButton {{
        background-color: {active.surface};
        color: {active.text};
        border: 1px solid {active.selection};
        border-radius: 4px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{ background-color: {active.selection}; }}
    QScrollBar:vertical {{ background: {active.surface}; width: 11px; margin: 0; }}
    QScrollBar::handle:vertical {{
        background: {active.muted}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
    QScrollBar:horizontal {{ background: {active.surface}; height: 11px; margin: 0; }}
    QScrollBar::handle:horizontal {{
        background: {active.muted}; border-radius: 5px; min-width: 30px;
    }}
    QSplitter::handle {{ background-color: {active.surface}; }}
    QProgressBar {{
        background-color: {active.surface};
        border: none;
        height: 4px;
        text-align: center;
        color: {active.muted};
    }}
    QProgressBar::chunk {{ background-color: {active.accent}; }}
    """
