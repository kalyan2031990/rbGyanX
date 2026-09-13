"""
Generic clinical-cohort CSV loader (site-/endpoint-agnostic).

Any user runs the benchmark on *their* data by supplying a plain CSV with:

  - a patient-id column (default ``patient_id``) — non-null and unique;
  - one binary endpoint column (values in {0, 1} / {True, False} / {"yes","no"}),
    named by the caller (e.g. ``locoregional``, ``rectal_gi``, ``xerostomia_g2``);
  - any number of optional covariate columns (age, sex, stage, …).

No dataset names are hardcoded. Validation is strict and errors are actionable so a
malformed file fails fast with a clear message rather than a silent wrong result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# Accepted string spellings for a binary endpoint (lowercased).
_TRUE_TOKENS = {"1", "1.0", "true", "yes", "y", "pos", "positive", "event"}
_FALSE_TOKENS = {"0", "0.0", "false", "no", "n", "neg", "negative", "censored"}


@dataclass
class ClinicalCohort:
    """A validated cohort table plus a small summary."""

    df: pd.DataFrame
    id_col: str
    endpoint: str
    covariates: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(len(self.df))

    @property
    def n_events(self) -> int:
        return int(self.df[self.endpoint].sum())

    @property
    def event_rate(self) -> float:
        return float(self.df[self.endpoint].mean()) if self.n else float("nan")


def _coerce_binary(series: pd.Series, endpoint: str) -> pd.Series:
    """Map an endpoint column to strict {0, 1} ints; raise on anything ambiguous."""
    out: list[int] = []
    bad: set[str] = set()
    for v in series:
        if pd.isna(v):
            out.append(-1)  # placeholder; NaN rows are dropped by the caller
            continue
        token = str(v).strip().lower()
        if token in _TRUE_TOKENS:
            out.append(1)
        elif token in _FALSE_TOKENS:
            out.append(0)
        else:
            bad.add(str(v))
            out.append(-2)
    if bad:
        raise ValueError(
            f"endpoint {endpoint!r} has non-binary values {sorted(bad)[:8]}; "
            "expected 0/1 (or yes/no, true/false)"
        )
    return pd.Series(out, index=series.index, dtype=int)


def load_clinical_csv(
    path: str | Path,
    *,
    endpoint: str,
    covariate_cols: list[str] | None = None,
    id_col: str = "patient_id",
    drop_missing_endpoint: bool = True,
) -> ClinicalCohort:
    """Load and validate a generic clinical-cohort CSV.

    Parameters
    ----------
    path : CSV file with a header row.
    endpoint : name of the binary outcome column (0/1).
    covariate_cols : optional covariate column names that must all be present.
    id_col : patient-id column name (must be present, non-null, unique).
    drop_missing_endpoint : drop rows whose endpoint is blank/NaN (default True);
        if False, a missing endpoint is an error.

    Raises
    ------
    FileNotFoundError, ValueError with an actionable message.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"clinical CSV not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"clinical CSV {path} has no rows")

    if id_col not in df.columns:
        raise ValueError(f"missing id column {id_col!r}; columns present: {list(df.columns)[:12]}")
    if endpoint not in df.columns:
        raise ValueError(
            f"missing endpoint column {endpoint!r}; columns present: {list(df.columns)[:12]}"
        )

    covariates = list(covariate_cols or [])
    missing_cov = [c for c in covariates if c not in df.columns]
    if missing_cov:
        raise ValueError(f"missing covariate columns: {missing_cov}")

    # Patient id: non-null and unique.
    if df[id_col].isna().any():
        raise ValueError(f"{id_col!r} has blank values")
    dupes = df[id_col][df[id_col].duplicated()].unique()
    if len(dupes):
        raise ValueError(f"{id_col!r} not unique; duplicates: {list(dupes)[:8]}")

    # Endpoint: coerce to strict binary, then optionally drop missing rows.
    coded = _coerce_binary(df[endpoint], endpoint)
    keep = coded != -1
    if (~keep).any():
        if not drop_missing_endpoint:
            raise ValueError(f"endpoint {endpoint!r} has blank values in {int((~keep).sum())} rows")
        df = df.loc[keep].reset_index(drop=True)
        coded = coded.loc[keep].reset_index(drop=True)

    out = df.copy()
    out[endpoint] = coded.to_numpy()
    if out.empty:
        raise ValueError(f"no rows left after dropping missing {endpoint!r}")
    if out[endpoint].nunique() < 2:
        raise ValueError(
            f"endpoint {endpoint!r} is constant (all {int(out[endpoint].iloc[0])}); "
            "need both classes for a benchmark"
        )

    return ClinicalCohort(df=out, id_col=id_col, endpoint=endpoint, covariates=covariates)
