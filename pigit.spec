# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for pigit onedir distribution (single `pigit` binary).

The pip console scripts `g` and `r` are just ``pigit cmd`` / ``pigit repo``
aliases; binary users recreate them in their shell, so the bundle ships one
executable. The version's single source is ``pigit.const.__version__`` (the
bundled ``pigit --version`` reports it).

onedir (not onefile): startup has no unzip step, preserving pigit's fast
launch. Distribute the collected directory as tar.gz/zip.
"""

import os
import tempfile

from pigit.const import __version__  # noqa: F401  (version single source)

# Entry wrapper is a build artifact; keep it in the OS temp dir so a
# root-owned checkout ``build/`` never blocks the build.
_ENTRIES_DIR = tempfile.mkdtemp(prefix="pigit-entries-")

# Modules pigit never needs; keeps the bundle lean. Tune after measuring size.
# ``email`` stays: http.client / urllib / importlib.metadata pull it in.
_EXCLUDES = [
    "tkinter",
    "_tkinter",
    "test",
    "unittest",
    "http.server",
]


def _entry_script() -> str:
    """Write the tiny ``__main__``-style wrapper and return its path."""
    os.makedirs(_ENTRIES_DIR, exist_ok=True)
    path = os.path.join(_ENTRIES_DIR, "pigit_entry.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "from pigit.console_scripts import main as _run\n"
            "if __name__ == '__main__':\n"
            "    _run()\n"
        )
    return path


pigit_script = _entry_script()

a = Analysis(
    scripts=[pigit_script],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

pigit_exe = EXE(
    pyz,
    [("pigit", pigit_script, "PYSOURCE")],
    [],
    exclude_binaries=True,
    name="pigit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    pigit_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pigit",
)
