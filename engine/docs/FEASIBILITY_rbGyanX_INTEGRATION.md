# Feasibility: Unified TCP/NTCP Engine inside rbGyanX CDSS

**Date:** 2026-05-23  
**Scope:** Analysis only — no implementation committed until approved.

**Repositories:**

| Repo | Role |
|------|------|
| [py_tcpx](../) | Clean Phases 1–8 TCP library + CLI |
| [py_ntcpx](https://github.com/kalyan2031990/py_ntcpx) | Operationally mature NTCP pipeline (H&N real data) |
| `C:\Users\Sampa\OneDrive\Desktop\rbgyanx_dual` | **rbGyanX** — TCP+NTCP GUI prototype, clinic-facing |

---

## 1. Executive answer

**Can the unified framework be dropped directly into rbGyanX?**

**Partially — not as a blind copy-paste.** rbGyanX **already implements a dual TCP+NTCP product** (GUI + `code6` / `code3` / `code7`). The fastest path to a **clinically useful, modern CDSS** is:

1. **Keep rbGyanX** as the shell (GUI, workflow, therapeutic ratio, governance, clinical Excel).
2. **Replace the computation core** under `rbgyanx/core/` with a shared **`rbgyanx_engine`** package (merged py_tcpx + py_ntcpx logic).
3. **Wire ingestion** through one DVH layer (txt today + DICOM from py_tcpx).
4. **Retire duplicate** `code3`/`code6` monoliths gradually via `rbgyanx.logic.pipeline` direct calls.

**Feasibility: HIGH** for science engine integration over 3–4 months.  
**Feasibility: MEDIUM** for clinic-wide CDSS distribution (needs product layer beyond radiobiology).  
**Feasibility: LOW** to replace rbGyanX GUI with CLI-only py_tcpx.

---

## 2. What rbGyanX already is (prototype assessment)

### Strengths (clinic-oriented)

| Feature | Location | Clinical value |
|---------|----------|----------------|
| **Dual TCP + NTCP + integration** | `code6`, `code3`, `code7` | Unique vs py_tcpx alone — **UTCP, P+, CFTC**, Pareto |
| **Desktop GUI** | `rbgyanx_gui.py` (~8k+ lines) | Physicist-friendly workflow |
| **Governed modes** | `rbgyanx/logic/mode_controller.py` | BASIC vs ADVANCED, capability gating |
| **Validation acknowledgment** | `validation_controller.py` | Explicit “decision support only” |
| **ML safety (CCS)** | `utils/ml_safety.py` | Out-of-distribution warnings |
| **Provenance / logging** | `logic/provenance.py`, `structured_logging.py` | Audit trail for research |
| **Ask rbGyanX / LLM** | `ai/`, `ask_rbgyanx/` | Education layer (not auto-prescription) |
| **Clinical Excel adapter** | `clinical/` | Matches real clinic data entry |
| **Self-test QA** | `qa/self_test_engine.py` | Startup checks |
| **Layered refactor started** | `rbgyanx/core`, `logic`, `ui` | Right direction |

### Gaps vs py_tcpx / py_ntcpx

| Gap | rbGyanX today | Unified target |
|-----|---------------|----------------|
| **DICOM DVH** | `NotImplementedError` in `utils/dvh_parser.py` | py_tcpx `dicom_io/` |
| **TCP models** | Poisson, LKB, Logistic, EUD | + **Zaider–Minerbo**, site YAML, hypoxia |
| **NTCP depth** | LKB log-logit, RS, probit in core | + QUANTEC tiers, MLE refit, uNTCP from py_ntcpx |
| **Multi-site** | Mostly H&N NTCP params; `config/tcp_parameters.yaml` only | Brain, Lung, Breast OAR tables |
| **Site detection** | Manual / structure heuristics in parser | py_tcpx `site_detector` |
| **Tests** | Moderate pytest | py_tcpx 138 tests; py_ntcpx ~80 |
| **Packaging** | No `pyproject.toml` | Installable engine wheel |
| **Monolithic scripts** | `code3` ~260k chars | Modular pipeline |
| **Auth / multi-user / hospital IT** | None | Required for CDSS distribution |

### No existing link to py_tcpx

Zero imports of `py_tcpx` / `py_ntcpx`. rbGyanX is a **parallel implementation** of overlapping math, not a consumer of your new libraries.

---

## 3. Architecture comparison (three codebases)

```text
                    ┌─────────────────────────────────┐
                    │         rbGyanX (target CDSS)    │
                    │  GUI + governance + TCP∩NTCP     │
                    └───────────────┬─────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     ┌────────────────┐    ┌─────────────────┐   ┌──────────────────┐
     │  Ingestion     │    │  rbgyanx_engine  │   │  Presentation    │
     │  txt + DICOM   │    │  (NEW unified)   │   │  plots, Word,    │
     │                │    │  TCP + NTCP      │   │  Excel, SHAP UI  │
     └────────────────┘    └─────────────────┘   └──────────────────┘
              ▲                     ▲
              │                     │
       from py_tcpx          py_tcpx radiobiology
                             + py_ntcpx NTCP/QUANTEC
                             + validation/XAI
```

**py_ntcpx** contributes: contracts, clinical reconciliation, EPV, leakage, calibration correction, manuscript pipeline.  
**py_tcpx** contributes: DICOM, multi-site TCP YAML, Zaider–Minerbo, modular phases, test discipline.  
**rbGyanX** contributes: **therapeutic ratio**, GUI, clinical workflow, AI tutor, mode governance.

---

## 4. Integration strategies (ranked)

### Option A — **Engine package inside rbgyanx_dual** (recommended)

```
rbgyanx_dual/
  rbgyanx_engine/          # pip install -e ./rbgyanx_engine OR git submodule
    dicom_io/
    radiobiology/tcp/
    radiobiology/ntcp/
    statistical_models/
    ml_models/
    xai/
    validation/
    pipeline.py            # phase 1-8 run()
  rbgyanx/                 # keep logic + ui
  rbgyanx_gui.py           # call engine instead of subprocess code6/3
```

**Pros:** One repo for clinicians; GUI unchanged at first.  
**Cons:** Large refactor of `code6`/`code3`.

### Option B — **Git submodule: py_tcpx as `vendor/py_tcpx`**

**Pros:** Clear upstream for TCP science.  
**Cons:** NTCP still needs py_ntcpx port; two submodules to version.

### Option C — **New repo `rbgyanx-engine` + PyPI internal wheel**

**Pros:** Best for hospital IT (versioned wheel, signed builds).  
**Cons:** More release process upfront.

### Option D — **Replace rbGyanX core entirely with subprocess to py_tcpx CLI**

**Pros:** Fastest demo.  
**Cons:** Fragile on Windows paths; loses code7 integration granularity; not maintainable.

**Recommendation:** **Option A** for development → **Option C** for clinic distribution.

---

## 5. Migration map (rbGyanX → unified engine)

| rbGyanX today | Replace with |
|---------------|--------------|
| `rbgyanx/core/tcp/*` | `rbgyanx_engine.radiobiology.tcp` (py_tcpx + keep LKB if needed) |
| `rbgyanx/core/ntcp/*` | `rbgyanx_engine.radiobiology.ntcp` (py_ntcpx tiers) |
| `code1` + `utils/dvh_parser.py` | `dicom_io` txt + DICOM readers |
| `code6_tcp_analysis.py` | `pipeline.run(endpoint="tcp")` |
| `code3_ntcp_analysis_ml.py` | `pipeline.run(endpoint="ntcp")` |
| `code7_tcp_ntcp_integration.py` | **Keep** — thin layer on engine outputs (UTCP/P+) |
| `utils/ml_models.py`, `shap_utils.py` | `ml_models/`, `xai/` |
| `utils/ml_safety.py` | `validation/ccs.py` + py_ntcpx adaptive rules |
| `config/tcp_parameters.yaml` | `config/site_params_tcp.yaml` + NTCP YAML |

**Keep rbGyanX-only (do not delete):**

- `code7` therapeutic ratio logic
- `rbgyanx_gui.py` workflow
- `mode_controller`, `validation_controller`, manifesto principles
- `ai/` educational assistants (with strict scope guard)

---

## 6. What “successful CDSS for cancer clinics” requires

Radiobiology alone is **necessary, not sufficient**.

### Tier 1 — Science (your unified engine)

- [x] rbGyanX prototype TCP+NTCP+integration
- [ ] DICOM DVH (py_tcpx)
- [ ] Multi-site OAR NTCP (py_ntcpx + extension)
- [ ] Real outcome validation (not synthetic ML labels)
- [ ] Golden tests vs py_ntcpx H&N cohort

### Tier 2 — Clinical workflow (rbGyanX strength)

- [ ] Clinical template + reconciliation (port py_ntcpx code0 pattern)
- [ ] Clear PDF/Word report per plan comparison
- [ ] “Not for prescription” disclaimers (manifesto §8)
- [ ] CCS / applicability warnings surfaced in GUI

### Tier 3 — Product / distribution (missing today)

| Requirement | Suggestion |
|-------------|------------|
| **Installer** | Windows MSI (Inno Setup) bundling Python embedded + wheel |
| **No raw API keys in GUI** | Hospital-managed config; offline mode default |
| **Role-based use** | Optional: physicist vs resident (read-only) |
| **Audit log** | Extend `structured_logging` → signed JSON per run |
| **Update channel** | Semantic versioning + migration notes |
| **PHI handling** | Local-only processing; no cloud upload default |
| **Training** | 2h physicist course + `docs/rbgyanx_user_manual.html` |
| **Regulatory path** | Position as **decision support / research tool**; document limitations; CE/FDA is separate program |

### Tier 4 — Hospital integration (v2+)

- FHIR export of summary metrics (optional)
- PACS/TPS export folder watcher
- Not required for v1.0 pilot clinics

---

## 7. Recommended roadmap (rbGyanX-centric)

### Phase R0 — Alignment (2 weeks)

- Freeze manifesto scope: CDSS vs research-only.
- Choose Option A/C for engine packaging.
- Define outcome columns: `LocalControl`, `Toxicity`, organ-specific grades.

### Phase R1 — Engine v0.1 in rbgyanx_dual (6 weeks)

- Vendor or copy py_tcpx modules into `rbgyanx_engine/`.
- Port py_ntcpx NTCP classical + EPV/CCS into `rbgyanx_engine/`.
- Single function: `run_analysis(dvh_dir, clinical_xlsx, mode=tcp|ntcp|both)`.

### Phase R2 — GUI wiring (4 weeks)

- `rbgyanx.logic.pipeline` calls engine (not subprocess code6/3).
- DICOM import button → py_tcpx reader.
- Display `site_detection.csv` in GUI.

### Phase R3 — code7 + validation (3 weeks)

- Feed engine outputs to `code7` unchanged API.
- Cross-check 10 H&N patients: rbGyanX old vs engine new.

### Phase R4 — Multi-site OAR (4 weeks)

- Brain/Lung/Breast NTCP YAML.
- GUI organ picker filtered by detected site.

### Phase R5 — Pilot clinic package (4 weeks)

- Installer, user manual update, self-test on clinic laptop.
- Real cohort sign-off (your verification).

### Phase R6 — GitHub / distribution

- Public: `rbgyanx-engine` (science) + optional private `rbgyanx-clinical` (GUI).

**Total:** ~6–7 months part-time; ~4 months full-time focused.

---

## 8. Direct implementation into rbGyanX — feasibility matrix

| Component | Direct plug-in? | Effort |
|-----------|-----------------|--------|
| py_tcpx DICOM DVH | Yes, new GUI step + engine | Medium |
| py_tcpx TCP models | Replace `rbgyanx/core/tcp` | Medium |
| py_ntcpx NTCP LKB/RS + ML | Replace `code3` core | High (large script) |
| py_ntcpx clinical reconciliation | New `clinical/reconcile.py` + GUI tab | Medium |
| py_tcpx site YAML | New config screens | Low |
| py_tcpx pytest suite | CI in rbgyanx_dual | Low |
| rbGyanX code7 UTCP/P+ | Keep as-is | None |
| rbGyanX GUI | Keep, refactor calls | Medium |
| LLM features | Keep separate | None |

---

## 9. Risk: three divergent codebases

If you maintain py_tcpx, py_ntcpx, and rbGyanX separately, **equations will drift**.

**Rule:** One source of truth — `rbgyanx_engine` — with:

- py_tcpx repo becomes thin CLI wrapper **or** archived
- py_ntcpx repo imports engine NTCP module **or** archived after port
- rbGyanX imports same engine

---

## 10. Locked decisions (2026-05-23)

| # | Answer |
|---|--------|
| 1 | **Yes** — rbGyanX is the product (BASIC clinic CDSS + ADVANCED research platform). |
| 2 | **Multi-site** from v1.0 (Brain, H&N, Lung, Breast). |
| 3 | **DICOM DVH mandatory** for clinic release. |
| 4 | **Ask rbGyanX / LLM disabled in BASIC** — ADVANCED only (implemented in `mode_controller.py`). |
| 5 | **Open-source `rbgyanx-engine` + private GUI** — see `ARCHITECTURE_rbgyanx_engine.md`. |

---

*Implementation order: **R1 public engine** (from py_tcpx + py_ntcpx) → **R2 private GUI wiring** → **R3 code7** → clinic pilot.*
