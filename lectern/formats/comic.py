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

from ..i18n import tr
from .base import Book, BookKind, ExpansionBudget, LoadError, TocEntry, noop_progress

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
    progress(5, tr("Opening comic archive…"))
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
        raise LoadError(tr("The archive contains no images."))

    book = Book(path=path, kind=BookKind.COMIC)
    book.meta.title = os.path.splitext(os.path.basename(path))[0]
    for index, (_name, data) in enumerate(entries):
        key = "page_%05d" % index
        book.resources[key] = data
        book.images.append(key)
    book.cover = entries[0][1]
    book.toc = [TocEntry(tr("Page %d") % (i + 1), i) for i in range(len(book.images))]
    progress(100, tr("Done"))
    return book


def _from_zip(path: str, progress) -> list[tuple[str, bytes]]:
    budget = ExpansionBudget()
    with zipfile.ZipFile(path) as archive:
        names = sorted((n for n in archive.namelist() if _is_image(n)), key=natural_key)
        out = []
        for index, name in enumerate(names):
            progress(10 + int(85 * index / max(1, len(names))), tr("Page %d") % (index + 1))
            out.append((name, budget.read_zip(archive, name)))
        return out


def _from_tar(path: str, progress) -> list[tuple[str, bytes]]:
    budget = ExpansionBudget()
    with tarfile.open(path) as archive:
        members = sorted((m for m in archive.getmembers() if m.isfile() and _is_image(m.name)),
                         key=lambda m: natural_key(m.name))
        out = []
        for index, member in enumerate(members):
            progress(10 + int(85 * index / max(1, len(members))), tr("Page %d") % (index + 1))
            budget.check(member.size, member.name)
            handle = archive.extractfile(member)
            if handle is not None:
                data = handle.read()
                budget.spend(len(data), member.name)
                out.append((member.name, data))
        return out


def _from_sevenzip(path: str, progress) -> list[tuple[str, bytes]]:
    try:
        import py7zr
    except ImportError:
        return _extract_with_tool(path, progress, ("7z", "7za", "bsdtar"))
    progress(10, tr("Extracting 7z archive…"))
    with py7zr.SevenZipFile(path) as archive:
        total = sum(info.uncompressed for info in archive.list() if _is_image(info.filename))
        ExpansionBudget().check(total, os.path.basename(path))
        contents = archive.readall() or {}
    names = sorted((n for n in contents if _is_image(n)), key=natural_key)
    budget = ExpansionBudget()
    out = []
    for name in names:
        data = contents[name].read()
        budget.spend(len(data), name)
        out.append((name, data))
    return out


def _from_rar(path: str, progress) -> list[tuple[str, bytes]]:
    return _extract_with_tool(path, progress, ("unrar", "bsdtar", "7z", "7za"))


def _extract_with_tool(path: str, progress, candidates: tuple[str, ...]) -> list[tuple[str, bytes]]:
    # Resolve to an absolute path and launch *that*.  Passing the bare name to
    # subprocess would let the operating system search again at launch time,
    # and on some Python versions that search includes the current working
    # directory — so a file dropped beside the book could be run instead.
    resolved = next(
        ((name, shutil.which(name)) for name in candidates if shutil.which(name)),
        (None, None),
    )
    tool, executable = resolved
    if tool is None or executable is None:
        raise LoadError(
            tr("This archive needs an external extractor (unrar, bsdtar or 7z), and "
               "none was found on this system.\n\nRAR5 cannot be extracted with "
               "free software, and the unrar licence forbids shipping the tool.")
        )

    progress(10, tr("Extracting archive with %s…") % tool)
    with tempfile.TemporaryDirectory(prefix="lectern-") as workdir:
        # ``--`` everywhere, so an archive whose name begins with a dash is
        # read as a file name and not as another option.
        if tool == "unrar":
            command = [executable, "x", "-inul", "-o+", "--", path, workdir + os.sep]
        elif tool == "bsdtar":
            command = [executable, "-x", "-C", workdir, "-f", path]
        else:
            command = [executable, "x", "-y", "-o" + workdir, "--", path]
        try:
            result = subprocess.run(command, capture_output=True, timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LoadError(tr("The extractor %s failed: %s") % (tool, exc)) from exc
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", "replace").strip()[:400]
            raise LoadError(tr("%s could not extract the archive.\n%s") % (tool, detail))

        # Whether the external tool refuses "../" entries is its business, not
        # something we can rely on, so only files that really ended up inside
        # the temporary directory are read back.
        safe_root = os.path.realpath(workdir)
        found = []
        for root, _dirs, files in os.walk(workdir):
            for name in files:
                full = os.path.realpath(os.path.join(root, name))
                if not _is_image(full):
                    continue
                try:
                    if os.path.commonpath([safe_root, full]) != safe_root:
                        continue
                except ValueError:
                    continue
                found.append(os.path.relpath(full, safe_root))
        found.sort(key=natural_key)

        out = []
        budget = ExpansionBudget()
        for index, relative in enumerate(found):
            progress(20 + int(75 * index / max(1, len(found))), tr("Page %d") % (index + 1))
            full = os.path.join(safe_root, relative)
            budget.check(os.path.getsize(full), relative)
            with open(full, "rb") as handle:
                data = handle.read()
            budget.spend(len(data), relative)
            out.append((relative, data))
        return out
