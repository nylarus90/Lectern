"""Runs the touch tests in a process of their own, on Qt's offscreen platform.

Measured while building touch support: on a real Windows desktop, Qt dropped
simulated touch events for seconds at a time — every touch, on every widget,
including a fresh one that had nothing to do with the tests, and from every
kind of simulated device — and then accepted them again. The same tests passed
on their own, and passed every time on the offscreen platform, which has no
window manager, no focus rules and no other input to interfere.

What the touch tests check — how a stream of touch events becomes scrolling,
paging, pinching and selecting — does not depend on the platform. How it feels
on glass has to be checked on a device anyway.

Qt fixes the platform when the QApplication is created, once per process, so
the only way to run those tests offscreen inside an ordinary session is a
child process. Run with ``QT_QPA_PLATFORM=offscreen`` already set, the touch
tests run directly and this one steps aside.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.mark.skipif(os.environ.get("QT_QPA_PLATFORM") == "offscreen",
                    reason="already offscreen: test_touch.py runs directly")
def test_touch_tests_pass_offscreen(tmp_path):
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "--basetemp", str(tmp_path / "touch"), str(ROOT / "tests" / "test_touch.py")],
        cwd=ROOT, env=environment, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900, check=False,
    )
    # The names first: a CI annotation keeps only the end of a long message,
    # and the names are what says where to look.
    failed = [line for line in result.stdout.splitlines()
              if line.startswith(("FAILED", "ERROR"))]
    assert result.returncode == 0, (
        "touch tests failed in the offscreen process:\n" + "\n".join(failed)
        + "\n\n" + result.stdout[-6000:] + "\n" + result.stderr[-2000:]
    )
