"""
Context builder for the AI panel (v2 Phase 5 · Slice A).

Turns a completed run into a compact, **aggregate** text summary the assistant can reason over —
model names, NTCP/TCP values, cohort counts, dose statistics. By default it includes **no
per-patient identifiers**: it is an allow-list builder, so the panel cannot accidentally forward
a ``patient_id`` or a DVH file's contents.

``include_patient_level=True`` is available because the owner's policy permits real data on the
user's initiative (see ``docs/PHASE5_AI_PANEL_DESIGN.md``); even then it emits only labels the
run already surfaces, and the PHI guard still runs on the final text.
"""

from __future__ import annotations

from statistics import mean

__all__ = ["summarise_run", "build_system_prompt"]

SYSTEM_PROMPT = (
    "You are an assistant embedded in rbGyanX, a radiobiology decision-SUPPORT tool used in "
    "ADVANCED research mode. You EXPLAIN model outputs (NTCP/TCP, LKB/relative-seriality "
    "parameters, AUCs, cohort flow) and help draft QA notes and code. You do NOT give clinical "
    "recommendations, rankings, or per-patient advice, and you never claim to make decisions. "
    "State uncertainty plainly and defer to the treating team for any clinical judgement."
)


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def _fmt(x: float) -> str:
    return f"{x:.3g}" if x == x else "n/a"  # x != x catches NaN


def summarise_run(result, *, include_patient_level: bool = False, max_structures: int = 12) -> str:
    """Aggregate text summary of a run for the assistant.

    ``result`` is a ``rbgyanx.services.run_controller.RunResult`` (duck-typed: needs
    ``structures`` with ``label``/``mean_dose_gy``/``ntcp`` and ``n_files``). Returns "" when
    there is nothing to summarise.
    """
    if result is None or not getattr(result, "structures", None):
        return ""

    structures = list(result.structures)
    n = getattr(result, "n_files", len(structures))
    doses = [s.mean_dose_gy for s in structures if s.mean_dose_gy == s.mean_dose_gy]
    lines = [
        "Run summary (aggregate):",
        f"- structures analysed: {len(structures)} from {n} file(s)",
    ]
    if doses:
        lines.append(
            f"- mean dose across structures: {_fmt(mean(doses))} Gy "
            f"(min {_fmt(min(doses))}, max {_fmt(max(doses))})"
        )

    # Which NTCP models ran, and their value ranges — model-level, not patient-level.
    model_names: list[str] = []
    for s in structures:
        for k in getattr(s, "ntcp", {}) or {}:
            if k not in model_names:
                model_names.append(k)
    if model_names:
        lines.append(f"- NTCP models: {', '.join(model_names)}")
        for mname in model_names:
            vals = [
                s.ntcp[mname]
                for s in structures
                if getattr(s, "ntcp", None) and mname in s.ntcp and s.ntcp[mname] == s.ntcp[mname]
            ]
            if vals:
                lines.append(
                    f"  · {mname}: NTCP {_fmt(min(vals))}–{_fmt(max(vals))} "
                    f"(mean {_fmt(mean(vals))}), n={len(vals)}"
                )

    if include_patient_level:
        lines.append("Per-structure (labels as shown in the run):")
        for s in structures[:max_structures]:
            lines.append(f"  · {s.label}: mean dose {_fmt(s.mean_dose_gy)} Gy")

    return "\n".join(lines)
