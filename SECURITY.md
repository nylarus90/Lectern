# Security policy

## Reporting a vulnerability

Please report security problems **privately** through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
— the *Security* tab of this repository — rather than in a public issue.

Useful in a report:

- what happens, and what you expected instead;
- the file that triggers it, if you can share it, or a script that generates one;
- operating system, and whether you used the installer, the portable build or a
  source checkout.

This is a hobby project maintained in spare time, so there is no guaranteed
response time. Expect an acknowledgement within a couple of weeks. If a report
turns out to be serious, the fix and a new release take priority over
everything else on the list.

## Supported versions

Only the latest release receives fixes. There are no maintenance branches.

## Threat model

An e-book reader is a parser for files that come from anywhere — a download, a
mail attachment, a shared drive. The realistic attacker supplies a malicious
file and hopes it is opened. That is the case this project takes seriously.

**In scope, and interesting to us:**

- Memory exhaustion or a hang from a small crafted file (archive bombs,
  implausible header counts, XML entity expansion).
- A crash, or any code path that reaches an unhandled exception, from a
  malformed book.
- Anything that makes the reader read or write a file outside the book — path
  traversal through image references or archive entries.
- Anything that makes the reader execute code, contact the network, or hand
  content to an external program unexpectedly.
- Book content that is rendered as markup or as a command where it should be
  displayed as text.
- The Windows installer taking a file association it was not given, or leaving
  registry entries behind after uninstalling.

**Out of scope:**

- Bugs in Qt itself — its PDF engine, image decoders and text layout. Report
  those to the [Qt project](https://bugreports.qt.io/); we will pick up the
  fixed version.
- Anything requiring an attacker who already runs code as your user. Such an
  attacker can read the library database anyway.
- The SmartScreen warning on Windows. The builds are unsigned on purpose; see
  the README.
- Missing encryption of the reading history. The data directory is restricted
  to its owner, but it is not encrypted, and the README says so. If you need
  encryption at rest, point `--data-dir` at an encrypted volume.
- DRM removal of any kind. Out of scope legally and technically.

## What the project already does

Documented here so a report can tell a gap from a deliberate decision:

- No network code at all. Qt's network and WebEngine modules are excluded from
  the build, so the guarantee is structural rather than a promise. The only
  outbound path is opening a link in your browser, and that asks first.
- No `eval`, no `pickle`, no shelling out except to an archive extractor, which
  is launched by absolute path with `--` separators and whose output is
  verified to stay inside a temporary directory.
- Book markup passes an allow-list sanitiser before it reaches the rendering
  engine: scripts, styles and forms are dropped with their subtrees, link
  schemes are limited to http, https and mailto, and image sources can only
  resolve to keys already held in memory.
- Archives are expanded under a 512 MB budget, checked against both the
  declared and the actual size.
- XML is refused if it declares entities, which closes expansion bombs and XXE
  independently of the interpreter's libexpat version.
- All SQL is parameterised; settings are written atomically and range-checked
  on load.
- The data directory is created private to its owner — `0700`/`0600` on Unix,
  and on Windows an ACL naming only the owner and SYSTEM.

A [security and quality audit](docs/audit-2026-09-08.md) from September 2026
lists 16 findings and how each was fixed; the document is in German. Its
regression tests live in `tests/test_audit_fixes.py`.
