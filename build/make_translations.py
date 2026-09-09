"""Extract, fill and compile the translations.

    python build/make_translations.py           # extract, fill, compile
    python build/make_translations.py --report  # only say what is missing

Three steps, and the middle one exists because of a trap worth knowing about:
``lupdate`` writes an *empty* context name for calls to a plain ``tr()``
function, since there is no class to attribute them to. The runtime looks
strings up under the context given to ``QCoreApplication.translate`` — so
without rewriting the name, every lookup misses and the window stays English
with the translation loaded and no error anywhere.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
I18N = ROOT / "openreader" / "resources" / "i18n"
TS = I18N / "openreader_de.ts"
QM = I18N / "openreader_de.qm"
GERMAN = ROOT / "build" / "i18n_de.json"

#: Must match openreader.i18n.CONTEXT.
CONTEXT = "OpenReader"


def tool(name: str) -> str:
    """Locate a PySide6 command line tool next to the running interpreter."""

    candidate = pathlib.Path(sys.executable).parent / name
    for suffix in ("", ".exe"):
        if (candidate.with_suffix(suffix)).exists():
            return str(candidate.with_suffix(suffix))
    from shutil import which

    found = which(name)
    if not found:
        raise SystemExit("%s not found; is PySide6 installed?" % name)
    return found


def sources() -> list[str]:
    return [str(p) for p in sorted((ROOT / "openreader").rglob("*.py"))
            if "_versions" not in p.parts]


def extract() -> None:
    I18N.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [tool("pyside6-lupdate"), *sources(), "-ts", str(TS), "-no-obsolete"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit("lupdate failed")
    print(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "extracted")


def fill() -> tuple[int, list[str]]:
    """Name the context and report what is still untranslated.

    Translations themselves live in the ``.ts`` file, which ``lupdate`` merges
    rather than overwrites — that file is the source of truth and belongs in
    version control. ``i18n_de.json`` only existed to carry the German text
    across the one-off migration from German sources; it is optional now.
    """

    german = json.loads(GERMAN.read_text(encoding="utf-8")) if GERMAN.exists() else {}
    tree = ET.parse(TS)
    root = tree.getroot()

    filled, missing = 0, []
    for context in root.findall("context"):
        name = context.find("name")
        if name is not None and not (name.text or "").strip():
            name.text = CONTEXT          # see the module docstring
        for message in context.findall("message"):
            source = message.findtext("source") or ""
            translation = message.find("translation")
            if translation is None:
                continue
            existing = (translation.text or "").strip()
            if existing:
                # A translation that has text is a translation. lupdate re-marks
                # entries "unfinished" whenever a source line moves, and
                # lrelease then drops them — the German text sat in the file
                # while the window stayed English.
                translation.attrib.pop("type", None)
                continue
            if source in german:
                translation.text = german[source]
                translation.attrib.pop("type", None)
                filled += 1
            else:
                missing.append(source)

    tree.write(TS, encoding="utf-8", xml_declaration=True)
    # ElementTree drops the doctype; Qt tolerates that, but keep the file
    # looking like the one Linguist writes so a human diff stays readable.
    text = TS.read_text(encoding="utf-8")
    if "<!DOCTYPE TS>" not in text:
        text = text.replace("?>", "?>\n<!DOCTYPE TS>", 1)
        TS.write_text(text, encoding="utf-8")
    return filled, missing


def compile_qm() -> None:
    result = subprocess.run([tool("pyside6-lrelease"), str(TS), "-qm", str(QM)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit("lrelease failed")
    print(result.stdout.strip() or "compiled")


def verify() -> None:
    """Load the result and translate one string, because a silent miss is the
    failure mode this whole script exists to avoid."""

    from PySide6.QtCore import QCoreApplication, QTranslator

    app = QCoreApplication.instance() or QCoreApplication([])
    translator = QTranslator()
    if not translator.load(str(QM)):
        raise SystemExit("the compiled %s does not load" % QM.name)
    app.installTranslator(translator)

    german = json.loads(GERMAN.read_text(encoding="utf-8")) if GERMAN.exists() else {}
    if not german:
        # Without the migration map, verify what the .ts itself claims.
        import html as html_module
        import xml.etree.ElementTree as ElementTree

        german = {}
        for message in ElementTree.parse(TS).getroot().iter("message"):
            source = message.findtext("source") or ""
            target = message.findtext("translation") or ""
            if source and target:
                german[html_module.unescape(source)] = html_module.unescape(target)
    checked = failed = 0
    for source, expected in german.items():
        if "%" in source or "\n" in source:
            continue        # formatted strings are checked by the test suite
        got = QCoreApplication.translate(CONTEXT, source)
        checked += 1
        if got != expected:
            failed += 1
            if failed <= 3:
                print("  no translation for %r -> %r" % (source, got))
    if failed:
        raise SystemExit("%d of %d strings did not translate" % (failed, checked))
    print("verified: %d strings translate into German" % checked)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true",
                        help="only list strings without a German translation")
    options = parser.parse_args()

    extract()
    filled, missing = fill()
    total = len(re.findall(r"<source>", TS.read_text(encoding="utf-8")))
    print("%d of %d strings translated" % (total - len(missing), total))

    if missing:
        print("\nWithout a German translation (%d):" % len(missing))
        for source in missing[:40]:
            print("  %r" % source)
        if len(missing) > 40:
            print("  … and %d more" % (len(missing) - 40))
    if options.report:
        return 1 if missing else 0

    compile_qm()
    verify()
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
