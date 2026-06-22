# -*- mode: python ; coding: utf-8 -*-
"""
LoreKeeper — PyInstaller Spec File

Builds a standalone executable from main.py, bundling:
  - PySide6 (Qt for Python) with its dynamic Qt plugins
  - Pillow for image processing
  - SQLite (stdlib, included automatically)
  - All application modules: database/, ui/
  - Appdirs (optional, for default DB path)

Usage:
    pyinstaller lorekeeper.spec               # Clean build
    pyinstaller lorekeeper.spec --noconfirm    # Overwrite existing dist/

Output: dist/LoreKeeper/   (one-directory bundle)
      or dist/LoreKeeper    (single executable, see console=False)

Platform notes:
  - Linux:   Build on the oldest glibc you need to support.
  - Windows: Install PyInstaller via pip, run from cmd.exe.
  - macOS:   Build on macOS, codesign for distribution.

  The spec auto-detects the platform and sets appropriate flags.
"""

import os
import sys
import platform
from pathlib import Path

# ---------------------------------------------------------------------------
# Collect all hidden imports needed by PySide6, Pillow, and our app
# ---------------------------------------------------------------------------
HIDDEN_IMPORTS = [
    # PySide6 sub-modules
    "PySide6",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtXml",
    "PySide6.QtDBus",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtSerialPort",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    # shiboken6 (Python <-> C++ binding layer)
    "shiboken6",
    "shiboken6.Shiboken",
    # Our application modules
    "database",
    "database.manager",
    "database.schema",
    "database.models",
    "database.crud",
    "ui",
    "ui.theme",
    "ui.main_window",
    "ui.sidebar",
    "ui.article_view",
    "ui.form_builder",
    "ui.template_editor",
    "ui.default_templates",
    "ui.wiki_links",
    "ui.hover_preview",
    "ui.travel_map",
    "ui.search_dialog",
    "ui.link_autocomplete",
    "ui.backup_manager",
    # Optional but nice to have
    "appdirs",
]

# ---------------------------------------------------------------------------
# Platform-specific settings
# ---------------------------------------------------------------------------
SYSTEM = platform.system()

# Collect PySide6 Qt plugins (platform theme, image formats, styles, etc.)
# These are .so / .dll / .dylib files PySide6 ships in its own package data.
_qt_plugins = []
try:
    import PySide6
    pyside_dir = Path(PySide6.__file__).resolve().parent
    plugins_dir = pyside_dir / "Qt" / "plugins"
    if plugins_dir.is_dir():
        _qt_plugins.append(str(plugins_dir) + os.sep)
except Exception:
    pass

# Ensure we bundle shiboken6 libraries
_shiboken_libs = []
try:
    import shiboken6
    shiboken_dir = Path(shiboken6.__file__).resolve().parent
    _shiboken_libs.append(str(shiboken_dir))
except Exception:
    pass

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle PySide6 Qt plugins as binary data
        *[(p, "PySide6/Qt/plugins") for p in _qt_plugins],
    ],
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy / unused packages to reduce bundle size
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "transformers",
        "IPython",
        "jupyter",
        "notebook",
        "PIL.ImageShow",  # not needed headless
        "PIL.ImageQt",    # we use PySide6 natively
        "tkinter",
        "unittest",
        "pydoc",
        "test",
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# PyiCollect for Qt translations (optional, keeps .qm files)
# ---------------------------------------------------------------------------
# PySide6 ships translation files — we can include them for completeness.
# They live inside the PySide6 package, so they're normally collected.

# ---------------------------------------------------------------------------
# PYZ archive
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure, cipher=block_cipher)

# ---------------------------------------------------------------------------
# EXE (the main executable wrapper)
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LoreKeeper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # NOTE: console= is NOT set here - pass --windowed/--console on CLI instead.
    # PyInstaller passes CLI arguments into the spec namespace, so setting console
    # here AND via CLI causes a "multiple values" error.
)

# ---------------------------------------------------------------------------
# COLLECT (one-directory bundle — recommended for PySide6 apps)
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LoreKeeper",
)

# ---------------------------------------------------------------------------
# Optional: create an installer target (NSIS on Windows, app on macOS)
# For now, we only build the directory bundle.
# ---------------------------------------------------------------------------