"""
rbgyanx.logic.model_agreement - Model Agreement/Disagreement Analysis

This module provides comparative, descriptive analysis of model agreement
and disagreement for TCP and NTCP models.

Phase 6.1: ADVANCED mode only. Comparative, descriptive analysis only.
No rankings, no recommendations.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from pathlib import Path


@dataclass
class ModelAgreementResult:
    """
    Result of model agreement/disagreement analysis.
    
    Phase 6.1: Descriptive only. No rankings, no recommendations.
    """
    agreement_metrics: Dict[str, float] = field(default_factory=dict)
    disagreement_zones: List[Dict[str, Any]] = field(default_factory=list)
    stability_metrics: Dict[str, float] = field(default_factory=dict)
    model_predictions: Dict[str, List[float]] = field(default_factory=dict)
    agreement_bands: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    divergence_explanations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'agreement_metrics': self.agreement_metrics,
            'disagreement_zones': self.disagreement_zones,
            'stability_metrics': self.stability_metrics,
            'model_predictions': {k: v for k, v in self.model_predictions.items()},
            'agreement_bands': {k: list(v) for k, v in self.agreement_bands.items()},
            'divergence_explanations': self.divergence_explanations
        }


class ModelAgreementAnalyzer:
    """
    Analyzes agreement and disagreement between multiple TCP/NTCP models.
    
    Phase 6.1: ADVANCED mode only. Provides comparative, descriptive analysis.
    No rankings, no recommendations - only descriptive statistics and patterns.
    
    Design Principles:
    - Show agreement bands, not "best model"
    - Highlight divergence zones (dose, volume, fractionation)
    - Provide stability metrics across models
    - Descriptive analysis only (no rankings)
    """
    
    def __init__(self):
        """Initialize model agreement analyzer."""
        pass
    
    def analyze_tcp_agreement(
        self,
        tcp_results: Dict[str, List[float]],
        patient_ids: Optional[List[str]] = None,
        dose_metrics: Optional[Dict[str, List[float]]] = None
    ) -> ModelAgreementResult:
        """
        Analyze agreement between multiple TCP models.
        
        Parameters
        ----------
        tcp_results : Dict[str, List[float]]
            Dictionary mapping model names to TCP predictions
        patient_ids : Optional[List[str]]
            Patient IDs (for tracking)
        dose_metrics : Optional[Dict[str, List[float]]]
            Dose metrics (for divergence zone analysis)
            
        Returns
        -------
        ModelAgreementResult
            Agreement/disagreement analysis results (descriptive only)
        """
        result = ModelAgreementResult()
        
        if not tcp_results:
            return result
        
        # Store model predictions
        result.model_predictions = {
            model: list(predictions) for model, predictions in tcp_results.items()
        }
        
        # Calculate agreement metrics (descriptive only)
        result.agreement_metrics = self._calculate_agreement_metrics(tcp_results)
        
        # Calculate agreement bands (not "best model")
        result.agreement_bands = self._calculate_agreement_bands(tcp_results)
        
        # Calculate stability metrics
        result.stability_metrics = self._calculate_stability_metrics(tcp_results)
        
        # Identify disagreement zones
        result.disagreement_zones = self._identify_disagreement_zones(
            tcp_results, patient_ids, dose_metrics
        )
        
        # Generate divergence explanations (descriptive)
        result.divergence_explanations = self._generate_divergence_explanations(
            tcp_results, result.disagreement_zones
        )
        
        return result
    
    def analyze_ntcp_agreement(
        self,
        ntcp_results: Dict[str, Dict[str, List[float]]],
        patient_ids: Optional[List[str]] = None,
        dose_metrics: Optional[Dict[str, List[float]]] = None
    ) -> ModelAgreementResult:
        """
        Analyze agreement between multiple NTCP models.
        
        Parameters
        ----------
        ntcp_results : Dict[str, Dict[str, List[float]]]
            Dictionary mapping organ names to model predictions
            Format: {organ: {model: [predictions]}}
        patient_ids : Optional[List[str]]
            Patient IDs (for tracking)
        dose_metrics : Optional[Dict[str, List[float]]]
            Dose metrics (for divergence zone analysis)
            
        Returns
        -------
        ModelAgreementResult
            Agreement/disagreement analysis results (descriptive only)
        """
        result = ModelAgreementResult()
        
        if not ntcp_results:
            return result
        
        # Aggregate NTCP results across organs (per model)
        aggregated_results = {}
        for organ, models in ntcp_results.items():
            for model, predictions in models.items():
                key = f"{organ}_{model}"
                aggregated_results[key] = predictions
        
        # Store model predictions
        result.model_predictions = {
            model: list(predictions) for model, predictions in aggregated_results.items()
        }
        
        # Calculate agreement metrics
        result.agreement_metrics = self._calculate_agreement_metrics(aggregated_results)
        
        # Calculate agreement bands
        result.agreement_bands = self._calculate_agreement_bands(aggregated_results)
        
        # Calculate stability metrics
        result.stability_metrics = self._calculate_stability_metrics(aggregated_results)
        
        # Identify disagreement zones
        result.disagreement_zones = self._identify_disagreement_zones(
            aggregated_results, patient_ids, dose_metrics
        )
        
        # Generate divergence explanations
        result.divergence_explanations = self._generate_divergence_explanations(
            aggregated_results, result.disagreement_zones
        )
        
        return result
    
    def _calculate_agreement_metrics(
        self,
        model_results: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Calculate descriptive agreement metrics.
        
        Phase 6.1: Descriptive only. No rankings.
        """
        metrics = {}
        
        if not model_results:
            return metrics
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(model_results)
        
        # Mean absolute difference (MAD) across models
        if len(df.columns) > 1:
            pairwise_diffs = []
            for i, col1 in enumerate(df.columns):
                for col2 in df.columns[i+1:]:
                    diff = np.abs(df[col1] - df[col2])
                    pairwise_diffs.extend(diff.tolist())
            
            if pairwise_diffs:
                metrics['mean_absolute_difference'] = float(np.mean(pairwise_diffs))
                metrics['max_absolute_difference'] = float(np.max(pairwise_diffs))
                metrics['std_absolute_difference'] = float(np.std(pairwise_diffs))
        
        # Coefficient of variation across models (per patient)
        if len(df.columns) > 1:
            cv_per_patient = df.std(axis=1) / (df.mean(axis=1) + 1e-10)
            metrics['mean_coefficient_of_variation'] = float(cv_per_patient.mean())
            metrics['max_coefficient_of_variation'] = float(cv_per_patient.max())
        
        # Range across models (per patient)
        if len(df.columns) > 1:
            range_per_patient = df.max(axis=1) - df.min(axis=1)
            metrics['mean_range'] = float(range_per_patient.mean())
            metrics['max_range'] = float(range_per_patient.max())
        
        return metrics
    
    def _calculate_agreement_bands(
        self,
        model_results: Dict[str, List[float]]
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate agreement bands (not "best model").
        
        Phase 6.1: Shows range of predictions, not rankings.
        """
        bands = {}
        
        if not model_results:
            return bands
        
        # Convert to DataFrame
        df = pd.DataFrame(model_results)
        
        # Calculate bands per patient (min, max across models)
        if len(df.columns) > 1:
            min_values = df.min(axis=1)
            max_values = df.max(axis=1)
            
            bands['per_patient'] = (
                float(min_values.mean()),
                float(max_values.mean())
            )
            
            bands['overall'] = (
                float(df.min().min()),
                float(df.max().max())
            )
        
        return bands
    
    def _calculate_stability_metrics(
        self,
        model_results: Dict[str, List[float]]
    ) -> Dict[str, float]:
        """
        Calculate stability metrics across models.
        
        Phase 6.1: Descriptive stability analysis.
        """
        metrics = {}
        
        if not model_results:
            return metrics
        
        # Convert to DataFrame
        df = pd.DataFrame(model_results)
        
        if len(df.columns) > 1:
            # Standard deviation across models (per patient)
            std_per_patient = df.std(axis=1)
            metrics['mean_std_across_models'] = float(std_per_patient.mean())
            metrics['max_std_across_models'] = float(std_per_patient.max())
            
            # Interquartile range across models
            iqr_per_patient = df.quantile(0.75, axis=1) - df.quantile(0.25, axis=1)
            metrics['mean_iqr_across_models'] = float(iqr_per_patient.mean())
            metrics['max_iqr_across_models'] = float(iqr_per_patient.max())
        
        return metrics
    
    def _identify_disagreement_zones(
        self,
        model_results: Dict[str, List[float]],
        patient_ids: Optional[List[str]] = None,
        dose_metrics: Optional[Dict[str, List[float]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify zones where models disagree.
        
        Phase 6.1: Descriptive only. Highlights divergence zones.
        """
        zones = []
        
        if not model_results or len(model_results) < 2:
            return zones
        
        # Convert to DataFrame
        df = pd.DataFrame(model_results)
        
        if len(df.columns) < 2:
            return zones
        
        # Calculate disagreement per patient
        range_per_patient = df.max(axis=1) - df.min(axis=1)
        threshold = range_per_patient.quantile(0.75)  # Top 25% disagreement
        
        # Identify high-disagreement patients
        high_disagreement = range_per_patient > threshold
        
        for idx in df[high_disagreement].index:
            zone = {
                'patient_index': int(idx),
                'patient_id': patient_ids[idx] if patient_ids and idx < len(patient_ids) else f"Patient_{idx}",
                'disagreement_range': float(range_per_patient.iloc[idx]),
                'model_predictions': {
                    model: float(df.loc[idx, model]) for model in df.columns
                },
                'mean_prediction': float(df.loc[idx].mean()),
                'std_prediction': float(df.loc[idx].std())
            }
            
            # Add dose metrics if available
            if dose_metrics:
                for metric_name, metric_values in dose_metrics.items():
                    if idx < len(metric_values):
                        zone[f'dose_{metric_name}'] = float(metric_values[idx])
            
            zones.append(zone)
        
        return zones
    
    def _generate_divergence_explanations(
        self,
        model_results: Dict[str, List[float]],
        disagreement_zones: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate descriptive explanations for divergence.
        
        Phase 6.1: Descriptive only. No recommendations.
        """
        explanations = []
        
        if not disagreement_zones:
            explanations.append("Models show consistent agreement across all patients.")
            return explanations
        
        # Descriptive statistics about disagreement
        disagreement_ranges = [zone['disagreement_range'] for zone in disagreement_zones]
        mean_disagreement = np.mean(disagreement_ranges)
        max_disagreement = np.max(disagreement_ranges)
        
        explanations.append(
            f"Models show varying levels of agreement. "
            f"Mean disagreement range: {mean_disagreement:.4f}, "
            f"Maximum disagreement range: {max_disagreement:.4f}."
        )
        
        explanations.append(
            f"Identified {len(disagreement_zones)} patients with high model disagreement "
            f"(top 25% of disagreement range)."
        )
        
        # Descriptive patterns (no recommendations)
        if len(model_results) >= 2:
            model_names = list(model_results.keys())
            explanations.append(
                f"Comparing {len(model_names)} models: {', '.join(model_names)}. "
                f"Disagreement patterns are descriptive only - no model ranking provided."
            )
        
        return explanations


__all__ = [
    'ModelAgreementResult',
    'ModelAgreementAnalyzer'
]

