"""Worked extension example — a user-added NTCP model through the documented extension point.

**What this demonstrates.** The paper's claim is that rbGyanX is "a complete open-source package
anyone may extend". *Available* and *extensible* are different claims, and the second one needs
demonstrating rather than asserting. This file is the demonstration: a model the engine did not
ship, added by a user, reaching the engine's own model registry without touching engine code.

The extension point is `engine/radiobiology/model_registry.py`:

  * `NTCPModelProtocol` — any object with
    `compute_ntcp_dvh(dvh_df, organ_params, n_fractions=1) -> dict`
  * `register_ntcp_model(name, instance)` — adds it to the registry
  * `iter_ntcp_models()` — what the engine then sees

Nothing here subclasses an engine class, patches an engine module, or edits a dispatch table. The
protocol is structural, so a plain object that satisfies it is enough. That is the property being
demonstrated.

**The model.** Niemierko's gEUD-logistic NTCP (Niemierko 1999; Gay & Niemierko, Phys Med 2007):

    NTCP = 1 / (1 + (TD50 / gEUD) ** (4 * gamma50))

with gEUD the generalised equivalent uniform dose over the differential DVH,

    gEUD = ( sum_i v_i * D_i**a ) ** (1/a)

It is chosen deliberately for a reason that matters more than novelty: **it has closed-form
identities that can be tested without reference to any previously observed number**, which is what
makes the accompanying tests *positive controls* in the same sense as the engine's own 22 — see
`tests/test_extension_example.py`:

  * `NTCP = 0.5` **exactly** when `gEUD == TD50`, for every `TD50` and every `gamma50`;
  * monotonically increasing in dose;
  * `gamma50` controls the slope at `TD50` — `dNTCP/d(ln gEUD) = gamma50` there;
  * `a = 1` makes gEUD the mean dose, so a uniform DVH reduces to the dose itself.

Those hold by construction in the published formalism, so a test of them is a test of this
implementation and not a regression lock on its current output.

**Deliberately NOT claimed.** This is a demonstration of the extension mechanism. It is not a
clinically parameterised model, it is not used anywhere in the manuscript's results, and the
`TD50`/`gamma50` values in the tests are the published ones only where cited. The engine's own
NTCP models remain the ones every reported number comes from.

Run the tests with:

    pytest tests/test_extension_example.py -v
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

# The documented extension point. Nothing else from the engine is imported.
from radiobiology.model_registry import register_ntcp_model

_CLIP_LO = 1e-15
_CLIP_HI = 1.0 - 1e-15


def generalised_eud(doses_gy: np.ndarray, volume_frac: np.ndarray, a: float) -> float:
    """gEUD = (sum v_i D_i^a)^(1/a), with the volume fractions normalised to sum to 1.

    `a = 1` returns the mean dose, which is the identity the tests pin. Non-positive doses are
    dropped rather than clamped: a zero dose with a negative `a` is a pole, not a small number,
    and silently clamping it would invent dose where there is none.
    """
    d = np.asarray(doses_gy, dtype=float)
    v = np.asarray(volume_frac, dtype=float)
    ok = np.isfinite(d) & np.isfinite(v) & (d > 0) & (v > 0)
    if not ok.any() or not math.isfinite(a) or a == 0:
        return float("nan")
    d, v = d[ok], v[ok]
    v = v / v.sum()
    return float(np.power(np.sum(v * np.power(d, a)), 1.0 / a))


def niemierko_logistic_ntcp(geud_gy: float, TD50_gy: float, gamma50: float) -> float:
    """NTCP = 1 / (1 + (TD50/gEUD)^(4*gamma50)). Returns NaN on any invalid parameter."""
    if not all(math.isfinite(x) for x in (geud_gy, TD50_gy, gamma50)):
        return float("nan")
    if geud_gy <= 0 or TD50_gy <= 0 or gamma50 <= 0:
        return float("nan")
    try:
        # computed in logs so a large gamma50 cannot overflow the ratio
        z = 4.0 * gamma50 * (math.log(TD50_gy) - math.log(geud_gy))
        if z > 700:
            return _CLIP_LO
        if z < -700:
            return _CLIP_HI
        return float(np.clip(1.0 / (1.0 + math.exp(z)), _CLIP_LO, _CLIP_HI))
    except (OverflowError, ValueError, ZeroDivisionError):
        return float("nan")


@dataclass
class NiemierkoLogisticNTCP:
    """Satisfies `NTCPModelProtocol` by structure alone - no engine base class involved."""

    name: str = "niemierko_logistic"

    def compute_ntcp_dvh(
        self,
        dvh_df: Any,
        organ_params: Any,
        n_fractions: int = 1,
    ) -> dict:
        """Compute NTCP from a differential DVH.

        `dvh_df` needs `dose_gy` and `volume_frac`, matching the engine's own convention.
        `organ_params` supplies `TD50_gy`, `gamma50` and the gEUD exponent `a` (mapping-attribute
        or dict, so a caller can pass either).
        """
        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        td50 = _get(organ_params, "TD50_gy")
        gamma50 = _get(organ_params, "gamma50")
        a = _get(organ_params, "a", 1.0)

        try:
            doses = np.asarray(dvh_df["dose_gy"], dtype=float)
            vols = np.asarray(dvh_df["volume_frac"], dtype=float)
        except (KeyError, TypeError, ValueError):
            return {"ntcp": float("nan"), "model": self.name,
                    "reason": "dvh_df must provide dose_gy and volume_frac"}

        geud = generalised_eud(doses, vols, float(a) if a is not None else 1.0)
        ntcp = niemierko_logistic_ntcp(geud, float(td50) if td50 is not None else float("nan"),
                                       float(gamma50) if gamma50 is not None else float("nan"))
        return {
            "ntcp": ntcp,
            "geud_gy": geud,
            "model": self.name,
            "TD50_gy": td50,
            "gamma50": gamma50,
            "a": a,
            "n_fractions": n_fractions,
            # Stated, not implied: this extension does no fractionation correction. A caller
            # wanting EQD2 must pass an already-corrected DVH. Saying so in the output is cheaper
            # than a reader assuming otherwise.
            "fractionation_corrected": False,
        }


def install() -> NiemierkoLogisticNTCP:
    """Register the model and return it. Idempotent - re-registering replaces the instance."""
    model = NiemierkoLogisticNTCP()
    register_ntcp_model(model.name, model)
    return model


if __name__ == "__main__":
    import pandas as pd

    m = install()
    # a uniform 30 Gy DVH against a TD50 of 30 Gy must give exactly 0.5
    dvh = pd.DataFrame({"dose_gy": [30.0] * 100, "volume_frac": [0.01] * 100})
    out = m.compute_ntcp_dvh(dvh, {"TD50_gy": 30.0, "gamma50": 2.0, "a": 1.0})
    print(f"gEUD = {out['geud_gy']:.6f} Gy   NTCP = {out['ntcp']:.6f}   (expected exactly 0.5)")
    from radiobiology.model_registry import iter_ntcp_models
    print("registry now contains:", sorted(iter_ntcp_models()))
