"""Part F configuration fields (mixed into RunConfig via getattr)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class PartFConfig:
    enable_bayesian_ntcp: bool = False
    bayesian_ntcp_trace_dir: Path | None = None
    bayesian_n_samples: int = 500
    bayesian_n_tune: int = 500
    pinn_train: bool = False
    pinn_model_dir: Path | None = None
    pinn_epochs: int = 200
    pinn_lambda_physics: float = 1.0
    pinn_lambda_boundary: float = 0.5
