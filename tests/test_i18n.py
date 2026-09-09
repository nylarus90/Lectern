"""Guards for the translation setup.

The valuable test here is the last one: it walks every source file and reports
German text that is not inside a ``tr()`` call. Converting roughly 240 strings
by hand loses some — the first attempt missed two in a single file — and a
half-translated window is worse than an untranslated one, because the misses
look like bugs rather than a missing language.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
#: Editor backup folders are not part of the project.
SOURCES = sorted(p for p in (ROOT / "openreader").rglob("*.py")
                 if "_versions" not in p.parts)

#: Characters and words that only appear in German text. Deliberately narrow:
#: this is a net for prose, not a language detector, and a false positive costs
#: a maintainer more than a missed string costs a reader.
GERMAN_MARKERS = (
    "ä", "ö", "ü", "Ä", "Ö", "Ü", "ß",
    " der ", " die ", " das ", " ein ", " eine ", " nicht ", " kann ",
    " wurde ", " werden ", " wird ", " sich ", " keine ", " mit ",
    "Datei", "Buch", "Seite", "Kapitel", "Fehler", "Einstellung",
)

#: Strings that are German-looking but must stay as they are.
ALLOWED = {
    "Deutsch",          # a language name stays in its own language
}


def _looks_german(text: str) -> bool:
    if text in ALLOWED or len(text) < 4:
        return False
    padded = " %s " % text
    return any(marker in (text if len(marker) == 1 else padded)
               for marker in GERMAN_MARKERS)


class _StringVisitor(ast.NodeVisitor):
    """Collects string constants, remembering which ones are inside tr()."""

    def __init__(self) -> None:
        self.translated: set[int] = set()      # id() of nodes passed to tr()
        self.strings: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 - ast naming
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name in ("tr", "translate", "trUtf8"):
            for argument in node.args:
                self.translated.add(id(argument))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802 - ast naming
        if isinstance(node.value, str) and id(node) not in self.translated:
            self.strings.append((node.lineno, node.value))


def _untranslated(path: pathlib.Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # Docstrings are documentation, not interface text.
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))

    visitor = _StringVisitor()
    visitor.visit(tree)
    return [
        (line, text) for line, text in visitor.strings
        if _looks_german(text)
        and id(text) not in docstrings
        and not any(line == d for d in ())
    ]


def test_marker_detection_is_sane():
    """The net must catch prose and leave code alone."""

    assert _looks_german("Die Datei wurde nicht gefunden")
    assert _looks_german("Buch schließen")
    assert not _looks_german("utf-8")
    assert not _looks_german("The file was not found")
    assert not _looks_german("Deutsch")


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_untranslated_german_strings(path):
    """Every German string must sit inside tr(), or the language switch lies."""

    findings = _untranslated(path)
    if findings:
        listing = "\n".join("  line %d: %r" % (line, text) for line, text in findings)
        pytest.fail(
            "%s carries German text outside tr():\n%s"
            % (path.relative_to(ROOT), listing)
        )


def test_translation_file_is_loadable(tmp_path):
    """A compiled .qm must exist and actually install."""

    pytest.importorskip("PySide6.QtCore")
    from PySide6.QtCore import QTranslator

    from openreader import i18n

    qm = pathlib.Path(i18n.resources_dir()) / "openreader_de.qm"
    if not qm.exists():
        pytest.skip("openreader_de.qm not built yet (run build/make_translations.py)")
    translator = QTranslator()
    assert translator.load(str(qm)), "the compiled translation refuses to load"


def test_language_resolution():
    from openreader import i18n

    assert i18n.resolve("de") == "de"
    assert i18n.resolve("en") == "en"
    # Anything unknown, including "system", ends at a language we actually ship.
    assert i18n.resolve("system") in ("de", "en")
    assert i18n.resolve("klingon") in ("de", "en")
