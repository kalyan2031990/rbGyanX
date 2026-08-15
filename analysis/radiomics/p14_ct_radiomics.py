"""Phase 14 - full CT radiomics extraction on the UID-reconciled TCIA multimodal cohort.

Inputs come from the T1-T4 linkage, so every patient here has a CT series that its own RTSTRUCT
references, in the frame of reference the dose grid uses. RTDOSE-only patients are structurally absent.

Pipeline per patient
--------------------
1. read the linked CT series from its ZIP, rescale to HU, sort by ImagePositionPatient[2];
2. reject gantry tilt (ImageOrientationPatient must be axial to 1e-3);
3. resample to 2 mm isotropic (trilinear for HU, nearest for masks);
4. rasterise each selected ROI from the RTSTRUCT contours onto that grid;
5. clip HU to [-1000, 3000] and discretise with a FIXED BIN WIDTH of 25 HU (IBSI's recommendation for
   CT, where HU is a calibrated absolute scale - unlike the dose grid, where v2 used a fixed bin count);
6. compute shape, first-order, GLCM, GLRLM, GLSZM, GLDM and NGTDM.

Implementation note that must reach the manuscript
--------------------------------------------------
pyradiomics does not build on this Python (3.14) and SimpleITK is unavailable, so the feature engine is
the project's own IBSI-aligned implementation, extended here with GLDM, NGTDM and shape. It has NOT
been benchmarked against the IBSI digital phantom, so absolute feature values are not guaranteed
interchangeable with pyradiomics-derived values in the literature. Within-study comparisons are
unaffected because every patient goes through the identical code path. This is recorded as a
limitation rather than glossed over.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pydicom
from scipy import ndimage

VOXEL_MM = 2.0
BIN_WIDTH_HU = 25.0
HU_CLIP = (-1000.0, 3000.0)
MIN_VOXELS = 64
MAX_LEVELS = 200

# Pre-specified ROI set, fixed AFTER inventorying the 53 distinct ROI names that actually occur in
# these structure sets (see T2_rtstruct_links.csv). Two consequences of that inventory:
#   * this AIRTP-curated collection contains NO GTV and NO CTV - only PTVs. Gross-tumour radiomics is
#     therefore impossible here and is reported as unavailable rather than approximated by a PTV.
#   * the salivary glands are contoured BILATERALLY as `Parotids` and `Submandibular`. There is no
#     left/right split, so no lateralised parotid result exists or may be claimed.
# The `-PTV` variants (e.g. `Parotids-PTV`) are Boolean subtractions used for optimisation, not
# anatomy, and are excluded.
ROI_PATTERNS = {
    "PTV_high": ("ptv70",),
    "PTV_total": ("ptv_total",),
    "PTV_low": ("ptvlow",),
    "Parotids": ("parotids",),
    "Submandibular": ("submandibular",),
    "PharynxConstrictor": ("pharynxconst", "pharconst"),
    "OralCavity": ("oralcavity", "oral cavity", "ocavity"),
    "Larynx": ("larynx",),
    "Mandible": ("mandible",),
    "SpinalCord": ("spinalcord", "spinal cord"),
    "BrainStem": ("brainstem", "brain stem"),
    "Thyroid": ("thyroid",),
    "Lips": ("lips",),
    "BrachialPlexus": ("brachialplexus", "brachial plexus"),
    "Esophagus": ("esophagus", "oesophagus"),
    "Lungs": ("lungs",),
}
EXCLUDE_TOKENS = ("prv", "opt", "-ptv", "ring", "avoid", "help", "dummy", "z_", "bolus",
                  "_05", "_03")


# ----------------------------------------------------------------- discretisation & texture

def discretise_fbw(vol: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Fixed-bin-width discretisation inside the mask; background 0, levels 1..n."""
    out = np.zeros(vol.shape, dtype=np.int16)
    v = np.clip(vol[mask], *HU_CLIP)
    lo = float(np.floor(v.min() / BIN_WIDTH_HU) * BIN_WIDTH_HU)
    lv = np.floor((v - lo) / BIN_WIDTH_HU).astype(int) + 1
    nl = int(min(lv.max(), MAX_LEVELS))
    out[mask] = np.clip(lv, 1, nl)
    return out, nl


def f_shape(mask: np.ndarray, spacing: float) -> dict:
    n = int(mask.sum())
    vox = spacing ** 3
    vol = n * vox
    # surface from the 6-neighbour boundary face count (voxel-counting approximation)
    faces = 0
    for ax in (0, 1, 2):
        d = np.diff(mask.astype(np.int8), axis=ax)
        faces += int(np.abs(d).sum())
        sl0 = [slice(None)] * 3
        sl1 = [slice(None)] * 3
        sl0[ax] = 0
        sl1[ax] = -1
        faces += int(mask[tuple(sl0)].sum() + mask[tuple(sl1)].sum())
    surf = faces * spacing ** 2
    idx = np.argwhere(mask)
    ext = (idx.max(0) - idx.min(0) + 1) * spacing
    c = idx.mean(0)
    d2 = ((idx - c) ** 2).sum(1) * spacing ** 2
    # principal axes of the voxel cloud -> elongation / flatness
    cov = np.cov(((idx - c) * spacing).T) if n > 3 else np.eye(3)
    ev = np.sort(np.linalg.eigvalsh(cov))[::-1] if np.all(np.isfinite(cov)) else np.ones(3)
    ev = np.clip(ev, 1e-9, None)
    return {
        "shape_volume_mm3": float(vol),
        "shape_surface_mm2": float(surf),
        "shape_sa_to_vol": float(surf / vol) if vol else math.nan,
        "shape_sphericity": float((math.pi ** (1 / 3)) * ((6 * vol) ** (2 / 3)) / surf) if surf else math.nan,
        "shape_compactness": float(vol / (surf ** 1.5)) if surf else math.nan,
        "shape_max_extent_mm": float(ext.max()),
        "shape_extent_x_mm": float(ext[2]), "shape_extent_y_mm": float(ext[1]),
        "shape_extent_z_mm": float(ext[0]),
        "shape_max_radius_mm": float(np.sqrt(d2.max())),
        "shape_mean_radius_mm": float(np.sqrt(d2).mean()),
        "shape_elongation": float(math.sqrt(ev[1] / ev[0])),
        "shape_flatness": float(math.sqrt(ev[2] / ev[0])),
        "shape_n_voxels": n,
    }


def f_first_order(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)].astype(np.float64)
    if v.size == 0:
        return {}
    p = np.percentile(v, [10, 25, 50, 75, 90])
    hist, _ = np.histogram(v, bins=64)
    pr = hist / max(hist.sum(), 1)
    nz = pr[pr > 0]
    sd = v.std(ddof=1) if v.size > 1 else 0.0
    sd_pop = v.std() if v.size > 1 else 0.0      # IBSI moments use the population SD
    return {
        "fo_mean": float(v.mean()), "fo_std": float(sd),
        "fo_min": float(v.min()), "fo_max": float(v.max()),
        "fo_p10": float(p[0]), "fo_p25": float(p[1]), "fo_median": float(p[2]),
        "fo_p75": float(p[3]), "fo_p90": float(p[4]), "fo_iqr": float(p[3] - p[1]),
        "fo_range": float(v.max() - v.min()),
        "fo_skewness": (float(((v - v.mean()) ** 3).mean() / sd_pop ** 3)
                        if sd_pop > 0 else math.nan),
        "fo_kurtosis": (float(((v - v.mean()) ** 4).mean() / sd_pop ** 4 - 3)
                        if sd_pop > 0 else math.nan),
        "fo_energy": float((v ** 2).sum()),
        "fo_entropy": float(-(nz * np.log2(nz)).sum()),
        "fo_uniformity": float((pr ** 2).sum()),
        "fo_mad": float(np.abs(v - v.mean()).mean()),
        "fo_rms": float(np.sqrt((v ** 2).mean())),
        "fo_n_voxels": int(v.size),
    }


def f_glcm(disc: np.ndarray, nl: int) -> dict:
    from itertools import product
    dirs = [d for d in product((0, 1), (-1, 0, 1), (-1, 0, 1)) if d != (0, 0, 0) and d >= (0, 0, 0)][:13]
    P = np.zeros((nl + 1, nl + 1), dtype=np.float64)
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
        if ok.any():
            np.add.at(P, (a[ok], b[ok]), 1.0)
    P = P[1:, 1:]
    P = P + P.T
    s = P.sum()
    if s <= 0:
        return {}
    P /= s
    i = np.arange(1, nl + 1)
    Ig, Jg = np.meshgrid(i, i, indexing="ij")
    mu_i = float((Ig * P).sum())
    mu_j = float((Jg * P).sum())
    sd_i = math.sqrt(float((((Ig - mu_i) ** 2) * P).sum())) or 1e-12
    sd_j = math.sqrt(float((((Jg - mu_j) ** 2) * P).sum())) or 1e-12
    nz = P[P > 0]
    off = Ig != Jg
    # marginal distributions for the sum/difference features
    k_sum = np.arange(2, 2 * nl + 1)
    ps = np.array([P[(Ig + Jg) == k].sum() for k in k_sum])
    k_dif = np.arange(0, nl)
    pd_ = np.array([P[np.abs(Ig - Jg) == k].sum() for k in k_dif])
    nzs, nzd = ps[ps > 0], pd_[pd_ > 0]
    return {
        "glcm_contrast": float((((Ig - Jg) ** 2) * P).sum()),
        "glcm_dissimilarity": float((np.abs(Ig - Jg) * P).sum()),
        "glcm_homogeneity": float((P / (1.0 + (Ig - Jg) ** 2)).sum()),
        "glcm_asm": float((P ** 2).sum()),
        "glcm_energy": float(math.sqrt((P ** 2).sum())),
        "glcm_entropy": float(-(nz * np.log2(nz)).sum()),
        "glcm_correlation": float(((Ig - mu_i) * (Jg - mu_j) * P).sum() / (sd_i * sd_j)),
        "glcm_joint_average": mu_i,
        "glcm_sum_average": float(((Ig + Jg) * P).sum()),
        "glcm_sum_entropy": float(-(nzs * np.log2(nzs)).sum()),
        "glcm_difference_entropy": float(-(nzd * np.log2(nzd)).sum()),
        "glcm_difference_average": float((k_dif * pd_).sum()),
        "glcm_cluster_shade": float((((Ig + Jg - mu_i - mu_j) ** 3) * P).sum()),
        "glcm_cluster_prominence": float((((Ig + Jg - mu_i - mu_j) ** 4) * P).sum()),
        "glcm_cluster_tendency": float((((Ig + Jg - mu_i - mu_j) ** 2) * P).sum()),
        "glcm_inverse_variance": float((P[off] / ((Ig - Jg) ** 2)[off]).sum()) if off.any() else math.nan,
        "glcm_autocorrelation": float((Ig * Jg * P).sum()),
        "glcm_max_probability": float(P.max()),
    }


def f_glrlm(disc: np.ndarray, nl: int) -> dict:
    """Run-length matrix along the three axis directions.

    Vectorised: the per-line Python loop it replaces was the single largest cost in the extraction
    (millions of interpreter iterations per ROI). Lines are concatenated with a zero sentinel between
    them so no run can span a line boundary, then run starts are found with a single diff.
    """
    from itertools import product
    # IBSI averages the run-length matrix over the 13 unique 3-D directions. An earlier version used
    # only the 3 axis directions, which failed every GLRLM feature on the IBSI digital phantom
    # (e.g. GLN 44.0 against a benchmark of 21.8). All 13 are now traversed.
    dirs = [d for d in product((0, 1), (-1, 0, 1), (-1, 0, 1))
            if d != (0, 0, 0) and d >= (0, 0, 0)][:13]
    Nr = max(disc.shape)
    R = np.zeros((nl + 1, Nr + 2), dtype=np.float64)

    def shifted(a, d, fill=0):
        """a shifted so that out[i] == a[i + d]; out-of-bounds filled with `fill`."""
        out = np.full_like(a, fill)
        src = tuple(slice(max(k, 0), a.shape[i] + min(k, 0)) for i, k in enumerate(d))
        dst = tuple(slice(max(-k, 0), a.shape[i] - max(k, 0)) for i, k in enumerate(d))
        out[dst] = a[src]
        return out

    for d in dirs:
        prev = shifted(disc, tuple(-k for k in d))         # the voxel before, along d
        start = (disc > 0) & (prev != disc)                # run starts
        if not start.any():
            continue
        # walk forward from every run start simultaneously: at step k, a start is still "alive" only
        # if every voxel from offset 0..k matched, so the accumulated count is the run length
        lengths = np.zeros(disc.shape, dtype=np.int32)
        alive = start.copy()
        for k in range(Nr):
            vk = shifted(disc, tuple(k * di for di in d))
            match = alive & (vk == disc) & (disc > 0)
            if not match.any():
                break
            lengths += match.astype(np.int32)
            alive = match
        v = disc[start].astype(int)
        L = np.minimum(lengths[start], Nr).astype(int)
        np.add.at(R, (v, L), 1.0)
    R = R[1:, 1:]
    s = R.sum()
    if s <= 0:
        return {}
    i = np.arange(1, nl + 1)[:, None]
    j = np.arange(1, R.shape[1] + 1)[None, :]
    Np = float((R * j).sum())
    Pn = R / s
    return {
        "glrlm_sre": float((R / j ** 2).sum() / s),
        "glrlm_lre": float((R * j ** 2).sum() / s),
        "glrlm_gln": float((R.sum(1) ** 2).sum() / s),
        "glrlm_gln_norm": float((R.sum(1) ** 2).sum() / s ** 2),
        "glrlm_rln": float((R.sum(0) ** 2).sum() / s),
        "glrlm_rln_norm": float((R.sum(0) ** 2).sum() / s ** 2),
        "glrlm_rp": float(s / Np) if Np else math.nan,
        "glrlm_lgre": float((R / i ** 2).sum() / s),
        "glrlm_hgre": float((R * i ** 2).sum() / s),
        "glrlm_srlge": float((R / (i ** 2 * j ** 2)).sum() / s),
        "glrlm_srhge": float((R * i ** 2 / j ** 2).sum() / s),
        "glrlm_lrlge": float((R * j ** 2 / i ** 2).sum() / s),
        "glrlm_lrhge": float((R * i ** 2 * j ** 2).sum() / s),
        "glrlm_run_variance": float((Pn * (j - (Pn * j).sum()) ** 2).sum()),
        "glrlm_run_entropy": float(-(Pn[Pn > 0] * np.log2(Pn[Pn > 0])).sum()),
    }


def f_glszm(disc: np.ndarray, nl: int) -> dict:
    zones: dict[tuple[int, int], int] = {}
    # iterate ONLY over levels present in this ROI; with fixed-bin-width CT most of the 1..nl range
    # is empty and calling ndimage.label on each empty level dominated the runtime
    for lvl in np.unique(disc[disc > 0]):
        lvl = int(lvl)
        m = disc == lvl
        if not m.any():
            continue
        # IBSI GLSZM uses 26-connectivity; scipy's default 6-connectivity splits
        # diagonally-touching voxels into separate zones and fails the benchmark
        lab, n = ndimage.label(m, structure=np.ones((3, 3, 3)))
        if n:
            for sz in np.bincount(lab.ravel())[1:]:
                zones[(lvl, int(sz))] = zones.get((lvl, int(sz)), 0) + 1
    if not zones:
        return {}
    mx = max(k[1] for k in zones)
    Z = np.zeros((nl, mx), dtype=np.float64)
    for (lvl, sz), c in zones.items():
        Z[lvl - 1, sz - 1] = c
    s = Z.sum()
    i = np.arange(1, nl + 1)[:, None]
    j = np.arange(1, mx + 1)[None, :]
    Nv = float((Z * j).sum())
    Pn = Z / s
    return {
        "glszm_sae": float((Z / j ** 2).sum() / s),
        "glszm_lae": float((Z * j ** 2).sum() / s),
        "glszm_gln": float((Z.sum(1) ** 2).sum() / s),
        "glszm_gln_norm": float((Z.sum(1) ** 2).sum() / s ** 2),
        "glszm_szn": float((Z.sum(0) ** 2).sum() / s),
        "glszm_szn_norm": float((Z.sum(0) ** 2).sum() / s ** 2),
        "glszm_zp": float(s / Nv) if Nv else math.nan,
        "glszm_lgze": float((Z / i ** 2).sum() / s),
        "glszm_hgze": float((Z * i ** 2).sum() / s),
        "glszm_salgze": float((Z / (i ** 2 * j ** 2)).sum() / s),
        "glszm_sahgze": float((Z * i ** 2 / j ** 2).sum() / s),
        "glszm_lalgze": float((Z * j ** 2 / i ** 2).sum() / s),
        "glszm_lahgze": float((Z * i ** 2 * j ** 2).sum() / s),
        "glszm_zone_variance": float((Pn * (j - (Pn * j).sum()) ** 2).sum()),
        "glszm_zone_entropy": float(-(Pn[Pn > 0] * np.log2(Pn[Pn > 0])).sum()),
        "glszm_n_zones": int(s),
    }


def f_gldm(disc: np.ndarray, nl: int, alpha: int = 0) -> dict:
    """Grey-level dependence: per voxel, how many of its 26 neighbours are within alpha levels."""
    m = disc > 0
    dep = np.zeros(disc.shape, dtype=np.int16)
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dz == dy == dx == 0:
                    continue
                sh = np.roll(np.roll(np.roll(disc, dz, 0), dy, 1), dx, 2)
                shm = np.roll(np.roll(np.roll(m, dz, 0), dy, 1), dx, 2)
                dep += ((np.abs(disc - sh) <= alpha) & shm & m).astype(np.int16)
    dep = dep + 1                                  # dependence counts the voxel itself
    D = np.zeros((nl + 1, 28), dtype=np.float64)
    np.add.at(D, (disc[m], np.clip(dep[m], 1, 27)), 1.0)
    D = D[1:, 1:]
    s = D.sum()
    if s <= 0:
        return {}
    i = np.arange(1, nl + 1)[:, None]
    j = np.arange(1, D.shape[1] + 1)[None, :]
    Pn = D / s
    return {
        "gldm_sde": float((D / j ** 2).sum() / s),
        "gldm_lde": float((D * j ** 2).sum() / s),
        "gldm_gln": float((D.sum(1) ** 2).sum() / s),
        "gldm_dn": float((D.sum(0) ** 2).sum() / s),
        "gldm_dn_norm": float((D.sum(0) ** 2).sum() / s ** 2),
        "gldm_lgle": float((D / i ** 2).sum() / s),
        "gldm_hgle": float((D * i ** 2).sum() / s),
        "gldm_sdlgle": float((D / (i ** 2 * j ** 2)).sum() / s),
        "gldm_sdhgle": float((D * i ** 2 / j ** 2).sum() / s),
        "gldm_ldlgle": float((D * j ** 2 / i ** 2).sum() / s),
        "gldm_ldhgle": float((D * i ** 2 * j ** 2).sum() / s),
        "gldm_dependence_variance": float((Pn * (j - (Pn * j).sum()) ** 2).sum()),
        "gldm_dependence_entropy": float(-(Pn[Pn > 0] * np.log2(Pn[Pn > 0])).sum()),
        "gldm_gl_variance": float((Pn * (i - (Pn * i).sum()) ** 2).sum()),
    }


def f_ngtdm(disc: np.ndarray, nl: int) -> dict:
    """Neighbourhood grey-tone difference, 26-neighbourhood, distance 1."""
    m = (disc > 0).astype(np.float64)
    v = disc.astype(np.float64) * m
    k = np.ones((3, 3, 3))
    k[1, 1, 1] = 0
    nsum = ndimage.convolve(v, k, mode="constant")
    ncnt = ndimage.convolve(m, k, mode="constant")
    valid = (disc > 0) & (ncnt > 0)
    if not valid.any():
        return {}
    avg = np.zeros_like(v)
    avg[valid] = nsum[valid] / ncnt[valid]
    s_i = np.zeros(nl + 1)
    n_i = np.zeros(nl + 1)
    np.add.at(s_i, disc[valid], np.abs(disc[valid] - avg[valid]))
    np.add.at(n_i, disc[valid], 1.0)
    s_i, n_i = s_i[1:], n_i[1:]
    N = n_i.sum()
    if N <= 0:
        return {}
    p = n_i / N
    i = np.arange(1, nl + 1)
    nz = p > 0
    coarse = float(1.0 / max((p * s_i).sum(), 1e-12))
    ii, jj = np.meshgrid(i[nz], i[nz], indexing="ij")
    pi, pj = p[nz][:, None], p[nz][None, :]
    si, sj = s_i[nz][:, None], s_i[nz][None, :]
    Ng = int(nz.sum())
    contrast = float(((pi * pj * (ii - jj) ** 2).sum() / max(Ng * (Ng - 1), 1)) *
                     (s_i.sum() / max(N, 1)))
    busy_den = float(np.abs(ii * pi - jj * pj).sum())
    return {
        "ngtdm_coarseness": coarse,
        "ngtdm_contrast": contrast,
        "ngtdm_busyness": float((p * s_i).sum() / busy_den) if busy_den else math.nan,
        "ngtdm_complexity": float((np.abs(ii - jj) / (pi + pj) *
                                   (pi * si + pj * sj)).sum() / max(N, 1)),
        "ngtdm_strength": float(((pi + pj) * (ii - jj) ** 2).sum() /
                                max(s_i.sum(), 1e-12)),
    }


# ----------------------------------------------------------------- CT + RTSTRUCT loading

def load_ct(zf: zipfile.ZipFile, members: list[str]):
    slices = []
    for name in members:
        with zf.open(name) as fh:
            ds = pydicom.dcmread(io.BytesIO(fh.read()), force=True)
        if not hasattr(ds, "pixel_array"):
            continue
        iop = [float(x) for x in getattr(ds, "ImageOrientationPatient", [1, 0, 0, 0, 1, 0])]
        if max(abs(np.array(iop) - np.array([1, 0, 0, 0, 1, 0]))) > 1e-3:
            raise ValueError("non-axial ImageOrientationPatient (gantry tilt or oblique)")
        slices.append((float(ds.ImagePositionPatient[2]), ds))
    if len(slices) < 2:
        raise ValueError("fewer than two readable CT slices")
    slices.sort(key=lambda t: t[0])
    ref = slices[0][1]
    arr = np.stack([s[1].pixel_array.astype(np.float32) for s in slices], axis=0)
    slope = float(getattr(ref, "RescaleSlope", 1) or 1)
    icpt = float(getattr(ref, "RescaleIntercept", 0) or 0)
    hu = arr * slope + icpt
    ps = [float(x) for x in ref.PixelSpacing]
    z = np.array([s[0] for s in slices])
    return {
        "hu": hu,
        "origin": np.array([float(ref.ImagePositionPatient[0]),
                            float(ref.ImagePositionPatient[1]), z[0]]),
        "spacing": np.array([float(np.median(np.diff(z))), ps[0], ps[1]]),  # z, y, x
        "z": z,
    }


def resample_iso(ct: dict, mm: float):
    zf_, yf, xf = ct["spacing"] / mm
    hu = ndimage.zoom(ct["hu"], (zf_, yf, xf), order=1, prefilter=False)
    return {"hu": hu, "origin": ct["origin"], "spacing": np.array([mm, mm, mm])}


def rasterise(contours, grid) -> np.ndarray:
    from matplotlib.path import Path as MplPath
    nz, ny, nx = grid["hu"].shape
    ox, oy, oz = grid["origin"]
    sz, sy, sx = grid["spacing"]
    mask = np.zeros((nz, ny, nx), dtype=bool)
    for c in contours:
        data = getattr(c, "ContourData", None)
        if data is None or len(data) < 9:
            continue
        p = np.array(data, dtype=float).reshape(-1, 3)
        k = int(round((p[0, 2] - oz) / sz))
        if not (0 <= k < nz):
            continue
        poly = np.column_stack([(p[:, 0] - ox) / sx, (p[:, 1] - oy) / sy])
        # test only the polygon's bounding box, not the whole 512x512 slice: an organ occupies a
        # few percent of the field, and testing every pixel of every slice dominated the runtime
        x0 = max(int(np.floor(poly[:, 0].min())) - 1, 0)
        x1 = min(int(np.ceil(poly[:, 0].max())) + 2, nx)
        y0 = max(int(np.floor(poly[:, 1].min())) - 1, 0)
        y1 = min(int(np.ceil(poly[:, 1].max())) + 2, ny)
        if x1 <= x0 or y1 <= y0:
            continue
        gy, gx = np.mgrid[y0:y1, x0:x1]
        inside = MplPath(poly).contains_points(
            np.column_stack([gx.ravel(), gy.ravel()])).reshape(y1 - y0, x1 - x0)
        mask[k, y0:y1, x0:x1] ^= inside      # XOR so inner contours cut holes
    # contours exist only on original slice positions; fill the gaps left by resampling
    filled = mask.any(axis=(1, 2))
    if filled.sum() >= 2:
        idx = np.where(filled)[0]
        for k0, k1 in zip(idx[:-1], idx[1:]):
            if k1 - k0 > 1:
                for k in range(k0 + 1, k1):
                    mask[k] = mask[k0] if (k - k0) <= (k1 - k) else mask[k1]
    return mask


def pick_rois(names: list[str]) -> dict:
    out = {}
    for canon, pats in ROI_PATTERNS.items():
        best = None
        for n in names:
            low = n.strip().lower()
            if any(t in low for t in EXCLUDE_TOKENS):
                continue
            if any(p in low.replace("-", "_").replace(" ", " ") for p in pats):
                if best is None or len(low) < len(best.strip().lower()):
                    best = n
        if best:
            out[canon] = best
    return out


# ----------------------------------------------------------------- driver

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--linkage-dir", required=True, type=Path)
    ap.add_argument("--zip-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=0)
    # extraction is independent per patient, so the cohort is sharded across worker processes;
    # each shard keeps its own checkpoint and the assembler merges them
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    chain = pd.read_csv(a.linkage_dir / "T2_patient_chain.csv", low_memory=False)
    elig = pd.read_csv(a.linkage_dir / "T4_cohort_TIER_B_multimodal.csv")
    idx = pd.read_csv(a.linkage_dir / "T1_dicom_index.csv", low_memory=False)
    ctidx = idx[idx.modality == "CT"]
    chain = chain[chain.patient_id.astype(str).isin(set(elig.patient_id.astype(str)))]
    if a.limit:
        chain = chain.head(a.limit)
    if a.shard_count > 1:
        chain = chain.reset_index(drop=True)
        chain = chain[chain.index % a.shard_count == a.shard_index].reset_index(drop=True)
        print(f"shard {a.shard_index}/{a.shard_count}: {len(chain)} patients", flush=True)

    zips = {p.name: p for p in a.zip_root.rglob("*.zip")}
    handles: dict[str, zipfile.ZipFile] = {}

    def zh(name):
        if name not in handles:
            handles[name] = zipfile.ZipFile(zips[name])
        return handles[name]

    # per-patient checkpoint so an interrupted run resumes instead of restarting
    tag = "" if a.shard_count <= 1 else f"_s{a.shard_index}"
    ck_feat = a.out / f"_checkpoint_features{tag}.jsonl"
    ck_qc = a.out / f"_checkpoint_qc{tag}.jsonl"
    # a shard also honours any checkpoint already written by an earlier unsharded run
    prior_qc = a.out / "_checkpoint_qc.jsonl"
    prior_feat = a.out / "_checkpoint_features.jsonl"
    rows, qc = [], []
    done: set[str] = set()
    seen_feat, seen_qc = [], []
    for f_, sink in ((ck_feat, seen_feat), (ck_qc, seen_qc)):
        if f_.exists():
            for line in f_.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    sink.append(json.loads(line))
    rows, qc = seen_feat, seen_qc
    done = {str(x["patient_id"]) for x in qc}
    if tag and prior_qc.exists():
        for line in prior_qc.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(str(json.loads(line)["patient_id"]))
    if done:
        print(f"resuming: {len(done)} patients already checkpointed", flush=True)
    t0 = time.time()
    fh_feat = open(ck_feat, "a", encoding="utf-8")
    fh_qc = open(ck_qc, "a", encoding="utf-8")
    for i, (_, r) in enumerate(chain.iterrows(), 1):
        pid = str(r.patient_id)
        if pid in done:
            continue
        try:
            cts = ctidx[(ctidx.patient_id == pid) & (ctidx.series_uid == r.ct_series_uid)]
            members = cts.sort_values("z_position")["member"].tolist()
            zname = cts["zip"].iloc[0]
            ct = load_ct(zh(zname), members)
            grid = resample_iso(ct, VOXEL_MM)
            with zh(r.rtstruct_zip).open(r.rtstruct_member) as fh:
                ss = pydicom.dcmread(io.BytesIO(fh.read()), force=True)
        except Exception as exc:
            qc.append({"patient_id": pid, "roi": "", "status": "PATIENT_FAILED",
                       "reason": f"{type(exc).__name__}: {str(exc)[:150]}"})
            continue

        names = [str(x.ROIName) for x in getattr(ss, "StructureSetROISequence", [])]
        num_by_name = {str(x.ROIName): int(x.ROINumber)
                       for x in getattr(ss, "StructureSetROISequence", [])}
        seq_by_num = {int(rc.ReferencedROINumber): getattr(rc, "ContourSequence", [])
                      for rc in getattr(ss, "ROIContourSequence", [])}
        chosen = pick_rois(names)
        if not chosen:
            qc.append({"patient_id": pid, "roi": "", "status": "PATIENT_FAILED",
                       "reason": f"no ROI matched the pre-specified set (had {len(names)})"})
            continue

        got = 0
        for canon, raw in chosen.items():
            try:
                seq = seq_by_num.get(num_by_name[raw], [])
                if not seq:
                    qc.append({"patient_id": pid, "roi": canon, "status": "SKIPPED",
                               "reason": "ROI has no contour sequence"})
                    continue
                mask = rasterise(seq, grid)
                n = int(mask.sum())
                if n < MIN_VOXELS:
                    qc.append({"patient_id": pid, "roi": canon, "status": "SKIPPED",
                               "reason": f"only {n} voxels at {VOXEL_MM} mm (< {MIN_VOXELS})"})
                    continue
                sub = np.argwhere(mask)
                lo, hi = sub.min(0), sub.max(0) + 1
                hu = grid["hu"][lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
                mk = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
                disc, nl = discretise_fbw(hu, mk)
                feats = {}
                feats.update(f_shape(mask, VOXEL_MM))
                feats.update(f_first_order(np.clip(grid["hu"][mask], *HU_CLIP)))
                feats.update(f_glcm(disc, nl))
                feats.update(f_glrlm(disc, nl))
                feats.update(f_glszm(disc, nl))
                feats.update(f_gldm(disc, nl))
                feats.update(f_ngtdm(disc, nl))
                rows.append({"patient_id": pid, "roi": canon, "roi_source_name": raw,
                             "n_levels": nl, **feats})
                qc.append({"patient_id": pid, "roi": canon, "status": "OK",
                           "reason": "", "n_voxels": n})
                got += 1
            except Exception as exc:
                qc.append({"patient_id": pid, "roi": canon, "status": "FAILED",
                           "reason": f"{type(exc).__name__}: {str(exc)[:150]}"})
        if got == 0:
            qc.append({"patient_id": pid, "roi": "", "status": "PATIENT_FAILED",
                       "reason": "every selected ROI failed or was too small"})
        for rec in [x for x in rows if str(x["patient_id"]) == pid]:
            fh_feat.write(json.dumps(rec) + "\n")
        for rec in [x for x in qc if str(x["patient_id"]) == pid]:
            fh_qc.write(json.dumps(rec) + "\n")
        fh_feat.flush()
        fh_qc.flush()
        done.add(pid)
        if i % 5 == 0:
            print(f"  {i}/{len(chain)} patients ({time.time() - t0:.0f}s), "
                  f"{len(rows)} ROI extractions", flush=True)

    fh_feat.close()
    fh_qc.close()
    for h in handles.values():
        h.close()

    long = pd.DataFrame(rows)
    long.to_csv(a.out / "radiomics_features_raw_long.csv", index=False)
    qcdf = pd.DataFrame(qc)
    qcdf.to_csv(a.out / "radiomics_qc_report.csv", index=False)

    if len(long):
        featcols = [c for c in long.columns
                    if c not in ("patient_id", "roi", "roi_source_name", "n_levels")]
        wide = long.pivot_table(index="patient_id", columns="roi", values=featcols)
        wide.columns = [f"ctrx_{roi}_{f}" for f, roi in wide.columns]
        wide = wide.reset_index()
        wide.to_csv(a.out / "radiomics_features_raw.csv", index=False)

        # QC: drop features that are constant or largely missing across patients
        keep = [c for c in wide.columns if c != "patient_id"]
        miss = wide[keep].isna().mean()
        const = wide[keep].nunique(dropna=True) <= 1
        drop = set(miss[miss > 0.20].index) | set(const[const].index)
        qcw = wide[["patient_id"] + [c for c in keep if c not in drop]]
        qcw.to_csv(a.out / "radiomics_features_qc.csv", index=False)

        fam = {"shape": "_shape_", "first_order": "_fo_", "GLCM": "_glcm_", "GLRLM": "_glrlm_",
               "GLSZM": "_glszm_", "GLDM": "_gldm_", "NGTDM": "_ngtdm_"}
        pd.DataFrame([{"feature": c, "roi": c.split("_")[1],
                       "family": next((k for k, t in fam.items() if t in c), "other"),
                       "retained_after_qc": c in qcw.columns}
                      for c in keep]).to_csv(a.out / "radiomics_feature_dictionary.csv", index=False)
    else:
        wide = pd.DataFrame()
        qcw = pd.DataFrame()

    man = {
        "eligible_multimodal": int(len(elig)),
        "attempted": int(len(chain)),
        "patients_with_any_feature": int(long.patient_id.nunique()) if len(long) else 0,
        "roi_extractions_ok": int((qcdf.status == "OK").sum()),
        "roi_skipped": int((qcdf.status == "SKIPPED").sum()),
        "roi_failed": int((qcdf.status == "FAILED").sum()),
        "patients_failed": int((qcdf.status == "PATIENT_FAILED").sum()),
        "features_before_qc": int(wide.shape[1] - 1) if len(wide) else 0,
        "features_after_qc": int(qcw.shape[1] - 1) if len(qcw) else 0,
        "voxel_mm": VOXEL_MM, "bin_width_HU": BIN_WIDTH_HU, "hu_clip": list(HU_CLIP),
        "min_voxels": MIN_VOXELS, "roi_set": list(ROI_PATTERNS),
        "engine": "rbGyanX in-house IBSI-aligned implementation (pyradiomics unavailable on "
                  "Python 3.14); NOT benchmarked against the IBSI digital phantom",
        "elapsed_s": round(time.time() - t0, 1),
    }
    (a.out / "radiomics_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(json.dumps(man, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
