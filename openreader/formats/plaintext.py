"""Plain text, Markdown, HTML and RTF loaders.

These share the same shape: read bytes, work out the encoding, produce one
chapter of HTML.  Markdown is handed to Qt, which renders CommonMark natively;
RTF gets a purpose-built converter for the subset that book files actually use.
"""

from __future__ import annotations

import os
import re
from html import escape
from typing import Callable

from ..render.html_clean import normalize, strip_tags
from .base import Book, BookKind, Chapter, LoadError, TocEntry, noop_progress

#: Tried in order; the first that decodes without loss and without obvious
#: mojibake wins.  Explicit BOMs short-circuit the whole list.
ENCODINGS = ("utf-8", "cp1252", "iso-8859-15", "cp1251", "utf-16")

BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


def detect_encoding(data: bytes) -> str:
    """Pick a text encoding without pulling in a detection dependency."""

    for bom, name in BOMS:
        if data.startswith(bom):
            return name
    for candidate in ENCODINGS:
        try:
            text = data.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
        # A stray replacement character or a high density of control characters
        # means we guessed wrong even though decoding technically succeeded.
        if "\ufffd" in text:
            continue
        controls = sum(1 for ch in text[:4000] if ord(ch) < 9 or 14 <= ord(ch) < 32)
        if controls > len(text[:4000]) * 0.02:
            continue
        return candidate
    return "utf-8"


def read_text(path: str) -> str:
    with open(path, "rb") as handle:
        data = handle.read()
    return data.decode(detect_encoding(data), "replace").replace("\r\n", "\n").replace("\r", "\n")


# --------------------------------------------------------------------------
# Plain text
# --------------------------------------------------------------------------
#: Lines that name a division outright, in the languages a reader is likely to
#: meet.  Matched case-insensitively and anywhere in a short line, because
#: "Erstes Kapitel" puts the keyword second.
_CHAPTER_WORD_RE = re.compile(
    r"\b(kapitel|chapter|teil|part|buch|book|abschnitt|prolog|epilog|"
    r"prologue|epilogue|vorwort|nachwort|anhang|appendix|inhalt)\b",
    re.I,
)
_SENTENCE_END = ".,;:!?…“„"


def looks_like_heading(block: str) -> bool:
    """Decide whether a paragraph of a plain text book is a heading.

    Plain text carries no structure, so this is necessarily a heuristic: a
    single short line, not ending like a sentence, that is either shouted in
    capitals or names a division explicitly.
    """

    line = block.strip()
    if not line or "\n" in line or len(line) > 70:
        return False
    if line[-1] in _SENTENCE_END:
        return False
    letters = [ch for ch in line if ch.isalpha()]
    if not letters:
        return False
    if all(ch.isupper() for ch in letters):
        return True
    if _CHAPTER_WORD_RE.search(line) and len(line.split()) <= 8:
        return True
    # A very short title-cased line with no lowercase-only first word.
    words = line.split()
    return len(words) <= 6 and all(w[:1].isupper() or not w[:1].isalpha() for w in words)


def load_txt(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(10, "Textdatei wird gelesen…")
    text = read_text(path)
    book = Book(path=path, kind=BookKind.TEXT)
    book.meta.title = os.path.splitext(os.path.basename(path))[0]

    blocks = re.split(r"\n[ \t]*\n", text)
    parts: list[str] = ['<a name="ch0"></a>']
    toc: list[TocEntry] = []
    for index, block in enumerate(blocks):
        stripped = block.strip()
        if not stripped:
            continue
        if looks_like_heading(stripped):
            name = "tx%d" % len(toc)
            parts.append('<a name="%s"></a><h2>%s</h2>' % (name, escape(stripped)))
            toc.append(TocEntry(stripped, "#" + name))
        else:
            # Single newlines inside a paragraph are hard wraps, not breaks.
            parts.append("<p>%s</p>" % escape(stripped).replace("\n", " "))
        if index % 200 == 0:
            progress(10 + int(80 * index / max(1, len(blocks))), "Absatz %d" % index)

    if toc:
        book.meta.title = toc[0].title if len(toc) > 1 else book.meta.title
    book.chapters = [Chapter(ident="ch0", title=book.meta.title, html="".join(parts))]
    book.toc = toc or [TocEntry(book.display_title, "#ch0")]
    progress(100, "Fertig")
    return book


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------
def load_markdown(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    """Render Markdown through Qt's own CommonMark parser."""

    from PySide6.QtGui import QTextDocument

    progress(10, "Markdown wird gelesen…")
    text = read_text(path)
    document = QTextDocument()
    document.setMarkdown(text, QTextDocument.MarkdownDialectCommonMark)
    html = document.toHtml()

    book = Book(path=path, kind=BookKind.TEXT)
    book.meta.title = os.path.splitext(os.path.basename(path))[0]
    return _finish_html_book(book, html, base_dir=os.path.dirname(path), progress=progress)


# --------------------------------------------------------------------------
# HTML / XHTML
# --------------------------------------------------------------------------
def load_html(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(10, "HTML wird gelesen…")
    text = read_text(path)
    book = Book(path=path, kind=BookKind.TEXT)
    book.meta.title = os.path.splitext(os.path.basename(path))[0]
    return _finish_html_book(book, text, base_dir=os.path.dirname(path), progress=progress)


_H_RE = re.compile(r"<h([1-3])\b[^>]*>(.*?)</h\1>", re.I | re.S)


def _finish_html_book(book: Book, html: str, *, base_dir: str, progress) -> Book:
    """Shared tail for HTML-ish sources: side-load images, build a TOC."""

    progress(40, "Bilder werden geladen…")

    def resolve_src(src: str) -> str:
        if not src or not base_dir or src.startswith(("http://", "https://", "data:")):
            return ""
        candidate = os.path.normpath(os.path.join(base_dir, src.split("#")[0]))
        # Never follow a book's relative path outside its own directory.
        if base_dir and not candidate.startswith(os.path.abspath(base_dir)):
            return ""
        if candidate in book.resources:
            return candidate
        try:
            with open(candidate, "rb") as handle:
                book.resources[candidate] = handle.read()
            return candidate
        except OSError:
            return ""

    # Anchor the headings first so the TOC has somewhere to point.
    parts: list[str] = []
    toc: list[TocEntry] = []
    last = 0
    for match in _H_RE.finditer(html):
        title = strip_tags(match.group(2))
        if not title:
            continue
        name = "hd%d" % len(toc)
        parts.append(html[last:match.start()])
        parts.append('<a name="%s"></a>' % name)
        last = match.start()
        toc.append(TocEntry(title, "#ch0__" + name))
    parts.append(html[last:])

    progress(70, "Text wird aufbereitet…")
    body, title = normalize(
        "".join(parts),
        anchor_prefix="ch0",
        resolve_href=lambda h: h if h.startswith(("http://", "https://", "mailto:")) else (
            "#ch0__" + h[1:] if h.startswith("#") else ""
        ),
        resolve_src=resolve_src,
    )
    if title:
        book.meta.title = title
    book.chapters = [Chapter(ident="ch0", title=book.meta.title,
                             html='<a name="ch0"></a>' + body)]
    book.toc = toc or [TocEntry(book.display_title, "#ch0")]
    if book.resources:
        book.cover = next(iter(book.resources.values()))
    progress(100, "Fertig")
    return book


# --------------------------------------------------------------------------
# RTF
# --------------------------------------------------------------------------
_RTF_TOKEN = re.compile(r"\\([a-zA-Z]+)(-?\d+)? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}]+)")

#: Control words whose entire group is metadata rather than body text.
_RTF_SKIP_GROUPS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header",
    "footer", "footnote", "xmlns", "themedata", "datastore", "generator",
    "listtable", "listoverridetable", "rsidtable", "mmathPr", "wgrffmtfilter",
}

_RTF_SPECIAL = {
    "par": "\n\n", "line": "\n", "tab": "\t", "emdash": "\u2014", "endash": "\u2013",
    "lquote": "\u2018", "rquote": "\u2019", "ldblquote": "\u201c", "rdblquote": "\u201d",
    "bullet": "\u2022", "~": "\u00a0", "-": "", "_": "\u2011",
}


def rtf_to_html(source: str) -> tuple[str, str, str]:
    """Convert an RTF document to ``(html, title, author)``.

    Handles the subset that matters for reading: groups, character escapes,
    code pages, unicode escapes, bold/italic/underline and paragraph breaks.
    Anything else is skipped rather than shown as control noise.
    """

    out: list[str] = []
    title = author = ""
    codepage = "cp1252"
    # Stack of (skip_this_group, formatting) so a group restores state on exit.
    stack: list[tuple[bool, dict]] = []
    state = {"b": False, "i": False, "ul": False}
    skip = False
    capture = ""
    captured: list[str] = []
    pending_unicode_skip = 0

    def flush_format(name: str, on: bool) -> None:
        tag = {"b": "b", "i": "i", "ul": "u"}[name]
        if on and not state[name]:
            out.append("<%s>" % tag)
        elif not on and state[name]:
            out.append("</%s>" % tag)
        state[name] = on

    def add_text(text: str) -> None:
        nonlocal pending_unicode_skip
        if pending_unicode_skip > 0:
            drop = min(pending_unicode_skip, len(text))
            pending_unicode_skip -= drop
            text = text[drop:]
        if not text:
            return
        if capture:
            captured.append(text)
        elif not skip:
            out.append(escape(text))

    for match in _RTF_TOKEN.finditer(source):
        word, param, hexval, escaped, brace, text = match.groups()

        if brace == "{":
            stack.append((skip, dict(state)))
            continue
        if brace == "}":
            if capture:
                value = "".join(captured).strip()
                if capture == "title":
                    title = value
                elif capture == "author":
                    author = value
                capture, captured = "", []
            if stack:
                skip, restored = stack.pop()
                for key in ("b", "i", "ul"):
                    if state[key] != restored[key]:
                        flush_format(key, restored[key])
            continue

        if hexval is not None:
            add_text(bytes([int(hexval, 16)]).decode(codepage, "replace"))
            continue
        if escaped is not None:
            add_text(_RTF_SPECIAL.get(escaped, escaped))
            continue
        if text is not None:
            add_text(text)
            continue

        # -- control word ------------------------------------------------
        value = int(param) if param else None
        if word in _RTF_SKIP_GROUPS:
            skip = True
            continue
        if word == "title":
            capture, captured = "title", []
            continue
        if word == "author":
            capture, captured = "author", []
            continue
        if word == "ansicpg" and value:
            codepage = "cp%d" % value
            continue
        if word == "u" and value is not None:
            add_text(chr(value if value >= 0 else value + 65536))
            pending_unicode_skip = 1  # \uc1 default: one fallback character
            continue
        if word == "uc" and value is not None:
            pending_unicode_skip = 0
            continue
        if word in _RTF_SPECIAL:
            add_text(_RTF_SPECIAL[word])
            continue
        if word in ("b", "i", "ul") and not skip:
            flush_format(word, value != 0)
            continue
        if word == "ulnone" and not skip:
            flush_format("ul", False)
            continue
        if word in ("pard", "plain") and not skip:
            for key in ("b", "i", "ul"):
                flush_format(key, False)
            continue

    for key in ("b", "i", "ul"):
        if state[key]:
            out.append("</%s>" % {"b": "b", "i": "i", "ul": "u"}[key])

    body = "".join(out)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body)]
    rendered = []
    for paragraph in paragraphs:
        if not paragraph or paragraph in ("<b></b>", "<i></i>", "<u></u>"):
            continue
        # RTF has no heading concept; a short paragraph that is entirely bold is
        # how authoring tools express one, so treat it as such.
        bold = re.fullmatch(r"<b>(.{1,70}?)</b>", paragraph, re.S)
        if bold and "\n" not in bold.group(1):
            rendered.append("<h2>%s</h2>" % bold.group(1))
        else:
            rendered.append("<p>%s</p>" % paragraph.replace("\n", "<br />"))
    return "".join(rendered), title, author


def load_rtf(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(10, "RTF wird gelesen…")
    source = read_text(path)
    if not source.lstrip().startswith("{\\rtf"):
        raise LoadError("Die Datei beginnt nicht mit einer RTF-Signatur.")
    html, title, author = rtf_to_html(source)
    if not strip_tags(html):
        raise LoadError("Aus der RTF-Datei konnte kein Text gewonnen werden.")

    book = Book(path=path, kind=BookKind.TEXT)
    book.meta.title = title or os.path.splitext(os.path.basename(path))[0]
    if author:
        book.meta.authors = [author]
    progress(60, "Text wird aufbereitet…")
    return _finish_html_book(book, html, base_dir="", progress=progress)
