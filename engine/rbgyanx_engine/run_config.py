"""Public API configuration for rbgyanx-engine (R1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


Endpoint = Literal["tcp", "ntcp", "both"]
InputKind = Literal["dicom", "dvh_txt"]
RunMode = Literal["basic", "advanced"]


@dataclass
class RunConfig:
    """Single-run configuration for :func:`run_analysis`."""

    endpoint: Endpoint = "tcp"
    input_kind: InputKind = "dicom"
    input_dir: Path = Path(".")
    output_dir: Path = Path("rbgyanx_output")
    clinical_csv: Path | None = None
    clinical_features_csv: Path | None = None
    outcome_csv: Path | None = None
    site: str | None = None
    n_mc: int = 1000
    enable_ml: bool = False  # opt-in explicitly; engine_bridge sets True for advanced+outcome
    mode: RunMode = "basic"
    user_config: Path | None = None
    user_ntcp_config: Path | None = None
    dvh_glob: str = "*.txt"
    dose_per_fraction: float = 2.0
    cohort: bool = False
    no_uncertainty: bool = False
    no_ml_augment: bool = False
    figures: bool = False
    verbose: bool = False
    # Part F (ADVANCED): Bayesian NTCP + PINN training (engine_advanced_f)
    enable_bayesian_ntcp: bool = False
    bayesian_ntcp_trace_dir: Path | None = None
    bayesian_n_samples: int = 500
    bayesian_n_tune: int = 500
    pinn_train: bool = False
    pinn_model_dir: Path | None = None
    pinn_epochs: int = 200
    pinn_lambda_physics: float = 1.0
    pinn_lambda_boundary: float = 0.5


@dataclass
class EngineResult:
    """Paths and status from a completed engine run."""

    exit_code: int
    output_dir: Path
    tcp_results: list[dict] = field(default_factory=list)
    ntcp_results: list[dict] = field(default_factory=list)
    site_detection_csv: Path | None = None
    tcp_benchmark_xlsx: Path | None = None
    ntcp_benchmark_xlsx: Path | None = None
    ntcp_results_csv: Path | None = None
    cohort_features_csv: Path | None = None
    provenance_json: Path | None = None
    qa_report_json: Path | None = None
    physical_metrics_csv: Path | None = None
    plan_quality_summary_xlsx: Path | None = None
    plan_quality_flags_csv: Path | None = None
    patient_summary_pdf: Path | None = None
    validation_metrics_xlsx: Path | None = None
    dose_arrays_available: bool = False
    physical_results: list[dict] = field(default_factory=list)
    bayesian_ntcp_summary_csv: Path | None = None
    pinn_checkpoint: Path | None = None
    message: str = ""
