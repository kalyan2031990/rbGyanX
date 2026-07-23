"""
rbgyanx.logic.sensitivity_analysis - Parameter Sensitivity & Stability Analysis

This module provides parameter sensitivity and stability analysis for TCP/NTCP models.

Phase 6.2: ADVANCED mode only. Sensitivity analysis, not optimization.
No rankings, no recommendations - only descriptive sensitivity analysis.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
import pandas as pd
import numpy as np
from pathlib import Path


@dataclass
class SensitivityResult:
    """
    Result of parameter sensitivity analysis.
    
    Phase 6.2: Descriptive only. No optimization, no rankings, no recommendations.
    """
    parameter_name: str
    parameter_range: Tuple[float, float]
    sensitivity_metrics: Dict[str, float] = field(default_factory=dict)
    response_curve: Dict[str, List[float]] = field(default_factory=dict)
    stability_zones: List[Dict[str, Any]] = field(default_factory=list)
    unstable_regimes: List[Dict[str, Any]] = field(default_factory=list)
    sensitivity_gradients: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'parameter_name': self.parameter_name,
            'parameter_range': list(self.parameter_range),
            'sensitivity_metrics': self.sensitivity_metrics,
            'response_curve': {k: v for k, v in self.response_curve.items()},
            'stability_zones': self.stability_zones,
            'unstable_regimes': self.unstable_regimes,
            'sensitivity_gradients': self.sensitivity_gradients
        }


@dataclass
class StabilityAnalysisResult:
    """
    Result of stability analysis across parameters.
    
    Phase 6.2: Descriptive only. No optimization, no rankings.
    """
    stability_metrics: Dict[str, float] = field(default_factory=dict)
    stable_parameter_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    unstable_parameter_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    stability_heatmap_data: Optional[Dict[str, Any]] = None
    breakdown_indicators: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'stability_metrics': self.stability_metrics,
            'stable_parameter_ranges': {k: list(v) for k, v in self.stable_parameter_ranges.items()},
            'unstable_parameter_ranges': {k: list(v) for k, v in self.unstable_parameter_ranges.items()},
            'stability_heatmap_data': self.stability_heatmap_data,
            'breakdown_indicators': self.breakdown_indicators
        }


class SensitivityAnalyzer:
    """
    Analyzes parameter sensitivity and stability for TCP/NTCP models.
    
    Phase 6.2: ADVANCED mode only. Provides sensitivity analysis, not optimization.
    No rankings, no recommendations - only descriptive sensitivity analysis.
    
    Design Principles:
    - Sensitivity analysis, not optimization
    - Show response surfaces and stability zones
    - Highlight stable vs unstable regimes
    - No dose modification, no plan alteration
    - Analysis only (descriptive)
    """
    
    def __init__(self):
        """Initialize sensitivity analyzer."""
        pass
    
    def analyze_parameter_sensitivity(
        self,
        parameter_name: str,
        parameter_values: List[float],
        model_function: Callable[[float], float],
        baseline_value: Optional[float] = None,
        baseline_result: Optional[float] = None
    ) -> SensitivityResult:
        """
        Analyze sensitivity of a model to a parameter.
        
        Parameters
        ----------
        parameter_name : str
            Name of the parameter (e.g., 'alpha_beta', 'D50')
        parameter_values : List[float]
            List of parameter values to test
        model_function : Callable[[float], float]
            Function that takes parameter value and returns model result
        baseline_value : Optional[float]
            Baseline parameter value (for relative sensitivity)
        baseline_result : Optional[float]
            Baseline model result (for relative sensitivity)
            
        Returns
        -------
        SensitivityResult
            Sensitivity analysis results (descriptive only)
        """
        result = SensitivityResult(
            parameter_name=parameter_name,
            parameter_range=(min(parameter_values), max(parameter_values))
        )
        
        # Calculate model results for each parameter value
        model_results = []
        for param_val in parameter_values:
            try:
                model_result = model_function(param_val)
                model_results.append(model_result)
            except Exception as e:
                # Handle errors gracefully
                model_results.append(np.nan)
        
        # Store response curve
        result.response_curve = {
            'parameter_values': parameter_values,
            'model_results': model_results
        }
        
        # Calculate sensitivity metrics (descriptive only)
        result.sensitivity_metrics = self._calculate_sensitivity_metrics(
            parameter_values, model_results, baseline_value, baseline_result
        )
        
        # Calculate sensitivity gradients
        result.sensitivity_gradients = self._calculate_sensitivity_gradients(
            parameter_values, model_results
        )
        
        # Identify stability zones
        result.stability_zones = self._identify_stability_zones(
            parameter_values, model_results
        )
        
        # Identify unstable regimes
        result.unstable_regimes = self._identify_unstable_regimes(
            parameter_values, model_results
        )
        
        return result
    
    def analyze_stability(
        self,
        parameter_sensitivity_results: List[SensitivityResult],
        stability_threshold: float = 0.1
    ) -> StabilityAnalysisResult:
        """
        Analyze stability across multiple parameters.
        
        Parameters
        ----------
        parameter_sensitivity_results : List[SensitivityResult]
            List of sensitivity analysis results for different parameters
        stability_threshold : float
            Threshold for stability (coefficient of variation)
            
        Returns
        -------
        StabilityAnalysisResult
            Stability analysis results (descriptive only)
        """
        result = StabilityAnalysisResult()
        
        if not parameter_sensitivity_results:
            return result
        
        # Calculate overall stability metrics
        result.stability_metrics = self._calculate_stability_metrics(
            parameter_sensitivity_results
        )
        
        # Identify stable and unstable parameter ranges
        for sens_result in parameter_sensitivity_results:
            param_name = sens_result.parameter_name
            cv = sens_result.sensitivity_metrics.get('coefficient_of_variation', np.inf)
            
            if cv < stability_threshold:
                result.stable_parameter_ranges[param_name] = sens_result.parameter_range
            else:
                result.unstable_parameter_ranges[param_name] = sens_result.parameter_range
        
        # Identify breakdown indicators
        result.breakdown_indicators = self._identify_breakdown_indicators(
            parameter_sensitivity_results
        )
        
        return result
    
    def _calculate_sensitivity_metrics(
        self,
        parameter_values: List[float],
        model_results: List[float],
        baseline_value: Optional[float] = None,
        baseline_result: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate descriptive sensitivity metrics.
        
        Phase 6.2: Descriptive only. No optimization, no rankings.
        """
        metrics = {}
        
        # Remove NaN values
        valid_mask = ~np.isnan(model_results)
        param_vals = np.array(parameter_values)[valid_mask]
        results = np.array(model_results)[valid_mask]
        
        if len(results) < 2:
            return metrics
        
        # Range of results
        metrics['result_range'] = float(np.max(results) - np.min(results))
        metrics['result_mean'] = float(np.mean(results))
        metrics['result_std'] = float(np.std(results))
        
        # Coefficient of variation
        if metrics['result_mean'] != 0:
            metrics['coefficient_of_variation'] = float(
                metrics['result_std'] / abs(metrics['result_mean'])
            )
        else:
            metrics['coefficient_of_variation'] = np.inf
        
        # Relative sensitivity (if baseline provided)
        if baseline_value is not None and baseline_result is not None:
            baseline_idx = np.argmin(np.abs(param_vals - baseline_value))
            if baseline_idx < len(results):
                baseline_res = results[baseline_idx]
                if baseline_res != 0:
                    relative_changes = (results - baseline_res) / abs(baseline_res)
                    metrics['mean_relative_change'] = float(np.mean(np.abs(relative_changes)))
                    metrics['max_relative_change'] = float(np.max(np.abs(relative_changes)))
        
        # Sensitivity index (normalized gradient)
        if len(param_vals) > 1:
            param_range = np.max(param_vals) - np.min(param_vals)
            if param_range > 0:
                result_range = np.max(results) - np.min(results)
                metrics['sensitivity_index'] = float(result_range / param_range)
        
        return metrics
    
    def _calculate_sensitivity_gradients(
        self,
        parameter_values: List[float],
        model_results: List[float]
    ) -> Dict[str, float]:
        """
        Calculate sensitivity gradients.
        
        Phase 6.2: Descriptive gradients, not optimization.
        """
        gradients = {}
        
        # Remove NaN values
        valid_mask = ~np.isnan(model_results)
        param_vals = np.array(parameter_values)[valid_mask]
        results = np.array(model_results)[valid_mask]
        
        if len(results) < 2:
            return gradients
        
        # Calculate gradients (finite differences)
        param_diff = np.diff(param_vals)
        result_diff = np.diff(results)
        
        # Avoid division by zero
        valid_grad_mask = param_diff != 0
        if np.any(valid_grad_mask):
            local_gradients = result_diff[valid_grad_mask] / param_diff[valid_grad_mask]
            gradients['mean_gradient'] = float(np.mean(local_gradients))
            gradients['max_gradient'] = float(np.max(np.abs(local_gradients)))
            gradients['min_gradient'] = float(np.min(local_gradients))
            gradients['std_gradient'] = float(np.std(local_gradients))
        
        return gradients
    
    def _identify_stability_zones(
        self,
        parameter_values: List[float],
        model_results: List[float],
        stability_threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Identify zones where model is stable.
        
        Phase 6.2: Descriptive only. Highlights stable regimes.
        """
        zones = []
        
        # Remove NaN values
        valid_mask = ~np.isnan(model_results)
        param_vals = np.array(parameter_values)[valid_mask]
        results = np.array(model_results)[valid_mask]
        
        if len(results) < 3:
            return zones
        
        # Calculate local coefficient of variation (rolling window)
        window_size = min(5, len(results) // 3)
        if window_size < 2:
            return zones
        
        for i in range(len(results) - window_size + 1):
            window_results = results[i:i+window_size]
            window_params = param_vals[i:i+window_size]
            
            cv = np.std(window_results) / (np.mean(np.abs(window_results)) + 1e-10)
            
            if cv < stability_threshold:
                zones.append({
                    'parameter_range': (float(window_params[0]), float(window_params[-1])),
                    'mean_result': float(np.mean(window_results)),
                    'std_result': float(np.std(window_results)),
                    'coefficient_of_variation': float(cv)
                })
        
        return zones
    
    def _identify_unstable_regimes(
        self,
        parameter_values: List[float],
        model_results: List[float],
        instability_threshold: float = 0.2
    ) -> List[Dict[str, Any]]:
        """
        Identify regimes where model is unstable.
        
        Phase 6.2: Descriptive only. Highlights unstable regimes.
        """
        regimes = []
        
        # Remove NaN values
        valid_mask = ~np.isnan(model_results)
        param_vals = np.array(parameter_values)[valid_mask]
        results = np.array(model_results)[valid_mask]
        
        if len(results) < 3:
            return regimes
        
        # Calculate local coefficient of variation (rolling window)
        window_size = min(5, len(results) // 3)
        if window_size < 2:
            return regimes
        
        for i in range(len(results) - window_size + 1):
            window_results = results[i:i+window_size]
            window_params = param_vals[i:i+window_size]
            
            cv = np.std(window_results) / (np.mean(np.abs(window_results)) + 1e-10)
            
            if cv > instability_threshold:
                regimes.append({
                    'parameter_range': (float(window_params[0]), float(window_params[-1])),
                    'mean_result': float(np.mean(window_results)),
                    'std_result': float(np.std(window_results)),
                    'coefficient_of_variation': float(cv),
                    'instability_level': 'high' if cv > 0.5 else 'medium'
                })
        
        return regimes
    
    def _calculate_stability_metrics(
        self,
        parameter_sensitivity_results: List[SensitivityResult]
    ) -> Dict[str, float]:
        """
        Calculate overall stability metrics across parameters.
        
        Phase 6.2: Descriptive only.
        """
        metrics = {}
        
        if not parameter_sensitivity_results:
            return metrics
        
        # Aggregate coefficient of variation across all parameters
        cvs = [
            sens.sensitivity_metrics.get('coefficient_of_variation', np.inf)
            for sens in parameter_sensitivity_results
        ]
        cvs = [cv for cv in cvs if not np.isinf(cv)]
        
        if cvs:
            metrics['mean_coefficient_of_variation'] = float(np.mean(cvs))
            metrics['max_coefficient_of_variation'] = float(np.max(cvs))
            metrics['min_coefficient_of_variation'] = float(np.min(cvs))
        
        # Aggregate sensitivity indices
        sensitivity_indices = [
            sens.sensitivity_metrics.get('sensitivity_index', 0)
            for sens in parameter_sensitivity_results
        ]
        sensitivity_indices = [si for si in sensitivity_indices if si > 0]
        
        if sensitivity_indices:
            metrics['mean_sensitivity_index'] = float(np.mean(sensitivity_indices))
            metrics['max_sensitivity_index'] = float(np.max(sensitivity_indices))
        
        return metrics
    
    def _identify_breakdown_indicators(
        self,
        parameter_sensitivity_results: List[SensitivityResult]
    ) -> List[Dict[str, Any]]:
        """
        Identify model breakdown indicators.
        
        Phase 6.2: Descriptive only. Flags where models break down.
        """
        indicators = []
        
        for sens_result in parameter_sensitivity_results:
            # Check for extreme sensitivity
            cv = sens_result.sensitivity_metrics.get('coefficient_of_variation', 0)
            if cv > 1.0:  # Very high coefficient of variation
                indicators.append({
                    'parameter': sens_result.parameter_name,
                    'indicator_type': 'high_sensitivity',
                    'severity': 'high' if cv > 2.0 else 'medium',
                    'coefficient_of_variation': float(cv),
                    'description': f"Model shows high sensitivity to {sens_result.parameter_name}"
                })
            
            # Check for unstable regimes
            if sens_result.unstable_regimes:
                indicators.append({
                    'parameter': sens_result.parameter_name,
                    'indicator_type': 'unstable_regime',
                    'severity': 'high',
                    'unstable_ranges': sens_result.unstable_regimes,
                    'description': f"Model shows unstable behavior for {sens_result.parameter_name}"
                })
        
        return indicators


__all__ = [
    'SensitivityResult',
    'StabilityAnalysisResult',
    'SensitivityAnalyzer'
]

