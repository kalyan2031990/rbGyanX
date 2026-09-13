from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rbgyanx_advanced.advanced_config import AdvancedRunConfig


@dataclass
class PINNConfig(AdvancedRunConfig):
    pinn_model_dir: Path | None = None
    pinn_train: bool = False
    pinn_epochs: int = 500
    lambda_physics: float = 1.0
    lambda_boundary: float = 0.5
    pinn_sites: list[str] = field(default_factory=lambda: ["HN", "LUNG", "BREAST"])
