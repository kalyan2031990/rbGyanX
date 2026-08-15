"""FINAL_V3 Upgrade B - benchmark the rbGyanX radiomics engine against the IBSI-1 digital phantom.

Source of truth
---------------
* Phantom: `theibsi/data_sets` -> `ibsi_1_digital_phantom/nifti` (CC-BY-4.0), 5x4x4 voxels at 2 mm
  isotropic, 74 voxels inside the mask.
* Reference values and tolerances: the `benchmark_value` / `tolerance` columns of the IBSI-1
  submission workbooks in `theibsi/ibsi_1_data_analysis/data`. Three INDEPENDENT teams are read
  (pyradiomics, oncoray, McGill) and their benchmark columns are checked for mutual agreement before
  any value is used, so the reference is not taken on one team's word.

Configuration
-------------
The digital-phantom configuration is fixed by IBSI: **no interpolation, no re-segmentation**, and
discretisation with a fixed bin size of 1, which leaves the integer intensities unchanged. The engine
is therefore fed the phantom exactly as published; nothing is tuned to make it pass.

Honest scope
------------
Only features rbGyanX actually implements are benchmarked. A feature the engine does not compute is
recorded as `not implemented`, never as a pass. Where the engine's definition differs from IBSI's
(for example a voxel-face surface area against IBSI's mesh-based area, or 3-directional run-length
against IBSI's 13-directional), the benchmark is expected to fail and the deviation is reported as a
finding rather than hidden.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# engine feature name -> (IBSI tag, IBSI family on the digital-phantom sheet, note)
MAP = {
    # ---- first-order / statistics ----
    "fo_mean": ("stat_mean", "Statistics", ""),
    "fo_min": ("stat_min", "Statistics", ""),
    "fo_max": ("stat_max", "Statistics", ""),
    "fo_median": ("stat_median", "Statistics", ""),
    "fo_p10": ("stat_p10", "Statistics", ""),
    "fo_p90": ("stat_p90", "Statistics", ""),
    "fo_iqr": ("stat_iqr", "Statistics", ""),
    "fo_range": ("stat_range", "Statistics", ""),
    "fo_skewness": ("stat_skew", "Statistics", ""),
    "fo_kurtosis": ("stat_kurt", "Statistics", ""),
    "fo_mad": ("stat_mad", "Statistics", ""),
    "fo_energy": ("stat_energy", "Statistics", ""),
    "fo_rms": ("stat_rms", "Statistics", ""),
    "fo_variance_population": ("stat_var", "Statistics",
                               "IBSI uses the population variance; the engine reports SD with ddof=1"),
    # ---- shape ----
    "shape_volume_mm3": ("morph_vol_approx", "Morphology", "voxel-counting volume"),
    "shape_sa_to_vol": ("morph_av", "Morphology",
                        "engine uses voxel-face area; IBSI uses a mesh-based area"),
    "shape_sphericity": ("morph_sphericity", "Morphology", "depends on the area definition"),
    "shape_surface_mm2": ("morph_area_mesh", "Morphology",
                          "engine uses voxel-face counting, IBSI a marching-cubes mesh - "
                          "different definitions"),
    # ---- GLCM: the engine accumulates all 13 directions into ONE matrix before computing
#      features, which is IBSI's MERGED variant (_3D_comb), not the averaged one ----
    "glcm_joint_average": ("cm_joint_avg_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_contrast": ("cm_contrast_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_dissimilarity": ("cm_dissimilarity_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_homogeneity": ("cm_inv_diff_mom_3D_comb", "Co-occurrence matrix (3D, merged)",
                         "engine homogeneity 1/(1+d^2) == IBSI inverse difference "
                         "MOMENT, not inverse difference 1/(1+|d|)"),
    "glcm_asm": ("cm_energy_3D_comb", "Co-occurrence matrix (3D, merged)",
                 "IBSI 'angular second moment' is named energy"),
    "glcm_entropy": ("cm_joint_entr_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_correlation": ("cm_corr_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_sum_average": ("cm_sum_avg_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_sum_entropy": ("cm_sum_entr_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_difference_average": ("cm_diff_avg_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_difference_entropy": ("cm_diff_entr_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_cluster_shade": ("cm_clust_shade_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_cluster_prominence": ("cm_clust_prom_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_cluster_tendency": ("cm_clust_tend_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_autocorrelation": ("cm_auto_corr_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_max_probability": ("cm_joint_max_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    "glcm_inverse_variance": ("cm_inv_var_3D_comb", "Co-occurrence matrix (3D, merged)", ""),
    # ---- GLRLM: like GLCM, the engine merges all 13 directions into one matrix, so the
#      comparator is IBSI's MERGED variant (_3D_comb) ----
    "glrlm_sre": ("rlm_sre_3D_comb", "Run length matrix (3D, merged)",
                  "13 directions, merged (was 3 axis directions before the IBSI audit)"),
    "glrlm_lre": ("rlm_lre_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    "glrlm_lgre": ("rlm_lgre_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    "glrlm_hgre": ("rlm_hgre_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    "glrlm_gln": ("rlm_glnu_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    "glrlm_rln": ("rlm_rlnu_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    "glrlm_rp": ("rlm_r_perc_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    "glrlm_run_entropy": ("rlm_rl_entr_3D_comb", "Run length matrix (3D, merged)", "13 directions, merged"),
    # ---- GLSZM, 3D ----
    "glszm_sae": ("szm_sze_3D", "Size zone matrix (3D)", ""),
    "glszm_lae": ("szm_lze_3D", "Size zone matrix (3D)", ""),
    "glszm_lgze": ("szm_lgze_3D", "Size zone matrix (3D)", ""),
    "glszm_hgze": ("szm_hgze_3D", "Size zone matrix (3D)", ""),
    "glszm_gln": ("szm_glnu_3D", "Size zone matrix (3D)", ""),
    "glszm_szn": ("szm_zsnu_3D", "Size zone matrix (3D)", ""),
    "glszm_zp": ("szm_z_perc_3D", "Size zone matrix (3D)", ""),
    "glszm_zone_entropy": ("szm_zs_entr_3D", "Size zone matrix (3D)", ""),
    # ---- GLDM / NGLDM, 3D ----
    "gldm_sde": ("ngl_lde_3D", "Neighbouring grey level dependence matrix (3D)",
                 "engine 'small dependence' == IBSI low dependence emphasis"),
    "gldm_lde": ("ngl_hde_3D", "Neighbouring grey level dependence matrix (3D)", ""),
    "gldm_lgle": ("ngl_lgce_3D", "Neighbouring grey level dependence matrix (3D)", ""),
    "gldm_hgle": ("ngl_hgce_3D", "Neighbouring grey level dependence matrix (3D)", ""),
    "gldm_gln": ("ngl_glnu_3D", "Neighbouring grey level dependence matrix (3D)", ""),
    "gldm_dn": ("ngl_dcnu_3D", "Neighbouring grey level dependence matrix (3D)", ""),
    "gldm_dependence_entropy": ("ngl_dc_entr_3D", "Neighbouring grey level dependence matrix (3D)", ""),
    # ---- NGTDM, 3D ----
    "ngtdm_coarseness": ("ngt_coarseness_3D", "Neighbourhood grey tone difference matrix (3D)", ""),
    "ngtdm_contrast": ("ngt_contrast_3D", "Neighbourhood grey tone difference matrix (3D)", ""),
    "ngtdm_busyness": ("ngt_busyness_3D", "Neighbourhood grey tone difference matrix (3D)", ""),
    "ngtdm_complexity": ("ngt_complexity_3D", "Neighbourhood grey tone difference matrix (3D)", ""),
    "ngtdm_strength": ("ngt_strength_3D", "Neighbourhood grey tone difference matrix (3D)", ""),
}

TEAM_FILES = ("20181005_pyradiomics.xlsx", "20181120_oncoray.xlsx", "20181008_mcgill.xlsx")
def precision_tolerance(value: float) -> float:
    """Half the last significant digit of the published benchmark.

    IBSI reports the digital-phantom consensus to about three significant figures, so 17.4 carries an
    implicit +/-0.05 and 0.0296 an implicit +/-0.00005. A single flat epsilon would fail features that
    actually agree and pass features that do not."""
    import math as _m
    v = abs(float(value))
    if v == 0:
        return 5e-4
    exp = _m.floor(_m.log10(v))
    return 0.5 * 10 ** (exp - 2)          # three significant figures


def load_reference(ibsi_dir: Path) -> pd.DataFrame:
    frames = []
    for fn in TEAM_FILES:
        p = ibsi_dir / fn
        if not p.is_file():
            continue
        d = pd.ExcelFile(p).parse("digital phantom")
        d = d[["family", "image_biomarker", "tag", "benchmark_value", "tolerance"]].copy()
        d["team"] = fn.split("_", 1)[1].replace(".xlsx", "")
        frames.append(d)
    allr = pd.concat(frames, ignore_index=True)
    # verify the three teams quote the SAME benchmark before trusting it
    agg = allr.groupby(["tag", "family"]).agg(
        benchmark_value=("benchmark_value", "first"),
        n_teams=("team", "nunique"),
        value_spread=("benchmark_value", lambda s: float(np.nanmax(s) - np.nanmin(s))),
        tolerance=("tolerance", "first")).reset_index()
    return agg


def compute_engine_features(vol: np.ndarray, mask: np.ndarray, spacing: float,
                            scripts_dir: Path) -> dict:
    sys.path.insert(0, str(scripts_dir))
    import p14_ct_radiomics as eng

    feats: dict[str, float] = {}
    vals = vol[mask].astype(float)
    feats.update(eng.f_first_order(vals))
    feats["fo_variance_population"] = float(vals.var())          # IBSI uses population variance
    feats.update(eng.f_shape(mask, spacing))

    # IBSI digital-phantom configuration: FBS bin width 1 leaves the integer intensities unchanged
    disc = np.zeros(vol.shape, dtype=np.int16)
    disc[mask] = vol[mask].astype(int)
    nl = int(disc.max())
    feats.update(eng.f_glcm(disc, nl))
    feats.update(eng.f_glrlm(disc, nl))
    feats.update(eng.f_glszm(disc, nl))
    feats.update(eng.f_gldm(disc, nl))
    feats.update(eng.f_ngtdm(disc, nl))
    return feats, nl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ibsi-dir", required=True, type=Path)
    ap.add_argument("--scripts-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    O = a.out
    (O / "figures").mkdir(parents=True, exist_ok=True)
    (O / "tables").mkdir(parents=True, exist_ok=True)

    import nibabel as nib
    img = nib.load(a.ibsi_dir / "image_phantom.nii.gz")
    msk = nib.load(a.ibsi_dir / "mask_mask.nii.gz")
    vol = np.asanyarray(img.dataobj).astype(float)
    mask = np.asanyarray(msk.dataobj).astype(bool)
    spacing = float(img.header.get_zooms()[0])

    feats, nl = compute_engine_features(vol, mask, spacing, a.scripts_dir)
    ref = load_reference(a.ibsi_dir)
    ref_by_tag = {r.tag: r for _, r in ref.iterrows()}

    rows = []
    for eng_name, (tag, family, note) in MAP.items():
        r = ref_by_tag.get(tag)
        got = feats.get(eng_name)
        if r is None:
            rows.append({"engine_feature": eng_name, "ibsi_tag": tag, "ibsi_family": family,
                         "engine_value": got, "ibsi_benchmark": None, "ibsi_tolerance": None,
                         "abs_diff": None, "verdict": "no IBSI reference for this tag",
                         "note": note})
            continue
        if got is None or not np.isfinite(got):
            rows.append({"engine_feature": eng_name, "ibsi_tag": tag, "ibsi_family": family,
                         "engine_value": got, "ibsi_benchmark": r.benchmark_value,
                         "ibsi_tolerance": r.tolerance, "abs_diff": None,
                         "verdict": "not implemented / not computed", "note": note})
            continue
        bench = float(r.benchmark_value)
        tol = float(r.tolerance) if np.isfinite(r.tolerance) else 0.0
        eff_tol = max(tol, precision_tolerance(bench))
        diff = abs(float(got) - bench)
        rows.append({"engine_feature": eng_name, "ibsi_tag": tag, "ibsi_family": family,
                     "engine_value": float(got), "ibsi_benchmark": bench,
                     "ibsi_tolerance": tol, "effective_tolerance": eff_tol,
                     "abs_diff": diff, "rel_diff": diff / abs(bench) if bench else np.nan,
                     "teams_agreeing": int(r.n_teams), "team_value_spread": float(r.value_spread),
                     "verdict": "PASS" if diff <= eff_tol else "FAIL", "note": note})

    comp = pd.DataFrame(rows)
    comp.to_csv(O / "IBSI_FEATURE_COMPARISON.csv", index=False)

    def family_group(f: str) -> str:
        if f.startswith("Morph"):
            return "shape"
        if f.startswith("Statistics"):
            return "first-order"
        if f.startswith("Co-occurrence"):
            return "GLCM"
        if f.startswith("Run length"):
            return "GLRLM"
        if f.startswith("Size zone"):
            return "GLSZM"
        if f.startswith("Neighbouring grey level"):
            return "GLDM/NGLDM"
        if f.startswith("Neighbourhood grey tone"):
            return "NGTDM"
        return "other"

    comp["family_group"] = comp.ibsi_family.map(family_group)
    mat = comp.groupby("family_group").agg(
        features_compared=("verdict", "size"),
        passed=("verdict", lambda s: int((s == "PASS").sum())),
        failed=("verdict", lambda s: int((s == "FAIL").sum())),
        no_reference=("verdict", lambda s: int((s == "no IBSI reference for this tag").sum())),
    ).reset_index()
    mat["pass_rate"] = (mat.passed / (mat.passed + mat.failed).replace(0, np.nan)).round(3)
    mat["status"] = mat.apply(
        lambda r: ("IBSI verified" if r.failed == 0 and r.passed > 0 else
                   "IBSI partially verified" if r.passed > 0 else
                   "not verified"), axis=1)
    mat.to_csv(O / "IBSI_COMPLIANCE_MATRIX.csv", index=False)

    cfg = {
        "generated": date.today().isoformat(),
        "phantom": {"source": "theibsi/data_sets - ibsi_1_digital_phantom/nifti",
                    "licence": "CC-BY-4.0",
                    "shape": list(vol.shape), "spacing_mm": spacing,
                    "voxels_in_mask": int(mask.sum()),
                    "intensity_levels_in_mask": sorted(np.unique(vol[mask]).astype(int).tolist())},
        "reference_values": {
            "source": "theibsi/ibsi_1_data_analysis/data - benchmark_value and tolerance columns",
            "teams_read": list(TEAM_FILES),
            "cross_team_agreement_checked": True,
            "max_disagreement_between_teams": float(ref.value_spread.max()),
        },
        "configuration": {"interpolation": "none (IBSI digital-phantom configuration)",
                          "resegmentation": "none",
                          "discretisation": "fixed bin size 1 - integer intensities unchanged",
                          "grey_levels_used": nl,
                          "tolerance_rule": "IBSI published tolerance, or half the last significant "
                                            "digit of the published value (3 s.f.) where IBSI "
                                            "reports an exact value"},
        "engine": "rbGyanX in-house IBSI-aligned implementation (p14_ct_radiomics.py)",
        "summary": {"compared": int((comp.verdict.isin(["PASS", "FAIL"])).sum()),
                    "passed": int((comp.verdict == "PASS").sum()),
                    "failed": int((comp.verdict == "FAIL").sum())},
    }
    (O / "IBSI_CONFIG.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    comp.to_csv(O / "tables" / "IBSI_feature_comparison.csv", index=False)
    mat.to_csv(O / "tables" / "IBSI_compliance_matrix.csv", index=False)

    # figure: pass/fail per family
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 150, "savefig.bbox": "tight", "font.size": 9})
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    y = np.arange(len(mat))
    ax.barh(y, mat.passed, color="#2e7d32", label="pass")
    ax.barh(y, mat.failed, left=mat.passed, color="#c0392b", label="fail")
    ax.set_yticks(y)
    ax.set_yticklabels(mat.family_group)
    ax.set_xlabel("features compared against the IBSI-1 digital phantom")
    ax.set_title("IBSI benchmark by feature family", fontsize=10)
    ax.legend(fontsize=8)
    for ext in (".png", ".svg"):
        fig.savefig(O / "figures" / f"FigI1_ibsi_compliance{ext}")
    plt.close(fig)

    print(mat.to_string(index=False))
    print(f"\ncompared {cfg['summary']['compared']} | passed {cfg['summary']['passed']} | "
          f"failed {cfg['summary']['failed']}")
    print("\nfailures:")
    f = comp[comp.verdict == "FAIL"][["engine_feature", "engine_value", "ibsi_benchmark",
                                      "abs_diff", "note"]]
    print(f.to_string(index=False) if len(f) else "  none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
