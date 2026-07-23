"""
rbgyanx.logic.provenance - Provenance Tracking and Reproducibility

This module provides provenance tracking and reproducibility mechanisms for rbGyanX.

Layer 2 (Logic) Responsibilities:
- Input/output hashing for reproducibility
- Configuration tracking
- Execution provenance records
- Deterministic execution support

Author: rbGyanX Team
Version: 1.0.0
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import numpy as np


@dataclass
class ProvenanceRecord:
    """
    Provenance record for a pipeline execution.
    
    Tracks all inputs, configuration, and execution metadata
    needed to reproduce an analysis exactly.
    """
    session_id: str
    execution_id: str
    timestamp: str
    pipeline_version: str
    input_hash: str
    config_hash: str
    execution_mode: str
    steps_executed: List[str]
    execution_time: float
    input_paths: Dict[str, str] = field(default_factory=dict)
    output_paths: Dict[str, str] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save(self, filepath: Union[str, Path]):
        """Save provenance record to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.to_json())


class ProvenanceTracker:
    """
    Tracks provenance information for pipeline execution.
    
    Provides deterministic execution support and reproducibility
    mechanisms without changing scientific behavior.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize provenance tracker.
        
        Parameters
        ----------
        session_id : Optional[str]
            Session identifier. If None, generates a new one.
        """
        self.session_id = session_id or self._generate_session_id()
        self.execution_id = self._generate_execution_id()
        self.start_time = time.time()
        self.timestamp = datetime.now().isoformat()
        self.steps_executed: List[str] = []
        self.input_paths: Dict[str, str] = {}
        self.output_paths: Dict[str, str] = {}
        self.configuration: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        
    @staticmethod
    def _generate_session_id() -> str:
        """Generate unique session identifier."""
        import uuid
        return f"rbgyanx-{uuid.uuid4().hex[:12]}"
    
    @staticmethod
    def _generate_execution_id() -> str:
        """Generate unique execution identifier."""
        import uuid
        return f"exec-{uuid.uuid4().hex[:8]}"
    
    def hash_input(self, input_data: Any) -> str:
        """
        Generate deterministic hash of input data.
        
        Parameters
        ----------
        input_data : Any
            Input data to hash (dict, list, Path, str, etc.)
            
        Returns
        -------
        str
            SHA256 hash of input data
        """
        if isinstance(input_data, Path):
            # Hash file path and modification time
            if input_data.exists():
                stat = input_data.stat()
                data = f"{input_data.resolve()}:{stat.st_mtime}:{stat.st_size}"
            else:
                data = str(input_data.resolve())
        elif isinstance(input_data, (dict, list)):
            # Hash JSON representation
            data = json.dumps(input_data, sort_keys=True, default=str)
        elif isinstance(input_data, (int, float, str, bool, type(None))):
            # Hash string representation
            data = str(input_data)
        else:
            # Fallback: string representation
            data = str(input_data)
        
        return hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    def hash_configuration(self, config: Dict[str, Any]) -> str:
        """
        Generate deterministic hash of configuration.
        
        Parameters
        ----------
        config : Dict[str, Any]
            Configuration dictionary
            
        Returns
        -------
        str
            SHA256 hash of configuration
        """
        # Sort keys for deterministic hashing
        sorted_config = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(sorted_config.encode('utf-8')).hexdigest()
    
    def track_input(self, name: str, path: Union[str, Path]):
        """Track input file path."""
        self.input_paths[name] = str(Path(path).resolve())
    
    def track_output(self, name: str, path: Union[str, Path]):
        """Track output file path."""
        self.output_paths[name] = str(Path(path).resolve())
    
    def track_step(self, step_name: str):
        """Track executed step."""
        self.steps_executed.append(step_name)
    
    def track_config(self, key: str, value: Any):
        """Track configuration value."""
        self.configuration[key] = value
    
    def track_metadata(self, key: str, value: Any):
        """Track metadata value."""
        self.metadata[key] = value
    
    def create_record(
        self,
        pipeline_input: Any,
        execution_mode: str,
        pipeline_version: str = "1.0.0"
    ) -> ProvenanceRecord:
        """
        Create provenance record from tracked information.
        
        Parameters
        ----------
        pipeline_input : Any
            Pipeline input object
        execution_mode : str
            Execution mode ('pipeline' or 'subprocess')
        pipeline_version : str
            Pipeline version string
            
        Returns
        -------
        ProvenanceRecord
            Complete provenance record
        """
        # Hash inputs
        input_hash = self.hash_input(pipeline_input)
        
        # Hash configuration
        config_hash = self.hash_configuration(self.configuration)
        
        # Calculate execution time
        execution_time = time.time() - self.start_time
        
        return ProvenanceRecord(
            session_id=self.session_id,
            execution_id=self.execution_id,
            timestamp=self.timestamp,
            pipeline_version=pipeline_version,
            input_hash=input_hash,
            config_hash=config_hash,
            execution_mode=execution_mode,
            steps_executed=self.steps_executed.copy(),
            execution_time=execution_time,
            input_paths=self.input_paths.copy(),
            output_paths=self.output_paths.copy(),
            configuration=self.configuration.copy(),
            metadata=self.metadata.copy()
        )


def create_provenance_record(
    pipeline_input: Any,
    execution_mode: str,
    steps_executed: List[str],
    execution_time: float,
    input_paths: Optional[Dict[str, str]] = None,
    output_paths: Optional[Dict[str, str]] = None,
    configuration: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    pipeline_version: str = "1.0.0"
) -> ProvenanceRecord:
    """
    Create a provenance record for pipeline execution.
    
    Parameters
    ----------
    pipeline_input : Any
        Pipeline input object
    execution_mode : str
        Execution mode ('pipeline' or 'subprocess')
    steps_executed : List[str]
        List of executed steps
    execution_time : float
        Total execution time in seconds
    input_paths : Optional[Dict[str, str]]
        Dictionary of input file paths
    output_paths : Optional[Dict[str, str]]
        Dictionary of output file paths
    configuration : Optional[Dict[str, Any]]
        Configuration dictionary
    metadata : Optional[Dict[str, Any]]
        Additional metadata
    session_id : Optional[str]
        Session identifier
    pipeline_version : str
        Pipeline version string
        
    Returns
    -------
    ProvenanceRecord
        Complete provenance record
    """
    tracker = ProvenanceTracker(session_id=session_id)
    tracker.steps_executed = steps_executed
    tracker.execution_time = execution_time
    if input_paths:
        tracker.input_paths = input_paths
    if output_paths:
        tracker.output_paths = output_paths
    if configuration:
        tracker.configuration = configuration
    if metadata:
        tracker.metadata = metadata
    
    return tracker.create_record(pipeline_input, execution_mode, pipeline_version)


__all__ = ['ProvenanceRecord', 'ProvenanceTracker', 'create_provenance_record']

