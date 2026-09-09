# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for a self-contained OpenReader executable.

The point of this file is what it *excludes*.  A default PySide6 bundle drags in
QtWebEngine, Qt3D, QtQuick, the SQL drivers and every translation, which turns a
90 MB reader into a 400 MB download.  OpenReader uses Qt Widgets, Qt PDF and
nothing else, so everything else is dropped explicitly.

    pyinstaller build/openreader.spec --noconfirm
"""

import os
import sys

BLOCK_CIPHER = None
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))

#: Qt modules the reader genuinely uses.  Everything else in PySide6 is excluded.
EXCLUDED_QT = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtQuickControls2", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtSensors",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtHelp",
    "PySide6.QtSql", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtHttpServer",
    "PySide6.QtNetworkAuth", "PySide6.QtTextToSpeech", "PySide6.QtVirtualKeyboard",
    "PySide6.QtPdfQuick", "PySide6.QtSvgWidgets",
]

EXCLUDED_MODULES = [
    "tkinter", "unittest", "pydoc_data", "test", "distutils", "setuptools",
    "pip", "lib2to3", "email.test", "numpy", "PIL", "matplotlib", "pytest",
    "shiboken6.support",
]

analysis = Analysis(
    [os.path.join(ROOT, "build", "entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=["PySide6.QtPdf", "PySide6.QtPdfWidgets"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED_QT + EXCLUDED_MODULES,
    cipher=BLOCK_CIPHER,
    noarchive=False,
)


def _unwanted(name: str) -> bool:
    """Drop Qt payload the reader never touches.

    Translations alone are ~20 MB and Qt loads its own English strings without
    them; the QML and WebEngine trees are dead weight once the modules above are
    excluded.
    """

    lowered = name.lower().replace("\\", "/")
    for marker in (
        "/translations/", "qt6webengine", "qtwebengine", "/qml/", "qt6quick",
        "qt6qml", "qt63d", "qt6charts", "qt6datavis", "qt6multimedia",
        "qt6designer", "qt6test", "qt6sql", "opengl32sw", "d3dcompiler",
        "/sqldrivers/", "libvulkan", "qt6virtualkeyboard", "qt6texttospeech",
    ):
        if marker in lowered:
            return True
    return False


analysis.binaries = TOC([entry for entry in analysis.binaries if not _unwanted(entry[0])])
analysis.datas = TOC([entry for entry in analysis.datas if not _unwanted(entry[0])])


def _translations():
    """The application's own .qm plus the one Qt translation worth carrying.

    Added *after* the filter above, deliberately: that filter drops everything
    under a ``translations`` directory to keep Qt's 60 MB of languages out of a
    36 MB download, and it would take these with it. What survives is our own
    file and ``qtbase_de.qm`` — 220 KB, and without it a German window ends up
    with English "OK" and "Cancel" in every standard dialog.
    """

    entries = []
    own = os.path.join(ROOT, "openreader", "resources", "i18n")
    if os.path.isdir(own):
        for name in sorted(os.listdir(own)):
            if name.endswith(".qm"):
                entries.append((os.path.join("openreader", "resources", "i18n", name),
                                os.path.join(own, name), "DATA"))

    try:
        import PySide6

        qt_translations = os.path.join(os.path.dirname(PySide6.__file__), "translations")
    except ImportError:
        return entries
    for name in ("qtbase_de.qm",):
        source = os.path.join(qt_translations, name)
        if os.path.exists(source):
            entries.append((os.path.join("openreader", "resources", "i18n", name),
                            source, "DATA"))
    return entries


def _licences():
    """The licence texts, carried inside every build.

    Three of the four release files are a single executable. A licence text
    that exists only in the repository does not accompany those in any sense
    the GPL or the LGPL would recognise, and Help → Licences has nothing to
    show. A missing file stops the build rather than producing a package that
    quietly ships without one.
    """

    entries = []
    for name, source in (("GPL-3.0.txt", os.path.join(ROOT, "LICENSE")),
                         ("LGPL-3.0.txt",
                          os.path.join(ROOT, "licenses", "LGPL-3.0.txt"))):
        if not os.path.exists(source):
            raise SystemExit("Lizenztext fehlt: %s" % source)
        entries.append((os.path.join("openreader", "resources", "licenses", name),
                        source, "DATA"))
    return entries


analysis.datas = TOC(list(analysis.datas) + _translations() + _licences())

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=BLOCK_CIPHER)

ICON = None
if sys.platform == "win32" and os.path.exists(os.path.join(ROOT, "build", "icon.ico")):
    ICON = os.path.join(ROOT, "build", "icon.ico")
elif sys.platform == "darwin" and os.path.exists(os.path.join(ROOT, "build", "icon.icns")):
    ICON = os.path.join(ROOT, "build", "icon.icns")

#: One file or one directory.  The single file is what makes the download
#: portable — copy it to a stick and it runs — but it unpacks itself into a
#: temporary directory on every launch.  An installed copy has no such
#: constraint and should not pay that cost, so the installer build sets
#: ``OPENREADER_ONEDIR=1``.
ONEDIR = os.environ.get("OPENREADER_ONEDIR") == "1"

COMMON = dict(
    name="OpenReader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # A reader is a GUI program: no console window should flash up on Windows.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=sys.platform == "darwin",
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

if ONEDIR:
    executable = EXE(pyz, analysis.scripts, [], exclude_binaries=True, **COMMON)
    collected = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        name="OpenReader",
    )
else:
    executable = EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        runtime_tmpdir=None,
        **COMMON,
    )

if sys.platform == "darwin":
    app = BUNDLE(
        executable,
        name="OpenReader.app",
        icon=ICON,
        bundle_identifier="org.openreader.app",
        info_plist={
            "CFBundleName": "OpenReader",
            "CFBundleDisplayName": "OpenReader",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "CFBundleDocumentTypes": [
                {
                    "CFBundleTypeName": "E-Book",
                    "CFBundleTypeRole": "Viewer",
                    "LSHandlerRank": "Alternate",
                    "CFBundleTypeExtensions": [
                        "epub", "mobi", "azw", "azw3", "prc", "fb2", "fbz",
                        "cbz", "cbr", "cb7", "cbt", "pdf", "txt", "md", "rtf",
                        "html", "htm", "xhtml",
                    ],
                }
            ],
        },
    )
