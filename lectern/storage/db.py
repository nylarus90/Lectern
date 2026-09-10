"""Reading state: recent books, positions, bookmarks and highlights.

Positions are character offsets into the assembled document.  Because the
document is built deterministically from the file, the same book always yields
the same offsets, so a note keeps pointing at the same words across sessions.

Every annotation also stores the text it covered.  That excerpt is what the
annotation list displays and what the Markdown export contains; it is not yet
used to re-find an anchor should a change to the loaders shift the offsets.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

from ..i18n import tr
from .paths import database_path, secure_file

SCHEMA_VERSION = 1

#: The wall clock, through a name of its own so tests can stop or rewind it
#: without bending ``time.time`` for the whole process.
_clock = time.time


SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id           TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    authors      TEXT NOT NULL DEFAULT '',
    format       TEXT NOT NULL DEFAULT '',
    added        REAL NOT NULL,
    last_opened  REAL NOT NULL,
    position     INTEGER NOT NULL DEFAULT 0,
    total        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bookmarks (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id  TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    label    TEXT NOT NULL DEFAULT '',
    created  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS highlights (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id  TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    start    INTEGER NOT NULL,
    end      INTEGER NOT NULL,
    colour   TEXT NOT NULL DEFAULT 'yellow',
    excerpt  TEXT NOT NULL DEFAULT '',
    note     TEXT NOT NULL DEFAULT '',
    created  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookmarks_book ON bookmarks(book_id, position);
CREATE INDEX IF NOT EXISTS idx_highlights_book ON highlights(book_id, start);
"""


@dataclass
class Bookmark:
    ident: int
    position: int
    label: str
    created: float


@dataclass
class Highlight:
    ident: int
    start: int
    end: int
    colour: str
    excerpt: str
    note: str
    created: float


@dataclass
class RecentBook:
    ident: str
    path: str
    title: str
    authors: str
    format: str
    last_opened: float
    position: int
    total: int

    @property
    def percent(self) -> int:
        return int(100 * self.position / self.total) if self.total else 0


@dataclass
class BookState:
    """Everything stored about one book, loaded in a single round trip."""

    position: int = 0
    total: int = 0
    bookmarks: list[Bookmark] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)


class Library:
    """Thin SQLite wrapper; one instance lives for the life of the app."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or database_path()
        #: Set once a write has failed, so the window can say so exactly once
        #: instead of losing the reading position without a word.
        self.degraded = False
        # A second instance — portable and installed side by side — shares this
        # file.  Without a timeout the loser of a race raises immediately.
        self.connection = sqlite3.connect(self.path, timeout=5.0)
        secure_file(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(SCHEMA)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    # -- books -----------------------------------------------------------
    def _stamp(self) -> float:
        """A last-opened value later than every one already stored.

        Recency is an order, not a clock reading. On a virtual machine the
        system clock can hand out the same value twice or step back while it
        is being synchronised, and ``recent()`` sorts by nothing else: on
        GitHub's ARM runner two books opened back to back came out in the
        wrong order. The larger of the clock and the newest stored stamp plus
        a microsecond keeps the order strict whatever the clock does.
        """

        row = self.connection.execute("SELECT MAX(last_opened) FROM books").fetchone()
        newest = row[0] if row is not None and row[0] is not None else 0.0
        return max(_clock(), newest + 1e-6)

    def remember_book(self, ident: str, path: str, title: str, authors: str, fmt: str) -> None:
        now = self._stamp()
        self.connection.execute(
            """INSERT INTO books(id, path, title, authors, format, added, last_opened)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                    path = excluded.path,
                    title = excluded.title,
                    authors = excluded.authors,
                    format = excluded.format,
                    last_opened = excluded.last_opened""",
            (ident, path, title, authors, fmt, now, now),
        )
        self.connection.commit()

    def recent(self, limit: int = 20) -> list[RecentBook]:
        rows = self.connection.execute(
            "SELECT * FROM books ORDER BY last_opened DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            RecentBook(r["id"], r["path"], r["title"], r["authors"], r["format"],
                       r["last_opened"], r["position"], r["total"])
            for r in rows
        ]

    def forget_book(self, ident: str) -> None:
        self.connection.execute("DELETE FROM highlights WHERE book_id = ?", (ident,))
        self.connection.execute("DELETE FROM bookmarks WHERE book_id = ?", (ident,))
        self.connection.execute("DELETE FROM books WHERE id = ?", (ident,))
        self.connection.commit()

    def clear_recent(self) -> None:
        self.connection.execute("DELETE FROM highlights")
        self.connection.execute("DELETE FROM bookmarks")
        self.connection.execute("DELETE FROM books")
        self.connection.commit()

    # -- reading position -------------------------------------------------
    def save_position(self, ident: str, position: int, total: int) -> bool:
        """Store the reading position; ``False`` means it could not be saved.

        This runs on a timer, so a locked or read-only database used to raise
        from inside Qt's event loop, where the traceback went to a console the
        windowed build does not have.  The reader silently stopped remembering
        where you were.
        """

        try:
            self.connection.execute(
                "UPDATE books SET position = ?, total = ?, last_opened = ? WHERE id = ?",
                (int(position), int(total), self._stamp(), ident),
            )
            self.connection.commit()
        except sqlite3.Error:
            self.degraded = True
            return False
        return True

    def state(self, ident: str) -> BookState:
        row = self.connection.execute(
            "SELECT position, total FROM books WHERE id = ?", (ident,)
        ).fetchone()
        state = BookState(position=row["position"] if row else 0,
                          total=row["total"] if row else 0)
        state.bookmarks = self.bookmarks(ident)
        state.highlights = self.highlights(ident)
        return state

    # -- bookmarks --------------------------------------------------------
    def add_bookmark(self, ident: str, position: int, label: str) -> Bookmark:
        now = time.time()
        cursor = self.connection.execute(
            "INSERT INTO bookmarks(book_id, position, label, created) VALUES (?, ?, ?, ?)",
            (ident, int(position), label, now),
        )
        self.connection.commit()
        return Bookmark(int(cursor.lastrowid or 0), int(position), label, now)

    def bookmarks(self, ident: str) -> list[Bookmark]:
        rows = self.connection.execute(
            "SELECT * FROM bookmarks WHERE book_id = ? ORDER BY position", (ident,)
        ).fetchall()
        return [Bookmark(r["id"], r["position"], r["label"], r["created"]) for r in rows]

    def remove_bookmark(self, bookmark_id: int) -> None:
        self.connection.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
        self.connection.commit()

    # -- highlights -------------------------------------------------------
    def add_highlight(
        self, ident: str, start: int, end: int, colour: str, excerpt: str, note: str = ""
    ) -> Highlight:
        now = time.time()
        cursor = self.connection.execute(
            """INSERT INTO highlights(book_id, start, end, colour, excerpt, note, created)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ident, int(start), int(end), colour, excerpt[:2000], note, now),
        )
        self.connection.commit()
        return Highlight(int(cursor.lastrowid or 0), int(start), int(end),
                         colour, excerpt, note, now)

    def highlights(self, ident: str) -> list[Highlight]:
        rows = self.connection.execute(
            "SELECT * FROM highlights WHERE book_id = ? ORDER BY start", (ident,)
        ).fetchall()
        return [
            Highlight(r["id"], r["start"], r["end"], r["colour"],
                      r["excerpt"], r["note"], r["created"])
            for r in rows
        ]

    def update_highlight(self, highlight_id: int, *, colour: str | None = None,
                         note: str | None = None) -> None:
        if colour is not None:
            self.connection.execute(
                "UPDATE highlights SET colour = ? WHERE id = ?", (colour, highlight_id)
            )
        if note is not None:
            self.connection.execute(
                "UPDATE highlights SET note = ? WHERE id = ?", (note, highlight_id)
            )
        self.connection.commit()

    def remove_highlight(self, highlight_id: int) -> None:
        self.connection.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
        self.connection.commit()

    # -- export -----------------------------------------------------------
    def export_markdown(self, ident: str, title: str) -> str:
        """Render one book's annotations as Markdown for sharing or archiving."""

        lines = [tr("# Notes on %s") % title, ""]
        bookmarks = self.bookmarks(ident)
        if bookmarks:
            lines.append(tr("## Bookmarks"))
            lines.append("")
            for mark in bookmarks:
                lines.append("- %s (Position %d)" % (mark.label or tr("Bookmark"), mark.position))
            lines.append("")

        marks = self.highlights(ident)
        if marks:
            lines.append(tr("## Highlights"))
            lines.append("")
            for mark in marks:
                stamp = time.strftime("%d.%m.%Y", time.localtime(mark.created))
                lines.append("### %s — %s" % (stamp, mark.colour))
                lines.append("")
                lines.append("> " + mark.excerpt.replace("\n", "\n> "))
                if mark.note:
                    lines.append("")
                    lines.append(mark.note)
                lines.append("")
        if not bookmarks and not marks:
            lines.append(tr("_No annotations yet._"))
        return "\n".join(lines)
