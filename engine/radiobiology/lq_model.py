"""Linear-quadratic model, USC extension, BED, and EQD2."""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


def survival_fraction_lq(dose_gy: float, alpha: float, beta: float) -> float:
    """LQ survival fraction for a single fraction: SF = exp(-α·d - β·d²)."""
    if dose_gy <= 0:
        return 1.0
    try:
        return float(math.exp(-alpha * dose_gy - beta * dose_gy**2))
    except (OverflowError, ValueError):
        logger.warning("survival_fraction_lq overflow at dose=%s", dose_gy)
        return math.nan


def survival_fraction_usc(
    dose_gy: float,
    alpha: float,
    beta: float,
    d_transition_gy: float = 10.0,
) -> float:
    """Universal Survival Curve survival fraction for a single fraction."""
    if dose_gy <= 0:
        return 1.0
    if dose_gy <= d_transition_gy:
        return survival_fraction_lq(dose_gy, alpha, beta)
    try:
        exponent = -dose_gy * (alpha + 2 * beta * d_transition_gy) + beta * d_transition_gy**2
        return float(math.exp(exponent))
    except (OverflowError, ValueError):
        logger.warning("survival_fraction_usc overflow at dose=%s", dose_gy)
        return math.nan


def survival_fraction(
    dose_gy: float,
    alpha: float,
    beta: float,
    d_transition_gy: float = 10.0,
    use_usc: bool = False,
) -> float:
    """Choose LQ or USC survival fraction."""
    if use_usc:
        return survival_fraction_usc(dose_gy, alpha, beta, d_transition_gy)
    return survival_fraction_lq(dose_gy, alpha, beta)


def bed(total_dose_gy: float, dose_per_fraction_gy: float, alpha_beta_gy: float) -> float:
    """Biological Effective Dose: BED = D · (1 + d / (α/β))."""
    if total_dose_gy <= 0 or dose_per_fraction_gy <= 0 or alpha_beta_gy <= 0:
        return math.nan
    return total_dose_gy * (1.0 + dose_per_fraction_gy / alpha_beta_gy)


def eqd2(
    total_dose_gy: float, dose_per_fraction_gy: float, alpha_beta_gy: float
) -> float:
    """Equivalent dose in 2-Gy fractions: EQD2 = D · (d + α/β) / (2 + α/β)."""
    if total_dose_gy <= 0 or dose_per_fraction_gy < 0 or alpha_beta_gy <= 0:
        return math.nan
    return total_dose_gy * (dose_per_fraction_gy + alpha_beta_gy) / (2.0 + alpha_beta_gy)


def eqd2_usc(
    total_dose_gy: float,
    dose_per_fraction_gy: float,
    alpha_beta_gy: float,
    d_transition_gy: float = 10.0,
    alpha_ref: float = 0.30,
) -> float:
    """
    EQD2 derived from the Universal Survival Curve (USC) for high dose-per-fraction.

    alpha_ref is the reference alpha (Gy⁻¹) for USC EQD2 normalisation (default 0.30 Gy⁻¹,
    typical for epithelial tumours with alpha/beta ≈ 10 Gy). Pass tissue-specific alpha for OARs.
    """
    if total_dose_gy <= 0 or dose_per_fraction_gy <= 0 or alpha_beta_gy <= 0:
        return math.nan
    beta_ref = alpha_ref / alpha_beta_gy
    n_fractions = total_dose_gy / dose_per_fraction_gy
    use_usc = dose_per_fraction_gy > d_transition_gy
    sf = survival_fraction(
        dose_per_fraction_gy,
        alpha_ref,
        beta_ref,
        d_transition_gy=d_transition_gy,
        use_usc=use_usc,
    )
    if sf <= 0 or math.isnan(sf):
        return math.nan
    total_bed_usc = -n_fractions * math.log(sf) / alpha_ref
    return total_bed_usc / (1.0 + 2.0 / alpha_beta_gy)


def treatment_time_days(
    n_fractions: int, fractions_per_week: float = 5.0
) -> float:
    """Estimate calendar treatment time in days."""
    if n_fractions <= 1:
        return 1.0
    if fractions_per_week <= 0:
        return math.nan
    # Elapsed weeks × 7 days/week plus one buffer day (prompt specification).
    return (n_fractions - 1) / fractions_per_week * 7.0 + 7.0 / fractions_per_week
