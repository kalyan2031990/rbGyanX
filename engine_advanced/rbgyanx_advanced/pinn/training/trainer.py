"""PINN training loop stub — full training requires institutional outcome_csv."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def train_tcp_pinn(
    feature_df: pd.DataFrame,
    outcome_col: str,
    output_path: Path,
    epochs: int = 100,
    lambda_physics: float = 1.0,
) -> bool:
    try:
        import torch
        from rbgyanx_advanced.pinn.models.pinn_base import RadiobiologyPINN
        from rbgyanx_advanced.pinn.training.physics_loss import lq_tcp_physics_residual
    except ImportError:
        logger.warning("PINN training skipped: torch not installed")
        return False

    if outcome_col not in feature_df.columns or len(feature_df) < 20:
        logger.warning("PINN training needs >=20 rows with %s", outcome_col)
        return False

    numeric_cols = feature_df.select_dtypes(include=[np.number]).columns[:10]
    if len(numeric_cols) < 3:
        return False

    X = torch.tensor(feature_df[numeric_cols].fillna(0).values, dtype=torch.float32)
    y = torch.tensor(feature_df[outcome_col].astype(float).values, dtype=torch.float32)
    model = RadiobiologyPINN(n_features=X.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    for _ in range(min(epochs, 50)):
        opt.zero_grad()
        alpha, beta, n0 = model(X)
        dose = X[:, 0] * 60 + 10
        nfx = torch.clamp(X[:, 1] if X.shape[1] > 1 else torch.ones_like(dose) * 30, min=1)
        tcp = model.tcp_from_params(alpha, beta, n0, dose, nfx)
        data_loss = torch.mean((tcp.squeeze() - y) ** 2)
        phys = lq_tcp_physics_residual(tcp.squeeze(), alpha, beta, n0, dose, nfx)
        loss = data_loss + lambda_physics * phys
        loss.backward()
        opt.step()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)
    logger.info("PINN weights saved to %s", output_path)
    return True
