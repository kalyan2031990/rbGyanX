"""
Visualisation demo — one API, two engines (v2 Phase 4 · Slice 2).

Renders the three core views with BOTH backends from the same specs, so you can see that the
interactive and publication outputs are two renderings of one truth:

    python examples/viz_demo.py

Writes to examples/output/viz/:
    *_interactive.html   Plotly    — hover, zoom, legend toggle (what the Qt app embeds)
    *_publication.png    Matplotlib — print-ready

ILLUSTRATIVE ONLY: every curve below is synthetic, generated from closed-form functions.
No patient data is read, written, or transmitted.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rbgyanx.viz import (
    DoseResponseCurve,
    DoseResponseSpec,
    DVHCurve,
    DVHSpec,
    OptimismRow,
    OptimismSpec,
    available_backends,
    get_backend,
)

OUT = Path(__file__).resolve().parent / "output" / "viz"


def dvh_spec() -> DVHSpec:
    """A target and two OARs with plausible synthetic shapes."""
    dose = np.linspace(0, 72, 120)
    return DVHSpec(
        curves=[
            DVHCurve("PTV70", dose, 100 * np.clip(1 - (dose / 71.0) ** 12, 0, 1)),
            DVHCurve("Parotid", dose, 100 * np.exp(-((dose / 20.0) ** 1.6))),
            DVHCurve("Spinal cord", dose, 100 * np.exp(-((dose / 12.0) ** 2.2))),
        ],
        title="DVH — synthetic demonstration case",
    )


def dose_response_spec() -> DoseResponseSpec:
    """Two NTCP models + a Monte-Carlo band + the uNTCP consensus overlay."""
    dose = np.linspace(0, 80, 160)
    td50 = 39.9

    probit = 0.5 * (1 + np.vectorize(_erf)((dose - td50) / (0.4 * td50 * np.sqrt(2))))
    loglog = 1.0 / (1.0 + (td50 / np.maximum(dose, 1e-9)) ** 2.5)

    rng = np.random.default_rng(0)  # deterministic "Monte-Carlo" parameter sampling
    draws = np.stack(
        [
            0.5 * (1 + np.vectorize(_erf)((dose - t) / (m * t * np.sqrt(2))))
            for t, m in zip(
                rng.normal(td50, 2.5, 200),
                rng.normal(0.40, 0.04, 200).clip(0.15, 0.8),
                strict=True,
            )
        ]
    )
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    consensus = 0.5 * (probit + loglog)

    return DoseResponseSpec(
        curves=[
            DoseResponseCurve("LKB probit", dose, probit, band_lo=lo, band_hi=hi),
            DoseResponseCurve("LKB log-logistic", dose, loglog, dashed=True),
        ],
        consensus=DoseResponseCurve(
            "uNTCP consensus",
            dose,
            consensus,
            band_lo=np.clip(consensus - (hi - lo) / 2, 0, 1),
            band_hi=np.clip(consensus + (hi - lo) / 2, 0, 1),
        ),
        reference_dose_gy=td50,
        title="NTCP dose-response with Monte-Carlo band and uNTCP consensus",
        y_label="NTCP",
    )


def optimism_spec() -> OptimismSpec:
    """The apparent-vs-CV message: flexible models overfit at small event counts."""
    return OptimismSpec(
        rows=[
            OptimismRow("classical (fixed)", 0.60, 0.60),
            OptimismRow("classical (refit)", 0.60, 0.50),
            OptimismRow("covariate logistic", 0.72, 0.64),
            OptimismRow("dosiomics RF", 1.00, 0.63),
            OptimismRow("LQ-PINN", 1.00, 0.59),
        ],
        title="Apparent vs cross-validated AUC (synthetic illustration)",
    )


def _erf(x: float) -> float:
    import math

    return math.erf(x)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    specs = {
        "dvh": dvh_spec(),
        "dose_response": dose_response_spec(),
        "optimism": optimism_spec(),
    }
    backends = available_backends()
    print("available backends:")
    for name, why in backends.items():
        print(f"  {name:12s} {why}")

    for name in backends:
        engine = get_backend(name)
        suffix = "_interactive.html" if engine.interactive else "_publication.png"
        for key, spec in specs.items():
            path = engine.render(spec).save(OUT / f"{key}{suffix}")
            print(f"  wrote {path.relative_to(OUT.parent.parent)}")

    print("\nSame specs, both engines — interactive and publication views agree by construction.")
    print("Synthetic data only; nothing here touches patient records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
