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
    # plus the ADVANCED xAI view, which renders SHAP values only if something hands it some (see
    # the shap note below). Everything below is an OPTIONAL research/ML extra or a Tk-only
    # dependency the Qt app never imports. Excluding them keeps the analysis tractable (the first
    # attempt scanned the full sympy/ML graph and was killed after 18 min) and the installer small.
    #
    # shap, numba and llvmlite are NOT bundled, deliberately. An earlier version of this comment
    # claimed the opposite, and nothing enforced either claim, so it stood unchallenged until the
    # shipped v1.3.0 installer was inspected by hand.
    #
    # Why they are absent: shap is declared in the "ml" extra only, while this installer is built
    # with `pip install -e "./engine" -e ".[qt]"` (.github/workflows/release.yml). shap is simply
    # not in the build environment, so PyInstaller cannot collect it; numba and llvmlite were only
    # ever shap's dependencies and so are absent too. "shap" is now also listed in excludes below,
    # to make that a guarantee rather than a side effect of the install line.
    #
    # Why that is correct: no user-reachable code path imports shap. ml_models and xai ARE bundled
    # (both are in the embedded PYZ), but ml_models/random_forest_tcp.py imports shap lazily under
    # `if compute_shap:` inside try/except, so a missing shap degrades to shap_values=None plus the
    # warning "SHAP computation failed: No module named 'shap'" — the RandomForest itself still
    # trains, since sklearn ships. engine/xai/shap_tcp.py only plots values handed to it and never
    # imports shap at all.
    #
    # What the packaged SHAP/xAI view therefore shows: its documented placeholder, not fabricated
    # attributions. VisualisationScreen.set_ml_result() is the only way to populate that view, and
    # nothing in the app calls it (sole caller: tests/test_qtapp_smoke.py). Bundling shap would
    # drag numba + llvmlite into an already ~872 MB install to fill a view that would stay empty.
    #
    # _selftest_shap() in rbgyanx/qtapp/main_window.py matches this design: a cleanly absent shap
    # is a PASS, while a shap that is present but cannot compute — including a half-bundled one,
    # e.g. shap without numba — is a FAIL. The release workflow runs that frozen self-test right
    # after the freeze and fails the job on a non-zero exit, which is what now pins all of the
    # above. Same "assert it, do not assume it" pattern as the QtWebEngine note further up.
    excludes=[
        "tkinter",
        "tensorflow",
        "torch",
        "xgboost",
        "lightgbm",
        "lime",
        # shap: see the long note above. Excluded explicitly so that a future change to the
        # build's install line cannot silently pull shap — and with it numba + llvmlite — back in.
        "shap",
        # NOTE: lifelines (cox_regression.py, top-level) and skimage (via dicompylercore,
        # needed for DICOM DVH extraction) are genuine engine imports — do NOT exclude them.
        # numba + llvmlite need no entry here: with shap gone, nothing bundled imports them.
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
