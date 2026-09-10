# Lectern

*Formerly OpenReader — renamed in 1.2, see the [changelog](CHANGELOG.md).*

[Deutsch](README.de.md) · **English**

A free e-book reader — no runtime, no browser, no dependencies. A **portable
single file** you download and run, or, on Windows, an **installer** with file
associations you choose yourself.

![License](https://img.shields.io/badge/License-GPL--3.0--or--later-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Qt](https://img.shields.io/badge/Interface-Qt%20Widgets-41cd52)

---

## Supported formats

| Format | Extensions | What is handled |
|---|---|---|
| **EPUB 2 / EPUB 3** | `.epub` | Spine, NCX and nav table of contents, cover, images, internal links, metadata including series |
| **Kindle KF7** | `.mobi` `.azw` `.prc` `.pdb` | PalmDOC and HUFF/CDIC decompression, EXTH metadata, `recindex` images, `filepos` links |
| **Kindle KF8** | `.azw3` `.azw` | Main flow, `kindle:embed:` images, combined MOBI/KF8 files |
| **FictionBook** | `.fb2` `.fb2.zip` `.fbz` | Nested sections, poems, quotes, embedded images |
| **PDF** | `.pdf` | Native rendering through Qt PDF, outline, full-text search, zoom |
| **Comics** | `.cbz` `.cbt` `.cb7` `.cba` `.cbr` | Natural page ordering, fit modes |
| **Text** | `.txt` `.log` | Encoding detection, automatic chapter detection |
| **Markdown** | `.md` `.markdown` | CommonMark |
| **HTML** | `.html` `.htm` `.xhtml` | With images from the neighbouring directory |
| **Rich Text** | `.rtf` | Formatting, encodings, Unicode escapes |

The format is detected **from the content**, not the extension — an AZW3 file
named `.epub` still opens correctly.

### What deliberately does not work

| | Why |
|---|---|
| **DRM-protected books** (Adobe ADEPT, Kindle) | Legally and technically outside this project. Such files are recognised and refused with a clear message instead of showing garbage. |
| **KFX** (the newer Kindle format) | Undocumented and in practice always DRM-encumbered. |
| **`.cbr` without a system tool** | There is no free RAR5 extractor for Python, and the unrar licence forbids shipping the binary. If `unrar`, `bsdtar` or `7z` is installed it is used; otherwise you get an explanation rather than a silent failure. |
| **DjVu** | Would need a C library, and therefore a compiler in the build chain. |

---

## Installation

Windows gets both options; everywhere else the single executable is enough.

| Platform | File | Note |
|---|---|---|
| Windows 10/11 (x64) | `Lectern-*-windows-x86_64-setup.exe` | Installer with selectable file associations |
| Windows 10/11 (x64) | `Lectern-*-windows-x86_64.exe` | Portable, double-click, nothing installed |
| Windows 11 on ARM (e.g. Surface Pro 11) | `Lectern-*-windows-arm64-setup.exe` | Installer, native ARM64 |
| Windows 11 on ARM | `Lectern-*-windows-arm64.exe` | Portable, native ARM64 |
| macOS (Apple Silicon) | `Lectern-*-macos-arm64.zip` | Unpack, then right-click → "Open" (unsigned) |
| Linux (x64, glibc ≥ 2.35) | `Lectern-*-linux-x86_64` | `chmod +x` and run |

### Language

The interface speaks **English and German**. On first start it follows the
system language: a German Windows gets German, everything else English. It can
be fixed either way under **Settings → Reading → Language**, which takes effect
after a restart.

Qt's own dialog buttons follow along — a German window says "OK" and
"Abbrechen", not "OK" and "Cancel" — because the build carries Qt's German
translation alongside its own.

Adding a language means translating one file, `lectern_de.ts`'s sibling, in
Qt Linguist; `python build/make_translations.py` extracts and compiles it.

### Windows warns on first launch

Both Windows files are **unsigned**, so SmartScreen shows "Windows protected
your PC" the first time. **More info → Run anyway** continues.

This says nothing about the file itself; it is simply the absence of a
certificate. Code signing costs money every year, has been capped at 460 days
of validity since March 2026, and would not even remove the warning right away
— SmartScreen builds trust from download numbers. For a hobby project that is
out of proportion.

To check the download, compare it against `SHA256SUMS.txt` from the same
release:

```powershell
Get-FileHash .\Lectern-v1.2.0-windows-x86_64-setup.exe -Algorithm SHA256
```

### Installer or portable?

| | Installer | Portable file |
|---|---|---|
| Launch to first window | **351 ms** | 854 ms |
| Download | 28 MB | 36 MB |
| File associations | yes, freely selectable | no |
| Start menu, uninstaller | yes | no |
| Administrator rights | not required (optional) | not required |
| Leaves traces | yes, uninstallable | none |

The portable file is slower because it unpacks itself into a temporary
directory on **every** launch — which is exactly what makes it portable. The
installer writes the files once and skips that.

### File associations

The installer has a page of its own where **every file type is individually**
selectable, with buttons for "Recommended", "All" and "None". E-books and comic
archives start ticked because Windows usually has no handler for them at all.
PDF, text and HTML start unticked — those almost always have a handler already.

What the installer does then depends on the file type, and that is not
arbitrary but the line Windows draws:

- **Type had no handler** (`.mobi`, `.azw3`, `.fb2`, `.cbz` …) → Lectern
  becomes the default.
- **Type already has a handler** (`.pdf`, `.txt`, often `.epub`) → Lectern is
  added to "Open with" and to the Windows default apps; the existing default is
  left alone.

Windows 10 and 11 do not let an installer force the default handler, and that
is a good thing. To change it: **Settings → Apps → Default apps → Lectern**.

Uninstalling takes the associations back — but only its own. If you have since
pointed a file type at another program, that choice survives.

For unattended installs:

```bat
Lectern-v1.2.0-windows-x86_64-setup.exe /VERYSILENT /ASSOC=.epub,.cbz
```

`/ASSOC=` accepts `none`, `all`, `suggested`, `previous` or a list of
extensions. Without it, `previous` applies: an update keeps the earlier
choice, a first install gets the suggested set. `/CURRENTUSER` and `/ALLUSERS` select the install scope, `/DIR=`
the target directory.

### Tablets: touch and pen

On a touch screen Lectern is read with the finger:

| Gesture | Effect |
|---|---|
| Drag | Scroll, with momentum |
| Swipe left / right | Next / previous page |
| Tap the left / right third | Previous / next page |
| Tap in the middle | In full screen: show or hide the toolbar |
| Tap a link | Follow it |
| Pinch | Font size; zoom in PDFs; fit mode in comics |
| Long press | Select a word, drag to extend, then highlight or copy |

A pen, such as the Surface Pen, selects text like a mouse, so highlighting with
it needs no long press. When a touch screen is present, touch mode enlarges the
toolbar and the list rows and adds a full-screen button, since a tablet has no
F11 and no Esc. *Settings → Reading → Touch operation* switches it on, off, or
back to automatic.

### Portable on a USB stick

By default the reading position and settings live in your user profile. For a
fully portable setup that leaves nothing on the machine, put an empty
`portable.txt` next to the executable — or start with:

```bash
Lectern --portable
```

Any other location works too:

```bash
Lectern --data-dir /path/to/my/data
```

---

## Using it

| Key | Action |
|---|---|
| `Space` · `Page Down` · `→` | Next page |
| `Backspace` · `Page Up` · `←` | Previous page |
| `Ctrl+O` / `Ctrl+W` | Open / close book |
| `Ctrl+F` · `F3` · `Shift+F3` | Search · next · previous match |
| `Ctrl+B` | Add bookmark |
| `Ctrl+H` | Highlight selection |
| `Ctrl+G` | Go to page or position |
| `Ctrl++` / `Ctrl+−` / `Ctrl+0` | Zoom in / out / reset |
| `F9` / `F11` | Sidebar / full screen |
| `Ctrl+,` | Settings |
| `Esc` | Leave search, leave full screen |

Books can also be dropped onto the window.

**Also included:** four colour schemes (light, sepia, dark, OLED black);
adjustable font, size, line and paragraph spacing, page margin and maximum line
length; bookmarks and coloured highlights with notes, exportable as Markdown.
The reading position is remembered per book and survives moving the file,
because books are identified by content rather than by path.

---

## From source

```bash
python -m pip install -r requirements-dev.txt
python -m lectern                     # run
python -m pytest                         # 174 tests
python tests/smoke_gui.py --visible      # screenshots of every view
python tests/bench_reader.py             # measure scrolling performance
python tests/bench_prefetch.py --book X  # quantify the remaining stutter
pyinstaller build/lectern.spec --noconfirm --distpath build/dist
python build/make_installer.py           # Windows installer (needs Inno Setup 6)
```

Requires Python 3.10 or newer.

---

## Layout

```
lectern/
├── formats/     One parser per format → one shared Book model
├── render/      HTML5→Qt normalisation, colour schemes, typography
├── storage/     SQLite (position, bookmarks, highlights) and settings
└── ui/          Main window, text/PDF/comic views, panels, loading thread
```

Every format parser produces the same `Book` object, which is what keeps the
views free of format-specific special cases. Loading runs on a worker thread;
only the finished document is handed to the interface.

### Technical decisions

**Why Qt's own rich text engine rather than an embedded browser engine?**
An embedded Chromium would grow the executable from 36 MB to over 250 MB and
would effectively be a browser. In exchange, Qt's engine understands only part
of CSS 2.1 — excellent for fiction and ordinary non-fiction, simplified for
multi-column or elaborately designed EPUB 3 layouts. Publisher stylesheets can
be switched on in the settings; they are off by default, because a
half-applied stylesheet usually looks worse than a clean one of our own.

**Why a single document instead of one per chapter?**
It is the only way continuous scrolling, whole-book search and stable highlight
positions work at all. Because the document is built deterministically from the
file, a stored highlight still points at the same words months later.

**Why does the reader cache images itself?**
Qt only puts a resource into its cache when the *base implementation* of
`loadResource` runs. Book images live in memory rather than on disk, so the
reader has to return before that point — and therefore has to cache them
itself. Without that, every illustration was decoded and smoothly rescaled on
**every single repaint**. On a 21 MB novel with 15 full-page plates that cost
303 ms per frame, and half of all frames fell below 30 fps. Measured and fixed:
see [Scrolling performance](#scrolling-performance).

**Why are images not prefetched in the background?**
Because the benefit was measured. After the cache one cost remains: a picture
must be decoded once, the first time it appears. Scrolling through an entire
21 MB illustrated book, that is **11 noticeable frames out of 7,426** — 0.15 %,
each about 17 ms above normal, so one or two dropped frames at 60 Hz. Paging
through the whole book costs 0.26 seconds in total. In the worst case, a jump
via the table of contents, only ~25 ms of roughly 59 ms is decoding, so a
prefetcher could not even save half of it. Against that stand a background
thread, a locked cache, viewport prediction logic and a hard-to-test class of
race conditions. Recheck it with `tests/bench_prefetch.py`.

**Why is the line height reset for images?**
A relative `line-height` multiplies the height of the tallest element on a
line. A 320 px illustration inside a 155 % paragraph would otherwise occupy
496 px and leave a hole. Blocks containing images therefore get 100 % line
height afterwards — and are centred while we are at it.

### What is stored, and where

Lectern sends nothing over the network. Stored locally are the file path,
title, author, time of opening, reading position, plus bookmarks, highlights
and notes — in `library.sqlite3` and `settings.json`:

| Platform | Location |
|---|---|
| Windows | `%APPDATA%\lectern` |
| macOS | `~/Library/Application Support/lectern` |
| Linux | `$XDG_DATA_HOME/lectern` or `~/.local/share/lectern` |

Up to version 1.1.1 the program was called OpenReader and kept its data in a
folder named `openreader`. Lectern takes that folder over on first start by
renaming it — reading positions, bookmarks and notes stay as they were.

The directory belongs to your account alone: `0700` on Linux and macOS with
`0600` for the files, and on Windows an ACL naming only the owner and SYSTEM.
This matters most in portable mode — a data folder inside a shared directory
would otherwise inherit that directory's permissions. On a file system with no
permissions at all, such as a FAT-formatted USB stick, nothing can be enforced
and the data sits in the open.

**It is not encrypted.** If you need that, point `--data-dir` at an encrypted
volume. **File → Recently opened → Clear list** deletes the whole history,
bookmarks and notes included.

---

## Scrolling performance

Measured with `tests/bench_reader.py` on a real 21 MB novel with 15 full-page
JPEG plates, window maximised, 150 wheel notches, 150 % display scaling:

| | before | after |
|---|---|---|
| Frame over an illustration (median) | 303 ms | **4 ms** |
| Worst frame | 453 ms | **31 ms** |
| Frames below 30 fps | 77 of 150 | **0 of 150** |
| Image decodes while scrolling | 939 | **2** |
| Load time | 2.85 s | **0.47 s** |
| Memory | 199 MB | 249 MB |

Plain text passages sat at about 5 ms before and after — the text layout was
never the problem, and it does not grow with the position in the book.

The extra 50 MB is the image cache. Its budget was not guessed but measured: at
48 MB not one frame dropped, at 24 MB 39 did and at 12 MB 75 did. More than
48 MB bought no further smoothness.

Two smaller fixes came out of the same measurement: images are decoded straight
to their target size via `QImageReader.setScaledSize` rather than fully and then
scaled (that alone makes loading six times faster), and `apply_typography` no
longer forces a full relayout when neither the font nor the width changed.

```bash
python tests/bench_reader.py --book "my-book.epub"
```

The tool reports frame times separately for passages with and without an
illustration, and exits with status 1 as soon as a frame stutters.

---

## Tests

174 automated tests, 34 of them at widget level driving the real window: every
format is opened through the actual loading path, search, highlights and
restoring the reading position are exercised, and damaged as well as
DRM-protected files must produce a comprehensible message instead of crashing.

The test books are **real files** — a valid ZIP EPUB, a byte-correct PalmDB
MOBI, a PDF with a consistent xref table — so the parsers are stressed the same
way a book from a shop would stress them.

### Test bench

What rests on what evidence:

| | Status |
|---|---|
| EPUB 2/3, MOBI (KF7), FB2, PDF, CBZ, TXT, MD, HTML, RTF | Tested automatically and inspected by hand |
| Windows executable and installer | Built, launched, opens books, associations and uninstall verified |
| **HUFF/CDIC decompression** | Tested against a purpose-built, format-conformant Huffman table including nested phrases. That covers the bit reader, table access and recursion — but **not** the variable code lengths of a real published book. |
| **AZW3 / KF8** | Tested against a self-generated KF8 file (flow cut, `kindle:embed`, anchors, TOC). **No commercial AZW3 file was available**; the skeleton/fragment reconstruction in particular is deliberately simplified. Please cross-check with a real book. |
| macOS and Linux executables | Built **and launched** by CI on their own platforms. Never used for actual reading there, though — development happened on Windows, so anything beyond "it starts" is untested on those two. |
| CBR | Path through external tools implemented; what is tested is the error message when none is present |

---

## Project documents

| Document | Language |
|---|---|
| [CHANGELOG.md](CHANGELOG.md) — what changed in each release | English |
| [SECURITY.md](SECURITY.md) — threat model and how to report a vulnerability | English |
| [docs/RELEASING.md](docs/RELEASING.md) — how a release is cut | English |
| [docs/audit-2026-09-08.md](docs/audit-2026-09-08.md) — security and quality audit, 16 findings and their fixes | German |

---

## Licence

GNU General Public License v3.0 or later — see [LICENSE](LICENSE).

The interface uses Qt through PySide6 under the LGPL v3 — the text is in
[licenses/LGPL-3.0.txt](licenses/LGPL-3.0.txt). Both licence texts travel
inside every build and are shown under *Help → Licences*. The installer puts a
second copy in `licenses\` beside the program, and shows the GPL during setup.

The Qt libraries are shipped as separate files. In the installed build they can
be replaced where they lie; in the portable single file they are packed into
the executable, so replacing Qt there means rebuilding — which this program's
licence permits and its source makes possible.

Unmodified sources of the libraries:
[Qt](https://download.qt.io/official_releases/qt/) ·
[PySide6](https://download.qt.io/official_releases/QtForPython/).
