"""LQ physics residual losses for PINN training (§19)."""

from __future__ import annotations

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def lq_tcp_physics_residual(tcp_pred, alpha_pred, beta_pred, n0_pred, total_dose, n_fractions):
    import torch

    dpf = total_dose / n_fractions.clamp(min=1)
    sf = torch.exp(-alpha_pred * dpf - beta_pred * dpf**2)
    tcp_lq = torch.exp(-n0_pred * sf**n_fractions)
    return torch.mean((tcp_pred - tcp_lq) ** 2)


def tcp_boundary_loss(model, feature_zeros, feature_highdose):
    import torch

    alpha_z, beta_z, n0_z = model(feature_zeros)
    tcp_zero = model.tcp_from_params(
        alpha_z, beta_z, n0_z,
        torch.zeros(len(feature_zeros)),
        torch.ones(len(feature_zeros)),
    )
    alpha_h, beta_h, n0_h = model(feature_highdose)
    tcp_high = model.tcp_from_params(
        alpha_h, beta_h, n0_h,
        torch.full((len(feature_highdose),), 200.0),
        torch.full((len(feature_highdose),), 100.0),
    )
    return torch.mean(tcp_zero**2) + torch.mean((1.0 - tcp_high) ** 2)
