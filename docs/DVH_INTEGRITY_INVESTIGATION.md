# DVH integrity investigation (branch `fix/dvh-integrity`)

## A. Does this affect the published validation numbers? **NO.**

Evidence:
1. The buggy reader `engine/dicom_io/txt_dvh_reader.py` is imported by **no** validation,
   cohort-feature, or external-validation code — only by the GUI service
   (`rbgyanx/services/run_controller.py`) and the Tkinter app. (`grep` over
   `engine/validation`, `engine/dicom_io/cohort_features.py`, `external_validation`, `scripts`
   returns nothing.)
2. The published validation (TCIA HNSCC, SPARK, parotid) extracts DVH features from DVHs
   **computed** by dicompylercore — `engine/dicom_io/dvh_extractor.py` calls
   `dvhcalc.get_dvh(rt_struct_ds, rt_dose_ds, roi_number)` on RTDOSE+RTSTRUCT. A DVH computed
   from a dose grid is cumulative and monotonically non-increasing **by construction**; an
   inverted/non-monotonic cumulative curve cannot arise there.
3. The 22 analytic positive controls pass; the classical numerics are untouched by this work
   (the fixes are to the GUI service and a new validator on the *text* path, not the DICOM
   validation path).

The defect is isolated to the **demo data + GUI display path**. The paper's numbers stand.

## B. Root cause of each defect

| Defect | File? | Reader? | Param resolution? | Plot? |
|---|---|---|---|---|
| (i) PTV70 inverted cumulative DVH | **YES** — dose descending, volume descending; sorted-by-dose → volume increases | **YES** — `_is_cumulative` only checks volume non-increasing *in file order*, never that dose is ascending; no rejection of inverted curves; no sort | — | curve plotted with descending dose |
| (ii) Parotid_L **and Parotid_R** last two rows out of dose order | **YES** — `3360,3200` / `3080,3000` | **YES** — same silence | — | — |
| (iii) NTCP shown for PTV70 (a target) | — | reader also mislabels every single-file structure `canonical_name=PTV` | **YES** — `run_controller._read_one` applies the one OAR model (LKB parotid TD50=39.9) to **every** structure with no target check | shown in table + Sankey |

Extra finding (F): `parse_dvh_text_file` coerces **every** structure's `canonical_name` to `PTV`
via `_infer_target_type`'s default — the reader's own canonical is unusable for OAR/target
gating. Target classification must come from `structure_mapper.canon_target(raw_name)`.

## C. Reproduced metrics (EX-001, today's code)

| Structure | Dmean (Gy) | dose ascending? | valid cumulative after sort? | NTCP shown (LKB parotid) |
|---|---|---|---|---|
| PTV70 | 70.70 | no | **no (inverted)** | 0.9732 ✗ (target) |
| Parotid_L | 24.00 | no | **no** | 0.1596 |
| Parotid_R | 22.00 | no | **no** | 0.1310 |
| SpinalCord | 16.80 | yes | yes | 0.0739 |

## C (cont.) P+ / consensus contamination

Before the fix, `run_controller._read_one` applied the one OAR NTCP model (LKB parotid) to
**every** structure, so PTV70 carried NTCP 0.973 and was folded into the Sankey P+ composition
as `(1 - NTCP_target)`. That is a scientific error in the **GUI display only**. It does **not**
touch any published number: the manuscript's P+/uNTCP/consensus and the cohort-consistency score
are computed in `engine/validation/*` from the OAR-only cohort feature tables (targets live in a
separate PTV block, `cohort_features._ptv_block`), never from the GUI's per-structure NTCP.
Corrected: targets now carry no NTCP and are excluded from the Sankey P+ product.

## D. What changed + tests

- `engine/dicom_io/dvh_integrity.py` (new): `validate_cumulative_dvh` — sorts by dose, rejects
  inverted/rising, duplicate-dose, negative, non-finite curves. Never repairs.
- `engine/dicom_io/txt_dvh_reader.py`: validates + canonicalises every cumulative curve.
- `rbgyanx/services/run_controller.py`: classifies targets via `canon_target(raw_name)`; a
  target receives **no** NTCP (`is_target`, empty `ntcp`).
- `rbgyanx/qtapp/{main_window,screens/visualisation}.py`: table shows "n/a — target"; Sankey
  excludes targets and labels OAR nodes per patient.
- Demo data regenerated valid + high-resolution (`scripts/generate_demo_dvhs.py`).
- Tests: `tests/test_dvh_integrity.py` (validator, reader-rejects-inverted, targets-never-get-
  NTCP through the run controller, every shipped example valid). Fixed two engine reader
  fixtures and one e2e fixture that had encoded the inverted-DVH bug.

## E. Screenshots
Re-captured on the corrected data: DVH monotone with smooth shoulders; PTV70 shows
"n/a — target (PTV)"; Sankey excludes targets and is per-patient labelled.

## F. Things found that were not asked
- **Parotid_R** had the same out-of-order last-two-rows defect as Parotid_L (not only Parotid_L).
- `parse_dvh_text_file` coerces **every** single-file `canonical_name` to `PTV`, so the reader's
  own canonical could never be trusted to gate targets — classification must use `canon_target`.
- Existing engine/e2e test fixtures had themselves encoded the inverted-DVH bug (now corrected).
