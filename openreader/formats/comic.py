"""Comic archive loader: CBZ, CBT, CB7 and — where the system allows — CBR.

Only the image entries are kept, in natural sort order, because that order is
the reading order for every comic archive in practice.

RAR is the one gap: RAR5 has no free pure-Python decoder, and the official
``unrar`` source licence forbids redistribution in a competing unarchiver, so it
cannot be bundled.  If a system ``unrar``, ``bsdtar`` or ``7z`` exists we use it,
otherwise the user gets an explanation instead of a silent failure.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from typing import Callable

from .base import Book, BookKind, LoadError, TocEntry, noop_progress

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif", ".jxl"}
_NUM_RE = re.compile(r"(\d+)")


def natural_key(name: str) -> list:
    """Sort ``page2`` before ``page10`` the way a human would."""

    return [int(part) if part.isdigit() else part.lower()
            for part in _NUM_RE.split(name.replace("\\", "/"))]


def _is_image(name: str) -> bool:
    if name.endswith("/") or "__MACOSX" in name:
        return False
    return os.path.splitext(name)[1].lower() in IMAGE_EXT


def load(path: str, progress: Callable[[int, str], None] = noop_progress) -> Book:
    progress(5, "Comic-Archiv wird geöffnet…")
    lowered = path.lower()

    if zipfile.is_zipfile(path):
        entries = _from_zip(path, progress)
    elif tarfile.is_tarfile(path):
        entries = _from_tar(path, progress)
    elif lowered.endswith((".cb7", ".7z")):
        entries = _from_sevenzip(path, progress)
    else:
        entries = _from_rar(path, progress)

    if not entries:
        raise LoadError("Im Archiv wurden keine Bilder gefunden.")

    book = Book(path=path, kind=BookKind.COMIC)
    book.meta.title = os.path.splitext(os.path.basename(path))[0]
    for index, (_name, data) in enumerate(entries):
        key = "page_%05d" % index
        book.resources[key] = data
        book.images.append(key)
    book.cover = entries[0][1]
    book.toc = [TocEntry("Seite %d" % (i + 1), i) for i in range(len(book.images))]
    progress(100, "Fertig")
    return book


def _from_zip(path: str, progress) -> list[tuple[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        names = sorted((n for n in archive.namelist() if _is_image(n)), key=natural_key)
        out = []
        for index, name in enumerate(names):
            progress(10 + int(85 * index / max(1, len(names))), "Seite %d" % (index + 1))
            out.append((name, archive.read(name)))
        return out


def _from_tar(path: str, progress) -> list[tuple[str, bytes]]:
    with tarfile.open(path) as archive:
        members = sorted((m for m in archive.getmembers() if m.isfile() and _is_image(m.name)),
                         key=lambda m: natural_key(m.name))
        out = []
        for index, member in enumerate(members):
            progress(10 + int(85 * index / max(1, len(members))), "Seite %d" % (index + 1))
            handle = archive.extractfile(member)
            if handle is not None:
                out.append((member.name, handle.read()))
        return out


def _from_sevenzip(path: str, progress) -> list[tuple[str, bytes]]:
    try:
        import py7zr
    except ImportError:
        return _extract_with_tool(path, progress, ("7z", "7za", "bsdtar"))
    progress(10, "7z-Archiv wird entpackt…")
    with py7zr.SevenZipFile(path) as archive:
        contents = archive.readall() or {}
    names = sorted((n for n in contents if _is_image(n)), key=natural_key)
    return [(name, contents[name].read()) for name in names]


def _from_rar(path: str, progress) -> list[tuple[str, bytes]]:
    return _extract_with_tool(path, progress, ("unrar", "bsdtar", "7z", "7za"))


def _extract_with_tool(path: str, progress, candidates: tuple[str, ...]) -> list[tuple[str, bytes]]:
    tool = next((name for name in candidates if shutil.which(name)), None)
    if tool is None:
        raise LoadError(
            "Für dieses Archiv wird ein externes Entpackprogramm benötigt "
            "(unrar, bsdtar oder 7z), das auf diesem System nicht gefunden wurde.\n\n"
            "Grund: RAR5 lässt sich nicht frei entpacken, und die unrar-Lizenz "
            "erlaubt es nicht, das Programm mitzuliefern."
        )

    progress(10, "Archiv wird mit %s entpackt…" % tool)
    with tempfile.TemporaryDirectory(prefix="openreader-") as workdir:
        if tool == "unrar":
            command = [tool, "x", "-inul", "-o+", "--", path, workdir + os.sep]
        elif tool == "bsdtar":
            command = [tool, "-xf", path, "-C", workdir]
        else:
            command = [tool, "x", "-y", "-o" + workdir, "--", path]
        try:
            result = subprocess.run(command, capture_output=True, timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LoadError("Das Entpackprogramm %s ist fehlgeschlagen: %s" % (tool, exc)) from exc
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", "replace").strip()[:400]
            raise LoadError("%s konnte das Archiv nicht entpacken.\n%s" % (tool, detail))

        found = []
        for root, _dirs, files in os.walk(workdir):
            for name in files:
                full = os.path.join(root, name)
                if _is_image(full):
                    found.append(os.path.relpath(full, workdir))
        found.sort(key=natural_key)

        out = []
        for index, relative in enumerate(found):
            progress(20 + int(75 * index / max(1, len(found))), "Seite %d" % (index + 1))
            with open(os.path.join(workdir, relative), "rb") as handle:
                out.append((relative, handle.read()))
        return out
