# -*- mode: python ; coding: utf-8 -*-
# rbGyanX 1.0 — PyInstaller spec (one-folder distribution)
# Set RBGYANX_INCLUDE_TENSORFLOW=1 when building the full installer (Python 3.10–3.12).
import os
import sys
from pathlib import Path

INCLUDE_TENSORFLOW = os.environ.get("RBGYANX_INCLUDE_TENSORFLOW", "0").strip() in (
    "1",
    "true",
    "yes",
)

block_cipher = None
SPEC_DIR = Path(SPECPATH)
DUAL_ROOT = SPEC_DIR.parent
BUNDLE = DUAL_ROOT / "engine_bundle"
HOOKS = SPEC_DIR / "hooks"

datas = []
binaries = []
pathex = [str(DUAL_ROOT)]
if BUNDLE.is_dir():
    pathex.append(str(BUNDLE))
    cfg = BUNDLE / "config"
    if cfg.is_dir():
        datas.append((str(cfg), "config"))

for name in ("config", "utils", "qa", "ai", "core", "rbgyanx", "docs"):
    folder = DUAL_ROOT / name
    if folder.is_dir():
        datas.append((str(folder), name))

for pattern in ("code*.py", "VERSION.txt", "requirements.txt"):
    for item in DUAL_ROOT.glob(pattern):
        if item.is_file():
            datas.append((str(item), "."))

hiddenimports = [
    "rbgyanx",
    "rbgyanx.logic",
    "rbgyanx.logic.engine_bridge",
    "rbgyanx.logic.pipeline",
    "rbgyanx.logic.mode_controller",
    "rbgyanx.paths",
    "rbgyanx.version",
    "rbgyanx_engine",
    "rbgyanx_engine.engine",
    "rbgyanx_engine.run_config",
    "pydicom",
    "pydicom.encoders",
    "pydicom.encoders.gdcm",
    "sklearn",
    "sklearn.utils._typedefs",
    "sklearn.neighbors._quad_tree",
    "xgboost",
    "lightgbm",
    "shap",
    "openpyxl",
    "yaml",
    "scipy.special.cython_special",
    "matplotlib.backends.backend_tkagg",
]

if INCLUDE_TENSORFLOW:
    hiddenimports.extend(
        [
            "tensorflow",
            "tensorflow.python",
            "tensorflow.python.framework",
            "tensorflow.python.platform",
        ]
    )
    try:
        from PyInstaller.utils.hooks import collect_all

        _tf_datas, _tf_binaries, _tf_hidden = collect_all("tensorflow")
        datas += _tf_datas
        binaries += _tf_binaries
        hiddenimports += _tf_hidden
    except Exception as exc:
        print(f"WARNING: collect_all(tensorflow) failed: {exc}", file=sys.stderr)

_common_excludes = [
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "IPython",
    "jupyter",
    "notebook",
    "sphinx",
    "pytest",
    "PyQt5.QtCore",
    "PyQt6.QtCore",
]
_pyinstaller_excludes = list(_common_excludes)
if not INCLUDE_TENSORFLOW:
    _pyinstaller_excludes.extend(["tensorflow", "torch", "tensorflow_intel"])
else:
    _pyinstaller_excludes.extend(["torch", "torchvision", "torchaudio"])

a = Analysis(
    [str(DUAL_ROOT / "rbgyanx_gui.py")],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(HOOKS / "rthook_rbgyanx_paths.py")],
    excludes=_pyinstaller_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="rbGyanX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="rbGyanX",
)
