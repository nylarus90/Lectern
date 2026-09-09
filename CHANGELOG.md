# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed

- The README's two copy-paste commands named `OpenReader-1.0.0-…`, while the
  release job names its files after the tag — the real file is
  `OpenReader-v1.0.0-…`. Both commands failed with "file not found" for anyone
  who followed them. A test now compares the names against the version.

## 1.1.0 — 2026-09-09

### Added

- **English interface.** Source strings are English now, with German shipped as
  a Qt translation; the language follows the system on first start and can be
  fixed under Settings → Reading → Language. 189 strings, and the German wording
  is the same text as before — it was moved into the translation file verbatim
  rather than written anew.
- Qt's own German translation (`qtbase_de.qm`, 220 KB) travels with the build,
  so a German window no longer mixes German menus with English "OK" and
  "Cancel" in standard dialogs.
- `build/make_translations.py` extracts, fills and compiles the translations,
  and refuses to finish unless every string actually translates at runtime.
- `tests/test_i18n.py` fails the build if a German string appears outside
  `tr()`, which is how a half-translated window gets caught.
- `tests/test_version.py` compares `version.py`, `pyproject.toml`, the release
  tag and the changelog heading. This release was first tagged without the
  version bump — the artefacts carried the new number in their file names while
  the installer registered the old one, and nothing in CI noticed.

### Fixed

- Two traps that make translations fail *silently* are now handled explicitly:
  `lupdate` writes an empty context for a plain `tr()` function, which no
  runtime lookup matches; and it re-marks entries "unfinished" whenever a source
  line moves, after which `lrelease` drops them. Either one leaves the text in
  the file and the window in English, with no error anywhere.

### Known limitations

- Command-line help (`--help`) stays English: it is printed before a
  QApplication exists, so it cannot be translated even in principle.
- Changing the language needs a restart. Qt only reads translated text when a
  widget is built, so switching in place would leave half the window in the old
  language — the dialog says so rather than pretending otherwise.

## 1.0.0 — 2026-09-09

First public release. Everything below shipped in it; the entries record how
the work actually went, including what was measured and rejected.

### Reading

- Formats: EPUB 2/3, Kindle KF7 (`.mobi`, `.azw`, `.prc`, `.pdb`) with PalmDOC
  and HUFF/CDIC decompression, Kindle KF8 (`.azw3`), FictionBook, PDF through
  Qt PDF, comic archives (`.cbz`, `.cbt`, `.cb7`, `.cba`, and `.cbr` when a
  system extractor is present), plain text, Markdown, HTML and RTF.
- Format detection reads the file's content, not its extension, so a
  mislabelled book still opens.
- Table of contents, whole-book search, bookmarks and coloured highlights with
  notes, exportable as Markdown.
- Four colour schemes, adjustable font, size, line and paragraph spacing, page
  margin and maximum line length.
- Reading position is stored per book and keyed to the file's content, so
  moving or renaming a book keeps its position and notes.
- Books can be dropped onto the window.

### Distribution

- Portable single-file executables for Windows, macOS and Linux — no runtime,
  no installation.
- Windows installer with a wizard page where every one of the 22 file types is
  individually selectable, plus "Recommended", "All" and "None" buttons.
  Unattended installs are driven by `/ASSOC=`.
- The installer registers `OpenWithProgids`, `SupportedTypes` and
  `Capabilities` always, and claims a type's default handler only where none
  exists — Windows 10 and 11 do not permit more, and taking over an existing
  handler would be rude anyway.
- Portable mode via `--portable`, `--data-dir` or a `portable.txt` marker file
  beside the executable.
- Windows builds are **unsigned**; SmartScreen warns on first launch. Releases
  ship `SHA256SUMS.txt` for verification.

### Performance

- Images are decoded once and kept in a bounded LRU cache. Previously Qt's
  resource cache never saw them, because it only fills when the base
  implementation of `loadResource` runs, so every repaint re-decoded and
  rescaled every visible picture. On a 21 MB illustrated novel that was 303 ms
  per frame over an illustration; it is now 4 ms, with no frame below 30 fps
  where half of them used to be.
- Images are decoded straight to their target size through
  `QImageReader.setScaledSize`, which cut load time for that book from 2.85 s
  to 0.47 s.
- `apply_typography` no longer forces a full document relayout when neither the
  font nor the column width changed.
- The 48 MB cache budget was measured, not guessed: 24 MB dropped 39 frames of
  150 and 12 MB dropped 75, while more than 48 MB bought nothing.
- Background image prefetching was implemented as a measurement and then
  **rejected**: it would have removed 11 noticeable frames out of 7,426, and in
  the worst case could not have saved even half of a single slow frame.
  `tests/bench_prefetch.py` re-runs that analysis.
- The installer ships the directory build rather than the single file, because
  the single file unpacks itself on every launch: 351 ms to the first window
  instead of 854 ms.

### Security and robustness

A security and quality audit raised 16 findings; all were verified against the
source, fixed, and covered by regression tests.

- Cancelling a running load no longer aborts the process. Dropping the last
  reference to a live `QThread` made Qt terminate with `0xC0000409`; loading is
  now cancelled cooperatively and the thread released only once it has stopped.
- A hidden empty element no longer swallows the rest of a chapter. Elements
  such as `<img style="display:none"/>`, `<meta>` and `<input>` have no end tag,
  so the drop region they opened was never closed. Content lost to an unclosed
  region is now reported as a warning instead of vanishing silently.
- Archives are read under a 512 MB expansion budget, checked against both the
  declared and the actual size, so a small crafted file can no longer exhaust
  memory. MOBI's `huff_count` is validated against the records that exist.
- DRM detection evaluates `encryption.xml` per `EncryptedData` entry. A
  keyword search previously let any book combining font obfuscation with
  encrypted chapters through, which then rendered as garbage.
- XML with `<!ENTITY` declarations is refused, which closes entity-expansion
  bombs and XXE on every supported Python version rather than relying on the
  interpreter's libexpat.
- Damaged MOBI headers and malformed RTF produce a readable message instead of
  a traceback.
- A failure to write the reading position is reported once instead of being
  lost silently; the database opens with a busy timeout.
- The data directory is restricted to its owner: `0700`/`0600` on Unix, and an
  ACL naming only the owner and SYSTEM on Windows, which matters for portable
  installations inside shared folders.
- Image paths in HTML books are confined to the book's own directory using
  `commonpath` on resolved paths.
- External extractors are launched by absolute path with `--` separators, and
  extracted paths are verified to be inside the temporary directory.
- Dialogs and tooltips showing file names or book text render as plain text, so
  content cannot disguise itself as markup.
- Settings are range-checked rather than merely type-coerced, so a hand-edited
  configuration cannot produce an unusable window.
- A PDF that fails to open no longer leaves the application claiming a book is
  open.
- Zoom keys act on whatever view is active, PDF passwords are prompted for, the
  stored PDF zoom is restored, and the table of contents follows the reading
  position. Settings that were never read (`reading_mode`, `hyphenate`) were
  removed rather than left as an empty promise.

### Testing

- 174 automated tests, 34 of them driving the real window, including 51
  regression tests written for the audit findings.
- Test books are genuine files — a valid ZIP EPUB, a byte-correct PalmDB MOBI,
  a PDF with a consistent xref table.
- CI builds and smoke-tests on Windows, macOS and Linux, builds the Windows
  installer, and fails if a silent install and uninstall leaves registry
  entries behind.

### Known limitations

- The interface is German only; there is no translation layer yet.
- macOS and Linux executables are built and launched by CI on their own
  platforms, but were never used for actual reading there. Development happened
  on Windows, so on those two anything beyond "it starts" is untested.
- HUFF/CDIC decompression is tested against a purpose-built table, not against
  a commercially published book.
- AZW3/KF8 reconstruction is deliberately simplified and was tested only
  against self-generated files.
- DRM-protected books, KFX, and DjVu are out of scope.
