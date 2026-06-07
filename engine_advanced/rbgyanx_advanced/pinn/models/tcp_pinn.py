"""PINN TCP adapter for model registry (§19)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from rbgyanx_advanced.pinn.models.pinn_base import TORCH_AVAILABLE, RadiobiologyPINN


class PINNTCPAdapter:
    """Registry adapter: DVH summary features → LQ-constrained TCP."""

    def __init__(
        self,
        model: RadiobiologyPINN | None = None,
        site: str = "HN",
        feat_means: np.ndarray | None = None,
        feat_stds: np.ndarray | None = None,
        feat_names: list[str] | None = None,
    ):
        self.model = model
        self.site = site
        self.feat_means = feat_means
        self.feat_stds = feat_stds
        self.feat_names = feat_names or []

    @classmethod
    def load(cls, path: Path, site: str = "HN") -> "PINNTCPAdapter":
        if not TORCH_AVAILABLE or not path.is_file():
            return cls(model=None, site=site)
        import torch

        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        if isinstance(ckpt, dict) and "model_state" in ckpt:
            n_features = int(ckpt.get("n_features", len(ckpt.get("feat_names", [])) or 10))
            model = RadiobiologyPINN(n_features=n_features)
            model.load_state_dict(ckpt["model_state"])
            model.eval()
            return cls(
                model=model,
                site=str(ckpt.get("site", site)),
                feat_means=np.asarray(ckpt.get("feat_means")) if ckpt.get("feat_means") is not None else None,
                feat_stds=np.asarray(ckpt.get("feat_stds")) if ckpt.get("feat_stds") is not None else None,
                feat_names=list(ckpt.get("feat_names", [])),
            )
        model = RadiobiologyPINN()
        model.load_state_dict(ckpt)
        model.eval()
        return cls(model=model, site=site)

    def _feature_vector(self, dvh_df: pd.DataFrame, n_fractions: int, site_params, target_type: str):
        from dicom_io.dvh_shape_features import compute_dvh_shape_features

        shape = compute_dvh_shape_features(dvh_df)
        dmean = shape.get("D50_gy", 0.0) or 0.0
        return np.array(
            [
                shape.get("D2_gy", dmean),
                dmean,
                shape.get("D98_gy", dmean),
                shape.get("dose_std_gy", 0.0) or 0.0,
                shape.get("dose_skewness", 0.0) or 0.0,
                float(getattr(site_params, "alpha_beta_gy", 10.0)),
                float(n_fractions),
                dmean,
                shape.get("V95_rx_frac", 0.0) or 0.0,
                shape.get("D2_D98_ratio", 1.0) or 1.0,
            ],
            dtype=np.float32,
        )

    def _tensor_from_features(self, vec: np.ndarray):
        import torch

        x = torch.tensor(vec, dtype=torch.float32).unsqueeze(0)
        if self.feat_means is not None and self.feat_stds is not None and len(self.feat_names):
            out = np.zeros(len(self.feat_names), dtype=np.float32)
            name_to_val = dict(zip(self._default_feat_names(), vec))
            for i, name in enumerate(self.feat_names):
                out[i] = name_to_val.get(name, 0.0)
            stds = np.asarray(self.feat_stds, dtype=np.float32)
            stds[stds < 1e-8] = 1.0
            out = (out - np.asarray(self.feat_means, dtype=np.float32)) / stds
            x = torch.tensor(out, dtype=torch.float32).unsqueeze(0)
        return x

    @staticmethod
    def _default_feat_names() -> list[str]:
        return [
            "D2_gy", "D50_gy", "D98_gy", "dose_std_gy", "dose_skewness",
            "alpha_beta_gy", "n_fractions", "Dmean_proxy", "V95_rx_frac", "D2_D98_ratio",
        ]

    def compute_tcp_dvh(self, dvh_df, n_fractions: int, site_params, target_type: str = "GTV") -> dict:
        if self.model is None or dvh_df is None or dvh_df.empty:
            return {"tcp": math.nan, "model": f"PINN_{self.site}"}

        import torch

        vec = self._feature_vector(dvh_df, n_fractions, site_params, target_type)
        x = self._tensor_from_features(vec)
        with torch.no_grad():
            alpha, beta, n0 = self.model(x)
            total = float(dvh_df["dose_gy"].max()) if "dose_gy" in dvh_df.columns else 60.0
            tcp = self.model.tcp_from_params(
                alpha, beta, n0,
                torch.tensor([total]),
                torch.tensor([float(n_fractions)]),
            )
        return {"tcp": float(tcp.item()), "model": f"PINN_{self.site}"}


class PINNTCPStub(PINNTCPAdapter):
    """Untrained stub: returns NaN unless weights loaded."""

    def compute_tcp_dvh(self, dvh_df, n_fractions: int, site_params, target_type: str = "GTV") -> dict:
        if self.model is not None:
            return super().compute_tcp_dvh(dvh_df, n_fractions, site_params, target_type)
        return {"tcp": math.nan, "model": "PINN_STUB"}
