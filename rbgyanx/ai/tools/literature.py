"""
Literature quick-compare: two tiers, and a gate on the way out.

The problem this solves is not "can the model recall QUANTEC". It is that a recalled number and
a checked number look identical once they are in the same table, and a table is the thing that
gets pasted into a QA document six months later. So provenance is a property of every row, it is
always rendered, and it survives export.

The tiers
---------
SHIPPED_REFERENCE  Computed from a versioned pack in ``rbgyanx/ai/reference_packs/``. The
                   comparison is arithmetic - ``observed`` against ``value`` under
                   ``comparator`` - so it is reproducible with no model in the loop at all.
                   Carries a real citation and the pack version.

MODEL_RECALL       The model said so. Marked unverified, and any DOI or citation is replaced
                   with "unverified - resolve before citing" rather than rendered as a clean
                   reference. A plausible-looking citation is worse than none.

WEB_RETRIEVED      Fetched at run time. Treated as unverified for export purposes: retrieval
                   proves a page said it, not that the page is right.

The export gate
---------------
Any export carrying an unverified row gets :data:`ORIENTATION_NOTICE` prepended, and the rows
stay marked inside the artefact. Asking to export unverified rows *without* the provenance
column is refused outright - that is the one operation that would turn recalled content into
something indistinguishable from checked content, which is precisely what this module exists to
prevent.

Nothing here computes a TCP or NTCP value. It compares numbers the engine already produced
against numbers a pack already contains.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path

from rbgyanx.ai.capability import Capability
from rbgyanx.ai.tools.registry import Tool, ToolContext, ToolResult, register

__all__ = [
    "Provenance",
    "ReferenceEntry",
    "ReferencePack",
    "ComparisonRow",
    "ExportRefused",
    "ORIENTATION_NOTICE",
    "UNVERIFIED_CITATION",
    "packs_dir",
    "load_pack",
    "load_all_packs",
    "compare_against_pack",
    "render_table",
    "export",
    "literature_compare",
]


#: Shown to the user, and prepended to any export carrying an unverified row. Verbatim.
ORIENTATION_NOTICE = (
    "Quick orientation only. Values marked unverified come from model recall, not a checked "
    "source. Any comparison intended for publication, QA documentation or clinical use must be "
    "performed and verified by a human against primary literature."
)

#: What a recalled citation renders as. Never a DOI, never anything resolvable-looking.
UNVERIFIED_CITATION = "unverified - resolve before citing"


class ExportRefused(RuntimeError):
    """Raised when an export would strip provenance from unverified rows."""


class Provenance(str, Enum):
    SHIPPED_REFERENCE = "SHIPPED_REFERENCE"
    MODEL_RECALL = "MODEL_RECALL"
    WEB_RETRIEVED = "WEB_RETRIEVED"

    @property
    def verified(self) -> bool:
        """Only a shipped pack is verified. Retrieval is not verification."""
        return self is Provenance.SHIPPED_REFERENCE


@dataclass(frozen=True)
class ReferenceEntry:
    organ: str
    endpoint: str
    metric: str
    comparator: str
    value: float
    units: str
    citation: str
    risk_pct: float | None = None
    site: str | None = None


@dataclass(frozen=True)
class ReferencePack:
    pack_id: str
    pack_version: str
    title: str
    entries: tuple[ReferenceEntry, ...]
    description: str = ""
    applicability: str = ""

    def find(self, organ: str, metric: str | None = None) -> list[ReferenceEntry]:
        """Entries for an organ, matched loosely enough to survive naming differences.

        "Parotid_L" has to find "Parotid (single gland)": either key may be the longer one, so
        the match is symmetric rather than a one-way prefix test.
        """
        organ_key = _key(organ)
        matches = []
        for entry in self.entries:
            entry_key = _key(entry.organ)
            if not (entry_key.startswith(organ_key) or organ_key.startswith(entry_key)):
                continue
            if metric is not None and _key(entry.metric) != _key(metric):
                continue
            matches.append(entry)
        return matches


@dataclass(frozen=True)
class ComparisonRow:
    """One row. ``provenance`` is not optional and is always rendered."""

    organ: str
    endpoint: str
    metric: str
    observed: float | None
    reference: float | None
    units: str
    verdict: str
    provenance: Provenance
    citation: str
    pack_id: str = ""
    pack_version: str = ""

    @property
    def unverified(self) -> bool:
        return not self.provenance.verified

    def display_citation(self) -> str:
        """A recalled citation is never rendered as a resolvable reference."""
        if self.unverified:
            return UNVERIFIED_CITATION
        suffix = f" [{self.pack_id} v{self.pack_version}]" if self.pack_id else ""
        return f"{self.citation}{suffix}"


def _key(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


# --------------------------------------------------------------------------- packs


def packs_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "reference_packs"


def _entry_from(raw: dict) -> ReferenceEntry:
    return ReferenceEntry(
        organ=str(raw.get("organ", "")),
        endpoint=str(raw.get("endpoint", "")),
        metric=str(raw.get("metric", "")),
        comparator=str(raw.get("comparator", "=")),
        value=float(raw["value"]),
        units=str(raw.get("units", "")),
        citation=str(raw.get("citation", "")),
        risk_pct=None if raw.get("risk_pct") is None else float(raw["risk_pct"]),
        site=raw.get("site"),
    )


def load_pack(path: Path) -> ReferencePack:
    """Load one versioned JSON pack. A site can drop its own file into the packs directory."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    for field in ("pack_id", "pack_version", "entries"):
        if field not in raw:
            raise ValueError(f"{path.name} is not a reference pack: missing {field!r}")
    return ReferencePack(
        pack_id=str(raw["pack_id"]),
        pack_version=str(raw["pack_version"]),
        title=str(raw.get("title", raw["pack_id"])),
        description=str(raw.get("description", "")),
        applicability=str(raw.get("applicability", "")),
        entries=tuple(_entry_from(e) for e in raw["entries"]),
    )


@lru_cache(maxsize=1)
def _cached_packs() -> tuple[ReferencePack, ...]:
    return tuple(
        load_pack(p) for p in sorted(packs_dir().glob("*.json")) if not p.name.startswith("_")
    )


def load_all_packs(directory: Path | None = None) -> list[ReferencePack]:
    """Every pack available, shipped or site-supplied.

    rbGyanX is installed in many countries and under many protocols; asserting one institution's
    tolerances as universal would be wrong, so packs are additive and a site can ship its own.
    """
    if directory is None:
        return list(_cached_packs())
    return [
        load_pack(p) for p in sorted(Path(directory).glob("*.json")) if not p.name.startswith("_")
    ]


# --------------------------------------------------------------------------- comparing


def _verdict(observed: float, comparator: str, reference: float) -> str:
    """Pure arithmetic. No model is consulted, so the result is reproducible."""
    if comparator in ("<", "<="):
        ok = observed < reference if comparator == "<" else observed <= reference
        return "within" if ok else "exceeds"
    if comparator in (">", ">="):
        ok = observed > reference if comparator == ">" else observed >= reference
        return "within" if ok else "below"
    if comparator == "=":
        return "matches" if abs(observed - reference) < 1e-9 else "differs"
    return "not comparable"


def compare_against_pack(
    observed: dict[str, float],
    pack: ReferencePack,
    *,
    organ: str,
) -> list[ComparisonRow]:
    """Compare observed metrics for one organ against a pack, arithmetically.

    ``observed`` maps metric name (``Dmean``, ``V20``) to value. Every returned row is
    SHIPPED_REFERENCE, because every one of them was computed here rather than recalled.
    """
    rows: list[ComparisonRow] = []
    for metric, value in observed.items():
        for entry in pack.find(organ, metric):
            rows.append(
                ComparisonRow(
                    organ=entry.organ,
                    endpoint=entry.endpoint,
                    metric=entry.metric,
                    observed=float(value),
                    reference=entry.value,
                    units=entry.units,
                    verdict=_verdict(float(value), entry.comparator, entry.value),
                    provenance=Provenance.SHIPPED_REFERENCE,
                    citation=entry.citation,
                    pack_id=pack.pack_id,
                    pack_version=pack.pack_version,
                )
            )
    return rows


# --------------------------------------------------------------------------- rendering


_COLUMNS = (
    "organ",
    "endpoint",
    "metric",
    "observed",
    "reference",
    "units",
    "verdict",
    "provenance",
    "source",
)


def _cells(row: ComparisonRow) -> list[str]:
    def _num(value):
        return "-" if value is None else f"{value:g}"

    provenance = row.provenance.value + (" (unverified)" if row.unverified else "")
    return [
        row.organ,
        row.endpoint,
        row.metric,
        _num(row.observed),
        _num(row.reference),
        row.units,
        row.verdict,
        provenance,
        row.display_citation(),
    ]


def render_table(rows: list[ComparisonRow]) -> str:
    """Markdown table. The provenance column is not optional and is never dropped."""
    if not rows:
        return "(no comparable reference entries)"
    header = "| " + " | ".join(c.capitalize() for c in _COLUMNS) + " |"
    rule = "|" + "|".join("---" for _ in _COLUMNS) + "|"
    body = ["| " + " | ".join(_cells(r)) + " |" for r in rows]
    return "\n".join([header, rule, *body])


def export(
    rows: list[ComparisonRow],
    *,
    fmt: str = "markdown",
    include_provenance: bool = True,
) -> str:
    """Render rows for export, prepending the orientation notice when any row is unverified.

    Refuses to drop the provenance column while unverified rows are present: that single
    operation is what would let someone produce a clean-looking table out of recalled content
    by accident, which is the thing this gate exists to stop.
    """
    unverified = [r for r in rows if r.unverified]

    if unverified and not include_provenance:
        raise ExportRefused(
            f"refusing to export {len(unverified)} unverified row(s) without the provenance "
            "column: an unmarked table cannot be told apart from a checked one. Either keep "
            "the provenance column, or remove the unverified rows first."
        )

    if fmt == "csv":
        keep = [c for c in _COLUMNS if include_provenance or c != "provenance"]
        lines = [",".join(keep)]
        for row in rows:
            cells = [cell for cell, name in zip(_cells(row), _COLUMNS, strict=True) if name in keep]
            lines.append(",".join('"' + cell.replace('"', '""') + '"' for cell in cells))
        body = "\n".join(lines)
    elif fmt == "markdown":
        body = render_table(rows)
    else:
        raise ValueError(f"unknown export format {fmt!r}")

    # The notice is a comment in both formats, so it survives a paste into either without
    # having to be re-added by hand - and so it cannot be lost by choosing the other format.
    if unverified:
        return "# " + ORIENTATION_NOTICE + "\n\n" + body
    return body


# --------------------------------------------------------------------------- the tool


def literature_compare(
    ctx: ToolContext,
    *,
    organ: str,
    observed: dict[str, float],
    model_rows: list[ComparisonRow] | None = None,
) -> ToolResult:
    """Compare observed metrics against every available pack.

    ``model_rows`` lets a caller add MODEL_RECALL rows alongside. They are kept, marked, and
    never allowed to lose their marking - mixing tiers is permitted, hiding the mix is not.
    """
    rows: list[ComparisonRow] = []
    for pack in load_all_packs():
        rows.extend(compare_against_pack(observed, pack, organ=organ))
    rows.extend(model_rows or [])

    unverified = sum(1 for r in rows if r.unverified)
    table = render_table(rows)
    notice = ORIENTATION_NOTICE if unverified else ""

    return ToolResult(
        ok=True,
        tool="literature_compare",
        capability=Capability.LITERATURE_COMPARE.value,
        output=(notice + "\n\n" + table) if notice else table,
        reason=notice,
        metadata={
            "organ": organ,
            "rows": len(rows),
            "unverified_rows": unverified,
            "packs": [p.pack_id for p in load_all_packs()],
        },
    )


register(
    Tool(
        name="literature_compare",
        capability=Capability.LITERATURE_COMPARE,
        func=literature_compare,
        description=(
            "Compare observed dose metrics against versioned reference packs. Shipped-pack rows "
            "are arithmetic; recalled rows are marked unverified and stay marked on export."
        ),
    )
)
