# Making a release

The release itself is done by CI: pushing a tag that starts with `v` builds
every platform, produces the Windows installer, and publishes a GitHub release
with checksums. What follows is what has to be right *before* the tag.

## Before tagging

1. **Bump the version.** `lectern/version.py` and `pyproject.toml` must
   agree; the installer takes its version from `version.py`.

   ```bash
   grep -n "version" lectern/version.py pyproject.toml
   ```

   `tests/test_version.py` compares the two, and on a tag build it also
   compares them against the tag itself and against a dated changelog section.
   That test exists because v1.1.0 was first tagged without the bump: the files
   were named after the tag, the installer registered the old version, and all
   eight jobs were green.

2. **Write the changelog entry.** Add a section to `CHANGELOG.md` with the new
   version and the release date. Date it the day the tag is pushed.

3. **Rebuild the translations.** New or changed strings otherwise ship
   untranslated, and nothing else in the build notices.

   ```bash
   python build/make_translations.py
   ```

   It exits non-zero when a string has no German text, and verifies that the
   compiled file really translates rather than merely existing.

4. **Run the tests and the linter.** Both must be clean.

   ```bash
   python -m pytest
   python -m ruff check .
   ```

5. **Build and try the artefacts by hand.** CI checks that they start; it does
   not check that they are pleasant to use.

   ```bash
   pyinstaller build/lectern.spec --noconfirm --distpath build/dist
   python build/make_installer.py
   ```

   Open a real book of each kind that changed, and on Windows run the installer
   once with associations on and uninstall it again.

6. **Check the performance floor** if anything in the reader view or the format
   parsers changed. The tool exits non-zero as soon as a frame stutters.

   ```bash
   python tests/bench_reader.py --book "some-illustrated-book.epub"
   ```

7. **Clean the working tree.** `git status` must be empty, and the build
   directories are ignored rather than committed.

## Tagging

```bash
git tag -a v1.0.0 -m "Lectern 1.0.0"
git push origin main --tags
```

The `release` job runs only for tags matching `refs/tags/v*`. It waits for both
the `build` and the `installer` jobs, so a failure in either stops the release
rather than publishing half of it.

## What CI produces

| File | Built by |
|---|---|
| `Lectern-vX.Y.Z-windows-x86_64-setup.exe` | `installer` job (Windows runner, Inno Setup) |
| `Lectern-vX.Y.Z-windows-x86_64.exe` | `build` job (portable single file) |
| `Lectern-vX.Y.Z-windows-arm64-setup.exe` | `installer` job on `windows-11-arm` |
| `Lectern-vX.Y.Z-windows-arm64.exe` | `build` job on `windows-11-arm` |
| `Lectern-vX.Y.Z-macos-arm64.zip` | `build` job |
| `Lectern-vX.Y.Z-linux-x86_64` | `build` job (built on Ubuntu 22.04 so it runs on newer releases too) |
| `SHA256SUMS.txt` | `release` job |

## After the release

- Download the Windows installer from the release page and check its SHA-256
  against `SHA256SUMS.txt`. This catches a broken upload, and it is the same
  check the README asks users to perform.
- CI builds and launches the macOS and Linux binaries on their own platforms,
  but nobody has read a book with them. If someone reports a problem there that
  goes beyond starting up, treat it as plausible rather than surprising.

## Things that are deliberately not done

- **No code signing.** The Windows builds are unsigned, so SmartScreen warns on
  first launch. A certificate costs money every year, has been capped at 460
  days of validity since March 2026, and would not remove the warning
  immediately anyway. The README explains this to users; do not quietly change
  it without updating that text.
- **No `[project.urls]` in `pyproject.toml`** while the project has no public
  home. Add it together with the repository, not before.
