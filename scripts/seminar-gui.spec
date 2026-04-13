# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


spec_dir = Path(SPECPATH).resolve()
project_root = spec_dir
for candidate in (spec_dir, spec_dir.parent, spec_dir.parent.parent):
    if (candidate / "python" / "seminar_gui.py").exists():
        project_root = candidate
        break
python_root = project_root / "python"

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "docs"), "docs"),
    (str(python_root / "seminar.config.example.json"), "."),
]
binaries = []
hiddenimports = []

for package_name in ("PySide6", "qfluentwidgets", "shiboken6"):
    collected_datas, collected_binaries, collected_hiddenimports = collect_all(package_name)
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hiddenimports


a = Analysis(
    [str(python_root / "seminar_gui.py")],
    pathex=[str(python_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="xauat-seminar-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "xauat-emblem.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="xauat-seminar-gui",
)
