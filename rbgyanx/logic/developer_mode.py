"""
rbgyanx.logic.developer_mode - Developer Mode (Governed Sandbox)

This module provides a governed Developer Mode sandbox for experimental models
and methods with full tracking, logging, and auditability.

Phase 7: ADVANCED mode only. Governed sandbox with mandatory tracking.
No silent execution, no bypass of provenance or structured logging.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime
import hashlib
import json
import uuid


@dataclass
class ScientificIntentMetadata:
    """
    Scientific Intent Metadata (mandatory for Developer Mode changes).
    
    Phase 7: Every developer change must declare scientific intent.
    """
    hypothesis: str  # Hypothesis being tested
    expected_failure_modes: List[str]  # Expected failure modes
    risk_level: str  # "low", "medium", "high"
    intended_scope: str  # "research_only" or "future_basic_migration"
    validation_approach: str  # How validation will be performed
    developer_id: Optional[str] = None  # Developer identifier
    timestamp: Optional[str] = None  # Timestamp of change
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'hypothesis': self.hypothesis,
            'expected_failure_modes': self.expected_failure_modes,
            'risk_level': self.risk_level,
            'intended_scope': self.intended_scope,
            'validation_approach': self.validation_approach,
            'developer_id': self.developer_id,
            'timestamp': self.timestamp or datetime.now().isoformat()
        }


@dataclass
class DeveloperModification:
    """
    Record of a developer mode modification.
    
    Phase 7: Full tracking and auditability of all modifications.
    """
    modification_id: str
    modification_type: str  # "experimental_model", "parameter_override", "method_change", etc.
    scientific_intent: ScientificIntentMetadata
    code_hash: Optional[str] = None  # Hash of modified code
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    execution_log: List[str] = field(default_factory=list)
    provenance_record_id: Optional[str] = None
    structured_log_ids: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'modification_id': self.modification_id,
            'modification_type': self.modification_type,
            'scientific_intent': self.scientific_intent.to_dict(),
            'code_hash': self.code_hash,
            'before_state': self.before_state,
            'after_state': self.after_state,
            'execution_log': self.execution_log,
            'provenance_record_id': self.provenance_record_id,
            'structured_log_ids': self.structured_log_ids,
            'timestamp': self.timestamp or datetime.now().isoformat()
        }


@dataclass
class DeveloperModeSession:
    """
    Developer Mode session record.
    
    Phase 7: Full auditability of Developer Mode sessions.
    """
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    modifications: List[DeveloperModification] = field(default_factory=list)
    experimental_models_used: List[str] = field(default_factory=list)
    provenance_records: List[str] = field(default_factory=list)
    structured_logs: List[str] = field(default_factory=list)
    session_summary: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'modifications': [m.to_dict() for m in self.modifications],
            'experimental_models_used': self.experimental_models_used,
            'provenance_records': self.provenance_records,
            'structured_logs': self.structured_logs,
            'session_summary': self.session_summary
        }


class DeveloperModeSandbox:
    """
    Governed Developer Mode sandbox for experimental models and methods.
    
    Phase 7: ADVANCED mode only. Governed sandbox with mandatory tracking.
    No silent execution, no bypass of provenance or structured logging.
    
    Design Principles:
    - Full tracking of all modifications
    - Mandatory scientific intent metadata
    - No silent execution
    - No bypass of provenance or structured logging
    - Complete auditability
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize Developer Mode sandbox.
        
        Parameters
        ----------
        session_id : Optional[str]
            Session ID (generated if not provided)
        """
        self.session_id = session_id or self._generate_session_id()
        self.current_session: Optional[DeveloperModeSession] = None
        self.modifications: List[DeveloperModification] = []
        self._audit_log: List[str] = []
        
        # Start session
        self._start_session()
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return f"dev_session_{uuid.uuid4().hex[:16]}"
    
    def _start_session(self):
        """Start a new Developer Mode session."""
        self.current_session = DeveloperModeSession(
            session_id=self.session_id,
            start_time=datetime.now().isoformat()
        )
        self._audit_log.append(f"[{datetime.now().isoformat()}] Developer Mode session started: {self.session_id}")
    
    def register_experimental_modification(
        self,
        modification_type: str,
        scientific_intent: ScientificIntentMetadata,
        code_snippet: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        provenance_record_id: Optional[str] = None,
        structured_log_ids: Optional[List[str]] = None
    ) -> DeveloperModification:
        """
        Register an experimental modification in Developer Mode.
        
        Parameters
        ----------
        modification_type : str
            Type of modification (e.g., "experimental_model", "parameter_override")
        scientific_intent : ScientificIntentMetadata
            Mandatory scientific intent metadata
        code_snippet : Optional[str]
            Code snippet (for hashing)
        before_state : Optional[Dict[str, Any]]
            State before modification
        after_state : Optional[Dict[str, Any]]
            State after modification
        provenance_record_id : Optional[str]
            Associated provenance record ID
        structured_log_ids : Optional[List[str]]
            Associated structured log IDs
            
        Returns
        -------
        DeveloperModification
            Registered modification record
        """
        # Generate modification ID
        modification_id = f"mod_{uuid.uuid4().hex[:16]}"
        
        # Calculate code hash if code snippet provided
        code_hash = None
        if code_snippet:
            code_hash = hashlib.sha256(code_snippet.encode()).hexdigest()
        
        # Create modification record
        modification = DeveloperModification(
            modification_id=modification_id,
            modification_type=modification_type,
            scientific_intent=scientific_intent,
            code_hash=code_hash,
            before_state=before_state,
            after_state=after_state,
            provenance_record_id=provenance_record_id,
            structured_log_ids=structured_log_ids or [],
            timestamp=datetime.now().isoformat()
        )
        
        # Register modification
        self.modifications.append(modification)
        if self.current_session:
            self.current_session.modifications.append(modification)
        
        # Log to audit trail
        self._audit_log.append(
            f"[{datetime.now().isoformat()}] Modification registered: {modification_id} "
            f"(Type: {modification_type}, Risk: {scientific_intent.risk_level})"
        )
        
        return modification
    
    def log_execution(
        self,
        modification_id: str,
        execution_message: str
    ):
        """
        Log execution event for a modification.
        
        Parameters
        ----------
        modification_id : str
            Modification ID
        execution_message : str
            Execution message
        """
        # Find modification
        modification = next(
            (m for m in self.modifications if m.modification_id == modification_id),
            None
        )
        
        if modification:
            modification.execution_log.append(
                f"[{datetime.now().isoformat()}] {execution_message}"
            )
            self._audit_log.append(
                f"[{datetime.now().isoformat()}] Execution logged for {modification_id}: {execution_message}"
            )
    
    def end_session(self) -> DeveloperModeSession:
        """
        End current Developer Mode session.
        
        Returns
        -------
        DeveloperModeSession
            Completed session record
        """
        if self.current_session:
            self.current_session.end_time = datetime.now().isoformat()
            
            # Generate session summary
            self.current_session.session_summary = self._generate_session_summary()
            
            # Log to audit trail
            self._audit_log.append(
                f"[{datetime.now().isoformat()}] Developer Mode session ended: {self.session_id}"
            )
            
            return self.current_session
        
        return None
    
    def get_audit_trail(self) -> List[str]:
        """
        Get complete audit trail for Developer Mode session.
        
        Returns
        -------
        List[str]
            Audit trail entries
        """
        return self._audit_log.copy()
    
    def export_session(
        self,
        output_path: Path,
        include_code: bool = False
    ) -> Path:
        """
        Export Developer Mode session to JSON file.
        
        Parameters
        ----------
        output_path : Path
            Output file path
        include_code : bool
            Whether to include code snippets in export
            
        Returns
        -------
        Path
            Exported file path
        """
        if not self.current_session:
            raise ValueError("No active session to export")
        
        # End session if still active
        if not self.current_session.end_time:
            self.end_session()
        
        # Prepare export data
        export_data = {
            'session': self.current_session.to_dict(),
            'audit_trail': self._audit_log,
            'export_timestamp': datetime.now().isoformat(),
            'export_metadata': {
                'include_code': include_code,
                'total_modifications': len(self.modifications),
                'session_duration': self._calculate_session_duration()
            }
        }
        
        # Write to file
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return output_path
    
    def _generate_session_summary(self) -> List[str]:
        """Generate session summary."""
        if not self.current_session:
            return []
        
        summary = []
        summary.append(f"Developer Mode Session: {self.session_id}")
        summary.append(f"Start Time: {self.current_session.start_time}")
        summary.append(f"End Time: {self.current_session.end_time}")
        summary.append(f"Total Modifications: {len(self.current_session.modifications)}")
        
        # Modification types breakdown
        mod_types = {}
        for mod in self.current_session.modifications:
            mod_type = mod.modification_type
            mod_types[mod_type] = mod_types.get(mod_type, 0) + 1
        
        summary.append("Modification Types:")
        for mod_type, count in sorted(mod_types.items()):
            summary.append(f"  {mod_type}: {count}")
        
        # Risk levels breakdown
        risk_levels = {}
        for mod in self.current_session.modifications:
            risk = mod.scientific_intent.risk_level
            risk_levels[risk] = risk_levels.get(risk, 0) + 1
        
        summary.append("Risk Levels:")
        for risk, count in sorted(risk_levels.items()):
            summary.append(f"  {risk}: {count}")
        
        return summary
    
    def _calculate_session_duration(self) -> Optional[str]:
        """Calculate session duration."""
        if not self.current_session or not self.current_session.end_time:
            return None
        
        start = datetime.fromisoformat(self.current_session.start_time)
        end = datetime.fromisoformat(self.current_session.end_time)
        duration = end - start
        
        return str(duration)
    
    def validate_scientific_intent(
        self,
        scientific_intent: ScientificIntentMetadata
    ) -> tuple[bool, List[str]]:
        """
        Validate scientific intent metadata.
        
        Parameters
        ----------
        scientific_intent : ScientificIntentMetadata
            Scientific intent to validate
            
        Returns
        -------
        tuple[bool, List[str]]
            (is_valid, validation_errors)
        """
        errors = []
        
        # Check required fields
        if not scientific_intent.hypothesis or not scientific_intent.hypothesis.strip():
            errors.append("Hypothesis is required")
        
        if not scientific_intent.expected_failure_modes:
            errors.append("At least one expected failure mode must be specified")
        
        if scientific_intent.risk_level not in ["low", "medium", "high"]:
            errors.append(f"Invalid risk level: {scientific_intent.risk_level}")
        
        if scientific_intent.intended_scope not in ["research_only", "future_basic_migration"]:
            errors.append(f"Invalid intended scope: {scientific_intent.intended_scope}")
        
        if not scientific_intent.validation_approach or not scientific_intent.validation_approach.strip():
            errors.append("Validation approach is required")
        
        return len(errors) == 0, errors


__all__ = [
    'ScientificIntentMetadata',
    'DeveloperModification',
    'DeveloperModeSession',
    'DeveloperModeSandbox'
]

