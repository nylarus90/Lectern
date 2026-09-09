"""Guards against a release that lies about its own version.

v1.1.0 was tagged while ``version.py`` still said ``1.0.0``. Nothing failed:
the release files are named after the tag, so they were called ``v1.1.0``,
while the installer registered "OpenReader 1.0.0" in Programs and Features and
``--version`` agreed with it. Every job was green, because no job ever compared
the two.

The tag test below is skipped during normal work and only bites on a tag push,
where it runs in the ``test`` job that ``build`` and ``installer`` depend on —
so a mislabelled tag stops before anything is published.
"""

from __future__ import annotations

import os
import pathlib
import re

import pytest

from openreader.version import __version__

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_version_matches_pyproject() -> None:
    """The packaging metadata and the application must agree.

    The installer reads ``version.py``; anything installing the package reads
    ``pyproject.toml``. When they drift, which one is "the" version depends on
    how the user got the program.
    """

    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml declares no version"
    assert match.group(1) == __version__


@pytest.mark.skipif(os.environ.get("GITHUB_REF_TYPE") != "tag",
                    reason="only meaningful for a tag build")
def test_release_tag_matches_version() -> None:
    """On a tag, the tag, the version and a dated changelog entry must agree."""

    tag = os.environ.get("GITHUB_REF_NAME", "")
    assert tag.startswith("v"), "release tags are expected to start with v"
    assert tag[1:] == __version__, (
        "tag %s does not match __version__ %s — bump openreader/version.py and "
        "pyproject.toml before tagging" % (tag, __version__)
    )

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.compile(r"^## %s — \d{4}-\d{2}-\d{2}$" % re.escape(__version__),
                         re.MULTILINE)
    assert heading.search(changelog), (
        "CHANGELOG.md has no dated section for %s; a section still headed "
        "'Unreleased' means the release notes describe nothing" % __version__
    )


def test_readme_examples_name_a_file_that_will_exist() -> None:
    """The README's copy-paste commands must name the current release file.

    They were written as ``OpenReader-1.0.0-…`` while the release job names its
    files after the tag, so the real file is ``OpenReader-v1.0.0-…``. Both
    commands failed with "file not found" for anyone who followed them, and
    they went on drifting with every release.
    """

    expected = "OpenReader-v%s-windows-x86_64-setup.exe" % __version__
    for name in ("README.md", "README.de.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        stale = re.findall(r"OpenReader-v?\d+\.\d+\.\d+-windows-x86_64-setup\.exe",
                           text)
        assert stale, "%s names no installer file any more" % name
        assert set(stale) == {expected}, (
            "%s refers to %s; the release is %s" % (name, sorted(set(stale)), expected)
        )
