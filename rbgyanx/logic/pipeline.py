"""
rbgyanx.logic.pipeline - Analysis Pipeline Orchestration

This module provides the central orchestration layer for rbGyanX analysis pipeline.

Layer 2 (Logic) Responsibilities:
- Pipeline orchestration
- Execution sequencing
- Input/output validation
- Conditional branching (physical vs biological)
- QA-driven flow control
- Mode-aware capability gating (future)

NOTE: Phase 1.5 - Initial implementation wraps existing scripts via subprocess
for backward compatibility. Will gradually replace with direct function calls.

Author: rbGyanX Team
Version: 1.0.0
"""

import sys
import subprocess
import time
import random
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Phase 2: Import provenance and structured logging
from rbgyanx.logic.provenance import ProvenanceTracker, create_provenance_record
from rbgyanx.logic.structured_logging import StructuredLogger, LogCategory

# Phase 3: Import applicability checking
from rbgyanx.logic.applicability import (
    ApplicabilityChecker,
    ApplicabilityResult,
    TreatmentTechnique,
    BiologicalModel
)

# Phase 4: Import mode controller
from rbgyanx.logic.mode_controller import ModeController, RunMode, ModeError

# Phase 6.1: Import model agreement analysis
from rbgyanx.logic.model_agreement import ModelAgreementAnalyzer, ModelAgreementResult

# Phase 6.2: Import sensitivity analysis
from rbgyanx.logic.sensitivity_analysis import SensitivityAnalyzer, StabilityAnalysisResult

# Phase 6.3: Import uncertainty decomposition
from rbgyanx.logic.uncertainty_decomposition import UncertaintyDecomposer, UncertaintyDecompositionResult

# Phase 6.4: Import robustness analysis
from rbgyanx.logic.robustness_analysis import RobustnessAnalyzer, RobustnessAnalysisResult

# Phase 6.5: Import applicability boundary detection
from rbgyanx.logic.applicability_boundary import (
    ApplicabilityBoundaryDetector, 
    ApplicabilityBoundaryResult,
    BoundaryType
)

# Phase 7: Import developer mode
from rbgyanx.logic.developer_mode import (
    DeveloperModeSandbox,
    ScientificIntentMetadata
)

# Phase 8: Import benchmark integration
from rbgyanx.logic.benchmark_integration import (
    BenchmarkIntegration,
    DICOMImporter,
    BenchmarkIntegrationResult
)

# Phase 9: Import protocol stress-testing
from rbgyanx.logic.protocol_stress_testing import (
    ProtocolStressTestingSandbox,
    ProtocolStressTestResult
)

# Phase 10: Import AI integration
from rbgyanx.logic.ai_integration import (
    AskRbGyanXIntegration,
    AIPersonality
)

# Phase 11: Import education & training
from rbgyanx.logic.education_training import (
    EducationTrainingWorkflow,
    EducationTrainingResult
)

# Phase 12: Import publication & provenance toolkit
from rbgyanx.logic.publication_provenance import (
    PublicationProvenanceToolkit
)


@dataclass
class PipelineInput:
    """
    Input data structure for analysis pipeline.
    
    Attributes
    ----------
    dvh_directory : Path
        Directory containing DVH files
    output_directory : Path
        Directory for analysis outputs
    patient_data_file : Optional[Path]
        Path to patient data file (for NTCP analysis)
    clinical_file : Optional[Path]
        Path to clinical factors file (for factors analysis)
    treatment_info : Optional[Dict[str, Any]]
        Treatment information (dose per fraction, n fractions, etc.)
    config : Optional[Dict[str, Any]]
        Analysis configuration options
    
    Step 3 (TCP/NTCP) Parameters:
    -----------------------------
    tcp_config : Optional[Dict[str, Any]]
        TCP analysis configuration:
        - tumor_type: str - Tumor type (e.g., 'HNSCC')
        - physical_metrics_file: Optional[Path] - Physical metrics file path
        - enable_ml: bool - Enable ML models
        - enable_shap: bool - Enable SHAP explainability (requires ML)
        - use_fdvh: bool - Use fractionation-aware DVH
        - n_fractions: Optional[int] - Number of fractions (for FDVH)
        - alpha_beta_tumor: Optional[float] - Alpha/beta ratio for tumor (for FDVH)
        - use_utcp: bool - Use uncertainty-aware TCP
        - ccs_file: Optional[Path] - CCS file path for ML safety gating
        - ccs_threshold: Optional[float] - CCS threshold for ML safety gating
    
    ntcp_config : Optional[Dict[str, Any]]
        NTCP analysis configuration:
        - enable_ml: bool - Enable ML models
        - enable_shap: bool - Enable SHAP explainability (requires ML)
    
    Note: Pipeline supports basic TCP/NTCP execution. Advanced features
    (FDVH, uTCP, CCS) trigger subprocess fallback.
    """
    dvh_directory: Path
    output_directory: Path
    dicom_directory: Optional[Path] = None
    input_source: str = "auto"  # auto | dicom | tps_txt
    engine_root: Optional[Path] = None
    patient_data_file: Optional[Path] = None
    clinical_file: Optional[Path] = None
    treatment_info: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    tcp_config: Optional[Dict[str, Any]] = None
    ntcp_config: Optional[Dict[str, Any]] = None


@dataclass
class PipelineOutput:
    """
    Output data structure from analysis pipeline.
    
    Attributes
    ----------
    status : str
        Execution status: 'success', 'error', 'partial'
    physical_results_path : Optional[Path]
        Path to physical metrics results
    biological_results_path : Optional[Path]
        Path to biological metrics results (TCP/NTCP)
    qa_results_path : Optional[Path]
        Path to QA report
    logs : List[str]
        Execution logs
    execution_time : float
        Total execution time in seconds
    errors : List[str]
        Error messages (if any)
    warnings : List[str]
        Warning messages (if any)
    
    Step 3 (TCP/NTCP) Results:
    --------------------------
    tcp_results_path : Optional[Path]
        Path to TCP analysis results
    ntcp_results_path : Optional[Path]
        Path to NTCP analysis results
    execution_mode : Optional[str]
        Execution mode: 'pipeline' or 'subprocess' (for debugging)
    """
    status: str
    physical_results_path: Optional[Path] = None
    biological_results_path: Optional[Path] = None
    qa_results_path: Optional[Path] = None
    logs: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tcp_results_path: Optional[Path] = None
    ntcp_results_path: Optional[Path] = None
    site_detection_path: Optional[Path] = None
    execution_mode: Optional[str] = None
    provenance: Optional[Any] = None  # ProvenanceRecord
    structured_logs: Optional[Any] = None  # StructuredLogger
    applicability_result: Optional[Any] = None  # ApplicabilityResult (Phase 3)
    model_agreement_result: Optional[Any] = None  # ModelAgreementResult (Phase 6.1)
    sensitivity_analysis_result: Optional[Any] = None  # StabilityAnalysisResult (Phase 6.2)
    uncertainty_decomposition_result: Optional[Any] = None  # UncertaintyDecompositionResult (Phase 6.3)
    robustness_analysis_result: Optional[Any] = None  # RobustnessAnalysisResult (Phase 6.4)
    applicability_boundary_result: Optional[Any] = None  # ApplicabilityBoundaryResult (Phase 6.5)
    developer_mode_session: Optional[Any] = None  # DeveloperModeSession (Phase 7)
    benchmark_integration_result: Optional[Any] = None  # BenchmarkIntegrationResult (Phase 8)
    protocol_stress_test_result: Optional[Any] = None  # ProtocolStressTestResult (Phase 9)
    ai_integration: Optional[Any] = None  # AskRbGyanXIntegration (Phase 10)
    education_training_result: Optional[Any] = None  # EducationTrainingResult (Phase 11)
    publication_provenance_toolkit: Optional[Any] = None  # PublicationProvenanceToolkit (Phase 12)


def run_analysis_pipeline(
    inputs: PipelineInput,
    steps: Optional[List[str]] = None,
    timeout: int = 300,
    random_seed: Optional[int] = None,
    enable_provenance: bool = True,
    enable_structured_logging: bool = True,
    mode_controller: Optional[ModeController] = None
) -> PipelineOutput:
    """
    Execute the rbGyanX analysis pipeline.
    
    This is the central orchestration function that coordinates the execution
    of analysis steps. Currently wraps existing scripts via subprocess for
    backward compatibility.
    
    Pipeline Stages:
    1. DVH Preprocessing (code1_dvh_preprocess.py)
    2. Physical Metrics & Plotting (code2_dvh_plot_and_summary.py)
    3. NTCP Analysis (code3_ntcp_analysis_ml.py)
    4. QA Reporting (code4_ntcp_output_QA_reporter.py)
    5. Clinical Factors Analysis (code5_ntcp_factors_analysis.py)
    6. TCP Analysis (code6_tcp_analysis.py)
    7. TCP/NTCP Integration (code7_tcp_ntcp_integration.py)
    
    Parameters
    ----------
    inputs : PipelineInput
        Input data for the pipeline
    steps : Optional[List[str]]
        List of steps to execute. If None, executes all steps.
        Valid steps: ['preprocess', 'physical', 'ntcp', 'qa', 'factors', 'tcp', 'integration']
    timeout : int
        Timeout per step in seconds (default: 300)
    random_seed : Optional[int]
        Random seed for deterministic execution (Phase 2)
    enable_provenance : bool
        Enable provenance tracking (Phase 2, default: True)
    enable_structured_logging : bool
        Enable structured logging (Phase 2, default: True)
    mode_controller : Optional[ModeController]
        Mode controller for governance (Phase 4, defaults to BASIC)
    
    Returns
    -------
    PipelineOutput
        Pipeline execution results with provenance and structured logs
    
    Notes
    -----
    - Phase 1.5: Initial implementation uses subprocess to wrap existing scripts
    - Phase 2: Added deterministic execution, provenance tracking, structured logging
    - Phase 3: Added applicability checking and scientific validity gates
    - Phase 4: Added mode governance (BASIC mode enforced)
    - Future: Will gradually replace with direct function calls to core modules
    - Maintains backward compatibility with existing workflows
    """
    start_time = time.time()
    output = PipelineOutput(status='success')
    
    # Phase 4: Initialize mode controller (defaults to BASIC)
    if mode_controller is None:
        mode_controller = ModeController(RunMode.BASIC)
    
    # Phase 4: Apply conservative defaults for BASIC mode
    if mode_controller.is_basic():
        conservative_defaults = mode_controller.get_conservative_defaults()
        # Apply defaults to config if not already set
        if inputs.config is None:
            inputs.config = {}
        for key, default_value in conservative_defaults.items():
            if key not in inputs.config:
                inputs.config[key] = default_value
                if structured_logger:
                    structured_logger.debug(
                        f"Applied conservative default: {key}={default_value}",
                        metadata={'mode': 'BASIC', 'default_key': key}
                    )
        
        # Phase 4: Track explicit intent
        explicit_intent = mode_controller.get_explicit_intent()
        if provenance_tracker:
            provenance_tracker.track_metadata('explicit_intent', explicit_intent)
        if structured_logger:
            structured_logger.info(
                f"Explicit intent: {explicit_intent['intent']}",
                metadata={'intent': explicit_intent}
            )
    
    # Phase 2: Initialize deterministic execution
    if random_seed is not None:
        random.seed(random_seed)
        np.random.seed(random_seed)
    
    # Phase 2: Initialize provenance tracking
    provenance_tracker = None
    if enable_provenance:
        provenance_tracker = ProvenanceTracker()
        provenance_tracker.track_input('dvh_directory', inputs.dvh_directory)
        if inputs.patient_data_file:
            provenance_tracker.track_input('patient_data_file', inputs.patient_data_file)
        if inputs.clinical_file:
            provenance_tracker.track_input('clinical_file', inputs.clinical_file)
        if inputs.config:
            for key, value in inputs.config.items():
                provenance_tracker.track_config(key, value)
        if inputs.tcp_config:
            for key, value in inputs.tcp_config.items():
                provenance_tracker.track_config(f'tcp_{key}', value)
        if inputs.ntcp_config:
            for key, value in inputs.ntcp_config.items():
                provenance_tracker.track_config(f'ntcp_{key}', value)
        if random_seed is not None:
            provenance_tracker.track_metadata('random_seed', random_seed)
    
    # Phase 2: Initialize structured logging
    structured_logger = None
    if enable_structured_logging:
        structured_logger = StructuredLogger(
            session_id=provenance_tracker.session_id if provenance_tracker else None
        )
    # Phase 4: Log mode and contract message
        structured_logger.info(
            f"Pipeline execution started in {mode_controller.mode.value.upper()} mode",
            metadata={
                'steps': steps,
                'mode': mode_controller.mode.value,
                'contract': mode_controller.get_contract_message()
            }
        )
    output.logs.append(f"rbGyanX running in {mode_controller.mode.value.upper()} mode")
    output.logs.append(mode_controller.get_contract_message())
    
    # Phase 10: Initialize AI Integration (Ask rbGyanX) - Available in both modes
    if mode_controller and mode_controller.is_capability_enabled("ai_integration"):
        # Determine personality based on mode
        personality = AIPersonality.BASIC if mode_controller.is_basic() else AIPersonality.ADVANCED
        
        # Initialize AI integration with appropriate personality
        ai_integration = AskRbGyanXIntegration(personality)
        output.ai_integration = ai_integration
        
        if structured_logger:
            structured_logger.info(
                f"AI Integration (Ask rbGyanX) initialized with {personality.value.upper()} personality",
                category=LogCategory.EXECUTION,
                metadata={
                    'ai_integration': True,
                    'personality': personality.value,
                    'mode': mode_controller.mode.value,
                    'note': 'Explanation-only - no recommendations, no actions, no rankings, no automation'
                }
            )
        
        # Track in provenance
        if provenance_tracker:
            provenance_tracker.track_metadata('ai_integration', {
                'enabled': True,
                'personality': personality.value,
                'mode': mode_controller.mode.value,
                'capability': 'ai_integration',
                'note': 'Explanation-only AI - no recommendations, no actions, no rankings, no automation'
            })
    
    # Phase 11: Initialize Education & Training Workflows - Available in both modes
    if mode_controller and mode_controller.is_capability_enabled("education_training"):
        education_workflow = EducationTrainingWorkflow()
        
        # Generate education session (example)
        education_result = education_workflow.generate_education_session(
            include_plateaus=True,
            include_cliffs=True,
            include_fragility=True
        )
        output.education_training_result = education_result
        
        if structured_logger:
            structured_logger.info(
                "Education & Training Workflows initialized",
                category=LogCategory.EXECUTION,
                metadata={
                    'education_training': True,
                    'mode': mode_controller.mode.value,
                    'learning_paths': len(education_result.learning_paths),
                    'demonstrations': len(education_result.demonstrations),
                    'teaching_overlays': len(education_result.teaching_overlays),
                    'note': 'EDUCATIONAL USE ONLY - No scoring, no recommendations, no pass/fail logic'
                }
            )
        
        # Track in provenance
        if provenance_tracker:
            provenance_tracker.track_metadata('education_training', {
                'enabled': True,
                'capability': 'education_training',
                'mode': mode_controller.mode.value,
                'learning_paths': len(education_result.learning_paths),
                'demonstrations': len(education_result.demonstrations),
                'note': 'Education & Training: EDUCATIONAL USE ONLY - No scoring, no recommendations, no pass/fail logic'
            })
    
    # Phase 12: Initialize Publication & Provenance Toolkit - Available in both modes
    if mode_controller and mode_controller.is_capability_enabled("publication_provenance"):
        publication_toolkit = PublicationProvenanceToolkit()
        output.publication_provenance_toolkit = publication_toolkit
        
        if structured_logger:
            structured_logger.info(
                "Publication & Provenance Toolkit initialized",
                category=LogCategory.EXECUTION,
                metadata={
                    'publication_provenance': True,
                    'mode': mode_controller.mode.value,
                    'note': 'Journal-ready exports, deterministic replay, provenance bundles, and reviewer auditability - No new scientific analysis, no new AI behavior, no UI redesign'
                }
            )
        
        # Track in provenance
        if provenance_tracker:
            provenance_tracker.track_metadata('publication_provenance', {
                'enabled': True,
                'capability': 'publication_provenance',
                'mode': mode_controller.mode.value,
                'note': 'Publication & Provenance Toolkit: Journal-ready exports, deterministic replay, provenance bundles, reviewer auditability'
            })
    
    # Phase 3: Initialize applicability checking
    applicability_checker = ApplicabilityChecker()
    applicability_result = None
    
    # Phase 3: Perform applicability check if treatment info available
    if inputs.treatment_info:
        dose_per_fraction = inputs.treatment_info.get('dose_per_fraction', 2.0)
        n_fractions = inputs.treatment_info.get('n_fractions')
        alpha_beta = inputs.treatment_info.get('alpha_beta_ratio')
        
        # Determine biological model from config
        requested_model = None
        if inputs.tcp_config and inputs.tcp_config.get('use_fdvh'):
            requested_model = BiologicalModel.MODIFIED_LQ  # FDVH uses modified LQ
        elif inputs.config:
            model_name = inputs.config.get('biological_model', 'lq')
            try:
                requested_model = BiologicalModel(model_name.lower())
            except ValueError:
                requested_model = BiologicalModel.LQ  # Default
        
        applicability_result = applicability_checker.check_applicability(
            dose_per_fraction=dose_per_fraction,
            n_fractions=n_fractions,
            requested_model=requested_model,
            alpha_beta_ratio=alpha_beta
        )
        
        # Log applicability warnings (non-blocking)
        if structured_logger and applicability_result.warnings:
            for warning in applicability_result.warnings:
                structured_logger.warning(
                    f"Applicability: {warning.message}",
                    category=LogCategory.VALIDATION,
                    metadata={
                        'category': warning.category,
                        'confidence': warning.confidence,
                        'context': warning.context
                    }
                )
        
        # Track applicability in provenance
        if provenance_tracker:
            provenance_tracker.track_metadata('applicability_check', {
                'biological_allowed': applicability_result.biological_allowed,
                'model_validity': applicability_result.model_validity,
                'fractionation_compatible': applicability_result.fractionation_compatible,
                'confidence': applicability_result.confidence,
                'warnings_count': len(applicability_result.warnings)
            })
    
    # Phase 4: Track mode in provenance
    if provenance_tracker:
        provenance_tracker.track_metadata('mode_governance', {
            'mode': mode_controller.mode.value,
            'is_basic': mode_controller.is_basic(),
            'is_advanced': mode_controller.is_advanced(),
            'capabilities': mode_controller.get_capabilities(),
            'session_id': mode_controller._session_id,
            'decision_support_only': mode_controller.enforce_decision_support_only()
        })
        
        # Add warnings to output
        for warning in applicability_result.warnings:
            output.warnings.append(f"[Applicability] {warning.message}")
    
    # Default to all steps if not specified
    if steps is None:
        steps = ['preprocess', 'physical', 'ntcp', 'qa', 'factors', 'tcp', 'integration']
    
    # Get script directory (assumes scripts are in repo root)
    from rbgyanx.paths import get_scripts_dir

    script_dir = get_scripts_dir()
    
    execution_mode = 'subprocess'  # Default execution mode
    
    try:
        # Step 1: DVH Preprocessing
        if 'preprocess' in steps:
            step_name = 'preprocess'
            if structured_logger:
                structured_logger.log_stage_start(step_name)
            output.logs.append("=== Step 1: DVH Preprocessing ===")
            if provenance_tracker:
                provenance_tracker.track_step(step_name)
            
            result = _run_dvh_preprocessing(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            if result.get('error'):
                output.errors.append(result['error'])
                output.status = 'partial'
                if structured_logger:
                    structured_logger.error(f"Step {step_name} failed: {result['error']}")
            else:
                if structured_logger:
                    structured_logger.log_stage_end(step_name)
                if provenance_tracker:
                    provenance_tracker.track_output('preprocessed_dvh', inputs.output_directory)
        
        # Step 2: Physical Metrics & Plotting
        if 'physical' in steps:
            output.logs.append("=== Step 2: Physical Metrics & Plotting ===")
            result = _run_physical_metrics(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            if result.get('error'):
                output.errors.append(result['error'])
                output.status = 'partial'
            else:
                output.physical_results_path = inputs.output_directory / 'dvh_analysis'
        
        # Step 3: NTCP Analysis (Biological)
        # Phase 3: Physical vs Biological Branching - Warnings logged above if applicable
        if 'ntcp' in steps:
            output.logs.append("=== Step 3: NTCP Analysis ===")
            # Phase 3: Applicability warnings already logged above (non-blocking)
            result = _run_ntcp_analysis(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            output.execution_mode = result.get('execution_mode', 'subprocess')
            if result.get('error'):
                output.errors.append(result['error'])
                output.status = 'partial'
            else:
                output.ntcp_results_path = inputs.output_directory / 'ntcp_analysis'
                site_csv = inputs.output_directory / 'site_detection.csv'
                if site_csv.exists():
                    output.site_detection_path = site_csv
                if output.biological_results_path is None:
                    output.biological_results_path = output.ntcp_results_path
        
        # Step 4: QA Reporting
        if 'qa' in steps:
            output.logs.append("=== Step 4: QA Reporting ===")
            result = _run_qa_reporting(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            if result.get('error'):
                output.warnings.append(result['error'])
            else:
                output.qa_results_path = inputs.output_directory / 'qa_reports'
        
        # Step 5: Clinical Factors Analysis
        if 'factors' in steps and inputs.clinical_file:
            output.logs.append("=== Step 5: Clinical Factors Analysis ===")
            result = _run_factors_analysis(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            if result.get('error'):
                output.warnings.append(result['error'])
        
        # Step 6: TCP Analysis (Biological)
        # Phase 3: Physical vs Biological Branching - Warnings logged above if applicable
        if 'tcp' in steps:
            output.logs.append("=== Step 6: TCP Analysis ===")
            # Phase 3: Applicability warnings already logged above (non-blocking)
            result = _run_tcp_analysis(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            output.execution_mode = result.get('execution_mode', 'subprocess')
            if result.get('error'):
                output.errors.append(result['error'])
                output.status = 'partial'
            else:
                output.tcp_results_path = inputs.output_directory / 'tcp_analysis'
                site_csv = inputs.output_directory / 'site_detection.csv'
                if site_csv.exists():
                    output.site_detection_path = site_csv
                if output.biological_results_path is None:
                    output.biological_results_path = output.tcp_results_path
        
        # Step 7: TCP/NTCP Integration
        if 'integration' in steps:
            output.logs.append("=== Step 7: TCP/NTCP Integration ===")
            result = _run_integration(inputs, script_dir, timeout)
            output.logs.extend(result.get('logs', []))
            if result.get('error'):
                output.warnings.append(result['error'])
        
        # Finalize status
        if output.errors and output.status == 'success':
            output.status = 'error'
        
    except Exception as e:
        output.status = 'error'
        error_msg = f"Pipeline execution failed: {str(e)}"
        output.errors.append(error_msg)
        output.logs.append(f"ERROR: {error_msg}")
        if structured_logger:
            structured_logger.critical(error_msg, metadata={'exception': str(e)})
    
    output.execution_time = time.time() - start_time
    output.logs.append(f"=== Pipeline Complete (Time: {output.execution_time:.2f}s) ===")
    
    # Phase 2: Create provenance record
    if enable_provenance and provenance_tracker:
        # Track output paths
        if output.physical_results_path:
            provenance_tracker.track_output('physical_results', output.physical_results_path)
        if output.biological_results_path:
            provenance_tracker.track_output('biological_results', output.biological_results_path)
        if output.qa_results_path:
            provenance_tracker.track_output('qa_results', output.qa_results_path)
        if output.tcp_results_path:
            provenance_tracker.track_output('tcp_results', output.tcp_results_path)
        if output.ntcp_results_path:
            provenance_tracker.track_output('ntcp_results', output.ntcp_results_path)
        
        # Create provenance record
        output.provenance = provenance_tracker.create_record(
            pipeline_input=inputs,
            execution_mode=execution_mode or output.execution_mode or 'subprocess',
            pipeline_version="1.0.0"
        )
        
        # Phase 4: Add mode metadata to provenance
        if mode_controller:
            output.provenance.metadata['mode_controller'] = mode_controller.get_session_metadata()
            
            # Phase 6.1: Track model agreement analysis if enabled
            if mode_controller.is_capability_enabled("model_comparison"):
                provenance_tracker.track_metadata('model_agreement_analysis', {
                    'enabled': True,
                    'capability': 'model_comparison',
                    'mode': 'ADVANCED',
                    'note': 'Descriptive analysis only - no rankings, no recommendations'
                })
            
            # Phase 6.2: Track sensitivity analysis if enabled
            if mode_controller.is_capability_enabled("sensitivity_analysis"):
                provenance_tracker.track_metadata('sensitivity_analysis', {
                    'enabled': True,
                    'capability': 'sensitivity_analysis',
                    'mode': 'ADVANCED',
                    'note': 'Sensitivity analysis only - no optimization, no rankings, no recommendations'
                })
            
            # Phase 6.3: Track uncertainty decomposition if enabled
            if mode_controller.is_capability_enabled("uncertainty_decomposition"):
                provenance_tracker.track_metadata('uncertainty_decomposition', {
                    'enabled': True,
                    'capability': 'uncertainty_decomposition',
                    'mode': 'ADVANCED',
                    'note': 'Uncertainty decomposition with attribution - no rankings, no recommendations'
                })
            
            # Phase 6.4: Track robustness analysis if enabled
            if mode_controller.is_capability_enabled("robustness_analysis"):
                provenance_tracker.track_metadata('robustness_analysis', {
                    'enabled': True,
                    'capability': 'robustness_analysis',
                    'mode': 'ADVANCED',
                    'note': 'Robustness and stability indices - no ranking outcomes, no recommending actions'
                })
            
            # Phase 6.5: Track applicability boundary detection if enabled
            if mode_controller.is_capability_enabled("applicability_boundary"):
                provenance_tracker.track_metadata('applicability_boundary_detection', {
                    'enabled': True,
                    'capability': 'applicability_boundary',
                    'mode': 'ADVANCED',
                    'note': 'Applicability boundary detection - no blocking, no recommendations'
                })
            
            # Phase 7: Track Developer Mode if enabled
            if mode_controller.is_capability_enabled("developer_mode"):
                provenance_tracker.track_metadata('developer_mode', {
                    'enabled': True,
                    'capability': 'developer_mode',
                    'mode': 'ADVANCED',
                    'note': 'Developer Mode: Full tracking and auditability required - no silent execution, no bypass of logging'
                })
            
            # Phase 8: Track Benchmark Integration if enabled
            if mode_controller.is_capability_enabled("benchmark_integration"):
                provenance_tracker.track_metadata('benchmark_integration', {
                    'enabled': True,
                    'capability': 'benchmark_integration',
                    'mode': 'ADVANCED',
                    'note': 'Benchmark Integration: Contextual reference only - no enforcement, no pass/fail logic, no clinical workflow integration'
                })
            
            # Phase 9: Track Protocol Stress-Testing if enabled
            if mode_controller.is_capability_enabled("protocol_stress_testing"):
                provenance_tracker.track_metadata('protocol_stress_testing', {
                    'enabled': True,
                    'capability': 'protocol_stress_testing',
                    'mode': 'ADVANCED',
                    'note': 'Protocol Stress-Testing: RESEARCH ONLY - No enforcement, no accept/reject logic, no clinical recommendations'
                })
            
            # Phase 10: Track AI Integration if enabled
            if mode_controller.is_capability_enabled("ai_integration"):
                personality = AIPersonality.BASIC if mode_controller.is_basic() else AIPersonality.ADVANCED
                provenance_tracker.track_metadata('ai_integration', {
                    'enabled': True,
                    'personality': personality.value,
                    'capability': 'ai_integration',
                    'mode': mode_controller.mode.value,
                    'note': 'AI Integration: Explanation-only - no recommendations, no actions, no rankings, no automation'
                })
            
            # Phase 11: Track Education & Training if enabled
            if mode_controller.is_capability_enabled("education_training"):
                provenance_tracker.track_metadata('education_training', {
                    'enabled': True,
                    'capability': 'education_training',
                    'mode': mode_controller.mode.value,
                    'note': 'Education & Training: EDUCATIONAL USE ONLY - No scoring, no recommendations, no pass/fail logic'
                })
            
            # Phase 12: Track Publication & Provenance Toolkit if enabled
            if mode_controller.is_capability_enabled("publication_provenance"):
                provenance_tracker.track_metadata('publication_provenance', {
                    'enabled': True,
                    'capability': 'publication_provenance',
                    'mode': mode_controller.mode.value,
                    'note': 'Publication & Provenance Toolkit: Journal-ready exports, deterministic replay, provenance bundles, reviewer auditability'
                })
        
        # Save provenance to output directory
        provenance_file = inputs.output_directory / 'provenance.json'
        output.provenance.save(provenance_file)
        output.logs.append(f"Provenance saved: {provenance_file}")
    
    # Phase 3: Store applicability result in output
    output.applicability_result = applicability_result
    
    # Phase 6.1: Model Agreement/Disagreement Analysis (ADVANCED mode only)
    if mode_controller and mode_controller.is_capability_enabled("model_comparison"):
        if structured_logger:
            structured_logger.info(
                "Model agreement/disagreement analysis enabled (ADVANCED mode)",
                category=LogCategory.EXECUTION,
                metadata={'capability': 'model_comparison'}
            )
        
        # Initialize model agreement analyzer
        # Note: Actual analysis will be performed when TCP/NTCP results are available
        # This is a placeholder for future integration with result processing
        model_agreement_analyzer = ModelAgreementAnalyzer()
        
        if structured_logger:
            structured_logger.info(
                "Model agreement analyzer initialized (results will be computed after TCP/NTCP steps)",
                category=LogCategory.EXECUTION
            )
        
        # Store analyzer reference (for future use when results are available)
        # For now, we just track that the capability is enabled
        output.model_agreement_result = None  # Will be populated when results available
    
    # Phase 6.2: Parameter Sensitivity & Stability Analysis (ADVANCED mode only)
    if mode_controller and mode_controller.is_capability_enabled("sensitivity_analysis"):
        if structured_logger:
            structured_logger.info(
                "Parameter sensitivity and stability analysis enabled (ADVANCED mode)",
                category=LogCategory.EXECUTION,
                metadata={'capability': 'sensitivity_analysis'}
            )
        
        # Initialize sensitivity analyzer
        # Note: Actual analysis will be performed when model results are available
        # This is a placeholder for future integration with result processing
        sensitivity_analyzer = SensitivityAnalyzer()
        
        if structured_logger:
            structured_logger.info(
                "Sensitivity analyzer initialized (results will be computed when model results available)",
                category=LogCategory.EXECUTION
            )
        
        # Store analyzer reference (for future use when results are available)
        # For now, we just track that the capability is enabled
        output.sensitivity_analysis_result = None  # Will be populated when results available
    
    # Phase 6.3: Uncertainty Decomposition (ADVANCED mode only)
    if mode_controller and mode_controller.is_capability_enabled("uncertainty_decomposition"):
        if structured_logger:
            structured_logger.info(
                "Uncertainty decomposition enabled (ADVANCED mode)",
                category=LogCategory.EXECUTION,
                metadata={'capability': 'uncertainty_decomposition'}
            )
        
        # Initialize uncertainty decomposer
        # Note: Actual decomposition will be performed when uncertainty data is available
        # This is a placeholder for future integration with uncertainty quantification
        uncertainty_decomposer = UncertaintyDecomposer()
        
        if structured_logger:
            structured_logger.info(
                "Uncertainty decomposer initialized (results will be computed when uncertainty data available)",
                category=LogCategory.EXECUTION
            )
        
        # Store decomposer reference (for future use when uncertainty data is available)
        # For now, we just track that the capability is enabled
        output.uncertainty_decomposition_result = None  # Will be populated when uncertainty data available
    
    # Phase 6.4: Robustness & Stability Indices (ADVANCED mode only)
    if mode_controller and mode_controller.is_capability_enabled("robustness_analysis"):
        if structured_logger:
            structured_logger.info(
                "Robustness and stability analysis enabled (ADVANCED mode)",
                category=LogCategory.EXECUTION,
                metadata={'capability': 'robustness_analysis'}
            )
        
        # Initialize robustness analyzer
        # Note: Actual analysis will be performed when perturbation data is available
        # This is a placeholder for future integration with perturbation analysis
        robustness_analyzer = RobustnessAnalyzer()
        
        if structured_logger:
            structured_logger.info(
                "Robustness analyzer initialized (results will be computed when perturbation data available)",
                category=LogCategory.EXECUTION
            )
        
        # Store analyzer reference (for future use when perturbation data is available)
        # For now, we just track that the capability is enabled
        output.robustness_analysis_result = None  # Will be populated when perturbation data available
    
    # Phase 7: Initialize Developer Mode sandbox (will be used if enabled)
    developer_sandbox = None
    
    # Phase 6.5: Applicability Boundary Detection (ADVANCED mode only)
    if mode_controller and mode_controller.is_capability_enabled("applicability_boundary"):
        if structured_logger:
            structured_logger.info(
                "Applicability boundary detection enabled (ADVANCED mode)",
                category=LogCategory.EXECUTION,
                metadata={'capability': 'applicability_boundary'}
            )
        
        # Initialize boundary detector
        # Note: Actual detection will be performed when parameter data is available
        # This is a placeholder for future integration with parameter analysis
        boundary_detector = ApplicabilityBoundaryDetector()
        
        # If treatment_info is available, perform boundary detection
        if inputs.treatment_info:
            try:
                current_params = {
                    'dose_per_fraction': inputs.treatment_info.get('dose_per_fraction', 2.0),
                    'n_fractions': inputs.treatment_info.get('n_fractions', 30),
                }
                
                # Detect boundaries
                boundary_result = boundary_detector.detect_boundaries(current_params)
                output.applicability_boundary_result = boundary_result
                
                # Log detection summary
                if structured_logger:
                    for summary_line in boundary_result.detection_summary:
                        structured_logger.info(
                            summary_line,
                            category=LogCategory.VALIDATION,
                            metadata={'boundary_detection': True}
                        )
                
                # Add boundary warnings to output (descriptive, not blocking)
                for boundary in boundary_result.boundaries:
                    if boundary.boundary_type == BoundaryType.EXTRAPOLATION:
                        output.warnings.append(
                            f"[Boundary Detection] {boundary.parameter_name} in extrapolation zone "
                            f"(detection only, not a block)"
                        )
                    elif boundary.boundary_type == BoundaryType.FRAGILE:
                        output.warnings.append(
                            f"[Boundary Detection] {boundary.parameter_name} near applicability boundary "
                            f"(detection only, not a block)"
                        )
            except Exception as e:
                if structured_logger:
                    structured_logger.warning(
                        f"Boundary detection failed: {str(e)}",
                        category=LogCategory.VALIDATION
                    )
        else:
            if structured_logger:
                structured_logger.info(
                    "Boundary detector initialized (results will be computed when parameter data available)",
                    category=LogCategory.EXECUTION
                )
            
            output.applicability_boundary_result = None  # Will be populated when parameter data available
    
    # Phase 7: Developer Mode (Governed Sandbox) - ADVANCED mode only
    if mode_controller and mode_controller.is_capability_enabled("developer_mode"):
        if structured_logger:
            structured_logger.warning(
                "Developer Mode enabled - Experimental modifications will be fully tracked and logged",
                category=LogCategory.VALIDATION,
                metadata={'capability': 'developer_mode', 'mode': 'ADVANCED'}
            )
        
        # Initialize Developer Mode sandbox
        # Phase 7: Mandatory tracking, no silent execution
        developer_sandbox = DeveloperModeSandbox()
        output.developer_mode_session = developer_sandbox.current_session
        
        if structured_logger:
            structured_logger.info(
                f"Developer Mode sandbox initialized: {developer_sandbox.session_id}",
                category=LogCategory.EXECUTION,
                metadata={
                    'developer_mode': True,
                    'session_id': developer_sandbox.session_id,
                    'note': 'All modifications will be tracked and logged - no silent execution'
                }
            )
            
            # Log audit trail start (mandatory - no silent execution)
            for audit_entry in developer_sandbox.get_audit_trail():
                structured_logger.info(
                    audit_entry,
                    category=LogCategory.AUDIT,
                    metadata={'developer_mode': True, 'session_id': developer_sandbox.session_id}
                )
        
        # Track in provenance (mandatory - no bypass)
        if provenance_tracker:
            provenance_tracker.track_metadata('developer_mode', {
                'enabled': True,
                'session_id': developer_sandbox.session_id,
                'capability': 'developer_mode',
                'mode': 'ADVANCED',
                'note': 'Developer Mode: Full tracking and auditability required - no silent execution, no bypass of logging'
            })
    
    # Phase 2: Finalize structured logging
    if enable_structured_logging and structured_logger:
        structured_logger.info(
            f"Pipeline execution completed",
            metadata={
                'status': output.status,
                'execution_time': output.execution_time,
                'steps_executed': steps
            }
        )
        output.structured_logs = structured_logger
        
        # Save structured logs to output directory
        logs_file = inputs.output_directory / 'structured_logs.json'
        structured_logger.save(logs_file)
        output.logs.append(f"Structured logs saved: {logs_file}")
        
        # Phase 7: End Developer Mode session if active (after logging, before return)
        if developer_sandbox:
            completed_session = developer_sandbox.end_session()
            output.developer_mode_session = completed_session
            
            # Export session to output directory
            try:
                session_export_path = inputs.output_directory / f'developer_mode_session_{developer_sandbox.session_id}.json'
                developer_sandbox.export_session(session_export_path)
                output.logs.append(f"Developer Mode session exported: {session_export_path}")
                
                # Log final audit trail (mandatory - no silent execution)
                structured_logger.info(
                    f"Developer Mode session completed and exported: {session_export_path}",
                    category=LogCategory.AUDIT,
                    metadata={'developer_mode': True, 'session_id': developer_sandbox.session_id}
                )
                
                # Log session summary
                for summary_line in completed_session.session_summary:
                    structured_logger.info(
                        summary_line,
                        category=LogCategory.AUDIT,
                        metadata={'developer_mode': True, 'session_id': developer_sandbox.session_id}
                    )
            except Exception as e:
                output.errors.append(f"Failed to export Developer Mode session: {str(e)}")
                structured_logger.error(
                    f"Failed to export Developer Mode session: {str(e)}",
                    category=LogCategory.ERROR,
                    metadata={'developer_mode': True, 'session_id': developer_sandbox.session_id}
                )
    
    return output


def _run_dvh_preprocessing(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """Run DVH preprocessing step."""
    script_path = script_dir / 'code1_dvh_preprocess.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    # code1_dvh_preprocess.py takes: input_path (positional) --outdir output_dir
    cmd = [
        sys.executable,
        str(script_path),
        str(inputs.dvh_directory),
        '--outdir', str(inputs.output_directory)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


def _run_physical_metrics(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """Run physical metrics calculation step."""
    script_path = script_dir / 'code2_dvh_plot_and_summary.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    # code2 takes: processed_dir (positional) --outdir output_dir
    # processed_dir should be the output from code1 (contains cDVH_csv and dDVH_csv)
    processed_dir = inputs.output_directory
    if not processed_dir.exists():
        return {'error': f'Processed directory not found: {processed_dir}'}
    
    cmd = [
        sys.executable,
        str(script_path),
        str(processed_dir),
        '--outdir', str(inputs.output_directory / 'dvh_analysis')
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


def _run_ntcp_analysis(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """
    Run NTCP analysis step.

    Phase R2: uses rbgyanx-engine for DICOM + classical NTCP when available.
    Falls back to code3 subprocess for ML/SHAP or TPS-only legacy path.
    """
    from rbgyanx.logic.engine_bridge import (
        detect_input_kind,
        is_engine_available,
        needs_subprocess_fallback,
        run_engine_analysis,
    )

    engine_in = inputs.dicom_directory
    if engine_in is None and detect_input_kind(inputs.dvh_directory) == "dicom":
        engine_in = inputs.dvh_directory

    if (
        engine_in
        and engine_in.exists()
        and is_engine_available(inputs.engine_root)
        and not needs_subprocess_fallback(inputs.tcp_config, inputs.ntcp_config)
    ):
        try:
            mode = (inputs.config or {}).get("engine_mode", "basic")
            site = (inputs.config or {}).get("site_override")
            result, logs = run_engine_analysis(
                input_dir=engine_in,
                output_dir=inputs.output_directory,
                endpoint="ntcp",
                mode=mode,
                site_override=site,
                enable_ml=False,
                cohort=True,
                engine_root=inputs.engine_root,
            )
            return {
                "logs": logs,
                "error": None if result.exit_code == 0 else f"Engine exit code {result.exit_code}",
                "execution_mode": "engine",
            }
        except Exception as exc:
            return {"logs": [f"Engine NTCP failed: {exc}"], "error": str(exc), "execution_mode": "engine"}

    script_path = script_dir / 'code3_ntcp_analysis_ml.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    dvh_dir = inputs.output_directory / 'processed_DVH' / 'dDVH_csv'
    output_dir = inputs.output_directory / 'ntcp_analysis'
    
    if not dvh_dir.exists():
        return {'error': f'DVH directory not found: {dvh_dir}'}
    
    # Check if pipeline can handle this configuration
    # Pipeline supports: basic execution, ML models, SHAP
    # All other options trigger fallback (currently none, but reserved for future)
    use_pipeline = True  # Basic NTCP is always pipeline-supported
    
    # Build command
    cmd = [
        sys.executable,
        str(script_path),
        '--dvh_dir', str(dvh_dir),
        '--output_dir', str(output_dir)
    ]
    
    # Add patient data if provided
    patient_data = inputs.patient_data_file
    if patient_data and patient_data.exists():
        cmd.extend(['--patient_data', str(patient_data)])
    elif inputs.ntcp_config and inputs.ntcp_config.get('require_patient_data', False):
        return {'error': 'Patient data file required for NTCP analysis'}
    
    # Add ML models flag if configured
    if inputs.ntcp_config and inputs.ntcp_config.get('enable_ml', False):
        cmd.append('--ml_models')
    
    # Add SHAP flag if configured (requires ML)
    if (inputs.ntcp_config and 
        inputs.ntcp_config.get('enable_shap', False) and 
        inputs.ntcp_config.get('enable_ml', False)):
        cmd.append('--enable_shap')
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}',
            'execution_mode': 'pipeline' if use_pipeline else 'subprocess'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


def _run_qa_reporting(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """Run QA reporting step."""
    script_path = script_dir / 'code4_ntcp_output_QA_reporter.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    ntcp_dir = inputs.output_directory / 'ntcp_analysis'
    if not ntcp_dir.exists():
        return {'error': f'NTCP directory not found: {ntcp_dir}'}
    
    cmd = [
        sys.executable,
        str(script_path),
        '--input_dir', str(ntcp_dir),
        '--output_dir', str(inputs.output_directory / 'qa_reports')
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


def _run_factors_analysis(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """Run clinical factors analysis step."""
    script_path = script_dir / 'code5_ntcp_factors_analysis.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    if not inputs.clinical_file or not inputs.clinical_file.exists():
        return {'error': 'Clinical file required for factors analysis'}
    
    ntcp_dir = inputs.output_directory / 'ntcp_analysis'
    if not ntcp_dir.exists():
        return {'error': f'NTCP directory not found: {ntcp_dir}'}
    
    cmd = [
        sys.executable,
        str(script_path),
        '--input_file', str(inputs.clinical_file),
        '--enhanced_output_dir', str(ntcp_dir)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


def _run_tcp_analysis(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """
    Run TCP analysis step.

    Phase R2: uses rbgyanx-engine for DICOM + classical TCP when available.
    Falls back to code6 for FDVH/uTCP/CCS/ML or TPS legacy path.
    """
    from rbgyanx.logic.engine_bridge import (
        detect_input_kind,
        is_engine_available,
        needs_subprocess_fallback,
        run_engine_analysis,
    )

    engine_in = inputs.dicom_directory
    if engine_in is None and detect_input_kind(inputs.dvh_directory) == "dicom":
        engine_in = inputs.dvh_directory

    if (
        engine_in
        and engine_in.exists()
        and is_engine_available(inputs.engine_root)
        and not needs_subprocess_fallback(inputs.tcp_config, inputs.ntcp_config)
    ):
        try:
            mode = (inputs.config or {}).get("engine_mode", "basic")
            site = (inputs.config or {}).get("site_override")
            outcome = inputs.patient_data_file if inputs.patient_data_file and str(inputs.patient_data_file).lower().endswith(".csv") else None
            result, logs = run_engine_analysis(
                input_dir=engine_in,
                output_dir=inputs.output_directory,
                endpoint="tcp",
                mode=mode,
                site_override=site,
                outcome_csv=outcome,
                enable_ml=bool((inputs.tcp_config or {}).get("enable_ml")),
                cohort=True,
                engine_root=inputs.engine_root,
            )
            return {
                "logs": logs,
                "error": None if result.exit_code == 0 else f"Engine exit code {result.exit_code}",
                "execution_mode": "engine",
            }
        except Exception as exc:
            return {"logs": [f"Engine TCP failed: {exc}"], "error": str(exc), "execution_mode": "engine"}

    script_path = script_dir / 'code6_tcp_analysis.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    dvh_dir = inputs.output_directory / 'processed_DVH' / 'dDVH_csv'
    output_dir = inputs.output_directory / 'tcp_analysis'
    
    if not dvh_dir.exists():
        return {'error': f'DVH directory not found: {dvh_dir}'}
    
    if not inputs.patient_data_file or not inputs.patient_data_file.exists():
        return {'error': 'Patient data file required for TCP analysis'}
    
    # Check if pipeline can handle this configuration
    tcp_config = inputs.tcp_config or {}
    use_pipeline = True
    
    # Check for advanced options that trigger fallback
    if tcp_config.get('use_fdvh', False):
        use_pipeline = False
    if tcp_config.get('use_utcp', False):
        use_pipeline = False
    if tcp_config.get('ccs_file') is not None:
        use_pipeline = False
    
    # Build command
    cmd = [
        sys.executable,
        str(script_path),
        '--tumor_dvh_dir', str(dvh_dir),
        '--clinical_xlsx', str(inputs.patient_data_file),
        '--outdir', str(output_dir)
    ]
    
    # Add tumor type (required)
    tumor_type = tcp_config.get('tumor_type', 'HNSCC')
    cmd.extend(['--tumor_type', str(tumor_type)])
    
    # Add physical metrics file if provided
    if tcp_config.get('physical_metrics_file'):
        metrics_file = Path(tcp_config['physical_metrics_file'])
        if metrics_file.exists():
            cmd.extend(['--physical_metrics_file', str(metrics_file)])
    
    # Add ML flag if configured
    if tcp_config.get('enable_ml', False):
        cmd.append('--enable_ml')
    
    # Add SHAP flag if configured (requires ML)
    if (tcp_config.get('enable_shap', False) and 
        tcp_config.get('enable_ml', False)):
        cmd.append('--enable_shap')
    
    # Advanced options that trigger fallback (documented but not used in pipeline path)
    if tcp_config.get('use_fdvh', False):
        cmd.append('--use_fdvh')
        if tcp_config.get('n_fractions'):
            cmd.extend(['--n_fractions', str(tcp_config['n_fractions'])])
        if tcp_config.get('alpha_beta_tumor'):
            cmd.extend(['--alpha_beta_tumor', str(tcp_config['alpha_beta_tumor'])])
    
    if tcp_config.get('use_utcp', False):
        cmd.append('--use_utcp')
    
    if tcp_config.get('ccs_file'):
        ccs_file = Path(tcp_config['ccs_file'])
        if ccs_file.exists():
            cmd.extend(['--ccs_file', str(ccs_file)])
            if tcp_config.get('ccs_threshold') is not None:
                cmd.extend(['--ccs_threshold', str(tcp_config['ccs_threshold'])])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}',
            'execution_mode': 'pipeline' if use_pipeline else 'subprocess'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


def _run_integration(inputs: PipelineInput, script_dir: Path, timeout: int) -> Dict[str, Any]:
    """Run TCP/NTCP integration step."""
    script_path = script_dir / 'code7_tcp_ntcp_integration.py'
    if not script_path.exists():
        return {'error': f'Script not found: {script_path}'}
    
    tcp_dir = inputs.output_directory / 'tcp_analysis'
    ntcp_dir = inputs.output_directory / 'ntcp_analysis'
    output_dir = inputs.output_directory / 'integration'
    
    if not tcp_dir.exists():
        return {'error': f'TCP directory not found: {tcp_dir}'}
    if not ntcp_dir.exists():
        return {'error': f'NTCP directory not found: {ntcp_dir}'}
    
    cmd = [
        sys.executable,
        str(script_path),
        '--tcp_dir', str(tcp_dir),
        '--ntcp_dir', str(ntcp_dir),
        '--output_dir', str(output_dir)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=timeout
        )
        
        logs = []
        if result.stdout:
            logs.extend(result.stdout.split('\n'))
        if result.stderr:
            logs.extend([f"STDERR: {line}" for line in result.stderr.split('\n') if line.strip()])
        
        return {
            'logs': logs,
            'error': None if result.returncode == 0 else f'Exit code: {result.returncode}'
        }
    except subprocess.TimeoutExpired:
        return {'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'error': str(e)}


# Export main function
__all__ = ['PipelineInput', 'PipelineOutput', 'run_analysis_pipeline']

