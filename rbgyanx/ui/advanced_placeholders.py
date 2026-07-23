"""
rbgyanx.ui.advanced_placeholders - ADVANCED Mode UI Placeholders

This module provides UI placeholders for ADVANCED mode features.

Phase 5: All placeholders are disabled (scaffolding only).
Clear research-only labeling and warnings.

Author: rbGyanX Team
Version: 1.0.0
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional


def create_advanced_placeholder_frame(parent, mode_controller, validation_controller=None) -> Optional[ttk.Frame]:
    """
    Create ADVANCED mode placeholder frame with disabled features.
    
    MODE-AWARE UI FIX: Phase 5 "LOCKED" messages only when:
    mode == ADVANCED AND validation_enabled == False
    
    When validation_enabled == True, return None (no placeholder).
    
    Parameters
    ----------
    parent : tk.Widget
        Parent widget
    mode_controller : ModeController
        Mode controller instance
    validation_controller : Optional[ValidationController]
        Validation controller instance
        
    Returns
    -------
    Optional[ttk.Frame]
        Placeholder frame, or None if validation enabled or not in ADVANCED mode
    """
    if not mode_controller or not mode_controller.is_advanced():
        return None
    
    # MODE-AWARE UI FIX: No placeholder if validation enabled
    if validation_controller and validation_controller.is_validation_enabled():
        return None  # Real ADVANCED panels should be shown instead
    
    # Only show Phase 5 locked message when ADVANCED mode but validation NOT enabled
    frame = ttk.LabelFrame(
        parent,
        text="ADVANCED Mode Features (Phase 5: Locked)",
        padding=10
    )
    
    # Warning label
    warning_text = (
        "⚠️ RESEARCH USE ONLY — NOT FOR CLINICAL USE\n\n"
        "All ADVANCED mode features are currently locked.\n"
        "This is intentional scaffolding for Phase 5.\n\n"
        "To enable ADVANCED features, enable Validation Mode.\n\n"
        "Locked Features:\n"
        "• Applicability Override: DISABLED\n"
        "• Parameter Sweep: DISABLED\n"
        "• Model Comparison: DISABLED\n"
        "• Developer Mode: DISABLED\n\n"
        "Enable Validation Mode to unlock ADVANCED features."
    )
    
    warning_label = ttk.Label(
        frame,
        text=warning_text,
        justify=tk.LEFT,
        font=('Arial', 9),
        foreground='orange',
        wraplength=500
    )
    warning_label.pack(pady=10, padx=10)
    
    # Placeholder checkboxes (all disabled)
    placeholder_frame = ttk.Frame(frame)
    placeholder_frame.pack(fill=tk.X, pady=10)
    
    # Applicability Override placeholder
    app_override_var = tk.BooleanVar(value=False)
    app_override_cb = ttk.Checkbutton(
        placeholder_frame,
        text="Applicability Override (Locked)",
        variable=app_override_var,
        state=tk.DISABLED
    )
    app_override_cb.pack(anchor=tk.W, pady=2)
    
    # Parameter Sweep placeholder
    param_sweep_var = tk.BooleanVar(value=False)
    param_sweep_cb = ttk.Checkbutton(
        placeholder_frame,
        text="Parameter Sweep (Locked)",
        variable=param_sweep_var,
        state=tk.DISABLED
    )
    param_sweep_cb.pack(anchor=tk.W, pady=2)
    
    # Model Comparison placeholder
    model_comp_var = tk.BooleanVar(value=False)
    model_comp_cb = ttk.Checkbutton(
        placeholder_frame,
        text="Model Comparison (Locked)",
        variable=model_comp_var,
        state=tk.DISABLED
    )
    model_comp_cb.pack(anchor=tk.W, pady=2)
    
    # Developer Mode placeholder
    dev_mode_var = tk.BooleanVar(value=False)
    dev_mode_cb = ttk.Checkbutton(
        placeholder_frame,
        text="Developer Mode (Locked)",
        variable=dev_mode_var,
        state=tk.DISABLED
    )
    dev_mode_cb.pack(anchor=tk.W, pady=2)
    
    return frame


__all__ = ['create_advanced_placeholder_frame']

