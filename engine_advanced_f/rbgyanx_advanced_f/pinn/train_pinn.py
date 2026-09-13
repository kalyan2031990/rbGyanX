"""Full PINN training loop (§30) — BCE + physics + boundary losses."""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

FEATURE_COLUMNS = [
    "EQD2_gy",
    "BED_gy",
    "Dmean_gy",
    "D95_gy",
    "TCP_Poisson",
    "TCP_gEUD",
    "dosio_mean",
    "dosio_std",
    "dosio_d2_gy",
    "dosio_d98_gy",
    "dosio_skewness",
    "dosio_entropy",
]


def _load_and_merge(features_csv: Path, outcome_csv: Path, site: str) -> pd.DataFrame:
    feat = pd.read_csv(features_csv)
    out = pd.read_csv(outcome_csv)
    id_col = next(
        (c for c in out.columns if c.lower() in ("anonpatientid", "patientid", "id")),
        None,
    )
    if id_col:
        out = out.rename(columns={id_col: "AnonPatientID"})
    out_col = "tcp_outcome" if "tcp_outcome" in out.columns else "LocalControl"
    if out_col not in out.columns:
        raise ValueError("outcome CSV needs tcp_outcome or LocalControl")
    out = out.rename(columns={out_col: "tcp_outcome"})
    df = feat.merge(out[["AnonPatientID", "tcp_outcome"]], on="AnonPatientID", how="inner")
    if "site" in df.columns:
        df = df[df["site"].astype(str).str.upper() == site.upper()]
    logger.info("PINN training: %d patients, site=%s", len(df), site)
    return df


def _prepare_tensors(df: pd.DataFrame, feature_cols: list[str]):
    if not _TORCH_AVAILABLE:
        raise ImportError("PyTorch required. pip install torch")

    available = [c for c in feature_cols if c in df.columns]
    if len(available) < 3:
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        available = [c for c in numeric if c != "tcp_outcome"][: max(3, len(FEATURE_COLUMNS))]
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.warning("PINN: %d feature columns missing: %s", len(missing), missing[:5])

    X = df[available].fillna(0.0).values.astype(np.float32)
    y = df["tcp_outcome"].astype(float).values.astype(np.float32)
    means = X.mean(axis=0)
    stds = X.std(axis=0)
    stds[stds < 1e-8] = 1.0
    X = (X - means) / stds
    return (
        torch.tensor(X, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
        means,
        stds,
        available,
    )


def train_pinn_from_df(
    df: pd.DataFrame,
    site: str,
    output_dir: Path,
    epochs: int = 200,
    lr: float = 1e-3,
    lambda_physics: float = 1.0,
    lambda_boundary: float = 0.5,
    batch_size: int = 32,
    val_split: float = 0.2,
    seed: int = 42,
    min_patients: int = 20,
    experimental: bool = False,
) -> tuple[object | None, dict]:
    if not experimental:
        logger.warning(
            "PINN training refused: set experimental=True (research-grade; not for clinical use)"
        )
        return None, {"refused": True, "reason": "experimental_flag_required"}
    logger.warning("PINN: research-grade implementation — NOT FOR CLINICAL USE")
    if not _TORCH_AVAILABLE:
        logger.warning("PINN training skipped: torch not installed")
        return None, {}
    if "tcp_outcome" not in df.columns and "LocalControl" in df.columns:
        df = df.rename(columns={"LocalControl": "tcp_outcome"})
    if "tcp_outcome" not in df.columns or len(df) < min_patients:
        logger.warning("PINN needs >=%d rows with tcp_outcome", min_patients)
        return None, {}

    from rbgyanx_advanced.pinn.models.pinn_base import RadiobiologyPINN
    from rbgyanx_advanced.pinn.training.physics_loss import (
        lq_tcp_physics_residual,
        tcp_boundary_loss,
    )

    torch.manual_seed(seed)
    np.random.seed(seed)

    X, y, feat_means, feat_stds, feat_names = _prepare_tensors(df, FEATURE_COLUMNS)
    # Per-patient physics inputs. Previously the trainer hard-coded 30 fractions and the validation
    # pass hard-coded 50 Gy / 25 fx for EVERY patient, so the validation TCP ignored the actual plan
    # and the reported val_loss (and the LR schedule driven by it) were meaningless.
    if "total_dose_gy" in df.columns:
        dose_all = torch.tensor(df["total_dose_gy"].astype(float).values, dtype=torch.float32)
    else:
        dose_all = torch.tensor(df[feat_names[0]].astype(float).values, dtype=torch.float32)
    if "n_fractions" in df.columns:
        nfx_all = torch.tensor(df["n_fractions"].astype(float).values, dtype=torch.float32)
    else:
        nfx_all = torch.full((len(X),), 30.0)
    dose_all = torch.clamp(dose_all, min=0.1)
    nfx_all = torch.clamp(nfx_all, min=1.0)
    n_features = X.shape[1]
    n = len(X)
    n_val = max(5, int(n * val_split))
    idx = torch.randperm(n)
    X_tr, y_tr = X[idx[n_val:]], y[idx[n_val:]]
    X_val, y_val = X[idx[:n_val]], y[idx[:n_val]]
    d_tr, d_val = dose_all[idx[n_val:]], dose_all[idx[:n_val]]
    f_tr, f_val = nfx_all[idx[n_val:]], nfx_all[idx[:n_val]]

    model = RadiobiologyPINN(n_features=n_features)
    optimiser = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimiser, patience=20, factor=0.5)
    loader = DataLoader(TensorDataset(X_tr, y_tr, d_tr, f_tr),
                        batch_size=min(batch_size, len(X_tr)), shuffle=True)
    X_zeros = torch.zeros(16, n_features)
    X_high = X_tr[: min(16, len(X_tr))].clone()

    history: dict[str, list[float]] = {
        "train_loss": [],
        "val_loss": [],
        "physics_loss": [],
        "data_loss": [],
    }
    max_epochs = int(epochs)
    best_val, best_state, patience, bad = float("inf"), None, 40, 0

    for epoch in range(max_epochs):
        model.train()
        epoch_data, epoch_phys = 0.0, 0.0
        for X_b, y_b, d_b, f_b in loader:
            optimiser.zero_grad()
            alpha, beta, n0 = model(X_b)
            total_dose = d_b            # the patient's ACTUAL prescribed/plan dose
            n_fractions = f_b           # the patient's ACTUAL fraction count
            tcp_pred = model.tcp_from_params(alpha, beta, n0, total_dose, n_fractions)
            tcp_pred = torch.clamp(tcp_pred.reshape(-1), 1e-6, 1 - 1e-6)
            loss_data = nn.BCELoss()(tcp_pred, y_b)
            loss_phys = lq_tcp_physics_residual(
                tcp_pred, alpha, beta, n0, total_dose, n_fractions
            )
            loss_bound = tcp_boundary_loss(model, X_zeros, X_high)
            loss = loss_data + lambda_physics * loss_phys + lambda_boundary * loss_bound
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimiser.step()
            epoch_data += loss_data.item()
            epoch_phys += loss_phys.item()

        model.eval()
        with torch.no_grad():
            alpha_v, beta_v, n0_v = model(X_val)
            dose_v = d_val
            nfx_v = f_val
            tcp_v = torch.clamp(
                model.tcp_from_params(alpha_v, beta_v, n0_v, dose_v, nfx_v).squeeze(),
                1e-6,
                1 - 1e-6,
            )
            val_loss = nn.BCELoss()(tcp_v, y_val).item()

        scheduler.step(val_loss)
        if val_loss < best_val - 1e-5:
            best_val, bad = val_loss, 0
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                logger.info("PINN early stop at epoch %d (best val %.4f)", epoch, best_val)
                history["train_loss"].append(epoch_data / max(len(loader), 1))
                history["val_loss"].append(val_loss)
                history["physics_loss"].append(epoch_phys / max(len(loader), 1))
                history["data_loss"].append(epoch_data / max(len(loader), 1))
                break
        history["train_loss"].append(epoch_data / max(len(loader), 1))
        history["val_loss"].append(val_loss)
        history["physics_loss"].append(epoch_phys / max(len(loader), 1))
        history["data_loss"].append(epoch_data / max(len(loader), 1))

    if best_state is not None:
        model.load_state_dict(best_state)   # restore BEST epoch, not the last one
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_path = output_dir / f"tcp_pinn_{site.lower()}.pt"
    torch.save(
        {
            "model_state": model.state_dict(),
            "feat_means": feat_means,
            "feat_stds": feat_stds,
            "feat_names": feat_names,
            "site": site,
            "n_features": n_features,
            "n_patients_train": int(len(X_tr)),
            "final_val_loss": history["val_loss"][-1] if history["val_loss"] else math.nan,
        },
        save_path,
    )
    logger.info("PINN model saved to %s", save_path)
    return model, history


def train_pinn(
    features_csv: Path,
    outcome_csv: Path,
    site: str,
    output_dir: Path,
    epochs: int = 500,
    **kwargs,
) -> tuple[object | None, dict]:
    df = _load_and_merge(features_csv, outcome_csv, site)
    return train_pinn_from_df(df, site, output_dir, epochs=epochs, **kwargs)
