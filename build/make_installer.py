"""Build the Windows installer.

Two steps: a PyInstaller *directory* build, then Inno Setup over it.  The
directory build rather than the single file is deliberate — measured here, the
single file needs 854 ms to its first window because it unpacks itself into a
temporary directory on every launch, against 351 ms for the directory build.
That trade-off is worth it for a portable download and pointless for an
installed copy.

    python build/make_installer.py                 # build everything
    python build/make_installer.py --skip-app      # only re-run Inno Setup
    python build/make_installer.py --iscc "C:\\...\\ISCC.exe"
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
APP_DIR = os.path.join(BUILD, "dist-onedir", "Lectern")
OUT_DIR = os.path.join(BUILD, "dist-installer")
SCRIPT = os.path.join(BUILD, "installer", "lectern.iss")

#: Where Inno Setup puts itself, plus the private copy this script can use when
#: the tool is not installed system-wide.
ISCC_CANDIDATES = (
    os.path.join(BUILD, "tools", "innosetup", "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
)


def app_version() -> str:
    with open(os.path.join(ROOT, "lectern", "version.py"), encoding="utf-8") as handle:
        source = handle.read()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', source)
    if not match:
        raise SystemExit("Version ließ sich aus lectern/version.py nicht lesen.")
    return match.group(1)


def find_iscc(explicit: str | None) -> str:
    if explicit:
        if not os.path.exists(explicit):
            raise SystemExit("ISCC.exe nicht gefunden: %s" % explicit)
        return explicit
    from shutil import which

    found = which("ISCC") or next(
        (path for path in ISCC_CANDIDATES if os.path.exists(path)), None
    )
    if found:
        return found
    raise SystemExit(
        "Inno Setup (ISCC.exe) wurde nicht gefunden.\n\n"
        "Entweder installieren (https://jrsoftware.org/isdl.php) oder den Pfad\n"
        "mit --iscc angeben. Ohne Installation lässt sich der Setup-Assistent\n"
        "auch über die GitHub-Actions-Aufgabe »installer« bauen."
    )


def build_app() -> None:
    print("== PyInstaller (Verzeichnisbau) ==")
    environment = dict(os.environ, LECTERN_ONEDIR="1")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", os.path.join(BUILD, "lectern.spec"),
         "--noconfirm", "--clean",
         "--distpath", os.path.join(BUILD, "dist-onedir"),
         "--workpath", os.path.join(BUILD, "work-onedir")],
        cwd=ROOT, env=environment, check=False,
    )
    if result.returncode != 0:
        raise SystemExit("PyInstaller ist fehlgeschlagen.")
    if not os.path.exists(os.path.join(APP_DIR, "Lectern.exe")):
        raise SystemExit("PyInstaller hat keine Lectern.exe erzeugt: %s" % APP_DIR)


def build_installer(iscc: str, version: str) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    licence = os.path.join(ROOT, "LICENSE")
    command = [
        iscc,
        "/DAppVersion=%s" % version,
        "/DSourceDir=%s" % APP_DIR,
        "/DOutputDir=%s" % OUT_DIR,
    ]
    if os.path.exists(licence):
        command.append("/DLicenseFile=%s" % licence)
    command.append(SCRIPT)

    print("\n== Inno Setup ==")
    print(" ", iscc)
    result = subprocess.run(command, cwd=ROOT, check=False,
                            capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit("Inno Setup ist fehlgeschlagen (Code %d)." % result.returncode)

    expected = os.path.join(
        OUT_DIR, "Lectern-%s-windows-x86_64-setup.exe" % version)
    if not os.path.exists(expected):
        sys.stdout.write(result.stdout)
        raise SystemExit("Der Setup-Assistent wurde nicht erzeugt: %s" % expected)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-app", action="store_true",
                        help="den vorhandenen Verzeichnisbau verwenden")
    parser.add_argument("--iscc", help="Pfad zu ISCC.exe")
    options = parser.parse_args()

    if sys.platform != "win32":
        raise SystemExit("Der Windows-Installer lässt sich nur unter Windows bauen.")

    version = app_version()
    print("Lectern %s" % version)

    iscc = find_iscc(options.iscc)      # checked before the long build step
    if not options.skip_app:
        build_app()
    elif not os.path.exists(os.path.join(APP_DIR, "Lectern.exe")):
        raise SystemExit("--skip-app, aber es gibt keinen Verzeichnisbau in %s" % APP_DIR)

    installer = build_installer(iscc, version)
    print("\nFertig: %s  (%.1f MB)"
          % (installer, os.path.getsize(installer) / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
