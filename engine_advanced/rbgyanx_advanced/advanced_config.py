"""Extended configuration for ADVANCED analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rbgyanx_engine.run_config import RunConfig


@dataclass
class AdvancedRunConfig(RunConfig):
    """RunConfig plus PINN / dosiomics options (ADVANCED only)."""

    pinn_model_dir: Path | None = None
    pinn_train: bool = False
    pinn_epochs: int = 500
    lambda_physics: float = 1.0
    lambda_boundary: float = 0.5
    pinn_sites: list[str] = field(default_factory=lambda: ["HN", "LUNG", "BREAST"])
    enable_dosiomics: bool = True
    dose3d_voxel_mm: float = 3.0
