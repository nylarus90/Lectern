"""Frozen-build entry point.

``lectern/__main__.py`` cannot serve as the PyInstaller entry script: it is
run as the top-level ``__main__`` module, where its relative imports have no
parent package.  This script imports absolutely instead, and is the only thing
the spec file points at.
"""

import sys

from lectern.app import main

if __name__ == "__main__":
    sys.exit(main())
