import struct

import pytest

from lectern.formats import mobi
from lectern.formats.base import DRMError, LoadError

from . import make_samples


@pytest.fixture(scope="module")
def book():
    return mobi.load(make_samples.make_mobi())


def test_metadata_from_header_and_exth(book):
    assert book.meta.title == "Des Kaisers neue Kleider (MOBI)"
    assert book.meta.authors == ["Hans Christian Andersen"]
    assert book.meta.publisher == "OpenReader"


def test_text_roundtrips_utf8(book):
    html = book.chapters[0].html
    assert "über alles liebte" in html, "UTF-8 text must survive decompression"
    assert "Betrüger" in html


def test_recindex_images_are_resolved(book):
    assert "image_0001" in book.resources
    assert 'src="image_0001"' in book.chapters[0].html
    assert book.cover is not None and book.cover.startswith(b"\x89PNG")


def test_toc_is_derived_from_headings(book):
    assert [e.title for e in book.toc] == ["Erstes Kapitel", "Zweites Kapitel"]
    # Targets must use the same namespaced anchors the normaliser emits.
    for entry in book.toc:
        assert entry.target.startswith("#ch0__")
        assert 'name="%s"' % entry.target[1:] in book.chapters[0].html


def test_palmdoc_roundtrip_including_backreferences():
    original = b"abc abc abc abc " * 40 + bytes(range(0x80, 0x100))
    # Literal-only compression is what the sample builder emits.
    assert mobi.palmdoc_decompress(make_samples._palmdoc_compress(original)) == original


def test_palmdoc_decodes_backreferences_and_space_pairs():
    # 0x80..0xBF is an 11-bit distance / 3-bit length back-reference.
    seed = b"hallo"
    pair = (5 << 3) | (3 - 3)          # distance 5, length 3
    encoded = seed + bytes([0x80 | (pair >> 8), pair & 0xFF])
    assert mobi.palmdoc_decompress(encoded) == b"hallohal"
    # 0xC0..0xFF expands to a space plus the byte with bit 7 cleared.
    assert mobi.palmdoc_decompress(bytes([0xC0 | 0x21])) == b" a"


def test_non_palmdb_file_is_rejected(tmp_path):
    bad = tmp_path / "not.mobi"
    bad.write_bytes(b"x" * 200)
    with pytest.raises(LoadError):
        mobi.load(str(bad))


def test_encrypted_file_is_reported_as_drm(tmp_path):
    path = make_samples.make_mobi("drm_probe.mobi")
    data = bytearray(open(path, "rb").read())
    # The encryption field lives at offset 12 of record 0.
    record0 = struct.unpack_from(">I", data, 78)[0]
    struct.pack_into(">H", data, record0 + 12, 1)
    target = tmp_path / "drm.mobi"
    target.write_bytes(bytes(data))
    with pytest.raises(DRMError):
        mobi.load(str(target))


def test_trailing_entry_stripping():
    # A single-byte trailer whose high bit terminates the varint encodes size 1.
    assert mobi._strip_trailing_entries(b"text\x81", 0b10) == b"text"
    # Bit 0 means a multibyte overlap of (n & 3) + 1 bytes.
    assert mobi._strip_trailing_entries(b"text\x00", 0b1) == b"text"
    assert mobi._strip_trailing_entries(b"text", 0) == b"text"


# --------------------------------------------------------------------------
# KF8 / AZW3
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def kf8():
    return mobi.load(make_samples.make_azw3())


def test_kf8_is_recognised_and_read(kf8):
    assert kf8.meta.title == "Des Kaisers neue Kleider (KF8)"
    assert kf8.meta.authors == ["Hans Christian Andersen"]
    assert "Betrüger" in kf8.chapters[0].html


def test_kf8_drops_the_trailing_flows(kf8):
    """Only flow 0 is the book; the CSS flow after </html> must not be shown."""

    html = kf8.chapters[0].html
    assert "font-family: serif" not in html
    assert "page-break-before" not in html


def test_kf8_embed_uris_resolve_to_resources(kf8):
    assert "image_0001" in kf8.resources
    assert 'src="image_0001"' in kf8.chapters[0].html
    assert "kindle:embed" not in kf8.chapters[0].html


def test_kf8_ids_become_anchors(kf8):
    html = kf8.chapters[0].html
    assert 'name="ch0__kap1"' in html and 'name="ch0__kap2"' in html


def test_kf8_toc_from_headings(kf8):
    assert [e.title for e in kf8.toc] == ["Erstes Kapitel", "Zweites Kapitel"]


def test_base32_decoding():
    assert mobi._b32_value("0001") == 1
    assert mobi._b32_value("000A") == 10
    assert mobi._b32_value("0010") == 32
    assert mobi._b32_value("zzz!") == -1, "invalid characters must not raise"


def test_detection_routes_azw3_to_the_kindle_loader():
    from lectern import formats

    path = make_samples.make_azw3()
    assert formats.detect(path) == "mobi"
    assert formats.load(path).format_key == "mobi"
