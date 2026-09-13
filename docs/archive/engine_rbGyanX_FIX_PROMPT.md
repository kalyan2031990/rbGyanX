# rbGyanX CDSS — FIX PROMPT (P1 + P2): Bug Fixes, bDVH, uNTCP, NTCP Reporting
## Expert Cursor Implementation Prompt

**Scope:** Three confirmed bugs + three missing core modules that make the existing
NTCP pipeline physically incorrect or clinically incomplete.
All changes are confined to the files listed under each task.
Do NOT touch the TCP pipeline (radiobiology/tcp*, config/site_params.py,
uncertainty/parameter_mc.py, ml_models/, xai/, validation/tcp_evaluator.py)
unless explicitly instructed.

---

## CONTEXT — WHAT EXISTS AND WHY THESE BUGS MATTER

rbGyanX is a dual-endpoint (TCP + NTCP) radiotherapy CDSS.
The TCP side (Phases 1–8) is complete and tested.
The NTCP side is partially built with three correctness issues:

1. **EPV gate is disabled** — the safety check that prevents underpowered logistic
   regression from producing misleading odds ratios is bypassed with `epv_threshold=1.0`.
   In radiation oncology, publishing logistic regression with EPV < 10 is a known
   source of model overfit that has caused incorrect clinical guidance.

2. **LKB probit formula receives wrong inputs** — the function receives
   `v_effective = total_volume_cc` (a volume in cm³) as if it were a dimensionless
   Kutcher-Burman effective volume fraction. For spinal cord (volume ≈ 40 cc),
   the computed `t` argument to the probit is physically wrong. The correct approach
   is to use the gEUD with `a = 1/n` (a mathematically equivalent formulation) and
   pass it to the probit model. This is the standard used in all modern TPS implementations
   (Niemierko & Goitein 1991; Mohan et al. 1992).

3. **No OAR EQD2 correction (bDVH)** — NTCP models require biological equivalent doses
   because OAR α/β values differ from the prescription α/β. For SBRT (e.g. 60 Gy/3 fr),
   the spinal cord receives an EQD2 approximately 2–3× the physical dose. Applying
   NTCP models to the physical DVH without bDVH correction produces systematic errors
   of 30–200% in NTCP for SBRT/SRS treatments. This module is the single highest-impact
   missing piece for clinical correctness.

---

## FIX 1 — EPV GATE BYPASS in `rbgyanx_engine/pipeline.py`

### What's wrong
Line 388 of `pipeline.py`:
```python
mvl = fit_mvl_tcp(X.values, y, feature_names=FEATURE_COLS, epv_threshold=1.0)
```
The hardcoded `epv_threshold=1.0` accepts any EPV ≥ 1 — i.e., 2 recurrence events
and 2 features gives EPV = 1.0 which passes. This completely bypasses the Phase 4
safety mechanism designed to prevent overfitting in small clinical cohorts.

### Fix
```python
# At top of file, add import:
from statistical_models.epv_guard import EPV_MINIMUM

# Replace line 388:
mvl = fit_mvl_tcp(
    X.values, y, feature_names=FEATURE_COLS, epv_threshold=EPV_MINIMUM
)
```

Wrap in try/except to gracefully degrade when EPV is insufficient:
```python
try:
    mvl = fit_mvl_tcp(
        X.values, y, feature_names=FEATURE_COLS, epv_threshold=EPV_MINIMUM
    )
    ...
except ValueError as epv_exc:
    logger.warning(
        "MVL skipped — EPV insufficient: %s "
        "(need EPV≥%.0f; collect more recurrence events or reduce features).",
        epv_exc, EPV_MINIMUM
    )
```

No other changes to `pipeline.py` in this fix.

---

## FIX 2 — LKB PROBIT FORMULA in `radiobiology/ntcp/lkb_probit.py`

### Physics background

The Lyman-Kutcher-Burman (LKB) NTCP probit model (Lyman 1985; Kutcher & Burman 1989):

```
NTCP = Φ(t)
where t = (D_eff − TD50) / (m × TD50)
and   Φ(t) = standard normal CDF = norm.cdf(t)
```

The "effective dose" D_eff for a non-uniform DVH is computed via one of two
mathematically equivalent routes:
- **Route A (KB reduction):** V_eff = Σᵢ vᵢ × (Dᵢ/Dmax)^(1/n), then
  D_eff = Dmax × V_eff^n  (Kutcher & Burman 1989 Eq. 1)
- **Route B (gEUD):** D_eff = gEUD with a = 1/n (Niemierko 1999)
  gEUD = (Σᵢ vᵢ × Dᵢ^a)^(1/a), a = 1/n

Both routes give the same result. Route B is preferred because `compute_geud()`
already exists in `radiobiology/geud_tcp.py` and `NTCPCalculator.compute_all()`
already computes `geud` before calling the probit function.

### Current bug
The current `lkb_probit.py` signature is:
```python
def calculate_ntcp_lkb_probit(dose_metrics, TD50, m, n)
```
It then uses `dose_metrics["v_effective"]` which is `total_volume_cm3` (not a
dimensionless fraction) and `dose_metrics["max_dose"]`. For spinal cord with
volume 40 cc and n=0.05, the formula computes `TD50 × (40)^(−0.05)` which is
physically meaningless.

### Corrected implementation
Change the function to accept `geud_gy` directly:

```python
# radiobiology/ntcp/lkb_probit.py

"""LKB NTCP probit (normal tissue) model using gEUD formalism."""

from __future__ import annotations
import math
import numpy as np
from scipy.stats import norm


def calculate_ntcp_lkb_probit(
    geud_gy: float,
    TD50_gy: float,
    m: float,
) -> float:
    """
    Lyman-Kutcher-Burman NTCP using the probit (normal CDF) link.

    NTCP = Φ(t),  t = (gEUD − TD50) / (m × TD50)

    gEUD is pre-computed with volume parameter a = 1/n (see NTCPCalculator).
    Φ is the standard normal CDF (scipy.stats.norm.cdf).

    Arguments:
        geud_gy  : generalised EUD (Gy) computed with a = 1/n for this organ.
        TD50_gy  : dose (Gy) to whole organ producing 50% complication probability.
        m        : normalised slope of dose-response curve (dimensionless, 0.1–0.3).

    Returns NTCP ∈ (0, 1).

    Reference: Lyman JT. Radiat Res Suppl 1985;8:S13–19.
               Kutcher GJ, Burman C. IJROBP 1989;16:1623–1630.
               Mohan R et al. Med Phys 1992;19:1371–1382.
    """
    if math.isnan(geud_gy) or geud_gy <= 0 or TD50_gy <= 0 or m <= 0:
        return 0.0
    try:
        t    = (geud_gy - TD50_gy) / (m * TD50_gy)
        ntcp = float(norm.cdf(t))
        return float(np.clip(ntcp, 1e-15, 1.0 - 1e-15))
    except (OverflowError, ZeroDivisionError, ValueError):
        return 0.0
```

### Update `config/site_params_ntcp_default.yaml` — add LKB_probit geud_a

Each organ that uses LKB_probit must now have its gEUD `a` value set to `1/n`.
Add `geud_a_probit` fields to YAML organs that have `LKB_probit` entries:

```yaml
# In site_params_ntcp_default.yaml, for each LKB_probit organ:
# geud_a_probit = 1/n (derived from the probit n parameter)
# SpinalCord n=0.05 → a=20.0; Brainstem n=0.05 → a=20.0

HN:
  organs:
    SpinalCord:
      geud_a: 20.0          # for LKB probit: a = 1/n = 1/0.05 = 20.0
      LKB_probit: {TD50_gy: 45.0, m: 0.18, n: 0.05}
      RS: {D50_gy: 45.0, gamma: 2.0, s: 1.0}
    Brainstem:
      geud_a: 20.0
      LKB_probit: {TD50_gy: 53.0, m: 0.18, n: 0.05}
```

### Update `radiobiology/ntcp_calculator.py`

Change the call site for LKB probit to pass `geud` (already computed) instead
of `metrics`:

```python
# ntcp_calculator.py — in NTCPCalculator.compute_all():
# REPLACE:
if organ_params.lkb_probit:
    p = organ_params.lkb_probit
    row["NTCP_LKB_probit"] = calculate_ntcp_lkb_probit(
        metrics,                     # ← WRONG
        float(p["TD50_gy"]),
        float(p["m"]),
        float(p["n"]),
    )

# WITH:
if organ_params.lkb_probit and not math.isnan(geud):
    p = organ_params.lkb_probit
    # gEUD for probit model: use a = 1/n (LKB volume parameter)
    n_lkb = float(p["n"])
    if n_lkb > 0:
        from radiobiology.geud_tcp import compute_geud
        geud_probit = compute_geud(dvh_df, a=1.0 / n_lkb)
    else:
        geud_probit = math.nan
    row["NTCP_LKB_probit"] = calculate_ntcp_lkb_probit(
        geud_probit,
        float(p["TD50_gy"]),
        float(p["m"]),
    )
    row["gEUD_probit_gy"] = geud_probit
```

### Update `tests/test_ntcp_models.py`

Add a probit midpoint test:
```python
def test_lkb_probit_midpoint():
    """At gEUD = TD50, NTCP must be exactly 0.5 (probit midpoint)."""
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    ntcp = calculate_ntcp_lkb_probit(geud_gy=45.0, TD50_gy=45.0, m=0.18)
    assert abs(ntcp - 0.5) < 1e-6, f"Expected NTCP=0.5 at gEUD=TD50, got {ntcp:.6f}"

def test_lkb_probit_increases_with_geud():
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    low  = calculate_ntcp_lkb_probit(30.0, 45.0, 0.18)
    high = calculate_ntcp_lkb_probit(60.0, 45.0, 0.18)
    assert high > low

def test_lkb_probit_below_half_at_sub_td50():
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    ntcp = calculate_ntcp_lkb_probit(35.0, 45.0, 0.18)
    assert ntcp < 0.5
```

Remove the old `test_lkb_probit_increases_with_dose` test that used the wrong
`dose_metrics` dict — it is no longer valid.

---

## FIX 3 / NEW MODULE — BIOLOGICAL DVH (bDVH) `radiobiology/bdvh.py`

### Clinical importance

Every NTCP model in this codebase (LKB loglogit, LKB probit, RS Poisson) operates
on **physical dose bins** from the DVH. This is correct only when
dose-per-fraction ≈ 2 Gy (conventional fractionation). For SBRT/SABR and SRS:

| Treatment          | d/frac | Lung EQD2 (α/β=3) | Physical dose |
|--------------------|--------|-------------------|---------------|
| NSCLC SBRT 54Gy/3f | 18 Gy  | **97 Gy** per frac | 54 Gy         |
| Lung SBRT 48Gy/4f  | 12 Gy  | **72 Gy** per frac | 48 Gy         |
| SRS 18Gy/1f        | 18 Gy  | **97 Gy** per frac | 18 Gy         |

Applying NTCP models without EQD2 correction underestimates toxicity risk by
orders of magnitude for SBRT OARs.

**Formula — EQD2 per voxel (Dale 1985; Jones et al. 2001):**
```
EQD2(Dᵢ, dᵢ) = Dᵢ × (dᵢ + α/β_oar) / (2 + α/β_oar)
```
where:
- Dᵢ = total physical dose at DVH bin i (Gy)
- dᵢ = dose per fraction at bin i = Dᵢ / n_fractions
- α/β_oar = α/β ratio specific to the OAR (not the tumour)
- Factor `2` in denominator = reference dose per fraction (2 Gy)

**Note:** dᵢ = Dᵢ / n_fractions assumes uniform fractionation throughout the
irradiated volume — a valid approximation for most 3DCRT/IMRT plans where
fractionation is constant even though dose varies spatially.

### OAR α/β values (literature consensus)

Add `alpha_beta_gy` to each organ entry in `site_params_ntcp_default.yaml`:

| OAR                | α/β (Gy) | Reference                   |
|--------------------|----------|-----------------------------|
| Spinal cord        | 3.0      | van der Kogel 2009          |
| Brainstem          | 2.0      | Marks et al. 2010 (QUANTEC) |
| Optic nerve/chiasm | 2.0      | Marks et al. 2010           |
| Parotid gland      | 3.0      | Welsh et al. 2013           |
| Submandibular      | 3.0      | Welsh et al. 2013           |
| Lung (pneumonitis) | 3.0      | Marks et al. 2010           |
| Heart              | 3.0      | Gagliardi et al. 2010       |
| Esophagus          | 3.0      | Werner-Wasik et al. 2010    |
| Cochlea            | 3.0      | Bhandare et al. 2010        |
| Hippocampus        | 2.0      | clinical estimate            |
| LAD (coronary)     | 3.0      | van Nimwegen et al.          |

### Code specification

```python
# radiobiology/bdvh.py

"""
Biological DVH (bDVH) — EQD2 correction of the physical DVH per OAR.

Converts each dose bin of a physical differential DVH to its biological
equivalent in 2-Gy fractions using the OAR's α/β ratio.

This correction is mandatory before applying LKB or RS NTCP models when
dose-per-fraction deviates from 2 Gy (i.e. for SBRT, SABR, SRS, and
hypofractionated regimens).

Reference:
  Dale RG. The application of the LQ model to fractionated radiotherapy.
  Br J Radiol 1985;58:515–528.

  Jones B et al. The role of biological effective dose (BED) in clinical
  oncology. Clin Oncol 2001;13:71–81.
"""

from __future__ import annotations
import math
import numpy as np
import pandas as pd

# Default OAR α/β values (Gy) — overridden by per-organ YAML entry.
# All values from QUANTEC 2010 (Marks et al., IJROBP supplement).
DEFAULT_OAR_ALPHA_BETA: dict[str, float] = {
    "SpinalCord":      3.0,
    "Brainstem":       2.0,
    "OpticChiasm":     2.0,
    "OpticNerve_L":    2.0,
    "OpticNerve_R":    2.0,
    "Parotid_L":       3.0,
    "Parotid_R":       3.0,
    "Submandibular_L": 3.0,
    "Submandibular_R": 3.0,
    "LungTotal":       3.0,
    "Lung_L":          3.0,
    "Lung_R":          3.0,
    "Heart":           3.0,
    "Esophagus":       3.0,
    "Cochlea_L":       3.0,
    "Cochlea_R":       3.0,
    "Hippocampus_L":   2.0,
    "Hippocampus_R":   2.0,
    "LAD":             3.0,
    "Lung_Ipsi":       3.0,
}


def compute_eqd2_dvh(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    alpha_beta_oar_gy: float,
) -> pd.DataFrame:
    """
    Convert a physical differential DVH to its EQD2-equivalent DVH.

    For each dose bin Dᵢ (total physical dose at that voxel group):
        dᵢ        = Dᵢ / n_fractions          (dose per fraction at bin i)
        EQD2ᵢ     = Dᵢ × (dᵢ + α/β) / (2 + α/β)

    Volume fractions are unchanged — only the dose axis is transformed.

    Parameters
    ----------
    dvh_df          : DataFrame with columns 'dose_gy' and 'volume_frac'
                      (differential DVH; volume_frac sums to 1.0).
    n_fractions     : number of treatment fractions.
    alpha_beta_oar_gy: OAR-specific α/β ratio (Gy). Use DEFAULT_OAR_ALPHA_BETA
                      if organ-specific value not available.

    Returns
    -------
    DataFrame with same columns but dose_gy replaced by EQD2 values.
    Bins with dose_gy == 0 are passed through unchanged (EQD2 = 0).
    """
    if dvh_df is None or dvh_df.empty:
        return dvh_df
    if n_fractions <= 0 or alpha_beta_oar_gy <= 0:
        raise ValueError(
            f"n_fractions={n_fractions} and alpha_beta_oar_gy={alpha_beta_oar_gy} "
            f"must both be > 0."
        )

    physical_dose = np.asarray(dvh_df["dose_gy"], dtype=float)
    dpf           = physical_dose / n_fractions            # dose per fraction per bin
    eqd2          = physical_dose * (dpf + alpha_beta_oar_gy) / (2.0 + alpha_beta_oar_gy)
    eqd2          = np.where(physical_dose <= 0, 0.0, eqd2)

    result = dvh_df.copy()
    result["dose_gy"] = eqd2
    return result


def get_alpha_beta_for_organ(
    canonical_name: str,
    organ_params_alpha_beta: float | None = None,
) -> float:
    """
    Return OAR α/β (Gy) from NTCP YAML entry or DEFAULT_OAR_ALPHA_BETA lookup.
    Falls back to 3.0 Gy (conservative parallel-organ estimate) if not found.
    """
    if organ_params_alpha_beta is not None and organ_params_alpha_beta > 0:
        return float(organ_params_alpha_beta)
    ab = DEFAULT_OAR_ALPHA_BETA.get(canonical_name)
    if ab is not None:
        return float(ab)
    # Warn and use conservative default
    import logging
    logging.getLogger(__name__).warning(
        "No α/β found for OAR '%s'; using 3.0 Gy (parallel organ default). "
        "Add alpha_beta_gy to site_params_ntcp_default.yaml for this organ.",
        canonical_name,
    )
    return 3.0
```

### Wire bDVH into `NTCPCalculator.compute_all()`

In `radiobiology/ntcp_calculator.py`, add bDVH conversion **before** the NTCP
model calls, and only when `n_fractions > 1` and `dose_per_fraction > 2.5 Gy`
(i.e., non-standard fractionation where correction matters):

```python
# ntcp_calculator.py — add at top:
from radiobiology.bdvh import compute_eqd2_dvh, get_alpha_beta_for_organ

# In NTCPCalculator.compute_all(), after dvh_df is extracted:

n_fractions_plan = int(plan_metadata.get("n_fractions", 1) or 1)
dpf_plan = float(plan_metadata.get("dose_per_fraction_gy", 2.0) or 2.0)

# Apply bDVH correction when dose/fraction deviates from reference 2 Gy.
# Threshold: |dpf - 2| > 0.3 Gy (i.e. not standard 2 Gy fractionation).
bdvh_applied = False
dvh_for_ntcp = dvh_df  # physical by default

if abs(dpf_plan - 2.0) > 0.3 and n_fractions_plan >= 1 and not dvh_df.empty:
    alpha_beta_oar = get_alpha_beta_for_organ(
        canonical,
        organ_params_alpha_beta=getattr(organ_params, "alpha_beta_gy", None),
    )
    dvh_for_ntcp = compute_eqd2_dvh(dvh_df, n_fractions_plan, alpha_beta_oar)
    bdvh_applied = True

# Use dvh_for_ntcp (EQD2-corrected when applicable) for all NTCP model calls.
# Update geud computation to also use dvh_for_ntcp:
geud = compute_geud(dvh_for_ntcp, organ_params.geud_a) if not dvh_for_ntcp.empty else math.nan
metrics = _dvh_metrics(dvh_for_ntcp)

# Add provenance fields to result row:
row["bdvh_applied"] = bdvh_applied
row["n_fractions_plan"] = n_fractions_plan
row["dose_per_fraction_plan_gy"] = dpf_plan
```

### Update `OrganNTCPParams` dataclass to store α/β

In `config/site_ntcp_params.py`:
```python
@dataclass
class OrganNTCPParams:
    canonical: str
    geud_a: float = 3.0
    alpha_beta_gy: float = 3.0    # ← ADD THIS (OAR-specific, for bDVH)
    lkb_loglogit: dict[str, float] | None = None
    lkb_probit: dict[str, float] | None = None
    rs: dict[str, float] | None = None

# In _parse_organ():
def _parse_organ(name: str, raw: dict[str, Any]) -> OrganNTCPParams:
    return OrganNTCPParams(
        canonical=name,
        geud_a=float(raw.get("geud_a", 3.0)),
        alpha_beta_gy=float(raw.get("alpha_beta_gy", 3.0)),  # ← ADD
        lkb_loglogit=raw.get("LKB_loglogit"),
        lkb_probit=raw.get("LKB_probit"),
        rs=raw.get("RS"),
    )
```

### Update `config/site_params_ntcp_default.yaml`

Add `alpha_beta_gy` to **every** organ entry. Example:

```yaml
HN:
  organs:
    Parotid_L:
      geud_a: 3.0
      alpha_beta_gy: 3.0      # Welsh et al. 2013
      LKB_loglogit: {TD50_gy: 28.4, gamma50: 0.6}
      RS: {D50_gy: 28.4, gamma: 1.0, s: 0.25}
    SpinalCord:
      geud_a: 20.0             # a = 1/n = 1/0.05 = 20 for probit
      alpha_beta_gy: 3.0       # van der Kogel 2009
      LKB_probit: {TD50_gy: 45.0, m: 0.18, n: 0.05}
      RS: {D50_gy: 45.0, gamma: 2.0, s: 1.0}
    Brainstem:
      geud_a: 20.0
      alpha_beta_gy: 2.0       # Marks et al. QUANTEC 2010
      LKB_probit: {TD50_gy: 53.0, m: 0.18, n: 0.05}
    # ... etc for all organs across all sites
```

---

## NEW MODULE — uNTCP (NTCP Parameter Uncertainty)
### `uncertainty/ntcp_mc.py`

### Clinical context

Just as TCP carries parameter uncertainty (uTCP — captured in `uncertainty/parameter_mc.py`
for Poisson, ZM, gEUD, Logistic models), NTCP carries analogous uncertainty in its
tissue tolerance parameters (TD50, m, n, γ50, D50). Published CVs for NTCP parameters
(Deasy 1997; Marks et al. 2010) are comparable in magnitude to TCP parameter CVs.

Reporting a point-estimate NTCP without confidence intervals has been criticised in
the QUANTEC literature as potentially misleading clinical guidance.

**Notation distinction** (mandatory — do not confuse):
- **uNTCP** — uncertainty-aware NTCP: MC-sampled CI bands on the NTCP prediction
  (analogous to uTCP for TCP). This is what this module implements.
- **UTCP** — Uncomplicated TCP (Brahme 1984): UTCP = TCP × Π(1 − NTCP_k).
  This is a plan-quality composite metric, not implemented in this module.

### Sampling distributions for NTCP parameters

| Parameter | Distribution | Default CV | Reference |
|-----------|-------------|------------|-----------|
| TD50_gy   | Truncated N (>0) | CV = 0.15 | Deasy 1997 |
| m         | Truncated N (>0) | CV = 0.25 | Deasy 1997 |
| n (LKB)   | Truncated N (>0) | CV = 0.30 | Deasy 1997 |
| gamma50   | Truncated N (>0) | CV = 0.20 | Marks 2010 |
| D50 (RS)  | Truncated N (>0) | CV = 0.15 | Källman 1992 |
| gamma (RS)| Truncated N (>0) | CV = 0.20 | Källman 1992 |
| s (RS)    | Truncated N (>0) | CV = 0.25 | Källman 1992 |

### Code specification

```python
# uncertainty/ntcp_mc.py

"""
uNTCP — Monte Carlo parameter uncertainty for classical NTCP models.

Propagates uncertainty in organ tolerance parameters (TD50, m, n, γ50, D50, s)
through the three NTCP models (LKB loglogit, LKB probit, RS Poisson) to produce
confidence intervals on each model's prediction.

Terminology note:
  uNTCP = uncertainty-aware NTCP (this module).
  UTCP  = Uncomplicated TCP = TCP × Π(1-NTCP_k) (separate concept, Brahme 1984).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class NTCPUncertaintyConfig:
    """
    Coefficient of variation (CV) for each NTCP model parameter.
    Derived from Deasy (1997) and QUANTEC supplement (Marks et al. 2010).
    """
    TD50_cv: float = 0.15         # LKB: tolerance dose CV
    m_cv: float = 0.25            # LKB: probit slope CV
    n_cv: float = 0.30            # LKB: volume parameter CV
    gamma50_cv: float = 0.20      # loglogit: gradient CV
    D50_rs_cv: float = 0.15       # RS: D50 CV
    gamma_rs_cv: float = 0.20     # RS: γ CV
    s_rs_cv: float = 0.25         # RS: seriality parameter CV
    n_samples: int = 1000
    seed: int = 42


def _truncated_normal(mean: float, cv: float, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw n samples from N(mean, (cv×mean)²) truncated at 0."""
    sd = abs(mean) * cv
    if sd <= 0 or mean <= 0:
        return np.full(n, mean)
    a_clip = -mean / sd
    return stats.truncnorm.rvs(a_clip, np.inf, loc=mean, scale=sd, size=n, random_state=rng)


def _agg(arr: np.ndarray) -> dict:
    v = arr[np.isfinite(arr)]
    if len(v) == 0:
        return {'mean': math.nan, 'sd': math.nan, 'p5': math.nan, 'p95': math.nan, 'n_valid': 0}
    return {
        'mean': float(np.mean(v)),
        'sd':   float(np.std(v, ddof=1)),
        'p5':   float(np.percentile(v, 5)),
        'p95':  float(np.percentile(v, 95)),
        'n_valid': int(len(v)),
    }


def run_untcp(
    dvh_df: pd.DataFrame,
    organ_params,           # OrganNTCPParams dataclass
    config: NTCPUncertaintyConfig | None = None,
) -> dict:
    """
    Monte Carlo uNTCP: sample NTCP parameters, compute NTCP distributions.

    For each MC sample:
      - Draw TD50, m, n (for LKB probit/loglogit) from truncated normal
      - Draw D50, gamma, s (for RS Poisson) from truncated normal
      - Compute gEUD with sampled n → compute NTCP_LKB_loglogit, NTCP_LKB_probit, NTCP_RS
      - Collect results

    Returns aggregated statistics (mean, SD, P5, P95) for each model.
    This is uNTCP — NOT the same as UTCP (Uncomplicated TCP).
    """
    from radiobiology.geud_tcp import compute_geud
    from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

    if config is None:
        config = NTCPUncertaintyConfig()

    rng = np.random.default_rng(config.seed)
    n   = config.n_samples

    # Base parameter values
    ll  = organ_params.lkb_loglogit or {}
    pb  = organ_params.lkb_probit or {}
    rs  = organ_params.rs or {}

    TD50_ll  = float(ll.get("TD50_gy",  organ_params.geud_a))
    g50_ll   = float(ll.get("gamma50",  0.5))
    TD50_pb  = float(pb.get("TD50_gy",  0.0))
    m_pb     = float(pb.get("m",        0.18))
    n_pb     = float(pb.get("n",        0.05))
    D50_rs   = float(rs.get("D50_gy",   0.0))
    gamma_rs = float(rs.get("gamma",    1.0))
    s_rs     = float(rs.get("s",        0.25))

    # Sample all parameters once (vectorised)
    TD50_ll_s = _truncated_normal(TD50_ll,  config.TD50_cv,    n, rng) if TD50_ll  > 0 else None
    g50_ll_s  = _truncated_normal(g50_ll,   config.gamma50_cv, n, rng) if g50_ll   > 0 else None
    TD50_pb_s = _truncated_normal(TD50_pb,  config.TD50_cv,    n, rng) if TD50_pb  > 0 else None
    m_pb_s    = _truncated_normal(m_pb,     config.m_cv,       n, rng) if m_pb     > 0 else None
    n_pb_s    = _truncated_normal(n_pb,     config.n_cv,       n, rng) if n_pb     > 0 else None
    D50_rs_s  = _truncated_normal(D50_rs,   config.D50_rs_cv,  n, rng) if D50_rs   > 0 else None
    g_rs_s    = _truncated_normal(gamma_rs, config.gamma_rs_cv,n, rng) if gamma_rs > 0 else None
    s_rs_s    = _truncated_normal(s_rs,     config.s_rs_cv,    n, rng) if s_rs     > 0 else None

    ntcp_ll  = np.full(n, math.nan)
    ntcp_pb  = np.full(n, math.nan)
    ntcp_rs  = np.full(n, math.nan)

    for i in range(n):
        # LKB loglogit
        if TD50_ll_s is not None and g50_ll_s is not None:
            geud_ll = compute_geud(dvh_df, organ_params.geud_a)
            ntcp_ll[i] = calculate_ntcp_lkb_loglogit(geud_ll, TD50_ll_s[i], g50_ll_s[i])

        # LKB probit (sampled n → sampled a = 1/n → sampled gEUD)
        if TD50_pb_s is not None and m_pb_s is not None and n_pb_s is not None:
            n_i = float(n_pb_s[i])
            if n_i > 0:
                geud_pb = compute_geud(dvh_df, a=1.0 / n_i)
                ntcp_pb[i] = calculate_ntcp_lkb_probit(geud_pb, TD50_pb_s[i], m_pb_s[i])

        # RS Poisson
        if D50_rs_s is not None and g_rs_s is not None and s_rs_s is not None:
            try:
                ntcp_rs[i] = calculate_ntcp_rs_poisson(
                    dvh_df, D50_rs_s[i], g_rs_s[i], s_rs_s[i]
                )
            except Exception:
                pass

    return {
        'uNTCP_LKB_loglogit': _agg(ntcp_ll),
        'uNTCP_LKB_probit':   _agg(ntcp_pb),
        'uNTCP_RS':           _agg(ntcp_rs),
        'n_samples':          n,
        'organ':              organ_params.canonical,
        '_note': 'uNTCP = uncertainty-aware NTCP (MC CI). UTCP = Uncomplicated TCP is separate.',
    }
```

### Wire uNTCP into `rbgyanx_engine/pipeline.py`

Add a new function `apply_ntcp_uncertainty()` called after `collect_dicom_ntcp()`:

```python
# pipeline.py — add after collect_dicom_ntcp() call in run_analysis():

def apply_ntcp_uncertainty(
    ntcp_results: list[dict],
    site_key: str,
    user_ntcp_config: Path | None,
    n_mc: int,
) -> None:
    """Phase 3 NTCP: run uNTCP parameter MC in-place on each OAR row."""
    from uncertainty.ntcp_mc import NTCPUncertaintyConfig, run_untcp
    from config.site_ntcp_params import load_site_ntcp_params

    ntcp_site = load_site_ntcp_params(site_key, user_config=user_ntcp_config)
    cfg = NTCPUncertaintyConfig(n_samples=n_mc)

    for r in ntcp_results:
        organ = r.get("structure", "")
        dvh_df = r.get("_dvh_df")
        op = ntcp_site.organs.get(organ)
        if dvh_df is None or op is None:
            continue
        try:
            mc = run_untcp(dvh_df, op, config=cfg)
            r["uNTCP_LKB_loglogit"] = mc["uNTCP_LKB_loglogit"]
            r["uNTCP_LKB_probit"]   = mc["uNTCP_LKB_probit"]
            r["uNTCP_RS"]           = mc["uNTCP_RS"]
        except Exception as exc:
            logger.warning("uNTCP failed for %s/%s: %s", r.get("AnonPatientID"), organ, exc)
```

Also update `run_analysis()` in `engine.py` to call `apply_ntcp_uncertainty()`
after `collect_dicom_ntcp()` when `not cfg.no_uncertainty`.

---

## NEW MODULE — NTCP EXCEL REPORTING

### `outputs/ntcp_reporter.py`

NTCP results currently go to a flat `ntcp_results.csv`.
A formatted Excel workbook is required for clinical reporting.

```python
# outputs/ntcp_reporter.py

"""NTCP benchmarking Excel workbook with OAR-level summary."""

from __future__ import annotations
import pathlib
import pandas as pd


def build_ntcp_table(ntcp_results: list[dict]) -> pd.DataFrame:
    """Flatten NTCP result dicts to a per-patient per-OAR DataFrame."""
    rows = []
    for r in ntcp_results:
        mc_ll  = r.get("uNTCP_LKB_loglogit") or {}
        mc_pb  = r.get("uNTCP_LKB_probit")   or {}
        mc_rs  = r.get("uNTCP_RS")            or {}
        rows.append({
            "AnonPatientID":       r.get("AnonPatientID", ""),
            "Site":                r.get("site", ""),
            "OAR":                 r.get("structure", ""),
            "gEUD_Gy":             r.get("gEUD_gy", float("nan")),
            "Dmax_Gy":             r.get("Dmax_gy", float("nan")),
            "Dmean_Gy":            r.get("Dmean_gy", float("nan")),
            "bDVH_Applied":        r.get("bdvh_applied", False),
            "DPF_plan_Gy":         r.get("dose_per_fraction_plan_gy", float("nan")),
            # Classical NTCP
            "NTCP_LKB_loglogit":   r.get("NTCP_LKB_loglogit", float("nan")),
            "NTCP_LKB_probit":     r.get("NTCP_LKB_probit",   float("nan")),
            "NTCP_RS":             r.get("NTCP_RS",            float("nan")),
            # uNTCP CI bands
            "uNTCP_loglogit_mean": mc_ll.get("mean", float("nan")),
            "uNTCP_loglogit_P5":   mc_ll.get("p5",   float("nan")),
            "uNTCP_loglogit_P95":  mc_ll.get("p95",  float("nan")),
            "uNTCP_probit_mean":   mc_pb.get("mean", float("nan")),
            "uNTCP_probit_P5":     mc_pb.get("p5",   float("nan")),
            "uNTCP_probit_P95":    mc_pb.get("p95",  float("nan")),
            "uNTCP_RS_mean":       mc_rs.get("mean", float("nan")),
            "uNTCP_RS_P5":         mc_rs.get("p5",   float("nan")),
            "uNTCP_RS_P95":        mc_rs.get("p95",  float("nan")),
        })
    return pd.DataFrame(rows)


def save_ntcp_excel(
    ntcp_results: list[dict],
    output_path: str | pathlib.Path,
) -> pathlib.Path:
    """
    Save multi-sheet NTCP benchmarking Excel workbook.

    Sheet 1: NTCP_Summary  — per-patient, per-OAR classical NTCP + uNTCP CI bands
    Sheet 2: bDVH_Flag     — patients where bDVH correction was applied (SBRT/SRS)
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("openpyxl required for NTCP Excel output.") from exc

    ntcp_df = build_ntcp_table(ntcp_results)

    # bDVH flag sheet: highlight cases where EQD2 correction was applied
    bdvh_df = ntcp_df[ntcp_df["bDVH_Applied"] == True][
        ["AnonPatientID", "Site", "OAR", "DPF_plan_Gy",
         "NTCP_LKB_loglogit", "uNTCP_loglogit_mean"]
    ].copy()

    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        ntcp_df.to_excel(writer, sheet_name="NTCP_Summary", index=False)
        bdvh_df.to_excel(writer, sheet_name="bDVH_Corrected", index=False)

        # Auto column width
        for sname in writer.sheets:
            ws = writer.sheets[sname]
            for col in ws.columns:
                max_len = max(
                    (len(str(c.value)) for c in col if c.value is not None), default=10
                )
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)
    return out
```

Wire into `engine.py`: replace `ntcp_df.to_csv(ntcp_csv)` with:
```python
from outputs.ntcp_reporter import save_ntcp_excel
ntcp_xlsx_path = output_dir / "ntcp_benchmarking.xlsx"
save_ntcp_excel(ntcp_results, ntcp_xlsx_path)
result.ntcp_benchmark_xlsx = ntcp_xlsx_path
```
Also add `ntcp_benchmark_xlsx: Path | None = None` to `EngineResult` dataclass.

---

## CLEANUP — Remove empty `src/` stub directories

Delete the following directories and their stub `__init__.py` files.
These are leftover scaffold stubs that add no code and confuse the package layout:

```
src/__init__.py
src/data/__init__.py
src/features/__init__.py
src/metrics/__init__.py
src/models/__init__.py
src/models/machine_learning/__init__.py
src/models/traditional/__init__.py
src/models/uncertainty/__init__.py
src/reporting/__init__.py
src/safety/__init__.py
src/utils/__init__.py
src/validation/__init__.py
src/visualization/__init__.py
```

Remove the entire `src/` directory tree. It is not imported by any module.
Verify with `grep -r "from src" .` before deleting — should return zero matches.

---

## UNIT TESTS TO WRITE OR UPDATE

All tests in `tests/test_ntcp_models.py`:

```python
# NEW TESTS (add to tests/test_ntcp_models.py):

def test_lkb_probit_midpoint_exact():
    """At gEUD = TD50, NTCP must equal 0.5 (probit midpoint, mathematics)."""
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    assert abs(calculate_ntcp_lkb_probit(45.0, 45.0, 0.18) - 0.5) < 1e-6

def test_lkb_probit_below_half_sub_td50():
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    assert calculate_ntcp_lkb_probit(30.0, 45.0, 0.18) < 0.5

def test_lkb_probit_above_half_super_td50():
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    assert calculate_ntcp_lkb_probit(60.0, 45.0, 0.18) > 0.5

def test_bdvh_eqd2_greater_than_physical_for_sbrt():
    """For SBRT (dpf >> 2 Gy), EQD2 must exceed physical dose for all α/β."""
    import pandas as pd
    from radiobiology.bdvh import compute_eqd2_dvh
    dvh = pd.DataFrame({"dose_gy": [18.0, 36.0, 54.0], "volume_frac": [0.4, 0.3, 0.3]})
    bdvh = compute_eqd2_dvh(dvh, n_fractions=3, alpha_beta_oar_gy=3.0)
    # EQD2 for 54Gy/3fr to lung (α/β=3): 54×(18+3)/(2+3) = 54×4.2 = 226.8 Gy? No:
    # EQD2 per bin = D_bin × (D_bin/n + αβ) / (2 + αβ)
    # For D_bin=54, n=3, d=18: EQD2 = 54×(18+3)/(2+3) = 54×4.2 = 226.8 — very high
    # Just verify EQD2 > physical dose for hypofractionated bins
    assert all(bdvh["dose_gy"].values >= dvh["dose_gy"].values), (
        "EQD2 must be >= physical dose when dpf > 2 Gy"
    )

def test_bdvh_identity_at_2gy_per_fraction():
    """At exactly 2 Gy/fraction, EQD2 = physical dose (definition of EQD2)."""
    import pandas as pd
    import numpy as np
    from radiobiology.bdvh import compute_eqd2_dvh
    dvh = pd.DataFrame({"dose_gy": [40.0, 50.0, 60.0], "volume_frac": [1/3]*3})
    bdvh = compute_eqd2_dvh(dvh, n_fractions=25, alpha_beta_oar_gy=3.0)
    # d = 2.0 Gy/frac → EQD2 = D × (2+3)/(2+3) = D × 1 = D
    np.testing.assert_allclose(bdvh["dose_gy"].values, dvh["dose_gy"].values, rtol=1e-6)

def test_untcp_sd_nonzero_for_real_dvh():
    """uNTCP SD must be > 0 when parameter CV > 0."""
    import pandas as pd
    from config.site_ntcp_params import load_site_ntcp_params
    from uncertainty.ntcp_mc import run_untcp, NTCPUncertaintyConfig
    site = load_site_ntcp_params("HN")
    op = site.organs["Parotid_L"]
    dvh = pd.DataFrame({"dose_gy": [20.0, 28.0, 35.0], "volume_frac": [0.3, 0.4, 0.3]})
    result = run_untcp(dvh, op, config=NTCPUncertaintyConfig(n_samples=300, seed=0))
    assert result["uNTCP_LKB_loglogit"]["sd"] > 0
    assert result["uNTCP_LKB_loglogit"]["p5"] < result["uNTCP_LKB_loglogit"]["p95"]

def test_untcp_mean_close_to_deterministic():
    """uNTCP mean must be close to deterministic NTCP (within 0.1 absolute)."""
    import pandas as pd
    from config.site_ntcp_params import load_site_ntcp_params
    from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
    from radiobiology.geud_tcp import compute_geud
    from uncertainty.ntcp_mc import run_untcp, NTCPUncertaintyConfig
    site = load_site_ntcp_params("HN")
    op = site.organs["Parotid_L"]
    dvh = pd.DataFrame({"dose_gy": [28.4], "volume_frac": [1.0]})
    geud = compute_geud(dvh, op.geud_a)
    nominal = calculate_ntcp_lkb_loglogit(geud, 28.4, 0.6)
    mc = run_untcp(dvh, op, config=NTCPUncertaintyConfig(n_samples=500, seed=0))
    assert abs(mc["uNTCP_LKB_loglogit"]["mean"] - nominal) < 0.10

def test_epv_gate_now_enforced_in_pipeline():
    """Verify EPV_MINIMUM (10.0) is used in pipeline, not 1.0."""
    import inspect
    import rbgyanx_engine.pipeline as pl
    src = inspect.getsource(pl.run_ml_xai_validation)
    assert "epv_threshold=1.0" not in src, (
        "CRITICAL: epv_threshold=1.0 found in pipeline — EPV gate is still bypassed."
    )
    assert "EPV_MINIMUM" in src, (
        "EPV_MINIMUM must be imported and used in fit_mvl_tcp call."
    )
```

---

## COMPLETION CHECKLIST

- [ ] `rbgyanx_engine/pipeline.py` — EPV gate uses `EPV_MINIMUM`, not 1.0
- [ ] `radiobiology/ntcp/lkb_probit.py` — signature `(geud_gy, TD50_gy, m)`, uses `norm.cdf(t)`
- [ ] `radiobiology/ntcp_calculator.py` — calls probit with computed `gEUD(a=1/n)`, adds `bdvh_applied` flag
- [ ] `config/site_ntcp_params.py` — `OrganNTCPParams` has `alpha_beta_gy` field
- [ ] `config/site_params_ntcp_default.yaml` — every organ has `alpha_beta_gy` and `geud_a` consistent with LKB probit `n`
- [ ] `radiobiology/bdvh.py` — `compute_eqd2_dvh()`, `get_alpha_beta_for_organ()`
- [ ] `uncertainty/ntcp_mc.py` — `run_untcp()`, `NTCPUncertaintyConfig` dataclass
- [ ] `rbgyanx_engine/pipeline.py` — `apply_ntcp_uncertainty()` called from `run_analysis()` when NTCP + `not cfg.no_uncertainty`
- [ ] `rbgyanx_engine/engine.py` — `EngineResult.ntcp_benchmark_xlsx` field; call `save_ntcp_excel()`
- [ ] `outputs/ntcp_reporter.py` — `build_ntcp_table()`, `save_ntcp_excel()`
- [ ] `outputs/__init__.py` — export `build_ntcp_table`, `save_ntcp_excel`
- [ ] `src/` directory tree — deleted entirely after confirming zero imports
- [ ] `tests/test_ntcp_models.py` — 7 new tests pass; old wrong probit test removed
- [ ] `pytest tests/` — all tests pass (no collection errors, no failures)

**Do NOT proceed to the ENHANCE prompt until all checklist items are complete
and `pytest tests/ -v` exits green.**
