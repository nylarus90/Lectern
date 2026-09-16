"""Release metadata parsing without making real network requests."""

from __future__ import annotations

import json

import pytest

from lectern.update import RELEASE_PAGE_PREFIX, fetch_update, version_tuple


class _Response:
    def __init__(self, payload) -> None:
        self.raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.raw


def _release(version: str, url: str | None = None) -> dict:
    return {
        "tag_name": "v%s" % version,
        "html_url": url or RELEASE_PAGE_PREFIX + "v%s" % version,
    }


def test_newer_release_is_reported_and_request_identifies_lectern():
    seen = {}

    def open_request(request, *, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return _Response(_release("1.4.0"))

    info = fetch_update("1.3.2", timeout=3.5, opener=open_request)
    assert info is not None
    assert info.version == "1.4.0"
    assert info.page_url == RELEASE_PAGE_PREFIX + "v1.4.0"
    assert seen["timeout"] == 3.5
    assert seen["request"].get_header("User-agent") == "Lectern/1.3.2"


@pytest.mark.parametrize("latest", ["1.3.2", "1.3.1", "1.2.99"])
def test_current_or_older_release_is_ignored(latest):
    info = fetch_update("1.3.2", opener=lambda *_a, **_k: _Response(_release(latest)))
    assert info is None


@pytest.mark.parametrize("value", ["latest", "1.2", "1.2.3.4", "1.2.3-beta"])
def test_ambiguous_versions_are_rejected(value):
    with pytest.raises(ValueError, match="version"):
        version_tuple(value)


def test_release_page_must_stay_inside_the_project():
    payload = _release("1.4.0", "https://example.invalid/update.exe")
    with pytest.raises(ValueError, match="outside"):
        fetch_update("1.3.2", opener=lambda *_a, **_k: _Response(payload))


def test_oversized_response_is_rejected():
    with pytest.raises(ValueError, match="large"):
        fetch_update("1.3.2", opener=lambda *_a, **_k: _Response(b"x" * (256 * 1024 + 1)))
