"""User preferences, stored as JSON next to the reading database.

A plain dict with defaults rather than ``QSettings``, so preferences travel with
the portable build and stay readable and editable by hand.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .paths import secure_file, settings_path

DEFAULTS: dict[str, Any] = {
    "language": "system",          # system | en | de
    "theme": "light",              # light | sepia | dark | black
    "font_family": "",             # empty means the platform serif default
    "font_size": 17,
    "line_height": 1.55,
    "page_margin": 56,
    "text_width": 44,              # maximum line length in em; 0 disables the cap
    "paragraph_spacing": 0.7,
    "justify": True,
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

#: Permitted range per numeric setting, mirroring the dialog's spin boxes.
#: Type coercion alone let a hand-edited ``"font_size": 1000000`` through to
#: ``QFont.setPointSize``, leaving a window that could only be repaired by
#: deleting the file.
RANGES: dict[str, tuple[float, float]] = {
    "font_size": (6, 96),
    "line_height": (0.8, 4.0),
    "page_margin": (0, 400),
    "text_width": (0, 200),
    "paragraph_spacing": (0.0, 4.0),
    "recent_limit": (1, 200),
    "pdf_zoom": (0.05, 16.0),
}

#: Permitted values per enumerated setting.
CHOICES: dict[str, tuple[str, ...]] = {
    "language": ("system", "en", "de"),
    "theme": THEMES,
    "comic_fit": ("width", "height", "page", "original"),
    "pdf_zoom_mode": ("width", "page", "custom"),
}


def sanitise(key: str, value: Any) -> Any:
    """Clamp a value into the range this setting actually supports."""

    low_high = RANGES.get(key)
    if low_high is not None and isinstance(value, (int, float)):
        low, high = low_high
        value = max(low, min(high, value))
        return int(value) if isinstance(DEFAULTS[key], int) else float(value)
    allowed = CHOICES.get(key)
    if allowed is not None and value not in allowed:
        return DEFAULTS[key]
    return value


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
                    coerced: Any = bool(value)
                elif isinstance(default, int):
                    coerced = int(value)
                elif isinstance(default, float):
                    coerced = float(value)
                elif isinstance(default, str) and isinstance(value, str):
                    coerced = value
                else:
                    continue
            except (TypeError, ValueError):
                continue
            self._values[key] = sanitise(key, coerced)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self._values, handle, indent=2, ensure_ascii=False)
        os.replace(temporary, self.path)
        secure_file(self.path)

    def __getitem__(self, key: str) -> Any:
        return self._values.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        # Clamped here too, so a caller cannot write a value that reloading
        # would reject — the file and the running program stay in agreement.
        self._values[key] = sanitise(key, value)

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._values.get(key, fallback if fallback is not None else DEFAULTS.get(key))

    def reset(self) -> None:
        self._values = dict(DEFAULTS)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)
