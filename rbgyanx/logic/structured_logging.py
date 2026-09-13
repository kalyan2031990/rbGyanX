"""
rbgyanx.logic.structured_logging - Structured Logging System

This module provides structured logging for rbGyanX pipeline execution.

Layer 2 (Logic) Responsibilities:
- Structured log format with timestamps
- Stage-based logging
- Log levels and categorization
- Log serialization for reproducibility

Author: rbGyanX Team
Version: 1.0.0
"""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """Log category enumeration."""
    PIPELINE = "pipeline"
    VALIDATION = "validation"
    EXECUTION = "execution"
    RESULT = "result"
    ERROR = "error"
    METADATA = "metadata"
    AUDIT = "audit"  # Phase 7: For Developer Mode audit trail


@dataclass
class LogEntry:
    """
    Structured log entry.
    
    Provides timestamped, categorized logging for reproducibility.
    """
    timestamp: str
    level: str
    category: str
    stage: str | None
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class StructuredLogger:
    """
    Structured logger for pipeline execution.
    
    Provides deterministic, reproducible logging without changing
    scientific behavior.
    """
    
    def __init__(self, session_id: str | None = None):
        """
        Initialize structured logger.
        
        Parameters
        ----------
        session_id : Optional[str]
            Session identifier for log correlation
        """
        self.session_id = session_id
        self.start_time = time.time()
        self.entries: list[LogEntry] = []
        self.current_stage: str | None = None
        
    def _create_entry(
        self,
        level: LogLevel,
        category: LogCategory,
        message: str,
        metadata: dict[str, Any] | None = None
    ) -> LogEntry:
        """Create a log entry."""
        timestamp = datetime.now().isoformat()
        entry = LogEntry(
            timestamp=timestamp,
            level=level.value,
            category=category.value,
            stage=self.current_stage,
            message=message,
            metadata=metadata or {}
        )
        self.entries.append(entry)
        return entry
    
    def set_stage(self, stage: str):
        """Set current execution stage."""
        self.current_stage = stage
    
    def debug(self, message: str, category: LogCategory = LogCategory.PIPELINE, metadata: dict[str, Any] | None = None):
        """Log debug message."""
        self._create_entry(LogLevel.DEBUG, category, message, metadata)
    
    def info(self, message: str, category: LogCategory = LogCategory.PIPELINE, metadata: dict[str, Any] | None = None):
        """Log info message."""
        self._create_entry(LogLevel.INFO, category, message, metadata)
    
    def warning(self, message: str, category: LogCategory = LogCategory.PIPELINE, metadata: dict[str, Any] | None = None):
        """Log warning message."""
        self._create_entry(LogLevel.WARNING, category, message, metadata)
    
    def error(self, message: str, category: LogCategory = LogCategory.ERROR, metadata: dict[str, Any] | None = None):
        """Log error message."""
        self._create_entry(LogLevel.ERROR, category, message, metadata)
    
    def critical(self, message: str, category: LogCategory = LogCategory.ERROR, metadata: dict[str, Any] | None = None):
        """Log critical message."""
        self._create_entry(LogLevel.CRITICAL, category, message, metadata)
    
    def log_stage_start(self, stage: str, metadata: dict[str, Any] | None = None):
        """Log stage start."""
        self.set_stage(stage)
        self.info(f"Stage started: {stage}", LogCategory.EXECUTION, metadata)
    
    def log_stage_end(self, stage: str, metadata: dict[str, Any] | None = None):
        """Log stage end."""
        self.info(f"Stage completed: {stage}", LogCategory.EXECUTION, metadata)
    
    def log_result(self, result_type: str, result_data: Any, metadata: dict[str, Any] | None = None):
        """Log result."""
        result_metadata = {'result_type': result_type, 'result_data': str(result_data)}
        if metadata:
            result_metadata.update(metadata)
        self.info(f"Result: {result_type}", LogCategory.RESULT, result_metadata)
    
    def get_entries(self, level: LogLevel | None = None, category: LogCategory | None = None) -> list[LogEntry]:
        """Get log entries with optional filtering."""
        entries = self.entries
        if level:
            entries = [e for e in entries if e.level == level.value]
        if category:
            entries = [e for e in entries if e.category == category.value]
        return entries
    
    def get_messages(self) -> list[str]:
        """Get all log messages as simple strings."""
        return [f"[{e.level}] {e.message}" for e in self.entries]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert all entries to dictionary."""
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'entries': [e.to_dict() for e in self.entries]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert all entries to JSON."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save(self, filepath: str | Path):
        """Save logs to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(self.to_json())


__all__ = [
    'LogLevel',
    'LogCategory',
    'LogEntry',
    'StructuredLogger'
]

