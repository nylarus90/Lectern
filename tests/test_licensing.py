"""Guards for the licence texts that have to accompany the binaries.

The GPL and the LGPL both ask for a copy of the licence to travel with the
program. Until v1.1.0 none of the four release files carried one, and the LGPL
text for Qt was not in the repository at all — the About dialog named the
licences, which is the notice, not the copy.

Nothing about that failure is visible at build time, so it is checked here.
"""

from __future__ import annotations

import pathlib

import pytest

from lectern.licensing import COMPONENTS, SOURCES, licence_text

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("file_name", [entry[2] for entry in COMPONENTS])
def test_licence_text_is_present_and_whole(file_name: str) -> None:
    """Every component's licence must resolve to its actual text."""

    text = licence_text(file_name)
    assert len(text) > 5000, "%s looks truncated: %d characters" % (file_name, len(text))
    assert "GNU" in text and "Version 3" in text
    # The fallback string is returned when the file is missing; seeing it here
    # means the lookup failed rather than that the text is unusual.
    assert "does not carry the licence text" not in text


def test_lgpl_text_is_in_the_repository() -> None:
    """Qt travels in the bundle, so its licence has to be shipped with it."""

    assert (ROOT / "licenses" / "LGPL-3.0.txt").is_file()


def test_the_build_collects_both_texts() -> None:
    """The spec must place the texts where the frozen lookup expects them.

    ``licences_dir()`` resolves to ``lectern/resources/licenses`` inside the
    bundle; if the spec ever stops copying them there, Help → Licences shows
    the fallback note and the binaries ship without a licence again.
    """

    spec = (ROOT / "build" / "lectern.spec").read_text(encoding="utf-8")
    assert '"lectern", "resources", "licenses"' in spec
    for file_name in (entry[2] for entry in COMPONENTS):
        assert file_name in spec, "the spec does not collect %s" % file_name


def test_sources_are_named() -> None:
    """The LGPL asks where the uncombined library can be obtained."""

    assert SOURCES and all(address.startswith("https://") for _name, address in SOURCES)
