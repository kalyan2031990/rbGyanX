# Roadmap: Unified TCP + NTCP Framework (py_rtcx)

**Status:** Approved — implement as public **`rbgyanx-engine`**; private **rbGyanX GUI** consumes it.  
**Author intent:** Extend [py_ntcpx](https://github.com/kalyan2031990/py_ntcpx) multi-site OAR coverage (Brain, H&N, Breast, Lung), merge with [py_tcpx](../) into `rbgyanx_engine`, validated on real data before clinic pilot.

**Version target:** `rbgyanx-engine` 0.1.0-alpha → 0.2.0-beta; rbGyanX GUI 1.1.0 private.

**Product decisions:** See `ARCHITECTURE_rbgyanx_engine.md` and `FEASIBILITY_rbGyanX_INTEGRATION.md` §10.

---

## 1. Executive summary

| Today | Target |
|-------|--------|
| **py_ntcpx** — NTCP, H&N OAR–centric, subprocess pipeline (code0–7), operationally mature on real toxicity data | **Unified library** — TCP + NTCP, multi-site, single CLI |
| **py_tcpx** — TCP, modular Phases 1–8, DICOM + txt DVH, cleaner code, small real-data smoke tests | Same package, inheriting py_ntcpx validation patterns |

**Design principle:** Keep py_ntcpx’s **clinical rigor** (contracts, EPV, CCS, leakage, calibration, manuscript outputs). Rebuild execution on py_tcpx’s **module layout** (no 300 KB monolithic `code3` scripts).

---

## 2. Why unify (and why not “just extend py_ntcpx”)

### Strengths to preserve from py_ntcpx
- Real-cohort NTCP workflow (clinical reconciliation, QUANTEC, bDVH).
- Four-tier classical + ML + tiered reporting.
- uNTCP / parameter uncertainty, adaptive CCS, ClinicalSafetyGuard.
- SHAP + LIME at scale; publication pipeline (600 DPI, LaTeX, supp tables).
- ~80 integration tests on real workflow paths.

### Strengths to adopt from py_tcpx
- Package layout: `dicom_io/`, `config/`, `radiobiology/`, `statistical_models/`, `ml_models/`, `xai/`, `validation/`, `outputs/`.
- Single entry: `python -m py_rtcx --mode tcp|ntcp|both`.
- DICOM RT ingestion + TPS txt DVH + flat multi-patient cohorts.
- Site YAML by **tumour / organ biology**, not delivery technique (SRS/SBRT).
- Path-independent CLI (no hardcoded machine paths).

### Technical debt to retire from py_ntcpx
- Subprocess orchestration (`run_pipeline.py` spawning code1–7).
- Duplicate logic across `code*.py` and `src/`.
- H&N-only organ parameter tables scattered in scripts.
- Mixed versioning (README v1.0.0 vs release v3.0.1).
- OAR list not formalized for Brain / Breast / Lung the way TCP sites are in py_tcpx.

---

## 3. Target architecture (Phase 1–8, dual endpoint)

```
                    ┌─────────────────────────────────────┐
                    │  CLI: python -m py_rtcx               │
                    │  --endpoint tcp | ntcp | both         │
                    │  --input dicom | dvh-txt              │
                    │  --output-dir ...                     │
                    │  --clinical-csv / --outcome-csv       │
                    └─────────────────┬───────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
   ┌───────────┐              ┌───────────────┐            ┌──────────────┐
   │ Phase 1   │              │ Phase 2       │            │ Phase 3      │
   │ Ingestion │──────────────│ Classical     │────────────│ Uncertainty  │
   │ DICOM/txt │              │ TCP + NTCP    │            │ MC, hypoxia, │
   │ registry  │              │ models        │            │ uNTCP        │
   └───────────┘              └───────────────┘            └──────────────┘
         │                            │                            │
         └────────────────────────────┼────────────────────────────┘
                                      ▼
              ┌───────────────────────────────────────────┐
              │ Phase 4 — Multivariable logistic (MVL)      │
              │  TCP: LocalControl  |  NTCP: Toxicity     │
              └───────────────────────────────────────────┘
                                      ▼
              ┌───────────────────────────────────────────┐
              │ Phase 5 — ML (XGB, RF, optional ANN/LGBM)   │
              │  Nested CV, EPV gates, patient-level split │
              └───────────────────────────────────────────┘
                                      ▼
              ┌───────────────────────────────────────────┐
              │ Phase 6 — XAI (SHAP, PDP/ICE, LIME)         │
              └───────────────────────────────────────────┘
                                      ▼
              ┌───────────────────────────────────────────┐
              │ Phase 7 — Validation (DeLong, calib, CCS) │
              │  Leakage audit, clinical safety layer       │
              └───────────────────────────────────────────┘
                                      ▼
              ┌───────────────────────────────────────────┐
              │ Phase 8 — Reporting (Excel, figures, LaTeX) │
              │  Optional manuscript bundle (ex-code6/7)    │
              └───────────────────────────────────────────┘
```

**Shared core:** patient registry, structure canonicalization, site/OAR detection, DVH quality flags, contract checkpoints (optional but recommended for NTCP parity).

---

## 4. Multi-site OAR extension (py_ntcpx → unified config)

### 4.1 Site × structure matrix

| Site | Target volumes (TCP) | OARs (NTCP) — initial set |
|------|----------------------|---------------------------|
| **Brain / BRAIN_GBM** | GTV, CTV, PTV | Brain, brainstem, chiasm, optic nerves, cochlea, hippocampus, pituitary |
| **Brain / BRAIN_METS** | GTV, CTV, PTV | Same + surgical cavity conventions |
| **HN** | GTV, CTV, PTV | Parotid L/R, submandibular, mandible, cord, pharynx, oral cavity, larynx, etc. (existing QUANTEC set) |
| **LUNG** | GTV, CTV, PTV | Lung L/R, heart, esophagus, brachial plexus, chest wall |
| **BREAST** | CTV, PTV | Heart, LAD, ipsi/contra lung, chest wall |

Deliverables:
- `config/structure_aliases.yaml` — unified targets + OARs.
- `config/site_params_tcp.yaml` — from py_tcpx `site_params_default.yaml`.
- `config/site_params_ntcp.yaml` — QUANTEC + literature TD50/m/n per OAR per site.
- `config/organ_risk_map.yaml` — which OARs are scored for which endpoint (e.g. parotid → xerostomia grade ≥2).

### 4.2 Auto site detection (one module, two uses)

Reuse py_tcpx `site_detector` logic:
- **Anatomy** from plan label + OAR/target presence (not SRS/SBRT fractionation).
- **Brain histology** GBM vs METS from keywords only.
- **NTCP mode:** after site is known, restrict OAR scoring to site-appropriate organ list.

### 4.3 Biological DVH (bDVH)

Port `code2_bDVH` into `radiobiology/bdvh.py`:
- Shared EQD2/BED with site-specific α/β for **tumour** (TCP) and **OAR** (NTCP).
- Single API: `compute_bdvh(dvh_df, organ_type="oar"|"target", site=...)`.

---

## 5. Classical models layer

### 5.1 TCP (from py_tcpx — migrate as-is, then harden)

| Model | Module | Notes |
|-------|--------|-------|
| Poisson TCP | `radiobiology/tcp/poisson.py` | DVH-based |
| Zaider–Minerbo | `radiobiology/tcp/zm.py` | |
| gEUD-TCP | `radiobiology/tcp/geud.py` | Negative *a* for tumour |
| Logistic TCP | `radiobiology/tcp/logistic.py` | |
| Hypoxia | `uncertainty/hypoxia.py` | Tumour only |

### 5.2 NTCP (from py_ntcpx — refactor tiers into modules)

| Tier | py_ntcpx source | Unified module |
|------|-----------------|------------------|
| 1 — Fixed QUANTEC | `ntcp_models/legacy_fixed` | `radiobiology/ntcp/lkb.py`, `rs.py`, `probit.py` |
| 2 — MLE refit | `ntcp_models/legacy_mle` | `radiobiology/ntcp/mle_refit.py` |
| 3 — Multivariable logistic | `modern_logistic` | `statistical_models/logistic_ntcp_mv.py` |
| Novel / RS fixes | `ntcp_novel_models.py`, biological_refitting | `radiobiology/ntcp/novel.py` |

**Unified calculator pattern** (mirror `TCPCalculator`):

```text
TCPCalculator.compute_all(dvh, plan_meta, site_params, target_type)
NTCPCalculator.compute_all(dvh, plan_meta, organ_params, endpoint)
```

Both return dict + `_dvh_df` for uncertainty propagation.

---

## 6. Phases 4–8 — feature parity checklist

| Feature | py_ntcpx | py_tcpx | Unified target |
|---------|----------|---------|----------------|
| EPV guard | Yes | Yes | Shared `statistical_models/epv_guard.py` |
| MVL logistic | NTCP | TCP (MVL) | `fit_mvl_tcp` / `fit_mvl_ntcp` |
| Cox | — | Yes | Optional survival endpoints |
| XGBoost / RF | XGB, ANN, LGBM | XGB, RF | Configurable model zoo |
| Nested CV | Yes | Yes | `ml_models/nested_cv.py` |
| DeLong AUC | Yes | Yes | `validation/delong.py` |
| Calibration (Platt/isotonic) | Yes | Plots only | Full for both endpoints |
| CCS | Adaptive | Basic | Port adaptive rules from py_ntcpx |
| uNTCP / TCP MC | uNTCP | Parameter MC | `uncertainty/` |
| Leakage audit | Yes | — | Port `LeakageAudit` |
| Clinical safety guard | Yes | — | Port for both endpoints |
| SHAP | code7 | Yes | Unified `xai/shap.py` |
| LIME | code7 | Yes | Unified `xai/lime.py` |
| PDP/ICE | — | Yes | TCP exploration |
| Clinical reconciliation | code0 | — | `clinical/reconcile.py` |
| Contract validator | Yes | — | `pipeline/contracts.py` (optional strict mode) |
| QUANTEC stratifier | Yes | — | `quantification/quantec.py` |
| Factor analysis | code5 | — | `analysis/clinical_factors.py` |
| Publication / LaTeX | code6, supp | Basic figures | `outputs/manuscript.py` |
| DICOM ingestion | — | Yes | `dicom_io/` |
| TPS txt DVH | code1 | Yes | `dicom_io/txt_dvh_reader.py` |

---

## 7. Implementation phases (work packages)

### WP0 — Decision record (1 week)
- [ ] Final package name (`py_rtcx` recommended).
- [ ] Repo strategy: new repo vs py_tcpx repo renamed vs monorepo (`packages/py_rtcx`).
- [ ] License, citation (merge CITATION.cff from py_ntcpx).
- [ ] Endpoint naming: `Toxicity` vs `Complication`, `LocalControl` vs `Event`.

### WP1 — Foundation (2–3 weeks)
- [ ] Create unified repo skeleton from py_tcpx layout.
- [ ] Merge `requirements.txt` (add lightgbm, python-docx if manuscript kept).
- [ ] Unified `pyproject.toml` + `python -m py_rtcx` CLI skeleton.
- [ ] Config: TCP + NTCP YAML trees for 5 site keys.
- [ ] Structure aliases: targets + OARs for Brain, HN, Lung, Breast.
- [ ] Port site_detector + OAR-aware detection.

**Exit criterion:** `pytest` passes on config + detection only.

### WP2 — Phase 1–2 ingestion + classical (3–4 weeks)
- [ ] Port py_tcpx DICOM + txt readers (no regression).
- [ ] Port `PatientRegistry` + cohort iterator (flat DICOM, subfolders).
- [ ] Implement `NTCPCalculator` from py_ntcpx tiers (unit tests per organ model).
- [ ] Wire `pipeline.run_classical(endpoint=...)`.
- [ ] Excel row schema: one sheet TCP, one sheet NTCP per patient-organ.

**Exit criterion:** Reproduce py_tcpx test cohort TCP; reproduce one py_ntcpx H&N OAR NTCP case from saved txt.

### WP3 — Phase 3 uncertainty (2 weeks)
- [ ] TCP: parameter MC + hypoxia (py_tcpx).
- [ ] NTCP: uNTCP + parameter MC (py_ntcpx quantification).
- [ ] Shared uncertainty report columns in Excel.

**Exit criterion:** MC stats on 4-patient DICOM + 14 txt PTV match prior py_tcpx run within tolerance.

### WP4 — Phase 4–5 statistics + ML (3 weeks)
- [ ] Shared EPV module; separate feature sets for TCP vs NTCP rows.
- [ ] MVL TCP + MVL NTCP.
- [ ] ML zoo with patient-level split; **no augmentation in production mode**.
- [ ] Port leakage audit + ClinicalSafetyGuard.

**Exit criterion:** ML runs only when user supplies real outcome CSV and n≥EPV threshold.

### WP5 — Phase 6–7 XAI + validation (2 weeks)
- [ ] Unified SHAP (fix XGB `base_score` from py_ntcpx).
- [ ] LIME for both endpoints.
- [ ] PDP/ICE for TCP features.
- [ ] DeLong, calibration correction, adaptive CCS.

**Exit criterion:** Figures match structure of current py-tcpx_test_output + py_ntcpx code7 samples.

### WP6 — Phase 8 reporting + contracts (2 weeks)
- [ ] `tcp_benchmarking.xlsx` / `ntcp_benchmarking.xlsx` or combined workbook.
- [ ] Optional contract mode: `Step1_DVHRegistry` → … → QA (port ContractValidator).
- [ ] Port clinical reconciliation (code0) as `clinical/reconcile.py`.
- [ ] Manuscript bundle behind `--manuscript` flag (port code6, supp summary).

**Exit criterion:** One command produces publication-ready folder from real H&N NTCP cohort.

### WP7 — Multi-site OAR expansion (3–4 weeks, parallel with WP2–3)
- [ ] Brain OAR NTCP parameter table + aliases.
- [ ] Lung OAR set (esophagus, heart, lungs).
- [ ] Breast OAR set (heart, LAD, lungs).
- [ ] Validation notebooks/scripts per site (not in main package).

**Exit criterion:** At least 2 OARs per site compute NTCP without NaN on site-specific test DVHs.

### WP8 — Real-data verification gate (your step — 4+ weeks)
- [ ] **TCP cohort:** DICOM + txt from `py_tcpx_test_input` + additional patients.
- [ ] **NTCP cohort:** Existing py_ntcpx H&N toxicity cohort (reference outputs).
- [ ] **New:** Brain / Lung / Breast OAR txt or DICOM subsets you provide.
- [ ] Comparison report: unified vs py_ntcpx v3.0.1 (NTCP), unified vs py_tcpx v1.0.0 (TCP).
- [ ] Sign-off checklist (see §9).

**Exit criterion:** Written verification report + frozen golden outputs committed to `tests/golden/`.

### WP9 — GitHub release (1 week)
- [ ] README, ARCHITECTURE.md, OUTPUT_INDEX.md (from py_ntcpx docs style).
- [ ] CI: pytest + ruff + black.
- [ ] CHANGELOG, CITATION.cff, example data (synthetic only if no PHI).
- [ ] Migration guide: py_ntcpx `run_pipeline.py` → `py_rtcx` CLI flags.

---

## 8. Proposed repository layout (unified)

```text
py_rtcx/
├── py_rtcx/              # CLI + pipeline orchestration
│   ├── __main__.py
│   └── pipeline.py
├── dicom_io/             # DICOM, txt DVH, site_detector, registry
├── config/               # TCP + NTCP YAML, structure_aliases
├── radiobiology/
│   ├── tcp/              # Poisson, ZM, gEUD, logistic
│   ├── ntcp/             # LKB, RS, probit, MLE
│   └── bdvh.py
├── uncertainty/          # MC, hypoxia, uNTCP
├── statistical_models/   # EPV, MVL TCP/NTCP, Cox
├── ml_models/
├── xai/
├── validation/           # DeLong, CCS, calibration, leakage, safety
├── clinical/             # reconciliation (ex-code0)
├── quantification/       # QUANTEC (ex-quantification/)
├── analysis/             # clinical factors (ex-code5)
├── outputs/              # Excel, figures, manuscript
├── tests/
├── docs/
│   └── ROADMAP_UNIFIED_TCP_NTCP.md   # this file
└── examples/
```

---

## 9. Real-data verification checklist (before GitHub)

Use this when you say “implement” is done:

### TCP
- [ ] ≥10 patients with DICOM RT triplet; TCP not NaN for ≥1 target per patient.
- [ ] ≥10 patients with txt DVH; site auto-detect documented in `site_detection.csv`.
- [ ] Dmean vs TPS report ≤2% where header mean exists.
- [ ] Real `LocalControl` CSV; ML only with `--no-ml-augment`.

### NTCP (H&N baseline)
- [ ] Re-run historical py_ntcpx cohort; NTCP LKB/RS within 1% of v3.0.1 for parotid/cord spot checks.
- [ ] Toxicity grades aligned via clinical reconciliation.

### NTCP (new sites)
- [ ] Brain: ≥5 patients, ≥3 OARs scored.
- [ ] Lung: ≥5 patients, lung + esophagus (or SBRT OAR set).
- [ ] Breast: ≥5 patients, heart/LAD.

### ML / validation
- [ ] EPV enforced; training refused when underpowered.
- [ ] Patient-level split verified by leakage audit.
- [ ] CCS + calibration plots generated.
- [ ] No synthetic outcome augmentation in reported metrics.

---

## 10. Risk register

| Risk | Mitigation |
|------|------------|
| py_ntcpx code3 regression during refactor | Golden-file tests from v3.0.1 Excel outputs |
| OAR parameters wrong for non-HN sites | QUANTEC + literature review per organ; expert sign-off |
| Scope creep (full py_ntcpx parity day 1) | WP6 manuscript optional; WP7 site rollout incremental |
| DICOM DVH failures (`dicom` package) | Document dependency; fallback to txt export |
| Dual endpoint confusion in one Excel | Separate sheets + `endpoint` column everywhere |

---

## 11. Effort estimate (solo developer, part-time)

| Work package | Calendar (part-time) |
|--------------|-------------------|
| WP0–WP1 | 3–4 weeks |
| WP2–WP3 | 6–8 weeks |
| WP4–WP6 | 6–8 weeks |
| WP7 (multi-site OAR) | 3–4 weeks (overlap WP2–3) |
| WP8 (your verification) | 4–8 weeks |
| WP9 | 1 week |
| **Total** | **~6–9 months** to unified v1.0 with multi-site OAR + real-data sign-off |

Aggressive full-time: **~3–4 months** for core unification; +2 months for multi-site OAR validation.

---

## 12. What happens when you say “implement”

1. Start **WP1** in unified repo (branch `unified/v0.1-foundation`).
2. Do **not** delete py_ntcpx or py_tcpx until WP8 sign-off.
3. Each WP ends with pytest + short verification note in `docs/verification/`.
4. You run real data at WP8; we fix deltas before WP9 GitHub.

---

## 13. Open decisions for you

1. **Package name:** `py_rtcx` / `py_tcpx_ntcpx` / other?
2. **Single repo or monorepo** with deprecated `py_ntcpx` archived?
3. **Default endpoint:** `both` in one run, or separate commands?
4. **Keep subprocess code0–7** as thin wrappers during migration (yes/no)?
5. **ANN + LightGBM** in v1.0 unified, or XGB+RF only initially?
6. **Manuscript pipeline** in v1.0 or v1.1?

---

*Document version: 2026-05-23 — planning only.*
