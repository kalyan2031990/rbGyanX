"""
rbgyanx.logic.validation_controller - Validation Controller

This module provides validation enablement for clinical validation workflows.

FINAL CURSOR PROMPT: Full feature exposure for clinical validation
- Enables visibility and manual access to ALL implemented capabilities
- Preserves all governance, safety, and ethical constraints
- Requires explicit user acknowledgment

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib


@dataclass
class ValidationProfile:
    """
    Validation profile for clinical validation workflows.
    
    FINAL CURSOR PROMPT: Enables full feature exposure for validation
    while preserving all safeguards.
    """
    validation_enabled: bool = False
    acknowledgment_timestamp: Optional[str] = None
    user_identifier: Optional[str] = None
    dataset_identifiers: Dict[str, str] = field(default_factory=dict)  # name -> hash
    mode: Optional[str] = None  # BASIC or ADVANCED
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'validation_enabled': self.validation_enabled,
            'acknowledgment_timestamp': self.acknowledgment_timestamp,
            'user_identifier': self.user_identifier,
            'dataset_identifiers': self.dataset_identifiers,
            'mode': self.mode,
            'metadata': self.metadata
        }


class ValidationController:
    """
    Validation Controller for rbGyanX.
    
    FINAL CURSOR PROMPT: Enables visibility and manual access to ALL
    implemented BASIC and ADVANCED capabilities for clinical validation,
    while preserving all governance, safety, and ethical constraints.
    
    Design Principles:
    - validation_enabled = False by default
    - Explicit user acknowledgment required
    - Applies to BOTH BASIC and ADVANCED modes
    - All safeguards remain active
    - No automation, no recommendations, no plan modification
    """
    
    def __init__(self):
        """Initialize validation controller."""
        self.profile = ValidationProfile()
    
    def enable_validation(
        self,
        user_identifier: Optional[str] = None,
        mode: Optional[str] = None,
        dataset_identifiers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Enable validation mode.
        
        Parameters
        ----------
        user_identifier : Optional[str]
            User identifier for logging
        mode : Optional[str]
            Operating mode (BASIC or ADVANCED)
        dataset_identifiers : Optional[Dict[str, str]]
            Dataset identifiers (name -> hash)
        
        Returns
        -------
        bool
            True if validation enabled successfully
        """
        self.profile.validation_enabled = True
        self.profile.acknowledgment_timestamp = datetime.now().isoformat()
        self.profile.user_identifier = user_identifier
        self.profile.mode = mode
        
        if dataset_identifiers:
            self.profile.dataset_identifiers = dataset_identifiers
        
        return True
    
    def disable_validation(self):
        """Disable validation mode."""
        self.profile.validation_enabled = False
        self.profile.acknowledgment_timestamp = None
        self.profile.user_identifier = None
        self.profile.dataset_identifiers = {}
    
    def is_validation_enabled(self) -> bool:
        """
        Check if validation is enabled.
        
        Returns
        -------
        bool
            True if validation is enabled
        """
        return self.profile.validation_enabled
    
    def get_profile(self) -> ValidationProfile:
        """
        Get validation profile.
        
        Returns
        -------
        ValidationProfile
            Current validation profile
        """
        return self.profile
    
    def hash_dataset_identifier(self, dataset_name: str, dataset_path: Optional[str] = None) -> str:
        """
        Hash dataset identifier for logging.
        
        Parameters
        ----------
        dataset_name : str
            Dataset name
        dataset_path : Optional[str]
            Dataset path (if available)
        
        Returns
        -------
        str
            Hashed dataset identifier
        """
        identifier = f"{dataset_name}:{dataset_path or 'unknown'}"
        return hashlib.sha256(identifier.encode('utf-8')).hexdigest()[:16]
    
    def track_dataset(self, dataset_name: str, dataset_path: Optional[str] = None):
        """
        Track dataset identifier.
        
        Parameters
        ----------
        dataset_name : str
            Dataset name
        dataset_path : Optional[str]
            Dataset path
        """
        dataset_hash = self.hash_dataset_identifier(dataset_name, dataset_path)
        self.profile.dataset_identifiers[dataset_name] = dataset_hash


__all__ = ['ValidationProfile', 'ValidationController']
