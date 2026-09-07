"""Exercise the HUFF/CDIC decoder against a purpose-built, format-valid table.

Real HUFF/CDIC books use Huffman codes of varying length that no free tool
generates, so the fixture below constructs the simplest table the format allows:
256 terminal eight-bit codes, one per byte value, each pointing at a one-byte
dictionary phrase.  With that table the encoded stream is byte-identical to the
plaintext, which lets the decoder's bit reader, table lookup and dictionary
indexing be checked exactly.  One entry is deliberately left marked as still
compressed so the recursive phrase path is covered too.
"""

from __future__ import annotations

import struct

import pytest

from openreader.formats.base import LoadError
from openreader.formats.mobi import HuffCdic


def build_huff() -> bytes:
    """A HUFF record whose 256 direct codes map byte ``b`` to dictionary slot ``b``.

    The decoder computes ``index = (maxcode - code) >> (32 - codelen)`` and
    stores ``maxcode`` as ``((raw + 1) << (32 - codelen)) - 1``.  Solving both
    for ``index == b`` at ``codelen == 8`` gives ``raw == 2 * b``.
    """

    dict1 = b"".join(
        struct.pack(">I", (2 * value << 8) | 0x80 | 8)   # raw=2b, terminal, codelen=8
        for value in range(256)
    )
    # All codes are terminal, so the min/max walk table is never consulted.
    dict2 = b"\0" * (64 * 4)

    off1 = 24
    off2 = off1 + len(dict1)
    header = b"HUFF" + struct.pack(">I", 0x18) + struct.pack(">II", off1, off2)
    header += b"\0" * (off1 - len(header))
    return header + dict1 + dict2


def build_cdic(phrases: dict[int, tuple[bytes, bool]]) -> bytes:
    """A CDIC record holding 256 phrases; ``phrases`` overrides individual slots.

    Each entry is ``(payload, already_decompressed)``.  An entry marked as not
    decompressed makes the decoder recurse into the payload.
    """

    count = 256
    entries = []
    for index in range(count):
        payload, done = phrases.get(index, (bytes([index]), True))
        entries.append((payload, done))

    # Offsets are counted from byte 16 of the record, right where the table
    # itself starts, so the payload area begins after the 2-byte-per-entry table.
    table_size = count * 2
    blobs = bytearray()
    offsets = []
    for payload, done in entries:
        offsets.append(table_size + len(blobs))
        flag = 0x8000 if done else 0x0000
        blobs += struct.pack(">H", len(payload) | flag) + payload

    header = b"CDIC" + struct.pack(">I", 0x10) + struct.pack(">II", count, 8)
    return header + b"".join(struct.pack(">H", off) for off in offsets) + bytes(blobs)


@pytest.fixture
def codec():
    return HuffCdic(build_huff(), [build_cdic({})])


def test_identity_table_roundtrip(codec):
    """With one byte per code the stream decodes back to itself."""

    for payload in (b"Hallo Welt", b"", bytes(range(256)), b"x" * 5000):
        assert codec.decompress(payload) == payload


def test_decoder_handles_non_ascii(codec):
    payload = "Über Straßen und Bäume".encode()
    assert codec.decompress(payload) == payload


def test_nested_phrase_is_decompressed_recursively():
    """A phrase flagged as still compressed must be decoded on first use."""

    # Slot 200 holds the encoded form of "ab" and is marked not-yet-decompressed.
    codec = HuffCdic(build_huff(), [build_cdic({200: (b"ab", False)})])
    assert codec.decompress(bytes([200])) == b"ab"
    # Second use comes from the cache, and must give the same answer.
    assert codec.decompress(bytes([200, 200])) == b"abab"


def test_nested_phrase_is_cached_after_first_expansion():
    codec = HuffCdic(build_huff(), [build_cdic({77: (b"xyz", False)})])
    codec.decompress(bytes([77]))
    blob, flag = codec.dictionary[77]
    assert (blob, bool(flag)) == (b"xyz", True), "the expansion must be memoised"


def test_multiple_cdic_records_extend_the_dictionary():
    """Books split the phrase dictionary across several CDIC records."""

    codec = HuffCdic(build_huff(), [build_cdic({}), build_cdic({})])
    # The second record finds the dictionary already full and adds nothing.
    assert len(codec.dictionary) == 256


def test_broken_headers_are_rejected():
    with pytest.raises(LoadError, match="HUFF"):
        HuffCdic(b"XXXX" + b"\0" * 2048, [])
    with pytest.raises(LoadError, match="CDIC"):
        HuffCdic(build_huff(), [b"XXXX" + b"\0" * 1024])


def test_corrupt_stream_stops_instead_of_looping():
    """A truncated or nonsensical stream must return, not spin or crash."""

    codec = HuffCdic(build_huff(), [build_cdic({})])
    assert codec.decompress(b"\xff" * 3) == b"\xff" * 3
    assert isinstance(codec.decompress(b"\x00"), bytes)


def test_mobi_selects_the_huff_decompressor():
    """Compression id 17480 must route through HUFF/CDIC, not PalmDOC."""

    from openreader.formats import mobi

    class FakeDB:
        count = 4

        def record(self, index):
            return {1: build_huff(), 2: build_cdic({})}.get(index, b"")

    decompress = mobi._make_decompressor(FakeDB(), 17480, 1, 2)
    assert decompress(b"Test") == b"Test"


def test_unknown_compression_is_reported():
    from openreader.formats import mobi

    class FakeDB:
        count = 1

        def record(self, index):
            return b""

    with pytest.raises(LoadError, match="Kompressionsverfahren"):
        mobi._make_decompressor(FakeDB(), 999, 0, 0)
