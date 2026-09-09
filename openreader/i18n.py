"""Language selection and translation loading.

Source strings in this project are English, which is what Qt expects and what
appears when no translation is loaded. German is shipped as a translation
alongside, compiled to ``openreader_de.qm``.

Two translators get installed for a non-English language, not one: ours for the
application's own text, and Qt's ``qtbase`` for the strings Qt itself supplies —
the buttons in a message box, the file dialog's furniture. Without the second, a
German window ends up with English "OK" and "Cancel", which looks like an
oversight rather than a decision.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

#: Translation context for strings outside a QObject. Qt would otherwise use
#: the class name, which those modules do not have.
CONTEXT = "OpenReader"

#: Selectable languages: setting value, and the name shown in the settings
#: dialog. Language names stay in their own language by convention — a German
#: speaker looks for "Deutsch", not for "German".
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("system", ""),        # label filled in at runtime, since it is translated
    ("en", "English"),
    ("de", "Deutsch"),
)

#: Languages an actual translation file exists for. English is the source and
#: therefore needs none.
TRANSLATED = ("de",)

#: Kept alive for the life of the process: Qt does not take ownership of an
#: installed translator, and a garbage-collected one silently stops working.
_INSTALLED: list[QTranslator] = []


def translate(text: str, disambiguation: str | None = None) -> str:
    """Translate a string from code that is not a ``QObject``.

    Works before a ``QApplication`` exists — it then simply returns the source
    text, which is what the format parsers need when they are used from a
    script or a test.
    """

    return QCoreApplication.translate(CONTEXT, text, disambiguation)


#: Short alias; the parsers and other non-widget modules use this.
tr = translate


def resources_dir() -> str:
    """Where the compiled ``.qm`` files live, frozen or from source."""

    if getattr(sys, "frozen", False):
        # PyInstaller unpacks data files below _MEIPASS, mirroring the paths
        # given in the spec.
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "openreader", "resources", "i18n")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "i18n")


def system_language() -> str:
    """The shipped language closest to the system's, or the source language."""

    for name in QLocale.system().uiLanguages() or []:
        code = name.replace("-", "_").split("_")[0].lower()
        if code in TRANSLATED or code == "en":
            return code
    return "en"


def resolve(preference: str) -> str:
    """Turn a stored setting into the language actually to be used."""

    if preference in TRANSLATED or preference == "en":
        return preference
    return system_language()


def install(preference: str = "system") -> str:
    """Load the translations for ``preference`` and return the language used.

    Any previously installed translator is removed first, so switching language
    at runtime does not leave the old one underneath.
    """

    application = QCoreApplication.instance()
    if application is None:
        return resolve(preference)

    for translator in _INSTALLED:
        application.removeTranslator(translator)
    _INSTALLED.clear()

    language = resolve(preference)
    if language == "en":
        return language     # English is the source; nothing to load

    ours = QTranslator()
    if ours.load("openreader_%s" % language, resources_dir()):
        application.installTranslator(ours)
        _INSTALLED.append(ours)

    # Qt's own strings. The bundled build ships only the languages we
    # translate; from source, Qt's full set is available where PySide6 put it.
    qt_base = QTranslator()
    for directory in (resources_dir(), QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        if directory and qt_base.load("qtbase_%s" % language, directory):
            application.installTranslator(qt_base)
            _INSTALLED.append(qt_base)
            break

    return language


def language_label(code: str) -> str:
    """Name for the settings dialog."""

    if code == "system":
        # Written as tr(), not translate(): lupdate looks for the name it knows,
        # and a call it does not recognise never reaches the .ts at all — the
        # string then stays English however complete the translation looks.
        return tr("Use system language")
    for value, label in LANGUAGES:
        if value == code:
            return label
    return code
