"""T1 - index every DICOM header in the TCIA / AIRTP archives.

The ZIP-level audit established modality *presence* per PatientID. Presence is not linkage: a patient
can have a CT and an RTDOSE that belong to different studies, different frames of reference, or a plan
that references a structure set which is not in the archive at all. Nothing downstream is safe until
the actual UID cross-references have been read, so this pass captures them.

Speed: a CT slice's header sits in the first few kilobytes, so CT members are stream-decompressed with
a small prefix instead of in full (a full read of ~37 700 CT slices would decompress ~8 GB). RT objects
are read whole because their reference sequences can sit well past any fixed prefix.

Output is one row per DICOM instance. TCIA PatientIDs are the collection's own de-identified
identifiers, but the index still lands outside the public repository.
"""

from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import pandas as pd
import pydicom

CT_PREFIX = 32 * 1024
CT_PREFIX_RETRY = 512 * 1024


def _first(seq, *path):
    """Walk a DICOM sequence path defensively; return None rather than raising."""
    cur = seq
    for p in path:
        try:
            cur = cur[0] if isinstance(cur, (list, pydicom.sequence.Sequence)) else cur
            cur = getattr(cur, p)
        except Exception:
            return None
    if isinstance(cur, (list, pydicom.sequence.Sequence)):
        cur = cur[0] if len(cur) else None
    return cur


def _read(zf: zipfile.ZipFile, name: str, size: int | None):
    with zf.open(name) as fh:
        raw = fh.read() if size is None else fh.read(size)
    return pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True, force=True)


def read_header(zf: zipfile.ZipFile, name: str):
    """Return (dataset, truncated) or (None, False).

    A prefix read is enough to identify the modality, but it silently truncates the reference
    sequences that RT objects carry - and a truncated sequence can parse to an EMPTY list instead of
    raising, which would quietly destroy the linkage this whole pass exists to establish. So the
    prefix is only ever trusted for CT; every RT object is re-read in full.
    """
    try:
        ds = _read(zf, name, CT_PREFIX)
    except Exception:
        ds = None
    mod = str(getattr(ds, "Modality", "") or "").strip().upper() if ds is not None else ""
    if mod == "CT":
        return ds, False
    for size in (CT_PREFIX_RETRY, None):
        try:
            ds2 = _read(zf, name, size)
            if str(getattr(ds2, "Modality", "") or "").strip():
                return ds2, size is not None
        except Exception:
            continue
    return (ds, True) if mod else (None, False)


def row_for(ds, zip_name: str, member: str) -> dict:
    mod = str(getattr(ds, "Modality", "") or "").upper().strip()
    r = {
        "zip": zip_name, "member": member, "modality": mod,
        "patient_id": str(getattr(ds, "PatientID", "") or "").strip(),
        "study_uid": str(getattr(ds, "StudyInstanceUID", "") or ""),
        "series_uid": str(getattr(ds, "SeriesInstanceUID", "") or ""),
        "sop_uid": str(getattr(ds, "SOPInstanceUID", "") or ""),
        "for_uid": str(getattr(ds, "FrameOfReferenceUID", "") or ""),
        "study_date": str(getattr(ds, "StudyDate", "") or ""),
        "series_desc": str(getattr(ds, "SeriesDescription", "") or "")[:80],
    }
    if mod == "CT":
        ipp = getattr(ds, "ImagePositionPatient", None)
        ps = getattr(ds, "PixelSpacing", None)
        r.update({
            "rows": int(getattr(ds, "Rows", 0) or 0),
            "cols": int(getattr(ds, "Columns", 0) or 0),
            "pixel_spacing": float(ps[0]) if ps else None,
            "slice_thickness": float(getattr(ds, "SliceThickness", 0) or 0) or None,
            "z_position": float(ipp[2]) if ipp else None,
            "kernel": str(getattr(ds, "ConvolutionKernel", "") or "")[:20],
        })
    elif mod == "RTSTRUCT":
        ref_series, ref_for = [], []
        for rfor in getattr(ds, "ReferencedFrameOfReferenceSequence", []) or []:
            ref_for.append(str(getattr(rfor, "FrameOfReferenceUID", "") or ""))
            for st in getattr(rfor, "RTReferencedStudySequence", []) or []:
                for se in getattr(st, "RTReferencedSeriesSequence", []) or []:
                    ref_series.append(str(getattr(se, "SeriesInstanceUID", "") or ""))
        rois = [str(getattr(x, "ROIName", "") or "")
                for x in getattr(ds, "StructureSetROISequence", []) or []]
        r.update({
            "ref_ct_series_uids": "|".join(sorted(set(x for x in ref_series if x))),
            "ref_for_uids": "|".join(sorted(set(x for x in ref_for if x))),
            "n_rois": len(rois), "roi_names": "|".join(rois)[:4000],
        })
    elif mod == "RTPLAN":
        fg = getattr(ds, "FractionGroupSequence", None)
        nfx = _first(fg, "NumberOfFractionsPlanned") if fg else None
        rx = None
        if fg:
            try:
                rb = fg[0].ReferencedBeamSequence
                rx = sum(float(getattr(b, "BeamDose", 0) or 0) for b in rb) or None
            except Exception:
                rx = None
            if rx is None:
                try:
                    rx = float(fg[0].ReferencedBrachyApplicationSetupSequence[0]
                               .BrachyApplicationSetupDose)
                except Exception:
                    rx = None
        tgt = None
        try:
            tgt = float(getattr(ds.DoseReferenceSequence[0], "TargetPrescriptionDose", None))
        except Exception:
            pass
        r.update({
            "ref_structset_sop": str(_first(getattr(ds, "ReferencedStructureSetSequence", None),
                                            "ReferencedSOPInstanceUID") or ""),
            "n_fractions_planned": int(nfx) if nfx not in (None, "") else None,
            "beam_dose_sum_gy": rx,
            "target_prescription_gy": tgt,
            "approval_status": str(getattr(ds, "ApprovalStatus", "") or ""),
            "plan_label": str(getattr(ds, "RTPlanLabel", "") or "")[:60],
        })
    elif mod == "RTDOSE":
        gfo = getattr(ds, "GridFrameOffsetVector", None)
        r.update({
            "ref_plan_sop": str(_first(getattr(ds, "ReferencedRTPlanSequence", None),
                                       "ReferencedSOPInstanceUID") or ""),
            "dose_units": str(getattr(ds, "DoseUnits", "") or ""),
            "dose_summation": str(getattr(ds, "DoseSummationType", "") or ""),
            "dose_grid_scaling": float(getattr(ds, "DoseGridScaling", 0) or 0) or None,
            "rows": int(getattr(ds, "Rows", 0) or 0),
            "cols": int(getattr(ds, "Columns", 0) or 0),
            "n_frames": len(gfo) if gfo is not None else None,
        })
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    zips = sorted(a.root.rglob("*.zip"))
    print(f"archives: {len(zips)}", flush=True)
    rows, skipped, t0 = [], [], time.time()
    for zp in zips:
        n_ok = n_bad = 0
        with zipfile.ZipFile(zp) as zf:
            members = [i.filename for i in zf.infolist() if not i.is_dir()]
            for j, name in enumerate(members):
                low = name.lower()
                if not (low.endswith((".dcm", ".dicom")) or "." not in Path(name).name):
                    continue
                ds, truncated = read_header(zf, name)
                if ds is None:
                    n_bad += 1
                    skipped.append({"zip": zp.name, "member": name, "reason": "unreadable header"})
                    continue
                try:
                    r = row_for(ds, zp.name, name)
                except Exception as exc:      # a sequence that only fails on access
                    n_bad += 1
                    skipped.append({"zip": zp.name, "member": name,
                                    "reason": f"{type(exc).__name__}: {str(exc)[:120]}"})
                    continue
                r["header_truncated"] = bool(truncated)
                rows.append(r)
                n_ok += 1
                if n_ok % 4000 == 0:
                    print(f"  {zp.name}: {n_ok}/{len(members)} "
                          f"({time.time() - t0:.0f}s)", flush=True)
        print(f"{zp.name}: {n_ok} indexed, {n_bad} unreadable", flush=True)

    idx = pd.DataFrame(rows)
    idx.to_csv(a.out / "T1_dicom_index.csv", index=False)
    pd.DataFrame(skipped).to_csv(a.out / "T1_unreadable.csv", index=False)

    summ = (idx.groupby(["zip", "modality"]).size().unstack(fill_value=0)
            .reset_index())
    summ.to_csv(a.out / "T1_zip_modality_counts.csv", index=False)
    (a.out / "T1_manifest.json").write_text(json.dumps({
        "archives": [str(z) for z in zips],
        "instances_indexed": int(len(idx)),
        "unreadable": int(len(skipped)),
        "unique_patient_ids": int(idx.patient_id.nunique()),
        "modalities": idx.modality.value_counts().to_dict(),
        "elapsed_s": round(time.time() - t0, 1),
        "ct_prefix_bytes": CT_PREFIX,
    }, indent=2), encoding="utf-8")
    print(f"indexed {len(idx)} instances, {idx.patient_id.nunique()} patients, "
          f"{time.time() - t0:.0f}s", flush=True)
    print(summ.to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
