# rbGyanX 1.0 — Desktop (Windows)

## What you get

- **rbGyanX** desktop app: Tkinter GUI + bundled **rbgyanx-engine**
- **BASIC** — clinic: DICOM TCP/NTCP, UTCP, QUANTEC, physical dose / plan-quality indices, PDF summary, no ML augmentation
- **ADVANCED** — research: TCP ML (XGBoost / RF / LightGBM), outcomes CSV, Ask rbGyanX
- Legacy **code1–7** for TPS text DVH, NTCP ML/SHAP, integration (P+, CFTC) when those options are enabled

## For clinicians (no Python)

### Recommended: Windows installer

1. Run the installer **`rbGyanX-<version>-Qt-Setup.exe`** (from your IT team, from the
   [latest release](https://github.com/kalyan2031990/rbGyanX/releases/latest), or from
   `dist\` after a local build). The version in the file name is whichever release you
   downloaded; it is not written out here because a pinned example goes stale at the next
   release.
2. Follow the wizard (license → folder → optional desktop shortcut).
3. Launch **rbGyanX** from the Start Menu.

Uninstall: **Settings → Apps → rbGyanX → Uninstall**.

### Portable folder (no installer)

1. Unzip the **`dist\rbGyanX`** folder (must include `engine_bundle\`).
2. Double-click **`rbGyanX.exe`**.
3. Choose **DICOM RT** input → browse to patient/cohort folder.
4. Set output folder → run workflow steps.
5. Open **`tcp_benchmarking.xlsx`** (UTCP columns), **`ntcp_benchmarking.xlsx`** (QUANTEC_Flags sheet), **`plan_quality_summary.xlsx`** (Target_Indices, OAR_Indices, Integral_Dose), and **`patient_plan_summary.pdf`**.

## For developers

```powershell
cd <REPO_ROOT>
.\Install-rbGyanX.ps1
python rbgyanx_gui.py
```

Build portable app + Windows installer:

```powershell
.\packaging\build_rbGyanX.ps1 -BuildInstaller
# Portable: dist\rbGyanX\rbGyanX.exe
# Installer: dist\rbGyanX-<version>-Qt-Setup.exe
```

Installer only (after app already built):

```powershell
.\packaging\build_installer.ps1
```

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php) (`ISCC.exe` on PATH or default install location).

**Build Python:** default installer build **includes TensorFlow 2.15** (for SHAP deep explainers and future DL). TensorFlow requires **Python 3.10–3.12**; the build script auto-selects `py -3.10` if your default Python is 3.13+.

```powershell
# Full installer (TensorFlow bundled) — default
.\packaging\build_rbGyanX.ps1 -BuildInstaller

# Lean installer (~smaller, no TensorFlow)
.\packaging\build_rbGyanX.ps1 -BuildInstaller -IncludeTensorFlow:$false
```

After build, check `dist\rbGyanX\build_manifest.json` for `"include_tensorflow": true`.

**Clinical TCP/NTCP/UTCP/QUANTEC do not require TensorFlow** (XGBoost + sklearn only). TensorFlow is optional infrastructure in the full build.

## Engine resolution

The app finds the engine in this order:

1. `RBGYANX_ENGINE_PATH` environment variable  
2. `engine_bundle\` next to the exe (shipped build)  
3. Sibling folder `..\rbGyanX_cdss` (development)

## Disclaimer

Decision-support and research software — not a substitute for clinical judgment. ML outputs require adequate cohort size and real outcome data; see safety annotations in Model_Performance when ADVANCED ML is run.
