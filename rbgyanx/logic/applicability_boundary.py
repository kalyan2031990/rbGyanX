"""
rbgyanx.logic.applicability_boundary - Applicability Boundary Detection

This module provides detection and visualization of model applicability boundaries
and extrapolation zones for TCP/NTCP models.

Phase 6.5: ADVANCED mode only. Detection and visualization only.
No enforcing blocks, no making recommendations - only boundary detection.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
import pandas as pd
import numpy as np
from pathlib import Path
from enum import Enum


class BoundaryType(Enum):
    """Types of applicability boundaries."""
    VALIDATED = "validated"  # Within validated domain
    EXTRAPOLATION = "extrapolation"  # Outside validated domain
    FRAGILE = "fragile"  # Near boundary, potentially unreliable
    UNKNOWN = "unknown"  # Unknown validity


@dataclass
class ApplicabilityBoundary:
    """
    Individual applicability boundary.
    
    Phase 6.5: Descriptive only. No blocking, no recommendations.
    """
    boundary_type: BoundaryType
    parameter_name: str
    boundary_value: float
    validated_range: Tuple[float, float]
    current_value: Optional[float] = None
    distance_to_boundary: Optional[float] = None
    extrapolation_degree: Optional[float] = None
    fragility_indicators: List[str] = field(default_factory=list)
    attribution_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'boundary_type': self.boundary_type.value,
            'parameter_name': self.parameter_name,
            'boundary_value': self.boundary_value,
            'validated_range': list(self.validated_range),
            'current_value': self.current_value,
            'distance_to_boundary': self.distance_to_boundary,
            'extrapolation_degree': self.extrapolation_degree,
            'fragility_indicators': self.fragility_indicators,
            'attribution_details': self.attribution_details
        }


@dataclass
class ExtrapolationZone:
    """
    Extrapolation zone identification.
    
    Phase 6.5: Descriptive only. No blocking, no recommendations.
    """
    zone_name: str
    parameter_space: Dict[str, Tuple[float, float]]
    extrapolation_indicators: List[str] = field(default_factory=list)
    stability_metrics: Dict[str, float] = field(default_factory=dict)
    breakdown_probability: Optional[float] = None
    attribution_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'zone_name': self.zone_name,
            'parameter_space': {k: list(v) for k, v in self.parameter_space.items()},
            'extrapolation_indicators': self.extrapolation_indicators,
            'stability_metrics': self.stability_metrics,
            'breakdown_probability': self.breakdown_probability,
            'attribution_details': self.attribution_details
        }


@dataclass
class ApplicabilityBoundaryResult:
    """
    Result of applicability boundary detection.
    
    Phase 6.5: Detection and visualization only. No blocking, no recommendations.
    """
    boundaries: List[ApplicabilityBoundary] = field(default_factory=list)
    extrapolation_zones: List[ExtrapolationZone] = field(default_factory=list)
    current_position: Dict[str, float] = field(default_factory=dict)
    boundary_distances: Dict[str, float] = field(default_factory=dict)
    extrapolation_map: Dict[str, Any] = field(default_factory=dict)
    detection_summary: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'boundaries': [b.to_dict() for b in self.boundaries],
            'extrapolation_zones': [z.to_dict() for z in self.extrapolation_zones],
            'current_position': self.current_position,
            'boundary_distances': self.boundary_distances,
            'extrapolation_map': self.extrapolation_map,
            'detection_summary': self.detection_summary
        }


class ApplicabilityBoundaryDetector:
    """
    Detects and visualizes model applicability boundaries and extrapolation zones.
    
    Phase 6.5: ADVANCED mode only. Detection and visualization only.
    No enforcing blocks, no making recommendations - only boundary detection.
    
    Design Principles:
    - Detect boundaries and extrapolation zones
    - Flag fragile regions
    - No blocking, no recommendations
    - Descriptive boundary identification only
    """
    
    # Validated parameter ranges (from literature)
    VALIDATED_RANGES: Dict[str, Tuple[float, float]] = {
        'dose_per_fraction': (1.8, 2.2),  # Conventional fractionation
        'n_fractions': (25, 40),  # Typical range
        'alpha_beta': (1.5, 20.0),  # Typical α/β ratios
        'total_dose': (45.0, 80.0),  # Typical total dose (Gy)
    }
    
    # Extrapolation thresholds (fractional distance from validated range)
    EXTRAPOLATION_THRESHOLD = 0.2  # 20% beyond validated range
    FRAGILE_THRESHOLD = 0.1  # 10% from boundary
    
    def __init__(self):
        """Initialize applicability boundary detector."""
        pass
    
    def detect_boundaries(
        self,
        current_parameters: Dict[str, float],
        validated_ranges: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> ApplicabilityBoundaryResult:
        """
        Detect applicability boundaries for current parameters.
        
        Parameters
        ----------
        current_parameters : Dict[str, float]
            Current parameter values
        validated_ranges : Optional[Dict[str, Tuple[float, float]]]
            Custom validated ranges (defaults to literature ranges)
            
        Returns
        -------
        ApplicabilityBoundaryResult
            Boundary detection results (descriptive only, no blocking)
        """
        result = ApplicabilityBoundaryResult()
        
        # Use provided ranges or default validated ranges
        ranges = validated_ranges or self.VALIDATED_RANGES
        
        # Store current position
        result.current_position = current_parameters.copy()
        
        # Detect boundaries for each parameter
        for param_name, current_value in current_parameters.items():
            if param_name not in ranges:
                continue
            
            validated_range = ranges[param_name]
            min_val, max_val = validated_range
            
            # Calculate distance to boundaries
            distance_to_min = current_value - min_val
            distance_to_max = max_val - current_value
            
            # Determine boundary type
            if min_val <= current_value <= max_val:
                # Within validated range
                boundary_type = BoundaryType.VALIDATED
                boundary_value = current_value
                distance_to_boundary = min(distance_to_min, distance_to_max)
                extrapolation_degree = 0.0
            elif current_value < min_val:
                # Below minimum (extrapolation)
                boundary_type = BoundaryType.EXTRAPOLATION
                boundary_value = min_val
                distance_to_boundary = abs(distance_to_min)
                range_width = max_val - min_val
                extrapolation_degree = abs(distance_to_min) / (range_width + 1e-10)
            else:  # current_value > max_val
                # Above maximum (extrapolation)
                boundary_type = BoundaryType.EXTRAPOLATION
                boundary_value = max_val
                distance_to_boundary = abs(distance_to_max)
                range_width = max_val - min_val
                extrapolation_degree = abs(distance_to_max) / (range_width + 1e-10)
            
            # Check if fragile (near boundary)
            range_width = max_val - min_val
            if range_width > 0:
                normalized_distance = distance_to_boundary / range_width
                if normalized_distance < self.FRAGILE_THRESHOLD and boundary_type == BoundaryType.VALIDATED:
                    boundary_type = BoundaryType.FRAGILE
            
            # Collect fragility indicators
            fragility_indicators = []
            if extrapolation_degree > self.EXTRAPOLATION_THRESHOLD:
                fragility_indicators.append(f"Significant extrapolation beyond validated range")
            if normalized_distance < self.FRAGILE_THRESHOLD:
                fragility_indicators.append(f"Close to applicability boundary")
            
            # Create boundary object
            boundary = ApplicabilityBoundary(
                boundary_type=boundary_type,
                parameter_name=param_name,
                boundary_value=boundary_value,
                validated_range=validated_range,
                current_value=current_value,
                distance_to_boundary=distance_to_boundary,
                extrapolation_degree=extrapolation_degree if extrapolation_degree > 0 else None,
                fragility_indicators=fragility_indicators,
                attribution_details={
                    'description': f"Boundary detection for {param_name}",
                    'note': 'Detection only - not a block or recommendation'
                }
            )
            
            result.boundaries.append(boundary)
            result.boundary_distances[param_name] = distance_to_boundary
        
        # Identify extrapolation zones
        result.extrapolation_zones = self._identify_extrapolation_zones(
            current_parameters, ranges
        )
        
        # Build extrapolation map
        result.extrapolation_map = self._build_extrapolation_map(result)
        
        # Generate detection summary (descriptive, not recommendations)
        result.detection_summary = self._generate_detection_summary(result)
        
        return result
    
    def detect_extrapolation_zones(
        self,
        parameter_space: Dict[str, List[float]],
        model_response_function: Optional[Callable] = None,
        validated_ranges: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> List[ExtrapolationZone]:
        """
        Detect extrapolation zones in parameter space.
        
        Parameters
        ----------
        parameter_space : Dict[str, List[float]]
            Parameter space to explore
        model_response_function : Optional[Callable]
            Optional function to evaluate model response
        validated_ranges : Optional[Dict[str, Tuple[float, float]]]
            Custom validated ranges
            
        Returns
        -------
        List[ExtrapolationZone]
            Extrapolation zones (descriptive only, no blocking)
        """
        zones = []
        
        # Use provided ranges or default validated ranges
        ranges = validated_ranges or self.VALIDATED_RANGES
        
        # Identify extrapolation regions
        for param_name, param_values in parameter_space.items():
            if param_name not in ranges:
                continue
            
            validated_range = ranges[param_name]
            min_val, max_val = validated_range
            
            # Find values outside validated range
            extrapolation_values = [
                v for v in param_values
                if v < min_val or v > max_val
            ]
            
            if extrapolation_values:
                # Calculate extrapolation degree
                extrapolation_min = min(extrapolation_values)
                extrapolation_max = max(extrapolation_values)
                range_width = max_val - min_val
                
                if extrapolation_min < min_val:
                    degree_below = (min_val - extrapolation_min) / (range_width + 1e-10)
                else:
                    degree_below = 0.0
                
                if extrapolation_max > max_val:
                    degree_above = (extrapolation_max - max_val) / (range_width + 1e-10)
                else:
                    degree_above = 0.0
                
                max_extrapolation_degree = max(degree_below, degree_above)
                
                # Create extrapolation zone
                zone = ExtrapolationZone(
                    zone_name=f"{param_name}_extrapolation",
                    parameter_space={
                        param_name: (extrapolation_min, extrapolation_max)
                    },
                    extrapolation_indicators=[
                        f"Extrapolation detected for {param_name}",
                        f"Extrapolation degree: {max_extrapolation_degree:.2f}"
                    ],
                    stability_metrics={
                        'extrapolation_degree': float(max_extrapolation_degree),
                        'n_extrapolation_points': len(extrapolation_values)
                    },
                    breakdown_probability=min(max_extrapolation_degree, 1.0),
                    attribution_details={
                        'description': f"Extrapolation zone for {param_name}",
                        'note': 'Detection only - not a block or recommendation'
                    }
                )
                
                zones.append(zone)
        
        return zones
    
    def _identify_extrapolation_zones(
        self,
        current_parameters: Dict[str, float],
        validated_ranges: Dict[str, Tuple[float, float]]
    ) -> List[ExtrapolationZone]:
        """
        Identify extrapolation zones based on current parameters.
        
        Phase 6.5: Descriptive only. No blocking, no recommendations.
        """
        zones = []
        
        # Check if any parameters are in extrapolation
        extrapolation_params = {}
        for param_name, current_value in current_parameters.items():
            if param_name not in validated_ranges:
                continue
            
            min_val, max_val = validated_ranges[param_name]
            if current_value < min_val or current_value > max_val:
                extrapolation_params[param_name] = current_value
        
        if extrapolation_params:
            # Create extrapolation zone
            zone = ExtrapolationZone(
                zone_name="current_extrapolation",
                parameter_space=extrapolation_params,
                extrapolation_indicators=[
                    f"Extrapolation detected for parameters: {', '.join(extrapolation_params.keys())}"
                ],
                attribution_details={
                    'description': 'Current parameter position in extrapolation zone',
                    'note': 'Detection only - not a block or recommendation'
                }
            )
            zones.append(zone)
        
        return zones
    
    def _build_extrapolation_map(
        self,
        result: ApplicabilityBoundaryResult
    ) -> Dict[str, Any]:
        """
        Build extrapolation map for visualization.
        
        Phase 6.5: Descriptive only. No blocking, no recommendations.
        """
        map_data = {
            'boundaries_detected': len(result.boundaries),
            'extrapolation_zones_detected': len(result.extrapolation_zones),
            'parameters_in_extrapolation': [],
            'parameters_in_validated': [],
            'parameters_in_fragile': []
        }
        
        for boundary in result.boundaries:
            if boundary.boundary_type == BoundaryType.EXTRAPOLATION:
                map_data['parameters_in_extrapolation'].append(boundary.parameter_name)
            elif boundary.boundary_type == BoundaryType.FRAGILE:
                map_data['parameters_in_fragile'].append(boundary.parameter_name)
            else:
                map_data['parameters_in_validated'].append(boundary.parameter_name)
        
        return map_data
    
    def _generate_detection_summary(
        self,
        result: ApplicabilityBoundaryResult
    ) -> List[str]:
        """
        Generate detection summary (descriptive, not recommendations).
        
        Phase 6.5: Descriptive only. No blocking, no recommendations.
        """
        summary = []
        
        if not result.boundaries:
            summary.append("No boundaries detected.")
            return summary
        
        # Overall boundary detection
        summary.append(
            f"Applicability boundary detection: {len(result.boundaries)} boundaries analyzed "
            f"(detection only, not a block or recommendation)."
        )
        
        # Boundary types distribution
        boundary_types = [b.boundary_type for b in result.boundaries]
        type_counts = {bt: boundary_types.count(bt) for bt in set(boundary_types)}
        
        summary.append("Boundary types detected:")
        for btype, count in sorted(type_counts.items()):
            summary.append(f"  {btype.value}: {count} parameters")
        
        # Extrapolation zones
        if result.extrapolation_zones:
            summary.append(
                f"Extrapolation zones: {len(result.extrapolation_zones)} zones identified "
                f"(descriptive only, not a block or recommendation)."
            )
        
        # Current position relative to boundaries
        in_extrapolation = [
            b.parameter_name for b in result.boundaries
            if b.boundary_type == BoundaryType.EXTRAPOLATION
        ]
        if in_extrapolation:
            summary.append(
                f"Parameters in extrapolation: {', '.join(in_extrapolation)} "
                f"(detection only, not a block or recommendation)."
            )
        
        return summary


__all__ = [
    'BoundaryType',
    'ApplicabilityBoundary',
    'ExtrapolationZone',
    'ApplicabilityBoundaryResult',
    'ApplicabilityBoundaryDetector'
]

