"""
rbgyanx.logic.ai_integration - AI Integration (Ask rbGyanX)

This module provides explanation-only AI with dual personality profiles
aligned to BASIC and ADVANCED modes.

Phase 10: Available in both modes with different personalities.
No recommendations, no actions, no rankings, no automation.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class AIPersonality(Enum):
    """AI personality profiles."""
    BASIC = "basic"  # Conservative, cautious, clinical
    ADVANCED = "advanced"  # Analytical, exploratory, research-oriented


class AIInteractionType(Enum):
    """Types of AI interactions."""
    EXPLANATION = "explanation"  # Explain concepts, models, assumptions
    DIVERGENCE_ANALYSIS = "divergence_analysis"  # Explain model divergence
    UNCERTAINTY_DISCUSSION = "uncertainty_discussion"  # Discuss uncertainty sources
    WHY_NOT_QUERY = "why_not_query"  # Structured "Why Not?" queries
    EXPERIMENT_SUGGESTION = "experiment_suggestion"  # Suggest experiments (not treatments)


@dataclass
class AIResponse:
    """
    AI response (explanation-only, no recommendations).
    
    Phase 10: Explanation-only. No recommendations, no actions, no rankings.
    """
    query: str
    response: str
    personality: AIPersonality
    interaction_type: AIInteractionType
    explanation_only: bool = True
    contains_recommendations: bool = False
    contains_actions: bool = False
    contains_rankings: bool = False
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'query': self.query,
            'response': self.response,
            'personality': self.personality.value,
            'interaction_type': self.interaction_type.value,
            'explanation_only': self.explanation_only,
            'contains_recommendations': self.contains_recommendations,
            'contains_actions': self.contains_actions,
            'contains_rankings': self.contains_rankings,
            'timestamp': self.timestamp or datetime.now().isoformat(),
            'metadata': self.metadata
        }


@dataclass
class AIPersonalityProfile:
    """
    AI personality profile for mode-aware assistance.
    
    Phase 10: Dual personality profiles aligned to BASIC and ADVANCED modes.
    """
    personality: AIPersonality
    tone: str
    allowed_interactions: List[AIInteractionType]
    forbidden_interactions: List[str]
    system_prompt: str
    constraints: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'personality': self.personality.value,
            'tone': self.tone,
            'allowed_interactions': [i.value for i in self.allowed_interactions],
            'forbidden_interactions': self.forbidden_interactions,
            'system_prompt': self.system_prompt,
            'constraints': self.constraints
        }


class AskRbGyanXIntegration:
    """
    AI Integration (Ask rbGyanX) with dual personality profiles.
    
    Phase 10: Explanation-only AI. No recommendations, no actions, no rankings, no automation.
    BASIC mode: Conservative, cautious, clinical.
    ADVANCED mode: Analytical, exploratory, research-oriented.
    
    Design Principles:
    - Explanation-only (no recommendations, no actions, no rankings)
    - Dual personality profiles (BASIC conservative, ADVANCED exploratory)
    - Mode-aware behavior
    - Structured "Why Not?" queries
    - No automation or clinical recommendations
    """
    
    # BASIC mode personality profile (conservative)
    BASIC_PROFILE = AIPersonalityProfile(
        personality=AIPersonality.BASIC,
        tone="conservative, cautious, clinical",
        allowed_interactions=[
            AIInteractionType.EXPLANATION,
            AIInteractionType.UNCERTAINTY_DISCUSSION,
        ],
        forbidden_interactions=[
            "model_comparison",
            "hypotheticals",
            "sensitivity_speculation",
            "clinical_recommendations",
            "optimization",
            "prospective_prediction",
            "experiment_suggestions",
            "rankings",
            "actions"
        ],
        system_prompt=(
            "You are a conservative clinical AI assistant for rbGyanX. "
            "Your role is to explain concepts, models, and assumptions clearly. "
            "You must be cautious and restrained in your language. "
            "NEVER provide recommendations, suggest actions, make rankings, or automate decisions. "
            "NEVER engage in comparative reasoning or speculative analysis. "
            "Focus on clear, factual explanations only."
        ),
        constraints=[
            "Explanation-only - no recommendations",
            "No actions or automation",
            "No rankings or comparisons",
            "Conservative and cautious tone",
            "Clinical and restrained language"
        ]
    )
    
    # ADVANCED mode personality profile (exploratory)
    ADVANCED_PROFILE = AIPersonalityProfile(
        personality=AIPersonality.ADVANCED,
        tone="analytical, exploratory, research-oriented",
        allowed_interactions=[
            AIInteractionType.EXPLANATION,
            AIInteractionType.DIVERGENCE_ANALYSIS,
            AIInteractionType.UNCERTAINTY_DISCUSSION,
            AIInteractionType.WHY_NOT_QUERY,
            AIInteractionType.EXPERIMENT_SUGGESTION,
        ],
        forbidden_interactions=[
            "clinical_recommendations",
            "treatment_optimization",
            "prospective_clinical_prediction",
            "plan_generation",
            "dose_optimization",
            "rankings",
            "actions",
            "automation"
        ],
        system_prompt=(
            "You are a research-oriented AI assistant for rbGyanX in ADVANCED mode. "
            "Your role is to analyze model behavior, explain divergence, and discuss assumptions. "
            "You can suggest experiments (NOT treatments) and explore hypothetical scenarios. "
            "NEVER provide clinical recommendations, suggest treatment actions, make rankings, or automate decisions. "
            "Focus on scientific exploration and understanding. "
            "Be analytical and exploratory while maintaining scientific rigor."
        ),
        constraints=[
            "Explanation-only - no clinical recommendations",
            "No actions or automation",
            "No rankings or treatment optimization",
            "Analytical and exploratory tone",
            "Research-oriented language",
            "Can suggest experiments (not treatments)"
        ]
    )
    
    def __init__(self, personality: AIPersonality):
        """
        Initialize AI integration with specified personality.
        
        Parameters
        ----------
        personality : AIPersonality
            AI personality (BASIC or ADVANCED)
        """
        self.personality = personality
        self.profile = self.BASIC_PROFILE if personality == AIPersonality.BASIC else self.ADVANCED_PROFILE
    
    def get_profile(self) -> AIPersonalityProfile:
        """
        Get current personality profile.
        
        Returns
        -------
        AIPersonalityProfile
            Current personality profile
        """
        return self.profile
    
    def validate_query(self, query: str, interaction_type: AIInteractionType) -> tuple[bool, List[str]]:
        """
        Validate query against personality profile constraints.
        
        Parameters
        ----------
        query : str
            User query
        interaction_type : AIInteractionType
            Requested interaction type
            
        Returns
        -------
        tuple[bool, List[str]]
            (is_allowed, validation_errors)
        """
        errors = []
        
        # Check if interaction type is allowed
        if interaction_type not in self.profile.allowed_interactions:
            errors.append(
                f"Interaction type '{interaction_type.value}' not allowed in {self.personality.value.upper()} mode"
            )
        
        # Check for forbidden keywords
        query_lower = query.lower()
        for forbidden in self.profile.forbidden_interactions:
            if forbidden.lower() in query_lower:
                errors.append(
                    f"Query contains forbidden interaction: '{forbidden}'"
                )
        
        return len(errors) == 0, errors
    
    def create_response(
        self,
        query: str,
        interaction_type: AIInteractionType,
        response_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse:
        """
        Create AI response with validation.
        
        Parameters
        ----------
        query : str
            User query
        interaction_type : AIInteractionType
            Interaction type
        response_text : str
            Response text
        metadata : Optional[Dict[str, Any]]
            Additional metadata
            
        Returns
        -------
        AIResponse
            AI response (explanation-only)
        """
        # Validate query
        is_allowed, errors = self.validate_query(query, interaction_type)
        if not is_allowed:
            # Return error response
            response_text = f"Query not allowed in {self.personality.value.upper()} mode: {', '.join(errors)}"
        
        # Check for forbidden content in response
        response_lower = response_text.lower()
        contains_recommendations = any(
            keyword in response_lower
            for keyword in ['recommend', 'should', 'must', 'need to', 'ought to']
        )
        contains_actions = any(
            keyword in response_lower
            for keyword in ['do this', 'perform', 'execute', 'implement', 'apply']
        )
        contains_rankings = any(
            keyword in response_lower
            for keyword in ['best', 'worst', 'better than', 'prefer', 'rank']
        )
        
        return AIResponse(
            query=query,
            response=response_text,
            personality=self.personality,
            interaction_type=interaction_type,
            explanation_only=True,
            contains_recommendations=contains_recommendations,
            contains_actions=contains_actions,
            contains_rankings=contains_rankings,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )
    
    def get_system_prompt(self) -> str:
        """
        Get system prompt for current personality.
        
        Returns
        -------
        str
            System prompt
        """
        return self.profile.system_prompt
    
    def get_constraints(self) -> List[str]:
        """
        Get constraints for current personality.
        
        Returns
        -------
        List[str]
            List of constraints
        """
        return self.profile.constraints


__all__ = [
    'AIPersonality',
    'AIInteractionType',
    'AIResponse',
    'AIPersonalityProfile',
    'AskRbGyanXIntegration'
]

