"""
rbgyanx.logic.education_training - Education & Training Workflows

This module provides teaching overlays, structured learning paths, and
demonstrations of non-intuitive radiobiological behavior (plateaus, cliffs, fragility).

Phase 11: No scoring, no recommendations, no pass/fail logic.
Educational demonstrations only.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import numpy as np


class LearningTopic(Enum):
    """Learning topics for education workflows."""
    TCP_PLATEAU = "tcp_plateau"
    NTCP_CLIFF = "ntcp_cliff"
    SMALL_VOLUME_DOMINANCE = "small_volume_dominance"
    FRAGILITY = "fragility"
    APPLICABILITY_BOUNDARIES = "applicability_boundaries"
    MODEL_DIVERGENCE = "model_divergence"


class TeachingOverlayType(Enum):
    """Types of teaching overlays."""
    VISUALIZATION = "visualization"
    ANNOTATION = "annotation"
    EXPLANATION = "explanation"
    INTERACTIVE_DEMO = "interactive_demo"


@dataclass
class PlateauRegion:
    """
    Region where TCP plateaus (saturation awareness).
    
    Phase 11: Demonstrates non-intuitive TCP saturation behavior.
    """
    dose_range: Tuple[float, float]
    tcp_range: Tuple[float, float]
    gradient_threshold: float = 0.01  # ∂TCP/∂Dose threshold
    saturation_level: float = 0.0
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'dose_range': self.dose_range,
            'tcp_range': self.tcp_range,
            'gradient_threshold': self.gradient_threshold,
            'saturation_level': self.saturation_level,
            'explanation': self.explanation,
            'metadata': self.metadata
        }


@dataclass
class CliffRegion:
    """
    Region where NTCP has steep gradient (cliff detection).
    
    Phase 11: Demonstrates non-intuitive NTCP cliff behavior.
    """
    dose_range: Optional[Tuple[float, float]] = None
    volume_range: Optional[Tuple[float, float]] = None
    ntcp_range: Tuple[float, float] = (0.0, 1.0)
    gradient_threshold: float = 0.10  # ∂NTCP/∂Dose or ∂NTCP/∂Volume threshold
    cliff_severity: float = 0.0
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'dose_range': self.dose_range,
            'volume_range': self.volume_range,
            'ntcp_range': self.ntcp_range,
            'gradient_threshold': self.gradient_threshold,
            'cliff_severity': self.cliff_severity,
            'explanation': self.explanation,
            'metadata': self.metadata
        }


@dataclass
class FragilityZone:
    """
    Zone where small parameter changes cause large outcome changes.
    
    Phase 11: Demonstrates non-intuitive fragility behavior.
    """
    parameter_name: str
    parameter_range: Tuple[float, float]
    outcome_sensitivity: float = 0.0
    fragility_index: float = 0.0
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'parameter_name': self.parameter_name,
            'parameter_range': self.parameter_range,
            'outcome_sensitivity': self.outcome_sensitivity,
            'fragility_index': self.fragility_index,
            'explanation': self.explanation,
            'metadata': self.metadata
        }


@dataclass
class TeachingOverlay:
    """
    Teaching overlay for educational demonstrations.
    
    Phase 11: No scoring, no recommendations, no pass/fail logic.
    """
    overlay_type: TeachingOverlayType
    topic: LearningTopic
    title: str
    content: str
    visual_elements: Dict[str, Any] = field(default_factory=dict)
    annotations: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'overlay_type': self.overlay_type.value,
            'topic': self.topic.value,
            'title': self.title,
            'content': self.content,
            'visual_elements': self.visual_elements,
            'annotations': self.annotations,
            'timestamp': self.timestamp or datetime.now().isoformat(),
            'metadata': self.metadata
        }


@dataclass
class LearningPathStep:
    """
    Step in a structured learning path.
    
    Phase 11: Educational progression without pass/fail logic.
    """
    step_number: int
    topic: LearningTopic
    title: str
    description: str
    teaching_overlay: Optional[TeachingOverlay] = None
    prerequisites: List[str] = field(default_factory=list)
    learning_objectives: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'step_number': self.step_number,
            'topic': self.topic.value,
            'title': self.title,
            'description': self.description,
            'teaching_overlay': self.teaching_overlay.to_dict() if self.teaching_overlay else None,
            'prerequisites': self.prerequisites,
            'learning_objectives': self.learning_objectives,
            'metadata': self.metadata
        }


@dataclass
class StructuredLearningPath:
    """
    Structured learning path for education workflows.
    
    Phase 11: No scoring, no recommendations, no pass/fail logic.
    Educational progression only.
    """
    path_name: str
    path_description: str
    steps: List[LearningPathStep]
    estimated_duration: Optional[str] = None
    target_audience: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'path_name': self.path_name,
            'path_description': self.path_description,
            'steps': [step.to_dict() for step in self.steps],
            'estimated_duration': self.estimated_duration,
            'target_audience': self.target_audience,
            'metadata': self.metadata
        }


@dataclass
class NonIntuitiveBehaviorDemo:
    """
    Demonstration of non-intuitive radiobiological behavior.
    
    Phase 11: Educational demonstration without recommendations or scoring.
    """
    demo_name: str
    topic: LearningTopic
    description: str
    plateaus: List[PlateauRegion] = field(default_factory=list)
    cliffs: List[CliffRegion] = field(default_factory=list)
    fragility_zones: List[FragilityZone] = field(default_factory=list)
    teaching_overlays: List[TeachingOverlay] = field(default_factory=list)
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'demo_name': self.demo_name,
            'topic': self.topic.value,
            'description': self.description,
            'plateaus': [p.to_dict() for p in self.plateaus],
            'cliffs': [c.to_dict() for c in self.cliffs],
            'fragility_zones': [f.to_dict() for f in self.fragility_zones],
            'teaching_overlays': [o.to_dict() for o in self.teaching_overlays],
            'explanation': self.explanation,
            'metadata': self.metadata
        }


@dataclass
class EducationTrainingResult:
    """
    Result from education & training workflows.
    
    Phase 11: No scoring, no recommendations, no pass/fail logic.
    """
    learning_paths: List[StructuredLearningPath] = field(default_factory=list)
    demonstrations: List[NonIntuitiveBehaviorDemo] = field(default_factory=list)
    teaching_overlays: List[TeachingOverlay] = field(default_factory=list)
    disclaimer: str = "EDUCATIONAL USE ONLY - No scoring, no recommendations, no pass/fail logic"
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'learning_paths': [path.to_dict() for path in self.learning_paths],
            'demonstrations': [demo.to_dict() for demo in self.demonstrations],
            'teaching_overlays': [overlay.to_dict() for overlay in self.teaching_overlays],
            'disclaimer': self.disclaimer,
            'timestamp': self.timestamp or datetime.now().isoformat(),
            'metadata': self.metadata
        }


class EducationTrainingWorkflow:
    """
    Education & Training Workflows for rbGyanX.
    
    Phase 11: Teaching overlays, structured learning paths, and demonstrations
    of non-intuitive radiobiological behavior (plateaus, cliffs, fragility).
    
    Design Principles:
    - No scoring, no recommendations, no pass/fail logic
    - Educational demonstrations only
    - Bridge between equations and intuition
    - Training platform for residents and physicists
    """
    
    def __init__(self):
        """Initialize education & training workflow."""
        self.disclaimer = "EDUCATIONAL USE ONLY - No scoring, no recommendations, no pass/fail logic"
    
    def create_tcp_plateau_demo(
        self,
        dose_values: np.ndarray,
        tcp_values: np.ndarray,
        gradient_threshold: float = 0.01
    ) -> NonIntuitiveBehaviorDemo:
        """
        Create demonstration of TCP plateau (saturation behavior).
        
        Parameters
        ----------
        dose_values : np.ndarray
            Dose values (Gy)
        tcp_values : np.ndarray
            TCP values
        gradient_threshold : float
            Gradient threshold for plateau detection
            
        Returns
        -------
        NonIntuitiveBehaviorDemo
            TCP plateau demonstration
        """
        # Detect plateau regions (where gradient is below threshold)
        plateaus = []
        for i in range(len(dose_values) - 1):
            gradient = abs(tcp_values[i + 1] - tcp_values[i]) / (dose_values[i + 1] - dose_values[i] + 1e-10)
            if gradient < gradient_threshold:
                plateau = PlateauRegion(
                    dose_range=(float(dose_values[i]), float(dose_values[i + 1])),
                    tcp_range=(float(tcp_values[i]), float(tcp_values[i + 1])),
                    gradient_threshold=gradient_threshold,
                    saturation_level=float(tcp_values[i]),
                    explanation="TCP saturates in this dose range - further escalation provides minimal benefit",
                    metadata={'gradient': float(gradient)}
                )
                plateaus.append(plateau)
        
        # Create teaching overlay
        overlay = TeachingOverlay(
            overlay_type=TeachingOverlayType.VISUALIZATION,
            topic=LearningTopic.TCP_PLATEAU,
            title="TCP Plateau Paradox",
            content=(
                "Human intuition: Higher dose → higher TCP → always better\n"
                "Reality: TCP plateaus due to clonogen limits and hypoxia.\n"
                "Further dose escalation provides negligible tumor benefit."
            ),
            annotations=[
                f"Plateau detected in {len(plateaus)} dose range(s)",
                "Gradient threshold: {:.4f}".format(gradient_threshold)
            ],
            metadata={'plateau_count': len(plateaus)}
        )
        
        return NonIntuitiveBehaviorDemo(
            demo_name="TCP Plateau Demonstration",
            topic=LearningTopic.TCP_PLATEAU,
            description="Demonstrates TCP saturation behavior where further dose escalation provides minimal benefit",
            plateaus=plateaus,
            teaching_overlays=[overlay],
            explanation=(
                "TCP plateaus occur when the tumor control probability saturates "
                "due to biological limits (clonogen exhaustion, hypoxia). "
                "This demonstrates that 'more dose' is not always 'better'."
            )
        )
    
    def create_ntcp_cliff_demo(
        self,
        dose_values: np.ndarray,
        ntcp_values: np.ndarray,
        gradient_threshold: float = 0.10
    ) -> NonIntuitiveBehaviorDemo:
        """
        Create demonstration of NTCP cliff (steep gradient behavior).
        
        Parameters
        ----------
        dose_values : np.ndarray
            Dose values (Gy)
        ntcp_values : np.ndarray
            NTCP values
        gradient_threshold : float
            Gradient threshold for cliff detection
            
        Returns
        -------
        NonIntuitiveBehaviorDemo
            NTCP cliff demonstration
        """
        # Detect cliff regions (where gradient exceeds threshold)
        cliffs = []
        for i in range(len(dose_values) - 1):
            gradient = abs(ntcp_values[i + 1] - ntcp_values[i]) / (dose_values[i + 1] - dose_values[i] + 1e-10)
            if gradient > gradient_threshold:
                cliff = CliffRegion(
                    dose_range=(float(dose_values[i]), float(dose_values[i + 1])),
                    ntcp_range=(float(ntcp_values[i]), float(ntcp_values[i + 1])),
                    gradient_threshold=gradient_threshold,
                    cliff_severity=float(gradient),
                    explanation="NTCP has steep gradient in this dose range - small changes matter significantly",
                    metadata={'gradient': float(gradient)}
                )
                cliffs.append(cliff)
        
        # Create teaching overlay
        overlay = TeachingOverlay(
            overlay_type=TeachingOverlayType.VISUALIZATION,
            topic=LearningTopic.NTCP_CLIFF,
            title="NTCP Cliff Detection",
            content=(
                "Human intuition: Linear dose-response relationships\n"
                "Reality: NTCP has steep regions (cliffs) where small dose changes "
                "cause large toxicity probability changes."
            ),
            annotations=[
                f"Cliff detected in {len(cliffs)} dose range(s)",
                "Gradient threshold: {:.4f}".format(gradient_threshold)
            ],
            metadata={'cliff_count': len(cliffs)}
        )
        
        return NonIntuitiveBehaviorDemo(
            demo_name="NTCP Cliff Demonstration",
            topic=LearningTopic.NTCP_CLIFF,
            description="Demonstrates NTCP cliff behavior where small dose changes cause large toxicity changes",
            cliffs=cliffs,
            teaching_overlays=[overlay],
            explanation=(
                "NTCP cliffs occur when the normal tissue complication probability "
                "has steep gradients. Small dose changes in these regions can cause "
                "large changes in toxicity risk."
            )
        )
    
    def create_fragility_demo(
        self,
        parameter_name: str,
        parameter_values: np.ndarray,
        outcome_values: np.ndarray,
        sensitivity_threshold: float = 0.5
    ) -> NonIntuitiveBehaviorDemo:
        """
        Create demonstration of fragility zones.
        
        Parameters
        ----------
        parameter_name : str
            Parameter name (e.g., 'alpha_beta_ratio', 'dose_per_fraction')
        parameter_values : np.ndarray
            Parameter values
        outcome_values : np.ndarray
            Outcome values (e.g., TCP, NTCP)
        sensitivity_threshold : float
            Sensitivity threshold for fragility detection
            
        Returns
        -------
        NonIntuitiveBehaviorDemo
            Fragility zone demonstration
        """
        # Calculate sensitivity (outcome change per parameter change)
        fragilities = []
        for i in range(len(parameter_values) - 1):
            param_change = abs(parameter_values[i + 1] - parameter_values[i])
            if param_change > 1e-10:
                outcome_change = abs(outcome_values[i + 1] - outcome_values[i])
                sensitivity = outcome_change / param_change
                
                if sensitivity > sensitivity_threshold:
                    fragility = FragilityZone(
                        parameter_name=parameter_name,
                        parameter_range=(float(parameter_values[i]), float(parameter_values[i + 1])),
                        outcome_sensitivity=float(sensitivity),
                        fragility_index=float(sensitivity),
                        explanation=f"Small changes in {parameter_name} cause large outcome changes in this range",
                        metadata={'sensitivity': float(sensitivity)}
                    )
                    fragilities.append(fragility)
        
        # Create teaching overlay
        overlay = TeachingOverlay(
            overlay_type=TeachingOverlayType.VISUALIZATION,
            topic=LearningTopic.FRAGILITY,
            title="Fragility Zone Detection",
            content=(
                f"Human intuition: Linear, predictable relationships\n"
                f"Reality: Fragility zones exist where small {parameter_name} changes "
                f"cause large outcome changes. This violates intuition about robustness."
            ),
            annotations=[
                f"Fragility zones detected: {len(fragilities)}",
                f"Sensitivity threshold: {sensitivity_threshold:.4f}"
            ],
            metadata={'fragility_count': len(fragilities)}
        )
        
        return NonIntuitiveBehaviorDemo(
            demo_name=f"Fragility Zone Demonstration ({parameter_name})",
            topic=LearningTopic.FRAGILITY,
            description=f"Demonstrates fragility zones where small {parameter_name} changes cause large outcome changes",
            fragility_zones=fragilities,
            teaching_overlays=[overlay],
            explanation=(
                f"Fragility zones occur when small changes in {parameter_name} "
                f"cause large changes in outcomes. This demonstrates non-intuitive "
                f"radiobiological behavior where models are sensitive to parameter variations."
            )
        )
    
    def create_learning_path(
        self,
        path_name: str,
        path_description: str,
        topics: List[LearningTopic]
    ) -> StructuredLearningPath:
        """
        Create structured learning path.
        
        Parameters
        ----------
        path_name : str
            Learning path name
        path_description : str
            Learning path description
        topics : List[LearningTopic]
            List of learning topics
            
        Returns
        -------
        StructuredLearningPath
            Structured learning path
        """
        steps = []
        for idx, topic in enumerate(topics, 1):
            step = LearningPathStep(
                step_number=idx,
                topic=topic,
                title=f"Learning Step {idx}: {topic.value.replace('_', ' ').title()}",
                description=f"Educational step covering {topic.value.replace('_', ' ')}",
                learning_objectives=[
                    f"Understand {topic.value.replace('_', ' ')}",
                    f"Recognize non-intuitive behavior in {topic.value.replace('_', ' ')}"
                ],
                metadata={'topic': topic.value}
            )
            steps.append(step)
        
        return StructuredLearningPath(
            path_name=path_name,
            path_description=path_description,
            steps=steps,
            target_audience="Residents and physicists",
            metadata={'topic_count': len(topics)}
        )
    
    def generate_education_session(
        self,
        include_plateaus: bool = True,
        include_cliffs: bool = True,
        include_fragility: bool = True
    ) -> EducationTrainingResult:
        """
        Generate education & training session.
        
        Parameters
        ----------
        include_plateaus : bool
            Include TCP plateau demonstrations
        include_cliffs : bool
            Include NTCP cliff demonstrations
        include_fragility : bool
            Include fragility zone demonstrations
            
        Returns
        -------
        EducationTrainingResult
            Education & training session result
        """
        demonstrations = []
        
        # Create TCP plateau demo
        if include_plateaus:
            dose_vals = np.linspace(60, 80, 100)
            tcp_vals = 1 - np.exp(-0.1 * dose_vals) * (1 + 0.05 * dose_vals)
            tcp_vals = np.clip(tcp_vals, 0, 1)
            plateau_demo = self.create_tcp_plateau_demo(dose_vals, tcp_vals)
            demonstrations.append(plateau_demo)
        
        # Create NTCP cliff demo
        if include_cliffs:
            dose_vals = np.linspace(40, 70, 100)
            ntcp_vals = 1 / (1 + np.exp(-0.2 * (dose_vals - 55)))
            cliff_demo = self.create_ntcp_cliff_demo(dose_vals, ntcp_vals)
            demonstrations.append(cliff_demo)
        
        # Create fragility demo
        if include_fragility:
            alpha_beta_vals = np.linspace(1, 10, 100)
            outcome_vals = 0.5 + 0.3 * np.sin(alpha_beta_vals / 2)
            fragility_demo = self.create_fragility_demo('alpha_beta_ratio', alpha_beta_vals, outcome_vals)
            demonstrations.append(fragility_demo)
        
        # Create learning path
        topics = [LearningTopic.TCP_PLATEAU, LearningTopic.NTCP_CLIFF, LearningTopic.FRAGILITY]
        learning_path = self.create_learning_path(
            "Non-Intuitive Radiobiological Behavior",
            "Learn about plateaus, cliffs, and fragility in radiobiological models",
            topics
        )
        
        # Collect teaching overlays
        teaching_overlays = []
        for demo in demonstrations:
            teaching_overlays.extend(demo.teaching_overlays)
        
        return EducationTrainingResult(
            learning_paths=[learning_path],
            demonstrations=demonstrations,
            teaching_overlays=teaching_overlays,
            disclaimer=self.disclaimer,
            metadata={
                'include_plateaus': include_plateaus,
                'include_cliffs': include_cliffs,
                'include_fragility': include_fragility
            }
        )


__all__ = [
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
    'EducationTrainingWorkflow'
]
