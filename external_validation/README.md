# External-validation tooling

General tooling for evaluating the pipeline against an outcome endpoint. **No dataset is
included or downloaded**, and nothing here is specific to a particular collection.

| Script | What it does |
|---|---|
| `make_synthetic_mirror.py` | Generates a synthetic `cohort_features.csv` with the same schema as a real feature table, from a known generative model. No patient data is involved, which is what lets CI and an offline reader run the benchmark end to end. |
| `run_benchmark.py` | Runs the four-class benchmark on a `cohort_features.csv` you supply and writes one row per model class, plus the apparent-versus-cross-validated AUC plot. |
| `run_phase4_analysis.py` | Ablations on the same table: an N-subsampling learning curve, and MCD cohort-consistency scoring for out-of-domain plan flagging. |

To build a real feature table, use `engine/dicom_io/cohort_features.py` against your own DICOM,
under your own data governance, and write the result in this schema. The adapter that bound this
directory to one public archive was removed in v1.5.0: its zip layout and clinical-workbook column
map described one collection, not a format.

```bash
python external_validation/make_synthetic_mirror.py --out mirror/cohort_features.csv --n 120 --seed 0
python external_validation/run_benchmark.py --features mirror/cohort_features.csv --out-dir mirror/benchmark --quick --seed 0
```
