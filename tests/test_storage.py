"""Reading state and preferences."""

import json

import pytest

from lectern.storage.db import Library
from lectern.storage.settings import DEFAULTS, Settings


@pytest.fixture
def library(tmp_path):
    lib = Library(str(tmp_path / "test.sqlite3"))
    yield lib
    lib.close()


def test_remember_and_recent(library):
    library.remember_book("id1", "/pfad/a.epub", "Buch A", "Autor A", "epub")
    library.remember_book("id2", "/pfad/b.epub", "Buch B", "Autor B", "epub")
    recent = library.recent()
    assert [entry.ident for entry in recent] == ["id2", "id1"], "newest first"
    assert recent[0].title == "Buch B"

    # Re-opening the first book moves it back to the top without duplicating it.
    library.remember_book("id1", "/pfad/a.epub", "Buch A", "Autor A", "epub")
    assert [entry.ident for entry in library.recent()] == ["id1", "id2"]
    assert len(library.recent()) == 2


def test_position_and_percent(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    library.save_position("id1", 250, 1000)
    assert library.state("id1").position == 250
    assert library.recent()[0].percent == 25


def test_bookmarks_roundtrip(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    library.add_bookmark("id1", 500, "Mitte")
    first = library.add_bookmark("id1", 100, "Anfang")
    marks = library.bookmarks("id1")
    assert [m.position for m in marks] == [100, 500], "ordered by position"

    library.remove_bookmark(first.ident)
    assert [m.position for m in library.bookmarks("id1")] == [500]


def test_highlights_with_notes_and_colours(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    mark = library.add_highlight("id1", 10, 40, "yellow", "ein Zitat")
    library.update_highlight(mark.ident, colour="green", note="Wichtig")
    stored = library.highlights("id1")[0]
    assert (stored.colour, stored.note, stored.excerpt) == ("green", "Wichtig", "ein Zitat")

    library.remove_highlight(mark.ident)
    assert library.highlights("id1") == []


def test_forget_book_removes_its_annotations(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    library.add_bookmark("id1", 1, "x")
    library.add_highlight("id1", 1, 2, "blue", "y")
    library.forget_book("id1")
    assert library.recent() == []
    assert library.bookmarks("id1") == []
    assert library.highlights("id1") == []


def test_state_loads_everything_at_once(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    library.save_position("id1", 42, 100)
    library.add_bookmark("id1", 5, "b")
    library.add_highlight("id1", 6, 7, "pink", "h")
    state = library.state("id1")
    assert state.position == 42 and len(state.bookmarks) == 1 and len(state.highlights) == 1


def test_markdown_export(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    library.add_bookmark("id1", 5, "Kapitel 3")
    library.add_highlight("id1", 6, 7, "pink", "Ein Satz", "Meine Notiz")
    text = library.export_markdown("id1", "Mein Buch")
    assert "# Notes on Mein Buch" in text
    assert "Kapitel 3" in text
    assert "> Ein Satz" in text
    assert "Meine Notiz" in text


def test_markdown_export_when_empty(library):
    library.remember_book("id1", "/p/a.epub", "A", "", "epub")
    assert "No annotations" in library.export_markdown("id1", "Leer")


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
def test_settings_roundtrip(tmp_path):
    path = str(tmp_path / "settings.json")
    settings = Settings(path)
    settings["font_size"] = 21
    settings["theme"] = "dark"
    settings.save()

    assert Settings(path)["font_size"] == 21
    assert Settings(path)["theme"] == "dark"


def test_settings_ignore_unknown_and_coerce(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "font_size": "23",          # string that should coerce to int
        "line_height": 2,           # int that should coerce to float
        "justify": 0,               # falsy int for a bool
        "boesartig": {"x": 1},      # unknown key must be dropped
        "theme": 42,                # wrong type for a string
    }), encoding="utf-8")

    settings = Settings(str(path))
    assert settings["font_size"] == 23
    assert settings["line_height"] == 2.0
    assert settings["justify"] is False
    assert settings["theme"] == DEFAULTS["theme"], "bad value falls back to the default"
    assert "boesartig" not in settings.as_dict()


def test_settings_survive_a_corrupt_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ das ist kein JSON", encoding="utf-8")
    assert Settings(str(path))["font_size"] == DEFAULTS["font_size"]


def test_settings_reset(tmp_path):
    settings = Settings(str(tmp_path / "s.json"))
    settings["font_size"] = 40
    settings.reset()
    assert settings["font_size"] == DEFAULTS["font_size"]


def test_recent_order_survives_a_stalled_clock(library, monkeypatch):
    """Two books opened within one clock reading must still come out in order.

    This failed on GitHub's windows-11-arm runner: both books got the same
    ``last_opened``, and the list came back oldest first.
    """

    from lectern.storage import db

    monkeypatch.setattr(db, "_clock", lambda: 1_000_000.0)
    library.remember_book("id1", "/pfad/a.epub", "Buch A", "Autor A", "epub")
    library.remember_book("id2", "/pfad/b.epub", "Buch B", "Autor B", "epub")
    assert [entry.ident for entry in library.recent()] == ["id2", "id1"]


def test_recent_order_survives_a_clock_stepping_back(library, monkeypatch):
    """A clock corrected backwards must not push the book being read down."""

    from lectern.storage import db

    readings = iter([2_000_000.0, 1_500_000.0, 1_000_000.0])
    monkeypatch.setattr(db, "_clock", lambda: next(readings))
    library.remember_book("id1", "/pfad/a.epub", "Buch A", "Autor A", "epub")
    library.remember_book("id2", "/pfad/b.epub", "Buch B", "Autor B", "epub")
    library.save_position("id1", 5, 10)          # reading id1 again
    assert [entry.ident for entry in library.recent()] == ["id1", "id2"]


def test_data_dir_env_override(tmp_path, monkeypatch):
    from lectern.storage import paths

    target = tmp_path / "portable"
    monkeypatch.setenv("LECTERN_DATA_DIR", str(target))
    assert paths.data_dir() == str(target)
    assert target.is_dir(), "the directory must be created on demand"
