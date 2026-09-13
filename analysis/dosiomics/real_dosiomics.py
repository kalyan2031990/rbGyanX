"""
REAL 3-D dosiomics (v2) — first-order + GLCM/GLRLM/GLSZM texture on the actual masked dose grid.

WHY THIS EXISTS
---------------
The shipped `attach_dosiomics_to_ntcp_results` calls `extract_oar_dose_volume(None, None, ...)`, so the
real-data branch is never taken and every feature came from `synthetic_oar_dose_voxels` — 500 Gaussian
voxels seeded only by the organ mean dose. Verified: the stored features reproduce exactly from the mean
dose alone, i.e. they carried no patient-specific spatial information.

This module computes dosiomics properly:
  * loads the RT Dose grid (scaled to Gy) and resamples to isotropic voxels,
  * rasterises the ROI contours to a 3-D mask,
  * extracts the masked dose sub-volume,
  * computes first-order statistics plus **GLCM, GLRLM and GLSZM texture matrices** on the discretised
    3-D dose distribution.

Only the DICOM cohort (TCIA_HN) has a dose grid. TPS-text cohorts (Parotid, SPARK) supply DVHs only, so
spatial texture is mathematically impossible for them and is reported as NOT APPLICABLE — never synthesised.

Outputs are written under a NEW label; existing results are not touched.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd  # noqa: E402

N_BINS = 32          # grey-level discretisation for texture (fixed bin count, documented)
MIN_VOXELS = 64      # below this a texture matrix is not meaningful
# Repo root, resolved from this file's location (analysis/dosiomics/). Was an absolute local path
# while the script lived outside version control; de-localised on import into the repository so the
# default works for any checkout. Overridable with --repo; the value used for the reported run
# resolved to the same tree.
REPO = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ feature families

def first_order(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {}
    p = np.percentile(v, [10, 25, 50, 75, 90])
    hist, _ = np.histogram(v, bins=N_BINS)
    pr = hist / max(hist.sum(), 1)
    nz = pr[pr > 0]
    return {
        "fo_mean": float(v.mean()), "fo_std": float(v.std(ddof=1)) if v.size > 1 else 0.0,
        "fo_min": float(v.min()), "fo_max": float(v.max()),
        "fo_p10": float(p[0]), "fo_p25": float(p[1]), "fo_median": float(p[2]),
        "fo_p75": float(p[3]), "fo_p90": float(p[4]), "fo_iqr": float(p[3] - p[1]),
        "fo_range": float(v.max() - v.min()),
        "fo_cv": float(v.std(ddof=1) / v.mean()) if v.size > 1 and v.mean() else math.nan,
        "fo_skewness": float(((v - v.mean()) ** 3).mean() / (v.std() ** 3)) if v.std() > 0 else math.nan,
        "fo_kurtosis": float(((v - v.mean()) ** 4).mean() / (v.std() ** 4) - 3) if v.std() > 0 else math.nan,
        "fo_energy": float(np.sum(v.astype(np.float64) ** 2)),
        "fo_entropy": float(-np.sum(nz * np.log2(nz))),
        "fo_uniformity": float(np.sum(pr ** 2)),
        "fo_mad": float(np.mean(np.abs(v - v.mean()))),
        "fo_rms": float(np.sqrt(np.mean(v.astype(np.float64) ** 2))),
        "fo_n_voxels": int(v.size),
    }


def _discretise(vol: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fixed-bin-count discretisation inside the mask; background = 0, levels 1..N_BINS."""
    out = np.zeros(vol.shape, dtype=np.int16)
    v = vol[mask]
    lo, hi = float(v.min()), float(v.max())
    if hi <= lo:
        out[mask] = 1
        return out
    lv = np.floor((v - lo) / (hi - lo) * (N_BINS - 1)).astype(int) + 1
    out[mask] = np.clip(lv, 1, N_BINS)
    return out


def glcm_features(disc: np.ndarray, mask: np.ndarray) -> dict:
    """GLCM averaged over the 13 unique 3-D directions (offset 1), computed slice-consistently."""
    from itertools import product
    dirs = [d for d in product((0, 1), (-1, 0, 1), (-1, 0, 1)) if d != (0, 0, 0)]
    dirs = [d for d in dirs if d >= (0, 0, 0)][:13]
    P = np.zeros((N_BINS + 1, N_BINS + 1), dtype=np.float64)
    for dz, dy, dx in dirs:
        a = disc[max(dz, 0):disc.shape[0] + min(dz, 0) or None,
                 max(dy, 0):disc.shape[1] + min(dy, 0) or None,
                 max(dx, 0):disc.shape[2] + min(dx, 0) or None]
        b = disc[max(-dz, 0):disc.shape[0] - max(dz, 0) or None,
                 max(-dy, 0):disc.shape[1] - max(dy, 0) or None,
                 max(-dx, 0):disc.shape[2] - max(dx, 0) or None]
        if a.shape != b.shape or a.size == 0:
            continue
        ok = (a > 0) & (b > 0)
        if not ok.any():
            continue
        np.add.at(P, (a[ok], b[ok]), 1.0)
    P = P[1:, 1:]
    P = P + P.T
    s = P.sum()
    if s <= 0:
        return {}
    P /= s
    i = np.arange(1, N_BINS + 1)
    Ig, Jg = np.meshgrid(i, i, indexing="ij")
    mu_i = float((Ig * P).sum())
    mu_j = float((Jg * P).sum())
    sd_i = math.sqrt(float((((Ig - mu_i) ** 2) * P).sum())) or 1e-12
    sd_j = math.sqrt(float((((Jg - mu_j) ** 2) * P).sum())) or 1e-12
    nz = P[P > 0]
    return {
        "glcm_contrast": float((((Ig - Jg) ** 2) * P).sum()),
        "glcm_dissimilarity": float((np.abs(Ig - Jg) * P).sum()),
        "glcm_homogeneity": float((P / (1.0 + (Ig - Jg) ** 2)).sum()),
        "glcm_asm": float((P ** 2).sum()),
        "glcm_energy": float(math.sqrt((P ** 2).sum())),
        "glcm_entropy": float(-(nz * np.log2(nz)).sum()),
        "glcm_correlation": float((((Ig - mu_i) * (Jg - mu_j) * P).sum()) / (sd_i * sd_j)),
        "glcm_joint_average": mu_i,
        "glcm_sum_average": float(((Ig + Jg) * P).sum()),
        "glcm_cluster_shade": float((((Ig + Jg - mu_i - mu_j) ** 3) * P).sum()),
        "glcm_cluster_prominence": float((((Ig + Jg - mu_i - mu_j) ** 4) * P).sum()),
        "glcm_inverse_variance": float(P[Ig != Jg].sum() and
                                       (P[Ig != Jg] / ((Ig - Jg) ** 2)[Ig != Jg]).sum()),
    }


def glrlm_features(disc: np.ndarray) -> dict:
    """Grey-level run-length matrix along the 3 axis directions (runs of equal level)."""
    Nr = max(disc.shape)
    R = np.zeros((N_BINS + 1, Nr + 1), dtype=np.float64)
    for axis in (0, 1, 2):
        arr = np.moveaxis(disc, axis, -1)
        flat = arr.reshape(-1, arr.shape[-1])
        for line in flat:
            if not line.any():
                continue
            prev, run = line[0], 1
            for x in line[1:]:
                if x == prev and x > 0:
                    run += 1
                else:
                    if prev > 0:
                        R[prev, min(run, Nr)] += 1
                    prev, run = x, 1
            if prev > 0:
                R[prev, min(run, Nr)] += 1
    R = R[1:, 1:]
    s = R.sum()
    if s <= 0:
        return {}
    i = np.arange(1, N_BINS + 1)[:, None]
    j = np.arange(1, R.shape[1] + 1)[None, :]
    Np = float((R * j).sum())
    return {
        "glrlm_sre": float((R / j ** 2).sum() / s),
        "glrlm_lre": float((R * j ** 2).sum() / s),
        "glrlm_gln": float((R.sum(axis=1) ** 2).sum() / s),
        "glrlm_rln": float((R.sum(axis=0) ** 2).sum() / s),
        "glrlm_rp": float(s / Np) if Np else math.nan,
        "glrlm_lgre": float((R / i ** 2).sum() / s),
        "glrlm_hgre": float((R * i ** 2).sum() / s),
        "glrlm_run_entropy": float(-((R / s)[R > 0] * np.log2((R / s)[R > 0])).sum()),
    }


def glszm_features(disc: np.ndarray) -> dict:
    """Grey-level size-zone matrix: connected 3-D zones of identical discretised level."""
    from scipy import ndimage
    zones: dict[tuple[int, int], int] = {}
    for lvl in range(1, N_BINS + 1):
        m = disc == lvl
        if not m.any():
            continue
        lab, n = ndimage.label(m)
        if n == 0:
            continue
        sizes = np.bincount(lab.ravel())[1:]
        for sz in sizes:
            zones[(lvl, int(sz))] = zones.get((lvl, int(sz)), 0) + 1
    if not zones:
        return {}
    max_sz = max(k[1] for k in zones)
    Z = np.zeros((N_BINS, max_sz), dtype=np.float64)
    for (lvl, sz), c in zones.items():
        Z[lvl - 1, sz - 1] = c
    s = Z.sum()
    i = np.arange(1, N_BINS + 1)[:, None]
    j = np.arange(1, max_sz + 1)[None, :]
    Nv = float((Z * j).sum())
    return {
        "glszm_sae": float((Z / j ** 2).sum() / s),
        "glszm_lae": float((Z * j ** 2).sum() / s),
        "glszm_gln": float((Z.sum(axis=1) ** 2).sum() / s),
        "glszm_szn": float((Z.sum(axis=0) ** 2).sum() / s),
        "glszm_zp": float(s / Nv) if Nv else math.nan,
        "glszm_lgze": float((Z / i ** 2).sum() / s),
        "glszm_hgze": float((Z * i ** 2).sum() / s),
        "glszm_zone_entropy": float(-((Z / s)[Z > 0] * np.log2((Z / s)[Z > 0])).sum()),
        "glszm_n_zones": int(s),
    }


# ------------------------------------------------------------------ per-patient extraction

def organ_features(rtdose: Path, rtstruct: Path, roi_names: list[str], voxel_mm: float = 3.0) -> dict:
    """REAL masked-dose features per ROI. Returns {} for ROIs that cannot be masked."""
    from rbgyanx_advanced.dose3d.dose_grid_extractor import (
        build_oar_mask,
        load_dose_grid,
        resample_to_isotropic,
    )
    import pydicom

    dd = load_dose_grid(rtdose)
    if dd is None:
        return {}
    dd = resample_to_isotropic(dd, voxel_mm)
    ds = pydicom.dcmread(str(rtstruct))
    num_by_name = {str(r.ROIName).strip().lower(): int(r.ROINumber)
                   for r in getattr(ds, "StructureSetROISequence", [])}
    seq_by_num = {int(rc.ReferencedROINumber): getattr(rc, "ContourSequence", [])
                  for rc in getattr(ds, "ROIContourSequence", [])}

    out: dict = {}
    for name in roi_names:
        num = num_by_name.get(name.strip().lower())
        if num is None or not seq_by_num.get(num):
            continue
        try:
            mask = build_oar_mask(seq_by_num[num], dd)
        except Exception:
            continue
        if mask.sum() < MIN_VOXELS:
            continue
        vol = np.asarray(dd["dose_array"], dtype=np.float32)
        vals = vol[mask]
        feats = first_order(vals)
        # crop to the mask bounding box so texture is computed on the organ, not the whole grid
        idx = np.argwhere(mask)
        lo, hi = idx.min(0), idx.max(0) + 1
        sub_v = vol[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
        sub_m = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
        disc = _discretise(sub_v, sub_m)
        feats.update(glcm_features(disc, sub_m))
        feats.update(glrlm_features(disc))
        feats.update(glszm_features(disc))
        for k, v in feats.items():
            out[f"rdx_{name}_{k}"] = v
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--staging", required=True, type=Path, help="TCIA_HN DICOM staging root")
    ap.add_argument("--map-csv", required=True, type=Path, help="TCIA_HN pseudonym map")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    for p in ("engine", "engine_advanced"):
        sys.path.insert(0, str(a.repo / p))
    from dicom_io.cohort_discovery import discover_cohort
    from dicom_io.structure_mapper import canon_target

    a.out.mkdir(parents=True, exist_ok=True)
    pmap = {r["raw_patient_key"]: r["pseudonym"]
            for r in pd.read_csv(a.map_csv).to_dict("records")}

    rows, skipped = [], []
    mans = [m for m in discover_cohort(a.staging) if m.degraded_mode == "FULL"]
    if a.limit:
        mans = mans[: a.limit]
    for i, m in enumerate(mans, 1):
        pse = pmap.get(m.patient_key)
        if not pse:
            continue
        import pydicom
        try:
            ds = pydicom.dcmread(str(m.rtstruct_path), stop_before_pixels=True)
            names = [str(r.ROIName) for r in getattr(ds, "StructureSetROISequence", [])]
        except Exception as exc:
            skipped.append({"pseudonym": pse, "reason": type(exc).__name__})
            continue
        # only OARs the engine recognises, so features align with the NTCP organs
        keep = [n for n in names if canon_target(n).get("category") == "OAR"]
        try:
            f = organ_features(m.rtdose_path, m.rtstruct_path, keep)
        except Exception as exc:
            skipped.append({"pseudonym": pse, "reason": type(exc).__name__})
            continue
        if not f:
            skipped.append({"pseudonym": pse, "reason": "no maskable ROI"})
            continue
        rows.append({"pseudonym": pse, **f})
        if i % 20 == 0:
            print(f"  {i}/{len(mans)} processed", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(a.out / "real_dosiomics_TCIA_HN_wide.csv", index=False)
    long = df.melt(id_vars="pseudonym", var_name="feature", value_name="value").dropna()
    long.to_csv(a.out / "real_dosiomics_TCIA_HN_long.csv", index=False)
    pd.DataFrame(skipped).to_csv(a.out / "real_dosiomics_skipped.csv", index=False)
    classes = sorted({f.split("_")[-2] if False else f.split("_", 2)[2].split("_")[0]
                      for f in df.columns if f.startswith("rdx_")})
    meta = {"cohort": "TCIA_HN", "patients": len(df),
            "features_per_patient": int(df.shape[1] - 1),
            "n_bins": N_BINS, "voxel_mm": 3.0, "min_voxels": MIN_VOXELS,
            "families": ["first-order", "GLCM", "GLRLM", "GLSZM"],
            "note": "computed on the REAL masked 3-D dose grid; supersedes the synthetic-voxel features",
            "not_applicable": {"Parotid": "TPS DVH text only - no 3-D dose grid",
                               "SPARK": "TPS DVH text only - no 3-D dose grid"}}
    (a.out / "real_dosiomics_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nREAL dosiomics: {len(df)} patients x {df.shape[1]-1} features; skipped {len(skipped)}")
    print(f"  families: first-order + GLCM + GLRLM + GLSZM (feature-name classes: {len(classes)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
