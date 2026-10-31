# Data availability

**rbGyanX ships no patient data.** There is no DICOM, no dose grid, no contour, no clinical table
and no pseudonym map in this repository, at any tag, and none is downloaded by installing or
running it.

## What the tests run on

Synthetic data only, generated at test time. `tests/synthetic/dicom_rt_factory.py` builds analytic
DICOM-RT studies, `scripts/make_synthetic_dicom_cohort.py` builds a multi-patient study, and
`external_validation/make_synthetic_mirror.py` builds a feature table with the same schema as a
real one from a known generative model. `tests/fixtures/contour_name_corpus.txt` holds structure
**names** only, collected from public sources.

## What you supply

Your own DICOM-RT, under your own data governance and your own ethical approvals. rbGyanX reads
it; it does not transmit it. The AI assistant is opt-in, disabled in BASIC mode, and never sends
patient-derived content to a remote provider — see `docs/AI_ASSISTANT.md` and the tests that pin
that behaviour.

## Results published with the software

Results computed from a particular dataset, and the evidence needed to check them, are deposited
separately from the software and are not part of this repository.
