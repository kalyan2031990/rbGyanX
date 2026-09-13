"""
Layer 2: Orchestration & Governance
===================================

Orchestration layer for rbGyanX analysis pipeline.

Allowed Dependencies:
- rbgyanx.core
- Standard library

Forbidden Dependencies:
- UI frameworks
- Direct plotting (returns data for plotting)

Responsibilities:
- Pipeline orchestration
- Model applicability checks
- Conditional physical vs biological branching
- QA-driven flow control
- Central execution sequencing
- Mode-aware capability gating (future)
"""

# Phase 10: Import AI integration
from rbgyanx.logic.ai_integration import (
    AIInteractionType,
    AIPersonality,
    AIPersonalityProfile,
    AIResponse,
    AskRbGyanXIntegration,
)

# Phase 3: Import applicability checking
from rbgyanx.logic.applicability import (
    ApplicabilityChecker,
    ApplicabilityResult,
    ApplicabilityWarning,
    BiologicalModel,
    TreatmentTechnique,
)

# Phase 6.5: Import applicability boundary detection
from rbgyanx.logic.applicability_boundary import (
    ApplicabilityBoundary,
    ApplicabilityBoundaryDetector,
    ApplicabilityBoundaryResult,
    BoundaryType,
    ExtrapolationZone,
)

# Phase 8: Import benchmark integration
from rbgyanx.logic.benchmark_integration import (
    BenchmarkComparison,
    BenchmarkIntegration,
    BenchmarkIntegrationResult,
    BenchmarkReference,
    BenchmarkSource,
    DICOMImporter,
)

# Phase 7: Import developer mode
from rbgyanx.logic.developer_mode import (
    DeveloperModeSandbox,
    DeveloperModeSession,
    DeveloperModification,
    ScientificIntentMetadata,
)

# Phase 11: Import education & training
from rbgyanx.logic.education_training import (
    CliffRegion,
    EducationTrainingResult,
    EducationTrainingWorkflow,
    FragilityZone,
    LearningPathStep,
    LearningTopic,
    NonIntuitiveBehaviorDemo,
    PlateauRegion,
    StructuredLearningPath,
    TeachingOverlay,
    TeachingOverlayType,
)

# Phase 4: Import mode controller
from rbgyanx.logic.mode_controller import (
    Capability,
    ModeController,
    ModeError,
    RunMode,
)

# Phase 6.1: Import model agreement analysis
from rbgyanx.logic.model_agreement import (
    ModelAgreementAnalyzer,
    ModelAgreementResult,
)
from rbgyanx.logic.pipeline import (
    PipelineInput,
    PipelineOutput,
    run_analysis_pipeline,
)

# Phase 9: Import protocol stress-testing
from rbgyanx.logic.protocol_stress_testing import (
    FragileProtocolRegion,
    ProtocolAssumption,
    ProtocolComponent,
    ProtocolPerturbation,
    ProtocolStressTestingSandbox,
    ProtocolStressTestResult,
)

# Phase 2: Import provenance and structured logging
from rbgyanx.logic.provenance import (
    ProvenanceRecord,
    ProvenanceTracker,
    create_provenance_record,
)

# Phase 12: Import publication & provenance toolkit
from rbgyanx.logic.publication_provenance import (
    JournalExport,
    ProvenanceBundle,
    PublicationProvenanceToolkit,
    ReplayConfiguration,
)

# Phase 6.4: Import robustness analysis
from rbgyanx.logic.robustness_analysis import (
    RobustnessAnalysisResult,
    RobustnessAnalyzer,
    RobustnessIndex,
)

# Phase 6.2: Import sensitivity analysis
from rbgyanx.logic.sensitivity_analysis import (
    SensitivityAnalyzer,
    SensitivityResult,
    StabilityAnalysisResult,
)
from rbgyanx.logic.structured_logging import (
    LogCategory,
    LogEntry,
    LogLevel,
    StructuredLogger,
)

# Phase 6.3: Import uncertainty decomposition
from rbgyanx.logic.uncertainty_decomposition import (
    UncertaintyComponent,
    UncertaintyDecomposer,
    UncertaintyDecompositionResult,
    UncertaintySource,
    UncertaintyType,
)

# Validation Controller: Import validation controller
from rbgyanx.logic.validation_controller import (
    ValidationController,
    ValidationProfile,
)

__all__ = [
    'PipelineInput',
    'PipelineOutput',
    'run_analysis_pipeline',
    # Phase 2 exports
    'ProvenanceRecord',
    'ProvenanceTracker',
    'create_provenance_record',
    'LogLevel',
    'LogCategory',
    'LogEntry',
    'StructuredLogger',
    # Phase 3 exports
    'TreatmentTechnique',
    'BiologicalModel',
    'ApplicabilityWarning',
    'ApplicabilityResult',
    'ApplicabilityChecker',
    # Phase 4 exports
    'RunMode',
    'Capability',
    'ModeController',
    'ModeError',
    # Phase 6.1 exports
    'ModelAgreementResult',
    'ModelAgreementAnalyzer',
    # Phase 6.2 exports
    'SensitivityResult',
    'StabilityAnalysisResult',
    'SensitivityAnalyzer',
    # Phase 6.3 exports
    'UncertaintyType',
    'UncertaintySource',
    'UncertaintyComponent',
    'UncertaintyDecompositionResult',
    'UncertaintyDecomposer',
    # Phase 6.4 exports
    'RobustnessIndex',
    'RobustnessAnalysisResult',
    'RobustnessAnalyzer',
    # Phase 6.5 exports
    'BoundaryType',
    'ApplicabilityBoundary',
    'ExtrapolationZone',
    'ApplicabilityBoundaryResult',
    'ApplicabilityBoundaryDetector',
    # Phase 7 exports
    'ScientificIntentMetadata',
    'DeveloperModification',
    'DeveloperModeSession',
    'DeveloperModeSandbox',
    # Phase 8 exports
    'BenchmarkSource',
    'BenchmarkReference',
    'BenchmarkComparison',
    'BenchmarkIntegrationResult',
    'BenchmarkIntegration',
    'DICOMImporter',
    # Phase 9 exports
    'ProtocolComponent',
    'ProtocolAssumption',
    'ProtocolPerturbation',
    'FragileProtocolRegion',
    'ProtocolStressTestResult',
    'ProtocolStressTestingSandbox',
    # Phase 10 exports
    'AIPersonality',
    'AIInteractionType',
    'AIResponse',
    'AIPersonalityProfile',
    'AskRbGyanXIntegration',
    # Phase 11 exports
    'LearningTopic',
    'TeachingOverlayType',
    'PlateauRegion',
    'CliffRegion',
    'FragilityZone',
    'TeachingOverlay',
    'LearningPathStep',
    'StructuredLearningPath',
    'NonIntuitiveBehaviorDemo',
    'EducationTrainingResult',
    'EducationTrainingWorkflow',
    # Phase 12 exports
    'ReplayConfiguration',
    'ProvenanceBundle',
    'JournalExport',
    'PublicationProvenanceToolkit',
    # Validation Controller exports
    'ValidationProfile',
    'ValidationController',
]

