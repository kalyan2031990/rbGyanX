"""Reading an NTCP value off a result row without assuming which model produced it.

Until v1.5.0 every organ carried an ``LKB_loglogit`` block, so any consumer could read
``NTCP_LKB_loglogit`` and be sure of a number. The sourced-parameter review ended that: an organ
whose unsourced log-logistic block was replaced by a published probit fit has
``NTCP_LKB_loglogit`` = NaN, and the organs are now split between the two forms. At the
head-and-neck site, for example, four of the eight OARs that enter P+ carry only a probit fit and
four only a log-logistic one, so **no single column can score the whole set**.

A consumer that reads one fixed column therefore gets NaN for part of its input. Depending on what
it then does, that is either a refusal (correct), a silently shortened ranking (wrong), or a metric
computed on NaN (wrong). This module gives every consumer one way to ask "what is this organ's
NTCP, and which model gave it", so the answer is complete and the model is visible.
"""

from __future__ import annotations

import math

#: The model columns an NTCP row may carry, in the order they are preferred when the caller does
#: not ask for one. The probit form comes first because it is the form most of the shipped
#: parameters were transcribed into from their published fits; relative seriality comes last
#: because the shipped RS blocks are the ones still lacking a source.
NTCP_MODEL_ORDER = ("LKB_probit", "LKB_loglogit", "RS")

#: Written on a UTCP row when the product drew on more than one NTCP model.
UTCP_MIXED_NTCP_MODELS = "UTCP_MIXED_NTCP_MODELS"


def select_ntcp(row: dict, preferred: str | None = None) -> tuple[float, str]:
    """This row's NTCP and the model that produced it.

    ``preferred`` is tried first, by its short name (``"LKB_probit"``, ``"LKB_loglogit"``,
    ``"RS"``) or its column name (``"NTCP_LKB_probit"``). The remaining models are then tried in
    :data:`NTCP_MODEL_ORDER`. Returns ``(nan, "")`` when the row carries no finite NTCP at all,
    which is a real answer: the organ was not scored.
    """
    order: list[str] = []
    if preferred:
        short = str(preferred)
        if short.startswith("NTCP_"):
            short = short[len("NTCP_") :]
        if short in NTCP_MODEL_ORDER:
            order.append(short)
    order.extend(m for m in NTCP_MODEL_ORDER if m not in order)

    for model in order:
        value = row.get(f"NTCP_{model}")
        if isinstance(value, (int, float)) and not math.isnan(float(value)):
            return float(value), model
    return math.nan, ""


def ntcp_series(rows: list[dict], preferred: str | None = None) -> list[tuple[dict, float, str]]:
    """``(row, ntcp, model)`` for every row, so a ranking cannot silently drop a model."""
    return [(row, *select_ntcp(row, preferred)) for row in rows]
