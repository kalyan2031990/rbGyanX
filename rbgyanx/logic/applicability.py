"""
rbgyanx.logic.applicability - Model Applicability & Scientific Validity Gates

This module provides applicability checking and scientific validity gates for rbGyanX.

Layer 2 (Logic) Responsibilities:
- Model applicability validation
- Fractionation compatibility checks
- Physical vs biological branching decisions
- Transparent warnings (non-blocking, no recommendations)

Phase 3: Implements explicit applicability logic with transparent warnings.
No blocking, no recommendations - only informative warnings.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class TreatmentTechnique(Enum):
    """Treatment technique enumeration."""
    CONVENTIONAL = "conventional"  # 1.8-2.2 Gy per fraction
    HYPOFRACTIONATION = "hypofractionation"  # 2.5-5 Gy per fraction
    SBRT = "sbrt"  # Stereotactic Body Radiotherapy
    SRS = "srs"  # Stereotactic Radiosurgery
    BRACHYTHERAPY = "brachytherapy"
    UNKNOWN = "unknown"


class BiologicalModel(Enum):
    """Biological model enumeration."""
    LQ = "lq"  # Linear-Quadratic
    LQL = "lql"  # Linear-Quadratic-Linear
    MODIFIED_LQ = "modified_lq"
    GLQ = "glq"  # Generalized Linear-Quadratic
    PHYSICAL_ONLY = "physical_only"


@dataclass
class ApplicabilityWarning:
    """
    Individual applicability warning.
    
    Non-blocking, informative only. No recommendations provided.
    """
    category: str  # "fractionation", "model_validity", "dose_range", etc.
    message: str
    confidence: str  # "high", "medium", "low"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApplicabilityResult:
    """
    Result of applicability check.
    
    Provides transparent warnings without blocking execution.
    No recommendations - only informative warnings.
    """
    biological_allowed: bool  # Always True (non-blocking)
    selected_model: Optional[BiologicalModel]
    warnings: List[ApplicabilityWarning] = field(default_factory=list)
    fractionation_compatible: bool = True
    model_validity: str = "unknown"  # "valid", "limited", "questionable", "unknown"
    confidence: str = "medium"  # "high", "medium", "low"
    
    def add_warning(self, category: str, message: str, confidence: str = "medium", context: Optional[Dict[str, Any]] = None):
        """Add a warning to the result."""
        self.warnings.append(ApplicabilityWarning(
            category=category,
            message=message,
            confidence=confidence,
            context=context or {}
        ))


class ApplicabilityChecker:
    """
    Checks model applicability and scientific validity.
    
    Provides transparent warnings without blocking execution.
    No recommendations - only informative warnings about validity.
    
    Design Principles:
    - Non-blocking: Always allows execution
    - Transparent: Clear warnings about validity
    - No recommendations: User decides based on warnings
    - Scientific focus: Highlights where models are reliable/fragile
    """
    
    # Model validity matrix (from literature and manifesto)
    # Values: "valid", "limited", "questionable", "unknown"
    VALIDITY_MATRIX: Dict[TreatmentTechnique, Dict[BiologicalModel, str]] = {
        TreatmentTechnique.CONVENTIONAL: {
            BiologicalModel.LQ: "valid",
            BiologicalModel.LQL: "valid",
            BiologicalModel.MODIFIED_LQ: "valid",
            BiologicalModel.GLQ: "valid",
        },
        TreatmentTechnique.HYPOFRACTIONATION: {
            BiologicalModel.LQ: "limited",
            BiologicalModel.LQL: "valid",
            BiologicalModel.MODIFIED_LQ: "valid",
            BiologicalModel.GLQ: "valid",
        },
        TreatmentTechnique.SBRT: {
            BiologicalModel.LQ: "questionable",
            BiologicalModel.LQL: "limited",
            BiologicalModel.MODIFIED_LQ: "valid",
            BiologicalModel.GLQ: "valid",
        },
        TreatmentTechnique.SRS: {
            BiologicalModel.LQ: "questionable",
            BiologicalModel.LQL: "limited",
            BiologicalModel.MODIFIED_LQ: "valid",
            BiologicalModel.GLQ: "valid",
        },
        TreatmentTechnique.BRACHYTHERAPY: {
            BiologicalModel.LQ: "limited",
            BiologicalModel.LQL: "limited",
            BiologicalModel.MODIFIED_LQ: "questionable",
            BiologicalModel.GLQ: "questionable",
        },
        TreatmentTechnique.UNKNOWN: {
            BiologicalModel.LQ: "unknown",
            BiologicalModel.LQL: "unknown",
            BiologicalModel.MODIFIED_LQ: "unknown",
            BiologicalModel.GLQ: "unknown",
        },
    }
    
    # Fractionation compatibility thresholds
    CONVENTIONAL_RANGE = (1.8, 2.2)  # Gy per fraction
    HYPOFRACTIONATION_RANGE = (2.5, 5.0)  # Gy per fraction
    SBRT_RANGE = (5.0, 20.0)  # Gy per fraction
    SRS_RANGE = (10.0, 30.0)  # Gy per fraction
    
    def detect_technique(self, dose_per_fraction: float, n_fractions: Optional[int] = None) -> TreatmentTechnique:
        """
        Detect treatment technique from fractionation parameters.
        
        Parameters
        ----------
        dose_per_fraction : float
            Dose per fraction in Gy
        n_fractions : Optional[int]
            Number of fractions
            
        Returns
        -------
        TreatmentTechnique
            Detected treatment technique
        """
        if dose_per_fraction >= self.SRS_RANGE[0]:
            return TreatmentTechnique.SRS
        elif dose_per_fraction >= self.SBRT_RANGE[0]:
            return TreatmentTechnique.SBRT
        elif dose_per_fraction >= self.HYPOFRACTIONATION_RANGE[0]:
            return TreatmentTechnique.HYPOFRACTIONATION
        elif self.CONVENTIONAL_RANGE[0] <= dose_per_fraction <= self.CONVENTIONAL_RANGE[1]:
            return TreatmentTechnique.CONVENTIONAL
        else:
            return TreatmentTechnique.UNKNOWN
    
    def check_fractionation_compatibility(
        self,
        dose_per_fraction: float,
        n_fractions: Optional[int] = None,
        technique: Optional[TreatmentTechnique] = None
    ) -> tuple[bool, List[ApplicabilityWarning]]:
        """
        Check fractionation compatibility.
        
        Parameters
        ----------
        dose_per_fraction : float
            Dose per fraction in Gy
        n_fractions : Optional[int]
            Number of fractions
        technique : Optional[TreatmentTechnique]
            Treatment technique (if known)
            
        Returns
        -------
        tuple[bool, List[ApplicabilityWarning]]
            (is_compatible, warnings)
        """
        warnings: List[ApplicabilityWarning] = []
        is_compatible = True
        
        if technique is None:
            technique = self.detect_technique(dose_per_fraction, n_fractions)
        
        # Check dose per fraction ranges
        if technique == TreatmentTechnique.CONVENTIONAL:
            if not (self.CONVENTIONAL_RANGE[0] <= dose_per_fraction <= self.CONVENTIONAL_RANGE[1]):
                warnings.append(ApplicabilityWarning(
                    category="fractionation",
                    message=f"Dose per fraction ({dose_per_fraction:.2f} Gy) outside conventional range ({self.CONVENTIONAL_RANGE[0]}-{self.CONVENTIONAL_RANGE[1]} Gy)",
                    confidence="high",
                    context={"dose_per_fraction": dose_per_fraction, "expected_range": self.CONVENTIONAL_RANGE}
                ))
        elif technique == TreatmentTechnique.HYPOFRACTIONATION:
            if not (self.HYPOFRACTIONATION_RANGE[0] <= dose_per_fraction <= self.HYPOFRACTIONATION_RANGE[1]):
                warnings.append(ApplicabilityWarning(
                    category="fractionation",
                    message=f"Dose per fraction ({dose_per_fraction:.2f} Gy) outside hypofractionation range ({self.HYPOFRACTIONATION_RANGE[0]}-{self.HYPOFRACTIONATION_RANGE[1]} Gy)",
                    confidence="high",
                    context={"dose_per_fraction": dose_per_fraction, "expected_range": self.HYPOFRACTIONATION_RANGE}
                ))
        elif technique == TreatmentTechnique.UNKNOWN:
            warnings.append(ApplicabilityWarning(
                category="fractionation",
                message=f"Treatment technique could not be determined from dose per fraction ({dose_per_fraction:.2f} Gy)",
                confidence="medium",
                context={"dose_per_fraction": dose_per_fraction}
            ))
        
        # Check number of fractions if provided
        if n_fractions is not None:
            if n_fractions < 1:
                warnings.append(ApplicabilityWarning(
                    category="fractionation",
                    message=f"Number of fractions ({n_fractions}) is invalid",
                    confidence="high",
                    context={"n_fractions": n_fractions}
                ))
            elif technique == TreatmentTechnique.SRS and n_fractions > 5:
                warnings.append(ApplicabilityWarning(
                    category="fractionation",
                    message=f"SRS typically uses 1-5 fractions, but {n_fractions} fractions specified",
                    confidence="medium",
                    context={"n_fractions": n_fractions, "technique": technique.value}
                ))
        
        return is_compatible, warnings
    
    def check_model_validity(
        self,
        technique: TreatmentTechnique,
        model: BiologicalModel
    ) -> tuple[str, List[ApplicabilityWarning]]:
        """
        Check model validity for treatment technique.
        
        Parameters
        ----------
        technique : TreatmentTechnique
            Treatment technique
        model : BiologicalModel
            Biological model
            
        Returns
        -------
        tuple[str, List[ApplicabilityWarning]]
            (validity_status, warnings)
        """
        warnings: List[ApplicabilityWarning] = []
        
        validity = self.VALIDITY_MATRIX.get(technique, {}).get(model, "unknown")
        
        if validity == "questionable":
            warnings.append(ApplicabilityWarning(
                category="model_validity",
                message=f"{model.value.upper()} model validity is questionable for {technique.value} technique",
                confidence="high",
                context={"technique": technique.value, "model": model.value, "validity": validity}
            ))
        elif validity == "limited":
            warnings.append(ApplicabilityWarning(
                category="model_validity",
                message=f"{model.value.upper()} model has limited validity for {technique.value} technique",
                confidence="medium",
                context={"technique": technique.value, "model": model.value, "validity": validity}
            ))
        elif validity == "unknown":
            warnings.append(ApplicabilityWarning(
                category="model_validity",
                message=f"Model validity unknown for {technique.value} technique with {model.value.upper()} model",
                confidence="low",
                context={"technique": technique.value, "model": model.value, "validity": validity}
            ))
        
        return validity, warnings
    
    def check_applicability(
        self,
        dose_per_fraction: float,
        n_fractions: Optional[int] = None,
        technique: Optional[TreatmentTechnique] = None,
        requested_model: Optional[BiologicalModel] = None,
        alpha_beta_ratio: Optional[float] = None
    ) -> ApplicabilityResult:
        """
        Check overall applicability and scientific validity.
        
        Provides transparent warnings without blocking execution.
        No recommendations - only informative warnings.
        
        Parameters
        ----------
        dose_per_fraction : float
            Dose per fraction in Gy
        n_fractions : Optional[int]
            Number of fractions
        technique : Optional[TreatmentTechnique]
            Treatment technique (if known, otherwise auto-detected)
        requested_model : Optional[BiologicalModel]
            Requested biological model (if specified)
        alpha_beta_ratio : Optional[float]
            Alpha/beta ratio (for validity checks)
            
        Returns
        -------
        ApplicabilityResult
            Applicability result with warnings (non-blocking)
        """
        # Always allow biological calculation (non-blocking)
        result = ApplicabilityResult(
            biological_allowed=True,
            selected_model=requested_model or BiologicalModel.LQ
        )
        
        # Detect technique if not provided
        if technique is None:
            technique = self.detect_technique(dose_per_fraction, n_fractions)
            result.add_warning(
                category="technique_detection",
                message=f"Treatment technique auto-detected as {technique.value}",
                confidence="medium",
                context={"dose_per_fraction": dose_per_fraction, "n_fractions": n_fractions}
            )
        
        # Check fractionation compatibility
        is_compatible, fractionation_warnings = self.check_fractionation_compatibility(
            dose_per_fraction, n_fractions, technique
        )
        result.fractionation_compatible = is_compatible
        result.warnings.extend(fractionation_warnings)
        
        # Check model validity if model specified
        if requested_model:
            validity, validity_warnings = self.check_model_validity(technique, requested_model)
            result.model_validity = validity
            result.warnings.extend(validity_warnings)
            
            # Set confidence based on validity
            if validity == "valid":
                result.confidence = "high"
            elif validity == "limited":
                result.confidence = "medium"
            elif validity == "questionable":
                result.confidence = "low"
            else:
                result.confidence = "low"
        else:
            result.model_validity = "unknown"
            result.confidence = "medium"
        
        # Check alpha/beta ratio if provided
        if alpha_beta_ratio is not None:
            if alpha_beta_ratio <= 0:
                result.add_warning(
                    category="parameter_validity",
                    message=f"Alpha/beta ratio ({alpha_beta_ratio}) must be positive",
                    confidence="high",
                    context={"alpha_beta_ratio": alpha_beta_ratio}
                )
            elif alpha_beta_ratio < 0.5 or alpha_beta_ratio > 20:
                result.add_warning(
                    category="parameter_validity",
                    message=f"Alpha/beta ratio ({alpha_beta_ratio}) outside typical range (0.5-20 Gy)",
                    confidence="medium",
                    context={"alpha_beta_ratio": alpha_beta_ratio}
                )
        
        return result


__all__ = [
    'TreatmentTechnique',
    'BiologicalModel',
    'ApplicabilityWarning',
    'ApplicabilityResult',
    'ApplicabilityChecker'
]

