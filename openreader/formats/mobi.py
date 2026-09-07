"""Kindle format loader: MOBI, PRC, AZW (KF7) and AZW3 (KF8).

All of them are PalmDB containers.  Record 0 holds a PalmDOC header followed by
a MOBI header and optionally an EXTH metadata block; the records after it hold
the book text, compressed with either PalmDOC LZ77 or the HUFF/CDIC scheme, and
after those come the images.

Header field offsets below are given relative to the ``MOBI`` magic, which sits
16 bytes into record 0 (after the PalmDOC header).
"""

from __future__ import annotations

import re
import struct
from typing import Callable

from ..render.html_clean import anchor_name, normalize, strip_tags
from .base import Book, BookKind, Chapter, DRMError, LoadError, Metadata, TocEntry, noop_progress

# -- MOBI header offsets ----------------------------------------------------
OFF_ENCODING = 0x0C
OFF_VERSION = 0x14
OFF_FULLNAME_OFF = 0x44
OFF_FULLNAME_LEN = 0x48
OFF_FIRST_RESOURCE = 0x5C
OFF_HUFF_OFF = 0x60
OFF_HUFF_COUNT = 0x64
OFF_EXTH_FLAGS = 0x70
OFF_EXTRA_FLAGS = 0xF2

# -- EXTH record types ------------------------------------------------------
EXTH_AUTHOR = 100
EXTH_PUBLISHER = 101
EXTH_DESCRIPTION = 103
EXTH_ISBN = 104
EXTH_SUBJECT = 105
EXTH_DATE = 106
EXTH_UPDATED_TITLE = 503
EXTH_LANGUAGE = 524
EXTH_COVER_OFFSET = 201
EXTH_KF8_BOUNDARY = 121

CODEPAGES = {1252: "cp1252", 65001: "utf-8"}

#: Kindle's own base32 alphabet, used inside ``kindle:embed:`` URIs.
_B32 = "0123456789ABCDEFGHIJKLMNOPQRSTUV"


class PalmDB:
    """Minimal PalmDB reader giving indexed access to the raw records."""

    def __init__(self, data: bytes) -> None:
        if len(data) < 78:
            raise LoadError("Die Datei ist zu klein für ein Kindle-Buch.")
        self.data = data
        self.type = data[60:64]
        self.creator = data[64:68]
        count = struct.unpack_from(">H", data, 76)[0]
        if count == 0:
            raise LoadError("Das Kindle-Archiv enthält keine Datensätze.")
        offsets = []
        for index in range(count):
            base = 78 + index * 8
            if base + 4 > len(data):
                raise LoadError("Die Datensatz-Tabelle ist beschädigt.")
            offsets.append(struct.unpack_from(">I", data, base)[0])
        offsets.append(len(data))
        self._bounds = offsets
        self.count = count

    def record(self, index: int) -> bytes:
        if not 0 <= index < self.count:
            return b""
        start, end = self._bounds[index], self._bounds[index + 1]
        if start > len(self.data):
            return b""
        return self.data[start:min(end, len(self.data))]


class ShiftedDB:
    """A view onto a PalmDB whose record 0 sits at ``offset``.

    Joint MOBI6+KF8 files store both halves in one container; the KF8 half is a
    complete book that simply starts at a later record.  Shifting the accessor
    lets the whole loader run against it unchanged.
    """

    def __init__(self, base: PalmDB, offset: int) -> None:
        self.data = base.data
        self.type = base.type
        self.creator = base.creator
        self._base = base
        self._offset = offset
        self.count = max(0, base.count - offset)

    def record(self, index: int) -> bytes:
        if not 0 <= index < self.count:
            return b""
        return self._base.record(self._offset + index)


# --------------------------------------------------------------------------
# Decompression
# --------------------------------------------------------------------------
def palmdoc_decompress(data: bytes) -> bytes:
    """PalmDOC LZ77 (compression type 2)."""

    out = bytearray()
    index = 0
    size = len(data)
    while index < size:
        byte = data[index]
        index += 1
        if byte == 0x00:
            out.append(0)
        elif byte <= 0x08:
            # Literal run of 1..8 bytes, used to escape otherwise special values.
            out += data[index:index + byte]
            index += byte
        elif byte <= 0x7F:
            out.append(byte)
        elif byte <= 0xBF:
            # 14-bit back-reference: 11 bits distance, 3 bits length.
            if index >= size:
                break
            pair = ((byte << 8) | data[index]) & 0x3FFF
            index += 1
            distance = pair >> 3
            length = (pair & 0x07) + 3
            if distance == 0 or distance > len(out):
                break
            for _ in range(length):
                out.append(out[-distance])
        else:
            # A space plus the low seven bits of the byte.
            out.append(0x20)
            out.append(byte ^ 0x80)
    return bytes(out)


class HuffCdic:
    """Decoder for the HUFF/CDIC scheme (compression type 17480).

    ``HUFF`` holds two tables: a 256-entry direct lookup for short codes and a
    32-entry min/max table used to walk longer codes bit by bit.  Each ``CDIC``
    record contributes a slice of the phrase dictionary; phrases may themselves
    be compressed, which is why :meth:`_decode` recurses.
    """

    def __init__(self, huff: bytes, cdics: list[bytes]) -> None:
        if huff[0:4] != b"HUFF":
            raise LoadError("Der HUFF-Datensatz des Buches ist beschädigt.")
        off1, off2 = struct.unpack_from(">LL", huff, 8)

        self.dict1: list[tuple[int, int, int]] = []
        for value in struct.unpack_from(">256L", huff, off1):
            codelen = value & 0x1F
            terminal = value & 0x80
            maxcode = value >> 8
            if codelen == 0:
                raise LoadError("Ungültige HUFF-Tabelle im Buch.")
            self.dict1.append((codelen, terminal, ((maxcode + 1) << (32 - codelen)) - 1))

        dict2 = struct.unpack_from(">64L", huff, off2)
        self.mincode = [code << (32 - length) for length, code in enumerate(dict2[0::2])]
        self.maxcode = [((code + 1) << (32 - length)) - 1
                        for length, code in enumerate(dict2[1::2])]

        self.dictionary: list[tuple[bytes, int] | None] = []
        for cdic in cdics:
            self._load_cdic(cdic)

    def _load_cdic(self, cdic: bytes) -> None:
        if cdic[0:4] != b"CDIC":
            raise LoadError("Ein CDIC-Datensatz des Buches ist beschädigt.")
        phrases, bits = struct.unpack_from(">LL", cdic, 8)
        count = min(1 << bits, max(0, phrases - len(self.dictionary)))
        if count == 0:
            return
        for offset in struct.unpack_from(">%dH" % count, cdic, 16):
            length = struct.unpack_from(">H", cdic, 16 + offset)[0]
            blob = cdic[18 + offset:18 + offset + (length & 0x7FFF)]
            self.dictionary.append((blob, length & 0x8000))

    def decompress(self, data: bytes) -> bytes:
        return self._decode(data, 0)

    def _decode(self, data: bytes, depth: int) -> bytes:
        if depth > 32:
            raise LoadError("Die Kompression des Buches ist beschädigt (Rekursion).")
        out = bytearray()
        bitsleft = len(data) * 8
        data = data + b"\0" * 8
        pos = 0
        value = struct.unpack_from(">Q", data, pos)[0]
        available = 32
        while True:
            if available <= 0:
                pos += 4
                if pos + 8 > len(data):
                    break
                value = struct.unpack_from(">Q", data, pos)[0]
                available += 32
            code = (value >> available) & 0xFFFFFFFF
            codelen, terminal, maxcode = self.dict1[code >> 24]
            if not terminal:
                while codelen < len(self.mincode) and code < self.mincode[codelen]:
                    codelen += 1
                if codelen >= len(self.maxcode):
                    break
                maxcode = self.maxcode[codelen]
            available -= codelen
            bitsleft -= codelen
            if bitsleft < 0:
                break
            index = (maxcode - code) >> (32 - codelen)
            if not 0 <= index < len(self.dictionary):
                break
            entry = self.dictionary[index]
            if entry is None:  # self-referential phrase in a corrupt file
                break
            blob, flag = entry
            if not flag:
                self.dictionary[index] = None
                blob = self._decode(blob, depth + 1)
                self.dictionary[index] = (blob, 1)
            out += blob
        return bytes(out)


# --------------------------------------------------------------------------
# Header helpers
# --------------------------------------------------------------------------
def _parse_exth(record0: bytes, start: int) -> dict[int, list[bytes]]:
    result: dict[int, list[bytes]] = {}
    if record0[start:start + 4] != b"EXTH":
        return result
    length, count = struct.unpack_from(">II", record0, start + 4)
    pos = start + 12
    limit = min(start + length, len(record0))
    for _ in range(count):
        if pos + 8 > limit:
            break
        tag, size = struct.unpack_from(">II", record0, pos)
        if size < 8:
            break
        result.setdefault(tag, []).append(record0[pos + 8:pos + size])
        pos += size
    return result


def _text(values: list[bytes] | None, encoding: str) -> str:
    return values[0].decode(encoding, "replace").strip() if values else ""


def _is_image(blob: bytes) -> bool:
    return (
        blob[:4] in (b"\x89PNG", b"GIF8")
        or blob[:2] == b"\xff\xd8"
        or (blob[:4] == b"RIFF" and blob[8:12] == b"WEBP")
    )


def _b32_value(token: str) -> int:
    total = 0
    for char in token.upper():
        if char not in _B32:
            return -1
        total = total * 32 + _B32.index(char)
    return total


def _trailing_size(chunk: bytes) -> int:
    """Decode the backwards variable-width integer at the end of a text record."""

    total = 0
    for offset in range(1, min(4, len(chunk)) + 1):
        byte = chunk[-offset]
        total |= (byte & 0x7F) << (7 * (offset - 1))
        if byte & 0x80:
            return total
    return 0


def _strip_trailing_entries(chunk: bytes, extra_flags: int) -> bytes:
    """Remove the trailing metadata entries appended to every text record.

    Each set bit above bit 0 means one backwards-encoded length field; bit 0
    means a trailing multibyte-character overlap of up to three bytes.
    """

    for bit in range(1, 16):
        if extra_flags & (1 << bit):
            size = _trailing_size(chunk)
            if 0 < size <= len(chunk):
                chunk = chunk[:len(chunk) - size]
    if extra_flags & 1 and chunk:
        chunk = chunk[:len(chunk) - ((chunk[-1] & 0x03) + 1)]
    return chunk


def _make_decompressor(db, compression: int, huff_offset: int, huff_count: int):
    if compression == 1:
        return lambda chunk: chunk
    if compression == 2:
        return palmdoc_decompress
    if compression == 17480:
        if not huff_offset or huff_offset >= db.count:
            raise LoadError("Das Buch nutzt HUFF/CDIC, aber die Tabelle fehlt.")
        cdics = [db.record(huff_offset + i) for i in range(1, max(1, huff_count))]
        return HuffCdic(db.record(huff_offset), cdics).decompress
    raise LoadError("Unbekanntes Kompressionsverfahren (%d) in der Kindle-Datei." % compression)


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------
_FILEPOS_RE = re.compile(r'filepos=["\']?(\d+)["\']?', re.I)
_FILEPOS_BYTES_RE = re.compile(rb'filepos=["\']?(\d+)["\']?', re.I)
_RECINDEX_RE = re.compile(r'<img([^>]*?)recindex=["\']?(\d+)["\']?([^>]*?)/?>', re.I)
_EMBED_RE = re.compile(r'kindle:embed:([0-9A-Va-v]+)(?:\?[^"\'\s>]*)?')
_HEADING_RE = re.compile(r"<h([1-3])\b[^>]*>(.*?)</h\1>", re.I | re.S)
_PAGEBREAK_RE = re.compile(rb"<\s*mbp:pagebreak[^>]*>", re.I)


def load(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(2, "Kindle-Datei wird gelesen…")
    with open(path, "rb") as handle:
        raw = handle.read()

    db = PalmDB(raw)
    if db.type + db.creator not in (b"BOOKMOBI", b"TEXtREAd"):
        raise LoadError("Das ist keine MOBI-/AZW-Datei (falsche PalmDB-Signatur).")
    return _load_container(path, db, progress, allow_boundary=True)


def _load_container(path: str, db, progress, *, allow_boundary: bool) -> Book:
    record0 = db.record(0)
    if len(record0) < 16:
        raise LoadError("Der Kopfdatensatz des Buches ist unvollständig.")

    compression, _pad, text_length, text_records, _record_size, encryption = \
        struct.unpack_from(">HHIHHH", record0, 0)
    if encryption not in (0,):
        raise DRMError(
            "Diese Kindle-Datei ist DRM-geschützt und kann nicht geöffnet werden."
        )

    book = Book(path=path, kind=BookKind.TEXT)
    meta = Metadata()

    has_mobi = record0[16:20] == b"MOBI"
    encoding = "cp1252"
    first_resource = file_version = huff_offset = huff_count = extra_flags = 0
    exth: dict[int, list[bytes]] = {}

    if has_mobi:
        header = record0[16:]
        header_length = struct.unpack_from(">I", header, 4)[0]
        encoding = CODEPAGES.get(struct.unpack_from(">I", header, OFF_ENCODING)[0], "cp1252")
        file_version = struct.unpack_from(">I", header, OFF_VERSION)[0]

        def field(offset: int) -> int:
            return (struct.unpack_from(">I", header, offset)[0]
                    if len(header) >= offset + 4 else 0)

        first_resource = field(OFF_FIRST_RESOURCE)
        huff_offset = field(OFF_HUFF_OFF)
        huff_count = field(OFF_HUFF_COUNT)
        if header_length >= OFF_EXTRA_FLAGS + 2 and len(header) >= OFF_EXTRA_FLAGS + 2:
            extra_flags = struct.unpack_from(">H", header, OFF_EXTRA_FLAGS)[0]

        name_off, name_len = field(OFF_FULLNAME_OFF), field(OFF_FULLNAME_LEN)
        if 0 < name_len < 4096 and name_off + name_len <= len(record0):
            meta.title = record0[name_off:name_off + name_len].decode(encoding, "replace")

        if field(OFF_EXTH_FLAGS) & 0x40:
            exth = _parse_exth(record0, 16 + header_length)

    # A joint MOBI6+KF8 file carries the modern half after a boundary record.
    if allow_boundary and file_version < 8:
        boundary = exth.get(EXTH_KF8_BOUNDARY)
        if boundary and len(boundary[0]) >= 4:
            index = struct.unpack_from(">I", boundary[0])[0]
            if 0 < index < db.count:
                inner = _load_container(
                    path, ShiftedDB(db, index), progress, allow_boundary=False
                )
                inner.warnings.append("Kombinierte MOBI/KF8-Datei: KF8-Teil gelesen.")
                return inner

    # -- metadata --------------------------------------------------------
    for value in exth.get(EXTH_AUTHOR, []):
        author = value.decode(encoding, "replace").strip()
        if author:
            meta.authors.append(author)
    meta.publisher = _text(exth.get(EXTH_PUBLISHER), encoding)
    meta.description = strip_tags(_text(exth.get(EXTH_DESCRIPTION), encoding))
    meta.identifier = _text(exth.get(EXTH_ISBN), encoding)
    meta.date = _text(exth.get(EXTH_DATE), encoding)
    meta.language = _text(exth.get(EXTH_LANGUAGE), encoding)
    meta.subjects = [v.decode(encoding, "replace").strip() for v in exth.get(EXTH_SUBJECT, [])]
    updated = _text(exth.get(EXTH_UPDATED_TITLE), encoding)
    if updated:
        meta.title = updated
    book.meta = meta

    # -- text ------------------------------------------------------------
    progress(20, "Text wird entpackt…")
    decompress = _make_decompressor(db, compression, huff_offset, huff_count)
    pieces = []
    for index in range(1, min(text_records, db.count - 1) + 1):
        pieces.append(decompress(_strip_trailing_entries(db.record(index), extra_flags)))
    text = b"".join(pieces)
    if text_length:
        text = text[:text_length]
    if not text.strip():
        raise LoadError("Im Buch wurde kein lesbarer Text gefunden.")

    # -- resources -------------------------------------------------------
    progress(60, "Bilder werden gelesen…")
    image_records: dict[int, str] = {}
    if first_resource and first_resource < db.count:
        for offset in range(db.count - first_resource):
            blob = db.record(first_resource + offset)
            if _is_image(blob):
                key = "image_%04d" % (offset + 1)
                book.resources[key] = blob
                image_records[offset + 1] = key

    cover = exth.get(EXTH_COVER_OFFSET)
    if cover and len(cover[0]) >= 4:
        index = struct.unpack_from(">I", cover[0])[0] + 1
        book.cover = book.resources.get(image_records.get(index, ""))
    if book.cover is None and image_records:
        book.cover = book.resources[image_records[min(image_records)]]

    progress(75, "Text wird aufbereitet…")
    _build_document(book, text, encoding, image_records, is_kf8=file_version >= 8)
    progress(100, "Fertig")
    return book


def _build_document(
    book: Book,
    text: bytes,
    encoding: str,
    image_records: dict[int, str],
    *,
    is_kf8: bool,
) -> None:
    """Turn the raw book markup into one chapter plus a heading-derived TOC."""

    text = _PAGEBREAK_RE.sub(b'<div class="or-pagebreak"></div>', text)

    # ``filepos`` targets are byte offsets into this very buffer, so the anchors
    # must be injected before decoding, and from the back so offsets stay valid.
    targets = sorted({int(m.group(1)) for m in _FILEPOS_BYTES_RE.finditer(text)}, reverse=True)
    for offset in targets:
        if 0 <= offset <= len(text):
            text = text[:offset] + (b'<a name="fp%d"></a>' % offset) + text[offset:]

    html = text.decode(encoding, "replace")
    html = _FILEPOS_RE.sub(lambda m: 'href="#fp%d"' % int(m.group(1)), html)

    if is_kf8:
        # Flow 0 is the book itself; the CSS and SVG flows follow </html>.
        end = html.lower().rfind("</html>")
        if end > 0:
            html = html[:end + len("</html>")]
        html = _EMBED_RE.sub(
            lambda m: image_records.get(_b32_value(m.group(1)), "orphan-resource"), html
        )
    else:
        html = _RECINDEX_RE.sub(
            lambda m: (
                '<img%ssrc="%s"%s>' % (m.group(1), image_records[int(m.group(2))], m.group(3))
                if int(m.group(2)) in image_records else ""
            ),
            html,
        )

    # Insert an anchor before each heading so the generated TOC can jump to it.
    toc: list[TocEntry] = []
    parts: list[str] = []
    last = 0
    for number, match in enumerate(_HEADING_RE.finditer(html)):
        title = strip_tags(match.group(2))
        if not title:
            continue
        name = "hd%d" % number
        parts.append(html[last:match.start()])
        parts.append('<a name="%s"></a>' % name)
        last = match.start()
        # The normaliser namespaces every anchor with the chapter prefix, so the
        # TOC target has to use the same namespaced form.
        toc.append(TocEntry(title, "#" + anchor_name("ch0", name)))
    parts.append(html[last:])
    html = "".join(parts)

    def resolve_href(href: str) -> str:
        if href.startswith(("http://", "https://", "mailto:")):
            return href
        if href.startswith("#"):
            return "#" + anchor_name("ch0", href[1:])
        return ""

    body, doc_title = normalize(
        html,
        anchor_prefix="ch0",
        resolve_href=resolve_href,
        resolve_src=lambda s: s if s in book.resources else "",
    )
    if not book.meta.title:
        book.meta.title = doc_title

    book.chapters = [Chapter(ident="ch0", title=book.meta.title, html=body)]
    book.toc = toc or [TocEntry(book.display_title, "#ch0")]
