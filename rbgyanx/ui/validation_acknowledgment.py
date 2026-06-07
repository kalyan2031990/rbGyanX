"""
rbgyanx.ui.validation_acknowledgment - Validation Acknowledgment Dialog

This module provides the mandatory validation acknowledgment dialog.

FINAL CURSOR PROMPT: Explicit user acknowledgment required for validation mode.
Must explicitly state all disclaimers and constraints.

Author: rbGyanX Team
Version: 1.0.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rbgyanx.logic.validation_controller import ValidationController


class ValidationAcknowledgmentDialog:
    """
    Mandatory validation acknowledgment dialog.
    
    FINAL CURSOR PROMPT: Must explicitly state:
    - "Real patient data may be used"
    - "Clinical decision support only"
    - "No automated decisions or recommendations"
    - "Results must be interpreted by a qualified clinician"
    - "All actions are logged and traceable"
    - "NOT a treatment planning system"
    
    User must actively confirm.
    """
    
    def __init__(self, parent: Optional[tk.Tk] = None, mode: Optional[str] = None):
        """
        Initialize validation acknowledgment dialog.
        
        Parameters
        ----------
        parent : Optional[tk.Tk]
            Parent window (if any)
        mode : Optional[str]
            Operating mode (BASIC or ADVANCED)
        """
        self.parent = parent
        self.mode = mode or "BASIC"
        self.validation_controller: Optional[ValidationController] = None
        self.dialog: Optional[tk.Toplevel] = None
        self.acknowledged = False
    
    def show(self) -> Optional[ValidationController]:
        """
        Display dialog and return validation controller if acknowledged.
        
        Returns
        -------
        Optional[ValidationController]
            Validation controller if acknowledged, or None if cancelled
        """
        # Create modal dialog
        self.dialog = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.dialog.title("rbGyanX Validation Mode Acknowledgment")
        self.dialog.resizable(True, True)
        
        # Center dialog on screen
        self.dialog.update_idletasks()
        width = 800
        height = 700
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        # Make dialog modal
        if self.parent:
            self.dialog.transient(self.parent)
            self.dialog.grab_set()
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="VALIDATION MODE ACKNOWLEDGMENT",
            font=('Arial', 16, 'bold'),
            foreground='red'
        )
        title_label.pack(pady=(0, 10))
        
        # Mode indicator
        mode_label = ttk.Label(
            main_frame,
            text=f"Operating Mode: {self.mode}",
            font=('Arial', 12, 'bold')
        )
        mode_label.pack(pady=(0, 20))
        
        # Mandatory disclaimers (scrolled text)
        disclaimer_frame = ttk.LabelFrame(main_frame, text="MANDATORY ACKNOWLEDGMENTS", padding=10)
        disclaimer_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        disclaimer_text = """REAL PATIENT DATA MAY BE USED

CLINICAL DECISION SUPPORT ONLY
• rbGyanX is a clinical decision-support system
• rbGyanX is a clinical research platform
• rbGyanX is NOT an autonomous system
• rbGyanX is NOT a recommendation engine
• rbGyanX is NOT an optimizer

NO AUTOMATED DECISIONS OR RECOMMENDATIONS
• All outputs are for decision support only
• No automated treatment decisions
• No automated plan modifications
• No automated dose optimization
• No automated protocol changes

RESULTS MUST BE INTERPRETED BY A QUALIFIED CLINICIAN
• All results require clinical interpretation
• All outputs must be reviewed by qualified personnel
• No direct clinical action without human oversight
• Clinical judgment is required for all decisions

ALL ACTIONS ARE LOGGED AND TRACEABLE
• All operations are logged with provenance
• All data access is tracked
• All executions are traceable
• Complete audit trail maintained

NOT A TREATMENT PLANNING SYSTEM
• rbGyanX does not modify treatment plans
• rbGyanX does not write to TPS
• rbGyanX does not overwrite files
• rbGyanX operates in read-only mode for patient data

DATA HANDLING CONSTRAINTS
• Read-only patient data access
• Read-only DICOM/DVH access
• No plan modification
• No TPS write-back
• No file overwrite

AI CONSTRAINTS REMAIN ACTIVE
• Explanation-only AI (no recommendations)
• No action verbs
• No ranking or "best plan"
• Mode-aware personality enforced

GOVERNANCE AND SAFEGUARDS
• All governance checks remain active
• All safety constraints enforced
• All ethical constraints preserved
• No automation allowed
• No recommendations allowed"""
        
        disclaimer_text_widget = scrolledtext.ScrolledText(
            disclaimer_frame,
            wrap=tk.WORD,
            width=80,
            height=25,
            font=('Arial', 10),
            bg='#f9f9f9',
            relief=tk.SUNKEN,
            borderwidth=2
        )
        disclaimer_text_widget.insert('1.0', disclaimer_text)
        disclaimer_text_widget.config(state=tk.DISABLED)  # Read-only
        disclaimer_text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Acknowledgment checkbox
        self.acknowledge_var = tk.BooleanVar(value=False)
        acknowledge_check = ttk.Checkbutton(
            main_frame,
            text="I have read and understand all the above disclaimers and constraints",
            variable=self.acknowledge_var,
            font=('Arial', 10, 'bold')
        )
        acknowledge_check.pack(pady=20)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Enable Validation button
        btn_enable = ttk.Button(
            button_frame,
            text="Enable Validation Mode",
            command=self._enable_validation,
            width=25
        )
        btn_enable.pack(side=tk.LEFT, padx=5)
        
        # Cancel button
        btn_cancel = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            width=15
        )
        btn_cancel.pack(side=tk.RIGHT, padx=5)
        
        # Warning label
        warning_label = ttk.Label(
            main_frame,
            text="⚠️ Validation mode enables ALL capabilities. All safeguards remain active. ⚠️",
            font=('Arial', 9, 'italic'),
            foreground='orange'
        )
        warning_label.pack(pady=10)
        
        # Wait for selection
        if self.parent:
            self.dialog.wait_window()
        else:
            self.dialog.mainloop()
        
        return self.validation_controller if self.acknowledged else None
    
    def _enable_validation(self):
        """Enable validation mode if acknowledged."""
        if not self.acknowledge_var.get():
            messagebox.showwarning(
                "Acknowledgment Required",
                "You must acknowledge all disclaimers before enabling validation mode."
            )
            return
        
        # Confirm one more time
        final_confirmation = messagebox.askyesno(
            "Final Confirmation",
            "Are you absolutely certain you want to enable VALIDATION MODE?\n\n"
            "This will expose ALL capabilities for clinical validation.\n"
            "All safeguards remain active, but all features will be visible.\n\n"
            "Proceed with enabling validation mode?",
            icon='warning'
        )
        
        if final_confirmation:
            # Create validation controller
            self.validation_controller = ValidationController()
            self.validation_controller.enable_validation(
                user_identifier="user",  # Can be enhanced with actual user ID
                mode=self.mode
            )
            self.acknowledged = True
            
            if self.dialog:
                self.dialog.destroy()
    
    def _cancel(self):
        """Cancel validation enablement."""
        self.validation_controller = None
        self.acknowledged = False
        if self.dialog:
            self.dialog.destroy()


__all__ = ['ValidationAcknowledgmentDialog']
