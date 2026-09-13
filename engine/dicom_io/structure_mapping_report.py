"""
Structure mapping report (Phase 3.1).

Maps every ROI in an RT Structure Set to its canonical name and classifies the outcome as
**mapped / ambiguous / unmapped** — never silently discarding a structure. Unmapped ROIs are returned
with their raw names so the authors can extend the alias dictionary. Additive; wraps
``structure_mapper.canon_target`` (unchanged).

ROI names are anatomical labels, not patient identifiers; still, callers writing this to disk should
route it through the Phase-5 pseudonymised QA path (constraint C2).
"""

from __future__ import annotations

from dicom_io.structure_mapper import canon_target


def _rois(rt_struct_ds) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for roi in getattr(rt_struct_ds, "StructureSetROISequence", []) or []:
        try:
            out.append(
                (int(roi.ROINumber), str(roi.ROIName), str(getattr(roi, "RTROIInterpretedType", "") or ""))
            )
        except Exception:
            continue  # a malformed ROI item — skip it, do not abort the report
    return sorted(out)


def structure_mapping_report(rt_struct_ds) -> dict:
    """Return per-ROI mapping outcome plus mapped/ambiguous/unmapped counts and the mapping rate.

    status is 'mapped' (canonical, MEDIUM/HIGH confidence), 'ambiguous' (canonical but LOW confidence),
    or 'unmapped' (category UNKNOWN — raw name preserved). Every ROI appears in `rows`.
    """
    rows: list[dict] = []
    mapped = ambiguous = unmapped = 0
    for num, name, rtype in _rois(rt_struct_ds):
        m = canon_target(name, rtype or None)
        if m["category"] == "UNKNOWN":
            status = "unmapped"
            unmapped += 1
        elif m["confidence"] == "LOW":
            status = "ambiguous"
            ambiguous += 1
        else:
            status = "mapped"
            mapped += 1
        rows.append(
            {
                "roi_number": num,
                "raw_name": name,
                "canonical": m["canonical"],
                "category": m["category"],
                "confidence": m["confidence"],
                "status": status,
            }
        )
    total = len(rows)
    return {
        "total": total,
        "mapped": mapped,
        "ambiguous": ambiguous,
        "unmapped": unmapped,
        "mapping_rate": (mapped / total) if total else 0.0,
        "unmapped_raw_names": [r["raw_name"] for r in rows if r["status"] == "unmapped"],
        "ambiguous_raw_names": [r["raw_name"] for r in rows if r["status"] == "ambiguous"],
        "rows": rows,
    }


def aggregate_reports(reports: list[dict]) -> dict:
    """Cohort-level roll-up over per-patient reports: totals + the union of unmapped raw names so the
    authors get one list to extend the dictionary from."""
    unmapped_names: dict[str, int] = {}
    totals = {"total": 0, "mapped": 0, "ambiguous": 0, "unmapped": 0}
    for rep in reports:
        for k in totals:
            totals[k] += int(rep.get(k, 0))
        for name in rep.get("unmapped_raw_names", []):
            unmapped_names[name] = unmapped_names.get(name, 0) + 1
    totals["mapping_rate"] = (totals["mapped"] / totals["total"]) if totals["total"] else 0.0
    totals["unmapped_raw_names"] = dict(sorted(unmapped_names.items(), key=lambda kv: (-kv[1], kv[0])))
    return totals
