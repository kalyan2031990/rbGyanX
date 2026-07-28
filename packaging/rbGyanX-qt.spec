# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the rbGyanX **Qt6** desktop app (v2 Phase 4 · Slice 3).

Deliberately SEPARATE from ``rbGyanX.spec`` (the Tkinter app), which still ships and must not
be disturbed while the Qt migration is incremental.

Key difference: QtWebEngine. The interactive Plotly views are hosted in a ``QWebEngineView``,
so the build must carry ``QtWebEngineProcess`` plus its resources and locales — ``collect_all``
pulls those in. Verified by ``tests/test_qt_packaging.py``.

    pyinstaller packaging/rbGyanX-qt.spec --noconfirm
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

# ---------------------------------------------------------------- data files
datas = []
for name in ("assets", "config"):  # keep the existing rbGyanX branding + site params
    folder = ROOT / name
    if folder.is_dir():
        datas.append((str(folder), name))

# ---------------------------------------------------------------- Qt + engine
binaries = []
hiddenimports = [
    "rbgyanx",
    "rbgyanx.qtapp",
    "rbgyanx.qtapp.main_window",
    "rbgyanx.qtapp.branding",
    "rbgyanx.services",
    "rbgyanx.services.run_controller",
    "rbgyanx.services.dvh_service",
    "rbgyanx.viz",
    "rbgyanx.viz.plotly_backend",
    "rbgyanx.viz.matplotlib_backend",
    "rbgyanx_engine",
    "dicom_io.txt_dvh_reader",
    "validation.ntcp_benchmark",
    "radiobiology",
    "pydicom",
    "plotly",
    "yaml",
]

# QtWebEngine ships a helper process (QtWebEngineProcess.exe) plus .pak resources and locales;
# all are required at runtime or the embedded plot renders as a blank window.
#
# NOTE: collect from the "PySide6" PACKAGE, not from PySide6.QtWebEngineCore — the latter is a
# module, so PyInstaller skips data/binary collection for it with only a warning and the build
# silently ships without the helper process. tests/test_qt_packaging.py pins this.
for module in ("PySide6", "plotly"):
    _d, _b, _h = collect_all(module)
    datas += _d
    binaries += _b
    hiddenimports += _h

# Keep the Qt modules we actually use as explicit hidden imports.
hiddenimports += [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
]

block_cipher = None

a = Analysis(
    [str(ROOT / "rbgyanx" / "qtapp" / "__main__.py")],
    pathex=[str(ROOT), str(ROOT / "engine")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The Qt run path is: DVH parse -> engine LKB/RS NTCP -> RandomForest -> Plotly/Matplotlib,
    # plus the ADVANCED xAI view (SHAP over the RandomForest TCP model). Everything below is an
    # OPTIONAL research/ML extra or a Tk-only dependency the Qt app never imports. Excluding them
    # keeps the analysis tractable (the first attempt scanned the full sympy/ML graph and was
    # killed after 18 min) and the installer small.
    #
    # shap is deliberately NOT excluded: the SHAP/xAI view ships in the packaged app (verified by
    # the frozen-exe self-test). This shap version imports numba unconditionally, so numba +
    # llvmlite must ship too — a frozen build that excluded them raised ModuleNotFoundError:
    # 'numba' the moment TreeExplainer ran. They are NOT in the excludes list below.
    excludes=[
        "tkinter",
        "tensorflow",
        "torch",
        "xgboost",
        "lightgbm",
        "lime",
        # NOTE: lifelines (cox_regression.py, top-level) and skimage (via dicompylercore,
        # needed for DICOM DVH extraction) are genuine engine imports — do NOT exclude them.
        # numba + llvmlite are also kept in: shap needs numba at import/compute time.
        "sympy",
        "statsmodels",
        "seaborn",
        "pymc",
        "arviz",
        "bokeh",
        "cv2",
        "IPython",
        "notebook",
        "sphinx",
        "pytest",
        "PyQt5",
        "PyQt6",
    ],
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
    name="rbGyanX-Qt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "icon.png") if (ROOT / "assets" / "icon.png").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="rbGyanX-Qt",
)
