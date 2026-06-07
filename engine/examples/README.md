# Examples

py_tcpx does not ship patient data. Run the CLI with your own paths:

```bash
# DICOM
python -m py_tcpx --dicom-dir /your/dicom/patient --site HN --output-dir /your/output

# DVH text exports
python -m py_tcpx --dvh-dir /your/dvh_folder --site HN --dvh-glob "*.txt" --output-dir /your/output

# Cohort + outcomes
python -m py_tcpx --dicom-dir /your/cohort --site LUNG --cohort \
  --outcome-csv /your/outcomes.csv --output-dir /your/output
```

See the [main README](../README.md) for full option list.
