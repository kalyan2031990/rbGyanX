"""Physics-informed NN base (§19)."""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None  # type: ignore


class RadiobiologyPINN(nn.Module if TORCH_AVAILABLE else object):  # type: ignore[misc]
    def __init__(self, n_features: int = 10, n_hidden: int = 128):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required for PINN: pip install torch")
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, n_hidden),
            nn.Tanh(),
            nn.Linear(n_hidden, n_hidden),
            nn.Tanh(),
            nn.Linear(n_hidden, n_hidden),
            nn.Tanh(),
            nn.Linear(n_hidden, 3),
            nn.Softplus(),
        )

    def forward(self, x):
        params = self.net(x)
        alpha = params[:, 0]
        beta = params[:, 1]
        n0 = params[:, 2] * 1e7
        return alpha, beta, n0

    def tcp_from_params(self, alpha, beta, n0, total_dose, n_fractions):
        import torch

        dpf = total_dose / n_fractions.clamp(min=1)
        sf = torch.exp(-alpha * dpf - beta * dpf**2)
        sf_total = sf**n_fractions
        n_eff = n0 * sf_total
        return torch.exp(-n_eff)
