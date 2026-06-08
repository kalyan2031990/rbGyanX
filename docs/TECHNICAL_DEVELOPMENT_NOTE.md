# rbGyanX 2.0 — Technical Development Note

**Author:** Kalyan Mondal  
**Repository:** [https://github.com/kalyan2031990/rbGyanX](https://github.com/kalyan2031990/rbGyanX)  
**Purpose:** Step-by-step development history, architecture, philosophy, synthetic validation strategy, test suites, and known limitations — from first NTCP research code through the current unified monorepo.

**Audience:** External reviewers, collaborators, journal supplementary material, and AI-assisted code audit.

**Desktop installer (not in Git — build locally):**  
`packaging/build_rbGyanX.ps1 -BuildInstaller` → `dist/rbGyanX-1.0.0-full-Setup.exe`

---

## 1. Executive summary

**rbGyanX** is a radiobiology-guided clinical decision support system (CDSS) for radiation oncology. It integrates:

| Pillar | Content |
|--------|---------|
| **Physical dosimetry** | DICOM DVH metrics, plan-quality indices (HI, CI, D95), integral dose |
| **Classical radiobiology** | Multi-model TCP (Poisson, Zaider–Minerbo, gEUD, logistic) and NTCP (LKB log-logistic, LKB probit, Relative Seriality) |
| **Composite endpoints** | UTCP (Källman-style), QUANTEC 2010 constraint checker |
| **Research extensions (ADVANCED)** | ML/XAI, dosiomics, PINN stub + training, Bayesian NTCP inference |
| **Delivery** | Windows Tkinter GUI + `rbgyanx-engine` CLI + optional PyInstaller/Inno Setup installer |

The product is **decision support**, not autonomous treatment planning or regulated SaMD unless separately validated.

**Design mantra** (from `docs/RBGYANX_MANIFESTO.md`):

> Does this help humans understand where radiobiological reasoning is reliable, fragile, or invalid?

---

## 2. Concept and philosophy

### 2.1 What rbGyanX is — and is not

| rbGyanX **is** | rbGyanX **is not** |
|----------------|-------------------|
| A governed scientific framework for plan review | A TPS replacement (Eclipse, RayStation, etc.) |
| Physics-first, auditable TCP/NTCP | A black-box deep-learning NTCP product |
| BASIC = clinic-safe classical models | An AI automation platform |
| ADVANCED = opt-in research infrastructure | Default clinical posture with unvalidated ML |

### 2.2 Core principles

1. **Engine before GUI** — Radiobiology math lives in `engine/` with unit tests; GUI and legacy scripts call the engine, not the reverse.
2. **Clinic-first input** — DICOM RT (RTPLAN, RTDOSE, RTSTRUCT) is primary; TPS DVH text is secondary via `input_kind=dvh_txt` or legacy `code3`/`code6`.
3. **Site-aware parameters** — Anatomical site (HN, LUNG, PROSTATE, …) drives YAML parameter packs; technique (IMRT/SBRT) modulates plan-quality indices only.
4. **Additive evolution** — New features add columns, sheets, and optional packages; they do not silently replace LKB/Poisson implementations.
5. **Traceability** — Every engine run writes `provenance.json`, `qa_report.json`, and structured Excel/CSV/PDF outputs.
6. **Explicit uncertainty** — Monte Carlo parameter sampling (BASIC/ADVANCED), bootstrap CIs on validation metrics, Bayesian NTCP posteriors (ADVANCED Part F).

### 2.3 BASIC vs ADVANCED contract

| | **BASIC** | **ADVANCED** |
|---|-----------|--------------|
| TCP/NTCP models | Classical only | Classical + registry plugins |
| ML | Off by default (`enable_ml=False`) | Opt-in with outcome CSV |
| Dosiomics / 3D dose | No | `engine_advanced/` |
| PINN / Bayesian NTCP | No | `engine_advanced_f/` |
| Intended use | Routine physicist review | Protocol development, publication |

---

## 3. Architecture (current monorepo)

```
project_rbGyanx/                    # GitHub: kalyan2031990/rbGyanX
├── rbgyanx_gui.py                  # Tkinter desktop entry
├── rbgyanx/                        # App logic (engine_bridge, modes, input router)
├── code1 … code7                   # Legacy TPS / ML / P+ integration scripts
├── engine/                         # rbgyanx-engine — CLINIC core (Parts A, C, D)
│   ├── rbgyanx_engine/             # run_analysis(), RunConfig, CLI
│   ├── dicom_io/                   # DICOM reader, site detector, DVH extraction
│   ├── radiobiology/               # TCP, NTCP, UTCP, uncertainty
│   ├── validation/                 # QUANTEC, calibration, publication metrics
│   ├── config/                     # Site YAML (TCP + NTCP + plan quality)
│   └── tests/                      # ~171 engine unit/integration tests
├── engine_advanced/                # ADVANCED Parts B & E
│   └── rbgyanx_advanced/           # PINN registry, dosiomics, clinical covariates
├── engine_advanced_f/              # ADVANCED Part F
│   └── rbgyanx_advanced_f/         # Bayesian NTCP + full PINN training
├── tests/                          # GUI, legacy, publication suite (~129 + integration)
├── test_data/                      # README + dicom_input placeholder (no PHI in Git)
├── scripts/run_all_tests.ps1       # Full CI-style test runner
├── packaging/                      # PyInstaller + Inno Setup
└── docs/                           # Manifesto, roadmap, outcome schema, this note
```

### 3.1 Engine resolution at runtime

Order in `rbgyanx/paths.py`:

1. `RBGYANX_ENGINE_PATH` environment variable  
2. `<app_root>/engine_bundle` (shipped with PyInstaller build)  
3. `<app_root>/engine` (monorepo dev layout)

### 3.2 Data flow (DICOM, BASIC)

```
DICOM folder → site_detector → TCP rows (targets) + NTCP rows (OARs)
            → optional UTCP (endpoint=both)
            → QUANTEC flags + plan-quality metrics
            → Excel/CSV/PDF + provenance.json
```

### 3.3 Key outputs

| Artifact | Content |
|----------|---------|
| `tcp_benchmarking.xlsx` | TCP models; UTCP when NTCP available |
| `ntcp_benchmarking.xlsx` | NTCP summary + QUANTEC_Flags sheet |
| `plan_quality_summary.xlsx` | Target/OAR indices, integral dose |
| `validation_metrics.xlsx` | AUC, Brier, Hosmer–Lemeshow, ECE (with outcome CSV) |
| `bayesian_ntcp_summary.csv` | Posterior TD50/m summaries (ADVANCED Part F) |
| `cohort_features.csv` | ML feature matrix (ADVANCED + outcome CSV) |

---

## 4. Step-by-step development history

### Phase A — NTCP research pipeline (GitHub origin)

- Open NTCP pipeline: LKB log-logistic/probit, Relative Seriality, organ YAML parameters.
- Established: structure aliasing, Excel reporting, cohort analysis patterns.
- Lineage repos: `NTCP_Analysis_Pipeline`, `py_ntcpx`.

### Phase B — py_ntcp → TCP extension

- Unified TCP+NTCP research platform.
- Added Poisson TCP, gEUD, Zaider–Minerbo, ML hooks (XGBoost, RF, LightGBM).
- Modular layout: `dicom_io/`, `radiobiology/`, `config/`, `validation/`.

### Phase C — py_tcpx nine-phase program

Structured TCP engine delivery:

1. DICOM ingestion (dicompyler-core)  
2. Structure mapping + site detection  
3. Classical TCP + site YAML  
4. Monte Carlo uncertainty  
5. ML cohort features + EPV guards  
6. XAI (SHAP, LIME, PDP/ICE)  
7. Validation (calibration, cohort metrics)  
8. Reporting workbooks  
9. Single `run_analysis()` CLI contract  

### Phase D — API harmonisation (py_ntcp ↔ py_tcpx)

- Shared `RunConfig` / `EngineResult`, common DICOM reader.
- Single engine for `endpoint: tcp | ntcp | both`.

### Phase E — rbGyanX_cdss (public engine core)

- UTCP (Källman-style, site OAR maps including LUNG_CONV)
- QUANTEC 2010 checker + pelvic organs (Rectum, Bladder, Liver)
- Clinical safety guard for ML, plan-quality physical layer
- StratifiedGroupKFold when patient IDs available

### Phase F — rbgyanx_dual (private GUI)

- Tkinter workflow, BASIC/ADVANCED modes, engine_bridge
- Legacy code1–7 for TPS fractional DVH, NTCP ML/SHAP, P+/CFTC (code7)
- PyInstaller + Inno Setup packaging

### Phase G — project_rbGyanx monorepo (v1.0 desktop freeze)

Merged `rbgyanx_dual` + `rbGyanX_cdss` + test assets into one tree.

### Phase H — CURSOR_FIXES implementation (Parts A–F, 2026)

Systematic hardening documented in `CURSOR_FIXES.md` and `docs/IMPLEMENTATION_ROADMAP.md`:

| Part | Scope | Package |
|------|-------|---------|
| **A** §1–15 | Site detection safety, NTCP NaN guards, DVH normalisation, UTCP lung map, re-exports | `engine/` |
| **B** §16–21 | Clinical covariates, DVH shape features, model registry, PINN stub, 3D dose stub | `engine_advanced/` |
| **C** §22–23 | Prostate/pelvic/liver YAML, publication validation metrics | `engine/` |
| **D** §24–26 | ΔNTCP plan comparison, MLE NTCP calibration, outcome schema | `engine/` |
| **E** §27–28 | 3D dose extraction + dosiomics (synthetic fallback without pydicom) | `engine_advanced/` |
| **F** §29–30 | Bayesian NTCP (bootstrap/PyMC) + PINN training loop | `engine_advanced_f/` |

### Phase I — CURSOR_FINAL_FIXES (2026)

Production hygiene (`CURSOR_FINAL_FIXES.md`):

- **FIX-1:** pytest `importlib` mode; moved `engine/conftest.py` to resolve `tests.conftest` collision  
- **FIX-2:** Graceful skip for xgboost, lightgbm, lifelines when not installed  
- **FIX-3:** Bootstrap CI diversity guards in `ntcp_calibration.py`  
- **FIX-4:** `test_data/` README + `.gitkeep` (no PHI in repository)  
- **FIX-5:** Bytecache cleanup in build/test scripts  
- **FIX-6:** `Brier_95CI` and `cal_adequate` in validation dict output  

---

## 5. Synthetic data and validation strategy

### 5.1 Why synthetic-first

Hospital DICOM cannot be committed (PHI, size, DTA requirements). All automated CI uses **synthetic DVH fixtures** with analytically verifiable properties.

### 5.2 Synthetic fixture layers

| Layer | Location | Purpose |
|-------|----------|---------|
| Engine unit fixtures | `engine/tests/synthetic_data/dvh_fixtures.py` | Uniform/ramp/SBRT DVHs |
| Engine conftest | `engine/conftest.py` | dicompyler-core cumulative DVH objects |
| Publication suite | `tests/test_publication_suite.py` | End-to-end radiobiology verification vs literature |
| Advanced dosiomics | Random voxel arrays in `engine_advanced/tests/` | IBSI-style features without 3D DICOM |
| Bayesian/PINN | Generated cohorts (≥20–200 patients) in `engine_advanced_f/tests/` | Part F without institutional outcomes |

### 5.3 Analytical anchors (publication suite)

Examples verified in `tests/test_publication_suite.py`:

- BED: 70 Gy / 2 Gy / αβ=10 → 84 Gy (Emami / standard LQ)
- NTCP = 0.5 when gEUD = TD50 (QUANTEC parotid TD50 = 26 Gy)
- UTCP = TCP × Π(1−NTCP_k) (Källman)
- Ambiguous 78 Gy/39 fx plan → site **UNKNOWN** (not silent HN default)
- Empty OAR DVH → **NaN** NTCP (not spurious zero)

### 5.4 Optional real DICOM

Place anonymised cohort in `test_data/dicom_input/` (local only, gitignored except README/.gitkeep). See `test_data/README.md`.

---

## 6. Test architecture

### 6.1 Configuration

Root `pytest.ini`:

```ini
testpaths = engine/tests tests engine_advanced/tests engine_advanced_f/tests
addopts = --import-mode=importlib -q --tb=short
pythonpath = engine engine/tests engine_advanced engine_advanced_f .
```

### 6.2 Test suites

| Suite | Path | Focus | Tests collected |
|-------|------|-------|-----------------|
| **Engine core** | `engine/tests/` | Radiobiology, DICOM IO, site detect, UTCP, QUANTEC, calibration, ML guards | ~171 |
| **Advanced B/E** | `engine_advanced/tests/` | DVH shape, dosiomics, PINN registry | ~10 |
| **Advanced F** | `engine_advanced_f/tests/` | Bayesian NTCP, PINN checkpoint, integration | ~3 |
| **App / legacy** | `tests/` | GUI hooks, code3/6/7, UTCP cross-path, TCP utils | ~239 |
| **Publication** | `tests/test_publication_suite.py` | Software-paper validation (129 tests, subset of above) | 129 |
| **Total (unique)** | All testpaths | | **423** |

### 6.3 Running tests

```powershell
cd project_rbGyanx
$env:PYTHONUTF8 = "1"
$env:RBGYANX_ENGINE_PATH = "$PWD\engine"

# Full suite (recommended)
.\scripts\run_all_tests.ps1

# Publication suite only (paper supplementary)
python -m pytest tests/test_publication_suite.py -v --tb=short

# Combined single invocation
python -m pytest engine/tests/ tests/ engine_advanced/tests/ engine_advanced_f/tests/ `
    --import-mode=importlib -q --tb=short
```

### 6.4 Optional dependency behaviour

Tests requiring **xgboost**, **lightgbm**, or **lifelines** use `@xgb_skip` / `@lifelines_skip` when packages are absent. PINN tests use `pytest.importorskip("torch")`. With all four packages installed (see §7.2), **zero ML-related skips** occur. Bayesian MCMC still uses bootstrap emulation by default; PyMC remains optional.

---

## 7. Test results (verified June 2026)

Environment: Windows 10/11, Python 3.14.2, pytest 9.0.2.

### 7.1 Baseline (optional ML deps absent)

| Run | Command | Result |
|-----|---------|--------|
| **Full monorepo suite** | `pytest` all testpaths, `--import-mode=importlib` | **419 passed**, ~4 skipped (xgboost/lifelines/torch), **0 failed** |
| **Publication suite** | `tests/test_publication_suite.py` | **129 passed** |

Skips were attributable to missing **xgboost**, **lightgbm**, **lifelines**, or **PyTorch** — not test errors.

### 7.2 Full dependency verification (8 June 2026)

Installed optional packages:

| Package | Version |
|---------|---------|
| xgboost | 3.1.2 |
| lightgbm | 4.6.0 |
| lifelines | 0.30.3 |
| torch | 2.12.0+cpu |

```powershell
pip install xgboost lightgbm lifelines torch
$env:RBGYANX_ENGINE_PATH = "$PWD\engine"
$env:PYTHONUTF8 = "1"
python -m pytest engine/tests/ tests/ engine_advanced/tests/ engine_advanced_f/tests/ `
    --import-mode=importlib -q --tb=no
python -m pytest tests/ --import-mode=importlib -q --tb=no -r s
```

| Run | Collected | Passed | Skipped | Failed |
|-----|-----------|--------|---------|--------|
| **Full monorepo suite** | 423 | **419** | **4** | **0** |
| **`tests/` directory only** | 205 | **201** | **4** | **0** |
| **Publication suite** | 129 | **129** | 0 | **0** |

**Remaining 4 skips (not dependency-related):**

| Test | Reason |
|------|--------|
| `tests/test_gui_integration.py` (×2) | `rbGyanXGUI` class not importable headless (Tkinter GUI) |
| `tests/test_utils.py` | `validation_utils` legacy module not present |
| `tests/test_with_real_data.py` | No `input_data/` clinical files on disk |

**Conclusion:** With xgboost, lightgbm, lifelines, and PyTorch installed, the full **423-test** monorepo suite passes with **0 failures**. All skips are environmental (GUI headless, missing local clinical data, optional legacy module) — not radiobiology or engine defects.

---

## 8. Known limitations

1. **Dual code paths** — DICOM classical via engine; some ML/SHAP/P+ metrics still via legacy code3/6/7.
2. **No PHI in Git** — DICOM integration tests require local cohort; CI is synthetic-only.
3. **TXT DVH plan-quality** — Physical/plan-quality layer is DICOM-only.
4. **ADVANCED ML** — Requires outcome CSV; not validated for routine clinical use.
5. **PINN / Bayesian NTCP** — Research-grade; bootstrap emulation default; PyMC/torch optional.
6. **Site detection** — Ambiguous curative plans return UNKNOWN; user must pass `--site`.
7. **Installer** — Unsigned Windows installer; TensorFlow full build ~220 MB; use Python 3.10 for TF bundle.
8. **Regulatory** — Not FDA/CE marked; institutional SOP and physicist review required.
9. **Python version** — Dev on 3.14; PyInstaller TF build targets 3.10.

---

## 9. Intellectual positioning

| Comparison | rbGyanX stance |
|------------|----------------|
| **TPS** | Ingests DICOM; adds radiobiology + protocol checks |
| **Pure ML NTCP papers** | DVH-feature ML is established; rbGyanX keeps physics-first core |
| **3D CNN NTCP (emerging)** | ADVANCED dosiomics/3D pathway as research hook, not clinical default |
| **PINN literature** | Novel territory; LQ-constrained training in Part F for institutional research |

See `docs/RBGYANX_MANIFESTO.md` for full positioning against DL competition (CURSOR_FIXES §21).

---

## 10. Version, citation, and contact

| Item | Value |
|------|--------|
| Product version | 1.0.0 (`VERSION.txt`) |
| Engine package | `rbgyanx-engine` (`engine/pyproject.toml`) |
| GitHub | [github.com/kalyan2031990/rbGyanX](https://github.com/kalyan2031990/rbGyanX) |
| License | MIT (`LICENSE`) |
| Citation | `CITATION.cff` |
| User guide | `docs/RBGYANX_1.0_DESKTOP.md` |
| Implementation roadmap | `docs/IMPLEMENTATION_ROADMAP.md` |

---

## 11. One-paragraph abstract

rbGyanX evolved from an open NTCP research pipeline through py_ntcp and a phased py_tcpx TCP program into a unified rbGyanX_cdss engine (TCP+NTCP+UTCP+QUANTEC+physical metrics), then a Tkinter desktop application with legacy workflow scripts, and finally into a four-package monorepo (engine, engine_advanced, engine_advanced_f, desktop shell) with 423 automated tests — including a 129-test publication suite on synthetic data — preserving classical radiobiology as the clinical core while layering opt-in ML, dosiomics, PINN, and Bayesian inference for research.

---

*Last updated: June 2026 — post CURSOR_FIXES (Parts A–F) and CURSOR_FINAL_FIXES.*
