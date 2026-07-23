# rbGyanX outcome data schema

Used by `outcome_csv` for NTCP calibration (`validation/ntcp_calibration.py`) and ML validation.

## Required columns

| Column | Type | Description |
|--------|------|-------------|
| AnonPatientID | string | Must match engine output IDs |
| ntcp_outcome | int (0/1) | 1 = grade ≥2 toxicity at endpoint |
| followup_months | float | Months to last follow-up or event |
| event_type | string | e.g. `xerostomia_g2`, `pneumonitis_g2` |

For TCP cohort studies, include `tcp_outcome` (1 = local control).

## Recommended columns

| Column | Type | Description |
|--------|------|-------------|
| age_years | float | Age at RT start |
| sex | string | M / F |
| smoking_pack_years | float | 0 if never |
| bmi | float | kg/m² |
| hpv_status | string | pos / neg / unknown (H&N) |

## Notes

- One row per patient per endpoint.
- Minimum ~50 patients per organ for LKB MLE; ≥100 recommended.
- Use the same rbGyanX version and site YAML for DVH processing and outcome merge.
