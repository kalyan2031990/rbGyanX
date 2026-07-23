"""
rbgyanx.logic.protocol_stress_testing - Protocol Stress-Testing Sandbox

This module provides a sandbox that treats clinical protocols as scientific
objects for assumption perturbation and robustness exploration.

Phase 9: ADVANCED mode only. Research only - no enforcement, no accept/reject
logic, no clinical recommendations.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
from enum import Enum
import copy


class ProtocolComponent(Enum):
    """Protocol components that can be stress-tested."""
    FRACTIONATION = "fractionation"  # Dose per fraction, number of fractions
    DOSE_CONSTRAINTS = "dose_constraints"  # Dose limits for OARs
    COVERAGE_REQUIREMENTS = "coverage_requirements"  # Target coverage requirements
    PARAMETER_ASSUMPTIONS = "parameter_assumptions"  # Biological parameter assumptions
    THRESHOLD_VALUES = "threshold_values"  # Protocol threshold values


@dataclass
class ProtocolAssumption:
    """
    A protocol assumption that can be perturbed.
    
    Phase 9: Scientific object for exploration - no enforcement, no recommendations.
    """
    component: ProtocolComponent
    parameter_name: str
    baseline_value: float
    assumption_description: str
    perturbation_range: Optional[Tuple[float, float]] = None
    contextual_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'component': self.component.value,
            'parameter_name': self.parameter_name,
            'baseline_value': self.baseline_value,
            'assumption_description': self.assumption_description,
            'perturbation_range': list(self.perturbation_range) if self.perturbation_range else None,
            'contextual_notes': self.contextual_notes
        }


@dataclass
class ProtocolPerturbation:
    """
    A single protocol perturbation scenario.
    
    Phase 9: Scientific exploration only - no enforcement, no recommendations.
    """
    perturbation_id: str
    assumption: ProtocolAssumption
    perturbed_value: float
    perturbation_magnitude: float  # Relative change from baseline
    stability_indicators: List[str] = field(default_factory=list)
    robustness_metrics: Dict[str, float] = field(default_factory=dict)
    exploratory_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'perturbation_id': self.perturbation_id,
            'assumption': self.assumption.to_dict(),
            'perturbed_value': self.perturbed_value,
            'perturbation_magnitude': self.perturbation_magnitude,
            'stability_indicators': self.stability_indicators,
            'robustness_metrics': self.robustness_metrics,
            'exploratory_notes': self.exploratory_notes
        }


@dataclass
class FragileProtocolRegion:
    """
    A fragile protocol region identified through stress-testing.
    
    Phase 9: Descriptive only - no enforcement, no recommendations.
    """
    region_name: str
    component: ProtocolComponent
    description: str
    sensitivity_indicators: List[str] = field(default_factory=list)
    exploration_summary: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'region_name': self.region_name,
            'component': self.component.value,
            'description': self.description,
            'sensitivity_indicators': self.sensitivity_indicators,
            'exploration_summary': self.exploration_summary
        }


@dataclass
class ProtocolStressTestResult:
    """
    Result of protocol stress-testing (exploratory only).
    
    Phase 9: Research only - no enforcement, no accept/reject logic, no clinical recommendations.
    """
    protocol_name: str
    assumptions: List[ProtocolAssumption] = field(default_factory=list)
    perturbations: List[ProtocolPerturbation] = field(default_factory=list)
    fragile_regions: List[FragileProtocolRegion] = field(default_factory=list)
    exploration_summary: List[str] = field(default_factory=list)
    disclaimer: str = "RESEARCH ONLY - No enforcement, no accept/reject logic, no clinical recommendations"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'protocol_name': self.protocol_name,
            'assumptions': [a.to_dict() for a in self.assumptions],
            'perturbations': [p.to_dict() for p in self.perturbations],
            'fragile_regions': [r.to_dict() for r in self.fragile_regions],
            'exploration_summary': self.exploration_summary,
            'disclaimer': self.disclaimer
        }


class ProtocolStressTestingSandbox:
    """
    Sandbox for protocol stress-testing and robustness exploration.
    
    Phase 9: ADVANCED mode only. Treats clinical protocols as scientific objects.
    Research only - no enforcement, no accept/reject logic, no clinical recommendations.
    
    Design Principles:
    - Protocols treated as scientific objects
    - Assumption perturbation for exploration
    - Robustness exploration
    - Fragile region identification
    - No enforcement or constraints
    - No accept/reject logic
    - No clinical recommendations
    """
    
    def __init__(self):
        """Initialize protocol stress-testing sandbox."""
        self.disclaimer = "RESEARCH ONLY - No enforcement, no accept/reject logic, no clinical recommendations"
    
    def register_protocol_assumptions(
        self,
        protocol_name: str,
        assumptions: List[ProtocolAssumption]
    ) -> List[ProtocolAssumption]:
        """
        Register protocol assumptions for stress-testing.
        
        Parameters
        ----------
        protocol_name : str
            Protocol name
        assumptions : List[ProtocolAssumption]
            List of protocol assumptions
            
        Returns
        -------
        List[ProtocolAssumption]
            Registered assumptions (for exploration only)
        """
        # Add disclaimer to all assumptions
        for assumption in assumptions:
            assumption.contextual_notes.append(self.disclaimer)
        
        return assumptions
    
    def perturb_assumption(
        self,
        assumption: ProtocolAssumption,
        perturbed_value: float,
        perturbation_id: Optional[str] = None
    ) -> ProtocolPerturbation:
        """
        Create a protocol perturbation scenario.
        
        Parameters
        ----------
        assumption : ProtocolAssumption
            Protocol assumption to perturb
        perturbed_value : float
            Perturbed value
        perturbation_id : Optional[str]
            Perturbation ID (generated if not provided)
            
        Returns
        -------
        ProtocolPerturbation
            Perturbation scenario (exploratory only, no enforcement)
        """
        if perturbation_id is None:
            perturbation_id = f"perturb_{assumption.parameter_name}_{datetime.now().timestamp()}"
        
        # Calculate perturbation magnitude
        if assumption.baseline_value != 0:
            perturbation_magnitude = (perturbed_value - assumption.baseline_value) / assumption.baseline_value
        else:
            perturbation_magnitude = 0.0
        
        # Build stability indicators (descriptive only)
        stability_indicators = []
        stability_indicators.append(f"Baseline: {assumption.baseline_value}, Perturbed: {perturbed_value}")
        stability_indicators.append(f"Relative change: {perturbation_magnitude:.2%}")
        
        # Build exploratory notes (no enforcement, no recommendations)
        exploratory_notes = []
        exploratory_notes.append(self.disclaimer)
        exploratory_notes.append(f"Perturbation of {assumption.parameter_name} for exploration only")
        exploratory_notes.append("No enforcement, no accept/reject logic, no clinical recommendations")
        
        return ProtocolPerturbation(
            perturbation_id=perturbation_id,
            assumption=assumption,
            perturbed_value=perturbed_value,
            perturbation_magnitude=perturbation_magnitude,
            stability_indicators=stability_indicators,
            robustness_metrics={},
            exploratory_notes=exploratory_notes
        )
    
    def explore_edge_cases(
        self,
        assumption: ProtocolAssumption,
        perturbation_values: List[float]
    ) -> List[ProtocolPerturbation]:
        """
        Explore edge cases for a protocol assumption.
        
        Parameters
        ----------
        assumption : ProtocolAssumption
            Protocol assumption to explore
        perturbation_values : List[float]
            List of perturbation values to test
            
        Returns
        -------
        List[ProtocolPerturbation]
            List of perturbation scenarios (exploratory only)
        """
        perturbations = []
        
        for i, value in enumerate(perturbation_values):
            perturbation = self.perturb_assumption(
                assumption,
                value,
                perturbation_id=f"edge_case_{assumption.parameter_name}_{i}"
            )
            perturbations.append(perturbation)
        
        return perturbations
    
    def identify_fragile_regions(
        self,
        perturbations: List[ProtocolPerturbation],
        sensitivity_threshold: float = 0.1
    ) -> List[FragileProtocolRegion]:
        """
        Identify fragile protocol regions based on perturbation results.
        
        Parameters
        ----------
        perturbations : List[ProtocolPerturbation]
            List of perturbations to analyze
        sensitivity_threshold : float
            Threshold for identifying fragile regions (relative change)
            
        Returns
        -------
        List[FragileProtocolRegion]
            Fragile regions (descriptive only, no enforcement)
        """
        fragile_regions = []
        
        # Group perturbations by component
        component_perturbations: Dict[ProtocolComponent, List[ProtocolPerturbation]] = {}
        for pert in perturbations:
            component = pert.assumption.component
            if component not in component_perturbations:
                component_perturbations[component] = []
            component_perturbations[component].append(pert)
        
        # Identify fragile regions
        for component, pert_list in component_perturbations.items():
            # Check for high sensitivity
            high_sensitivity = [
                p for p in pert_list
                if abs(p.perturbation_magnitude) > sensitivity_threshold
            ]
            
            if high_sensitivity:
                region = FragileProtocolRegion(
                    region_name=f"{component.value}_fragile_region",
                    component=component,
                    description=f"Fragile region identified in {component.value} (exploratory only)",
                    sensitivity_indicators=[
                        f"{len(high_sensitivity)} perturbations with sensitivity > {sensitivity_threshold:.1%}",
                        self.disclaimer
                    ],
                    exploration_summary=[
                        f"High sensitivity detected in {component.value}",
                        "Descriptive only - no enforcement, no recommendations"
                    ]
                )
                fragile_regions.append(region)
        
        return fragile_regions
    
    def test_guideline_sensitivity(
        self,
        protocol_name: str,
        assumptions: List[ProtocolAssumption],
        perturbation_scenarios: List[Dict[str, float]]
    ) -> ProtocolStressTestResult:
        """
        Test guideline sensitivity through assumption perturbation.
        
        Parameters
        ----------
        protocol_name : str
            Protocol name
        assumptions : List[ProtocolAssumption]
            Protocol assumptions
        perturbation_scenarios : List[Dict[str, float]]
            List of perturbation scenarios (dict mapping parameter names to values)
            
        Returns
        -------
        ProtocolStressTestResult
            Stress-test results (exploratory only, no enforcement)
        """
        # Register assumptions
        registered_assumptions = self.register_protocol_assumptions(protocol_name, assumptions)
        
        # Create perturbations
        perturbations = []
        for scenario in perturbation_scenarios:
            for param_name, perturbed_value in scenario.items():
                # Find matching assumption
                assumption = next(
                    (a for a in registered_assumptions if a.parameter_name == param_name),
                    None
                )
                if assumption:
                    perturbation = self.perturb_assumption(assumption, perturbed_value)
                    perturbations.append(perturbation)
        
        # Identify fragile regions
        fragile_regions = self.identify_fragile_regions(perturbations)
        
        # Build exploration summary
        exploration_summary = [
            f"Protocol stress-testing: {protocol_name}",
            f"Assumptions tested: {len(registered_assumptions)}",
            f"Perturbations explored: {len(perturbations)}",
            f"Fragile regions identified: {len(fragile_regions)}",
            self.disclaimer,
            "Research only - no enforcement, no accept/reject logic, no clinical recommendations"
        ]
        
        return ProtocolStressTestResult(
            protocol_name=protocol_name,
            assumptions=registered_assumptions,
            perturbations=perturbations,
            fragile_regions=fragile_regions,
            exploration_summary=exploration_summary
        )


__all__ = [
    'ProtocolComponent',
    'ProtocolAssumption',
    'ProtocolPerturbation',
    'FragileProtocolRegion',
    'ProtocolStressTestResult',
    'ProtocolStressTestingSandbox'
]

