"""
Headless run controller (v2 Phase 4 · Slice 3).

Drives a DVH-text run end-to-end without importing a GUI toolkit: validate the request, read
the DVHs through the canonical engine reader, compute the classical models, and report progress
through a :class:`~rbgyanx.services.progress.ProgressReporter`.

Both the Tkinter app and the Qt app can call this; tests call it directly. The scientific
computation is delegated to the validated engine — nothing is reimplemented here, so classical
numerics stay byte-identical.

PHI: results are held in memory and returned to the caller. Nothing is written to disk unless
the caller asks, and no identifier ever leaves the process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rbgyanx.services.progress import NullReporter, ProgressReporter
from rbgyanx.services.run_request import RunRequest, validate_run_request

__all__ = ["StructureResult", "RunResult", "RunController"]


def _cumulative_curve(diff: Any) -> tuple[list[float], list[float]]:
    """Differential DVH frame -> (dose_gy, cumulative volume %) for display.

    One implementation, shared by the DVH-text reader and the engine adapter, so the DVH view's
    contract cannot drift between the two run paths.
    """
    if diff is None or getattr(diff, "empty", True):
        return [], []
    cols = getattr(diff, "columns", [])
    if "dose_gy" not in cols or "volume_frac" not in cols:
        return [], []

    import numpy as np

    d = diff["dose_gy"].to_numpy(dtype=float)
    v = diff["volume_frac"].to_numpy(dtype=float)
    cum = np.cumsum(v[::-1])[::-1]
    if len(cum) and cum[0] > 0:
        cum = cum / cum[0] * 100.0
    return list(d), list(cum)


def _as_float(value: Any) -> float:
    """Engine rows carry numbers, ``None`` and occasionally ``nan``; absent means nan, not zero."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _models_from_row(row: dict, prefix: str) -> dict[str, float]:
    """Pull ``{model: value}`` out of an engine row for keys like ``TCP_gEUD``/``NTCP_RS``.

    Read off the row rather than against a hard-coded model list: the engine owns which models it
    computed, and a list here would silently drop a new one.
    """
    out: dict[str, float] = {}
    for key, value in row.items():
        if not key.startswith(prefix) or key in (f"{prefix}mean", f"{prefix}range"):
            continue
        try:
            out[key[len(prefix):]] = float(value)
        except (TypeError, ValueError):
            continue
    return out


@dataclass
class StructureResult:
    """Per-structure outcome of a run."""

    label: str
    patient_id: str
    dose_gy: list[float] = field(default_factory=list)
    volume_pct: list[float] = field(default_factory=list)
    mean_dose_gy: float = float("nan")
    volume_cc: float = float("nan")
    ntcp: dict[str, float] = field(default_factory=dict)
    source_file: str = ""
    is_target: bool = False  # PTV/CTV/GTV/ITV/BOOST — NTCP is not applicable
    target_type: str = ""  # the canonical target class, when is_target
    # Target control probability, by model name, as the engine computed it. Mirrors ``ntcp``:
    # empty for an OAR, exactly as ``ntcp`` is empty for a target. Only ``run_engine`` fills
    # this; ``run_dvh_text`` computes no TCP and leaves it empty rather than implying one.
    tcp: dict[str, float] = field(default_factory=dict)


@dataclass
class RunResult:
    """Everything a view needs to render a completed run."""

    ok: bool
    structures: list[StructureResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    n_files: int = 0

    @property
    def summary(self) -> str:
        if not self.ok:
            return f"Run failed ({len(self.errors)} error(s))"
        return f"{len(self.structures)} structure(s) from {self.n_files} file(s)"


class RunController:
    """UI-independent orchestration of a DVH-text run."""

    def __init__(self, reporter: ProgressReporter | None = None) -> None:
        self.reporter: ProgressReporter = reporter or NullReporter()

    # ---------------------------------------------------------------- public API

    def validate(self, request: RunRequest):
        """Pre-flight the request (shared rule set)."""
        return validate_run_request(request)

    def run_dvh_text(
        self,
        request: RunRequest,
        *,
        ntcp_models: dict[str, dict[str, Any]] | None = None,
    ) -> RunResult:
        """Parse every DVH in the input folder and compute the classical NTCP models.

        ``ntcp_models`` maps a display name to ``{"model": ..., "params": {...}}`` using the
        engine's model names (``lkb_probit``, ``lkb_loglogit``, ``rs_poisson``).
        """
        rep = self.reporter
        validation = self.validate(request)
        if not validation.ok:
            rep.status("Validation failed")
            for e in validation.errors:
                rep.log(f"[X] {e}")
            return RunResult(ok=False, errors=list(validation.errors))

        req = request.normalised()
        rep.status("Scanning input folder")
        rep.progress(0.0)

        try:
            files = self._list_dvh_files(req.input_path)
        except FileNotFoundError as exc:
            rep.log(f"[X] {exc}")
            return RunResult(ok=False, errors=[str(exc)])

        rep.log(f"Found {len(files)} DVH file(s)")
        results: list[StructureResult] = []
        errors: list[str] = []

        for i, path in enumerate(files, start=1):
            rep.status(f"Reading {i}/{len(files)}")
            try:
                results.append(self._read_one(path, ntcp_models or {}))
                rep.log(f"[OK] {path.name}")
            except Exception as exc:  # one bad file must not sink the run
                msg = f"{path.name}: {exc}"
                errors.append(msg)
                rep.log(f"[!] {msg}")
            rep.progress(i / max(len(files), 1))

        rep.status("Done")
        rep.progress(1.0)
        return RunResult(ok=bool(results), structures=results, errors=errors, n_files=len(files))

    # Engine endpoint names, from the analysis-mode labels the GUIs show.
    _ENDPOINTS = {"TCP": "tcp", "NTCP": "ntcp", "BOTH": "both"}

    def run_engine(self, request: RunRequest) -> RunResult:
        """Run the full engine — DICOM or TPS text, TCP and/or NTCP — and adapt the result.

        This is the path the Tkinter app has always used (``rbgyanx_gui.py`` calls
        ``run_engine_analysis`` directly). ``run_dvh_text`` reads DVH text and computes classical
        NTCP only, so a Qt run routed through it ignored the operator's analysis mode, cancer
        site, input source, clinical file and ML toggle, and wrote nothing to the output folder
        it insisted on. Same bridge for both GUIs, so there is one implementation to trust.
        """
        rep = self.reporter
        validation = self.validate(request)
        if not validation.ok:
            rep.status("Validation failed")
            for e in validation.errors:
                rep.log(f"[X] {e}")
            return RunResult(ok=False, errors=list(validation.errors))

        req = request.normalised()
        endpoint = self._ENDPOINTS.get(req.analysis_mode.upper())
        if endpoint is None:  # validate_run_request rejects this first; belt and braces
            return RunResult(ok=False, errors=[f"Unknown analysis mode: {req.analysis_mode}"])

        from rbgyanx.logic.engine_bridge import run_engine_analysis

        rep.status("Running the engine")
        rep.progress(0.0)
        try:
            engine_result, logs = run_engine_analysis(
                input_dir=req.input_path,
                output_dir=req.output_dir,
                endpoint=endpoint,
                mode="basic" if req.basic_mode else "advanced",
                site_override=req.site or None,
                outcome_csv=req.clinical_file,
                enable_ml=req.enable_ml,
            )
        except Exception as exc:
            # A failed engine run is reported, never swallowed into an empty-looking success.
            rep.log(f"[X] {type(exc).__name__}: {exc}")
            rep.status("Run failed")
            return RunResult(ok=False, errors=[f"{type(exc).__name__}: {exc}"])

        for line in logs:
            rep.log(line)
        rep.progress(1.0)
        rep.status("Done")
        return self._adapt_engine_result(engine_result)

    # ---------------------------------------------------------------- internals

    @staticmethod
    def _adapt_engine_result(engine_result: Any) -> RunResult:
        """Map an ``EngineResult`` onto what the views render.

        Target rows carry ``TCP_*`` and ``raw_name``; OAR rows carry ``NTCP_*`` and ``structure``
        (DICOM OAR rows have no ``raw_name`` — see the applicability-guard entry in
        docs/KNOWN_LIMITATIONS.md). Both carry ``_dvh_df``.
        """
        structures: list[StructureResult] = []

        for row in getattr(engine_result, "tcp_results", None) or []:
            dose, vol = _cumulative_curve(row.get("_dvh_df"))
            structures.append(
                StructureResult(
                    label=str(row.get("raw_name") or row.get("canonical_name") or "target"),
                    patient_id=str(row.get("AnonPatientID", "")),
                    dose_gy=dose,
                    volume_pct=vol,
                    mean_dose_gy=_as_float(row.get("Dmean_gy")),
                    volume_cc=_as_float(row.get("volume_cc")),
                    source_file=str(row.get("source_file", "")),
                    is_target=True,
                    target_type=str(row.get("target_type", "")),
                    tcp=_models_from_row(row, "TCP_"),
                )
            )

        for row in getattr(engine_result, "ntcp_results", None) or []:
            dose, vol = _cumulative_curve(row.get("_dvh_df"))
            structures.append(
                StructureResult(
                    label=str(row.get("structure") or row.get("raw_name") or "OAR"),
                    patient_id=str(row.get("AnonPatientID", "")),
                    dose_gy=dose,
                    volume_pct=vol,
                    mean_dose_gy=_as_float(row.get("Dmean_gy")),
                    volume_cc=_as_float(row.get("volume_cc")),
                    source_file=str(row.get("source_file", "")),
                    is_target=False,
                    ntcp=_models_from_row(row, "NTCP_"),
                )
            )

        exit_code = int(getattr(engine_result, "exit_code", 1) or 0)
        errors: list[str] = []
        message = str(getattr(engine_result, "message", "") or "")
        if exit_code != 0:
            errors.append(message or f"engine exited with code {exit_code}")
        # ``n_files`` is the denominator in ``RunResult.summary``. An engine run is per patient,
        # not per file, so count distinct patients: one input case, however many files it took.
        # Using len(structures) here would make the summary claim one file per structure.
        patients = {s.patient_id for s in structures if s.patient_id}
        return RunResult(
            ok=exit_code == 0 and bool(structures),
            structures=structures,
            errors=errors,
            n_files=len(patients) or len(structures),
        )

    @staticmethod
    def _list_dvh_files(folder: Path | None) -> list[Path]:
        from dicom_io.txt_dvh_reader import iter_dvh_text_files

        if folder is None:
            raise FileNotFoundError("no input folder supplied")
        return list(iter_dvh_text_files(folder))

    @staticmethod
    def _read_one(path: Path, ntcp_models: dict[str, dict[str, Any]]) -> StructureResult:
        """Parse one DVH file and evaluate the requested engine NTCP models."""
        from dicom_io.structure_mapper import TARGET_CANONICALS, canon_target
        from dicom_io.txt_dvh_reader import parse_dvh_text_file
        from radiobiology import dvh_object_to_dataframe
        from validation.ntcp_benchmark import classical_ntcp

        parsed = parse_dvh_text_file(path)
        diff = dvh_object_to_dataframe(parsed.dvh_object)

        # Classify from the RAW ROI name (the reader coerces every single-file canonical to PTV,
        # so parsed.canonical_name cannot be trusted for this). NTCP is an OAR concept; a target
        # must never receive one from some fallback organ's parameters.
        target_canonical = str(canon_target(parsed.raw_name).get("canonical", ""))
        is_target = target_canonical in TARGET_CANONICALS

        # Differential -> cumulative % for display, shared with the engine adapter.
        dose, vol_pct = _cumulative_curve(diff)

        # A target gets NO NTCP — explicitly not-applicable, never a fallback organ's number.
        ntcp: dict[str, float] = {}
        if not is_target:
            for label, cfg in ntcp_models.items():
                model = cfg["model"]
                params = cfg["params"]
                try:
                    if model == "rs_poisson":
                        value = float(classical_ntcp(model, params, dvhs=[diff])[0])
                    else:
                        value = float(
                            classical_ntcp(model, params, dose_metric=[parsed.dmean_gy])[0]
                        )
                except Exception:
                    value = float("nan")
                ntcp[label] = value

        return StructureResult(
            label=parsed.raw_name or path.stem,
            patient_id=parsed.patient_id,
            dose_gy=dose,
            volume_pct=vol_pct,
            mean_dose_gy=float(parsed.dmean_gy),
            volume_cc=float(parsed.total_volume_cc),
            ntcp=ntcp,
            source_file=path.name,
            is_target=is_target,
            target_type=target_canonical if is_target else "",
        )
