"""
rbgyanx.logic.uncertainty_decomposition - Uncertainty Decomposition Engine

This module provides explicit decomposition of uncertainty sources for TCP/NTCP models.

Phase 6.3: ADVANCED mode only. Attribution, not aggregation.
No rankings, no recommendations - only explicit uncertainty source attribution.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from pathlib import Path
from enum import Enum


class UncertaintyType(Enum):
    """Types of uncertainty."""
    ALEATORIC = "aleatoric"  # Irreducible (patient variability)
    EPISTEMIC = "epistemic"  # Reducible (parameter ignorance)
    STRUCTURAL = "structural"  # Model form uncertainty


class UncertaintySource(Enum):
    """Sources of uncertainty."""
    DOSIMETRIC = "dosimetric"  # Dose measurement/calculation uncertainty
    BIOLOGICAL = "biological"  # Biological parameter uncertainty
    MODEL_STRUCTURE = "model_structure"  # Model form uncertainty
    DATA_DOMAIN = "data_domain"  # Data/domain shift uncertainty


@dataclass
class UncertaintyComponent:
    """
    Individual uncertainty component with attribution.
    
    Phase 6.3: Attribution, not aggregation. Each source tracked separately.
    """
    source: UncertaintySource
    uncertainty_type: UncertaintyType
    magnitude: float
    contribution_percent: float
    reducibility: str  # "reducible", "irreducible", "partially_reducible"
    attribution_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'source': self.source.value,
            'uncertainty_type': self.uncertainty_type.value,
            'magnitude': self.magnitude,
            'contribution_percent': self.contribution_percent,
            'reducibility': self.reducibility,
            'attribution_details': self.attribution_details
        }


@dataclass
class UncertaintyDecompositionResult:
    """
    Result of uncertainty decomposition analysis.
    
    Phase 6.3: Explicit decomposition with attribution, not aggregation.
    No rankings, no recommendations - only attribution.
    """
    total_uncertainty: float
    uncertainty_components: List[UncertaintyComponent] = field(default_factory=list)
    dominant_source: Optional[UncertaintySource] = None
    dominant_type: Optional[UncertaintyType] = None
    reducibility_analysis: Dict[str, Any] = field(default_factory=dict)
    contribution_breakdown: Dict[str, float] = field(default_factory=dict)
    attribution_summary: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'total_uncertainty': self.total_uncertainty,
            'uncertainty_components': [comp.to_dict() for comp in self.uncertainty_components],
            'dominant_source': self.dominant_source.value if self.dominant_source else None,
            'dominant_type': self.dominant_type.value if self.dominant_type else None,
            'reducibility_analysis': self.reducibility_analysis,
            'contribution_breakdown': self.contribution_breakdown,
            'attribution_summary': self.attribution_summary
        }


class UncertaintyDecomposer:
    """
    Decomposes uncertainty into explicit sources with attribution.
    
    Phase 6.3: ADVANCED mode only. Provides explicit decomposition with attribution.
    No rankings, no recommendations - only attribution of uncertainty sources.
    
    Design Principles:
    - Attribution, not aggregation
    - Explicit separation of uncertainty sources
    - Reducibility analysis
    - No rankings, no recommendations
    """
    
    def __init__(self):
        """Initialize uncertainty decomposer."""
        pass
    
    def decompose_uncertainty(
        self,
        dosimetric_uncertainty: Optional[float] = None,
        biological_uncertainty: Optional[float] = None,
        model_structure_uncertainty: Optional[float] = None,
        data_domain_uncertainty: Optional[float] = None,
        aleatoric_components: Optional[Dict[str, float]] = None,
        epistemic_components: Optional[Dict[str, float]] = None,
        structural_components: Optional[Dict[str, float]] = None
    ) -> UncertaintyDecompositionResult:
        """
        Decompose uncertainty into explicit sources with attribution.
        
        Parameters
        ----------
        dosimetric_uncertainty : Optional[float]
            Dosimetric uncertainty magnitude (std or variance)
        biological_uncertainty : Optional[float]
            Biological parameter uncertainty magnitude
        model_structure_uncertainty : Optional[float]
            Model structure uncertainty magnitude
        data_domain_uncertainty : Optional[float]
            Data/domain shift uncertainty magnitude
        aleatoric_components : Optional[Dict[str, float]]
            Aleatoric uncertainty components by source
        epistemic_components : Optional[Dict[str, float]]
            Epistemic uncertainty components by source
        structural_components : Optional[Dict[str, float]]
            Structural uncertainty components by source
            
        Returns
        -------
        UncertaintyDecompositionResult
            Uncertainty decomposition with attribution (not aggregation)
        """
        result = UncertaintyDecompositionResult(total_uncertainty=0.0)
        
        # Build uncertainty components with attribution
        components = []
        
        # Dosimetric uncertainty
        if dosimetric_uncertainty is not None and dosimetric_uncertainty > 0:
            # Dosimetric is typically aleatoric (measurement noise)
            dos_aleatoric = aleatoric_components.get('dosimetric', dosimetric_uncertainty * 0.7) if aleatoric_components else dosimetric_uncertainty * 0.7
            dos_epistemic = epistemic_components.get('dosimetric', dosimetric_uncertainty * 0.3) if epistemic_components else dosimetric_uncertainty * 0.3
            
            components.append(UncertaintyComponent(
                source=UncertaintySource.DOSIMETRIC,
                uncertainty_type=UncertaintyType.ALEATORIC,
                magnitude=dos_aleatoric,
                contribution_percent=0.0,  # Will be calculated later
                reducibility="partially_reducible",
                attribution_details={
                    'description': 'Dosimetric measurement and calculation uncertainty',
                    'aleatoric_component': dos_aleatoric,
                    'epistemic_component': dos_epistemic
                }
            ))
        
        # Biological uncertainty
        if biological_uncertainty is not None and biological_uncertainty > 0:
            # Biological is typically epistemic (parameter ignorance)
            bio_epistemic = epistemic_components.get('biological', biological_uncertainty * 0.8) if epistemic_components else biological_uncertainty * 0.8
            bio_aleatoric = aleatoric_components.get('biological', biological_uncertainty * 0.2) if aleatoric_components else biological_uncertainty * 0.2
            
            components.append(UncertaintyComponent(
                source=UncertaintySource.BIOLOGICAL,
                uncertainty_type=UncertaintyType.EPISTEMIC,
                magnitude=bio_epistemic,
                contribution_percent=0.0,  # Will be calculated later
                reducibility="reducible",
                attribution_details={
                    'description': 'Biological parameter uncertainty (α/β, D50, etc.)',
                    'epistemic_component': bio_epistemic,
                    'aleatoric_component': bio_aleatoric
                }
            ))
        
        # Model structure uncertainty
        if model_structure_uncertainty is not None and model_structure_uncertainty > 0:
            # Model structure is structural uncertainty
            struct_structural = structural_components.get('model_structure', model_structure_uncertainty) if structural_components else model_structure_uncertainty
            
            components.append(UncertaintyComponent(
                source=UncertaintySource.MODEL_STRUCTURE,
                uncertainty_type=UncertaintyType.STRUCTURAL,
                magnitude=struct_structural,
                contribution_percent=0.0,  # Will be calculated later
                reducibility="irreducible",
                attribution_details={
                    'description': 'Model form and structural assumptions uncertainty',
                    'structural_component': struct_structural
                }
            ))
        
        # Data/domain uncertainty
        if data_domain_uncertainty is not None and data_domain_uncertainty > 0:
            # Data/domain is typically epistemic (domain shift)
            data_epistemic = epistemic_components.get('data_domain', data_domain_uncertainty * 0.9) if epistemic_components else data_domain_uncertainty * 0.9
            data_aleatoric = aleatoric_components.get('data_domain', data_domain_uncertainty * 0.1) if aleatoric_components else data_domain_uncertainty * 0.1
            
            components.append(UncertaintyComponent(
                source=UncertaintySource.DATA_DOMAIN,
                uncertainty_type=UncertaintyType.EPISTEMIC,
                magnitude=data_epistemic,
                contribution_percent=0.0,  # Will be calculated later
                reducibility="reducible",
                attribution_details={
                    'description': 'Data/domain shift and distributional uncertainty',
                    'epistemic_component': data_epistemic,
                    'aleatoric_component': data_aleatoric
                }
            ))
        
        # Calculate total uncertainty (quadrature sum for independent sources)
        if components:
            total_var = sum(comp.magnitude ** 2 for comp in components)
            result.total_uncertainty = np.sqrt(total_var)
            
            # Calculate contribution percentages (attribution, not aggregation)
            for comp in components:
                comp.contribution_percent = (comp.magnitude / result.total_uncertainty) * 100 if result.total_uncertainty > 0 else 0
            
            result.uncertainty_components = components
            
            # Identify dominant source and type (attribution, not ranking)
            if components:
                dominant_comp = max(components, key=lambda c: c.contribution_percent)
                result.dominant_source = dominant_comp.source
                result.dominant_type = dominant_comp.uncertainty_type
            
            # Build contribution breakdown (attribution by source)
            result.contribution_breakdown = {
                comp.source.value: comp.contribution_percent
                for comp in components
            }
            
            # Reducibility analysis (attribution, not recommendation)
            result.reducibility_analysis = self._analyze_reducibility(components)
            
            # Attribution summary (descriptive, not recommendations)
            result.attribution_summary = self._generate_attribution_summary(components, result)
        
        return result
    
    def _analyze_reducibility(
        self,
        components: List[UncertaintyComponent]
    ) -> Dict[str, Any]:
        """
        Analyze reducibility of uncertainty sources.
        
        Phase 6.3: Attribution, not recommendations.
        """
        analysis = {
            'reducible_uncertainty': 0.0,
            'irreducible_uncertainty': 0.0,
            'partially_reducible_uncertainty': 0.0,
            'reducibility_by_source': {}
        }
        
        for comp in components:
            source_key = comp.source.value
            if comp.reducibility == "reducible":
                analysis['reducible_uncertainty'] += comp.magnitude
                analysis['reducibility_by_source'][source_key] = "reducible"
            elif comp.reducibility == "irreducible":
                analysis['irreducible_uncertainty'] += comp.magnitude
                analysis['reducibility_by_source'][source_key] = "irreducible"
            else:
                analysis['partially_reducible_uncertainty'] += comp.magnitude
                analysis['reducibility_by_source'][source_key] = "partially_reducible"
        
        # Calculate percentages (attribution, not recommendation)
        total = analysis['reducible_uncertainty'] + analysis['irreducible_uncertainty'] + analysis['partially_reducible_uncertainty']
        if total > 0:
            analysis['reducible_percent'] = (analysis['reducible_uncertainty'] / total) * 100
            analysis['irreducible_percent'] = (analysis['irreducible_uncertainty'] / total) * 100
            analysis['partially_reducible_percent'] = (analysis['partially_reducible_uncertainty'] / total) * 100
        
        return analysis
    
    def _generate_attribution_summary(
        self,
        components: List[UncertaintyComponent],
        result: UncertaintyDecompositionResult
    ) -> List[str]:
        """
        Generate attribution summary (descriptive, not recommendations).
        
        Phase 6.3: Attribution only. No rankings, no recommendations.
        """
        summary = []
        
        if not components:
            summary.append("No uncertainty components identified.")
            return summary
        
        # Total uncertainty attribution
        summary.append(
            f"Total uncertainty: {result.total_uncertainty:.4f} "
            f"(decomposed into {len(components)} sources)"
        )
        
        # Source attribution (not ranking)
        for comp in sorted(components, key=lambda c: c.contribution_percent, reverse=True):
            summary.append(
                f"{comp.source.value.replace('_', ' ').title()}: "
                f"{comp.contribution_percent:.2f}% contribution "
                f"({comp.uncertainty_type.value} uncertainty, {comp.reducibility})"
            )
        
        # Dominant source attribution (not recommendation)
        if result.dominant_source:
            summary.append(
                f"Dominant uncertainty source: {result.dominant_source.value.replace('_', ' ').title()} "
                f"({result.dominant_type.value if result.dominant_type else 'unknown'} type)"
            )
        
        # Reducibility attribution (not recommendation)
        reducible_pct = result.reducibility_analysis.get('reducible_percent', 0)
        irreducible_pct = result.reducibility_analysis.get('irreducible_percent', 0)
        summary.append(
            f"Reducibility: {reducible_pct:.1f}% reducible, "
            f"{irreducible_pct:.1f}% irreducible "
            f"(attribution only, not a recommendation)"
        )
        
        return summary


__all__ = [
    'UncertaintyType',
    'UncertaintySource',
    'UncertaintyComponent',
    'UncertaintyDecompositionResult',
    'UncertaintyDecomposer'
]

