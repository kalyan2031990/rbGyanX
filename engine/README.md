# rbGyanX_cdss — open-source radiobiology engine

**Package:** `rbgyanx-engine` (import `rbgyanx_engine`)  
**Version:** 0.1.0-alpha (Phase R1)  
**Role:** Public TCP + NTCP computation core for the [rbGyanX](https://github.com/kalyan2031990) clinical decision-support platform. The Tkinter GUI remains private; this repo is the science engine clinics and researchers install via pip or wheel.

## Features (R1)

- **TCP** — Poisson, Zaider–Minerbo, gEUD, Logistic; Phases 1–8 (uncertainty, ML, XAI when ADVANCED + outcomes).
- **NTCP** — LKB (log-logistic, probit), Relative Seriality; multi-site OAR tables (Brain, H&N, Lung, Breast).
- **Ingestion** — **DICOM RT** (mandatory clinic path) and Eclipse-style **DVH text**.
- **Site detection** — Anatomy/histology from structures and plan metadata (not SRS/SBRT technique labels).
- **API** — `run_analysis(RunConfig(...))` for GUI integration.

## Install

```bash
git clone https://github.com/kalyan2031990/rbGyanX_cdss.git
cd rbGyanX_cdss
pip install -e ".[dev]"
```

## CLI

```bash
# Clinic-style: DICOM, TCP + NTCP, BASIC mode (no ML augmentation)
python -m rbgyanx_engine --dicom-dir /path/to/dicom --endpoint both --mode basic --output-dir ./out

# Research: with outcomes and ADVANCED ML
python -m rbgyanx_engine --dicom-dir /path/cohort --cohort --endpoint tcp --mode advanced \
  --outcome-csv outcomes.csv --output-dir ./out

# TPS text DVH (secondary)
python -m rbgyanx_engine --dvh-dir /path/dvh --endpoint ntcp --output-dir ./out
```

## Python API

```python
from pathlib import Path
from rbgyanx_engine import RunConfig, run_analysis

result = run_analysis(
    RunConfig(
        endpoint="both",
        input_kind="dicom",
        input_dir=Path("dicom_input"),
        output_dir=Path("out"),
        mode="basic",
        enable_ml=False,
    )
)
print(result.exit_code, result.ntcp_results_csv)
```

## Outputs

| File | Content |
|------|---------|
| `site_detection.csv` | Auto-detected site per patient |
| `tcp_benchmarking.xlsx` | TCP model comparison |
| `ntcp_results.csv` | Per-OAR NTCP values |
| `provenance.json` | Run metadata |
| `qa_report.json` | Input/contract warnings |

## Configuration

- TCP: `config/site_params_default.yaml` (+ optional `site_params_user.yaml`)
- NTCP: `config/site_params_ntcp_default.yaml` (+ optional `site_params_ntcp_user.yaml`)

## Tests

```bash
python -m pytest tests/ -q
```

## License

MIT — see [LICENSE](LICENSE).

## Related

- Private **rbGyanX GUI** consumes this engine (Phase R2).
- Prior prototypes: `py_tcpx`, `py_ntcpx`.
