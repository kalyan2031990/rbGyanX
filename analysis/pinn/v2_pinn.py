"""
PINN v2 — physics-informed TCP network, evaluated properly.

Three trainer defects were repaired first (see CHANGELOG); they explain the v1 failure:
  * training hard-coded 30 fractions for every patient,
  * **validation hard-coded 50 Gy / 25 fractions for every patient**, so the validation TCP ignored the
    actual plan and val_loss (and the LR schedule driven by it) were meaningless,
  * the LAST epoch was saved rather than the best, with no early stopping.

v2 additionally supplies the information the model was never given:
  * per-patient total dose and fraction count (the physics inputs),
  * clinical covariates available for TCIA_HN (age, sex, T/N/M stage, HPV status),
  * REAL 3-D texture dosiomics (GLCM/GLRLM/GLSZM) instead of the synthetic surrogates.

Evaluation is k-fold cross-validated AUC on held-out patients, so the number is comparable with the
published deep/PINN outcome-model literature. In-sample numbers are never reported as performance.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


class BoundedRadiobiologyPINN:
    """v2 PINN head with PHYSIOLOGICALLY BOUNDED radiobiological parameters.

    The shipped model emits alpha/beta/N0 through an unbounded Softplus. alpha then drifts until
    N0*SF ~ 0, TCP saturates at 1.0 for every patient and the gradient vanishes - so with 83.5%
    positives the network simply parks on the majority class (observed: all 121 predictions = 0.999999,
    AUC exactly 0.500). Constraining the parameters to their physiological ranges keeps the model in the
    region where TCP actually responds to dose. The physics (LQ + Poisson clonogen kill) is unchanged.

        alpha in [0.05, 0.50] Gy^-1     (clinical HNSCC radiosensitivity)
        alpha/beta in [5, 20] Gy        (beta derived, so the LQ ratio stays physiological)
        N0 in [1e5, 1e9]  (log-uniform) (clonogen number)
    """

    def __new__(cls, n_features: int, n_hidden: int = 64):
        import torch
        import torch.nn as nn

        class _Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.body = nn.Sequential(
                    nn.Linear(n_features, n_hidden), nn.Tanh(),
                    nn.Linear(n_hidden, n_hidden), nn.Tanh(),
                    nn.Linear(n_hidden, 3),
                )

            def forward(self, x):
                z = torch.sigmoid(self.body(x))
                alpha = 0.05 + 0.45 * z[:, 0]
                ab = 5.0 + 15.0 * z[:, 1]
                beta = alpha / ab
                n0 = torch.pow(10.0, 5.0 + 4.0 * z[:, 2])
                return alpha, beta, n0

            @staticmethod
            def tcp_from_params(alpha, beta, n0, total_dose, n_fractions):
                dpf = total_dose / n_fractions.clamp(min=1)
                # work in log space: log(N_eff) = log(N0) - n*(alpha*d + beta*d^2)
                log_neff = torch.log(n0) - n_fractions * (alpha * dpf + beta * dpf ** 2)
                return torch.exp(-torch.exp(log_neff.clamp(-30, 30)))

        return _Net()


class HybridResidualPINN:
    """v2c PINN: mechanistic LQ-Poisson head + data-driven residual on the SAME logit scale.

    The bounded head fixes saturation but the pure-physics output is a monotone function of dose alone,
    so it cannot express the clinical/texture signal - it discriminates at chance. The hybrid form used
    in the published physics-informed outcome literature keeps the mechanistic term and adds a learned
    residual:

        logit(p) = w * logit(TCP_LQ-Poisson(alpha, beta, N0 | d, n))  +  f_residual(x)

    w is learnable and initialised at 1, so the model starts exactly at the physics prediction and only
    departs from it where the data demand it. alpha/beta stay physiologically bounded and are held near
    the HNSCC prior by the same physics regulariser, so the mechanistic parameters remain interpretable.
    """

    def __new__(cls, n_features: int, n_hidden: int = 32, p_drop: float = 0.3):
        import torch
        import torch.nn as nn

        class _Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.phys = nn.Sequential(nn.Linear(n_features, n_hidden), nn.Tanh(),
                                          nn.Linear(n_hidden, 3))
                self.res = nn.Sequential(nn.Linear(n_features, n_hidden), nn.Tanh(),
                                         nn.Dropout(p_drop), nn.Linear(n_hidden, 1))
                self.w = nn.Parameter(torch.tensor(1.0))

            def physics(self, x, dose, nfx):
                z = torch.sigmoid(self.phys(x))
                alpha = 0.05 + 0.45 * z[:, 0]
                ab = 5.0 + 15.0 * z[:, 1]
                beta = alpha / ab
                n0 = torch.pow(10.0, 5.0 + 4.0 * z[:, 2])
                dpf = dose / nfx.clamp(min=1)
                log_neff = torch.log(n0) - nfx * (alpha * dpf + beta * dpf ** 2)
                p_phys = torch.exp(-torch.exp(log_neff.clamp(-30, 30))).clamp(1e-4, 1 - 1e-4)
                return p_phys, alpha, beta

            def forward(self, x, dose, nfx):
                p_phys, alpha, beta = self.physics(x, dose, nfx)
                logit_phys = torch.log(p_phys / (1 - p_phys))
                r = self.res(x).reshape(-1)
                return torch.sigmoid(self.w * logit_phys + r), alpha, beta, p_phys

        return _Net()


# feature families in the v2 frame -------------------------------------------------------------
DOSE_COLS = ["EQD2_gy", "BED_gy", "Dmean_gy", "D95_gy", "TCP_Poisson", "TCP_gEUD"]
CLIN_COLS = ["clin_age", "clin_sex_M", "clin_stage", "clin_hpv_pos"]


def feature_cols(df: pd.DataFrame, use_texture: bool) -> list[str]:
    cols = [c for c in DOSE_COLS if c in df.columns] + [c for c in CLIN_COLS if c in df.columns]
    if use_texture:
        cols += [c for c in df.columns if c.startswith("dosio_")]
    return cols


def select_texture_in_fold(tr_df: pd.DataFrame, ytr: np.ndarray, cols: list[str],
                           k: int = 8) -> list[str]:
    """NESTED selection: rank texture features by |Spearman| on the TRAINING fold only.

    The v2 ML run selected texture on the whole cohort, which inflates the AUC. Doing it inside the
    fold removes that path entirely, so the PINN number below is selection-bias free.
    """
    from scipy.stats import spearmanr
    tex = [c for c in cols if c.startswith("dosio_")]
    base = [c for c in cols if not c.startswith("dosio_")]
    if not tex:
        return base
    scored = []
    for c in tex:
        v = pd.to_numeric(tr_df[c], errors="coerce").values.astype(float)
        if not np.isfinite(v).any() or np.nanstd(v) < 1e-12:
            continue
        v = np.where(np.isfinite(v), v, np.nanmedian(v))
        r = spearmanr(v, ytr).statistic
        scored.append((abs(r) if np.isfinite(r) else 0.0, c))
    scored.sort(reverse=True)
    return base + [c for _, c in scored[:k]]


def standardise(tr_df: pd.DataFrame, te_df: pd.DataFrame, cols: list[str]):
    """Impute + z-score using TRAINING-fold statistics only (no test information leaks)."""
    A = tr_df[cols].apply(pd.to_numeric, errors="coerce").values.astype(float)
    med = np.nanmedian(A, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    A = np.where(np.isfinite(A), A, med)
    mu, sd = A.mean(axis=0), A.std(axis=0)
    sd[sd < 1e-8] = 1.0
    B = te_df[cols].apply(pd.to_numeric, errors="coerce").values.astype(float)
    B = np.where(np.isfinite(B), B, med)
    return ((A - mu) / sd).astype(np.float32), ((B - mu) / sd).astype(np.float32)


def auc(y, p) -> float:
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if pos.size == 0 or neg.size == 0:
        return math.nan
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def auc_ci(y, p, seed: int, n_boot: int = 2000) -> list:
    """Percentile bootstrap 95% CI for the cross-validated AUC (patient resampling)."""
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            continue
        vals.append(auc(y[i], p[i]))
    if not vals:
        return [math.nan, math.nan]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def build_frame(master: pd.DataFrame, final: Path, texture: pd.DataFrame | None,
                clinical: Path, map_csv: Path) -> pd.DataFrame:
    """One row per labelled TCIA_HN patient: physics inputs + dose + clinical + texture."""
    hv_root = final / "TCIA_HN_External_n186" / "advanced" / "ExternalValidation" / "TCIA_HN" / "PatientLevel"
    harvest = {f.parent.name: json.loads(f.read_text(encoding="utf-8"))
               for f in hv_root.glob("*/harvest.json")}
    raw_by_pse = {r["pseudonym"]: r["raw_patient_key"] for r in pd.read_csv(map_csv).to_dict("records")}
    clin = {r["patient_id"]: r for r in pd.read_csv(clinical).to_dict("records")}

    g = master[(master.cohort == "TCIA_HN") & (master.outcome_available == 1)]
    rows = []
    for _, r in g.iterrows():
        pse = r["pseudonym"]
        y = pd.to_numeric(pd.Series([r.get("outcome_locoregional")]), errors="coerce").iloc[0]
        if not np.isfinite(y):
            continue
        tcp = harvest.get(pse, {}).get("tcp", [])
        if not tcp:
            continue
        t = max(tcp, key=lambda x: float(x.get("total_volume_cc") or 0))
        c = clin.get(raw_by_pse.get(pse, ""), {})

        def cf(v):
            try:
                return float(v)
            except Exception:
                return np.nan

        def stage_num(s):
            s = str(s or "").upper().replace("STAGE", "").strip()
            for k, v in (("IV", 4), ("III", 3), ("II", 2), ("I", 1)):
                if s.startswith(k):
                    return v
            return np.nan

        rec = {
            "pseudonym": pse,
            # --- physics inputs the trainer needs per patient -------------------------------
            "total_dose_gy": cf(t.get("total_dose_gy")) or cf(t.get("EQD2_gy")),
            "n_fractions": cf(t.get("n_fractions")) or 35.0,
            # --- dose / radiobiology features ----------------------------------------------
            "EQD2_gy": cf(t.get("EQD2_gy")), "BED_gy": cf(t.get("BED_gy")),
            "Dmean_gy": cf(t.get("Dmean_gy")), "D95_gy": cf(t.get("D50_gy")),
            "TCP_Poisson": cf(t.get("TCP_Poisson")), "TCP_gEUD": cf(t.get("TCP_gEUD")),
            # --- clinical covariates (TCIA_HN has these; v1 never used them) ----------------
            "clin_age": cf(c.get("age")),
            "clin_sex_M": 1.0 if str(c.get("sex", "")).upper().startswith("M") else 0.0,
            "clin_stage": stage_num(c.get("stage_group")),
            "clin_hpv_pos": (1.0 if str(c.get("hpv_status", "")).lower().startswith(("pos", "+", "1"))
                             else 0.0),
            "tcp_outcome": 1.0 - float(y),      # LOCAL CONTROL (1 = controlled)
        }
        rows.append(rec)
    df = pd.DataFrame(rows)
    if texture is not None and len(df):
        t = texture.copy()
        keep = [c for c in t.columns if c != "pseudonym" and t[c].notna().sum() >= 0.8 * len(t)]
        # full GLCM/GLRLM/GLSZM candidate pool - the top-k are chosen INSIDE each training fold
        pick = [c for c in keep if any(k in c for k in ("glcm_", "glrlm_", "glszm_"))]
        df = df.merge(t[["pseudonym", *pick]], on="pseudonym", how="left")
        df = df.rename(columns={c: f"dosio_{i}" for i, c in enumerate(pick)})
        # keep the alias -> real texture-feature name map so SHAP and tables can be read by a human
        df.attrs["dosio_alias_map"] = {f"dosio_{i}": c for i, c in enumerate(pick)}
    return df


def dosio_alias_map(texture: pd.DataFrame) -> dict:
    """Rebuild the dosio_<i> -> real feature-name map used by build_frame (same ordering)."""
    keep = [c for c in texture.columns if c != "pseudonym"
            and texture[c].notna().sum() >= 0.8 * len(texture)]
    pick = [c for c in keep if any(k in c for k in ("glcm_", "glrlm_", "glszm_"))]
    return {f"dosio_{i}": c for i, c in enumerate(pick)}


def _train_bounded(Xtr, ytr, dtr, ftr, epochs, seed, lam_phys=0.1):
    """Train the bounded-parameter PINN with class-weighted BCE and early stopping."""
    import torch
    import torch.nn as nn
    torch.manual_seed(seed)
    net = BoundedRadiobiologyPINN(Xtr.shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=3e-3, weight_decay=1e-4)
    pos_w = float((ytr == 0).sum()) / max(float((ytr == 1).sum()), 1.0)
    w = torch.where(ytr > 0.5, torch.tensor(pos_w), torch.tensor(1.0))
    best, best_state, bad = float("inf"), None, 0
    for _ in range(epochs):
        net.train()
        opt.zero_grad()
        a, b, n0 = net(Xtr)
        p = net.tcp_from_params(a, b, n0, dtr, ftr).clamp(1e-6, 1 - 1e-6)
        loss = nn.functional.binary_cross_entropy(p, ytr, weight=w)
        # physics regulariser: keep the LQ ratio near the HNSCC prior (alpha/beta ~ 10 Gy)
        loss = loss + lam_phys * ((a / b - 10.0) ** 2).mean() / 100.0
        loss.backward()
        opt.step()
        v = float(loss.item())
        if v < best - 1e-5:
            best, bad = v, 0
            best_state = {k: t.detach().clone() for k, t in net.state_dict().items()}
        else:
            bad += 1
            if bad >= 60:
                break
    if best_state:
        net.load_state_dict(best_state)
    return net


def _train_hybrid(Xtr, ytr, dtr, ftr, epochs, seed, lam_phys=0.05, patience=40):
    """Hybrid physics+residual PINN, early-stopped on an inner split of the training fold."""
    import torch
    import torch.nn as nn
    from sklearn.model_selection import train_test_split

    g = torch.Generator().manual_seed(seed)
    torch.manual_seed(seed)
    idx = np.arange(len(ytr))
    ytr_np = ytr.numpy()
    itr, iva = train_test_split(idx, test_size=0.2, random_state=seed, stratify=ytr_np)
    net = HybridResidualPINN(Xtr.shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=2e-3, weight_decay=3e-3)
    pos_w = float((ytr_np == 0).sum()) / max(float((ytr_np == 1).sum()), 1.0)

    def loss_of(sel, train_mode):
        net.train(train_mode)
        p, a, b, _ = net(Xtr[sel], dtr[sel], ftr[sel])
        p = p.clamp(1e-6, 1 - 1e-6)
        w = torch.where(ytr[sel] > 0.5, torch.tensor(pos_w), torch.tensor(1.0))
        loss = nn.functional.binary_cross_entropy(p, ytr[sel], weight=w)
        return loss + lam_phys * ((a / b - 10.0) ** 2).mean() / 100.0

    best, best_state, bad = float("inf"), None, 0
    bs = 32
    for _ in range(epochs):
        perm = torch.randperm(len(itr), generator=g).numpy()
        for s in range(0, len(itr), bs):
            sel = itr[perm[s:s + bs]]
            if len(sel) < 4:
                continue
            opt.zero_grad()
            loss_of(sel, True).backward()
            opt.step()
        with torch.no_grad():
            v = float(loss_of(iva, False).item())
        if v < best - 1e-4:
            best, bad = v, 0
            best_state = {k: t.detach().clone() for k, t in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state:
        net.load_state_dict(best_state)
    net.eval()
    # Platt calibration fitted on the INNER validation split only (never on the outer test fold).
    with torch.no_grad():
        pv, _, _, _ = net(Xtr[iva], dtr[iva], ftr[iva])
    lv = np.log(np.clip(pv.numpy(), 1e-6, 1 - 1e-6) / (1 - np.clip(pv.numpy(), 1e-6, 1 - 1e-6)))
    cal = None
    if len(np.unique(ytr_np[iva])) == 2:
        from sklearn.linear_model import LogisticRegression
        lr = LogisticRegression(max_iter=1000)
        lr.fit(lv.reshape(-1, 1), ytr_np[iva].astype(int))
        cal = (float(lr.coef_[0][0]), float(lr.intercept_[0]))
    return net, best, cal


def run_cv(df: pd.DataFrame, repo: Path, out: Path, epochs: int, seed: int, folds: int = 5,
           bounded: bool = False, hybrid: bool = False, use_texture: bool = False,
           repeats: int = 1, n_seeds: int = 1) -> dict:
    from sklearn.model_selection import StratifiedKFold
    import torch
    from rbgyanx_advanced_f.pinn.train_pinn import FEATURE_COLUMNS, _prepare_tensors, train_pinn_from_df

    out.mkdir(parents=True, exist_ok=True)

    y = df["tcp_outcome"].astype(int).values
    acc = np.zeros(len(df))
    acc_n = np.zeros(len(df))
    acc_phys = np.zeros(len(df))
    oof_phys = np.full(len(df), np.nan)
    fold_hist = []
    all_cols = feature_cols(df, use_texture)
    n_feat_used = []
    splits = []
    for rep in range(repeats):
        skf_r = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed + 100 * rep)
        splits += list(skf_r.split(df, y))
    for k, (tr, te) in enumerate(splits, 1):
        oof = np.full(len(df), np.nan)
        tr_df = df.iloc[tr].drop(columns=["pseudonym"]).reset_index(drop=True)
        te_df = df.iloc[te].drop(columns=["pseudonym"]).reset_index(drop=True)
        if bounded or hybrid:
            cols = select_texture_in_fold(tr_df, y[tr], all_cols) if use_texture else all_cols
            n_feat_used.append(len(cols))
            Atr, Ate = standardise(tr_df, te_df, cols)
            Xtr = torch.tensor(Atr, dtype=torch.float32)
            Xte = torch.tensor(Ate, dtype=torch.float32)
            ytr = torch.tensor(y[tr].astype(np.float32))
            dtr = torch.tensor(tr_df["total_dose_gy"].astype(float).values, dtype=torch.float32).clamp(min=.1)
            ftr = torch.tensor(tr_df["n_fractions"].astype(float).values, dtype=torch.float32).clamp(min=1.)
            dte = torch.tensor(te_df["total_dose_gy"].astype(float).values, dtype=torch.float32).clamp(min=.1)
            fte = torch.tensor(te_df["n_fractions"].astype(float).values, dtype=torch.float32).clamp(min=1.)
            if hybrid:
                # ensemble over n_seeds independent initialisations (variance control at small n)
                ps, vbests = [], []
                for s in range(n_seeds):
                    net, vbest, cal = _train_hybrid(Xtr, ytr, dtr, ftr, epochs, seed + 7 * s)
                    with torch.no_grad():
                        p, _, _, p_phys = net(Xte, dte, fte)
                    pv = np.clip(p.numpy(), 1e-6, 1 - 1e-6)
                    if cal is not None:                      # Platt, fitted on inner val only
                        a_c, b_c = cal
                        pv = 1.0 / (1.0 + np.exp(-(a_c * np.log(pv / (1 - pv)) + b_c)))
                    ps.append(pv)
                    vbests.append(vbest)
                oof[te] = np.mean(ps, axis=0)
                acc_phys[te] += p_phys.numpy()
                fold_hist.append({"fold": k, "n_train": len(tr), "n_test": len(te),
                                  "variant": "hybrid", "n_features": len(cols),
                                  "n_seeds": n_seeds, "inner_val_loss": float(np.mean(vbests))})
            else:
                net = _train_bounded(Xtr, ytr, dtr, ftr, epochs, seed)
                with torch.no_grad():
                    a, b, n0 = net(Xte)
                    oof[te] = net.tcp_from_params(a, b, n0, dte, fte).clamp(1e-6, 1 - 1e-6).numpy()
                fold_hist.append({"fold": k, "n_train": len(tr), "n_test": len(te),
                                  "variant": "bounded", "n_features": len(cols)})
            acc[te] += oof[te]
            acc_n[te] += 1
            continue
        model, hist = train_pinn_from_df(tr_df, site="HN", output_dir=out / f"fold{k}",
                                         epochs=epochs, lr=5e-4, lambda_physics=0.3,
                                         lambda_boundary=0.1, batch_size=16, val_split=0.2,
                                         seed=seed, min_patients=20, experimental=True)
        if model is None:
            continue
        Xte, _, _, _, _ = _prepare_tensors(te_df, FEATURE_COLUMNS)
        dose = torch.tensor(te_df["total_dose_gy"].astype(float).values, dtype=torch.float32).clamp(min=.1)
        nfx = torch.tensor(te_df["n_fractions"].astype(float).values, dtype=torch.float32).clamp(min=1.)
        model.eval()
        with torch.no_grad():
            a, b, n0 = model(Xte)
            p = model.tcp_from_params(a, b, n0, dose, nfx).reshape(-1).clamp(1e-6, 1 - 1e-6)
        oof[te] = p.numpy()
        acc[te] += oof[te]
        acc_n[te] += 1
        fold_hist.append({"fold": k, "n_train": len(tr), "n_test": len(te),
                          "epochs_run": len(hist.get("val_loss", [])),
                          "best_val_loss": float(min(hist.get("val_loss", [np.nan])))})
    # average each patient's held-out prediction over the repeated partitions
    oof = np.where(acc_n > 0, acc / np.maximum(acc_n, 1), np.nan)
    if acc_phys.any():
        oof_phys = np.where(acc_n > 0, acc_phys / np.maximum(acc_n, 1), np.nan)
    ok = np.isfinite(oof)
    base = float(y.mean())
    res = {
        "n": int(len(df)), "events_controlled": int(y.sum()), "folds": folds,
        "repeats": repeats, "n_seeds_ensembled": n_seeds,
        "epochs_max": epochs, "lr": 5e-4, "lambda_physics": 0.3, "lambda_boundary": 0.1,
        "batch_size": 16, "seed": seed, "n_features": int(df.shape[1] - 2),
        "cv_AUC": auc(y[ok], oof[ok]),
        "cv_MAE": float(np.mean(np.abs(oof[ok] - y[ok]))),
        "cv_RMSE": float(np.sqrt(np.mean((oof[ok] - y[ok]) ** 2))),
        "cv_Brier": float(np.mean((oof[ok] - y[ok]) ** 2)),
        "base_rate": base,
        "base_rate_MAE": float(np.mean(np.abs(base - y))),
        "prediction_min": float(np.nanmin(oof)), "prediction_max": float(np.nanmax(oof)),
        "prediction_sd": float(np.nanstd(oof)),
        "n_distinct_predictions": int(len(np.unique(np.round(oof[ok], 6)))),
        "beats_base_rate_MAE": bool(np.mean(np.abs(oof[ok] - y[ok])) < np.mean(np.abs(base - y))),
        "features_used_per_fold": n_feat_used or None,
        "texture_selection": "nested (inside training fold)" if use_texture else "n/a",
        "folds_detail": fold_hist,
    }
    if np.isfinite(oof_phys).any():
        okp = np.isfinite(oof_phys)
        res["cv_AUC_physics_term_only"] = auc(y[okp], oof_phys[okp])
    res["cv_AUC_bootstrap95"] = auc_ci(y[ok], oof[ok], seed)
    pd.DataFrame({"pseudonym": df["pseudonym"], "tcp_outcome": y, "pinn_oof": oof,
                  "pinn_physics_term": oof_phys}).to_csv(
        out / "V2_PINN_oof_predictions.csv", index=False)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--final-validation", required=True, type=Path)
    ap.add_argument("--features", required=True, type=Path)
    ap.add_argument("--texture", type=Path, default=None)
    ap.add_argument("--clinical", required=True, type=Path)
    ap.add_argument("--map-csv", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=5, help="repeated stratified CV partitions")
    ap.add_argument("--seeds", type=int, default=3, help="model inits ensembled per fold (hybrid)")
    a = ap.parse_args()
    for p in ("engine", "engine_advanced", "engine_advanced_f"):
        sys.path.insert(0, str(a.repo / p))
    a.out.mkdir(parents=True, exist_ok=True)

    master = pd.read_csv(a.features / "patient_features_ALL.csv", low_memory=False)
    tex = pd.read_csv(a.texture, low_memory=False) if a.texture and a.texture.is_file() else None
    df = build_frame(master, a.final_validation, tex, a.clinical, a.map_csv)
    df.to_csv(a.out / "V2_PINN_input_features.csv", index=False)
    print(f"PINN v2 frame: {len(df)} patients x {df.shape[1]-2} features "
          f"(dose+physics+clinical{'+texture' if tex is not None else ''})")

    has_tex = any(c.startswith("dosio_") for c in df.columns)
    base_cols = [c for c in df.columns if not c.startswith("dosio_")]
    df_base = df[base_cols]

    # (name, frame, bounded, hybrid, use_texture)
    jobs = [
        ("A. shipped arch | dose only (as published v1)", df_base, False, False, False),
        ("B. bounded-param | dose+clinical", df_base, True, False, False),
        ("C. HYBRID physics+residual | dose+clinical", df_base, False, True, False),
    ]
    if has_tex:
        jobs += [
            ("D. bounded-param | dose+clinical+texture", df, True, False, True),
            ("E. HYBRID physics+residual | dose+clinical+texture", df, False, True, True),
        ]

    out_rows = []
    for name, d, bounded, hybrid, use_tex in jobs:
        slug = name.split(".")[0].strip()
        r = run_cv(d, a.repo, a.out / f"variant_{slug}", a.epochs, a.seed,
                   bounded=bounded, hybrid=hybrid, use_texture=use_tex,
                   repeats=(a.repeats if (bounded or hybrid) else 1),
                   n_seeds=(a.seeds if hybrid else 1))
        r["feature_set"] = name
        r["architecture"] = ("hybrid physics+residual v2c" if hybrid else
                             "bounded-parameter v2b" if bounded else
                             "shipped (unbounded Softplus)")
        out_rows.append(r)
        lo, hi = r.get("cv_AUC_bootstrap95", [float("nan")] * 2)
        print(f"  {name:52s} cvAUC={r['cv_AUC']:.3f} [{lo:.3f}-{hi:.3f}]  "
              f"MAE={r['cv_MAE']:.3f} (base {r['base_rate_MAE']:.3f})  "
              f"distinct_preds={r['n_distinct_predictions']}")
    res = pd.DataFrame(out_rows)
    res.drop(columns=["folds_detail"]).to_csv(a.out / "V2_PINN_RESULTS.csv", index=False)
    try:
        res.drop(columns=["folds_detail"]).to_excel(a.out / "V2_PINN_RESULTS.xlsx", index=False)
    except Exception:
        pass
    (a.out / "V2_PINN_RESULTS.json").write_text(json.dumps(out_rows, indent=2, default=str),
                                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
