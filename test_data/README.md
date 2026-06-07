# Test data

`dicom_input/` holds anonymised DICOM RT cohort for integration testing.

This directory is excluded from version control (PHI risk, binary size).

To run DICOM integration tests:
1. Place anonymised patient folders here (each with RTPLAN, RTDOSE, RTSTRUCT .dcm).
2. Run: `python -m rbgyanx_engine --dicom-dir test_data/dicom_input --endpoint both
         --cohort --output-dir out_dicom_test --no-uncertainty`

A 4-patient de-identified cohort is available to collaborators under a DTA.
Contact the corresponding author (see CITATION.cff).

For CI without real DICOM data, all engine tests use synthetic DVH fixtures
and do not require this directory.
