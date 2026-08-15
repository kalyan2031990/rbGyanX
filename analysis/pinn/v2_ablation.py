"""Ablation for the TCIA_HN texture result — is the gain really texture?

SHAP on the v2 model puts the stable signal in **Lungs** and **BrachialPlexus** GLSZM/GLRLM features.
For a head-and-neck loco-regional-control endpoint that is not a plausible mechanism, so the increment
has to be tested against the two cheap explanations before it may be reported as a texture effect:

  A. it is an irradiated-**volume** surrogate (GLSZM zone counts scale with mask size), or
  B. it is nothing that plain **first-order** statistics of the same organs would not already give.

Same protocol as everywhere else: 5-fold x 5-repeat stratified CV, train-fold-only standardisation,
bootstrap CI. Arms are pre-specified; nothing here is selected on the result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from v2_pinn import CLIN_COLS, DOSE_COLS, auc, auc_ci, dosio_alias_map, standardise

TARGET_ORGANS = ("Lungs", "BrachialPlexus")


def cv_auc(frame: pd.DataFrame, cols: list[str], y: np.ndarray, seed: int = 0,
           folds: int = 5, repeats: int = 5) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold
    acc, cnt = np.zeros(len(frame)), np.zeros(len(frame))
    for rep in range(repeats):
        for tr, te in StratifiedKFold(folds, shuffle=True,
                                      random_state=seed + 100 * rep).split(frame, y):
            A, B = standardise(frame.iloc[tr].reset_index(drop=True),
                               frame.iloc[te].reset_index(drop=True), cols)
            rf = RandomForestClassifier(n_estimators=400, min_samples_leaf=5,
                                        class_weight="balanced_subsample",
                                        random_state=seed, n_jobs=-1).fit(A, y[tr])
            acc[te] += rf.predict_proba(B)[:, 1]
            cnt[te] += 1
    p = acc / np.maximum(cnt, 1)
    lo, hi = auc_ci(y, p, seed)
    return {"n_features": len(cols), "cv_AUC": auc(y, p), "auc_lo95": lo, "auc_hi95": hi,
            "cv_Brier": float(np.mean((p - y) ** 2))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pinn-frame", required=True, type=Path)
    ap.add_argument("--texture", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    fr = pd.read_csv(a.pinn_frame, low_memory=False)
    tex = pd.read_csv(a.texture, low_memory=False)
    alias = dosio_alias_map(tex)
    y = fr["tcp_outcome"].astype(int).values

    stable_real = [alias[c] for c in ("dosio_81", "dosio_83", "dosio_86", "dosio_80",
                                      "dosio_249", "dosio_253") if c in alias]
    vol_cols = [c for c in tex.columns
                if any(c.startswith(f"rdx_{o}_fo_") for o in TARGET_ORGANS)
                and "n_voxels" in c]
    fo_cols = [c for c in tex.columns
               if any(c.startswith(f"rdx_{o}_fo_") for o in TARGET_ORGANS)
               and any(k in c for k in ("n_voxels", "mean", "std", "p90", "max"))]

    extra = sorted(set(stable_real + fo_cols))
    m = fr.merge(tex[["pseudonym", *extra]], on="pseudonym", how="left")

    dose = [c for c in DOSE_COLS if c in m.columns]
    clin = [c for c in CLIN_COLS if c in m.columns]
    arms = {
        "1. dose only": dose,
        "2. dose + clinical": dose + clin,
        "3. dose + clinical + IRRADIATED VOLUME of Lungs/Plexus": dose + clin + vol_cols,
        "4. dose + clinical + FIRST-ORDER of Lungs/Plexus": dose + clin + fo_cols,
        "5. dose + clinical + STABLE TEXTURE of Lungs/Plexus": dose + clin + stable_real,
        "6. dose + clinical + first-order + texture": dose + clin + sorted(set(fo_cols + stable_real)),
    }
    # Arms 3-6 fix a feature set that was chosen POST HOC from the whole-cohort SHAP / fold-frequency
    # analysis. Their absolute AUCs are therefore optimistic and must never be quoted as performance.
    # Only the CONTRASTS between them are interpretable, because all four share the same post-hoc organ
    # choice. The unbiased performance number for this cohort is the fully nested 0.699 from
    # v2_pinn_comparators.py.
    bias = {
        "1. dose only": "unbiased",
        "2. dose + clinical": "unbiased",
        "3. dose + clinical + IRRADIATED VOLUME of Lungs/Plexus": "POST-HOC organ choice - contrast only",
        "4. dose + clinical + FIRST-ORDER of Lungs/Plexus": "POST-HOC organ choice - contrast only",
        "5. dose + clinical + STABLE TEXTURE of Lungs/Plexus": "POST-HOC feature choice - NOT a performance estimate",
        "6. dose + clinical + first-order + texture": "POST-HOC feature choice - NOT a performance estimate",
    }
    rows = []
    for name, cols in arms.items():
        cols = [c for c in cols if c in m.columns]
        r = cv_auc(m, cols, y, a.seed)
        rows.append({"arm": name, **r, "bias_status": bias[name]})
        print(f"  {name:56s} k={r['n_features']:3d}  AUC={r['cv_AUC']:.3f} "
              f"[{r['auc_lo95']:.3f}-{r['auc_hi95']:.3f}]")
    res = pd.DataFrame(rows)
    res.to_csv(a.out / "V2_TEXTURE_ABLATION.csv", index=False)
    (a.out / "V2_TEXTURE_ABLATION.json").write_text(
        json.dumps({"unbiased_reference_AUC": 0.699,
                    "unbiased_reference_source": "v2_pinn_comparators.py, fully nested selection",
                    "arms": rows, "stable_texture_features": stable_real,
                    "volume_columns": vol_cols, "first_order_columns": fo_cols,
                    "n": int(len(m)), "events_controlled": int(y.sum())},
                   indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
