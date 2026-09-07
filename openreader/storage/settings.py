"""User preferences, stored as JSON next to the reading database.

A plain dict with defaults rather than ``QSettings``, so preferences travel with
the portable build and stay readable and editable by hand.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .paths import settings_path

DEFAULTS: dict[str, Any] = {
    "theme": "light",              # light | sepia | dark | black
    "font_family": "",             # empty means the platform serif default
    "font_size": 17,
    "line_height": 1.55,
    "page_margin": 56,
    "text_width": 44,              # maximum line length in em; 0 disables the cap
    "paragraph_spacing": 0.7,
    "justify": True,
    "hyphenate": False,
    "reading_mode": "paged",       # paged | scroll
    "use_publisher_css": False,
    "window_geometry": "",
    "window_state": "",
    "sidebar_visible": True,
    "recent_limit": 20,
    "comic_fit": "width",          # width | height | page | original
    "pdf_zoom_mode": "width",      # width | page | custom
    "pdf_zoom": 1.0,
}

#: Presets the view turns into concrete colours.
THEMES = ("light", "sepia", "dark", "black")


class Settings:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or settings_path()
        self._values = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as handle:
                stored = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(stored, dict):
            return
        # Unknown keys are dropped and known ones coerced, so neither a
        # downgrade nor a hand-edited file can poison the configuration.
        for key, value in stored.items():
            if key not in DEFAULTS:
                continue
            default = DEFAULTS[key]
            try:
                if isinstance(default, bool):
                    self._values[key] = bool(value)
                elif isinstance(default, int):
                    self._values[key] = int(value)
                elif isinstance(default, float):
                    self._values[key] = float(value)
                elif isinstance(default, str) and isinstance(value, str):
                    self._values[key] = value
            except (TypeError, ValueError):
                continue

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self._values, handle, indent=2, ensure_ascii=False)
        os.replace(temporary, self.path)

    def __getitem__(self, key: str) -> Any:
        return self._values.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self._values[key] = value

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._values.get(key, fallback if fallback is not None else DEFAULTS.get(key))

    def reset(self) -> None:
        self._values = dict(DEFAULTS)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)
