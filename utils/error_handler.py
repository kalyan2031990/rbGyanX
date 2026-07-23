"""
rbGyanX v1.0 - Comprehensive Error Handling System
===================================================
Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

Centralized error handling with logging and user feedback.

Author: rbGyanX Team
License: MIT
"""

import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import sys

# Try to import tkinter for GUI error dialogs
try:
    import tkinter.messagebox as messagebox
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


# ── Custom Exceptions ───────────────────────────────────────────────────────────

class rbGyanXError(Exception):
    """Base exception for rbGyanX errors"""
    pass


class DVHProcessingError(rbGyanXError):
    """DVH file processing error"""
    pass


class ClinicalDataError(rbGyanXError):
    """Clinical data error"""
    pass


class ModelingError(rbGyanXError):
    """NTCP/TCP modeling error"""
    pass


class FileFormatError(rbGyanXError):
    """Unsupported file format error"""
    pass


# ── Error Handler Class ─────────────────────────────────────────────────────────

class ErrorHandler:
    """
    Centralized error handling with logging and user feedback.
    
    Attributes
    ----------
    log_file : Path
        Path to log file
    errors : List[Dict]
        List of recorded errors
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize the Error Handler.
        
        Parameters
        ----------
        log_file : Path or str, optional
            Path to log file. Defaults to "rbgyanx_execution.log" in current directory.
        """
        if log_file is None:
            self.log_file = Path("rbgyanx_execution.log")
        else:
            self.log_file = Path(log_file)
        
        self.errors = []
        
        # Create log file with header
        self._initialize_log()
    
    def _initialize_log(self):
        """Initialize log file with header"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"rbGyanX v1.0 - Execution Log\n")
            f.write(f"{'='*70}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*70}\n\n")
    
    def log(self, message: str, level: str = "INFO"):
        """
        Log message to file and console.
        
        Parameters
        ----------
        message : str
            Message to log
        level : str, default "INFO"
            Log level: INFO, WARNING, ERROR, CRITICAL
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        
        # Console output with emoji indicators
        if level == "ERROR" or level == "CRITICAL":
            print(f"❌ {log_entry}")
        elif level == "WARNING":
            print(f"⚠️  {log_entry}")
        else:
            print(f"ℹ️  {log_entry}")
        
        # File logging
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    
    def handle_error(self, error: Exception, context: str = "", 
                    show_gui: bool = False) -> str:
        """
        Handle error with detailed logging and user feedback.
        
        Parameters
        ----------
        error : Exception
            The exception that occurred
        context : str, default ""
            Context where error occurred (e.g., "Step 1: DVH Preprocessing")
        show_gui : bool, default False
            Show GUI error dialog (if tkinter available)
        
        Returns
        -------
        str
            User-friendly error message with suggestions
        """
        # Extract error details
        error_type = type(error).__name__
        error_msg = str(error)
        stack_trace = traceback.format_exc()
        
        # Log error
        self.log(f"Error in {context}", "ERROR")
        self.log(f"Type: {error_type}", "ERROR")
        self.log(f"Message: {error_msg}", "ERROR")
        self.log(f"Stack trace:\n{stack_trace}", "ERROR")
        
        # Store error
        self.errors.append({
            'context': context,
            'type': error_type,
            'message': error_msg,
            'timestamp': datetime.now(),
            'stack_trace': stack_trace
        })
        
        # Generate helpful message
        helpful_msg = self.generate_helpful_message(error_type, error_msg, context)
        
        # GUI popup if requested
        if show_gui and GUI_AVAILABLE:
            self.show_error_dialog(context, error_msg, helpful_msg)
        
        return helpful_msg
    
    def generate_helpful_message(self, error_type: str, error_msg: str, 
                                context: str) -> str:
        """
        Generate user-friendly error message with suggestions.
        
        Parameters
        ----------
        error_type : str
            Type of error
        error_msg : str
            Error message
        context : str
            Context where error occurred
        
        Returns
        -------
        str
            Formatted helpful message
        """
        # File not found errors
        if "No such file" in error_msg or "FileNotFoundError" in error_type or "not found" in error_msg.lower():
            return (
                "❌ File Not Found\n\n"
                "Reason: The selected file or directory does not exist.\n\n"
                "Solutions:\n"
                "1. Check the file path is correct\n"
                "2. Verify the file has not been moved or deleted\n"
                "3. Ensure you have read permissions\n"
                f"4. Error details: {error_msg}\n"
            )
        
        # DVH parsing errors
        elif "Could not parse DVH" in error_msg or "DVH" in context or "parse" in error_msg.lower():
            return (
                "❌ DVH File Format Error\n\n"
                "Reason: rbGyanX could not understand the DVH file format.\n\n"
                "Supported Formats:\n"
                "- Varian Eclipse TXT export\n"
                "- Simple CSV (Dose[Gy], Volume[cm3])\n"
                "- DICOM RT files (.dcm) - Coming in v1.1\n\n"
                "Solutions:\n"
                "1. Check file is a valid DVH export from your TPS\n"
                "2. Verify file is not corrupted\n"
                "3. Try exporting in a different format\n"
                "4. Contact support with sample file for format addition\n"
                f"5. Error details: {error_msg}\n"
            )
        
        # Clinical data errors
        elif "Clinical" in context or "could not auto-detect" in error_msg.lower() or "column" in error_msg.lower():
            return (
                "❌ Clinical Data Format Error\n\n"
                "Reason: Column structure not recognized.\n\n"
                "Required Columns:\n"
                "- Patient ID (PatientID, Patient_ID, etc.)\n"
                "- Toxicity outcome (Observed_Toxicity, Toxicity, etc.)\n"
                "- Optional: Organ, Technique, Dose, etc.\n\n"
                "Solutions:\n"
                "1. Rename columns to standard names\n"
                "2. Use CLI mode for manual column selection\n"
                "3. Check example clinical data format in documentation\n"
                f"4. Error details: {error_msg}\n"
            )
        
        # ML/data insufficiency errors
        elif "Insufficient" in error_msg or "need ≥5" in error_msg or "events" in error_msg.lower():
            return (
                "❌ Insufficient Data for Machine Learning\n\n"
                "Reason: Not enough positive events (toxicity cases).\n\n"
                "Requirements:\n"
                "- Minimum 5 positive events (toxicity=1)\n"
                "- Minimum 20 total samples\n"
                "- Recommended: 30+ samples with 10+ events\n\n"
                "Solutions:\n"
                "1. Disable ML models (use traditional models only)\n"
                "2. Combine multiple toxicity grades (Grade 2+ = 1)\n"
                "3. Collect more patient data\n"
                f"4. Error details: {error_msg}\n"
            )
        
        # DICOM errors
        elif "DICOM" in error_msg or "NotImplementedError" in error_type:
            return (
                "❌ DICOM Support Not Available\n\n"
                "Reason: DICOM RT DVH extraction is planned for rbGyanX v1.1.\n\n"
                "Solutions:\n"
                "1. Export DVH data from your TPS as TXT or CSV format\n"
                "2. Use Eclipse TXT export (recommended)\n"
                "3. Wait for v1.1 release with DICOM support\n"
                f"4. Error details: {error_msg}\n"
            )
        
        # Import errors
        elif "ImportError" in error_type or "ModuleNotFoundError" in error_type:
            return (
                "❌ Missing Required Package\n\n"
                f"Reason: {error_msg}\n\n"
                "Solutions:\n"
                "1. Install missing package: pip install <package_name>\n"
                "2. Check requirements.txt for all dependencies\n"
                "3. Ensure virtual environment is activated\n"
                "4. Reinstall: pip install -r requirements.txt\n"
            )
        
        # Generic error
        else:
            return (
                f"❌ Unexpected Error in {context}\n\n"
                f"Error Type: {error_type}\n"
                f"Message: {error_msg}\n\n"
                "Solutions:\n"
                "1. Check execution log for details\n"
                f"2. Log file: {self.log_file}\n"
                "3. Try running individual steps to isolate issue\n"
                "4. Report bug with log file to developers\n"
            )
    
    def show_error_dialog(self, context: str, error_msg: str, helpful_msg: str):
        """
        Show GUI error dialog with helpful information.
        
        Parameters
        ----------
        context : str
            Context where error occurred
        error_msg : str
            Original error message
        helpful_msg : str
            Helpful message with suggestions
        """
        if not GUI_AVAILABLE:
            return
        
        messagebox.showerror(
            title=f"rbGyanX Error - {context}",
            message=helpful_msg
        )
    
    def get_error_summary(self) -> str:
        """
        Get summary of all errors encountered.
        
        Returns
        -------
        str
            Formatted error summary
        """
        if not self.errors:
            return "No errors encountered"
        
        summary = f"Total errors: {len(self.errors)}\n\n"
        for i, err in enumerate(self.errors, 1):
            summary += f"{i}. {err['context']}\n"
            summary += f"   Type: {err['type']}\n"
            summary += f"   Message: {err['message']}\n"
            summary += f"   Time: {err['timestamp'].strftime('%H:%M:%S')}\n\n"
        
        return summary
    
    def clear_errors(self):
        """Clear all recorded errors"""
        self.errors = []
    
    def save_summary(self, output_path: Path):
        """
        Save error summary to file.
        
        Parameters
        ----------
        output_path : Path
            Path to save summary file
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"rbGyanX v1.0 - Error Summary\n")
            f.write(f"{'='*70}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*70}\n\n")
            f.write(self.get_error_summary())

