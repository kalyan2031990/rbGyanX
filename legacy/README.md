# Legacy — quarantined, not part of the supported tool

**Nothing here is imported by the engine, the test suite, the CLI, or the packaged
application.** These files are kept for provenance (they are the lineage the engine grew out
of: JMP → py_ntcpx → rbGyanX) and for reference when reconciling historical results. They are
excluded from linting, typing, coverage and packaging.

> Do not add new code here, and do not import from here. Use the engine.

## Contents

| File | Superseded by |
| --- | --- |
| `code1_dvh_preprocess.py` | `engine/dicom_io/txt_dvh_reader.py` (canonical DVH text reader) |
| `code2_dvh_plot_and_summary.py` | `engine/outputs/*`, `engine/dicom_io/dvh_shape_features.py` |
| `code3_ntcp_analysis_ml.py` | `engine/radiobiology/ntcp/*` + `engine/validation/ntcp_benchmark.py` |
| `code4_ntcp_output_QA_reporter.py` | `engine/validation/*` (was imported by nothing) |
| `code5_ntcp_factors_analysis.py` | `engine/validation/*` (was imported by nothing) |
| `code6_tcp_analysis.py` | `engine/radiobiology/*` + `engine/validation/extval_benchmark.py` (was imported by nothing) |
| `code7_tcp_ntcp_integration.py` | `engine/validation/*`, UTCP consensus (was imported by nothing) |
| `qa_comprehensive_test_suite.py` | the `pytest` suite (574 tests) |
| `rbgyanx_qa_test_suite.py` | the `pytest` suite |

`code4`–`code7` were already dead at quarantine time (imported by no module). `code1`–`code3`
were imported only by `qa_comprehensive_test_suite.py`, which is quarantined with them, so the
group is internally consistent and self-contained.

## Why quarantine rather than delete
These monoliths implement the historical analyses that the published prior work was based on.
Keeping them (a) preserves the audit trail for the JMP → py_ntcpx → rbGyanX lineage table in the
manuscript, and (b) lets historical numbers be re-derived if a reviewer asks. Deleting them would
lose that, while leaving them at the repo root implied they were part of the tool.

## Status
Retired 2026-07-18 (Phase 2 de-duplication). See `docs/AUDIT_REPORT.md` §3 and §7.
