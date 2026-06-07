"""
rbgyanx.ui.mode_selection - Mode Selection Dialog

This module provides the startup mode selection dialog for rbGyanX.

Phase 5: ADVANCED Mode Scaffolding (Locked)
- Mode selection dialog with research-only disclaimers
- ADVANCED mode UI placeholders (all disabled)
- Clear research-only labeling
- All capabilities remain disabled

Author: rbGyanX Team
Version: 1.0.0
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rbgyanx.logic.mode_controller import ModeController, RunMode


class ModeSelectionDialog:
    """
    Startup dialog for BASIC vs ADVANCED mode selection.
    
    Phase 5: Implements mode selection with research-only disclaimers.
    All ADVANCED capabilities remain disabled (scaffolding only).
    """
    
    def __init__(self, parent: Optional[tk.Tk] = None):
        """
        Initialize mode selection dialog.
        
        Parameters
        ----------
        parent : Optional[tk.Tk]
            Parent window (if any)
        """
        self.parent = parent
        self.selected_mode_controller: Optional[ModeController] = None
        self.dialog: Optional[tk.Toplevel] = None
    
    def show(self) -> Optional[ModeController]:
        """
        Display dialog and return selected mode controller.
        
        Returns
        -------
        Optional[ModeController]
            Selected mode controller, or None if cancelled
        """
        # Create modal dialog
        self.dialog = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.dialog.title("rbGyanX Mode Selection")
        self.dialog.resizable(False, False)
        
        # Center dialog on screen - STEP 2: Ensure dialog scales to screen resolution
        self.dialog.update_idletasks()
        width = 650  # Increased for better visibility
        height = 550  # Increased for better visibility
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        # Ensure minimum width/height and respect screen bounds
        width = max(600, min(width, screen_width - 100))
        height = max(500, min(height, screen_height - 100))
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.dialog.geometry(f'{width}x{height}+{x}+{y}')
        
        # Make dialog modal
        if self.parent:
            self.dialog.transient(self.parent)
            self.dialog.grab_set()
        
        # STEP 1: Container for canvas and scrollbar
        container = ttk.Frame(self.dialog)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas with scrollbar
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # STEP 2: Create scrollable inner frame
        scrollable_frame = ttk.Frame(canvas, padding=20)
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Bind resize behavior
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Update canvas window width
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        
        # STEP 5: Mouse-wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Use scrollable_frame as main_frame (for compatibility with existing code)
        main_frame = scrollable_frame
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Select rbGyanX Operating Mode",
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 20))
        
        # Description
        desc_text = (
            "rbGyanX operates in two distinct modes:\n\n"
            "• BASIC Mode: Governed clinical and academic decision support\n"
            "• ADVANCED Mode — Research & Validation\n\n"
            "Please select your operating mode:"
        )
        desc_label = ttk.Label(
            main_frame,
            text=desc_text,
            justify=tk.LEFT,
            font=('Arial', 10)
        )
        desc_label.pack(pady=(0, 20))
        
        # Mode selection frame
        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Configure mode_frame grid for equal sizing
        mode_frame.columnconfigure(0, weight=1)
        mode_frame.columnconfigure(1, weight=1)
        
        # BASIC Mode button
        basic_frame = ttk.LabelFrame(mode_frame, text="BASIC Mode", padding=15)
        basic_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        
        basic_desc = (
            "Governed Clinical & Academic Decision Support\n\n"
            "✓ Decision support only\n"
            "✓ Conservative defaults\n"
            "✓ Validated applicability rules\n"
            "✓ Regulatory defensibility\n"
            "✓ Clinical use permitted"
        )
        basic_label = ttk.Label(
            basic_frame,
            text=basic_desc,
            justify=tk.LEFT,
            font=('Arial', 9)
        )
        basic_label.pack(pady=10, anchor="w")
        basic_label.configure(wraplength=400, justify=tk.LEFT)  # Ensure text wrapping
        
        # Spacer to push button to bottom (for alignment with ADVANCED)
        spacer_basic = ttk.Frame(basic_frame)
        spacer_basic.pack(expand=True, fill=tk.BOTH)
        
        btn_basic = ttk.Button(
            basic_frame,
            text="Select BASIC Mode",
            command=self._select_basic,
            width=20
        )
        btn_basic.pack(side="bottom", pady=20, ipadx=25, ipady=10)  # Same size as ADVANCED button
        
        # ADVANCED Mode button
        advanced_frame = ttk.LabelFrame(mode_frame, text="ADVANCED Mode — Research & Validation", padding=15)
        advanced_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        
        advanced_desc = (
            "Research & Validation\n\n"
            "⚠️ RESEARCH USE ONLY\n"
            "⚠️ NOT FOR CLINICAL USE\n\n"
            "This mode is for scientific validation and research\n"
            "using real patient data under institutional governance.\n\n"
            "Available features:\n"
            "• Model Agreement Analysis\n"
            "• Sensitivity Analysis\n"
            "• Uncertainty Decomposition\n"
            "• Robustness Analysis\n"
            "• Applicability Boundary Detection\n"
            "• Protocol Stress Testing\n"
            "• Benchmark Integration\n"
            "• Developer Mode"
        )
        advanced_label = ttk.Label(
            advanced_frame,
            text=advanced_desc,
            justify=tk.LEFT,
            font=('Arial', 9),
            foreground='#000000'  # STEP 2: Dark text on light background for better contrast
        )
        advanced_label.pack(pady=10, anchor="w")
        advanced_label.configure(wraplength=400, justify=tk.LEFT)  # Ensure text wrapping
        
        # Spacer to push button to bottom
        spacer = ttk.Frame(advanced_frame)
        spacer.pack(expand=True, fill=tk.BOTH)
        
        # ADVANCED button - explicitly packed at bottom
        btn_advanced = ttk.Button(
            advanced_frame,
            text="Select ADVANCED Mode",
            command=self._select_advanced,
            width=20
        )
        btn_advanced.pack(side="bottom", pady=20, ipadx=25, ipady=10)
        
        # Cancel button
        cancel_frame = ttk.Frame(main_frame)
        cancel_frame.pack(fill=tk.X, pady=20)
        
        btn_cancel = ttk.Button(
            cancel_frame,
            text="Cancel",
            command=self._cancel,
            width=15
        )
        btn_cancel.pack()
        
        # Wait for selection
        if self.parent:
            self.dialog.wait_window()
        else:
            self.dialog.mainloop()
        
        return self.selected_mode_controller
    
    def _select_basic(self):
        """Select BASIC mode and close dialog."""
        self.selected_mode_controller = ModeController(RunMode.BASIC)
        if self.dialog:
            self.dialog.destroy()
    
    def _select_advanced(self):
        """Show disclaimer before enabling ADVANCED mode."""
        disclaimer = (
            "ADVANCED MODE — Research & Validation\n\n"
            "⚠️ RESEARCH USE ONLY — NOT FOR CLINICAL USE ⚠️\n\n"
            "This mode is for scientific validation and research\n"
            "using real patient data under institutional governance.\n"
            "Results must NOT be used for clinical decision-making.\n\n"
            "By selecting ADVANCED mode, you acknowledge that:\n"
            "• Results are exploratory and non-clinical\n"
            "• Assumptions may violate clinical guidelines\n"
            "• Outputs may be unstable or experimental\n"
            "• No regulatory protections apply\n"
            "• Requires validation mode to be enabled\n\n"
            "Do you understand and accept these limitations?"
        )
        
        response = messagebox.askyesno(
            "Advanced Mode Warning",
            disclaimer,
            icon='warning'
        )
        
        if response:
            # Create ADVANCED mode controller
            self.selected_mode_controller = ModeController(RunMode.ADVANCED)
            
            if self.dialog:
                self.dialog.destroy()
    
    def _cancel(self):
        """Cancel mode selection."""
        self.selected_mode_controller = None
        if self.dialog:
            self.dialog.destroy()


__all__ = ['ModeSelectionDialog']

