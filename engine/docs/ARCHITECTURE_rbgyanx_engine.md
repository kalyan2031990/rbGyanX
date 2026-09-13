# rbgyanx-engine — Open-source radiobiology core

**Status:** Approved architecture (2026-05-23). Implementation starts as Phase R1.  
**Product shell:** rbGyanX private GUI (`rbgyanx_dual`) — BASIC (clinics) + ADVANCED (research).  
**License (engine):** MIT (match py_tcpx / rbGyanX science stack).

---

## 1. Locked product decisions

| # | Decision |
|---|----------|
| 1 | **rbGyanX** is the product brand: **BASIC** = governed clinic CDSS; **ADVANCED** = research platform (same binary, mode contract). |
| 2 | **Multi-site** from v1.0: Brain (GBM/Mets), H&N, Lung, Breast — TCP YAML + per-site NTCP OAR tables. |
| 3 | **DICOM DVH mandatory** for clinic release (TPS txt remains supported). |
| 4 | **Ask rbGyanX / LLM disabled in BASIC** — ADVANCED only (`ai_integration` capability). |
| 5 | **Open-source engine + private GUI** — this document defines the public engine; GUI stays in private repo. |

---

## 2. Repository split

```text
GitHub (public)                    Private
─────────────────                  ─────────────────────────
rbgyanx-engine/                    rbgyanx-clinical/  (or rbgyanx_dual)
  rbgyanx_engine/                    rbgyanx_gui.py
    dicom_io/                        rbgyanx/logic/  (modes, provenance)
    config/                          rbgyanx/ui/
    radiobiology/tcp/                code7 integration (UTCP/P+/CFTC)
    radiobiology/ntcp/
    statistical_models/
    ml_models/
    xai/
    validation/
    pipeline.py
  tests/  (200+ target)
  pyproject.toml
  README.md

Evolution path: py_tcpx repo → rename/publish as rbgyanx-engine v0.1, then add NTCP from py_ntcpx.
```

**Dependency rule:** Private GUI declares `rbgyanx-engine>=x.y.z` in `requirements.txt` or vendor wheel at build time. No duplicated Poisson/LKB math in GUI repo long-term.

---

## 3. Engine API (v1.0 contract)

Single entry for GUI and CLI:

```python
from rbgyanx_engine.pipeline import RunConfig, run_analysis

result = run_analysis(
    RunConfig(
        endpoint="tcp" | "ntcp" | "both",
        input_kind="dicom" | "dvh_txt",
        input_dir=Path("..."),
        output_dir=Path("..."),
        clinical_csv=Path("...") | None,
        outcome_csv=Path("...") | None,
        site=None,  # auto-detect if None
        n_mc=500,
        enable_ml=True,
        mode="basic" | "advanced",  # gates ML depth, no LLM here
    )
)
```

**Returns:** `EngineResult` with paths to `tcp_results.csv`, `ntcp_results.csv`, `site_detection.csv`, `figures/`, `qa_report.json`, `provenance.json`.

**Not in engine:** Tkinter, Ask rbGyanX, therapeutic-ratio Word reports (stay in private `code7` wrapper).

---

## 4. Module mapping (sources → engine)

| Engine module | From py_tcpx | From py_ntcpx | New |
|---------------|--------------|---------------|-----|
| `dicom_io/` | Full port | — | — |
| `dicom_io/txt_dvh_reader.py` | Full | — | — |
| `dicom_io/site_detector.py` | Full | — | Multi-site rules |
| `config/site_params_tcp.yaml` | Full | — | — |
| `config/site_params_ntcp.yaml` | — | Port + extend | Brain/Lung/Breast OAR |
| `radiobiology/tcp/` | Poisson, Z-M, hypoxia | — | Retire rbGyanX duplicate |
| `radiobiology/ntcp/` | — | LKB, RS, QUANTEC | — |
| `validation/` | CCS hooks | EPV, leakage, reconciliation | Unified CCS |
| `ml_models/` | TCP ML phases | NTCP ML | Shared nested CV |
| `pipeline.py` | Phases 1–8 TCP | NTCP phases | `endpoint=both` |

---

## 5. rbGyanX GUI integration (private)

### Phase R1 — Engine package (weeks 1–6)

1. Create `rbgyanx-engine` repo from py_tcpx tree; package name `rbgyanx_engine`.
2. Port py_ntcpx NTCP classical + validation into `radiobiology/ntcp/`.
3. Add `endpoint=both` and shared cohort registry.
4. **Mandatory DICOM:** `input_kind=dicom` must pass contract tests on `py_tcpx_test_input/dicom_input`.
5. Multi-site YAML for all five TCP keys + NTCP OAR lists per site.

### Phase R2 — GUI wiring (weeks 7–10)

1. `rbgyanx.logic.pipeline` calls `run_analysis()` instead of subprocess `code6`/`code3`.
2. Import wizard: DICOM folder required for BASIC TCP/NTCP runs (txt fallback labeled “TPS export only”).
3. Show `site_detection.csv` + confidence in results panel.

### Phase R3 — Therapeutic ratio (weeks 11–12)

1. `code7` reads engine CSV outputs (unchanged UTCP/P+/CFTC math).
2. Golden test: 10 H&N plans, old vs new engine ≤ 1% TCP/NTCP tolerance.

### Phase R4 — Clinic pilot package (weeks 13–16)

1. Windows installer bundles pinned `rbgyanx-engine` wheel.
2. User manual: BASIC vs ADVANCED, no LLM in BASIC.
3. Real outcome cohort sign-off.

---

## 6. BASIC vs ADVANCED (engine + GUI)

| Feature | BASIC (clinic) | ADVANCED (research) |
|---------|----------------|---------------------|
| DICOM DVH | Required path | Required + benchmark read-only |
| TCP / NTCP / both | Yes | Yes |
| Classical models | Yes | Yes |
| ML predictions | Yes, with CCS warnings | Yes + extended XAI |
| Parameter sweep / developer | No | Yes |
| Ask rbGyanX LLM | **No** | Yes |
| Applicability override | No | Optional (governed) |

Engine respects `mode` for: ML hyperparameter search depth, optional uncertainty decomposition flags, export of research-only tables.

---

## 7. Multi-site NTCP (v1.0 scope)

| Site key | TCP (existing py_tcpx) | NTCP OARs (v1.0 minimum) |
|----------|------------------------|----------------------------|
| `BRAIN_GBM` | Yes | Brainstem, chiasm, optic nerves, cochlea |
| `BRAIN_METS` | Yes | Same + hippocampus (if contoured) |
| `HN` | Yes | Parotid, cord, brainstem, oral cavity, larynx |
| `LUNG` | Yes | Lung, heart, esophagus |
| `BREAST` | Yes | Heart, lung (ipsi), LAD (optional) |

Parameters: literature defaults + institution override YAML (not hardcoded in GUI).

---

## 8. Quality gates before clinic pilot

- [ ] `pytest` engine ≥ 150 tests (TCP + NTCP + DICOM ingestion).
- [ ] DICOM cohort: 4+ patients, auto site ≠ UNKNOWN when OARs present.
- [ ] No synthetic outcomes in BASIC default reports.
- [ ] Provenance JSON per run (patient IDs hashed optional).
- [ ] CCS blocks or flags ML when OOD.
- [ ] GUI self-test passes on clean Windows VM.

---

## 9. Naming and GitHub release order

1. **Publish** `rbgyanx-engine` 0.1.0-alpha (TCP + DICOM + multi-site, NTCP H&N only).
2. **Publish** 0.2.0-beta (+ full multi-site NTCP).
3. **Private** rbGyanX 1.1.0 depends on engine `>=0.2.0,<0.3`.

---

## 10. Immediate next step

**Implement R1 in public repo:** fork py_tcpx → `rbgyanx_engine` package layout, add `pyproject.toml` name `rbgyanx-engine`, port first NTCP module from py_ntcpx.

Say **implement R1** to start coding the engine package.
