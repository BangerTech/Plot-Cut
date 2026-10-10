# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('plot_cut')

# .ico is the Windows icon. macOS wants .icns; Linux ignores the icon.
icon = 'assets/logo.ico' if sys.platform == 'win32' else None


a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('assets/logo.png', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Plot Cut',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=icon,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS startet Qt zuverlaessig aus einem App-Bundle.
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Plot Cut.app',
        icon=None,
        bundle_identifier='com.bangertech.plotcut',
    )
