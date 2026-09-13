"""
LQ-constrained physics-informed neural network for outcome classification (C4).

Predicts P(loco-regional recurrence) from the SAME feature vector as the dosiomics
ML class (C3). The physics prior encodes the qualitative behaviour of the LQ/TCP
model — tumour-control probability increases monotonically with delivered tumour
dose — so recurrence probability must be **non-increasing** in the dose driver
(e.g. PTV BED/gEUD), with boundary conditions p→1 at zero dose and p→0 at very
high dose.

    L = L_BCE + λ_phys · L_LQ + λ_bc · L_BC

``lambda_phys = 0`` reduces this to a plain MLP (the ablation). This is a research
/ benchmark model — it is never part of the clinic-safe BASIC path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    from torch import nn

    TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover - torch is an optional benchmark dep
    TORCH_AVAILABLE = False


@dataclass
class PINNConfig:
    hidden: tuple[int, ...] = (16, 8)
    lambda_phys: float = 1.0
    lambda_bc: float = 0.5
    epochs: int = 300
    lr: float = 1e-2
    weight_decay: float = 1e-3
    seed: int = 0


if TORCH_AVAILABLE:

    class _MLP(nn.Module):
        def __init__(self, n_features: int, hidden: tuple[int, ...]):
            super().__init__()
            layers: list[nn.Module] = []
            prev = n_features
            for h in hidden:
                layers += [nn.Linear(prev, h), nn.Tanh()]
                prev = h
            layers += [nn.Linear(prev, 1)]
            self.net = nn.Sequential(*layers)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x).squeeze(-1)  # logit


class OutcomePINN:
    """sklearn-style LQ-constrained PINN classifier (fit / predict_proba)."""

    def __init__(self, dose_idx: int = 0, config: PINNConfig | None = None):
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch is required for OutcomePINN (benchmark-only dependency).")
        self.dose_idx = dose_idx
        self.cfg = config or PINNConfig()
        self.model: _MLP | None = None
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None

    def _standardise(self, X: np.ndarray, fit: bool) -> np.ndarray:
        if fit:
            self._mean = np.nanmean(X, axis=0)
            self._std = np.nanstd(X, axis=0)
            self._std[self._std < 1e-8] = 1.0
        Xs = (np.nan_to_num(X, nan=0.0) - self._mean) / self._std
        return Xs.astype(np.float32)

    def fit(self, X: np.ndarray, y: np.ndarray) -> OutcomePINN:
        torch.manual_seed(self.cfg.seed)
        np.random.seed(self.cfg.seed)
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        Xs = self._standardise(X, fit=True)
        xt = torch.tensor(Xs, dtype=torch.float32, requires_grad=False)
        yt = torch.tensor(y, dtype=torch.float32)

        self.model = _MLP(X.shape[1], self.cfg.hidden)
        opt = torch.optim.Adam(
            self.model.parameters(), lr=self.cfg.lr, weight_decay=self.cfg.weight_decay
        )
        bce = nn.BCEWithLogitsLoss()

        # Boundary anchors: mean feature vector with the dose driver pushed to
        # standardised extremes (low dose -> recurrence, high dose -> control).
        lo = np.zeros((1, X.shape[1]), dtype=np.float32)
        hi = np.zeros((1, X.shape[1]), dtype=np.float32)
        lo[0, self.dose_idx] = -3.0
        hi[0, self.dose_idx] = 3.0
        lo_t = torch.tensor(lo)
        hi_t = torch.tensor(hi)

        for _ in range(self.cfg.epochs):
            opt.zero_grad()
            logit = self.model(xt)
            loss = bce(logit, yt)

            if self.cfg.lambda_phys > 0 or self.cfg.lambda_bc > 0:
                xg = xt.clone().detach().requires_grad_(True)
                p = torch.sigmoid(self.model(xg))
                grad = torch.autograd.grad(p.sum(), xg, create_graph=True, retain_graph=True)[0][
                    :, self.dose_idx
                ]
                # Penalise recurrence INCREASING with dose (LQ monotonicity prior).
                l_lq = torch.mean(torch.relu(grad) ** 2)
                p_lo = torch.sigmoid(self.model(lo_t))
                p_hi = torch.sigmoid(self.model(hi_t))
                l_bc = torch.mean((1.0 - p_lo) ** 2) + torch.mean(p_hi**2)
                loss = loss + self.cfg.lambda_phys * l_lq + self.cfg.lambda_bc * l_bc

            loss.backward()
            opt.step()
        self.model.eval()
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("OutcomePINN not fitted.")
        Xs = self._standardise(np.asarray(X, dtype=float), fit=False)
        with torch.no_grad():
            p = torch.sigmoid(self.model(torch.tensor(Xs, dtype=torch.float32))).numpy()
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.column_stack([1.0 - p, p])
