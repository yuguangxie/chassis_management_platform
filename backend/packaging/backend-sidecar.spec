# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

backend = Path(SPEC).resolve().parents[1]
datas = [(str(backend / "app" / "storage" / "schema.sql"), "app/storage")]
binaries = []
hiddenimports = collect_submodules("uvicorn") + ["win32print", "win32api", "win32con"]

for package in ("cantools", "reportlab", "fitz", "pymupdf", "docx"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(backend / "app" / "sidecar.py")],
    pathex=[str(backend)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="chassis-eol-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="chassis-eol-backend",
)
