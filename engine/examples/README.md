# Engine examples

The engine ships no patient data. For runnable, self-contained demos on **synthetic**
data (with a tiny example dataset and BASIC/ADVANCED scripts), see the top-level
[`examples/`](../../examples/README.md).

Quick CLI reference — run on your own paths:

```bash
# DICOM RT (RTSTRUCT + RTDOSE [+ RTPLAN])
python -m rbgyanx_engine --dicom-dir /your/dicom/patient --site HN --output-dir /your/output

# DVH text exports (Eclipse / RayStation / Pinnacle-style)
python -m rbgyanx_engine --dvh-dir /your/dvh_folder --dvh-glob "*.txt" --output-dir /your/output

# Cohort + outcomes
python -m rbgyanx_engine --dicom-dir /your/cohort --site LUNG --cohort \
  --outcome-csv /your/outcomes.csv --output-dir /your/output
```

See the [main README](../README.md) for the full option list.
