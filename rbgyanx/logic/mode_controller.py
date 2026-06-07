"""
rbgyanx.logic.mode_controller - Mode Governance Layer

This module provides mode governance for rbGyanX, enforcing BASIC vs ADVANCED
operating contracts.

Layer 2 (Logic) Responsibilities:
- Mode governance and capability exposure
- Decision-support-only behavior enforcement (BASIC mode)
- Conservative defaults
- Explicit intent handling

    Phase 5: BASIC mode fully implemented. ADVANCED mode exists as placeholder
    (scaffolding) with UI scaffolding, but no features enabled yet.

Author: rbGyanX Team
Version: 1.0.0
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid


class RunMode(Enum):
    """
    Operating modes for rbGyanX.
    
    Mode is an operating contract, not a feature switch.
    - BASIC: Governed clinical + academic decision support
    - ADVANCED: Explicit research / experimental intent (placeholder in Phase 4)
    """
    BASIC = "basic"
    ADVANCED = "advanced"  # Placeholder - no features enabled in Phase 4
    
    def __str__(self):
        return self.value.upper()


@dataclass
class Capability:
    """
    A capability that can be enabled/disabled by mode.
    
    Phase 4: All capabilities are disabled (scaffolding only).
    """
    name: str
    description: str
    risk_level: str  # "low", "medium", "high"
    requires_mode: RunMode


# Define all capabilities upfront (Phase 4: All disabled)
CAPABILITIES: Dict[str, Capability] = {
    "applicability_override": Capability(
        name="Applicability Override",
        description="Allow biological calculation outside validated domains",
        risk_level="high",
        requires_mode=RunMode.ADVANCED
    ),
    "parameter_sweep": Capability(
        name="Parameter Sweep",
        description="Vary biological parameters systematically",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "model_comparison": Capability(
        name="Model Comparison",
        description="Run multiple models side-by-side",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "developer_mode": Capability(
        name="Developer Mode",
        description="Experimental modification environment",
        risk_level="high",
        requires_mode=RunMode.ADVANCED
    ),
    "sensitivity_analysis": Capability(
        name="Sensitivity Analysis",
        description="Parameter sensitivity and stability analysis (no optimization, no rankings)",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "uncertainty_decomposition": Capability(
        name="Uncertainty Decomposition",
        description="Explicit decomposition of uncertainty sources (attribution, not aggregation)",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "robustness_analysis": Capability(
        name="Robustness Analysis",
        description="Robustness and stability indices quantifying resilience to perturbations (no ranking, no recommendations)",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "applicability_boundary": Capability(
        name="Applicability Boundary Detection",
        description="Detection and visualization of model applicability boundaries and extrapolation zones (no blocking, no recommendations)",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED
    ),
    "benchmark_integration": Capability(
        name="Benchmark Integration",
        description="Read-only DICOM data import and literature benchmark integration (QUANTEC, RTOG, ESTRO, ICRU) as contextual reference only (no enforcement, no pass/fail)",
        risk_level="low",
        requires_mode=RunMode.ADVANCED
    ),
    "protocol_stress_testing": Capability(
        name="Protocol Stress-Testing Sandbox",
        description="Treat clinical protocols as scientific objects for assumption perturbation and robustness exploration (no enforcement, no accept/reject logic, no clinical recommendations)",
        risk_level="high",
        requires_mode=RunMode.ADVANCED
    ),
    "ai_integration": Capability(
        name="AI Integration (Ask rbGyanX)",
        description="Explanation-only AI (ADVANCED mode only). No recommendations, no actions, no rankings, no automation. Disabled in BASIC clinic mode.",
        risk_level="medium",
        requires_mode=RunMode.ADVANCED,
    ),
    "education_training": Capability(
        name="Education & Training Workflows",
        description="Teaching overlays, structured learning paths, and demonstrations of non-intuitive radiobiological behavior (plateaus, cliffs, fragility). No scoring, no recommendations, no pass/fail logic",
        risk_level="low",
        requires_mode=None  # Available in both modes
    ),
    "publication_provenance": Capability(
        name="Publication & Provenance Toolkit",
        description="Journal-ready exports, deterministic replay, provenance bundles, and reviewer auditability. No new scientific analysis, no new AI behavior, no UI redesign",
        risk_level="low",
        requires_mode=None  # Available in both modes
    ),
}

# Capability exposure map (Phase 4: All False - scaffolding only)
CAPABILITY_EXPOSURE: Dict[RunMode, Dict[str, bool]] = {
    RunMode.BASIC: {
        "applicability_override": False,
        "parameter_sweep": False,
        "model_comparison": False,
        "developer_mode": False,
        "sensitivity_analysis": False,
        "uncertainty_decomposition": False,
        "robustness_analysis": False,
        "applicability_boundary": False,
        "benchmark_integration": False,
        "protocol_stress_testing": False,
        "ai_integration": False,  # Clinic BASIC: no LLM / Ask rbGyanX (product decision 2026-05)
        "education_training": True,  # Phase 11: Enabled for Education & Training Workflows
        "publication_provenance": True,  # Phase 12: Enabled for Publication & Provenance Toolkit
    },
    RunMode.ADVANCED: {
        # Phase 6.1: model_comparison enabled
        # Phase 6.2: sensitivity_analysis enabled
        # Phase 6.3: uncertainty_decomposition enabled
        # Phase 6.4: robustness_analysis enabled
        # Phase 6.5: applicability_boundary enabled
        # Phase 7: developer_mode enabled
        # Phase 8: benchmark_integration enabled
        # Phase 9: protocol_stress_testing enabled
        # Phase 10: ai_integration enabled with ADVANCED personality (exploratory)
        "applicability_override": False,
        "parameter_sweep": False,
        "model_comparison": True,  # Phase 6.1: Enabled for Model Agreement/Disagreement Analysis
        "developer_mode": True,  # Phase 7: Enabled for Developer Mode (Governed)
        "sensitivity_analysis": True,  # Phase 6.2: Enabled for Parameter Sensitivity & Stability Analysis
        "uncertainty_decomposition": True,  # Phase 6.3: Enabled for Uncertainty Decomposition
        "robustness_analysis": True,  # Phase 6.4: Enabled for Robustness & Stability Indices
        "applicability_boundary": True,  # Phase 6.5: Enabled for Applicability Boundary Detection
        "benchmark_integration": True,  # Phase 8: Enabled for Data & Benchmark Integration
        "protocol_stress_testing": True,  # Phase 9: Enabled for Protocol Stress-Testing Sandbox
        "ai_integration": True,  # Phase 10: Enabled with ADVANCED personality (exploratory)
        "education_training": True,  # Phase 11: Enabled for Education & Training Workflows
        "publication_provenance": True,  # Phase 12: Enabled for Publication & Provenance Toolkit
    }
}


class ModeController:
    """
    Governs rbGyanX operating mode and capability exposure.
    
    The ModeController enforces ethical and scientific separation
    between clinical (BASIC) and research (ADVANCED) intent.
    
    Design Principles:
    - Mode is immutable per session
    - Capabilities are declarative, not procedural
    - All mode checks must go through this controller
    - No silent mode changes
    
    Phase 4: BASIC mode fully implemented. ADVANCED mode exists as
    placeholder but no features enabled.
    """
    
    def __init__(self, mode: RunMode = RunMode.BASIC):
        """
        Initialize mode controller.
        
        Parameters
        ----------
        mode : RunMode
            Operating mode for this session (defaults to BASIC)
        """
        self._mode = mode
        self._capabilities = CAPABILITY_EXPOSURE[mode].copy()
        self._session_id = self._generate_session_id()
        self._initialization_time = datetime.now()
        
    @property
    def mode(self) -> RunMode:
        """
        Get current operating mode (immutable).
        
        Returns
        -------
        RunMode
            Current operating mode
        """
        return self._mode
    
    def get_mode(self) -> RunMode:
        """
        Get current operating mode (alias for mode property).
        
        Returns
        -------
        RunMode
            Current operating mode
        """
        return self._mode
    
    def is_basic(self) -> bool:
        """
        Check if running in BASIC mode.
        
        Returns
        -------
        bool
            True if in BASIC mode
        """
        return self._mode == RunMode.BASIC
    
    def is_advanced(self) -> bool:
        """
        Check if running in ADVANCED mode.
        
        Returns
        -------
        bool
            True if in ADVANCED mode
            
        Note: Phase 4 - ADVANCED mode exists as placeholder only.
        """
        return self._mode == RunMode.ADVANCED
    
    def assert_basic(self):
        """
        Assert that current mode is BASIC.
        
        Raises
        ------
        ModeError
            If not in BASIC mode
        """
        if not self.is_basic():
            raise ModeError(
                "This operation requires BASIC mode. "
                f"Current mode: {self._mode.value.upper()}"
            )
    
    def assert_advanced(self):
        """
        Assert that current mode is ADVANCED.
        
        Raises
        ------
        ModeError
            If not in ADVANCED mode
            
        Note: Phase 4 - ADVANCED mode exists as placeholder only.
        """
        if not self.is_advanced():
            raise ModeError(
                "This operation requires ADVANCED mode. "
                f"Current mode: {self._mode.value.upper()}"
            )
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Get current capability exposure map.
        
        Returns
        -------
        Dict[str, bool]
            Dictionary mapping capability names to enabled status
            
        Note: Phase 4 - All capabilities are False (scaffolding only).
        """
        return self._capabilities.copy()
    
    def is_capability_enabled(self, capability: str) -> bool:
        """
        Check if a specific capability is enabled.
        
        Parameters
        ----------
        capability : str
            Capability name
            
        Returns
        -------
        bool
            True if enabled, False otherwise
            
        Raises
        ------
        KeyError
            If capability name is unknown
            
        Note: Phase 4 - All capabilities return False (scaffolding only).
        """
        if capability not in self._capabilities:
            raise KeyError(f"Unknown capability: {capability}")
        return self._capabilities[capability]
    
    def get_contract_message(self) -> str:
        """
        Get the operating contract message for current mode.
        
        Returns
        -------
        str
            Human-readable contract description
        """
        if self.is_basic():
            return (
                "BASIC Mode: Governed clinical and academic decision support. "
                "All analyses are constrained by validated applicability rules. "
                "Decision-support-only behavior enforced."
            )
        else:
            return (
                "ADVANCED Mode: Research and experimental environment. "
                "Results are exploratory and non-clinical. "
                "(Phase 4: Placeholder - no features enabled yet)"
            )
    
    def get_session_metadata(self) -> Dict:
        """
        Get session metadata for provenance.
        
        Returns
        -------
        Dict
            Session metadata including mode, capabilities, and timing
        """
        return {
            "session_id": self._session_id,
            "mode": self._mode.value,
            "initialization_time": self._initialization_time.isoformat(),
            "capabilities": self.get_capabilities()
        }
    
    def get_conservative_defaults(self) -> Dict[str, any]:
        """
        Get conservative defaults for BASIC mode.
        
        Returns
        -------
        Dict[str, any]
            Dictionary of conservative default values
            
        Phase 4: BASIC mode uses conservative defaults for decision-support.
        """
        return {
            "biological_model": "lq",  # Linear-Quadratic (most validated)
            "alpha_beta_ratio": 10.0,  # Conservative default
            "enable_ml": False,  # Conservative: ML disabled by default
            "enable_shap": False,  # Requires ML
            "use_fdvh": False,  # Conservative: Standard DVH
            "use_utcp": False,  # Conservative: Standard TCP
            "use_ccs": False,  # Conservative: No CCS gating
        }
    
    def enforce_decision_support_only(self) -> bool:
        """
        Enforce decision-support-only behavior (BASIC mode requirement).
        
        Returns
        -------
        bool
            True if decision-support-only behavior is enforced
            
        Phase 4: BASIC mode enforces decision-support-only behavior.
        This means:
        - No automation
        - No rankings
        - No "best plan" outputs
        - No recommendations
        - Conditional radiobiology only
        - Model applicability gates enforced
        - Conservative defaults applied
        """
        return self.is_basic()
    
    def check_decision_support_violation(self, operation: str) -> Optional[str]:
        """
        Check if an operation violates decision-support-only behavior.
        
        Parameters
        ----------
        operation : str
            Operation name to check
            
        Returns
        -------
        Optional[str]
            Warning message if violation detected, None otherwise
            
        Phase 4: BASIC mode checks for violations of decision-support-only behavior.
        """
        if not self.enforce_decision_support_only():
            return None
        
        # List of operations that violate decision-support-only
        violations = {
            'automation': 'Automation not permitted in BASIC mode (decision-support-only)',
            'ranking': 'Plan ranking not permitted in BASIC mode (decision-support-only)',
            'best_plan': '"Best plan" selection not permitted in BASIC mode (decision-support-only)',
            'recommendation': 'Clinical recommendations not permitted in BASIC mode (decision-support-only)',
            'optimization': 'Dose optimization not permitted in BASIC mode (decision-support-only)',
        }
        
        return violations.get(operation.lower())
    
    def get_explicit_intent(self) -> Dict[str, any]:
        """
        Get explicit intent declaration for current mode.
        
        Returns
        -------
        Dict[str, any]
            Explicit intent declaration
            
        Phase 4: BASIC mode declares explicit decision-support intent.
        """
        if self.is_basic():
            return {
                'intent': 'decision_support',
                'purpose': 'clinical_and_academic_decision_support',
                'scope': 'governed_clinical_evaluation',
                'constraints': [
                    'validated_applicability_rules',
                    'conservative_defaults',
                    'no_automation',
                    'no_rankings',
                    'no_recommendations'
                ],
                'regulatory_defensibility': 'high',
                'clinical_use': 'permitted'
            }
        else:
            return {
                'intent': 'research',
                'purpose': 'experimental_research',
                'scope': 'non_clinical_exploration',
                'constraints': [],
                'regulatory_defensibility': 'not_intended',
                'clinical_use': 'prohibited'
            }
    
    @staticmethod
    def _generate_session_id() -> str:
        """
        Generate unique session identifier.
        
        Returns
        -------
        str
            Unique session ID
        """
        return f"rbgyanx-{uuid.uuid4().hex[:12]}"


class ModeError(Exception):
    """Raised when mode requirements are violated."""
    pass


__all__ = [
    'RunMode',
    'Capability',
    'CAPABILITIES',
    'CAPABILITY_EXPOSURE',
    'ModeController',
    'ModeError'
]

