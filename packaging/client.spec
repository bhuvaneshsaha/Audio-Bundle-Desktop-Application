# -*- mode: python ; coding: utf-8 -*-
"""Standalone Client application. Build: pyinstaller packaging/client.spec"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"

datas, binaries, hiddenimports = collect_all("PySide6")
hiddenimports += [
    "argon2",
    "argon2.low_level",
    "cryptography",
    "audio_bundle",
    "audio_bundle.client",
    "audio_bundle.core",
    "PySide6.QtMultimedia",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
]

a = Analysis(
    [str(Path(SPECPATH) / "run_client.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AudioBundleClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
)
