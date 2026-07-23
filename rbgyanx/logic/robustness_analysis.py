"""
rbgyanx.logic.robustness_analysis - Robustness & Stability Indices

This module provides robustness and stability indices that quantify resilience
to perturbations for TCP/NTCP models.

Phase 6.4: ADVANCED mode only. Stability characterization only.
No ranking outcomes, no recommending actions - only stability quantification.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
import pandas as pd
import numpy as np
from pathlib import Path


@dataclass
class RobustnessIndex:
    """
    Individual robustness index.
    
    Phase 6.4: Stability characterization only. No ranking, no recommendations.
    """
    index_name: str
    index_value: float
    interpretation: str
    perturbation_type: str
    stability_level: str  # "high", "medium", "low", "brittle"
    attribution_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'index_name': self.index_name,
            'index_value': self.index_value,
            'interpretation': self.interpretation,
            'perturbation_type': self.perturbation_type,
            'stability_level': self.stability_level,
            'attribution_details': self.attribution_details
        }


@dataclass
class RobustnessAnalysisResult:
    """
    Result of robustness and stability analysis.
    
    Phase 6.4: Stability characterization only. No ranking, no recommendations.
    """
    robustness_indices: List[RobustnessIndex] = field(default_factory=list)
    stability_metrics: Dict[str, float] = field(default_factory=dict)
    brittleness_indicators: List[Dict[str, Any]] = field(default_factory=list)
    resilience_profiles: Dict[str, Any] = field(default_factory=dict)
    perturbation_responses: Dict[str, List[float]] = field(default_factory=dict)
    stability_summary: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'robustness_indices': [idx.to_dict() for idx in self.robustness_indices],
            'stability_metrics': self.stability_metrics,
            'brittleness_indicators': self.brittleness_indicators,
            'resilience_profiles': self.resilience_profiles,
            'perturbation_responses': {k: v for k, v in self.perturbation_responses.items()},
            'stability_summary': self.stability_summary
        }


class RobustnessAnalyzer:
    """
    Analyzes robustness and stability of TCP/NTCP models.
    
    Phase 6.4: ADVANCED mode only. Quantifies resilience to perturbations.
    No ranking outcomes, no recommending actions - only stability characterization.
    
    Design Principles:
    - Compare stability, not outcomes
    - Quantify fragility
    - Highlight brittle plans/models
    - Stability characterization only (no ranking)
    """
    
    def __init__(self):
        """Initialize robustness analyzer."""
        pass
    
    def calculate_bri(
        self,
        baseline_result: float,
        perturbed_results: List[float],
        perturbation_magnitude: float
    ) -> RobustnessIndex:
        """
        Calculate Biological Robustness Index (BRI).
        
        BRI quantifies how much biological metrics change under parameter perturbations.
        Higher BRI = more robust (less sensitive to perturbations).
        
        Parameters
        ----------
        baseline_result : float
            Baseline model result
        perturbed_results : List[float]
            Model results under perturbations
        perturbation_magnitude : float
            Magnitude of perturbation applied
            
        Returns
        -------
        RobustnessIndex
            BRI index (stability characterization only)
        """
        if not perturbed_results or baseline_result == 0:
            return RobustnessIndex(
                index_name="BRI",
                index_value=0.0,
                interpretation="Cannot calculate BRI (insufficient data or zero baseline)",
                perturbation_type="parameter",
                stability_level="unknown"
            )
        
        # Calculate relative changes
        relative_changes = np.abs(np.array(perturbed_results) - baseline_result) / abs(baseline_result)
        mean_relative_change = np.mean(relative_changes)
        
        # BRI = 1 / (1 + mean_relative_change) - higher is more robust
        # Normalize by perturbation magnitude
        normalized_change = mean_relative_change / (perturbation_magnitude + 1e-10)
        bri_value = 1.0 / (1.0 + normalized_change)
        
        # Determine stability level (descriptive only, not ranking)
        if bri_value >= 0.8:
            stability_level = "high"
            interpretation = "High robustness - model results are stable under perturbations"
        elif bri_value >= 0.5:
            stability_level = "medium"
            interpretation = "Medium robustness - model results show moderate sensitivity"
        elif bri_value >= 0.2:
            stability_level = "low"
            interpretation = "Low robustness - model results are sensitive to perturbations"
        else:
            stability_level = "brittle"
            interpretation = "Brittle - model results are highly sensitive to perturbations"
        
        return RobustnessIndex(
            index_name="BRI",
            index_value=float(bri_value),
            interpretation=interpretation,
            perturbation_type="parameter",
            stability_level=stability_level,
            attribution_details={
                'baseline_result': baseline_result,
                'mean_relative_change': float(mean_relative_change),
                'perturbation_magnitude': perturbation_magnitude,
                'note': 'Stability characterization only - not a ranking or recommendation'
            }
        )
    
    def calculate_tws(
        self,
        baseline_result: float,
        perturbed_results: List[float],
        perturbation_magnitude: float
    ) -> RobustnessIndex:
        """
        Calculate Treatment Window Stability (TWS).
        
        TWS quantifies stability of therapeutic window under perturbations.
        Higher TWS = more stable therapeutic window.
        
        Parameters
        ----------
        baseline_result : float
            Baseline model result
        perturbed_results : List[float]
            Model results under perturbations
        perturbation_magnitude : float
            Magnitude of perturbation applied
            
        Returns
        -------
        RobustnessIndex
            TWS index (stability characterization only)
        """
        if not perturbed_results:
            return RobustnessIndex(
                index_name="TWS",
                index_value=0.0,
                interpretation="Cannot calculate TWS (insufficient data)",
                perturbation_type="parameter",
                stability_level="unknown"
            )
        
        # Calculate coefficient of variation under perturbations
        results_array = np.array(perturbed_results)
        cv = np.std(results_array) / (np.mean(np.abs(results_array)) + 1e-10)
        
        # TWS = 1 / (1 + cv) - higher is more stable
        tws_value = 1.0 / (1.0 + cv)
        
        # Determine stability level (descriptive only)
        if tws_value >= 0.8:
            stability_level = "high"
            interpretation = "High treatment window stability - therapeutic window is stable"
        elif tws_value >= 0.5:
            stability_level = "medium"
            interpretation = "Medium treatment window stability - therapeutic window shows moderate variation"
        elif tws_value >= 0.2:
            stability_level = "low"
            interpretation = "Low treatment window stability - therapeutic window is variable"
        else:
            stability_level = "brittle"
            interpretation = "Brittle treatment window - therapeutic window is highly variable"
        
        return RobustnessIndex(
            index_name="TWS",
            index_value=float(tws_value),
            interpretation=interpretation,
            perturbation_type="parameter",
            stability_level=stability_level,
            attribution_details={
                'baseline_result': baseline_result,
                'coefficient_of_variation': float(cv),
                'perturbation_magnitude': perturbation_magnitude,
                'note': 'Stability characterization only - not a ranking or recommendation'
            }
        )
    
    def analyze_robustness(
        self,
        baseline_result: float,
        perturbed_results: Dict[str, List[float]],
        perturbation_magnitudes: Dict[str, float]
    ) -> RobustnessAnalysisResult:
        """
        Analyze robustness and stability across multiple perturbations.
        
        Parameters
        ----------
        baseline_result : float
            Baseline model result
        perturbed_results : Dict[str, List[float]]
            Dictionary mapping perturbation types to results
        perturbation_magnitudes : Dict[str, float]
            Dictionary mapping perturbation types to magnitudes
            
        Returns
        -------
        RobustnessAnalysisResult
            Robustness analysis results (stability characterization only)
        """
        result = RobustnessAnalysisResult()
        
        # Calculate BRI for each perturbation type
        for pert_type, pert_results in perturbed_results.items():
            pert_magnitude = perturbation_magnitudes.get(pert_type, 0.1)
            
            # Calculate BRI
            bri = self.calculate_bri(baseline_result, pert_results, pert_magnitude)
            result.robustness_indices.append(bri)
            
            # Calculate TWS
            tws = self.calculate_tws(baseline_result, pert_results, pert_magnitude)
            result.robustness_indices.append(tws)
            
            # Store perturbation responses
            result.perturbation_responses[pert_type] = pert_results
        
        # Calculate overall stability metrics
        result.stability_metrics = self._calculate_stability_metrics(
            baseline_result, perturbed_results
        )
        
        # Identify brittleness indicators
        result.brittleness_indicators = self._identify_brittleness(
            result.robustness_indices
        )
        
        # Build resilience profiles
        result.resilience_profiles = self._build_resilience_profiles(
            result.robustness_indices
        )
        
        # Generate stability summary (descriptive, not recommendations)
        result.stability_summary = self._generate_stability_summary(result)
        
        return result
    
    def _calculate_stability_metrics(
        self,
        baseline_result: float,
        perturbed_results: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Calculate overall stability metrics.
        
        Phase 6.4: Descriptive only. No ranking, no recommendations.
        """
        metrics = {}
        
        if not perturbed_results:
            return metrics
        
        # Aggregate all perturbed results
        all_perturbed = []
        for pert_results in perturbed_results.values():
            all_perturbed.extend(pert_results)
        
        if not all_perturbed:
            return metrics
        
        all_perturbed = np.array(all_perturbed)
        
        # Overall coefficient of variation
        cv = np.std(all_perturbed) / (np.mean(np.abs(all_perturbed)) + 1e-10)
        metrics['overall_coefficient_of_variation'] = float(cv)
        
        # Range of results
        metrics['result_range'] = float(np.max(all_perturbed) - np.min(all_perturbed))
        metrics['result_mean'] = float(np.mean(all_perturbed))
        metrics['result_std'] = float(np.std(all_perturbed))
        
        # Relative stability (inverse of CV)
        metrics['relative_stability'] = float(1.0 / (1.0 + cv))
        
        return metrics
    
    def _identify_brittleness(
        self,
        robustness_indices: List[RobustnessIndex]
    ) -> List[Dict[str, Any]]:
        """
        Identify brittleness indicators.
        
        Phase 6.4: Descriptive only. Highlights brittle plans/models.
        """
        indicators = []
        
        for idx in robustness_indices:
            if idx.stability_level == "brittle":
                indicators.append({
                    'index_name': idx.index_name,
                    'index_value': idx.index_value,
                    'perturbation_type': idx.perturbation_type,
                    'description': f"{idx.index_name} indicates brittle behavior under {idx.perturbation_type} perturbations",
                    'note': 'Stability characterization only - not a ranking or recommendation'
                })
        
        return indicators
    
    def _build_resilience_profiles(
        self,
        robustness_indices: List[RobustnessIndex]
    ) -> Dict[str, Any]:
        """
        Build resilience profiles by perturbation type.
        
        Phase 6.4: Descriptive only. No ranking, no recommendations.
        """
        profiles = {}
        
        for idx in robustness_indices:
            pert_type = idx.perturbation_type
            if pert_type not in profiles:
                profiles[pert_type] = {
                    'indices': [],
                    'mean_robustness': 0.0,
                    'stability_levels': []
                }
            
            profiles[pert_type]['indices'].append({
                'name': idx.index_name,
                'value': idx.index_value,
                'stability_level': idx.stability_level
            })
            profiles[pert_type]['stability_levels'].append(idx.stability_level)
        
        # Calculate mean robustness per perturbation type
        for pert_type, profile in profiles.items():
            if profile['indices']:
                mean_rob = np.mean([idx['value'] for idx in profile['indices']])
                profile['mean_robustness'] = float(mean_rob)
        
        return profiles
    
    def _generate_stability_summary(
        self,
        result: RobustnessAnalysisResult
    ) -> List[str]:
        """
        Generate stability summary (descriptive, not recommendations).
        
        Phase 6.4: Descriptive only. No ranking, no recommendations.
        """
        summary = []
        
        if not result.robustness_indices:
            summary.append("No robustness indices calculated.")
            return summary
        
        # Overall stability characterization
        summary.append(
            f"Robustness analysis: {len(result.robustness_indices)} indices calculated "
            f"(stability characterization only, not a ranking)."
        )
        
        # Stability levels distribution
        stability_levels = [idx.stability_level for idx in result.robustness_indices]
        level_counts = {level: stability_levels.count(level) for level in set(stability_levels)}
        
        summary.append("Stability levels distribution:")
        for level, count in sorted(level_counts.items()):
            summary.append(f"  {level}: {count} indices")
        
        # Brittleness indicators
        if result.brittleness_indicators:
            summary.append(
                f"Brittleness indicators: {len(result.brittleness_indicators)} identified "
                f"(descriptive only, not recommendations)."
            )
        
        # Overall stability metrics
        if result.stability_metrics:
            rel_stab = result.stability_metrics.get('relative_stability', 0)
            summary.append(
                f"Overall relative stability: {rel_stab:.4f} "
                f"(stability characterization only, not a ranking)."
            )
        
        return summary


__all__ = [
    'RobustnessIndex',
    'RobustnessAnalysisResult',
    'RobustnessAnalyzer'
]

