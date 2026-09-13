# Test data

`dicom_input/` holds a DICOM-RT cohort for integration testing. The directory is excluded from version
control (PHI risk, binary size) and therefore ships **empty**.

## Generate a synthetic cohort (no real data needed)

Because the directory ships empty, a DICOM run against it used to complete with `attempted: 0` and
look like a pass. Generate a phantom cohort first:

```bash
python scripts/make_synthetic_dicom_cohort.py --out test_data/dicom_input --patients 2
```

That writes, per patient, a complete and self-consistent study — 24 CT slices, RTSTRUCT, RTPLAN and
RTDOSE — with the UID cross-references the ingest layer resolves (RTSTRUCT → CT series,
RTPLAN → RTSTRUCT, RTDOSE → RTPLAN, one frame of reference). Structures are PTV, Parotid_L,
Parotid_R and SpinalCord, with dose falling off from the PTV so DVHs and NTCP have real structure to
work on. The data are entirely synthetic — nested ellipsoids in a water background, no patient origin.

Then run either entry point:

```bash
python scripts/run_cohort.py --input-root test_data/dicom_input --cohort SynthSmoke --output-root out_synth --input-kind dicom --validation ExternalValidation --mode basic --endpoint both --site HN
```

```bash
python -m rbgyanx_engine --dicom-dir test_data/dicom_input --endpoint both --cohort --output-dir out_dicom_test --no-uncertainty
```

Expect `attempted: 2, completed: 2, failed: 0` and four structures per patient. `attempted: 0` means
the cohort was never generated.

`tests/test_synthetic_dicom_smoke.py` does all of this automatically and asserts that the run
processed the patients and produced finite, in-range NTCP values, so an empty input directory now
fails the suite instead of passing silently.

## Real data

A 4-patient de-identified cohort is available to collaborators under a DTA. Contact the corresponding
author (see `CITATION.cff`). Place anonymised patient folders here, one directory per patient, each
containing RTPLAN, RTDOSE and RTSTRUCT `.dcm` files.

Engine unit tests use synthetic DVH fixtures and do not require this directory at all.
