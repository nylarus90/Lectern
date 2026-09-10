"""The rename from OpenReader to Lectern must not cost anyone their data.

Up to 1.1.1 reading positions, bookmarks and notes lived in a directory named
after the old program. These tests pin down the adoption: the old directory is
moved, never copied; a directory under the new name always wins; and a failed
move leaves the old one in use rather than starting an empty library.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from lectern.storage import paths

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _library(directory: pathlib.Path) -> pathlib.Path:
    directory.mkdir(parents=True)
    marker = directory / "library.sqlite3"
    marker.write_text("notes that must survive", encoding="utf-8")
    return marker


def test_legacy_directory_is_moved(tmp_path):
    legacy = tmp_path / "openreader"
    _library(legacy)
    current = tmp_path / "lectern"

    assert paths.adopt_legacy(str(current), str(legacy)) == str(current)
    assert (current / "library.sqlite3").read_text(encoding="utf-8") == "notes that must survive"
    assert not legacy.exists(), "moved, not copied: one history, not two"


def test_existing_directory_wins(tmp_path):
    legacy, current = tmp_path / "openreader", tmp_path / "lectern"
    _library(legacy)
    current.mkdir()

    assert paths.adopt_legacy(str(current), str(legacy)) == str(current)
    assert legacy.exists(), "an existing new directory must never be overwritten"


def test_failed_move_keeps_using_the_legacy_directory(tmp_path, monkeypatch):
    legacy = tmp_path / "openreader"
    _library(legacy)

    def refuse(*_args):
        raise PermissionError("the old version still has the database open")

    monkeypatch.setattr(paths.os, "rename", refuse)
    chosen = paths.adopt_legacy(str(tmp_path / "lectern"), str(legacy))
    assert chosen == str(legacy), "an empty library is worse than an unmoved one"
    assert (legacy / "library.sqlite3").exists()


def test_nothing_to_adopt(tmp_path):
    current = tmp_path / "lectern"
    assert paths.adopt_legacy(str(current), str(tmp_path / "openreader")) == str(current)


def test_default_location_is_adopted(tmp_path, monkeypatch):
    monkeypatch.delenv("LECTERN_DATA_DIR", raising=False)
    monkeypatch.delenv("OPENREADER_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "_platform_dir", lambda name: str(tmp_path / name))
    _library(tmp_path / "openreader")

    assert paths.data_dir() == str(tmp_path / "lectern")
    assert (tmp_path / "lectern" / "library.sqlite3").exists()


def test_portable_directory_is_adopted(tmp_path):
    _library(tmp_path / "openreader-data")

    assert paths.portable_dir(str(tmp_path)) == str(tmp_path / "lectern-data")
    assert (tmp_path / "lectern-data" / "library.sqlite3").exists()


def test_legacy_environment_variable_still_counts(tmp_path, monkeypatch):
    monkeypatch.delenv("LECTERN_DATA_DIR", raising=False)
    monkeypatch.setenv("OPENREADER_DATA_DIR", str(tmp_path / "scripted"))
    assert paths.data_dir() == str(tmp_path / "scripted")


def test_new_environment_variable_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("LECTERN_DATA_DIR", str(tmp_path / "new"))
    monkeypatch.setenv("OPENREADER_DATA_DIR", str(tmp_path / "old"))
    assert paths.data_dir() == str(tmp_path / "new")


#: Where the old name may still appear: code that exists to find what the old
#: version left behind says so by naming itself legacy.
_SHIPPED = sorted(
    [p for p in (ROOT / "lectern").rglob("*") if p.suffix in (".py", ".ts")
     and "_versions" not in p.parts]
    + [ROOT / "build" / "lectern.spec", ROOT / "lectern.desktop"]
)


@pytest.mark.parametrize("path", _SHIPPED, ids=lambda p: str(p.relative_to(ROOT)))
def test_old_name_only_where_it_is_adopted(path: pathlib.Path) -> None:
    stray = [
        "%d: %s" % (number, line.strip())
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search("openreader", line, re.IGNORECASE) and "legacy" not in line.lower()
    ]
    assert not stray, "the old name outside the migration code:\n" + "\n".join(stray)
