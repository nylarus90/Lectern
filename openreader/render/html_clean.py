"""Normalise book XHTML into the HTML subset Qt's rich text engine understands.

Qt's ``QTextDocument`` parses an HTML 4 / CSS 2.1 subset.  Feeding it raw EPUB 3
markup loses content silently: unknown elements such as ``<section>`` are treated
as inline, ``<figure>`` collapses, and SVG cover wrappers render as nothing at
all.  This module rewrites the markup so that nothing disappears, resolves every
resource reference to a key in :attr:`Book.resources`, and turns ``id``
attributes into the ``<a name=...>`` anchors that ``scrollToAnchor`` needs.
"""

from __future__ import annotations

import re
from html import escape, unescape
from html.parser import HTMLParser
from typing import Callable

#: HTML5 elements Qt does not know, mapped onto a block element it does know.
BLOCK_ALIASES = {
    "section": "div", "article": "div", "aside": "div", "nav": "div",
    "header": "div", "footer": "div", "main": "div", "figure": "div",
    "hgroup": "div", "details": "div", "dialog": "div", "template": "div",
    "figcaption": "p", "summary": "p",
}

#: Inline HTML5 elements mapped onto ``<span>``.
INLINE_ALIASES = {
    "mark": "span", "time": "span", "data": "span", "output": "span",
    "bdi": "span", "bdo": "span", "ruby": "span", "rb": "span", "abbr": "span",
}

#: Elements whose entire subtree is discarded.
DROP_SUBTREE = {
    "script", "style", "head", "title", "meta", "link", "base",
    "video", "audio", "source", "track", "canvas", "iframe", "object",
    "embed", "param", "form", "input", "button", "select", "textarea",
    "noscript", "rt", "rp",
}

VOID_TAGS = {"br", "hr", "img", "wbr", "col"}

#: Attributes kept per tag.  Everything else is dropped, which both avoids
#: confusing Qt and removes any scripting surface from untrusted book files.
ALLOWED_ATTRS = {
    "*": {"style", "class", "dir", "lang"},
    "a": {"href", "name", "title"},
    "img": {"src", "alt", "width", "height"},
    "table": {"border", "cellpadding", "cellspacing", "width", "align"},
    "td": {"colspan", "rowspan", "align", "valign", "width", "bgcolor"},
    "th": {"colspan", "rowspan", "align", "valign", "width", "bgcolor"},
    "tr": {"align", "valign", "bgcolor"},
    "ol": {"start", "type"},
    "ul": {"type"},
    "p": {"align"},
    "div": {"align"},
    "h1": {"align"}, "h2": {"align"}, "h3": {"align"},
    "h4": {"align"}, "h5": {"align"}, "h6": {"align"},
    "font": {"color", "size", "face"},
    "blockquote": {"align"},
}

_HIDDEN_RE = re.compile(r"display\s*:\s*none", re.I)
_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]")


def anchor_name(prefix: str, ident: str = "") -> str:
    """Build a document-unique anchor from a chapter prefix and an element id."""

    clean = _ID_SAFE_RE.sub("_", ident)
    return f"{prefix}__{clean}" if clean else prefix


class _Normalizer(HTMLParser):
    def __init__(
        self,
        anchor_prefix: str,
        resolve_href: Callable[[str], str],
        resolve_src: Callable[[str], str],
    ) -> None:
        # convert_charrefs gives us decoded text; we re-escape on output, which
        # normalises the many different entity spellings books use.
        super().__init__(convert_charrefs=True)
        self.prefix = anchor_prefix
        self.resolve_href = resolve_href
        self.resolve_src = resolve_src
        self.out: list[str] = []
        self.title = ""
        self._drop_depth = 0
        self._drop_tag = ""
        self._in_title = False
        self._open: list[str] = []
        self._svg_depth = 0

    # -- helpers ---------------------------------------------------------
    def _emit(self, text: str) -> None:
        if self._drop_depth == 0:
            self.out.append(text)

    def _attrs_for(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        allowed = ALLOWED_ATTRS.get("*", set()) | ALLOWED_ATTRS.get(tag, set())
        parts = []
        for key, value in attrs:
            key = key.lower()
            if key in allowed and value is not None:
                parts.append('%s="%s"' % (key, escape(value, quote=True)))
        return (" " + " ".join(parts)) if parts else ""

    # -- HTMLParser interface -------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        adict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "title":
            self._in_title = True
            return

        # An SVG wrapper around a raster image is the standard EPUB cover idiom.
        if tag == "svg":
            self._svg_depth += 1
            return
        if self._svg_depth and tag == "image":
            href = adict.get("xlink:href") or adict.get("href") or ""
            key = self.resolve_src(href)
            if key:
                self._emit('<img src="%s" />' % escape(key, quote=True))
            return

        if self._drop_depth:
            if tag == self._drop_tag:
                self._drop_depth += 1
            return

        if tag in DROP_SUBTREE:
            self._drop_depth = 1
            self._drop_tag = tag
            return

        # ``display:none`` is genuinely hidden content (alternate covers, notes
        # meant for other renderers).  Qt ignores the property, so we honour it.
        if _HIDDEN_RE.search(adict.get("style", "")):
            self._drop_depth = 1
            self._drop_tag = tag
            return

        if tag in ("html", "body"):
            return

        # Every id becomes a real anchor so internal links keep working.
        if adict.get("id"):
            name = escape(anchor_name(self.prefix, adict["id"]), quote=True)
            self._emit('<a name="%s"></a>' % name)

        if tag == "img":
            key = self.resolve_src(adict.get("src", ""))
            if not key:
                alt = adict.get("alt", "").strip()
                if alt:
                    self._emit('<p class="or-alttext">[%s]</p>' % escape(alt))
                return
            kept: list[tuple[str, str | None]] = [("src", key)]
            for keep in ("alt", "width", "height", "style", "class"):
                if adict.get(keep):
                    kept.append((keep, adict[keep]))
            self._emit("<img%s />" % self._attrs_for("img", kept))
            return

        if tag == "a":
            new: list[tuple[str, str | None]] = []
            if adict.get("href"):
                target = self.resolve_href(adict["href"])
                if target:
                    new.append(("href", target))
            if adict.get("name"):
                new.append(("name", anchor_name(self.prefix, adict["name"])))
            for keep in ("title", "class", "style"):
                if adict.get(keep):
                    new.append((keep, adict[keep]))
            self._open.append("a")
            self._emit("<a%s>" % self._attrs_for("a", new))
            return

        mapped = BLOCK_ALIASES.get(tag) or INLINE_ALIASES.get(tag) or tag
        cls = adict.get("class", "")
        if tag in BLOCK_ALIASES or tag in INLINE_ALIASES:
            cls = (cls + " or-" + tag).strip()
        rendered = [(k, v) for k, v in attrs if k.lower() != "class"]
        if cls:
            rendered.append(("class", cls))

        if tag in VOID_TAGS or mapped in VOID_TAGS:
            self._emit("<%s%s />" % (mapped, self._attrs_for(mapped, rendered)))
            return

        self._open.append(mapped)
        self._emit("<%s%s>" % (mapped, self._attrs_for(mapped, rendered)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in DROP_SUBTREE:
            return
        self.handle_starttag(tag, attrs)
        if lower == "svg":
            self._svg_depth = max(0, self._svg_depth - 1)
        elif lower not in VOID_TAGS and lower != "image":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            return
        if tag == "svg":
            self._svg_depth = max(0, self._svg_depth - 1)
            return
        if self._drop_depth:
            if tag == self._drop_tag:
                self._drop_depth -= 1
                if self._drop_depth == 0:
                    self._drop_tag = ""
            return
        if tag in ("html", "body", "image") or tag in VOID_TAGS:
            return

        mapped = BLOCK_ALIASES.get(tag) or INLINE_ALIASES.get(tag) or tag
        if mapped in self._open:
            # Close any tags the book left dangling, innermost first.
            while self._open:
                current = self._open.pop()
                self._emit("</%s>" % current)
                if current == mapped:
                    break

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        if self._svg_depth:
            return
        self._emit(escape(data, quote=False))

    def handle_comment(self, data: str) -> None:
        pass

    def close_all(self) -> None:
        while self._open:
            self.out.append("</%s>" % self._open.pop())


def normalize(
    html: str,
    *,
    anchor_prefix: str,
    resolve_href: Callable[[str], str] = lambda h: h,
    resolve_src: Callable[[str], str] = lambda s: s,
) -> tuple[str, str]:
    """Return ``(body_html, document_title)`` ready for ``QTextDocument``."""

    parser = _Normalizer(anchor_prefix, resolve_href, resolve_src)
    parser.feed(html)
    parser.close()
    parser.close_all()
    return "".join(parser.out), parser.title.strip()


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_tags(html: str) -> str:
    """Plain text of a fragment, used for TOC titles and search snippets."""

    return _WS_RE.sub(" ", unescape(_TAG_RE.sub(" ", html))).strip()
