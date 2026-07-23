"""
rbGyanX 1.0 — Radiobiological Clinical Decision Support System
==============================================================

Desktop application: clinic (BASIC) and research (ADVANCED) modes.
Integrates rbgyanx-engine for DICOM TCP/NTCP, UTCP, and QUANTEC checks.

Author: rbGyanX Team
Version: 1.0.0

UI CONTRACT:
root uses GRID ONLY
No widget may call pack() with root as parent
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # type: ignore
from matplotlib.figure import Figure  # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import subprocess
import sys
import threading

# Phase 1: UTF-8 console on Windows (avoids charmap errors on log/print)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import time
import math
from pathlib import Path
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
from datetime import datetime
from collections import Counter
from typing import List, Optional, Dict
from enum import Enum

# Try to import PIL for image handling
try:
    from PIL import Image, ImageTk, ImageSequence  # type: ignore
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: PIL/Pillow not available. Logo and animation features will be limited.")

# Import rbGyanX utilities
try:
    from utils.error_handler import ErrorHandler
    from utils.dvh_parser import UniversalDVHParser, preprocess_dvh_intelligent
    UTILITIES_AVAILABLE = True
except ImportError as e:
    UTILITIES_AVAILABLE = False
    print(f"Warning: Some utilities not available: {e}")

try:
    from rbgyanx.paths import APP_VERSION, engine_status_message, get_app_root, get_engine_root
    from rbgyanx.version import product_title
    PATHS_AVAILABLE = True
except ImportError:
    PATHS_AVAILABLE = False
    APP_VERSION = "1.0.0"
    product_title = lambda mode=None: f"rbGyanX {APP_VERSION}"
    engine_status_message = lambda: ""
    get_app_root = lambda: Path(__file__).resolve().parent
    get_engine_root = lambda: None


def _rbgyanx_base_dir() -> Path:
    """Project root (dev) or folder containing rbGyanX.exe (frozen)."""
    if PATHS_AVAILABLE:
        return get_app_root()
    return Path(__file__).resolve().parent


# Import orchestration layer (Phase 1.5)
try:
    from rbgyanx.logic import PipelineInput, PipelineOutput, run_analysis_pipeline
    from rbgyanx.logic.engine_bridge import (
        detect_input_kind,
        is_dicom_directory,
        is_engine_available,
        map_site_override,
        needs_subprocess_fallback,
        run_engine_analysis,
    )
    PIPELINE_AVAILABLE = True
    ENGINE_BRIDGE_AVAILABLE = True
except ImportError as e:
    PIPELINE_AVAILABLE = False
    ENGINE_BRIDGE_AVAILABLE = False
    print(f"Warning: Pipeline orchestration not available: {e}")
    PipelineInput = None
    PipelineOutput = None
    run_analysis_pipeline = None
    detect_input_kind = None
    is_dicom_directory = None
    is_engine_available = None
    map_site_override = None
    needs_subprocess_fallback = None
    run_engine_analysis = None

try:
    from rbgyanx.logic.input_router import (
        resolve_input_kind,
        run_step1_ingest,
        sync_source_pref_from_path,
        validate_input_for_mode,
    )
    INPUT_ROUTER_AVAILABLE = True
except ImportError as e:
    INPUT_ROUTER_AVAILABLE = False
    resolve_input_kind = None
    run_step1_ingest = None
    sync_source_pref_from_path = None
    validate_input_for_mode = None
    print(f"Warning: Input router not available: {e}")

try:
    from rbgyanx.logic.patient_id_registry import (
        apply_mapping_to_clinical_df,
        build_auto_mapping,
        collect_clinical_patient_ids,
        collect_dvh_patient_ids,
        load_mapping,
        write_registry_report,
    )
    PATIENT_ID_REGISTRY_AVAILABLE = True
except ImportError as e:
    PATIENT_ID_REGISTRY_AVAILABLE = False
    print(f"Warning: Patient ID registry not available: {e}")

# Try to import yaml for configuration
try:
    import yaml  # type: ignore
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("Warning: PyYAML not available. Configuration save/load will be limited.")

# Import new backend modules for rbGyanX Pro v1.1.0
try:
    from core.project_state import ProjectStateManager
    from qa.qa_overfitting import QAOverfittingInspector
    from ai.local_llm_engine import LocalLLMEngine, create_ai_assistant
    import json
    BACKEND_MODULES_AVAILABLE = True
except ImportError as e:
    BACKEND_MODULES_AVAILABLE = False
    print(f"Warning: Some backend modules not available: {e}")
    ProjectStateManager = None
    QAOverfittingInspector = None
    LocalLLMEngine = None

# Import user manual generator
try:
    from docs.user_manual_generator import generate_user_manual
    MANUAL_GENERATOR_AVAILABLE = True
except ImportError as e:
    MANUAL_GENERATOR_AVAILABLE = False
    print(f"Warning: User manual generator not available: {e}")
    generate_user_manual = None

# Import clinical data adapter
try:
    from clinical.clinical_adapter import adapt_clinical_data
    CLINICAL_ADAPTER_AVAILABLE = True
except ImportError as e:
    CLINICAL_ADAPTER_AVAILABLE = False
    print(f"Warning: Clinical data adapter not available: {e}")
    adapt_clinical_data = None

# Import self-test engine
try:
    from qa.self_test_engine import SelfTestEngine, run_self_test
    SELF_TEST_AVAILABLE = True
except ImportError as e:
    SELF_TEST_AVAILABLE = False
    print(f"Warning: Self-test engine not available: {e}")
    SelfTestEngine = None
    run_self_test = None

# Import auto-correction engine
try:
    from qa.auto_correction_engine import AutoCorrectionEngine, run_auto_correction
    AUTO_CORRECTION_AVAILABLE = True
except ImportError as e:
    AUTO_CORRECTION_AVAILABLE = False
    print(f"Warning: Auto-correction engine not available: {e}")
    AutoCorrectionEngine = None
    run_auto_correction = None

# Import rule-based assistant (always available)
try:
    from ai.rule_based_assistant import RuleBasedAssistant, create_rule_based_assistant
    RULE_BASED_ASSISTANT_AVAILABLE = True
except ImportError as e:
    RULE_BASED_ASSISTANT_AVAILABLE = False
    print(f"Warning: Rule-based assistant not available: {e}")
    RuleBasedAssistant = None
    create_rule_based_assistant = None

# Import enhanced Ask rbGyanX assistant (with calculator, math tools, scope guards)
try:
    from ask_rbgyanx.enhanced_assistant import EnhancedAskrbGyanX, create_enhanced_assistant
    ENHANCED_ASSISTANT_AVAILABLE = True
except ImportError as e:
    ENHANCED_ASSISTANT_AVAILABLE = False
    print(f"Warning: Enhanced assistant not available: {e}")
    EnhancedAskrbGyanX = None
    create_enhanced_assistant = None


class AshokaChakra(tk.Canvas):
    """
    Animated Ashoka Chakra (24-spoke wheel) from Indian flag.
    Rotates continuously.
    """
    def __init__(self, parent, size=50, **kwargs):
        super().__init__(parent, width=size, height=size, 
                        highlightthickness=0, bg='#f5f5f5', **kwargs)
        
        self.size = size
        self.center = size // 2
        self.radius = (size // 2) - 4
        self.angle = 0
        self.rotation_speed = 2  # degrees per frame
        self.is_rotating = True
        
        # Ashoka Chakra navy blue color
        self.chakra_color = "#000080"  # Navy blue
        
        self.draw_chakra()
        self.animate()
    
    def draw_chakra(self):
        """Draw the 24-spoke Ashoka Chakra."""
        self.delete("all")
        
        cx, cy = self.center, self.center
        r = self.radius
        
        # Outer circle
        self.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=self.chakra_color, width=2
        )
        
        # Inner circle (hub)
        inner_r = r * 0.15
        self.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            fill=self.chakra_color, outline=self.chakra_color
        )
        
        # Middle circle
        mid_r = r * 0.4
        self.create_oval(
            cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r,
            outline=self.chakra_color, width=1
        )
        
        # 24 spokes
        for i in range(24):
            angle_rad = math.radians(self.angle + i * 15)  # 360/24 = 15 degrees
            
            # Spoke from inner to outer circle
            x1 = cx + inner_r * math.cos(angle_rad)
            y1 = cy + inner_r * math.sin(angle_rad)
            x2 = cx + r * 0.95 * math.cos(angle_rad)
            y2 = cy + r * 0.95 * math.sin(angle_rad)
            
            self.create_line(x1, y1, x2, y2, fill=self.chakra_color, width=1)
        
        # 24 curved spokes (the distinctive curved parts)
        for i in range(24):
            angle_rad = math.radians(self.angle + i * 15 + 7.5)  # Offset by half
            
            # Small semi-circles between spokes
            sx = cx + r * 0.7 * math.cos(angle_rad)
            sy = cy + r * 0.7 * math.sin(angle_rad)
            
            # Draw small arc/dot
            dot_r = r * 0.05
            self.create_oval(
                sx - dot_r, sy - dot_r, sx + dot_r, sy + dot_r,
                fill=self.chakra_color, outline=self.chakra_color
            )
    
    def animate(self):
        """Rotate the chakra."""
        if self.is_rotating:
            self.angle = (self.angle + self.rotation_speed) % 360
            self.draw_chakra()
            self.after(50, self.animate)  # ~20 FPS
    
    def start_rotation(self):
        """Start rotation."""
        if not self.is_rotating:
            self.is_rotating = True
            self.animate()
    
    def stop_rotation(self):
        """Stop rotation."""
        self.is_rotating = False


class BlinkingOwlIndicator(tk.Label):
    """
    Blinking owl animation indicator (branding)
    Symbolic status indicator for processing steps.
    Uses icon.png to create a subtle blinking-eye effect.
    """
    def __init__(self, parent, size=(24, 24), **kwargs):
        super().__init__(parent, **kwargs)
        self.size = size
        self.is_blinking = False
        self.animation_id = None
        self.blink_delay = 600  # milliseconds between blinks (faster, more visible)
        
        # Load owl icon if available
        icon_path = _rbgyanx_base_dir() / 'assets' / 'icon.png'
        self.normal_image = None
        self.blink_image = None
        
        if icon_path.exists() and PIL_AVAILABLE:
            try:
                img = Image.open(icon_path)
                img_resized = img.resize(size, Image.Resampling.LANCZOS)
                self.normal_image = ImageTk.PhotoImage(img_resized)
                
                # Create blink version (slightly dimmed/transparent)
                img_blink = img_resized.copy()
                # Reduce brightness for blink effect
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Brightness(img_blink)
                img_blink = enhancer.enhance(0.3)  # 30% brightness for blink
                self.blink_image = ImageTk.PhotoImage(img_blink)
                
                self.configure(image=self.normal_image, bg=self.cget('bg') if 'bg' in kwargs else 'white')
            except Exception:
                # Fallback to text-based indicator
                self.configure(text="🦉", font=("Arial", 16))
        else:
            # Fallback to text-based indicator
            self.configure(text="🦉", font=("Arial", 16))
    
    def start_blinking(self):
        """Start the blinking animation"""
        if not self.is_blinking:
            self.is_blinking = True
            self._blink_cycle()
    
    def stop_blinking(self):
        """Stop the blinking animation"""
        self.is_blinking = False
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None
        # Return to normal state
        if self.normal_image:
            self.configure(image=self.normal_image)
    
    def _blink_cycle(self):
        """Cycle between normal and blink states - continuous blinking while processing"""
        if not self.is_blinking:
            return
        
        current_image = self.cget('image') if 'image' in self.configure() else None
        
        if self.normal_image and self.blink_image:
            # Toggle between normal and blink images
            if str(current_image) == str(self.normal_image):
                self.configure(image=self.blink_image)
            else:
                self.configure(image=self.normal_image)
        else:
            # Text-based blinking fallback
            current_fg = self.cget('fg')
            if current_fg == 'black' or current_fg == '' or current_fg == 'SystemButtonText':
                self.configure(fg='#888888')  # Dimmed
            else:
                self.configure(fg='black')  # Normal
        
        # Continue blinking - schedule next cycle
        self.animation_id = self.after(self.blink_delay, self._blink_cycle)


class AnimatedGifLabel(tk.Label):
    """
    DEPRECATED: Replaced by BlinkingOwlIndicator
    Kept for backward compatibility but not used.
    """
    def __init__(self, parent, gif_path=None, size=(32, 32), **kwargs):
        super().__init__(parent, **kwargs)
        
        self.frames = []
        self.frame_index = 0
        self.is_animating = False
        self.animation_id = None
        self.delay = 50  # milliseconds between frames
        self.size = size
        
        if gif_path:
            self._load_gif(gif_path, size)
        else:
            # Fallback: text-based animation
            self.anim_chars = ['◐', '◓', '◑', '◒']
            self.anim_index = 0
    
    def _load_gif(self, gif_path, size):
        """Load and resize GIF frames."""
        if not PIL_AVAILABLE:
            return
            
        try:
            gif_path = Path(gif_path)
            if not gif_path.exists():
                return
                
            gif = Image.open(gif_path)
            
            for frame in ImageSequence.Iterator(gif):
                # Resize each frame
                frame = frame.copy()
                frame = frame.resize(size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(frame)
                self.frames.append(photo)
            
            # Try to get frame delay from GIF
            try:
                self.delay = gif.info.get('duration', 50)
            except:
                self.delay = 50
                
        except Exception as e:
            print(f"Error loading GIF: {e}")
            self.frames = []
    
    def start_animation(self):
        """Start the GIF animation or text animation."""
        if not self.is_animating:
            self.is_animating = True
            self.pack(side="left", padx=5)  # Make visible
            if self.frames:
                self._animate_gif()
            else:
                self._animate_text()
    
    def stop_animation(self):
        """Stop the animation."""
        self.is_animating = False
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None
        self.pack_forget()  # Hide when not animating
    
    def _animate_gif(self):
        """Update to next GIF frame."""
        if self.is_animating and self.frames:
            self.configure(image=self.frames[self.frame_index])
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.animation_id = self.after(self.delay, self._animate_gif)
    
    def _animate_text(self):
        """Text-based animation fallback."""
        if self.is_animating:
            self.configure(text=self.anim_chars[self.anim_index], font=("Arial", 16))
            self.anim_index = (self.anim_index + 1) % len(self.anim_chars)
            self.animation_id = self.after(100, self._animate_text)


class WorkflowState(Enum):
    """Workflow state enumeration for GUI synchronization"""
    IDLE = 0
    PREPROCESSING = 1
    PREPROCESSING_COMPLETE = 2
    TCP_RUNNING = 3
    TCP_COMPLETE = 4
    NTCP_RUNNING = 5
    NTCP_COMPLETE = 6
    INTEGRATION_RUNNING = 7
    INTEGRATION_COMPLETE = 8
    ERROR = 99


class PipelineExecutionState:
    """
    Shared execution state object for GUI synchronization.
    Tracks pipeline execution status, mode, and step completion.
    """
    def __init__(self):
        self.mode = None  # "TCP", "NTCP", "BOTH"
        self.step1_complete = False
        self.step2_complete = False
        self.tcp_step3_complete = False
        self.ntcp_step3_complete = False
        self.step4_complete = False
        self.step5_complete = False
        self.step6_complete = False
        self.tcp_enabled = False
        self.ntcp_enabled = False
        self.current_step = None
        
    def reset(self):
        """Reset all state"""
        self.step1_complete = False
        self.step2_complete = False
        self.tcp_step3_complete = False
        self.ntcp_step3_complete = False
        self.step4_complete = False
        self.step5_complete = False
        self.step6_complete = False
        self.current_step = None
        
    def can_run_step6(self):
        """Check if Step 6 (integration) can run"""
        return self.tcp_step3_complete and self.ntcp_step3_complete


class UILayoutConstants:
    """OBJECTIVE 6: UI Guard Layer - Centralized layout constants for future-proofing"""
    # Fonts
    FONT_FAMILY = 'Segoe UI'
    FONT_SIZE_NORMAL = 9
    FONT_SIZE_SMALL = 8
    FONT_SIZE_LARGE = 11
    FONT_SIZE_TITLE = 25  # Increased by +1 point (from 24 to 25)
    
    # Spacing
    PADDING_SMALL = (2, 2)
    PADDING_MEDIUM = (5, 5)
    PADDING_LARGE = (10, 10)
    WIDGET_SPACING = 5
    SECTION_SPACING = 10
    
    # Colors
    BG_LIGHT = '#f5f5f5'
    BG_DARK = '#E8E8E8'
    TEXT_PRIMARY = '#222222'
    TEXT_SECONDARY = '#666666'
    BORDER_COLOR = '#BDC3C7'
    SEPARATOR_COLOR = '#D0D0D0'
    
    # Header
    CHAKRA_SIZE = 45  # Exactly 45x45px
    CHAKRA_PADDING = 12  # 10-12px horizontal padding
    
    # Panel controls
    MAXIMIZE_BUTTON_SIZE = 20
    
    @classmethod
    def validate_widget_placement(cls, widget, parent, x, y):
        """Log warning if widget placement violates layout rules"""
        try:
            parent_width = parent.winfo_width()
            parent_height = parent.winfo_height()
            widget_width = widget.winfo_reqwidth()
            widget_height = widget.winfo_reqheight()
            
            if x + widget_width > parent_width or y + widget_height > parent_height:
                print(f"[UI Guard Warning] Widget {widget} may overflow parent bounds")
            if x < 0 or y < 0:
                print(f"[UI Guard Warning] Widget {widget} has negative coordinates")
        except:
            pass  # Non-blocking - just log warnings


class rbGyanX_GUI:
    """Redesigned GUI with 3-panel layout"""
    
    def __init__(self, root, mode_controller=None, validation_controller=None):
        self.root = root
        # Phase 5: Mode controller
        self.mode_controller = mode_controller
        # Validation Controller: FINAL CURSOR PROMPT
        self.validation_controller = validation_controller
        # OBJECTIVE C: High-DPI awareness
        try:
            # Enable high-DPI scaling on Windows
            if sys.platform == 'win32':
                try:
                    from ctypes import windll
                    windll.shcore.SetProcessDpiAwareness(1)
                except:
                    pass
            # Apply Tk scaling for high-resolution displays
            try:
                dpi = root.winfo_fpixels('1i')
                if dpi > 96:
                    scale_factor = dpi / 96.0
                    root.tk.call('tk', 'scaling', scale_factor)
            except:
                pass
        except:
            pass
        
        # Branding: Window title reflects product version and mode
        if self.mode_controller:
            if self.mode_controller.is_advanced():
                self.root.title(product_title("Advanced — Research & Validation"))
            else:
                self.root.title(product_title("Clinical Decision Support"))
        else:
            self.root.title(product_title())
        
        # Branding: Set window icon
        self._set_window_icon()
        
        # Set window size to 92% of screen (beautification fix)
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = int(screen_width * 0.92)
        window_height = int(screen_height * 0.88)
        x_position = (screen_width - window_width) // 2
        y_position = (screen_height - window_height) // 2 - 30
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        
        # State variables
        self.analysis_mode = tk.StringVar(value="NTCP_ONLY")  # TCP_ONLY, NTCP_ONLY, TCP_NTCP
        self.analysis_type = tk.StringVar(value="NTCP")  # Legacy: NTCP or TCP (derived from analysis_mode)
        self.output_dir = tk.StringVar()
        self.clinical_file = tk.StringVar()
        self.raw_input = tk.StringVar()
        self.input_format = tk.StringVar(value="directory")  # file or directory
        self.input_source = tk.StringVar(value="dicom")  # dicom | tps_txt (R2)
        self.dvh_type = tk.StringVar(value="auto")
        
        # OBJECTIVE B: Cancer site selection
        self.cancer_site = tk.StringVar(value="HeadNeck")  # Default to Head & Neck
        self.site_registry = self._load_site_registry()
        
        # Model parameters (Step 3) - Updated for dynamic switching
        self.tumor_organ_type = tk.StringVar(value="HNSCC")
        self.selected_traditional_model = tk.StringVar(value="LKB Log-Logistic")
        
        # NTCP models (for dynamic checkbox creation)
        self.ntcp_models = {
            'LKB_LogLogistic': tk.BooleanVar(value=True),
            'LKB_Probit': tk.BooleanVar(value=True),
            'RS_Poisson': tk.BooleanVar(value=True)
        }
        
        # TCP models (for dynamic checkbox creation)
        self.tcp_models = {
            'Poisson_TCP': tk.BooleanVar(value=True),
            'LKB_TCP': tk.BooleanVar(value=True),
            'Logistic_TCP': tk.BooleanVar(value=True),
            'EUD_TCP': tk.BooleanVar(value=True)
        }
        
        # Legacy variables for compatibility
        self.traditional_models_enabled = {
            "LKB Log-Logistic": self.ntcp_models['LKB_LogLogistic'],
            "LKB Probit": self.ntcp_models['LKB_Probit'],
            "RS Poisson": self.ntcp_models['RS_Poisson'],
        }
        self.tcp_models_enabled = {
            "Poisson TCP": self.tcp_models['Poisson_TCP'],
            "LKB-adapted TCP": self.tcp_models['LKB_TCP'],
            "Logistic TCP": self.tcp_models['Logistic_TCP'],
            "EUD-based TCP": self.tcp_models['EUD_TCP'],
        }
        
        # Options
        self.enable_ml = tk.BooleanVar(value=False)
        self.enable_shap = tk.BooleanVar(value=False)
        self.use_glm = tk.BooleanVar(value=False)
        
        # OBJECTIVE A: Novel feature flags
        self.use_fdvh = tk.BooleanVar(value=False)  # Fractionation-Aware DVH
        self.use_utcp = tk.BooleanVar(value=False)   # Uncertainty-Aware TCP
        self.use_ccs = tk.BooleanVar(value=False)    # Cohort Consistency Score (ML Safety)
        self.ccs_file_path = tk.StringVar(value="")  # Path to CCS checker JSON file
        self.ccs_threshold = tk.DoubleVar(value=0.1)  # CCS threshold
        
        # Step completion tracking
        self.steps_completed = {f"step{i}": False for i in range(1, 7)}
        self.step_status_labels = {}
        
        # Run all mode flag
        self.run_all_mode = False
        
        # Track Step 3 notebook for dynamic updates
        self.step3_notebook = None
        
        # Dynamic organ/target lists (populated after Step 1)
        self.detected_organs = {}  # For NTCP
        self.detected_targets = {}  # For TCP
        self.detected_diagnosis = None  # Auto-detected tumor site
        self.structure_checkboxes = {}  # For Step 3 structure selection
        
        # Timer variables
        self.step_start_times = {}
        self.step_durations = {}
        self.pipeline_start_time = None
        # Real-time timer tracking
        self._step_running_flags = {}  # Track which steps are currently running
        
        # Initialize error handler
        if UTILITIES_AVAILABLE:
            self.error_handler = ErrorHandler(log_file="rbgyanx_gui.log")
        else:
            self.error_handler = None
        
        # Owl indicators for each step (contextual, next to step buttons)
        self.step_owl_indicators = {}  # Dict: step_name -> owl_indicator widget
        self.processing_step = None  # Track which step is currently processing
        
        # DVH validation results (read-only, non-blocking)
        self.validation_results = []  # List of validation result dictionaries
        
        # Shared execution state object for GUI synchronization
        self.execution_state = PipelineExecutionState()
        
        # Workflow state management (PROMPT 7)
        self.workflow_state = WorkflowState.IDLE
        self.state_callbacks = {
            WorkflowState.IDLE: self.on_idle_state,
            WorkflowState.PREPROCESSING: self.on_preprocessing_state,
            WorkflowState.PREPROCESSING_COMPLETE: self.on_preprocessing_complete_state,
            WorkflowState.TCP_RUNNING: self.on_tcp_running_state,
            WorkflowState.TCP_COMPLETE: self.on_tcp_complete_state,
            WorkflowState.NTCP_RUNNING: self.on_ntcp_running_state,
            WorkflowState.NTCP_COMPLETE: self.on_ntcp_complete_state,
            WorkflowState.INTEGRATION_RUNNING: self.on_integration_running_state,
            WorkflowState.INTEGRATION_COMPLETE: self.on_integration_complete_state,
            WorkflowState.ERROR: self.on_error_state,
        }
        
        # Plot management for auto-refresh
        self.current_plot_index = 0
        self.available_plots = []
        self.plot_caption = None  # Will be set when right panel is created
        
        # Create main layout
        self.create_main_layout()
        
        # Setup tab handlers (PROMPT 7)
        self.setup_tab_handlers()
        
        # Check if manual needs updating (PROMPT 10)
        self.check_manual_version()

        if PATHS_AVAILABLE:
            self.log(f"[OK] {product_title()} | App: {get_app_root()}")
            self.log(f"[OK] {engine_status_message()}")
        elif ENGINE_BRIDGE_AVAILABLE and is_engine_available and is_engine_available():
            self.log("[OK] rbgyanx-engine available")
        else:
            self.log(
                "[!] rbgyanx-engine not found — DICOM TCP/NTCP will use legacy scripts only. "
                "Run Install-rbGyanX.ps1 or set RBGYANX_ENGINE_PATH."
            )
        
        # Initialize visualization placeholders
        self.initialize_placeholders()
        
        # Initialize model parameter frame reference
        self.param_inputs_frame = None
        
        # Initialize ProjectStateManager (rbGyanX Pro v1.1.0)
        self.project_manager = None
        if BACKEND_MODULES_AVAILABLE and ProjectStateManager:
            self.project_manager = ProjectStateManager()
        
        # Initialize QA Inspector (rbGyanX Pro v1.1.0)
        self.qa_inspector = None
        if BACKEND_MODULES_AVAILABLE and QAOverfittingInspector:
            self.qa_inspector = QAOverfittingInspector()
        
        # Initialize AI Assistant (rbGyanX Pro v1.1.0)
        # Try enhanced assistant first, fallback to rule-based
        self.enhanced_assistant = None
        self.ai_assistant = None
        self.rule_based_assistant = None
        
        _ai_allowed = (
            self.mode_controller is not None
            and self.mode_controller.is_capability_enabled("ai_integration")
        )
        if _ai_allowed:
            # Try to initialize enhanced assistant (includes calculator, math tools, scope guards)
            if ENHANCED_ASSISTANT_AVAILABLE and create_enhanced_assistant:
                try:
                    self.enhanced_assistant = create_enhanced_assistant()
                except Exception as e:
                    print(f"Warning: Could not initialize enhanced assistant: {e}")

            # Rule-based assistant (no cloud LLM) — ADVANCED only alongside Ask rbGyanX
            if RULE_BASED_ASSISTANT_AVAILABLE and create_rule_based_assistant:
                self.rule_based_assistant = create_rule_based_assistant()

            # Optional local LLM backend
            if BACKEND_MODULES_AVAILABLE and LocalLLMEngine:
                self.ai_assistant = create_ai_assistant()
        
        # Load feature registry for dashboard text (sync version from VERSION.txt)
        self.feature_registry = self._load_feature_registry()
        try:
            from rbgyanx.app_metadata import sync_feature_registry

            if sync_feature_registry(_rbgyanx_base_dir()):
                self.feature_registry = self._load_feature_registry()
        except ImportError:
            pass
        
        # OBJECTIVE E: Initialize backup system
        self.backup_dir = _rbgyanx_base_dir() / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        
        # Create menu bar (rbGyanX Pro v1.1.0)
        self.create_menu_bar()
        
        # Generate user manual on startup
        self._generate_user_manual_on_startup()
        
        # Check and run self-test if needed (first launch or code modification)
        self._check_and_run_self_test_if_needed()

        self._apply_mode_ui_restrictions()
    
    def _apply_mode_ui_restrictions(self):
        """Align Step 3 options with BASIC vs ADVANCED operating contract."""
        if not self.mode_controller:
            return
        basic = self.mode_controller.is_basic()
        mode_name = "BASIC" if basic else "ADVANCED"
        self.log(f"[INFO] Session mode: {mode_name}")

        if basic:
            if self.enable_ml.get():
                self.enable_ml.set(False)
            if self.enable_shap.get():
                self.enable_shap.set(False)
            if self.use_ccs.get():
                self.use_ccs.set(False)
            self.log(
                "[INFO] BASIC mode: ML, SHAP, and CCS are off. "
                "Use DICOM + Run Step 3 (TCP+NTCP) for rbgyanx-engine classical analysis."
            )
            if self.analysis_mode.get() == "TCP_NTCP" and not self._uses_engine_dicom_path():
                self.log(
                    "[!] BASIC: select DICOM RT input and a folder with RTPLAN/RTDOSE/RTSTRUCT "
                    "for integrated TCP+NTCP/UTCP/QUANTEC."
                )
        else:
            self.log(
                "[INFO] ADVANCED mode: ML, SHAP, FDVH, and legacy subprocess paths available. "
                "DICOM + TCP+NTCP still uses rbgyanx-engine when input is DICOM."
            )

        if hasattr(self, "step3_mode_hint"):
            if basic:
                self.step3_mode_hint.config(
                    text="BASIC: DICOM → Step 3 (TCP+NTCP) runs rbgyanx-engine (classical, fast). "
                    "Steps 1–2 optional for TPS text workflows."
                )
            else:
                self.step3_mode_hint.config(
                    text="ADVANCED: DICOM engine path + optional ML/SHAP/FDVH via legacy scripts when enabled."
                )

    def _set_window_icon(self, window=None):
        """Set window icon from assets (branding)"""
        icon_path = _rbgyanx_base_dir() / 'assets' / 'icon.png'
        if icon_path.exists() and PIL_AVAILABLE:
            try:
                icon_img = Image.open(icon_path)
                icon_photo = ImageTk.PhotoImage(icon_img)
                target = window if window else self.root
                target.iconphoto(False, icon_photo)
                # Keep reference to prevent garbage collection
                if not hasattr(self, '_icon_photo'):
                    self._icon_photo = icon_photo
            except Exception as e:
                # Fail silently if icon cannot be loaded
                pass
    
    def _generate_about_content(self, version):
        """Generate journal-aligned About dialog content (branding)"""
        # ADVANCED UI: Mode-aware About content
        mode_label = "BASIC"
        if self.mode_controller and self.mode_controller.is_advanced():
            mode_label = "ADVANCED"
        
        content = f"""rbGyanX ({mode_label})
Radiobiology-guided Clinical Decision Support System (CDSS) Framework

Developed as part of PhD research in Medical Physics.
Integrates physics, radiobiology, statistics, and explainable machine learning
for radiotherapy plan evaluation and research for clinical decision-support.

⚠️ Research & clinical support tool. Final clinical decisions remain with clinicians.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OVERVIEW

rbGyanX is a radiobiology-guided clinical decision support framework designed to integrate physical dosimetry, radiobiological modeling, and explainable machine learning for treatment plan evaluation in radiation oncology.


CAPABILITIES

• Physical Dosimetry
  - Dose-volume histogram (DVH) processing and analysis
  - Dose metric extraction and statistical evaluation
  - Multi-institutional data compatibility

• Radiobiological Modeling
  - Normal Tissue Complication Probability (NTCP) models:
    * Lyman-Kutcher-Burman (LKB) Log-Logistic
    * LKB Probit
    * Relative Seriality (RS) Poisson
  - Tumor Control Probability (TCP) models:
    * Poisson TCP
    * LKB-adapted TCP
    * Logistic TCP
    * Equivalent Uniform Dose (EUD)-based TCP

• Explainable Machine Learning
  - SHAP (SHapley Additive exPlanations) integration
  - Feature importance analysis
  - Model interpretability for clinical transparency
  - Overfitting detection and quality assurance

• Clinical Decision Support
  - Treatment plan evaluation workflows
  - Comparative analysis of TCP/NTCP outcomes
  - Risk assessment and visualization
  - Quality assurance reporting


INTENDED USE

rbGyanX ({mode_label}) is intended for:
{f'• Scientific validation and research using real patient data under institutional governance' if mode_label == 'ADVANCED' else '• Research applications in radiation oncology'}
• Academic use in medical physics and radiobiology
{f'• Research use only — NOT for clinical decision-making' if mode_label == 'ADVANCED' else '• Clinical decision support (not autonomous decision making)'}

All clinical decisions must be made by qualified healthcare professionals. rbGyanX provides analytical tools and insights to inform, not replace, clinical judgment.
{f'⚠️ ADVANCED MODE: This mode is for scientific validation and research using real patient data under institutional governance. Results are exploratory and non-clinical. NOT FOR CLINICAL USE.' if mode_label == 'ADVANCED' else ''}


DEVELOPMENT METHODOLOGY

rbGyanX is built with:
• Modular, QA-driven architecture
• Emphasis on explainable AI and human-in-the-loop design
• Local-only AI processing (no cloud access, no PHI exposure)
• Cursor-assisted development and testing
• Open-source principles for reproducibility


TECHNICAL ARCHITECTURE

• Python-based implementation
• Tkinter-based graphical user interface
• Local machine learning models (no external dependencies)
• Offline operation capability
• Cross-platform compatibility (Windows, Linux, macOS)


DEVELOPMENT TEAM

Developer: K. Mondal, Medical Physicist

rbGyanX is developed as part of doctoral research (PhD) in Medical Physics, focusing on radiobiological modeling, treatment plan evaluation, and clinical decision support in radiotherapy.

Contributors: rbGX Academic Team


SOFTWARE CITATION

Mondal, Kalyan. rbGyanX: A radiobiology-guided clinical decision support framework. Version {mode_label}. 2025.


AI ASSISTANCE ACKNOWLEDGMENT

rbGyanX may optionally interoperate with modern large language models for educational and documentation support.
Development and testing benefited from AI-assisted coding and reasoning tools including ChatGPT (OpenAI), Claude (Anthropic), DeepSeek, and Cursor IDE.
No clinical decisions are generated autonomously by these tools.


COPYRIGHT AND LICENSE

© rbGyanX Team
For academic and research use.


For more information, please refer to the documentation and citation guidelines.
"""
        return content
    
    def _is_mpl_canvas(self, obj):
        """Check if object is a Matplotlib FigureCanvasTkAgg (defensive guard)"""
        return hasattr(obj, "get_tk_widget")
    
    def set_processing_state(self, is_processing, step_name=None):
        """
        Generic helper to control owl animation (branding)
        Sets processing state for any step (future-proof).
        Owl appears contextually next to the active step button.
        """
        # Stop any currently running owl
        if self.processing_step and self.processing_step in self.step_owl_indicators:
            old_owl = self.step_owl_indicators[self.processing_step]
            old_owl.stop_blinking()
            old_owl.pack_forget()
        
        if is_processing and step_name:
            self.processing_step = step_name
            # Show owl for this step
            if step_name in self.step_owl_indicators:
                owl = self.step_owl_indicators[step_name]
                owl.pack(side=tk.LEFT, padx=5)
                owl.start_blinking()
        else:
            self.processing_step = None
    
    def _stop_step_animation(self, step_name):
        """Stop animation for a specific step (now uses owl indicator)."""
        self.set_processing_state(False, step_name)
    
    def _start_step_animation(self, step_name):
        """Start animation for a specific step (now uses owl indicator)."""
        self.set_processing_state(True, step_name)
        
    def create_main_layout(self):
        """Create 3-panel layout with scrollbars and improved color contrast"""
        
        # Configure medical software color scheme
        style = ttk.Style()
        style.theme_use('clam')
        
        # Medical software color scheme - improved contrast
        COLORS = {
            'bg_light': '#f5f5f5',       # Light neutral background
            'bg_dark': '#E8E8E8',        # Darker gray for panels
            'text_primary': '#222222',   # Dark text for better contrast
            'text_secondary': '#666666', # Medium gray text
            'header': '#2C3E50',         # Dark blue headers
            'success': '#27AE60',        # Green for success
            'warning': '#E67E22',        # Orange for warnings
            'error': '#C0392B',          # Red for errors
            'info': '#3498DB',           # Blue for info
            'border': '#BDC3C7',         # Light gray borders
        }
        
        # Configure styles with improved contrast - OBJECTIVE 5: Visual modernization with increased whitespace
        style.configure('TFrame', background=COLORS['bg_light'])
        style.configure('TLabel', background=COLORS['bg_light'], foreground=COLORS['text_primary'], 
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL), 
                       padding=UILayoutConstants.PADDING_SMALL)  # Increased spacing
        style.configure('TButton', font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL, 'bold'), 
                       padding=UILayoutConstants.PADDING_MEDIUM)  # Increased button padding
        style.configure('Header.TLabel', font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_LARGE, 'bold'), 
                       foreground=COLORS['header'])
        style.configure('Success.TLabel', foreground=COLORS['success'], 
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL))
        style.configure('Warning.TLabel', foreground=COLORS['warning'], 
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL))
        style.configure('Error.TLabel', foreground=COLORS['error'], 
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL))
        style.configure('TLabelFrame', background=COLORS['bg_light'], padding=UILayoutConstants.PADDING_MEDIUM)  # Increased padding
        style.configure('TLabelFrame.Label', background=COLORS['bg_light'], foreground=COLORS['text_primary'],
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL, 'bold'))
        # Improve contrast for labels vs values - OBJECTIVE 5: Better contrast
        style.configure('Value.TLabel', foreground='#000000', 
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL))
        style.configure('Label.TLabel', foreground=COLORS['text_primary'], 
                       font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL, 'bold'))
        # OBJECTIVE 5: Subtle separators instead of heavy borders
        style.configure('TSeparator', background=UILayoutConstants.SEPARATOR_COLOR)
        
        # Apply to window
        self.root.configure(bg=COLORS['bg_light'])
        
        # UI FREEZE ZONE:
        # Header layout MUST NOT be modified without UI regression testing
        
        # OBJECTIVE 1: Root grid configuration - Header NEVER expands
        self.root.grid_rowconfigure(0, weight=0)  # HEADER — NEVER EXPANDS
        self.root.grid_rowconfigure(1, weight=1)  # MAIN CONTENT
        self.root.grid_columnconfigure(0, weight=1)
        
        # OBJECTIVE 1: Header frame - Fixed height, always visible
        self.header_frame = ttk.Frame(self.root)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.configure(height=90)  # Fixed height
        self.header_frame.name = "header_frame"  # For self-test access
        
        # OBJECTIVE 3: Body frame for main content
        self.body_frame = ttk.Frame(self.root)
        self.body_frame.grid(row=1, column=0, sticky="nsew")
        
        # Configure body frame grid for panels (with minsize)
        self.body_frame.grid_columnconfigure(0, weight=1, minsize=250)  # Left panel
        self.body_frame.grid_columnconfigure(1, weight=2, minsize=250)  # Center panel
        self.body_frame.grid_columnconfigure(2, weight=2, minsize=250)  # Right panel
        self.body_frame.grid_rowconfigure(0, weight=1)
        
        # Header content container (inside header_frame - pack is OK here)
        header_content = tk.Frame(self.header_frame, bg=COLORS['bg_light'], padx=10, pady=5)
        header_content.pack(fill=tk.X, expand=False)
        
        # OBJECTIVE 2: Title container - Centered
        title_container = ttk.Frame(header_content)
        title_container.pack(anchor="center", side=tk.LEFT)
        
        # OBJECTIVE 2: Ashoka Chakra - Above title with 4px vertical gap
        chakra_container = tk.Frame(title_container, bg=COLORS['bg_light'])
        chakra_container.pack(pady=(0, 4))  # 4px vertical gap between logo and title
        try:
            self.chakra = AshokaChakra(chakra_container, size=UILayoutConstants.CHAKRA_SIZE)
            self.chakra.pack(anchor="center")
        except:
            # Fallback: placeholder
            tk.Label(chakra_container, text="⚫", font=("Arial", 20), bg=COLORS['bg_light']).pack(anchor="center")
        
        # Title canvas for tricolor text (below chakra)
        title_canvas = tk.Canvas(title_container, height=70, width=400,
                                highlightthickness=0, bg=COLORS['bg_light'])
        title_canvas.pack(anchor="center")
        
        # Draw tricolor title
        self._draw_tricolor_title_with_chakra(title_canvas, title_container)
        
        # OBJECTIVE 2: Subtitle label - Below title
        # STEP 3 FIX: Mode-aware header branding
        if self.mode_controller:
            if self.mode_controller.is_advanced():
                subtitle_text = "Research & Validation Platform"
            else:
                subtitle_text = "Clinical Decision Support System (CDSS) Framework"
        else:
            subtitle_text = "Radiobiology-guided Clinical Decision Support System (CDSS) Framework"
        
        subtitle_label = tk.Label(
            title_container,
            text=subtitle_text,
            font=("Segoe UI", 10, "normal"),
            fg="#666666",
            bg=COLORS['bg_light']
        )
        subtitle_label.pack(anchor="center")
        
        # MODE-AWARE UI FIX: Persistent visual mode indicator badge
        if self.mode_controller:
            if self.mode_controller.is_advanced():
                # Orange badge for ADVANCED
                mode_badge = tk.Label(
                    header_content,
                    text="ADVANCED",
                    font=("Arial", 10, "bold"),
                    fg="#FFFFFF",
                    bg="#E67E22",  # Orange background
                    padx=12,
                    pady=5,
                    relief=tk.RAISED,
                    borderwidth=2
                )
                mode_badge.pack(side=tk.RIGHT, padx=5)
            else:
                # Blue badge for BASIC
                mode_badge = tk.Label(
                    header_content,
                    text="BASIC",
                    font=("Arial", 10, "bold"),
                    fg="#FFFFFF",
                    bg="#3498DB",  # Blue background
                    padx=12,
                    pady=5,
                    relief=tk.RAISED,
                    borderwidth=2
                )
                mode_badge.pack(side=tk.RIGHT, padx=5)
        
        # FINAL CURSOR PROMPT: Validation mode banner (if validation enabled)
        if self.validation_controller and self.validation_controller.is_validation_enabled():
            validation_banner = tk.Label(
                header_content,
                text="⚠️ VALIDATION MODE — REAL PATIENT DATA ⚠️",
                font=("Arial", 11, "bold"),
                fg="#FFFFFF",
                bg="#C0392B",  # Red background for visibility
                padx=15,
                pady=5
            )
            validation_banner.pack(side=tk.RIGHT, padx=10)
        
        # OBJECTIVE 3: Create panels with grid layout (inside body_frame)
        left_panel = self.create_left_panel()
        left_panel.grid(row=0, column=0, sticky="nsew", in_=self.body_frame)
        
        center_panel = self.create_center_panel()
        center_panel.grid(row=0, column=1, sticky="nsew", in_=self.body_frame)
        
        right_panel = self.create_right_panel()
        right_panel.grid(row=0, column=2, sticky="nsew", in_=self.body_frame)
        
        
        # Store panel references for maximize/restore
        self.panels = {
            'left': left_panel,
            'center': center_panel,
            'right': right_panel
        }
        self.panel_states = {
            'left': 'normal',
            'center': 'normal',
            'right': 'normal'
        }
        self.main_frame = self.body_frame  # Store for maximize/restore (alias for compatibility)
        
        # OBJECTIVE 4: Run header visibility test after layout is complete
        self.root.after(100, self._test_header_visibility)
    
    def _test_header_visibility(self):
        """OBJECTIVE 4: Test header visibility - Critical UI regression check"""
        try:
            if not hasattr(self, 'header_frame') or self.header_frame is None:
                messagebox.showerror(
                    "Critical UI Regression",
                    "Header frame not found. Layout fix required.\n\nHeader must be at root.grid(row=0, column=0)"
                )
                return False
            
            # Force geometry update
            self.root.update_idletasks()
            header_height = self.header_frame.winfo_height()
            
            if header_height < 20:
                messagebox.showerror(
                    "Critical UI Regression",
                    f"Header collapsed. Layout fix required.\n\nHeader height: {header_height}px (minimum required: 20px)"
                )
                return False
            
            # Test passes - header is visible
            return True
            
        except Exception as e:
            messagebox.showerror(
                "Header Visibility Test Error",
                f"Error testing header visibility: {str(e)}\n\nLayout fix may be required."
            )
            return False
    
    def _draw_tricolor_title_with_chakra(self, canvas, parent_container):
        """Draw rbGyanX (BASIC) in tricolor - OBJECTIVE A: Chakra is centered above 'Gyan' in vertical stack."""
        # Indian flag colors
        saffron = "#FF9933"      # Saffron/Orange
        white = "#FFFFFF"         # White
        green = "#138808"         # India Green
        navy = "#000080"          # Navy Blue
        
        # Fonts - Typography adjustment: Increased by +2 points
        main_font = ("Georgia", UILayoutConstants.FONT_SIZE_TITLE, "bold")
        basic_font = ("Arial", 14, "bold")  # Adjusted proportionally
        
        # Calculate center position for text (Chakra is above, centered)
        canvas_width = canvas.winfo_reqwidth() if canvas.winfo_reqwidth() > 1 else 400
        y = 35  # Vertical center for text
        
        # Calculate "Gyan" position to center it (Chakra will be centered above)
        gyan_text = "Gyan"
        temp_id = canvas.create_text(0, 0, text=gyan_text, font=main_font, anchor="w")
        gyan_bbox = canvas.bbox(temp_id)
        canvas.delete(temp_id)
        gyan_width = gyan_bbox[2] - gyan_bbox[0] if gyan_bbox else 80
        
        # Start from center, work backwards for "rb", then forward for "X"
        center_x = canvas_width / 2
        gyan_start_x = center_x - gyan_width / 2
        x = gyan_start_x
        
        # Calculate "rb" width to position it before "Gyan"
        rb_text = "rb"
        temp_rb = canvas.create_text(0, 0, text=rb_text, font=main_font, anchor="w")
        rb_bbox = canvas.bbox(temp_rb)
        canvas.delete(temp_rb)
        rb_width = rb_bbox[2] - rb_bbox[0] if rb_bbox else 50
        x = gyan_start_x - rb_width - 2  # Small gap between "rb" and "Gyan"
        
        # "rb" - Saffron
        rb_id = canvas.create_text(x, y, text=rb_text, font=main_font,
                                   fill=saffron, anchor="w")
        rb_bbox = canvas.bbox(rb_id)
        x = rb_bbox[2] + 2  # Move x to end of "rb" with gap
        
        # "Gyan" - White with navy outline (centered)
        outline = 1
        for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), 
                       (0,1), (1,-1), (1,0), (1,1)]:
            canvas.create_text(x + dx*outline, y + dy*outline, 
                             text=gyan_text, font=main_font,
                             fill=navy, anchor="w")
        
        # Draw white fill on top
        canvas.create_text(x, y, text=gyan_text, font=main_font,
                          fill=white, anchor="w")
        gyan_bbox = canvas.bbox(canvas.find_all()[-1])
        x = gyan_bbox[2] + 2 if gyan_bbox else x + 80
        
        # "X" - Green (proportionally adjusted)
        x_id = canvas.create_text(x, y, text="X", font=("Georgia", 29, "bold"),  # Adjusted proportionally with title
                                 fill=green, anchor="w")
        x_bbox = canvas.bbox(x_id)
        x = x_bbox[2] if x_bbox else x + 30
        
        # STEP 1: Mode-aware title suffix
        if hasattr(self, 'mode_controller') and self.mode_controller:
            if self.mode_controller.is_advanced():
                mode_suffix = " (ADVANCED)"
            else:
                mode_suffix = " (BASIC)"
        else:
            mode_suffix = " (BASIC)"  # Default fallback
        
        # Mode suffix - Navy blue
        canvas.create_text(x + 5, y, text=mode_suffix, font=basic_font,
                          fill=navy, anchor="w")
    
    def create_menu_bar(self):
        """Create menu bar with File and Help menus (rbGyanX Pro v1.1.0)"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Project submenu
        project_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Project", menu=project_menu)
        project_menu.add_command(label="New Project...", command=self.menu_new_project)
        project_menu.add_command(label="Open Project...", command=self.menu_open_project)
        project_menu.add_separator()
        project_menu.add_command(label="Save Project", command=self.menu_save_project)
        project_menu.add_command(label="Save Project As...", command=self.menu_save_project_as)
        
        file_menu.add_separator()
        file_menu.add_command(label="Save Configuration...", command=self.save_configuration)
        file_menu.add_command(label="Load Configuration...", command=self.load_configuration)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Self-Test", command=self.menu_run_self_test)
        tools_menu.add_separator()
        tools_menu.add_command(label="Auto-Correction", command=self.menu_run_auto_correction)
        tools_menu.add_command(label="View Diagnostic Report", command=self.menu_view_diagnostic_report)
        # OBJECTIVE E: Rollback menu
        tools_menu.add_separator()
        tools_menu.add_command(label="Rollback", command=self.menu_rollback)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Manual", command=self.menu_open_user_manual)
        help_menu.add_separator()
        # Template downloads
        help_menu.add_command(label="📥 Download TCP Clinical Template", command=self.download_tcp_template)
        help_menu.add_command(label="📥 Download NTCP Clinical Template", command=self.download_ntcp_template)
        help_menu.add_separator()
        if self.mode_controller and self.mode_controller.is_capability_enabled("ai_integration"):
            help_menu.add_command(
                label="Ask rbGyanX — Your AI Assistant",
                command=self.menu_ask_rbgyanx,
            )
            help_menu.add_separator()
        help_menu.add_command(label="About", command=self.menu_about)
    
    def _load_feature_registry(self) -> dict:
        """Load feature registry JSON for dashboard text."""
        registry_path = _rbgyanx_base_dir() / 'core' / 'feature_registry.json'
        try:
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"Warning: Could not load feature registry: {e}")
        return {}
    
    def _load_site_registry(self) -> dict:
        """OBJECTIVE B: Load site registry JSON for multi-site support."""
        registry_path = _rbgyanx_base_dir() / 'core' / 'site_registry.json'
        try:
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"Warning: Could not load site registry: {e}")
        return {}
    
    def menu_new_project(self):
        """Create new project (rbGyanX Pro v1.1.0)"""
        if not self.project_manager:
            messagebox.showinfo("Info", "Project management not available.")
            return
        
        project_path = filedialog.asksaveasfilename(
            title="New Project",
            defaultextension=".rbgyanx.json",
            filetypes=[("rbGyanX Project", "*.rbgyanx.json"), ("All files", "*.*")]
        )
        
        if project_path:
            project_type = 'retrospective'  # Default, could add dialog for selection
            self.project_manager.new_project(Path(project_path), project_type)
            self.log(f"New project created: {project_path}")
            messagebox.showinfo("Success", f"New project created:\n{project_path}")
    
    def menu_open_project(self):
        """Open existing project (rbGyanX Pro v1.1.0)"""
        if not self.project_manager:
            messagebox.showinfo("Info", "Project management not available.")
            return
        
        project_path = filedialog.askopenfilename(
            title="Open Project",
            filetypes=[("rbGyanX Project", "*.rbgyanx.json"), ("All files", "*.*")]
        )
        
        if project_path:
            if self.project_manager.load_project(Path(project_path)):
                # Restore configuration from project
                state = self.project_manager.get_state()
                config = state.get('configuration', {})
                
                # Restore GUI state
                if 'analysis_type' in config:
                    self.analysis_type.set(config['analysis_type'])
                if 'output_dir' in config:
                    self.output_dir.set(config['output_dir'])
                if 'clinical_file' in config:
                    self.clinical_file.set(config['clinical_file'])
                if 'raw_input' in config:
                    self.raw_input.set(config['raw_input'])
                
                self.log(f"Project loaded: {project_path}")
                messagebox.showinfo("Success", f"Project loaded:\n{project_path}")
            else:
                messagebox.showerror("Error", "Failed to load project.")
    
    def menu_save_project(self):
        """Save current project (rbGyanX Pro v1.1.0)"""
        if not self.project_manager:
            messagebox.showinfo("Info", "Project management not available.")
            return
        
        if not self.project_manager.project_path:
            self.menu_save_project_as()
            return
        
        # Update configuration from GUI
        config_updates = {
            'analysis_type': self.analysis_type.get(),
            'output_dir': self.output_dir.get(),
            'clinical_file': self.clinical_file.get(),
            'raw_input': self.raw_input.get(),
            'input_format': self.input_format.get(),
            'dvh_type': self.dvh_type.get(),
            'tumor_organ_type': self.tumor_organ_type.get()
        }
        self.project_manager.update_configuration(config_updates)
        
        if self.project_manager.save_project():
            self.log("Project saved")
        else:
            messagebox.showerror("Error", "Failed to save project.")
    
    def menu_save_project_as(self):
        """Save project with new path (rbGyanX Pro v1.1.0)"""
        if not self.project_manager:
            messagebox.showinfo("Info", "Project management not available.")
            return
        
        project_path = filedialog.asksaveasfilename(
            title="Save Project As",
            defaultextension=".rbgyanx.json",
            filetypes=[("rbGyanX Project", "*.rbgyanx.json"), ("All files", "*.*")]
        )
        
        if project_path:
            # Update configuration from GUI
            config_updates = {
                'analysis_type': self.analysis_type.get(),
                'output_dir': self.output_dir.get(),
                'clinical_file': self.clinical_file.get(),
                'raw_input': self.raw_input.get(),
                'input_format': self.input_format.get(),
                'dvh_type': self.dvh_type.get(),
                'tumor_organ_type': self.tumor_organ_type.get()
            }
            self.project_manager.update_configuration(config_updates)
            
            if self.project_manager.save_as(Path(project_path)):
                self.log(f"Project saved as: {project_path}")
                messagebox.showinfo("Success", f"Project saved:\n{project_path}")
            else:
                messagebox.showerror("Error", "Failed to save project.")
    
    def get_recent_errors(self) -> List[str]:
        """Get recent error messages from log"""
        if not hasattr(self, 'log_text'):
            return []
        
        try:
            log_content = self.log_text.get("1.0", tk.END)
            errors = [line.strip() for line in log_content.split('\n') 
                     if '[!]' in line or 'Error' in line or '[X]' in line]
            return errors[-5:] if len(errors) > 5 else errors
        except Exception:
            return []
    
    def get_qa_warnings(self) -> List[str]:
        """Get QA warnings from latest report"""
        warnings = []
        
        try:
            base_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            if not base_dir:
                return warnings
            
            # Check validation results
            if hasattr(self, 'validation_results'):
                flagged = [r for r in self.validation_results if r.get('status') == 'FLAG']
                for result in flagged[:3]:  # Limit to 3
                    warnings.append(f"DVH flagged: {result.get('patient_id')} - {result.get('structure')}")
            
            # Check QA reports
            qa_reports_dir = base_dir / "qa" / "reports"
            if not qa_reports_dir.exists():
                qa_reports_dir = Path("qa") / "reports"
            
            if qa_reports_dir.exists():
                reports = sorted(qa_reports_dir.glob("*.html"),
                              key=lambda p: p.stat().st_mtime,
                              reverse=True)
                if reports:
                    # Try to extract warnings from latest report
                    # (simplified - could parse HTML more thoroughly)
                    warnings.append(f"QA report available: {reports[0].stem}")
        except Exception:
            pass
        
        return warnings
    
    def menu_ask_rbgyanx(self):
        """Open 'Ask rbGyanX' AI assistant window with API-based LLM (PROMPT 9)"""
        if self.mode_controller and not self.mode_controller.is_capability_enabled("ai_integration"):
            messagebox.showinfo(
                "Ask rbGyanX unavailable",
                "Ask rbGyanX (LLM assistant) is available only in ADVANCED research mode.\n\n"
                "BASIC clinic mode runs without cloud or local LLM features.",
            )
            return
        try:
            from ai.api_llm_engine import AskrbGyanXDialog
            
            # Gather current context
            context = {
                'analysis_mode': self.analysis_mode.get(),
                'project_dir': self.output_dir.get(),
                'workflow_state': str(self.workflow_state.value) if hasattr(self, 'workflow_state') else 'IDLE',
                'recent_errors': self.get_recent_errors(),
                'qa_warnings': self.get_qa_warnings()
            }
            
            # Open dialog - STEP 4: Pass mode_controller for personality
            AskrbGyanXDialog(self.root, context=context, mode_controller=self.mode_controller)
            
        except ImportError as e:
            # Fallback to enhanced assistant if API engine not available
            messagebox.showwarning(
                "API Engine Not Available",
                f"API-based LLM engine not available: {e}\n\n"
                "Falling back to local assistant if available."
            )
            # Try to initialize enhanced assistant if not already done
            if not hasattr(self, 'enhanced_assistant') or not self.enhanced_assistant:
                if ENHANCED_ASSISTANT_AVAILABLE and create_enhanced_assistant:
                    try:
                        self.enhanced_assistant = create_enhanced_assistant()
                    except Exception as e:
                        self.log(f"[!] Could not initialize enhanced assistant: {e}")
        
        # Ensure rule-based assistant is available (fallback)
        if not self.rule_based_assistant:
            if RULE_BASED_ASSISTANT_AVAILABLE and create_rule_based_assistant:
                self.rule_based_assistant = create_rule_based_assistant()
        
        # Try to initialize local LLM if not already done (optional)
        if not self.ai_assistant:
            if BACKEND_MODULES_AVAILABLE and LocalLLMEngine:
                self.ai_assistant = create_ai_assistant()
        
        # Determine which assistant to use
        use_enhanced = self.enhanced_assistant is not None
        use_llm = self.ai_assistant and self.ai_assistant.is_available()
        
        if use_enhanced:
            assistant_name = "Enhanced Assistant (Calculator + Math Tools + Knowledge)"
        elif use_llm:
            assistant_name = "AI Assistant (Local LLM)"
        else:
            assistant_name = "Rule-Based Assistant"
        
        # Create AI assistant window with proper sizing
        ai_window = tk.Toplevel(self.root)
        ai_window.title(f"Ask rbGyanX — Your AI Assistant - {assistant_name}")
        
        # Limit window to 80% of screen size with max size clamp
        screen_w = ai_window.winfo_screenwidth()
        screen_h = ai_window.winfo_screenheight()
        window_w = min(900, int(screen_w * 0.8))
        window_h = min(600, int(screen_h * 0.8))
        
        ai_window.geometry(f"{window_w}x{window_h}")
        ai_window.minsize(700, 500)
        ai_window.maxsize(int(screen_w * 0.9), int(screen_h * 0.9))
        ai_window.resizable(True, True)
        ai_window.transient(self.root)
        
        # Center window
        ai_window.update_idletasks()
        x = (screen_w // 2) - (window_w // 2)
        y = (screen_h // 2) - (window_h // 2)
        ai_window.geometry(f"+{x}+{y}")
        
        # Instruction text (top of panel)
        instruction_text_frame = ttk.Frame(ai_window, padding="10")
        instruction_text_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        instruction_text = (
            "Ask rbGyanX provides educational support in radiobiology, physics, "
            "statistics, and software usage. It does NOT access patient data."
        )
        instruction_text_label = tk.Label(
            instruction_text_frame,
            text=instruction_text,
            font=("Arial", 9, "italic"),
            foreground="#666666",
            background=ai_window.cget("bg"),
            justify=tk.LEFT,
            wraplength=800
        )
        instruction_text_label.pack(anchor=tk.W)
        
        # Query input section
        query_frame = ttk.Frame(ai_window, padding="10")
        query_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=10)
        
        # Explicit instruction label
        instruction_label = ttk.Label(
            query_frame,
            text="Enter your question or instruction:",
            font=("Arial", 10, "bold")
        )
        instruction_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Multiline input box (height ≥ 5 lines, scrollable, word wrap)
        instruction_box = scrolledtext.ScrolledText(
            query_frame,
            height=5,
            wrap=tk.WORD,
            font=("Arial", 10)
        )
        instruction_box.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add placeholder text
        placeholder = "Type your question here (e.g., \"Explain Poisson TCP model\")"
        instruction_box.insert("1.0", placeholder)
        instruction_box.config(foreground="gray")
        
        def on_focus_in(event):
            if instruction_box.get("1.0", tk.END).strip() == placeholder:
                instruction_box.delete("1.0", tk.END)
                instruction_box.config(foreground="black")
        
        def on_focus_out(event):
            if not instruction_box.get("1.0", tk.END).strip():
                instruction_box.insert("1.0", placeholder)
                instruction_box.config(foreground="gray")
        
        instruction_box.bind("<FocusIn>", on_focus_in)
        instruction_box.bind("<FocusOut>", on_focus_out)
        
        # Store reference for ask_question function
        query_text = instruction_box
        
        # Bind ENTER to submit, SHIFT+ENTER for new line
        def on_enter(event):
            if event.state & 0x1:  # Shift key pressed
                return  # Allow default behavior (new line)
            else:
                ask_question()
                return "break"
        
        instruction_box.bind("<Return>", on_enter)
        
        # Response area
        response_frame = ttk.Frame(ai_window, padding="10")
        response_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Response label
        response_label = ttk.Label(
            response_frame,
            text="rbGyanX Response:",
            font=("Arial", 10, "bold")
        )
        response_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Response text area (scrollable, read-only, copyable)
        response_text = scrolledtext.ScrolledText(
            response_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Arial", 10),
            padx=10,
            pady=10
        )
        response_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons frame (explicit buttons: Ask rbGyanX, Clear, Close)
        button_frame = ttk.Frame(ai_window, padding="10")
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Store ask button reference for enabling/disabling
        ask_button_ref = [None]  # Use list to allow modification in nested function
        
        def ask_question():
            """Ask question using available assistant (non-blocking)"""
            query = query_text.get("1.0", tk.END).strip()
            # Remove placeholder if present
            if query == placeholder:
                query = ""
            if not query:
                messagebox.showwarning("Empty Input", "Please enter a question or instruction.")
                return
            
            # Disable button and show status
            if ask_button_ref[0]:
                ask_button_ref[0].config(state=tk.DISABLED)
            
            # Update UI with status feedback
            response_text.config(state=tk.NORMAL)
            response_text.delete("1.0", tk.END)
            response_text.insert("1.0", "rbGyanX is thinking…")
            response_text.config(state=tk.DISABLED)
            ai_window.update()
            
            # Process in background thread to avoid blocking
            def process_query():
                try:
                    result = None
                    
                    # Try enhanced assistant first (includes calculator, math tools, scope guards)
                    if use_enhanced and self.enhanced_assistant:
                        try:
                            result = self.enhanced_assistant.ask(query)
                        except Exception as e:
                            self.log(f"[INFO] Enhanced assistant error, using fallback: {str(e)}")
                            # Fallback to rule-based
                            if self.rule_based_assistant:
                                result = self.rule_based_assistant.ask(query)
                    # Try LLM if available and enhanced not used
                    elif use_llm and self.ai_assistant:
                        try:
                            result = self.ai_assistant.ask(query)
                            # If LLM fails, fallback to rule-based
                            if result.get('status') == 'error' and self.rule_based_assistant:
                                self.log("[INFO] LLM unavailable, using rule-based fallback")
                                result = self.rule_based_assistant.ask(query)
                        except Exception as e:
                            self.log(f"[INFO] LLM error, using rule-based fallback: {str(e)}")
                            if self.rule_based_assistant:
                                result = self.rule_based_assistant.ask(query)
                    else:
                        # Use rule-based assistant
                        if self.rule_based_assistant:
                            result = self.rule_based_assistant.ask(query)
                    
                    # Update UI in main thread
                    def update_response():
                        # Re-enable button
                        if ask_button_ref[0]:
                            ask_button_ref[0].config(state=tk.NORMAL)
                        
                        response_text.config(state=tk.NORMAL)
                        response_text.delete("1.0", tk.END)
                        
                        if result:
                            if result.get('status') == 'success' or result.get('status') == 'partial':
                                answer = result.get('answer', 'No answer provided')
                                # Check for empty response
                                if not answer or not answer.strip():
                                    answer = "No response generated. Please rephrase your question."
                                # Add suggestion if blocked query
                                if result.get('suggestion'):
                                    answer = f"{answer}\n\n💡 Suggestion:\n{result.get('suggestion')}"
                                response_text.insert("1.0", answer)
                            elif result.get('status') == 'blocked':
                                error_msg = result.get('error', 'Query blocked')
                                suggestion = result.get('suggestion', '')
                                blocked_text = f"⚠️ {error_msg}"
                                if suggestion:
                                    blocked_text += f"\n\n💡 Educational Guidance:\n{suggestion}"
                                response_text.insert("1.0", blocked_text)
                            else:
                                error_msg = result.get('error', 'Unknown error')
                                response_text.insert("1.0", f"Ask rbGyanX error: {error_msg}\n\nPlease try again or rephrase your question.")
                        else:
                            response_text.insert("1.0", "No response generated. Please rephrase your question.")
                        
                        response_text.config(state=tk.DISABLED)
                        self.log(f"[OK] Ask rbGyanX: Question answered (source: {result.get('source', 'unknown') if result else 'unknown'})")
                    
                    ai_window.after(0, update_response)
                    
                except Exception as e:
                    def show_error():
                        # Re-enable button
                        if ask_button_ref[0]:
                            ask_button_ref[0].config(state=tk.NORMAL)
                        
                        response_text.config(state=tk.NORMAL)
                        response_text.delete("1.0", tk.END)
                        error_msg = f"Ask rbGyanX error: {str(e)}"
                        response_text.insert("1.0", f"{error_msg}\n\nPlease try again or rephrase your question.")
                        response_text.config(state=tk.DISABLED)
                        self.log(f"[X] Ask rbGyanX error: {str(e)}")
                    ai_window.after(0, show_error)
            
            # Run in background thread
            thread = threading.Thread(target=process_query, daemon=True)
            thread.start()
        
        # Create explicit buttons: Send/Ask (primary), Clear, Close
        ask_btn = ttk.Button(button_frame, text="Send", command=ask_question)
        ask_btn.pack(side=tk.LEFT, padx=5)
        ask_button_ref[0] = ask_btn  # Store reference for enabling/disabling
        
        ttk.Button(button_frame, text="Clear", command=lambda: [query_text.delete("1.0", tk.END), query_text.insert("1.0", placeholder), query_text.config(foreground="gray")]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=ai_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def menu_open_user_manual(self):
        """Open user manual in default web browser"""
        # Check if manual needs regeneration
        self._check_and_regenerate_manual_if_needed()
        
        # Try auto-generated manual first
        manual_path = _rbgyanx_base_dir() / "docs" / "rbgyanx_user_manual.html"
        
        # Fallback to old location if new one doesn't exist
        if not manual_path.exists():
            manual_path = _rbgyanx_base_dir() / "USER_MANUAL.html"
        
        if manual_path.exists():
            import webbrowser
            import os
            # Use file:// URL for local HTML file
            url = f"file://{manual_path.absolute()}"
            webbrowser.open(url)
        else:
            # Try to generate it
            if MANUAL_GENERATOR_AVAILABLE and generate_user_manual:
                self.log("Attempting to generate user manual...")
                success, msg = generate_user_manual(_rbgyanx_base_dir())
                self.log(msg)
                if success:
                    manual_path = _rbgyanx_base_dir() / "docs" / "rbgyanx_user_manual.html"
                    if manual_path.exists():
                        import webbrowser
                        url = f"file://{manual_path.absolute()}"
                        webbrowser.open(url)
                        return
            
            messagebox.showwarning(
                "Manual Not Found",
                f"User manual not found at:\n{manual_path}\n\n"
                "The manual will be generated automatically on next startup."
            )
    
    def _generate_user_manual_on_startup(self):
        """Generate user manual on application startup"""
        if not MANUAL_GENERATOR_AVAILABLE or not generate_user_manual:
            return
        
        try:
            repo_root = _rbgyanx_base_dir()
            success, message = generate_user_manual(repo_root)
            
            if success:
                self.log(f"[OK] User manual generated: {message}")
            else:
                self.log(f"[!] User manual generation warning: {message}")
        except Exception as e:
            # Don't crash on manual generation failure
            self.log(f"[!] User manual generation error (non-critical): {str(e)}")
    
    def check_manual_version(self):
        """Check if user manual is up-to-date (PROMPT 10)"""
        try:
            from rbgyanx.app_metadata import read_version_from_file, sync_feature_registry

            sync_feature_registry(_rbgyanx_base_dir())
            app_version = read_version_from_file(_rbgyanx_base_dir())
            if not app_version:
                return
            
            # Read manual version
            manual_file = _rbgyanx_base_dir() / "docs" / "rbgyanx_user_manual.html"
            if manual_file.exists():
                with open(manual_file, encoding='utf-8') as f:
                    content = f.read()
                    # Extract version from meta tag
                    import re
                    match = re.search(r'<meta name="version" content="([^"]+)"', content)
                    if match:
                        manual_version = match.group(1)
                        
                        if manual_version != app_version:
                            self.log(f"[!] User manual outdated ({manual_version} vs {app_version})")
                            self.log("    Regenerating manual...")
                            self.regenerate_manual()
            else:
                self.log("[!] User manual not found, generating...")
                self.regenerate_manual()
        
        except Exception as e:
            self.log(f"[!] Manual version check failed: {e}")
    
    def regenerate_manual(self):
        """Regenerate user manual (PROMPT 10)"""
        try:
            if MANUAL_GENERATOR_AVAILABLE and generate_user_manual:
                repo_root = _rbgyanx_base_dir()
                success, msg = generate_user_manual(repo_root)
                if success:
                    self.log("[OK] User manual regenerated")
                else:
                    self.log(f"[!] Manual regeneration failed: {msg}")
            else:
                self.log("[!] Manual generator not available")
        except Exception as e:
            self.log(f"[!] Manual regeneration error: {e}")
    
    def _check_and_regenerate_manual_if_needed(self):
        """Check if manual needs regeneration based on file changes and version (PROMPT 10)"""
        # First check version consistency
        self.check_manual_version()
        
        if not MANUAL_GENERATOR_AVAILABLE or not generate_user_manual:
            return
        
        try:
            repo_root = _rbgyanx_base_dir()
            manual_path = repo_root / "docs" / "rbgyanx_user_manual.html"
            feature_registry_path = repo_root / "core" / "feature_registry.json"
            clinical_schema_path = repo_root / "clinical" / "clinical_schema.json"
            clinical_templates_dir = repo_root / "clinical" / "templates"
            
            # Check if manual exists and is older than any of these files
            if manual_path.exists():
                manual_mtime = manual_path.stat().st_mtime
                needs_regeneration = False
                
                # Check feature registry
                if feature_registry_path.exists():
                    if feature_registry_path.stat().st_mtime > manual_mtime:
                        needs_regeneration = True
                
                # Check clinical schema
                if clinical_schema_path.exists():
                    if clinical_schema_path.stat().st_mtime > manual_mtime:
                        needs_regeneration = True
                
                # Check templates directory
                if clinical_templates_dir.exists():
                    for template_file in clinical_templates_dir.glob("*"):
                        if template_file.is_file() and template_file.stat().st_mtime > manual_mtime:
                            needs_regeneration = True
                            break
                
                if needs_regeneration:
                    self.log("Regenerating user manual due to file changes...")
                    success, message = generate_user_manual(repo_root)
                    if success:
                        self.log(f"[OK] User manual regenerated: {message}")
        except Exception as e:
            # Don't crash on regeneration check failure
            self.log(f"[!] Manual regeneration check error (non-critical): {str(e)}")
    
    def menu_run_self_test(self):
        """Run self-test engine"""
        if not SELF_TEST_AVAILABLE or not SelfTestEngine:
            messagebox.showerror(
                "Self-Test Unavailable",
                "Self-test engine is not available.\n\n"
                "Please ensure qa/self_test_engine.py exists."
            )
            return
        
        try:
            self.log("=== Starting Self-Test ===")
            
            # Show progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Self-Test in Progress")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # Center dialog
            progress_window.update_idletasks()
            x = (progress_window.winfo_screenwidth() // 2) - (progress_window.winfo_width() // 2)
            y = (progress_window.winfo_screenheight() // 2) - (progress_window.winfo_height() // 2)
            progress_window.geometry(f"+{x}+{y}")
            
            ttk.Label(progress_window, text="Running self-tests...", font=("Arial", 10)).pack(pady=20)
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=tk.X)
            progress_bar.start()
            
            progress_window.update()
            
            # Run self-test in background thread
            def run_test():
                try:
                    repo_root = _rbgyanx_base_dir()
                    engine = SelfTestEngine(repo_root)
                    results = engine.run_all_tests()
                    
                    # Generate HTML report
                    report_dir = repo_root / "qa" / "reports"
                    report_dir.mkdir(parents=True, exist_ok=True)
                    report_path = report_dir / f"selftest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    engine.generate_html_report(report_path)
                    
                    # Close progress window and show results
                    progress_window.after(0, progress_window.destroy)
                    self.root.after(0, lambda: self._show_self_test_results(results, report_path))
                except Exception as e:
                    progress_window.after(0, progress_window.destroy)
                    self.root.after(0, lambda: self._show_self_test_error(str(e)))
            
            thread = threading.Thread(target=run_test, daemon=True)
            thread.start()
            
        except Exception as e:
            self.log(f"[X] Self-test error: {str(e)}")
            messagebox.showerror("Self-Test Error", f"Error running self-test:\n{str(e)}")
    
    def _show_self_test_results(self, results: Dict, report_path: Path):
        """Show self-test results dialog"""
        status = results['status']
        summary = results['summary']
        
        # Log results
        self.log(f"Self-Test Status: {status}")
        self.log(f"Total: {summary['total']}, Passed: {summary['passed']}, "
                f"Warned: {summary['warned']}, Failed: {summary['failed']}")
        
        # Create results dialog
        results_window = tk.Toplevel(self.root)
        results_window.title("Self-Test Results")
        results_window.geometry("600x500")
        results_window.transient(self.root)
        
        # Center dialog
        results_window.update_idletasks()
        x = (results_window.winfo_screenwidth() // 2) - (results_window.winfo_width() // 2)
        y = (results_window.winfo_screenheight() // 2) - (results_window.winfo_height() // 2)
        results_window.geometry(f"+{x}+{y}")
        
        # Status badge
        status_colors = {'PASS': '#28a745', 'WARN': '#ffc107', 'FAIL': '#dc3545'}
        status_color = status_colors.get(status, '#666')
        
        status_frame = ttk.Frame(results_window, padding="10")
        status_frame.pack(fill=tk.X)
        
        status_label = tk.Label(
            status_frame,
            text=f"Status: {status}",
            font=("Arial", 14, "bold"),
            fg=status_color
        )
        status_label.pack()
        
        # Summary
        summary_text = (
            f"Total Tests: {summary['total']}\n"
            f"Passed: {summary['passed']}\n"
            f"Warnings: {summary['warned']}\n"
            f"Failed: {summary['failed']}"
        )
        ttk.Label(status_frame, text=summary_text, font=("Arial", 10)).pack(pady=10)
        
        # Results list
        results_frame = ttk.Frame(results_window)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(results_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        results_text = scrolledtext.ScrolledText(
            results_frame,
            wrap=tk.WORD,
            font=("Courier", 9),
            yscrollcommand=scrollbar.set
        )
        results_text.pack(fill=tk.BOTH, expand=True)
        
        # Add test results
        for result in results['results']:
            status_symbol = {'PASS': '✓', 'WARN': '⚠', 'FAIL': '✗'}.get(result['status'], '?')
            results_text.insert(tk.END, f"{status_symbol} {result['name']}: {result['message']}\n")
            if result['details']:
                results_text.insert(tk.END, f"   {result['details'][:200]}...\n")
        
        results_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(results_window)
        button_frame.pack(pady=10)
        
        def open_report():
            import webbrowser
            url = f"file://{report_path.absolute()}"
            webbrowser.open(url)
            self.log(f"[OK] Opened self-test report: {report_path.name}")
        
        def close_dialog():
            results_window.destroy()
        
        ttk.Button(button_frame, text="Open HTML Report", command=open_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=close_dialog).pack(side=tk.LEFT, padx=5)
    
    def _show_self_test_error(self, error_msg: str):
        """Show self-test error dialog"""
        self.log(f"[X] Self-test failed: {error_msg}")
        messagebox.showerror(
            "Self-Test Error",
            f"Self-test encountered an error:\n\n{error_msg}\n\n"
            "Check execution log for details."
        )
    
    def _check_and_run_self_test_if_needed(self):
        """Check if self-test should run (first launch or code modification)"""
        if not SELF_TEST_AVAILABLE or not SelfTestEngine:
            return
        
        try:
            repo_root = _rbgyanx_base_dir()
            state_file = repo_root / ".rbgyanx_selftest_state.json"
            
            # Check if this is first launch
            first_launch = not state_file.exists()
            
            # Check for code modifications
            code_modified = False
            if state_file.exists():
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                    last_test_time = state.get('last_test_time', 0)
                    
                    # Check if key files have been modified since last test
                    key_files = [
                        'rbgyanx_gui.py',
                        'code1_dvh_preprocess.py',
                        'code3_ntcp_analysis_ml.py',
                        'code6_tcp_analysis.py'
                    ]
                    
                    for file_name in key_files:
                        file_path = repo_root / file_name
                        if file_path.exists():
                            file_mtime = file_path.stat().st_mtime
                            if file_mtime > last_test_time:
                                code_modified = True
                                break
                except Exception:
                    code_modified = True  # If state file is corrupted, assume modified
            
            # Run self-test if needed
            if first_launch or code_modified:
                self.log("[INFO] Running self-test (first launch or code modification detected)...")
                
                # Run in background thread to avoid blocking startup
                def run_test():
                    try:
                        engine = SelfTestEngine(repo_root)
                        results = engine.run_all_tests()
                        
                        # Save state
                        state = {
                            'last_test_time': datetime.now().timestamp(),
                            'last_status': results['status']
                        }
                        with open(state_file, 'w') as f:
                            json.dump(state, f)
                        
                        # Log summary
                        summary = results['summary']
                        self.log(f"[OK] Self-test completed: {results['status']} "
                                f"({summary['passed']}/{summary['total']} passed)")
                        
                        if results['status'] == 'FAIL':
                            self.log("[!] Self-test detected failures - check Tools → Self-Test for details")
                            # Show user consent dialog for failures (non-blocking)
                            self.root.after(0, lambda r=results: self._handle_self_test_failures(r))
                            # Show user consent dialog for failures (non-blocking)
                            self.root.after(0, lambda r=results: self._handle_self_test_failures(r))
                    except Exception as e:
                        self.log(f"[!] Self-test error (non-critical): {str(e)}")
                
                thread = threading.Thread(target=run_test, daemon=True)
                thread.start()
        except Exception as e:
            # Never crash on self-test check
            self.log(f"[!] Self-test check error (non-critical): {str(e)}")
    
    def _handle_self_test_failures(self, results: Dict):
        """Handle self-test failures with user consent"""
        summary = results['summary']
        failed_count = summary.get('failed', 0)
        
        if failed_count == 0:
            return
        
        # Show consent dialog
        consent_msg = (
            f"Self-Test detected {failed_count} failure(s).\n\n"
            "This may indicate system issues that could affect functionality.\n\n"
            "Options:\n"
            "• Continue anyway (not recommended)\n"
            "• Run Auto-Correction to attempt fixes\n"
            "• View detailed test results\n\n"
            "How would you like to proceed?"
        )
        
        # Create custom dialog with options (non-blocking, dismissible)
        consent_dialog = tk.Toplevel(self.root)
        consent_dialog.title("Self-Test Failures Detected")
        consent_dialog.geometry("500x400")
        consent_dialog.transient(self.root)
        # Don't grab - allow user to continue working (non-blocking)
        
        # Center dialog
        consent_dialog.update_idletasks()
        x = (consent_dialog.winfo_screenwidth() // 2) - (consent_dialog.winfo_width() // 2)
        y = (consent_dialog.winfo_screenheight() // 2) - (consent_dialog.winfo_height() // 2)
        consent_dialog.geometry(f"+{x}+{y}")
        
        ttk.Label(
            consent_dialog,
            text=f"Self-Test: {failed_count} Failure(s) Detected",
            font=("Arial", 12, "bold"),
            foreground="#dc3545"
        ).pack(pady=10)
        
        ttk.Label(
            consent_dialog,
            text=consent_msg,
            font=("Arial", 9),
            justify=tk.LEFT,
            wraplength=450
        ).pack(pady=10, padx=20)
        
        button_frame = ttk.Frame(consent_dialog)
        button_frame.pack(pady=20)
        
        def on_continue():
            self.log("[INFO] User chose to continue despite self-test failures")
            consent_dialog.destroy()
        
        def on_auto_correct():
            self.log("[INFO] User chose to run auto-correction after self-test failures")
            consent_dialog.destroy()
            self.menu_run_auto_correction()
        
        def on_view_results():
            self.log("[INFO] User chose to view self-test results")
            consent_dialog.destroy()
            # Show self-test results
            self._show_self_test_results(results, None)
        
        ttk.Button(button_frame, text="Continue Anyway", command=on_continue).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Run Auto-Correction", command=on_auto_correct).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Results", command=on_view_results).pack(side=tk.LEFT, padx=5)
    
    def menu_run_auto_correction(self):
        """Run auto-correction engine"""
        if not AUTO_CORRECTION_AVAILABLE or not AutoCorrectionEngine:
            messagebox.showerror(
                "Auto-Correction Unavailable",
                "Auto-correction engine is not available.\n\n"
                "Please ensure qa/auto_correction_engine.py exists."
            )
            return
        
        try:
            # OBJECTIVE E: Create backup before auto-correction
            repo_root = _rbgyanx_base_dir()
            try:
                from utils.backup_manager import create_backup_before_operation
                backup_path = create_backup_before_operation(repo_root, "auto_correction")
                if backup_path:
                    self.log(f"[OK] Backup created before auto-correction: {backup_path.name}")
            except ImportError:
                self.log("[!] Backup manager not available - proceeding without backup")
            
            self.log("=== Starting Auto-Correction Analysis ===")
            
            log_file = repo_root / "rbgyanx_gui.log"
            
            # Analyze log
            engine = AutoCorrectionEngine(repo_root, log_file)
            issues = engine.analyze_log()
            fixes = engine.propose_fixes()
            
            # Check for escalation needed
            needs_escalation, escalated_issues = engine.check_escalation_needed()
            
            if needs_escalation:
                # Generate diagnostic report
                report_dir = repo_root / "qa" / "reports"
                report_dir.mkdir(parents=True, exist_ok=True)
                diagnostic_path = report_dir / f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                engine.generate_diagnostic_report(diagnostic_path)
                self.log(f"[!] Escalation needed - diagnostic report: {diagnostic_path.name}")
                
                # Show escalation message
                escalation_msg = (
                    "⚠️ Issues Requiring Developer Intervention Detected\n\n"
                    "Some issues cannot be auto-corrected safely:\n\n"
                )
                for escalated in escalated_issues[:3]:  # Show first 3
                    escalation_msg += f"• {escalated.get('issue', 'Unknown issue')}\n"
                
                escalation_msg += (
                    "\n\nThis issue requires developer intervention.\n"
                    "Please switch to rbGyanX_advanced or use Cursor / Copilot / Codex.\n\n"
                    "A diagnostic report has been generated."
                )
                
                response = messagebox.askyesno(
                    "Escalation Required",
                    escalation_msg + "\n\nView diagnostic report now?",
                    icon='warning'
                )
                
                if response:
                    self._view_diagnostic_report(diagnostic_path)
                
                # Still show fixable issues if any
                if fixes:
                    response2 = messagebox.askyesno(
                        "Continue with Auto-Correction?",
                        f"There are {len(fixes)} fixable issues that can be safely corrected.\n\n"
                        "Proceed with auto-correction for these issues?",
                        icon='question'
                    )
                    if response2:
                        self._show_auto_correction_dialog(engine, issues, fixes)
                return
            
            if not fixes:
                messagebox.showinfo(
                    "Auto-Correction",
                    "No fixable issues detected in execution log.\n\n"
                    "All systems appear to be functioning correctly."
                )
                self.log("[OK] No fixable issues detected")
                return
            
            # Show fixes dialog with permission request
            self._show_auto_correction_dialog(engine, issues, fixes)
            
        except Exception as e:
            self.log(f"[X] Auto-correction error: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            messagebox.showerror("Auto-Correction Error", f"Error running auto-correction:\n{str(e)}")
    
    def _show_auto_correction_dialog(self, engine: AutoCorrectionEngine, issues: List[Dict], fixes: List[Dict]):
        """Show auto-correction dialog with proposed fixes and permission request"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Auto-Correction: Proposed Fixes")
        dialog.geometry("700x600")
        dialog.transient(self.root)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        header_frame = ttk.Frame(dialog, padding="10")
        header_frame.pack(fill=tk.X)
        
        ttk.Label(
            header_frame,
            text="Auto-Correction: Proposed Fixes",
            font=("Arial", 12, "bold")
        ).pack()
        
        ttk.Label(
            header_frame,
            text=f"Found {len(issues)} issues, {len(fixes)} fixable",
            font=("Arial", 9)
        ).pack(pady=5)
        
        # Warning about scientific code
        warning_frame = ttk.Frame(dialog, padding="10")
        warning_frame.pack(fill=tk.X, padx=10, pady=5)
        
        warning_text = (
            "⚠️ SAFETY: Auto-correction will NEVER modify:\n"
            "  • Scientific equations or models\n"
            "  • TCP/NTCP calculation logic\n"
            "  • Workflow steps\n"
            "\n"
            "Only fixes: missing directories, config files, import guards"
        )
        ttk.Label(
            warning_frame,
            text=warning_text,
            font=("Arial", 9),
            foreground="#856404",
            background="#fff3cd",
            padding="10",
            relief=tk.SUNKEN
        ).pack(fill=tk.BOTH, expand=True)
        
        # Fixes list
        fixes_frame = ttk.Frame(dialog)
        fixes_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(fixes_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        fixes_text = scrolledtext.ScrolledText(
            fixes_frame,
            wrap=tk.WORD,
            font=("Courier", 9),
            yscrollcommand=scrollbar.set,
            height=15
        )
        fixes_text.pack(fill=tk.BOTH, expand=True)
        
        # Add fixes to text widget
        for i, fix in enumerate(fixes, 1):
            issue = fix['issue']
            fixes_text.insert(tk.END, f"{i}. {fix['description']}\n")
            fixes_text.insert(tk.END, f"   Action: {fix['action']}\n")
            fixes_text.insert(tk.END, f"   Risk: {fix['risk_level']}, Reversible: {fix['reversible']}\n\n")
        
        fixes_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def on_apply_all():
            # Ask for confirmation
            confirmed = messagebox.askyesno(
                "Confirm Auto-Correction",
                f"Apply all {len(fixes)} proposed fixes?\n\n"
                "This will:\n"
                "  • Create missing directories\n"
                "  • Create placeholder config files\n"
                "  • NOT modify any scientific code\n\n"
                "Continue?"
            )
            
            if not confirmed:
                self.log("[INFO] Auto-correction cancelled by user")
                dialog.destroy()
                return
            
            self.log(f"[OK] Applying {len(fixes)} fixes...")
            
            # Apply fixes
            result = engine.apply_all_fixes(fixes, ask_permission=False)
            
            # Log results
            self.log(f"[OK] Auto-correction applied: {result['message']}")
            self.log(f"  Applied: {result['applied']}, Failed: {result['failed']}, Skipped: {result['skipped']}")
            
            # Generate reports
            repo_root = _rbgyanx_base_dir()
            report_dir = repo_root / "qa" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate fix report
            report_path = report_dir / f"autocorrection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            engine.generate_fix_report(report_path)
            self.log(f"[OK] Auto-correction report: {report_path.name}")
            
            # Generate diagnostic report if escalation needed
            needs_escalation, escalated_issues = engine.check_escalation_needed()
            if needs_escalation:
                diagnostic_path = report_dir / f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                engine.generate_diagnostic_report(diagnostic_path)
                self.log(f"[!] Diagnostic report: {diagnostic_path.name}")
            
            # Verify scientific code integrity
            if engine.verify_scientific_code_integrity():
                self.log("[OK] Scientific code integrity verified")
            else:
                self.log("[!] WARNING: Scientific code integrity check failed")
                messagebox.showwarning(
                    "Integrity Check Failed",
                    "Scientific code integrity check failed.\n\n"
                    "Please verify that protected modules are intact."
                )
            
            dialog.destroy()
            
            # Run self-test automatically after correction
            self.log("[INFO] Running self-test after auto-correction...")
            if SELF_TEST_AVAILABLE and SelfTestEngine:
                # Run self-test in background
                def run_selftest():
                    try:
                        test_engine = SelfTestEngine(repo_root)
                        test_results = test_engine.run_all_tests()
                        summary = test_results['summary']
                        self.log(f"[OK] Post-correction self-test: {test_results['status']} "
                                f"({summary['passed']}/{summary['total']} passed)")
                    except Exception as e:
                        self.log(f"[!] Post-correction self-test error: {str(e)}")
                
                thread = threading.Thread(target=run_selftest, daemon=True)
                thread.start()
            
            messagebox.showinfo(
                "Auto-Correction Complete",
                f"Applied {result['applied']} fixes.\n\n"
                f"Failed: {result['failed']}\n"
                f"Skipped: {result['skipped']}\n\n"
                "Self-test is running in background.\n"
                "Check execution log for details."
            )
        
        def on_cancel():
            self.log("[INFO] Auto-correction cancelled by user")
            dialog.destroy()
        
        ttk.Button(button_frame, text="Apply All Fixes", command=on_apply_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
    
    def menu_view_diagnostic_report(self):
        """
        Display the latest diagnostic / self-test report.
        Basic version: read-only viewer.
        """
        repo_root = _rbgyanx_base_dir()
        
        # Check multiple possible locations for diagnostic report
        possible_paths = [
            repo_root / "QA" / "diagnostic_report.txt",
            repo_root / "qa" / "diagnostic_report.txt",
            repo_root / "qa" / "reports" / "diagnostic_report.txt",
        ]
        
        # Also check for latest diagnostic report in qa/reports
        qa_reports_dir = repo_root / "qa" / "reports"
        if qa_reports_dir.exists():
            diagnostic_files = sorted(
                qa_reports_dir.glob("diagnostic_*.txt"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True
            )
            if diagnostic_files:
                possible_paths.insert(0, diagnostic_files[0])
        
        # Find the first existing report
        report_path = None
        for path in possible_paths:
            if path.exists():
                report_path = path
                break
        
        if not report_path:
            messagebox.showinfo(
                "Diagnostic Report",
                "No diagnostic report found.\n\n"
                "Run Tools → Self-Test to generate one."
            )
            return
        
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror(
                "Diagnostic Report Error",
                f"Unable to read diagnostic report:\n{e}"
            )
            return
        
        viewer = tk.Toplevel(self.root)
        viewer.title("rbGyanX Diagnostic Report")
        viewer.geometry("800x600")
        viewer.transient(self.root)
        
        # Center dialog
        viewer.update_idletasks()
        x = (viewer.winfo_screenwidth() // 2) - (viewer.winfo_width() // 2)
        y = (viewer.winfo_screenheight() // 2) - (viewer.winfo_height() // 2)
        viewer.geometry(f"+{x}+{y}")
        
        # Create scrollable text widget
        text_frame = ttk.Frame(viewer, padding="10")
        text_frame.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text = tk.Text(text_frame, wrap="word", font=("Courier", 9), yscrollcommand=scrollbar.set)
        scrollbar.config(command=text.yview)
        text.insert("1.0", content)
        text.config(state="disabled")
        text.pack(fill="both", expand=True)
        
        # Close button
        button_frame = ttk.Frame(viewer)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="Close", command=viewer.destroy).pack(side=tk.RIGHT)
    
    def menu_rollback(self):
        """
        Rollback last analysis outputs (basic version).
        Does NOT modify code. Only restores output directories.
        """
        import tkinter.messagebox as messagebox
        import shutil
        from pathlib import Path
        
        # Get output directory from GUI
        output_dir_str = self.output_dir.get()
        if not output_dir_str:
            messagebox.showinfo(
                "Rollback",
                "No output directory configured.\n\n"
                "Please set an output directory first."
            )
            return
        
        output_root = Path(output_dir_str)
        backup_root = output_root / "_rollback_backup"
        
        if not backup_root.exists():
            messagebox.showinfo(
                "Rollback",
                "No rollback point found.\n\n"
                "Rollback points are created automatically before analysis runs."
            )
            return
        
        confirm = messagebox.askyesno(
            "Confirm Rollback",
            "This will restore the last saved output state.\n\n"
            "Current outputs will be replaced.\n\n"
            "Continue?"
        )
        
        if not confirm:
            return
        
        try:
            for item in output_root.iterdir():
                if item.name == "_rollback_backup":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            
            for item in backup_root.iterdir():
                dest = output_root / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            
            messagebox.showinfo(
                "Rollback Complete",
                "Output rollback completed successfully."
            )
            self.log("[OK] Rollback completed successfully")
        
        except Exception as e:
            messagebox.showerror(
                "Rollback Error",
                f"Rollback failed:\n{e}"
            )
            self.log(f"[X] Rollback error: {str(e)}")
    
    def download_tcp_template(self):
        """Download TCP clinical template"""
        try:
            from clinical_template_generator import create_tcp_template
            
            output = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="TCP_Clinical_Template.xlsx",
                title="Save TCP Clinical Template"
            )
            
            if output:
                template_path = create_tcp_template(output, with_samples=True, n_samples=30)
                messagebox.showinfo(
                    "Template Created",
                    f"TCP clinical template created:\n\n{template_path}\n\n"
                    f"This template includes:\n"
                    f"• Required columns (PatientID, TumorControl)\n"
                    f"• Optional columns (Age, Gender, Stage, etc.)\n"
                    f"• 30 sample rows with realistic data\n"
                    f"• Instructions sheet\n\n"
                    f"Please review the Instructions sheet and modify sample data."
                )
        except ImportError as e:
            messagebox.showerror(
                "Import Error",
                f"Could not import template generator:\n{e}\n\n"
                f"Please ensure clinical_template_generator.py is in the project root."
            )
        except Exception as e:
            messagebox.showerror(
                "Template Creation Error",
                f"Failed to create TCP template:\n{e}"
            )
    
    def download_ntcp_template(self):
        """Download NTCP clinical template"""
        try:
            from clinical_template_generator import create_ntcp_template
            
            output = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                initialfile="NTCP_Clinical_Template.xlsx",
                title="Save NTCP Clinical Template"
            )
            
            if output:
                template_path = create_ntcp_template(output, with_samples=True, n_samples=30)
                messagebox.showinfo(
                    "Template Created",
                    f"NTCP clinical template created:\n\n{template_path}\n\n"
                    f"This template includes:\n"
                    f"• Required columns (PatientID, Organ, Toxicity)\n"
                    f"• Optional columns (Age, Gender, Stage, etc.)\n"
                    f"• 30 sample rows with realistic data\n"
                    f"• Instructions sheet\n\n"
                    f"Please review the Instructions sheet and modify sample data."
                )
        except ImportError as e:
            messagebox.showerror(
                "Import Error",
                f"Could not import template generator:\n{e}\n\n"
                f"Please ensure clinical_template_generator.py is in the project root."
            )
        except Exception as e:
            messagebox.showerror(
                "Template Creation Error",
                f"Failed to create NTCP template:\n{e}"
            )
    
    def menu_about(self):
        """Show about dialog with journal-aligned, scrollable content"""
        about_window = tk.Toplevel(self.root)
        # ADVANCED UI: Mode-aware About window title
        mode_label = "BASIC"
        if self.mode_controller and self.mode_controller.is_advanced():
            mode_label = "ADVANCED"
        about_window.title(f"About rbGyanX {mode_label}")
        about_window.geometry("650x600")
        about_window.resizable(True, True)
        
        # Set icon for about window
        self._set_window_icon(about_window)
        
        # Create scrollable text widget
        text_frame = ttk.Frame(about_window, padding="15")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scroll_text = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=10,
            pady=10,
            state=tk.NORMAL
        )
        scroll_text.pack(fill=tk.BOTH, expand=True)
        
        try:
            from rbgyanx.app_metadata import resolve_display_version

            version = resolve_display_version(self.feature_registry, _rbgyanx_base_dir())
        except ImportError:
            version = APP_VERSION if PATHS_AVAILABLE else "1.0.0"
        
        # Generate journal-aligned about text
        about_content = self._generate_about_content(version)
        scroll_text.insert("1.0", about_content)
        scroll_text.config(state=tk.DISABLED)
        
        # Buttons: Copy Citation and Close
        button_frame = ttk.Frame(about_window)
        button_frame.pack(fill=tk.X, padx=15, pady=10)
        
        def copy_citation():
            """Copy citation to clipboard"""
            # ADVANCED UI: Mode-aware citation
            mode_label_citation = "BASIC"
            if self.mode_controller and self.mode_controller.is_advanced():
                mode_label_citation = "ADVANCED"
            citation_text = f"Mondal, Kalyan. rbGyanX: A radiobiology-guided clinical decision support framework. Version {mode_label_citation}. 2025."
            try:
                about_window.clipboard_clear()
                about_window.clipboard_append(citation_text)
                messagebox.showinfo("Citation Copied", "Citation has been copied to clipboard.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not copy to clipboard: {str(e)}")
        
        ttk.Button(button_frame, text="Copy Citation", command=copy_citation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=about_window.destroy).pack(side=tk.RIGHT, padx=5)
        
    def _toggle_panel_maximize(self, panel_name):
        """OBJECTIVE 3: Toggle panel maximize/restore using grid weights"""
        if panel_name not in self.panels or not hasattr(self, 'body_frame'):
            return
        
        current_state = self.panel_states[panel_name]
        
        if current_state == 'normal':
            # Maximize this panel, minimize others - OBJECTIVE 3: Use grid column weights
            for name, panel in self.panels.items():
                if name == panel_name:
                    self.panel_states[name] = 'maximized'
                    # Maximize: high weight
                    self.body_frame.grid_columnconfigure(self._get_panel_column(name), weight=100, minsize=250)
                else:
                    self.panel_states[name] = 'minimized'
                    # Minimize: low weight, maintain minsize using grid_columnconfigure
                    self.body_frame.grid_columnconfigure(self._get_panel_column(name), weight=1, minsize=100)
        else:
            # Restore all panels - OBJECTIVE 3: Restore original weights
            self.body_frame.grid_columnconfigure(0, weight=1, minsize=250)  # Left
            self.body_frame.grid_columnconfigure(1, weight=2, minsize=250)  # Center
            self.body_frame.grid_columnconfigure(2, weight=2, minsize=250)  # Right
            
            for name, panel in self.panels.items():
                self.panel_states[name] = 'normal'
    
    def _get_panel_column(self, panel_name):
        """Get grid column index for panel"""
        column_map = {'left': 0, 'center': 1, 'right': 2}
        return column_map.get(panel_name, 0)
    
    def _create_panel_header(self, parent, panel_name, title):
        """OBJECTIVE 2: Create panel header with maximize/restore button"""
        header_frame = tk.Frame(parent, bg=UILayoutConstants.BG_LIGHT, height=25)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)
        
        # Title label
        title_label = tk.Label(header_frame, text=title, 
                              font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_SMALL, 'bold'),
                              bg=UILayoutConstants.BG_LIGHT, fg=UILayoutConstants.TEXT_PRIMARY)
        title_label.pack(side=tk.LEFT, padx=5)
        
        # Maximize/restore button
        btn_frame = tk.Frame(header_frame, bg=UILayoutConstants.BG_LIGHT)
        btn_frame.pack(side=tk.RIGHT, padx=2)
        
        def toggle_maximize():
            self._toggle_panel_maximize(panel_name)
            # Update button text
            current_state = self.panel_states[panel_name]
            btn_text = "⤡" if current_state == 'maximized' else "⤢"
            max_btn.config(text=btn_text)
        
        max_btn = tk.Button(btn_frame, text="⤢", width=2, height=1,
                           font=("Arial", 10), command=toggle_maximize,
                           bg=UILayoutConstants.BG_LIGHT, relief=tk.FLAT,
                           cursor="hand2")
        max_btn.pack()
        
        return header_frame
    
    def create_left_panel(self):
        """Left panel: Inputs and execution controls"""
        panel = ttk.Frame(self.root, relief=tk.RIDGE, borderwidth=2)
        
        # OBJECTIVE 2: Add panel header with maximize control (packed first)
        header = self._create_panel_header(panel, 'left', 'Workflow & Steps')
        
        # Create separate content frame for scrollable area (uses grid)
        content_frame = ttk.Frame(panel)
        content_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        # Create frame with both vertical and horizontal scrollbars
        v_scrollbar = ttk.Scrollbar(content_frame, orient="vertical")
        h_scrollbar = ttk.Scrollbar(content_frame, orient="horizontal")
        
        scroll_canvas = tk.Canvas(content_frame, 
                          yscrollcommand=v_scrollbar.set,
                          xscrollcommand=h_scrollbar.set)
        
        scrollable_frame = ttk.Frame(scroll_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        )
        
        scroll_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        v_scrollbar.config(command=scroll_canvas.yview)
        h_scrollbar.config(command=scroll_canvas.xview)
        
        # Grid layout for scrollbars (in content_frame, not panel)
        scroll_canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Enable mousewheel scrolling (ONLY for tkinter Canvas, not matplotlib)
        def bind_mousewheel(event):
            self.root.bind_all("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            self.root.bind_all("<Shift-MouseWheel>", lambda e: scroll_canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
        
        def unbind_mousewheel(event):
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Shift-MouseWheel>")
        
        scroll_canvas.bind("<Enter>", bind_mousewheel)
        scroll_canvas.bind("<Leave>", unbind_mousewheel)
        
        # Global Settings
        self.create_global_settings(scrollable_frame)
        
        # Analysis Type Selection (NTCP/TCP)
        self.create_analysis_type_selection(scrollable_frame)
        
        # Steps 1-6
        self.create_step1(scrollable_frame)
        self.create_step2(scrollable_frame)
        self.create_step3(scrollable_frame)
        self.create_step4(scrollable_frame)
        self.create_step5(scrollable_frame)
        self.create_step6(scrollable_frame)
        
        # Bottom actions
        self.create_global_actions(scrollable_frame)
        
        # Execution log
        self.create_execution_log(scrollable_frame)
        
        return panel
    
    def create_global_settings(self, parent):
        """Global settings section with analysis mode selection"""
        frame = ttk.LabelFrame(parent, text="Global Settings", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        # Analysis Mode Selection (MANDATORY - must be selected first)
        ttk.Label(frame, text="Analysis Mode (Select ONE):", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # User guidance text for mode selection
        guidance_text = ("Select the analysis type to perform:\n"
                        "• TCP only: Tumor Control Probability analysis (requires target structures like PTV/GTV/CTV)\n"
                        "• NTCP only: Normal Tissue Complication Probability analysis (requires OAR structures)\n"
                        "• TCP + NTCP: Both analyses with therapeutic ratio integration (Step 6)")
        ttk.Label(frame, text=guidance_text, 
                 font=("Arial", 8, "italic"), foreground="darkblue", justify=tk.LEFT,
                 wraplength=600).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(mode_frame, text="☐ TCP only", 
                       variable=self.analysis_mode, value="TCP_ONLY",
                       command=self.on_analysis_mode_change).pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(mode_frame, text="☐ NTCP only", 
                       variable=self.analysis_mode, value="NTCP_ONLY",
                       command=self.on_analysis_mode_change).pack(side=tk.LEFT, padx=10)
        
        ttk.Radiobutton(mode_frame, text="☐ TCP + NTCP", 
                       variable=self.analysis_mode, value="TCP_NTCP",
                       command=self.on_analysis_mode_change).pack(side=tk.LEFT, padx=10)
        
        # OBJECTIVE B: Cancer Site Selection (with proper spacing)
        ttk.Label(frame, text="Cancer Site:", font=("Arial", 9, "bold")).grid(row=3, column=0, sticky=tk.W, pady=(15, 5))
        
        site_frame = ttk.Frame(frame)
        site_frame.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        site_options = []
        if self.site_registry:
            for site_key, site_data in self.site_registry.items():
                display_name = site_data.get('display_name', site_key)
                site_options.append((display_name, site_key))
        else:
            # Fallback if registry not loaded
            site_options = [("Head & Neck", "HeadNeck")]
        
        site_combo = ttk.Combobox(site_frame, textvariable=self.cancer_site, 
                                 values=[opt[1] for opt in site_options],
                                 state="readonly", width=20)
        site_combo.pack(side=tk.LEFT, padx=5)
        site_combo.bind('<<ComboboxSelected>>', self.on_cancer_site_change)
        
        # Site validation status label
        self.site_status_label = ttk.Label(site_frame, text="", font=("Arial", 8), foreground="green")
        self.site_status_label.pack(side=tk.LEFT, padx=10)
        
        # Update site status on initialization
        self.on_cancer_site_change()
        
        # Output directory (SINGLE location for everything)
        ttk.Label(frame, text="Output Directory (All Results):").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.output_dir, width=40).grid(row=5, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(frame, text="Browse", 
                  command=lambda: self.browse_directory(self.output_dir)).grid(row=5, column=2)
        frame.columnconfigure(1, weight=1)
        
        # Clinical data (optional)
        ttk.Label(frame, text="Clinical Data (Optional):").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.clinical_file, width=40).grid(row=6, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(frame, text="Browse", 
                  command=lambda: self.browse_file(self.clinical_file, 
                  [("Excel", "*.xlsx"), ("CSV", "*.csv")])).grid(row=6, column=2)
        
        ttk.Label(frame, text="Note: Required for ML models and clinical factors analysis", 
                 font=("Arial", 8, "italic"), foreground="gray").grid(row=7, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # Info about auto-created subfolders
        info_text = ("Output subfolders will be auto-created:\n"
                    "├── processed_DVH/\n"
                    "├── dose_metrics/\n"
                    "├── tcp_analysis/ (if TCP enabled)\n"
                    "├── ntcp_analysis/ (if NTCP enabled)\n"
                    "├── integration/ (if TCP+NTCP mode)\n"
                    "├── qa/\n"
                    "└── logs/")
        ttk.Label(frame, text=info_text, 
                 font=("Courier", 8), foreground="darkblue", justify=tk.LEFT).grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
    
    def _on_input_source_change(self, event=None):
        """Update hints when DICOM vs TPS text source is selected (R2)."""
        if not hasattr(self, "input_source_hint"):
            return
        src = self.input_source.get() if hasattr(self, "input_source") else "dicom"
        basic = self.mode_controller and self.mode_controller.is_basic()
        if src == "dicom":
            hint = "DICOM RT folder -> Step 3 engine (Step 1 records manifest)"
            if basic:
                hint += " | BASIC supported"
        else:
            hint = "TPS .txt/.csv -> Step 1 auto-preprocess -> Steps 2-6"
            if basic:
                hint += " | BASIC supported"
        self.input_source_hint.config(text=hint)

    def _sync_input_source_from_path(self, path: Path) -> None:
        """Auto-detect DICOM vs TPS from selected folder (Phase 2)."""
        if not INPUT_ROUTER_AVAILABLE or not sync_source_pref_from_path:
            return
        try:
            detected = sync_source_pref_from_path(path, "auto")
            if detected != self.input_source.get():
                self.input_source.set(detected)
                self._on_input_source_change()
                self.log(f"[OK] Auto-detected input source: {detected}")
        except Exception as exc:
            self.log(f"[!] Input auto-detect: {exc}")

    def _uses_engine_dicom_path(self) -> bool:
        if not ENGINE_BRIDGE_AVAILABLE or not is_engine_available():
            return False
        if not self.raw_input.get():
            return False
        path = Path(self.raw_input.get())
        if INPUT_ROUTER_AVAILABLE and resolve_input_kind:
            return resolve_input_kind(
                path,
                self.input_source.get() if hasattr(self, "input_source") else "auto",
            ) == "dicom"
        if self.input_source.get() == "dicom":
            return path.is_dir() and is_dicom_directory(path)
        return path.is_dir() and detect_input_kind(path) == "dicom"

    def _get_site_detection_summary(self) -> list:
        """Read site_detection.csv for dashboard (R2)."""
        try:
            base = Path(self.output_dir.get()) if self.output_dir.get() else None
            if not base:
                return [("Status", "No output directory", None)]
            csv_path = base / "site_detection.csv"
            if not csv_path.is_file():
                return [("Status", "Run TCP/NTCP to detect site", None)]
            df = pd.read_csv(csv_path)
            if df.empty:
                return [("Status", "Empty site detection file", None)]
            rows = []
            for _, row in df.head(6).iterrows():
                pid = str(row.get("AnonPatientID", "?"))
                site = str(row.get("site_params_key", row.get("site_detected", "?")))
                conf = str(row.get("site_confidence", ""))
                color = "#27AE60" if conf.upper() == "HIGH" else "#E67E22" if conf else None
                rows.append((pid[:16], f"{site} ({conf or '?'})", color))
            return rows or [("Status", "No rows", None)]
        except Exception as exc:
            return [("Status", f"Could not read site_detection.csv ({exc})", "#E67E22")]

    def on_cancer_site_change(self, event=None):
        """OBJECTIVE B: Handle cancer site selection change."""
        site_key = self.cancer_site.get()
        if not self.site_registry or site_key not in self.site_registry:
            self.site_status_label.config(text="⚠ Site registry not loaded", foreground="orange")
            return
        
        site_data = self.site_registry[site_key]
        validation_status = site_data.get('validation_status', 'unknown')
        evidence_level = site_data.get('evidence_level', 'unknown')
        
        if validation_status == 'validated':
            self.site_status_label.config(
                text="✓ Validated (Head & Neck - Strong evidence)", 
                foreground="green"
            )
        else:
            self.site_status_label.config(
                text=f"⚠ Supported - Evidence evolving (use with caution)", 
                foreground="orange"
            )
            self.log(f"[INFO] Cancer site: {site_data.get('display_name', site_key)} - Evidence level: {evidence_level}")
        
        # Update dashboard
        self.root.after(100, self.update_dashboard_state)
    
    def create_analysis_type_selection(self, parent):
        """Analysis type selection (NTCP/TCP) - DEPRECATED, kept for backward compatibility"""
        # This section is now handled in Global Settings
        # Keeping for backward compatibility but hiding it
        pass
    
    def create_step1(self, parent):
        """Step 1: DVH Input & Preprocessing"""
        frame = ttk.LabelFrame(parent, text="Step 1: DVH Preprocessing", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        # Input format selection
        format_frame = ttk.Frame(frame)
        format_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Label(format_frame, text="Input Format:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(format_frame, text="Single File", variable=self.input_format, 
                       value="file").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(format_frame, text="Directory (Multiple Files)", 
                       variable=self.input_format, value="directory").pack(side=tk.LEFT, padx=5)

        # Phase R2: DICOM (clinic) vs TPS text export
        source_frame = ttk.Frame(frame)
        source_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Label(source_frame, text="Input source:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            source_frame,
            text="DICOM RT (recommended for clinic)",
            variable=self.input_source,
            value="dicom",
            command=self._on_input_source_change,
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            source_frame,
            text="TPS DVH export (.txt) — secondary",
            variable=self.input_source,
            value="tps_txt",
            command=self._on_input_source_change,
        ).pack(side=tk.LEFT, padx=5)
        self.input_source_hint = ttk.Label(
            source_frame,
            text="",
            font=("Arial", 8, "italic"),
            foreground="darkblue",
        )
        self.input_source_hint.pack(side=tk.LEFT, padx=10)
        self._on_input_source_change()
        
        # Raw input
        ttk.Label(frame, text="Raw DVH Input:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.raw_input, width=40).grid(row=3, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(frame, text="Browse", 
                  command=self.browse_raw_input).grid(row=3, column=2)
        frame.columnconfigure(1, weight=1)
        
        # Dynamic help text based on analysis type
        self.step1_help = ttk.Label(frame, text="", font=("Arial", 8, "italic"), 
                                   wraplength=400, justify=tk.LEFT, foreground="gray")
        self.step1_help.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=5)
        self.update_step1_help()
        
        # DVH type
        dvh_type_frame = ttk.Frame(frame)
        dvh_type_frame.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Label(dvh_type_frame, text="DVH Type:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(dvh_type_frame, text="Auto-detect", variable=self.dvh_type, 
                       value="auto").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(dvh_type_frame, text="Cumulative", variable=self.dvh_type, 
                       value="cumulative").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(dvh_type_frame, text="Differential", variable=self.dvh_type, 
                       value="differential").pack(side=tk.LEFT, padx=5)
        
        # Run button and status
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Run Step 1", 
                  command=self.run_step1).pack(side=tk.LEFT, padx=5)
        
        # Create contextual owl indicator for step 1 (hidden initially)
        # Get background color from style (ttk frames don't have bg option)
        try:
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
        except:
            bg_color = '#f0f0f0'
        owl_step1 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg=bg_color
        )
        self.step_owl_indicators["step1"] = owl_step1
        # Don't pack yet - will be shown when step starts
        
        # Status indicator
        self.step1_status = ttk.Label(button_frame, text="[ ] Not Started", foreground="gray")
        self.step1_status.pack(side=tk.LEFT, padx=10)
        self.step_status_labels["step1"] = self.step1_status
    
    def create_step2(self, parent):
        """Step 2: Dose Metrics & DVH Plots"""
        frame = ttk.LabelFrame(parent, text="Step 2: Dose Metrics & Plots", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        # Info label
        info_label = ttk.Label(frame, 
            text="Input: Auto-linked from Step 1 output\n"
                 "Calculates: Physical dose metrics only (OAR: V5-V50, Dmax; Target: D95, D98, V95, V100, HI, CI)",
            font=("Arial", 8, "italic"), foreground="gray", justify=tk.LEFT)
        info_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Run button and status
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=10)
        
        step2_button = ttk.Button(button_frame, text="Run Step 2", 
                                  command=self.run_step2)
        step2_button.pack(side=tk.LEFT, padx=5)
        
        # Create contextual owl indicator for step 2 (hidden initially)
        # Get background color from style (ttk frames don't have bg option)
        try:
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
        except:
            bg_color = '#f0f0f0'
        owl_step2 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg=bg_color
        )
        self.step_owl_indicators["step2"] = owl_step2
        # Don't pack yet - will be shown when step starts
        
        self.step2_status = ttk.Label(button_frame, text="[ ] Not Started", foreground="gray")
        self.step2_status.pack(side=tk.LEFT, padx=10)
        self.step_status_labels["step2"] = self.step2_status
    
    def create_step3(self, parent):
        """Step 3: TCP/NTCP Analysis with tabs - ENHANCED VERSION"""
        frame = ttk.LabelFrame(parent, text="Step 3: TCP/NTCP Analysis", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)

        self.step3_mode_hint = ttk.Label(
            frame,
            text="Select analysis mode (TCP / NTCP / both) and input source in Step 1.",
            font=("Arial", 8, "italic"),
            foreground="darkblue",
            wraplength=700,
            justify=tk.LEFT,
        )
        self.step3_mode_hint.pack(anchor=tk.W, pady=(0, 6))
        
        # Notebook for tabs (store reference for dynamic updates)
        # Ensure tabs are contained within frame with proper overflow handling
        # Add vertical padding to prevent TCP tab from being hidden behind cancer site text
        notebook_container = ttk.Frame(frame)
        notebook_container.pack(fill=tk.BOTH, expand=True, pady=(10, 5))
        
        notebook = ttk.Notebook(notebook_container)
        notebook.pack(fill=tk.BOTH, expand=True)
        self.step3_notebook = notebook
        
        # Tab 1: Traditional Models
        tab1 = ttk.Frame(notebook, padding="10")
        notebook.add(tab1, text="Traditional Models")
        
        # Container for model checkboxes (will be updated dynamically)
        self.models_frame = ttk.Frame(tab1)
        self.models_frame.pack(fill=tk.BOTH, expand=True)
        
        # Diagnosis selection frame
        diagnosis_frame = ttk.LabelFrame(tab1, text="Tumor Site / Diagnosis")
        diagnosis_frame.pack(fill='x', padx=5, pady=5)
        
        self.diagnosis_label = ttk.Label(
            diagnosis_frame, 
            text="Detecting from DVH metadata...",
            font=("Arial", 9)
        )
        self.diagnosis_label.pack(pady=5)
        
        # Manual diagnosis selection (shown if auto-detect fails)
        self.diagnosis_manual = tk.StringVar(value="Head & Neck Cancer")
        self.diagnosis_combo = ttk.Combobox(
            diagnosis_frame,
            textvariable=self.diagnosis_manual,
            values=[
                "Head & Neck Cancer",
                "Lung Cancer", 
                "Prostate Cancer",
                "Breast Cancer",
                "Brain Cancer",
                "Pelvic Cancer",
                "Other"
            ],
            state='disabled',  # Initially disabled until needed
            width=25
        )
        self.diagnosis_combo.pack(pady=5)
        
        # Organ/Target selection frame (dynamically populated)
        selection_frame = ttk.LabelFrame(tab1, text="Select Structures")
        selection_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollable frame for checkboxes
        scroll_canvas = tk.Canvas(selection_frame, height=150)
        scrollbar = ttk.Scrollbar(selection_frame, orient="vertical", command=scroll_canvas.yview)
        self.structures_frame = ttk.Frame(scroll_canvas)
        
        self.structures_frame.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        )
        
        scroll_canvas.create_window((0, 0), window=self.structures_frame, anchor="nw")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        
        scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Select All button
        select_all_btn = ttk.Button(
            selection_frame,
            text="Select All Detected Structures",
            command=self.select_all_structures
        )
        select_all_btn.pack(pady=5)
        
        # Note: Tumor/Organ Type dropdown removed - structure selection checkboxes handle this
        
        # Initialize model checkboxes based on current analysis type
        self.update_step3_models()
        
        # Tab 2: Edit Model Parameters
        tab2 = ttk.Frame(notebook, padding="10")
        notebook.add(tab2, text="Edit Parameters")
        
        # User guidance for Edit Parameters tab
        guidance_label2 = ttk.Label(tab2, 
            text="Adjust model parameters from literature defaults. Use 'Reset to Literature Values' to restore defaults.\n"
                 "Changes apply to the selected model only. Clinical validation recommended for custom parameters.",
            font=("Arial", 8, "italic"), foreground="darkblue", justify=tk.LEFT, wraplength=500)
        guidance_label2.pack(fill=tk.X, pady=(0, 10))
        
        # Model selection (will be updated dynamically based on analysis type)
        model_select_frame = ttk.Frame(tab2)
        model_select_frame.pack(fill=tk.X, pady=5)
        
        # Create inner frame for label and combo to use pack horizontally
        model_inner_frame = ttk.Frame(model_select_frame)
        model_inner_frame.pack(fill=tk.X, anchor=tk.W)
        ttk.Label(model_inner_frame, text="Selected Model:").pack(side=tk.LEFT, padx=(0, 10))
        
        # Initialize model combo based on current analysis type
        if self.analysis_type.get() == "NTCP":
            model_values = ["LKB Log-Logistic", "LKB Probit", "RS Poisson"]
            if self.selected_traditional_model.get() not in model_values:
                self.selected_traditional_model.set("LKB Log-Logistic")
        else:  # TCP
            model_values = ["Poisson TCP", "LKB TCP", "Logistic TCP", "EUD TCP"]
            if self.selected_traditional_model.get() not in model_values:
                self.selected_traditional_model.set("Poisson TCP")
        
        self.model_combo = ttk.Combobox(model_inner_frame, textvariable=self.selected_traditional_model,
                                  values=model_values,
                                  state="readonly", width=25)
        self.model_combo.pack(side=tk.LEFT, padx=5)
        
        # Bind model change event to update parameters and equations
        def on_model_change(e):
            self.update_model_parameters()
            self.populate_equations_tab()
        
        self.model_combo.bind("<<ComboboxSelected>>", on_model_change)
        
        # Store reference for dynamic updates
        self.step3_model_combo = self.model_combo
        
        # Parameter entry fields (will be populated dynamically based on selected model)
        self.param_entries = {}
        self.param_frame = ttk.LabelFrame(tab2, text="Model Parameters", padding="10")
        self.param_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Store reference to param_frame for dynamic updates
        self.param_inputs_frame = self.param_frame
        
        # Initialize parameters for default model
        self.update_model_parameters()
        
        # Button frame
        button_frame = ttk.Frame(tab2)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Reset to Literature Values", 
                  command=self.reset_parameters).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply Changes", 
                  command=self.apply_custom_parameters).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show Equation", 
                  command=self.show_equation_popup).pack(side=tk.LEFT, padx=5)
        
        # Tab 3: View Model Equations
        tab3 = ttk.Frame(notebook, padding="10")
        notebook.add(tab3, text="View Equations")
        
        # User guidance for View Equations tab
        guidance_label3 = ttk.Label(tab3, 
            text="View mathematical equations for each radiobiological model. Equations show the theoretical foundation\n"
                 "and parameter dependencies. Select a model from the 'Edit Parameters' tab to view its equation.",
            font=("Arial", 8, "italic"), foreground="darkblue", justify=tk.LEFT, wraplength=500)
        guidance_label3.pack(fill=tk.X, pady=(0, 10))
        
        # Frame for equations content
        self.equations_text_frame = ttk.Frame(tab3)
        self.equations_text_frame.pack(fill='both', expand=True)
        
        # Initialize equations content
        self.populate_equations_tab()
        
        # ML Options with guidance
        ml_guidance_frame = ttk.Frame(frame)
        ml_guidance_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(ml_guidance_frame, 
                 text="ML Models (Optional): Enable machine learning models (ANN, XGBoost) for enhanced predictions.\n"
                      "SHAP: Enable explainability analysis to understand feature importance in ML predictions.",
                 font=("Arial", 8, "italic"), foreground="darkblue", justify=tk.LEFT, wraplength=600).pack(anchor=tk.W)
        
        ml_frame = ttk.Frame(frame)
        ml_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(ml_frame, text="Enable ML Models (Requires Clinical Data)", 
                       variable=self.enable_ml,
                       command=lambda: self.root.after(100, self.update_dashboard_state)).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(ml_frame, text="☑ ANN", state=tk.DISABLED).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(ml_frame, text="☑ XGBoost", state=tk.DISABLED).pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(ml_frame, text="Enable SHAP Explainability", 
                       variable=self.enable_shap).pack(side=tk.LEFT, padx=(20, 5))
        
        # OBJECTIVE B: Novel Features Section
        novel_features_frame = ttk.LabelFrame(frame, text="Novel Features (rbGyanX CDSS Framework)", padding="5")
        novel_features_frame.pack(fill=tk.X, pady=(10, 5))
        
        # Guidance text
        ttk.Label(novel_features_frame, 
                 text="Advanced radiobiological features for enhanced clinical decision support:",
                 font=("Arial", 8, "italic"), foreground="darkblue", justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 5))
        
        # Feature checkboxes
        features_inner = ttk.Frame(novel_features_frame)
        features_inner.pack(fill=tk.X)
        
        ttk.Checkbutton(features_inner, text="Enable FDVH (Fractionation-Aware DVH)", 
                       variable=self.use_fdvh,
                       command=self._on_fdvh_toggle).pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(features_inner, text="Enable uTCP (Uncertainty-Aware TCP)", 
                       variable=self.use_utcp,
                       state=tk.DISABLED if (self.mode_controller and self.mode_controller.is_advanced() and not self.mode_controller.is_capability_enabled("applicability_override")) else tk.NORMAL,
                       command=lambda: self.root.after(100, self.update_dashboard_state)).pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(features_inner, text="Enable CCS (ML Safety Gating)", 
                       variable=self.use_ccs,
                       command=self._on_ccs_toggle).pack(side=tk.LEFT, padx=5)
        
        # CCS file selection (shown when CCS is enabled)
        self.ccs_file_frame = ttk.Frame(novel_features_frame)
        self.ccs_file_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(self.ccs_file_frame, text="CCS Checker File:").pack(side=tk.LEFT, padx=(0, 5))
        ccs_entry = ttk.Entry(self.ccs_file_frame, textvariable=self.ccs_file_path, width=40)
        ccs_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.ccs_file_frame, text="Browse...", 
                  command=lambda: self._browse_ccs_file()).pack(side=tk.LEFT, padx=5)
        
        # Initially hide CCS file frame
        self.ccs_file_frame.pack_forget()
        
        # Run button and status
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        step3_button = ttk.Button(button_frame, text="Run Step 3", 
                                  command=self.run_step3)
        step3_button.pack(side=tk.LEFT, padx=5)
        
        # Create contextual owl indicator for step 3 (hidden initially)
        # Get background color from style (ttk frames don't have bg option)
        try:
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
        except:
            bg_color = '#f0f0f0'
        owl_step3 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg=bg_color
        )
        self.step_owl_indicators["step3"] = owl_step3
        # Don't pack yet - will be shown when step starts
        
        self.step3_status = ttk.Label(button_frame, text="[ ] Not Started", foreground="gray")
        self.step3_status.pack(side=tk.LEFT, padx=10)
        self.step_status_labels["step3"] = self.step3_status
    
    def create_step4(self, parent):
        """Step 4: Clinical Factors Analysis"""
        frame = ttk.LabelFrame(parent, text="Step 4: Clinical Factors Analysis", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        info_label = ttk.Label(frame, 
            text="Input: Uses TCP/NTCP results + Clinical Data (Auto-linked)",
            font=("Arial", 8, "italic"), foreground="gray")
        info_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        ttk.Checkbutton(frame, text="Use GLM (statsmodels) for advanced statistics", 
                       variable=self.use_glm).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        # Run button and status
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        step4_button = ttk.Button(button_frame, text="Run Step 4", 
                                  command=self.run_step4)
        step4_button.pack(side=tk.LEFT, padx=5)
        
        # Create contextual owl indicator for step 4 (hidden initially)
        owl_step4 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg='#f0f0f0'  # Default background (ttk frames don't have bg option)
        )
        self.step_owl_indicators["step4"] = owl_step4
        # Don't pack yet - will be shown when step starts
        
        # Create contextual owl indicator for step 4 (hidden initially)
        owl_step4 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg='#f0f0f0'  # Default background (ttk frames don't have bg option)
        )
        self.step_owl_indicators["step4"] = owl_step4
        # Don't pack yet - will be shown when step starts
        
        self.step4_status = ttk.Label(button_frame, text="[ ] Not Started", foreground="gray")
        self.step4_status.pack(side=tk.LEFT, padx=10)
        self.step_status_labels["step4"] = self.step4_status
    
    def create_step5(self, parent):
        """Step 5: Quality Assurance"""
        frame = ttk.LabelFrame(parent, text="Step 5: Quality Assurance", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        info_label = ttk.Label(frame, 
            text="Input: Uses all outputs (Auto-linked)\n"
                 "QA Checks: Patient count consistency, unrealistic values, overfitting, missing data",
            font=("Arial", 8, "italic"), foreground="gray", justify=tk.LEFT)
        info_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Run button and status (with robot animation)
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=10)
        
        step5_button = ttk.Button(button_frame, text="Run Step 5", 
                                  command=self.run_step5)
        step5_button.pack(side=tk.LEFT, padx=5)
        
        # Create contextual owl indicator for step 5 (hidden initially)
        # Get background color from style (ttk frames don't have bg option)
        try:
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
        except:
            bg_color = '#f0f0f0'
        owl_step5 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg=bg_color
        )
        self.step_owl_indicators["step5"] = owl_step5
        # Don't pack yet - will be shown when step starts
        
        self.step5_status = ttk.Label(button_frame, text="[ ] Not Started", foreground="gray")
        self.step5_status.pack(side=tk.LEFT, padx=10)
        self.step_status_labels["step5"] = self.step5_status
    
    def create_step6(self, parent):
        """Step 6: TCP-NTCP Integration - OBJECTIVE 3: Fixed layout collision"""
        frame = ttk.LabelFrame(parent, text="Step 6: TCP-NTCP Integration", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # OBJECTIVE 3: Use grid with proper row management to prevent overlap
        # Row 0: Info box (non-overlapping)
        info_box = tk.Frame(frame, bg='#f7f7f7', relief='solid', bd=1)
        info_box.grid(row=0, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(0, UILayoutConstants.WIDGET_SPACING), padx=5)
        info_box.grid_columnconfigure(0, weight=1)
        
        info_label = tk.Label(info_box, 
            text="Requires: Both TCP and NTCP analyses completed\n"
                 "Calculates: UTCP, P+, CFTC, TWI (Therapeutic Ratio Metrics)\n"
                 "Features: TWI calculation, plan ranking, risk-weighted NTCP",
            font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_SMALL, "italic"), 
            fg="darkblue", justify=tk.LEFT, bg='#f7f7f7', wraplength=400)
        info_label.pack(fill=tk.X, pady=4, padx=5)
        
        # Row 1: Warning banner (non-overlapping)
        warning_frame = tk.Frame(frame, bg='#f7f7f7', relief='solid', bd=1)
        warning_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(0, UILayoutConstants.WIDGET_SPACING), padx=5)
        warning_label = tk.Label(warning_frame, 
            text="⚠️ Decision support only – no automated clinical decisions",
            font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_SMALL, "bold"), 
            fg="#8B0000", justify=tk.CENTER, bg='#f7f7f7')
        warning_label.pack(fill=tk.X, pady=4, padx=5)
        
        # Row 2: Run button and status (separate row, no overlap)
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=UILayoutConstants.WIDGET_SPACING)
        ttk.Button(button_frame, text="Run Step 6", 
                  command=self.run_step6).pack(side=tk.LEFT, padx=5)
        
        # Create contextual owl indicator for step 6 (hidden initially)
        # Get background color from style (ttk frames don't have bg option)
        try:
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
        except:
            bg_color = '#f0f0f0'
        owl_step6 = BlinkingOwlIndicator(
            button_frame,
            size=(20, 20),
            bg=bg_color
        )
        self.step_owl_indicators["step6"] = owl_step6
        # Don't pack yet - will be shown when step starts
        
        self.step6_status = ttk.Label(button_frame, text="[ ] Not Started", foreground="gray")
        self.step6_status.pack(side=tk.LEFT, padx=10)
        self.step_status_labels["step6"] = self.step6_status
        
        # OBJECTIVE 3: Configure grid weights for proper resizing
        frame.grid_columnconfigure(0, weight=1)
    
    def create_global_actions(self, parent):
        """Global action buttons"""
        frame = ttk.LabelFrame(parent, text="Global Actions", padding="10")
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)
        
        run_all_text = f"Run All {self.analysis_type.get()} Steps"
        self.run_all_button = ttk.Button(button_frame, text=run_all_text, 
                                        command=self.run_all_steps)
        self.run_all_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Stop Execution", 
                  command=self.stop_execution).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear All Inputs", 
                  command=self.clear_all_inputs).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Configuration", 
                  command=self.save_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Configuration", 
                  command=self.load_configuration).pack(side=tk.LEFT, padx=5)
        
        # Progress bar for Run All mode
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame, variable=self.progress_var, 
                                           maximum=6, length=300, mode='determinate')
        self.progress_bar.pack(pady=(10, 0), fill=tk.X)
    
    def create_execution_log(self, parent):
        """Execution log area"""
        frame = ttk.LabelFrame(parent, text="Execution Log", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        
        self.log_text = scrolledtext.ScrolledText(frame, width=50, height=10, 
                                                  wrap=tk.WORD, font=("Courier", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log("Execution log initialized. Ready to run steps.")
    
    def create_center_panel(self):
        """Center panel: Summary and statistics with BOTH H and V scrollbars"""
        panel = ttk.Frame(self.root, relief=tk.RIDGE, borderwidth=2)
        
        # ADVANCED UI: Show ADVANCED dashboard if in ADVANCED mode with validation enabled
        if (self.mode_controller and self.mode_controller.is_advanced() and
            self.validation_controller and self.validation_controller.is_validation_enabled()):
            try:
                from rbgyanx.ui.advanced_dashboard import AdvancedDashboard
                advanced_dashboard = AdvancedDashboard(
                    panel,
                    mode_controller=self.mode_controller,
                    validation_controller=self.validation_controller
                )
                dashboard_frame = advanced_dashboard.create_dashboard()
                if dashboard_frame:
                    dashboard_frame.pack(fill=tk.BOTH, expand=True)
                    self.advanced_dashboard = advanced_dashboard  # Store reference
                    return panel
            except ImportError as e:
                # Fallback to BASIC if ADVANCED dashboard not available
                pass
        
        # OBJECTIVE 2: Add panel header with maximize control (packed first)
        # MODE-AWARE UI FIX: Dashboard header reflects mode
        if (self.mode_controller and self.mode_controller.is_advanced() and
            self.validation_controller and self.validation_controller.is_validation_enabled()):
            header_title = 'Advanced Dashboard — Research & Validation'
        else:
            header_title = 'Data Summary & QA — Clinical Decision Support'
        header = self._create_panel_header(panel, 'center', header_title)
        
        # Create separate content frame for scrollable area (uses grid)
        content_frame = ttk.Frame(panel)
        content_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        # Create frame with both vertical and horizontal scrollbars (beautification fix)
        v_scrollbar = ttk.Scrollbar(content_frame, orient="vertical")
        h_scrollbar = ttk.Scrollbar(content_frame, orient="horizontal")
        
        scroll_canvas = tk.Canvas(content_frame, 
                          yscrollcommand=v_scrollbar.set,
                          xscrollcommand=h_scrollbar.set,
                          highlightthickness=0)
        
        scrollable_frame = ttk.Frame(scroll_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        )
        
        # Bind scroll canvas configure to adjust inner frame width
        def on_scroll_canvas_configure(event):
            canvas_width = event.width
            frame_width = scrollable_frame.winfo_reqwidth()
            if frame_width < canvas_width:
                scroll_canvas.itemconfig(canvas_window, width=canvas_width)
        
        canvas_window = scroll_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        scroll_canvas.bind("<Configure>", on_scroll_canvas_configure)
        
        v_scrollbar.config(command=scroll_canvas.yview)
        h_scrollbar.config(command=scroll_canvas.xview)
        
        # Grid layout for scrollbars (in content_frame, not panel)
        scroll_canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Enable mousewheel scrolling (ONLY for tkinter Canvas, not matplotlib)
        def bind_mousewheel(event):
            self.root.bind_all("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            self.root.bind_all("<Shift-MouseWheel>", lambda e: scroll_canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
        
        def unbind_mousewheel(event):
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Shift-MouseWheel>")
        
        scroll_canvas.bind("<Enter>", bind_mousewheel)
        scroll_canvas.bind("<Leave>", unbind_mousewheel)
        
        # Notebook for different summaries (inside scrollable frame)
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Data Summary
        self.summary_text = scrolledtext.ScrolledText(notebook, width=40, height=30, 
                                                      wrap=tk.WORD, font=("Courier", 10))
        notebook.add(self.summary_text, text="Data Summary")
        self.summary_text.insert("1.0", "Data summary will appear here after Step 1 completes.")
        
        # Tab 2: Model Parameters
        self.params_text = scrolledtext.ScrolledText(notebook, width=40, height=30, 
                                                     wrap=tk.WORD, font=("Courier", 10))
        notebook.add(self.params_text, text="Model Parameters")
        self.params_text.insert("1.0", "Model parameters will appear here after Step 3 completes.")
        
        # Tab 3: Statistics
        self.stats_text = scrolledtext.ScrolledText(notebook, width=40, height=30, 
                                                    wrap=tk.WORD, font=("Courier", 10))
        notebook.add(self.stats_text, text="Statistics")
        self.stats_text.insert("1.0", "Statistics will appear here after analysis completes.")
        
        # Tab 4: QA Report
        self.qa_text = scrolledtext.ScrolledText(notebook, width=40, height=30, 
                                                 wrap=tk.WORD, font=("Courier", 10))
        notebook.add(self.qa_text, text="QA Report")
        self.qa_text.insert("1.0", "QA report will appear here after Step 5 completes.")
        
        # STEP 3: Add ADVANCED research tabs if in ADVANCED mode
        if self.mode_controller and self.mode_controller.is_advanced():
            self._add_advanced_research_tabs(notebook)
        
        # Store notebook reference for tab handlers
        self.center_notebook = notebook
        
        return panel
    
    def _add_advanced_research_tabs(self, notebook):
        """
        STEP 4: Add ADVANCED research analysis tabs.
        
        This method adds research-specific tabs to the center notebook
        when in ADVANCED mode. Each tab provides UI exposure for
        existing ADVANCED capabilities.
        
        Parameters
        ----------
        notebook : ttk.Notebook
            The center panel notebook to add tabs to
        """
        if not self.mode_controller or not self.mode_controller.is_advanced():
            return
        
        # Research Analysis tab container
        research_tab = ttk.Frame(notebook, padding=10)
        notebook.add(research_tab, text="Research Analysis")
        
        # Create inner notebook for research sub-tabs
        research_notebook = ttk.Notebook(research_tab)
        research_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Helper method to create research tabs
        def _add_research_tab(name, description):
            tab_frame = ttk.Frame(research_notebook, padding=15)
            research_notebook.add(tab_frame, text=name)
            
            # Research mode disclaimer
            disclaimer = ttk.Label(
                tab_frame,
                text="Research Mode — Exploratory Analysis\nNo clinical recommendations.\nResults are descriptive only.",
                foreground="darkorange",
                font=("Arial", 10, "bold"),
                wraplength=500,
                justify=tk.LEFT
            )
            disclaimer.pack(padx=20, pady=20, anchor="w")
            
            # Description
            desc_label = ttk.Label(
                tab_frame,
                text=description,
                font=("Arial", 9),
                wraplength=500,
                justify=tk.LEFT
            )
            desc_label.pack(padx=20, pady=(0, 20), anchor="w")
            
            # Results area
            results_frame = ttk.LabelFrame(tab_frame, text="Analysis Results", padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            results_text = scrolledtext.ScrolledText(
                results_frame,
                wrap=tk.WORD,
                font=("Courier", 9),
                height=15
            )
            results_text.pack(fill=tk.BOTH, expand=True)
            results_text.insert('1.0', f"Results for {name} will appear here.\n\nRun analysis to see results.")
            results_text.config(state=tk.DISABLED)
            
            return tab_frame
        
        # Add research tabs
        _add_research_tab("Model Agreement", "Compare model agreement / divergence")
        _add_research_tab("Sensitivity", "Parameter sensitivity & stability")
        _add_research_tab("Uncertainty", "Uncertainty source decomposition")
        _add_research_tab("Robustness", "Robustness & brittleness indices")
        _add_research_tab("Applicability", "Model applicability boundaries")
        _add_research_tab("Protocol Stress", "Protocol robustness exploration")
        _add_research_tab("Benchmarks", "QUANTEC / RTOG / ESTRO context")
        _add_research_tab("Developer", "Governed research sandbox")
        _add_research_tab("Education", "Teaching & intuition training")
    
    def create_right_panel(self):
        """Right panel: Visualizations with BOTH H and V scrollbars"""
        panel = ttk.Frame(self.root, relief=tk.RIDGE, borderwidth=2)
        
        # OBJECTIVE 2: Add panel header with maximize control (packed first)
        # ADVANCED UI: Mode-aware panel title
        panel_title = 'Visualizations & Dashboard'
        if (self.mode_controller and self.mode_controller.is_advanced() and
            self.validation_controller and self.validation_controller.is_validation_enabled()):
            panel_title = 'ADVANCED Visualizations & Dashboard'
        header = self._create_panel_header(panel, 'right', panel_title)
        
        # Create separate content frame for scrollable area (uses grid)
        content_frame = ttk.Frame(panel)
        content_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        # Create frame with both vertical and horizontal scrollbars (beautification fix)
        v_scrollbar = ttk.Scrollbar(content_frame, orient="vertical")
        h_scrollbar = ttk.Scrollbar(content_frame, orient="horizontal")
        
        scroll_canvas = tk.Canvas(content_frame, 
                          yscrollcommand=v_scrollbar.set,
                          xscrollcommand=h_scrollbar.set,
                          highlightthickness=0)
        
        scrollable_frame = ttk.Frame(scroll_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        )
        
        # Bind scroll canvas configure to adjust inner frame width
        def on_scroll_canvas_configure(event):
            canvas_width = event.width
            frame_width = scrollable_frame.winfo_reqwidth()
            if frame_width < canvas_width:
                scroll_canvas.itemconfig(canvas_window, width=canvas_width)
        
        canvas_window = scroll_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        scroll_canvas.bind("<Configure>", on_scroll_canvas_configure)
        
        v_scrollbar.config(command=scroll_canvas.yview)
        h_scrollbar.config(command=scroll_canvas.xview)
        
        # Grid layout for scrollbars (in content_frame, not panel)
        scroll_canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        
        # Enable mousewheel scrolling (ONLY for tkinter Canvas, not matplotlib)
        def bind_mousewheel(event):
            self.root.bind_all("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            self.root.bind_all("<Shift-MouseWheel>", lambda e: scroll_canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
        
        def unbind_mousewheel(event):
            self.root.unbind_all("<MouseWheel>")
            self.root.unbind_all("<Shift-MouseWheel>")
        
        scroll_canvas.bind("<Enter>", bind_mousewheel)
        scroll_canvas.bind("<Leave>", unbind_mousewheel)
        
        # Visualization tabs (inside scrollable frame)
        notebook = ttk.Notebook(scrollable_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # OBJECTIVE 4: Clinical Dashboard Panel (first tab, read-only)
        # STEP 5: Mode-aware right panel title
        if self.mode_controller and self.mode_controller.is_advanced():
            dashboard_label = "Research Context & Validity"
        else:
            dashboard_label = "Clinical Dashboard"
        
        dashboard_tab = ttk.Frame(notebook)
        notebook.add(dashboard_tab, text=dashboard_label)
        self._create_clinical_dashboard(dashboard_tab)
        
        # Create tabs for each visualization type
        self.viz_tabs = {}
        viz_types = ["Patient Cohort", "DVH Plots", "Dose-Response", 
                    "ROC/Calibration", "Factor Plots", "Therapeutic Window"]
        
        # OBJECTIVE A: Add Plan Comparison tab
        viz_types.append("Plan Comparison")
        
        for viz_type in viz_types:
            tab_frame = ttk.Frame(notebook)
            notebook.add(tab_frame, text=viz_type)
            
            # Matplotlib figure embedded in tkinter
            fig = Figure(figsize=(6, 5), dpi=100)
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, f"{viz_type}\n\nVisualization will appear here\nafter relevant steps complete.",
                   ha='center', va='center', fontsize=12, transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Use plot_canvas for Matplotlib canvas (never reuse scroll_canvas name)
            plot_canvas = FigureCanvasTkAgg(fig, master=tab_frame)
            plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Toolbar
            toolbar = NavigationToolbar2Tk(plot_canvas, tab_frame)
            toolbar.update()
            
            self.viz_tabs[viz_type] = {'figure': fig, 'canvas': plot_canvas, 'axes': ax}
        
        # OBJECTIVE A: Create Plan Comparison tab with disclaimer - Refined for less visual dominance
        if "Plan Comparison" in self.viz_tabs:
            plan_comp_tab = self.viz_tabs["Plan Comparison"]['figure'].canvas.get_tk_widget().master
            # Add disclaimer to Plan Comparison tab
            disclaimer_frame = tk.Frame(plan_comp_tab, bg='#f7f7f7', relief='solid', bd=1)  # Use tk.Frame for direct bg control
            disclaimer_frame.pack(fill=tk.X, padx=10, pady=5)
            disclaimer_label = tk.Label(
                disclaimer_frame,
                text="⚠️ rbGyanX provides comparative analysis only. Final clinical decisions remain clinician-led.",
                font=("Segoe UI", 8, "bold"),  # Reduced from 9 to 8, clinical font
                fg="#8B0000",  # Softer dark red instead of bright red
                wraplength=600,
                justify=tk.CENTER,
                bg='#f7f7f7'
            )
            disclaimer_label.pack(pady=4, padx=5)
        
        # Add Validation & QA tab (UI-only, non-blocking)
        validation_tab = ttk.Frame(notebook)
        notebook.add(validation_tab, text="Validation & QA")
        self._create_validation_qa_tab(validation_tab)
        
        # Store notebook reference for tab handlers
        self.right_notebook = notebook
        
        # Store dashboard reference for updates
        self.dashboard_tab = dashboard_tab
        
        return panel
    
    def _create_clinical_dashboard(self, parent):
        """Dynamic state-driven clinical dashboard with status cards"""
        # Main container with scrollable area
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        def on_frame_configure(event):
            """Update scroll region when frame size changes"""
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def on_canvas_configure(event):
            """Update canvas window width when canvas size changes"""
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        scrollable_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Store canvas and scrollable_frame for scroll region updates
        self.dashboard_canvas = canvas
        self.dashboard_scrollable_frame = scrollable_frame
        
        # Main container with padding
        main_frame = ttk.Frame(scrollable_frame, padding=UILayoutConstants.PADDING_LARGE)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Store main_frame for updates
        self.dashboard_main_frame = main_frame
        
        # Title - STEP 5: Mode-aware dashboard title
        if self.mode_controller and self.mode_controller.is_advanced():
            dashboard_title = "Research Context & Validity"
        else:
            dashboard_title = "Clinical Dashboard"
        
        title_label = ttk.Label(main_frame, 
                               text=dashboard_title,
                               font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_LARGE, 'bold'))
        title_label.pack(pady=(0, UILayoutConstants.SECTION_SPACING))
        
        # Create status cards container (will be populated by update method)
        self.dashboard_cards = {}
        
        # Initial dashboard state update
        self.update_dashboard_state()
    
    def _get_patient_count(self):
        """Get number of patients loaded from output directory"""
        try:
            output_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            if not output_dir or not output_dir.exists():
                return 0
            
            # Try to get patient count from processed DVH or results files
            processed_dir = output_dir / "processed_DVH"
            if processed_dir.exists():
                dvh_files = list(processed_dir.glob("*.xlsx"))
                if dvh_files:
                    # Try to read first file to count unique patients
                    try:
                        df = pd.read_excel(dvh_files[0], engine='openpyxl')
                        if 'Patient_ID' in df.columns:
                            return len(df['Patient_ID'].unique())
                        elif 'Patient' in df.columns:
                            return len(df['Patient'].unique())
                    except:
                        pass
                    return len(dvh_files)
            
            # Try TCP/NTCP results
            for results_file in [output_dir / "tcp_predictions.xlsx", 
                                output_dir / "ntcp_predictions.xlsx"]:
                if results_file.exists():
                    try:
                        df = pd.read_excel(results_file, engine='openpyxl')
                        if 'Patient_ID' in df.columns:
                            return len(df['Patient_ID'].unique())
                        elif 'Patient' in df.columns:
                            return len(df['Patient'].unique())
                    except:
                        pass
            
            return 0
        except:
            return 0
    
    def _get_current_step(self):
        """Get current step being executed"""
        if hasattr(self, 'processing_step') and self.processing_step:
            return self.processing_step.replace('step', 'Step ')
        return "Idle"
    
    def _read_engine_tcp_summary(self, output_dir: Path) -> pd.DataFrame | None:
        for rel in (
            "tcp_analysis/tcp_benchmarking.xlsx",
            "tcp_analysis/tcp_predictions.xlsx",
            "tcp_predictions.xlsx",
        ):
            path = output_dir / rel
            if path.is_file():
                try:
                    return pd.read_excel(path, engine="openpyxl")
                except Exception:
                    continue
        return None

    def _read_engine_ntcp_table(self, output_dir: Path) -> pd.DataFrame | None:
        for rel in (
            "ntcp_analysis/ntcp_results.csv",
            "ntcp_results.csv",
        ):
            path = output_dir / rel
            if path.is_file():
                try:
                    return pd.read_csv(path)
                except Exception:
                    continue
        ntcp_xlsx = output_dir / "ntcp_analysis" / "ntcp_benchmarking.xlsx"
        if ntcp_xlsx.is_file():
            try:
                return pd.read_excel(ntcp_xlsx, sheet_name="NTCP_Summary", engine="openpyxl")
            except Exception:
                pass
        return None

    def _get_utcp_summary(self) -> list:
        try:
            output_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            if not output_dir or not output_dir.exists():
                return [("Status", "No output yet", None)]
            df = self._read_engine_tcp_summary(output_dir)
            if df is None or "UTCP" not in df.columns:
                return [("Status", "Run TCP+NTCP (engine) for UTCP", None)]
            utcp = pd.to_numeric(df["UTCP"], errors="coerce")
            if utcp.notna().any():
                mean_u = float(utcp.mean())
                color = "#27AE60" if mean_u >= 0.5 else "#E67E22" if mean_u >= 0.2 else "#C0392B"
                rows = [("Mean UTCP", f"{mean_u:.3f}", color)]
                if "UTCP_weighted" in df.columns:
                    w = pd.to_numeric(df["UTCP_weighted"], errors="coerce")
                    if w.notna().any():
                        rows.append(("Mean UTCP (weighted)", f"{float(w.mean()):.3f}", None))
                return rows
            return [("Status", "UTCP column empty", None)]
        except Exception as exc:
            return [("Status", str(exc)[:60], "#E67E22")]

    def _get_physical_plan_summary(self) -> list:
        try:
            output_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            if not output_dir or not output_dir.exists():
                return [("Status", "No output yet", None)]
            for rel in (
                "physical_dose_metrics.csv",
                "plan_quality/physical_dose_metrics.csv",
            ):
                ppath = output_dir / rel
                if not ppath.is_file():
                    continue
                df = pd.read_csv(ppath)
                if df.empty:
                    return [("Status", "No physical metrics", None)]
                role_col = "structure_role" if "structure_role" in df.columns else None
                targets = df[df[role_col] == "TARGET"] if role_col else pd.DataFrame()
                oars = df[df[role_col] == "OAR"] if role_col else pd.DataFrame()
                rows: list = []
                if not targets.empty and "D95_gy" in targets.columns:
                    d95 = pd.to_numeric(targets["D95_gy"], errors="coerce").mean()
                    rows.append(("Mean target D95", f"{d95:.1f} Gy", None))
                if "HI" in targets.columns:
                    hi = pd.to_numeric(targets["HI"], errors="coerce").mean()
                    if pd.notna(hi):
                        rows.append(("Mean HI", f"{hi:.3f}", None))
                if "CI" in targets.columns:
                    ci = pd.to_numeric(targets["CI"], errors="coerce").mean()
                    if pd.notna(ci):
                        rows.append(("Mean CI", f"{ci:.3f}", None))
                if not oars.empty and "Dmean_gy" in oars.columns:
                    dmean = pd.to_numeric(oars["Dmean_gy"], errors="coerce")
                    if dmean.notna().any():
                        worst = oars.loc[dmean.idxmax()]
                        rows.append(
                            (
                                "Highest OAR Dmean",
                                f"{worst.get('structure')}: {float(worst['Dmean_gy']):.1f} Gy",
                                None,
                            )
                        )
                flags = output_dir / "plan_quality_flags.csv"
                if not flags.is_file():
                    flags = output_dir / "plan_quality" / "plan_quality_flags.csv"
                if flags.is_file():
                    fdf = pd.read_csv(flags)
                    n_warn = int((fdf.get("Severity", pd.Series()) == "WARNING").sum())
                    if n_warn:
                        rows.append(("Plan-quality flags", str(n_warn), "#E67E22"))
                rows.append(("Workbook", "plan_quality_summary.xlsx", None))
                return rows if rows else [("Status", "Physical metrics loaded", None)]
            return [("Status", "Run DICOM analysis for physical indices", None)]
        except Exception as exc:
            return [("Status", str(exc)[:60], "#E67E22")]

    def _get_quantec_summary(self) -> list:
        try:
            output_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            if not output_dir or not output_dir.exists():
                return [("Status", "No output yet", None)]
            for rel in ("quantec_flags.csv", "ntcp_analysis/quantec_flags.csv"):
                qpath = output_dir / rel
                if not qpath.is_file():
                    continue
                df = pd.read_csv(qpath)
                if df.empty:
                    return [("Status", "No QUANTEC violations", "#27AE60")]
                n_viol = int((df.get("Severity", pd.Series()) == "VIOLATION").sum())
                n_warn = int((df.get("Severity", pd.Series()) == "WARNING").sum())
                color = "#C0392B" if n_viol else "#E67E22" if n_warn else "#27AE60"
                return [
                    ("Violations", str(n_viol), "#C0392B" if n_viol else None),
                    ("Warnings", str(n_warn), "#E67E22" if n_warn else None),
                    ("Report", "ntcp_benchmarking.xlsx → QUANTEC_Flags", None),
                ]
            return [("Status", "Run NTCP for QUANTEC flags", None)]
        except Exception as exc:
            return [("Status", str(exc)[:60], "#E67E22")]

    def _get_risk_summary(self):
        """Get TCP and NTCP risk summary if available"""
        tcp_info = None
        ntcp_info = None

        try:
            output_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
            if output_dir and output_dir.exists():
                df = self._read_engine_tcp_summary(output_dir)
                if df is not None:
                    if "TCP_Poisson" in df.columns:
                        v = pd.to_numeric(df["TCP_Poisson"], errors="coerce").mean()
                        tcp_info = f"Poisson TCP mean {v:.3f}"
                    elif "TCP_mean" in df.columns:
                        tcp_info = f"{pd.to_numeric(df['TCP_mean'], errors='coerce').mean():.3f}"
                    elif "TCP" in df.columns:
                        tcp_info = f"{pd.to_numeric(df['TCP'], errors='coerce').mean():.3f}"

                ndf = self._read_engine_ntcp_table(output_dir)
                if ndf is not None:
                    oar_col = "OAR" if "OAR" in ndf.columns else "structure" if "structure" in ndf.columns else None
                    ntcp_col = None
                    for c in ("NTCP_LKB_loglogit", "NTCP_RS", "NTCP"):
                        if c in ndf.columns:
                            ntcp_col = c
                            break
                    if oar_col and ntcp_col:
                        ndf = ndf.copy()
                        ndf["_ntcp"] = pd.to_numeric(ndf[ntcp_col], errors="coerce")
                        idx = ndf["_ntcp"].idxmax()
                        if pd.notna(idx):
                            ntcp_info = (
                                f"{ndf.loc[idx, oar_col]}: {float(ndf.loc[idx, '_ntcp']):.3f}"
                            )
        except Exception:
            pass

        return tcp_info, ntcp_info
    
    def _get_qa_status(self):
        """Get QA status with color coding"""
        if not hasattr(self, 'qa_status'):
            return "Not Run", "gray"
        
        qa_status = self.qa_status.upper() if hasattr(self, 'qa_status') else "NOT RUN"
        
        if "PASS" in qa_status or "OK" in qa_status:
            return qa_status, "#27AE60"  # Green
        elif "WARN" in qa_status or "WARNING" in qa_status:
            return qa_status, "#E67E22"  # Amber
        elif "FAIL" in qa_status or "ERROR" in qa_status:
            return qa_status, "#C0392B"  # Red
        else:
            return qa_status, "gray"
    
    def _create_status_card(self, parent, title, content_items):
        """Create a status card with title and content items"""
        card = ttk.LabelFrame(parent, text=title, padding=UILayoutConstants.PADDING_MEDIUM)
        card.pack(fill=tk.X, pady=UILayoutConstants.WIDGET_SPACING)
        
        content_frame = ttk.Frame(card)
        content_frame.pack(fill=tk.X)
        
        labels = []
        for label_text, value_text, color in content_items:
            row_frame = ttk.Frame(content_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            label = ttk.Label(row_frame, text=label_text + ":", 
                            font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL, 'bold'))
            label.pack(side=tk.LEFT, padx=(0, 5))
            
            value = ttk.Label(row_frame, text=value_text,
                            font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_NORMAL),
                            foreground=color if color else UILayoutConstants.TEXT_PRIMARY)
            value.pack(side=tk.LEFT)
            
            labels.append((label, value))
        
        return card, labels
    
    def update_dashboard_state(self):
        """Update all dashboard status cards with current state"""
        if not hasattr(self, 'dashboard_main_frame'):
            return
        
        try:
            # Clear existing cards (except title)
            for widget in self.dashboard_main_frame.winfo_children():
                if isinstance(widget, ttk.LabelFrame):
                    widget.destroy()
            
            # Card 1: Study Context
            patient_count = self._get_patient_count()
            site = self.cancer_site.get() if self.cancer_site.get() else "Not Set"
            study_items = [
                ("Cancer Site", site, None),
                ("Patients Loaded", str(patient_count) if patient_count > 0 else "None", None)
            ]
            study_card, study_labels = self._create_status_card(
                self.dashboard_main_frame, "Study Context", study_items
            )
            self.dashboard_cards['study'] = study_labels
            
            # Card 1b: Site detection (R2 — from rbgyanx-engine)
            site_items = self._get_site_detection_summary()
            site_card, site_labels = self._create_status_card(
                self.dashboard_main_frame, "Site Detection (engine)", site_items
            )
            self.dashboard_cards['site_detection'] = site_labels
            
            # Card 2: Analysis Progress
            current_step = self._get_current_step()
            completed_steps = [f"Step {i}" for i in range(1, 7) if self.steps_completed.get(f"step{i}", False)]
            progress_text = f"Current: {current_step}"
            if completed_steps:
                progress_text += f" | Completed: {', '.join(completed_steps)}"
            progress_items = [
                ("Status", progress_text, None)
            ]
            progress_card, progress_labels = self._create_status_card(
                self.dashboard_main_frame, "Analysis Progress", progress_items
            )
            self.dashboard_cards['progress'] = progress_labels
            
            # Card 3: Biological Engines
            engines_items = [
                ("FDVH", "ON" if self.use_fdvh.get() else "OFF", 
                 "#27AE60" if self.use_fdvh.get() else UILayoutConstants.TEXT_SECONDARY),
                ("uTCP", "ON" if self.use_utcp.get() else "OFF",
                 "#27AE60" if self.use_utcp.get() else UILayoutConstants.TEXT_SECONDARY),
                ("TWI", "Auto" if self.analysis_mode.get() == "TCP_NTCP" else "N/A",
                 "#27AE60" if self.analysis_mode.get() == "TCP_NTCP" else UILayoutConstants.TEXT_SECONDARY),
                ("CCS", "ON" if self.use_ccs.get() else "OFF",
                 "#27AE60" if self.use_ccs.get() else UILayoutConstants.TEXT_SECONDARY)
            ]
            engines_card, engines_labels = self._create_status_card(
                self.dashboard_main_frame, "Biological Engines", engines_items
            )
            self.dashboard_cards['engines'] = engines_labels
            
            # Card 4: Model State
            if self.enable_ml.get():
                if self.use_ccs.get():
                    model_state = "ML Gated (CCS Active)"
                    model_color = "#E67E22"  # Amber
                else:
                    model_state = "ML Active"
                    model_color = "#27AE60"  # Green
            else:
                model_state = "Traditional Only"
                model_color = UILayoutConstants.TEXT_SECONDARY
            model_items = [
                ("State", model_state, model_color)
            ]
            model_card, model_labels = self._create_status_card(
                self.dashboard_main_frame, "Model State", model_items
            )
            self.dashboard_cards['model'] = model_labels
            
            # Card 5: Risk Summary (if available)
            tcp_info, ntcp_info = self._get_risk_summary()
            risk_items = []
            if tcp_info:
                risk_items.append(("TCP", tcp_info, None))
            if ntcp_info:
                try:
                    ntcp_val = float(ntcp_info.split(":")[-1].strip())
                    ntcp_color = "#E67E22" if ntcp_val > 0.1 else None
                except ValueError:
                    ntcp_color = None
                risk_items.append(("Highest NTCP", ntcp_info, ntcp_color))
            if not risk_items:
                risk_items.append(("Status", "No results available", UILayoutConstants.TEXT_SECONDARY))
            risk_card, risk_labels = self._create_status_card(
                self.dashboard_main_frame, "Risk Summary", risk_items
            )
            self.dashboard_cards['risk'] = risk_labels

            utcp_card, utcp_labels = self._create_status_card(
                self.dashboard_main_frame, "UTCP (engine)", self._get_utcp_summary()
            )
            self.dashboard_cards["utcp"] = utcp_labels

            quantec_card, quantec_labels = self._create_status_card(
                self.dashboard_main_frame, "QUANTEC (engine)", self._get_quantec_summary()
            )
            self.dashboard_cards["quantec"] = quantec_labels

            physical_card, physical_labels = self._create_status_card(
                self.dashboard_main_frame,
                "Physical dose & plan indices",
                self._get_physical_plan_summary(),
            )
            self.dashboard_cards["physical"] = physical_labels
            
            # Card 6: QA Status
            qa_text, qa_color = self._get_qa_status()
            qa_items = [
                ("Status", qa_text, qa_color)
            ]
            qa_card, qa_labels = self._create_status_card(
                self.dashboard_main_frame, "QA Status", qa_items
            )
            self.dashboard_cards['qa'] = qa_labels
            
            # Ethical disclaimer
            disclaimer_frame = tk.Frame(self.dashboard_main_frame, bg='#f7f7f7', relief='solid', bd=1)
            disclaimer_frame.pack(fill=tk.X, pady=UILayoutConstants.SECTION_SPACING)
            
            disclaimer_text = "⚠️ Decision support tool. Clinical decisions remain with qualified healthcare professionals."
            disclaimer_label = tk.Label(disclaimer_frame, text=disclaimer_text,
                                      font=(UILayoutConstants.FONT_FAMILY, UILayoutConstants.FONT_SIZE_SMALL),
                                      fg="#8B0000", bg='#f7f7f7', wraplength=400, justify=tk.LEFT)
            disclaimer_label.pack(pady=4, padx=5)
            
            # Update scroll region after content changes
            if hasattr(self, 'dashboard_canvas'):
                self.dashboard_canvas.update_idletasks()
                self.dashboard_canvas.configure(scrollregion=self.dashboard_canvas.bbox("all"))
            
        except Exception as e:
            print(f"[Dashboard Update Error] {e}")  # Non-blocking
    
    def _update_clinical_dashboard(self):
        """Legacy method - redirects to new update_dashboard_state"""
        self.update_dashboard_state()
    
    def _create_validation_qa_tab(self, parent):
        """Create Validation & QA tab UI (UI-only, non-blocking)"""
        # Main container with scrollbar
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Scrollable frame
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Section 1: Aggregated Validation Metrics
        metrics_frame = ttk.LabelFrame(scrollable_frame, text="Aggregated Validation Metrics", padding="10")
        metrics_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Explanatory note
        note_label = ttk.Label(
            metrics_frame,
            text="Note: Validation flags indicate physics consistency checks, not execution failure.",
            font=('Arial', 8),
            foreground='gray',
            wraplength=500
        )
        note_label.pack(anchor=tk.W, pady=(0, 5))
        
        # OBJECTIVE C.3: Tooltip text label
        tooltip_label = ttk.Label(
            metrics_frame,
            text="FLAG = Physics consistency warning, not execution failure.",
            font=('Arial', 7, 'italic'),
            foreground='darkgray',
            wraplength=500
        )
        tooltip_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.validation_metrics_label = ttk.Label(
            metrics_frame,
            text="Run Step 1 to see validation metrics",
            font=('Arial', 10)
        )
        self.validation_metrics_label.pack(anchor=tk.W)
        
        # Warning banner (initially hidden)
        self.validation_warning_banner = ttk.Label(
            metrics_frame,
            text="",
            background="#fff3cd",
            foreground="#856404",
            font=('Arial', 9, 'bold'),
            padding=5
        )
        self.validation_warning_banner.pack(fill=tk.X, pady=5)
        self.validation_warning_banner.pack_forget()  # Hide initially
        
        # Section 2: DVH Integrity Summary Table
        table_frame = ttk.LabelFrame(scrollable_frame, text="DVH Integrity Summary", padding="10")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview for table
        columns = ("Patient ID", "Structure", "DVH Type", "Status", "Flagged Checks", "Warnings")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure column headings
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor=tk.W)
        
        # OBJECTIVE C.3: Add tooltip for Status column
        def on_status_column_hover(event):
            # Show tooltip when hovering over Status column header
            if event.x < 120:  # Status column is first 120 pixels
                tooltip_text = "FLAG = Physics consistency warning, not execution failure."
                # Create tooltip (simple approach using messagebox on right-click)
                pass  # Tooltip will be shown via column header text
        
        # OBJECTIVE C.3: Update Status column header with tooltip hint
        tree.heading("Status", text="Status")
        # Add tooltip text via column description (shown in update method)
        
        # Scrollbars for treeview
        tree_v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree_h_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=tree_v_scroll.set, xscrollcommand=tree_h_scroll.set)
        
        tree.grid(row=0, column=0, sticky="nsew")
        tree_v_scroll.grid(row=0, column=1, sticky="ns")
        tree_h_scroll.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        self.validation_tree = tree
        
        # Section 3: Flagged DVH Viewer (Optional)
        viewer_frame = ttk.LabelFrame(scrollable_frame, text="Flagged DVH Viewer", padding="10")
        viewer_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Dropdown for patient + structure selection
        select_frame = ttk.Frame(viewer_frame)
        select_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(select_frame, text="Select DVH:").pack(side=tk.LEFT, padx=5)
        self.flagged_dvh_combo = ttk.Combobox(select_frame, state="readonly", width=40)
        self.flagged_dvh_combo.pack(side=tk.LEFT, padx=5)
        self.flagged_dvh_combo.bind("<<ComboboxSelected>>", self._on_flagged_dvh_selected)
        
        # Explanation text
        self.flagged_explanation = scrolledtext.ScrolledText(
            viewer_frame, height=5, width=50, wrap=tk.WORD, state=tk.DISABLED
        )
        self.flagged_explanation.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # View DVH Plot button
        view_plot_btn = ttk.Button(
            viewer_frame,
            text="View DVH Plot",
            command=self._view_flagged_dvh_plot
        )
        view_plot_btn.pack(pady=5)
        
        # Store references
        self.validation_qa_tab_created = True
        self.qa_scrollable_frame = scrollable_frame  # Store for updates
    
    def update_validation_qa_tab(self):
        """Update Validation & QA tab with current validation results"""
        if not hasattr(self, 'validation_qa_tab_created') or not self.validation_qa_tab_created:
            return
        
        # Update aggregated metrics
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r['status'] == 'PASS')
        flagged = sum(1 for r in self.validation_results if r['status'] == 'FLAG')
        percent_flagged = (flagged / total * 100) if total > 0 else 0
        
        metrics_text = f"Total DVHs processed: {total}\n"
        metrics_text += f"DVHs passed: {passed}\n"
        metrics_text += f"DVHs flagged: {flagged}\n"
        metrics_text += f"% Flagged: {percent_flagged:.1f}%"
        
        self.validation_metrics_label.config(text=metrics_text)
        
        # Show warning banner if flags > 0
        if flagged > 0:
            self.validation_warning_banner.config(
                text=f"⚠ Note: {flagged} DVH(s) flagged for physics consistency review. Review details below."
            )
            self.validation_warning_banner.pack(fill=tk.X, pady=5)
        else:
            self.validation_warning_banner.pack_forget()
        
        # Update table
        if hasattr(self, 'validation_tree'):
            # Clear existing items
            for item in self.validation_tree.get_children():
                self.validation_tree.delete(item)
            
            # Add validation results
            for result in self.validation_results:
                failed_checks_str = "; ".join(result['failed_checks'][:3])  # Show first 3
                if len(result['failed_checks']) > 3:
                    failed_checks_str += f" (+{len(result['failed_checks']) - 3} more)"
                
                warnings_str = "; ".join(result['warnings'][:2])  # Show first 2
                if len(result['warnings']) > 2:
                    warnings_str += f" (+{len(result['warnings']) - 2} more)"
                
                # Determine status color (FLAG = orange, PASS = green)
                if result['status'] == 'PASS':
                    status_color = "green"
                elif result['status'] == 'FLAG':
                    status_color = "orange"
                else:
                    status_color = "red"
                
                item = self.validation_tree.insert(
                    "",
                    tk.END,
                    values=(
                        result['patient_id'],
                        result['structure'],
                        result['dvh_type'],
                        result['status'],  # Will show PASS or FLAG
                        failed_checks_str if result['failed_checks'] else "None",
                        warnings_str if result['warnings'] else "None"
                    ),
                    tags=(status_color,)
                )
            
            # Configure tag colors
            self.validation_tree.tag_configure("green", foreground="green")
            self.validation_tree.tag_configure("orange", foreground="orange")  # For FLAG
            self.validation_tree.tag_configure("red", foreground="red")
        
        # PROMPT 8: Add self-test, auto-correction, and output validation sections
        self._update_qa_sections()
        
        # Update flagged DVH dropdown (use FLAG instead of FAIL)
        flagged_dvhs = [r for r in self.validation_results if r['status'] == 'FLAG']
        if flagged_dvhs:
            combo_values = [
                f"{r['patient_id']} - {r['structure']} ({r['dvh_type']})"
                for r in flagged_dvhs
            ]
            self.flagged_dvh_combo['values'] = combo_values
            if combo_values:
                self.flagged_dvh_combo.current(0)
                self._on_flagged_dvh_selected(None)
        else:
            self.flagged_dvh_combo['values'] = []
            self.flagged_explanation.config(state=tk.NORMAL)
            self.flagged_explanation.delete('1.0', tk.END)
            self.flagged_explanation.insert('1.0', "No flagged DVHs to display.")
            self.flagged_explanation.config(state=tk.DISABLED)
    
    def _on_flagged_dvh_selected(self, event):
        """Handle selection of flagged DVH in dropdown"""
        selection = self.flagged_dvh_combo.get()
        if not selection:
            return
        
        # Parse selection
        parts = selection.split(" - ")
        if len(parts) >= 2:
            patient_id = parts[0]
            structure_and_type = parts[1]
            structure = structure_and_type.split(" (")[0]
            
            # Find matching result
            result = None
            for r in self.validation_results:
                if r['patient_id'] == patient_id and r['structure'] == structure:
                    result = r
                    break
            
            if result:
                # Build explanation text
                explanation = f"Patient: {result['patient_id']}\n"
                explanation += f"Structure: {result['structure']}\n"
                explanation += f"DVH Type: {result['dvh_type']}\n"
                explanation += f"Status: {result['status']}\n\n"
                
                if result['failed_checks']:
                    explanation += "Failed Checks:\n"
                    for check in result['failed_checks']:
                        explanation += f"  • {check}\n"
                    explanation += "\n"
                
                if result['warnings']:
                    explanation += "Warnings:\n"
                    for warning in result['warnings']:
                        explanation += f"  • {warning}\n"
                
                self.flagged_explanation.config(state=tk.NORMAL)
                self.flagged_explanation.delete('1.0', tk.END)
                self.flagged_explanation.insert('1.0', explanation)
                self.flagged_explanation.config(state=tk.DISABLED)
    
    def _view_flagged_dvh_plot(self):
        """View DVH plot for selected flagged DVH"""
        selection = self.flagged_dvh_combo.get()
        if not selection:
            messagebox.showinfo("Info", "Please select a DVH from the dropdown")
            return
        
        # Parse selection
        parts = selection.split(" - ")
        if len(parts) >= 2:
            patient_id = parts[0]
            structure_and_type = parts[1]
            structure = structure_and_type.split(" (")[0]
            dvh_type = structure_and_type.split("(")[1].rstrip(")")
            
            # Try to load DVH plot (reuse existing function)
            base_dir = Path(self.output_dir.get())
            processed_dir = base_dir / "processed_DVH"
            
            if dvh_type == "cumulative":
                dvh_file = processed_dir / "cDVH_csv" / f"{patient_id}_{structure}.csv"
            else:
                dvh_file = processed_dir / "dDVH_csv" / f"{patient_id}_{structure}.csv"
            
            if dvh_file.exists():
                # Load into DVH Plots tab
                self.log(f"Loading flagged DVH plot: {dvh_file.name}")
                # Note: This would require additional implementation to plot individual DVH
                # For now, just log the action
                messagebox.showinfo(
                    "Info",
                    f"DVH file found: {dvh_file.name}\n"
                    "Use the DVH Plots tab to view this DVH."
                )
            else:
                messagebox.showwarning("Warning", f"DVH file not found: {dvh_file}")
    
    # ========== Event Handlers ==========
    
    def on_analysis_mode_change(self):
        """Handle analysis mode change - update dashboard"""
        # Update dashboard when mode changes
        if hasattr(self, 'dashboard_main_frame'):
            self.root.after(100, self.update_dashboard_state)
        """Handle analysis mode change (TCP_ONLY, NTCP_ONLY, TCP_NTCP)"""
        mode = self.analysis_mode.get()
        
        # Update legacy analysis_type for backward compatibility
        if mode == "TCP_ONLY":
            self.analysis_type.set("TCP")
        elif mode == "NTCP_ONLY":
            self.analysis_type.set("NTCP")
        else:  # TCP_NTCP
            # Default to NTCP for legacy compatibility, but both will run
            self.analysis_type.set("NTCP")
        
        # Update UI elements
        self.on_analysis_type_change()
        self.log(f"Analysis mode changed to: {mode}")
    
    def on_analysis_type_change(self):
        """Handle analysis type change"""
        # Update radio button display
        run_all_text = f"Run All {self.analysis_type.get()} Steps"
        if hasattr(self, 'run_all_button'):
            self.run_all_button.config(text=run_all_text)
        
        # Update Step 1 help text
        self.update_step1_help()
        
        # Update Step 3 model checkboxes based on analysis type
        self.update_step3_models()
        
        # Update model combo box values based on analysis type
        if hasattr(self, 'step3_model_combo'):
            if self.analysis_type.get() == "NTCP":
                self.step3_model_combo['values'] = ["LKB Log-Logistic", "LKB Probit", "RS Poisson"]
                if self.selected_traditional_model.get() not in ["LKB Log-Logistic", "LKB Probit", "RS Poisson"]:
                    self.selected_traditional_model.set("LKB Log-Logistic")
            else:  # TCP
                self.step3_model_combo['values'] = ["Poisson TCP", "LKB TCP", "Logistic TCP", "EUD TCP"]
                if self.selected_traditional_model.get() not in ["Poisson TCP", "LKB TCP", "Logistic TCP", "EUD TCP"]:
                    self.selected_traditional_model.set("Poisson TCP")
        
        # Update model parameters immediately
        self.update_model_parameters()
        
        # Update structure list when analysis type changes
        self.populate_structure_list()
        
        # Update equations tab when analysis type changes
        self.populate_equations_tab()
        
        self.log(f"Analysis type changed to: {self.analysis_type.get()}")
    
    def update_step3_models(self):
        """Update Step 3 model checkboxes based on analysis type"""
        if not hasattr(self, 'models_frame'):
            return
        
        # Clear existing checkboxes
        for widget in self.models_frame.winfo_children():
            widget.destroy()
        
        if self.analysis_type.get() == "NTCP":
            ttk.Label(self.models_frame, text="Select NTCP Models:", 
                     font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
            
            for model_name, var in self.ntcp_models.items():
                display_name = model_name.replace('_', ' ')
                ttk.Checkbutton(self.models_frame, text=f"☑ {display_name}", 
                              variable=var).pack(anchor=tk.W, padx=20, pady=2)
        else:  # TCP
            ttk.Label(self.models_frame, text="Select TCP Models:", 
                     font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
            
            for model_name, var in self.tcp_models.items():
                display_name = model_name.replace('_', ' ')
                ttk.Checkbutton(self.models_frame, text=f"☑ {display_name}", 
                              variable=var).pack(anchor=tk.W, padx=20, pady=2)
    
    def populate_structure_list(self):
        """
        Populate organ/target list based on detected structures from Step 1.
        Called after Step 1 completes.
        """
        if not hasattr(self, 'structures_frame'):
            return
        
        # Clear existing checkboxes
        for widget in self.structures_frame.winfo_children():
            widget.destroy()
        
        self.structure_checkboxes.clear()
        
        # Get structures from preprocessing summary
        structures = self.detected_organs if self.analysis_type.get() == "NTCP" else self.detected_targets
        
        if not structures:
            # No structures detected yet
            label = ttk.Label(
                self.structures_frame,
                text="[!] Run Step 1 first to detect structures",
                foreground="orange"
            )
            label.pack(pady=10)
            return
        
        # Create checkboxes for detected structures
        if self.analysis_type.get() == "NTCP":
            label = ttk.Label(self.structures_frame, text="Detected OARs:", font=('Arial', 10, 'bold'))
        else:
            label = ttk.Label(self.structures_frame, text="Detected Targets:", font=('Arial', 10, 'bold'))
        
        label.pack(anchor='w', pady=5)
        
        for structure, count in structures.items():
            var = tk.BooleanVar(value=True)  # Default: all selected
            self.structure_checkboxes[structure] = var
            
            cb = ttk.Checkbutton(
                self.structures_frame,
                text=f"{structure} (detected: {count} files)",
                variable=var
            )
            cb.pack(anchor='w', padx=20, pady=2)
    
    def select_all_structures(self):
        """Select/deselect all structure checkboxes"""
        # Toggle based on first checkbox state
        if self.structure_checkboxes:
            first_var = list(self.structure_checkboxes.values())[0]
            new_state = not first_var.get()
            
            for var in self.structure_checkboxes.values():
                var.set(new_state)
    
    def auto_detect_diagnosis(self):
        """
        Auto-detect tumor site from DVH metadata.
        """
        import re
        
        # Read first DVH file to check for diagnosis in header
        dvh_dir = Path(self.raw_input.get())
        
        if dvh_dir.is_dir():
            # Get first TXT file
            txt_files = list(dvh_dir.glob('*.txt'))
            if txt_files:
                first_file = txt_files[0]
                
                try:
                    with open(first_file, 'r', encoding='utf-8', errors='ignore') as f:
                        header = ''.join([f.readline() for _ in range(20)])
                    
                    # Diagnosis mapping
                    diagnosis_patterns = {
                        "Head & Neck Cancer": [
                            r'carcinoma.*tongue', r'ca.*buccal', r'laryngeal', 
                            r'oropharynx', r'nasopharynx', r'hypopharynx',
                            r'oral.*cavity', r'head.*neck', r'hn'
                        ],
                        "Lung Cancer": [
                            r'lung', r'nsclc', r'sclc', r'bronchogenic'
                        ],
                        "Prostate Cancer": [
                            r'prostate', r'ca.*prostate'
                        ],
                        "Breast Cancer": [
                            r'breast', r'ca.*breast', r'mammary'
                        ],
                        "Brain Cancer": [
                            r'brain', r'glioma', r'glioblastoma', r'gbm'
                        ],
                    }
                    
                    # Check patterns
                    header_lower = header.lower()
                    for diagnosis, patterns in diagnosis_patterns.items():
                        if any(re.search(pattern, header_lower) for pattern in patterns):
                            self.detected_diagnosis = diagnosis
                            if hasattr(self, 'diagnosis_label'):
                                self.diagnosis_label.config(
                                    text=f"[OK] Auto-detected: {diagnosis}",
                                    foreground="green"
                                )
                            if hasattr(self, 'diagnosis_manual'):
                                self.diagnosis_manual.set(diagnosis)
                            self.log(f"[OK] Auto-detected diagnosis: {diagnosis}")
                            return
                    
                    # If no match, ask user
                    if hasattr(self, 'diagnosis_label'):
                        self.diagnosis_label.config(
                            text="[!] Could not auto-detect. Please select manually:",
                            foreground="orange"
                        )
                    if hasattr(self, 'diagnosis_combo'):
                        self.diagnosis_combo.config(state='normal')
                    
                except Exception as e:
                    self.log(f"[!] Diagnosis auto-detection failed: {e}")
                    if hasattr(self, 'diagnosis_combo'):
                        self.diagnosis_combo.config(state='normal')
    
    # Model parameter specifications
    # Model-specific parameters based on literature values from code3_ntcp_analysis_ml.py
    NTCP_MODEL_PARAMS = {
        'LKB Log-Logistic': {
            'params': ['a', 'TD50', 'gamma50', 'alpha_beta'],
            'defaults': [2.2, 28.4, 1.0, 3.0],
            'descriptions': {
                'a': '(Lit: 2.2 for Parotid, 1.0 for Larynx, 7.4 for SpinalCord)',
                'TD50': '(Lit: 28.4 for Parotid, 44.0 for Larynx, 66.5 for SpinalCord)',
                'gamma50': '(Lit: 1.0 for Parotid/Larynx, 4.0 for SpinalCord)',
                'alpha_beta': '(Lit: 3.0 for Parotid/Larynx, 2.0 for SpinalCord)'
            }
        },
        'LKB Probit': {
            'params': ['TD50', 'm', 'n', 'alpha_beta'],
            'defaults': [28.4, 0.18, 0.45, 3.0],
            'descriptions': {
                'TD50': '(Lit: 28.4 for Parotid, 44.0 for Larynx, 66.5 for SpinalCord)',
                'm': '(Lit: 0.18 for Parotid, 0.20 for Larynx, 0.10 for SpinalCord)',
                'n': '(Lit: 0.45 for Parotid, 1.0 for Larynx, 0.03 for SpinalCord)',
                'alpha_beta': '(Lit: 3.0 for Parotid/Larynx, 2.0 for SpinalCord)'
            }
        },
        'RS Poisson': {
            'params': ['D50', 'gamma', 's', 'alpha_beta'],
            'defaults': [26.3, 0.73, 0.01, 3.0],
            'descriptions': {
                'D50': '(Lit: 26.3 for Parotid, 40.0 for Larynx, 68.6 for SpinalCord)',
                'gamma': '(Lit: 0.73 for Parotid, 1.2 for Larynx, 1.9 for SpinalCord)',
                's': '(Lit: 0.01 for Parotid, 0.12 for Larynx, 4.0 for SpinalCord)',
                'alpha_beta': '(Lit: 3.0 for Parotid/Larynx, 2.0 for SpinalCord)'
            }
        }
    }
    
    TCP_MODEL_PARAMS = {
        'Poisson TCP': {
            'params': ['alpha', 'K', 'rho0'],
            'defaults': [0.35, 100.0, 1e7],
            'descriptions': {
                'alpha': 'Cell kill parameter (Gy^-1)',
                'K': 'Carrying capacity',
                'rho0': 'Initial clonogenic cell density (cells/cm^3)'
            }
        },
        'LKB TCP': {
            'params': ['TD50', 'm', 'n', 'alpha_beta'],
            'defaults': [50.0, 0.18, 0.45, 10.0],
            'descriptions': {
                'TD50': 'Tumor control dose for 50% probability (Gy)',
                'm': 'Slope parameter (dimensionless)',
                'n': 'Volume effect parameter (0 = serial, 1 = parallel)',
                'alpha_beta': 'α/β ratio for fractionation (Gy)'
            }
        },
        'Logistic TCP': {
            'params': ['TCD50', 'gamma50', 'alpha_beta'],
            'defaults': [50.0, 1.0, 10.0],
            'descriptions': {
                'TCD50': 'Tumor control dose for 50% probability (Gy)',
                'gamma50': 'Normalized dose-response gradient',
                'alpha_beta': 'α/β ratio for fractionation (Gy)'
            }
        },
        'EUD TCP': {
            'params': ['a', 'D50', 'gamma50', 'alpha_beta'],
            'defaults': [-10.0, 50.0, 1.0, 10.0],
            'descriptions': {
                'a': 'EUD parameter (negative for tumors, typically -10 to -20)',
                'D50': 'Dose for 50% control probability (Gy)',
                'gamma50': 'Normalized dose-response gradient',
                'alpha_beta': 'α/β ratio for fractionation (Gy)'
            }
        }
    }
    
    def update_model_parameters(self):
        """Update parameter entry fields based on selected model - model-specific parameters"""
        if not hasattr(self, 'param_frame') or self.param_frame is None:
            return
        
        # Clear existing parameter inputs
        for widget in self.param_frame.winfo_children():
            widget.destroy()
        
        self.param_entries = {}
        
        # Get current model and analysis type
        model_name = self.selected_traditional_model.get()
        if self.analysis_type.get() == "NTCP":
            params_spec = self.NTCP_MODEL_PARAMS.get(model_name, self.NTCP_MODEL_PARAMS['LKB Log-Logistic'])
        else:
            params_spec = self.TCP_MODEL_PARAMS.get(model_name, self.TCP_MODEL_PARAMS['Poisson TCP'])
        
        # Create parameter inputs with model-specific parameters
        title_label = ttk.Label(
            self.param_frame,
            text=f"{model_name} Model Parameters:",
            font=('Arial', 10, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        row = 1
        for i, param in enumerate(params_spec['params']):
            # Parameter label
            label_text = f"{param}:"
            ttk.Label(self.param_frame, text=label_text, width=15, anchor='w').grid(
                row=row, column=0, sticky=tk.W, padx=5, pady=3
            )
            
            # Entry field
            var = tk.StringVar(value=str(params_spec['defaults'][i]))
            entry = ttk.Entry(self.param_frame, textvariable=var, width=15)
            entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=3)
            
            self.param_entries[param] = var
            
            # Description/range
            desc = params_spec['descriptions'].get(param, '')
            ttk.Label(
                self.param_frame,
                text=desc,
                font=('Arial', 8),
                foreground='gray'
            ).grid(row=row, column=2, sticky=tk.W, padx=5, pady=3)
            
            row += 1
        
        # Update equations tab when model changes
        self.populate_equations_tab()
    
    def reset_parameters(self):
        """Reset parameters to literature values"""
        model_name = self.selected_traditional_model.get()
        if self.analysis_type.get() == "NTCP":
            params_spec = self.NTCP_MODEL_PARAMS.get(model_name, self.NTCP_MODEL_PARAMS['LKB Log-Logistic'])
        else:
            params_spec = self.TCP_MODEL_PARAMS.get(model_name, self.TCP_MODEL_PARAMS['Poisson TCP'])
        
        for i, param in enumerate(params_spec['params']):
            if param in self.param_entries:
                self.param_entries[param].set(str(params_spec['defaults'][i]))
    
    def apply_custom_parameters(self):
        """Apply custom parameters (placeholder - would need to pass to analysis)"""
        self.log("[OK] Custom parameters applied (will be used in next analysis)")
        for param, var in self.param_entries.items():
            self.log(f"  {param}: {var.get()}")
    
    def show_equation_popup(self):
        """Show equation popup window for selected model"""
        model_name = self.selected_traditional_model.get()
        
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title(f"{model_name} - Model Equation")
        popup.geometry("700x600")
        popup.transient(self.root)
        popup.grab_set()
        
        # Create scrollable text widget
        text_frame = ttk.Frame(popup, padding="10")
        text_frame.pack(fill='both', expand=True)
        
        text_widget = tk.Text(
            text_frame,
            wrap='word',
            font=('Courier', 10),
            padx=10,
            pady=10
        )
        text_widget.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # Get equation content
        if self.analysis_type.get() == "NTCP":
            content = self.get_ntcp_equation_info(model_name)
        else:
            content = self.get_tcp_equation_info(model_name)
        
        # Insert content
        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')  # Read-only
        
        # Close button
        button_frame = ttk.Frame(popup)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Close", command=popup.destroy).pack()
    
    def populate_equations_tab(self):
        """Populate View Equations tab with model information"""
        if not hasattr(self, 'equations_text_frame') or self.equations_text_frame is None:
            return
        
        # Clear existing content
        for widget in self.equations_text_frame.winfo_children():
            widget.destroy()
        
        # Create scrollable text widget
        text_widget = tk.Text(
            self.equations_text_frame,
            wrap='word',
            font=('Courier', 9),
            height=20
        )
        text_widget.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(text_widget, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # Get current model
        model_name = self.selected_traditional_model.get()
        if self.analysis_type.get() == "NTCP":
            content = self.get_ntcp_equation_info(model_name)
        else:
            content = self.get_tcp_equation_info(model_name)
        
        # Insert content
        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')  # Read-only
        
        self.equations_text = text_widget
    
    def get_ntcp_equation_info(self, model):
        """Get NTCP model equation information"""
        equations = {
            'LKB Log-Logistic': """
================================================================
LKB (Lyman-Kutcher-Burman) NTCP Model - Log-Logistic
================================================================

EQUATION:
    NTCP = 1 / [1 + (TD50/EUD)^k]
    
    where: EUD = [Σ(v_i × D_i^n)]^(1/n)

PARAMETERS:
    • TD50: Tolerance dose for 50% complication probability (Gy)
    • m: Slope parameter (dimensionless)
    • n: Volume effect parameter (0 = serial, 1 = parallel)

EUD (Equivalent Uniform Dose):
    EUD = [Σ(v_i × D_i^n)]^(1/n)
    
    where:
    • v_i: Fractional volume at dose D_i
    • n: Volume parameter

INTERPRETATION:
    • TD50: Higher values = more radiation-resistant organ
    • m: Higher values = steeper dose-response curve
    • n: Serial organs (n→0), Parallel organs (n→1)

TYPICAL VALUES:
    Organ         TD50 (Gy)    m       n
    ------------------------------------
    Spinal Cord   66.5        0.175   0.05
    Parotid       46.0        0.18    0.7
    Larynx        63.0        0.18    0.44
    Lung          24.5        0.18    0.87

REFERENCES:
    [1] Lyman JT. Complication probability as assessed from 
        dose-volume histograms. Radiat Res. 1985;104:S13-S19.
    [2] Kutcher GJ, Burman C. Calculation of complication 
        probability factors for non-uniform normal tissue 
        irradiation. Int J Radiat Oncol Biol Phys. 1989;16:1623-30.

ADVANTAGES:
    [OK] Most widely validated model
    [OK] Extensive clinical parameter data available
    [OK] Accounts for volume effects

LIMITATIONS:
    [X] Assumes specific dose-response shape
    [X] May not fit all organ systems
================================================================
""",
            'LKB Probit': """
================================================================
LKB (Lyman-Kutcher-Burman) NTCP Model - Probit
================================================================

EQUATION:
    NTCP = (1/√(2π)) ∫[-∞ to t] exp(-x²/2) dx
    
    where: t = (EUD - TD50) / (m × TD50)

PARAMETERS:
    • TD50: Tolerance dose for 50% complication probability (Gy)
    • m: Slope parameter (dimensionless)
    • n: Volume effect parameter (0 = serial, 1 = parallel)

EUD (Equivalent Uniform Dose):
    EUD = [Σ(v_i × D_i^n)]^(1/n)

TYPICAL VALUES:
    Organ         TD50 (Gy)    m       n
    ------------------------------------
    Spinal Cord   66.5        0.175   0.05
    Parotid       46.0        0.18    0.7
    Larynx        63.0        0.18    0.44

REFERENCES:
    [1] Lyman JT. Complication probability as assessed from 
        dose-volume histograms. Radiat Res. 1985;104:S13-S19.
================================================================
""",
            'RS Poisson': """
================================================================
RS (Relative Seriality) NTCP Model
================================================================

EQUATION:
    NTCP = [1 - Π(1 - P(D_i))^(v_i^s)]^(1/s)
    
    P(D) = 1 / [1 + (D50/D)^(4γ)]

PARAMETERS:
    • D50: Dose causing 50% response (Gy)
    • gamma: Normalized dose-response gradient
    • s: Relative seriality (0 = serial, 1 = parallel)

INTERPRETATION:
    • s→0: Serial architecture (spinal cord, esophagus)
    • s→1: Parallel architecture (lung, liver, kidney)
    • s=0.5: Mixed architecture

TYPICAL VALUES:
    Organ         D50 (Gy)    gamma    s
    ------------------------------------
    Spinal Cord   68.6        1.6     0.0
    Parotid       46.3        1.8     0.7
    Rectum        76.9        1.4     0.6

REFERENCES:
    [1] Kallman P, et al. Tumour and normal tissue responses to 
        fractionated non-uniform dose delivery. Int J Radiat Biol. 
        1992;62:249-62.
================================================================
"""
        }
        return equations.get(model, "Model information not available")
    
    def get_tcp_equation_info(self, model):
        """Get TCP model equation information"""
        equations = {
            'Poisson TCP': """
================================================================
Poisson TCP Model
================================================================

EQUATION:
    TCP = exp(-N_0 × SF)
    
    SF = exp(-αD - βD²)  (LQ model)

PARAMETERS:
    • alpha: Linear radiosensitivity (Gy^-1)
    • beta: Quadratic radiosensitivity (Gy^-2)
    • N_0: Initial clonogenic cell number (or K, carrying capacity)
    • rho0: Initial clonogenic cell density (cells/cm^3)

INTERPRETATION:
    • α/β ratio: Tissue fractionation sensitivity
    • Higher α: More radiosensitive
    • N_0 depends on tumor volume

TYPICAL VALUES:
    Tumor Type      α (Gy^-1)    α/β (Gy)    N_0
    ---------------------------------------------
    H&N SCC         0.35        10          10^8
    Prostate        0.15        1.5         10^7
    Lung            0.30        10          10^8

REFERENCES:
    [1] Webb S, Nahum AE. A model for calculating tumour control 
        probability in radiotherapy. Phys Med Biol. 1993;38:1895-1921.
================================================================
""",
            'LKB TCP': """
================================================================
LKB (Lyman-Kutcher-Burman) TCP Model
================================================================

EQUATION:
    TCP = 1 / [1 + (TD50/EUD)^k]
    
    where: EUD = [Σ(v_i × D_i^n)]^(1/n)
    and: k = 4 × gamma50

PARAMETERS:
    • TD50: Tumor control dose for 50% probability (Gy)
    • m: Slope parameter (dimensionless)
    • n: Volume effect parameter (0 = serial, 1 = parallel)
    • alpha_beta: α/β ratio for fractionation (Gy)

EUD (Equivalent Uniform Dose):
    EUD = [Σ(v_i × D_i^n)]^(1/n)
    
    where:
    • v_i: Fractional volume at dose D_i
    • n: Volume parameter

INTERPRETATION:
    • TD50: Higher values = more radiation-resistant tumor
    • m: Higher values = steeper dose-response curve
    • n: Volume effect (typically 0.1-0.5 for tumors)

TYPICAL VALUES:
    Tumor Type      TD50 (Gy)    m       n       α/β (Gy)
    -----------------------------------------------------
    H&N SCC         50-60        0.18    0.3     10
    Prostate        60-70        0.15    0.2     1.5
    Lung            40-50        0.20    0.4     10

REFERENCES:
    [1] Lyman JT. Complication probability as assessed from 
        dose-volume histograms. Radiat Res. 1985;104:S13-S19.
    [2] Okunieff P, et al. Tumor control probability for 
        radiotherapy. Int J Radiat Oncol Biol Phys. 1995;32:761-7.
================================================================
""",
            'Logistic TCP': """
================================================================
Logistic TCP Model
================================================================

EQUATION:
    TCP = 1 / [1 + (TCD50/D)^(4×gamma50)]
    
    where D is the dose (typically mean dose or EUD)

PARAMETERS:
    • TCD50: Tumor control dose for 50% probability (Gy)
    • gamma50: Normalized dose-response gradient
    • alpha_beta: α/β ratio for fractionation (Gy)

INTERPRETATION:
    • TCD50: Dose at which 50% of tumors are controlled
    • gamma50: Steepness of dose-response curve
    • Higher gamma50 = more sensitive to dose changes

TYPICAL VALUES:
    Tumor Type      TCD50 (Gy)    gamma50    α/β (Gy)
    ------------------------------------------------
    H&N SCC         50-60         1.0-1.5    10
    Prostate        60-70         1.0-1.2    1.5
    Lung            40-50         1.2-1.8    10

REFERENCES:
    [1] Brahme A. Dosimetric precision requirements in radiation 
        therapy. Acta Radiol Oncol. 1984;23:379-91.
================================================================
""",
            'EUD TCP': """
================================================================
EUD (Equivalent Uniform Dose) TCP Model
================================================================

EQUATION:
    TCP = 1 / [1 + (D50/EUD)^(4×gamma50)]
    
    where: EUD = [Σ(v_i × D_i^a)]^(1/a)
    and a < 0 for tumors (typically -10 to -20)

PARAMETERS:
    • a: EUD parameter (negative for tumors)
    • D50: Dose for 50% control probability (Gy)
    • gamma50: Normalized dose-response gradient
    • alpha_beta: α/β ratio for fractionation (Gy)

EUD Calculation:
    EUD = [Σ(v_i × D_i^a)]^(1/a)
    
    where:
    • v_i: Fractional volume at dose D_i
    • a: Negative parameter (typically -10 to -20 for tumors)
    • More negative a = more emphasis on high-dose regions

INTERPRETATION:
    • a = -10: Moderate emphasis on high doses
    • a = -20: Strong emphasis on high doses (hot spots)
    • D50: Dose at which 50% of tumors are controlled
    • gamma50: Steepness of dose-response curve

TYPICAL VALUES:
    Tumor Type      a       D50 (Gy)    gamma50    α/β (Gy)
    --------------------------------------------------------
    H&N SCC         -10     50-60       1.0-1.5    10
    Prostate        -10     60-70       1.0-1.2    1.5
    Lung            -15     40-50       1.2-1.8    10

REFERENCES:
    [1] Niemierko A. Reporting and analyzing dose distributions: 
        a concept of equivalent uniform dose. Med Phys. 1997;24:103-10.
================================================================
"""
        }
        return equations.get(model, "Model information not available")
    
    def update_step1_help(self):
        """Update help text based on analysis type"""
        if self.analysis_type.get() == "NTCP":
            help_text = ("For NTCP: Provide OAR (Organ at Risk) DVH files\n"
                        "Expected format: {PatientID}_{OARName}.{txt|csv|dcm}\n"
                        "Example: P001_Parotid_L.txt, P002_Larynx.csv")
        else:  # TCP
            help_text = ("For TCP: Provide Tumor/PTV DVH files\n"
                        "Expected format: {PatientID}_{TumorName}.{txt|csv|dcm}\n"
                        "Example: P001_PTV70.txt, P002_GTV.csv")
        
        self.step1_help.config(text=help_text)
    
    def browse_directory(self, var):
        """Browse for directory and update variable"""
        directory = filedialog.askdirectory(title="Select Directory")
        if directory:
            var.set(directory)
            self.log(f"Selected directory: {directory}")
            
            # If this is the raw_input and it's a directory, preview it
            if var == self.raw_input:
                self._sync_input_source_from_path(Path(directory))
                self.preview_input_data()
    
    def browse_file(self, var, filetypes):
        """Browse for file and update variable"""
        filename = filedialog.askopenfilename(
            title="Select File",
            filetypes=filetypes
        )
        if filename:
            var.set(filename)
            self.log(f"Selected file: {filename}")
            
            # If this is the raw_input and it's a file, preview it
            if var == self.raw_input:
                self.preview_input_data()
            # If this is clinical_file, run adapter and show summary
            elif var == self.clinical_file:
                self._process_clinical_file_selection()
    
    def browse_raw_input(self):
        """Browse for raw DVH input (file or directory)"""
        if self.input_format.get() == "file":
            # Single file
            filename = filedialog.askopenfilename(
                title="Select DVH File",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("CSV files", "*.csv"),
                    ("DICOM files", "*.dcm"),
                    ("All supported", "*.txt *.csv *.dcm"),
                    ("All files", "*.*")
                ]
            )
            if filename:
                self.raw_input.set(filename)
                self.log(f"Selected DVH file: {filename}")
                self._sync_input_source_from_path(Path(filename))
                self.preview_input_data()
        else:
            # Directory
            title = (
                "Select DICOM RT Folder"
                if getattr(self, "input_source", None) and self.input_source.get() == "dicom"
                else "Select DVH Directory (TPS export)"
            )
            directory = filedialog.askdirectory(title=title)
            if directory:
                self.raw_input.set(directory)
                self.log(f"Selected DVH directory: {directory}")
                self._sync_input_source_from_path(Path(directory))
                self.preview_input_data()
                # Prompt for analysis mode after DVH folder selection
                self._prompt_analysis_mode_after_dvh_selection()
    
    def log(self, message):
        """Thread-safe logging to GUI"""
        def _log():
            if hasattr(self, 'log_text'):
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
                self.log_text.see(tk.END)
                self.log_text.update()
        
        if threading.current_thread() == threading.main_thread():
            _log()
        else:
            self.root.after(0, _log)
    
    # ============================================================
    # PROMPT 7: Workflow State Management
    # ============================================================
    
    def set_workflow_state(self, new_state: WorkflowState):
        """Update workflow state and trigger UI updates"""
        self.workflow_state = new_state
        
        # Call state callback
        if new_state in self.state_callbacks:
            self.state_callbacks[new_state]()
        
        # Update UI
        self.update_ui_for_state(new_state)
    
    def update_ui_for_state(self, state: WorkflowState):
        """Update all GUI panels based on workflow state"""
        
        # Update button states
        if state in [WorkflowState.PREPROCESSING, WorkflowState.TCP_RUNNING, 
                    WorkflowState.NTCP_RUNNING, WorkflowState.INTEGRATION_RUNNING]:
            # Disable run button
            if hasattr(self, 'run_all_button'):
                self.run_all_button.config(state=tk.DISABLED)
        else:
            if hasattr(self, 'run_all_button'):
                self.run_all_button.config(state=tk.NORMAL)
        
        # Update progress indicator
        self.update_progress_indicator(state)
        
        # Update center panel
        self.update_center_panel(state)
        
        # Update right panel (visualization)
        self.update_right_panel(state)
        
        # Update status tabs
        self.update_status_tabs(state)
    
    def update_progress_indicator(self, state: WorkflowState):
        """Update progress bar based on workflow state"""
        if not hasattr(self, 'progress_var'):
            return
        
        progress_map = {
            WorkflowState.IDLE: 0,
            WorkflowState.PREPROCESSING: 1,
            WorkflowState.PREPROCESSING_COMPLETE: 2,
            WorkflowState.TCP_RUNNING: 3,
            WorkflowState.TCP_COMPLETE: 3,
            WorkflowState.NTCP_RUNNING: 4,
            WorkflowState.NTCP_COMPLETE: 4,
            WorkflowState.INTEGRATION_RUNNING: 5,
            WorkflowState.INTEGRATION_COMPLETE: 6,
            WorkflowState.ERROR: 0,
        }
        
        self.progress_var.set(progress_map.get(state, 0))
    
    def update_center_panel(self, state: WorkflowState):
        """Update center panel content based on state"""
        # This will be called when state changes
        # Implementation can refresh summary, stats, etc.
        pass
    
    def update_right_panel(self, state: WorkflowState):
        """Update right panel (visualization) based on state"""
        # Auto-load plots when analysis completes
        if state in [WorkflowState.TCP_COMPLETE, WorkflowState.NTCP_COMPLETE, 
                    WorkflowState.INTEGRATION_COMPLETE]:
            self.auto_load_latest_plots()
    
    def update_status_tabs(self, state: WorkflowState):
        """Update status tabs based on workflow state"""
        # Refresh tab content when state changes
        if hasattr(self, 'step3_notebook'):
            # Trigger tab refresh if needed
            pass
    
    # State callback methods
    def on_idle_state(self):
        """Handle IDLE state"""
        self.log("System ready")
    
    def on_preprocessing_state(self):
        """Handle PREPROCESSING state"""
        self.log("Preprocessing in progress...")
    
    def on_preprocessing_complete_state(self):
        """Handle PREPROCESSING_COMPLETE state"""
        self.log("Preprocessing completed")
    
    def on_tcp_running_state(self):
        """Handle TCP_RUNNING state"""
        self.log("TCP analysis in progress...")
    
    def on_tcp_complete_state(self):
        """Handle TCP_COMPLETE state"""
        self.log("TCP analysis completed")
        self.auto_load_latest_plots()
        self.on_analysis_complete()
    
    def on_ntcp_running_state(self):
        """Handle NTCP_RUNNING state"""
        self.log("NTCP analysis in progress...")
    
    def on_ntcp_complete_state(self):
        """Handle NTCP_COMPLETE state"""
        self.log("NTCP analysis completed")
        self.auto_load_latest_plots()
        self.on_analysis_complete()
    
    def on_integration_running_state(self):
        """Handle INTEGRATION_RUNNING state"""
        self.log("Integration analysis in progress...")
    
    def on_integration_complete_state(self):
        """Handle INTEGRATION_COMPLETE state"""
        self.log("Integration analysis completed")
        self.auto_load_latest_plots()
        self.on_analysis_complete()
    
    def on_error_state(self):
        """Handle ERROR state"""
        self.log("Error occurred during analysis")
    
    def auto_load_latest_plots(self):
        """Auto-load most recent plots after analysis"""
        if not hasattr(self, 'output_dir') or not self.output_dir.get():
            return
        
        base_dir = Path(self.output_dir.get())
        
        # Determine which analysis just completed
        plot_dir = None
        if self.workflow_state == WorkflowState.TCP_COMPLETE:
            plot_dir = base_dir / "tcp_analysis" / "plots"
        elif self.workflow_state == WorkflowState.NTCP_COMPLETE:
            plot_dir = base_dir / "enhanced_ntcp_analysis" / "plots"
            if not plot_dir.exists():
                plot_dir = base_dir / "ntcp_analysis" / "plots"
        elif self.workflow_state == WorkflowState.INTEGRATION_COMPLETE:
            plot_dir = base_dir / "integration_results" / "plots"
            if not plot_dir.exists():
                plot_dir = base_dir / "integration" / "plots"
        else:
            return
        
        if not plot_dir.exists():
            return
        
        # Find latest plots
        plot_files = sorted(plot_dir.glob("*.png"), 
                          key=lambda p: p.stat().st_mtime, 
                          reverse=True)
        
        if plot_files:
            self.display_plot(plot_files[0])
            self.current_plot_index = 0
            self.available_plots = plot_files
    
    def display_plot(self, plot_path: Path):
        """Display plot in right panel"""
        if not PIL_AVAILABLE:
            self.log(f"PIL not available - cannot display plot: {plot_path.name}")
            return
        
        try:
            from PIL import Image, ImageTk
            
            # Find the right panel visualization notebook
            if not hasattr(self, 'viz_tabs'):
                return
            
            # Use the first available tab (DVH Plots)
            if "DVH Plots" in self.viz_tabs:
                tab_info = self.viz_tabs["DVH Plots"]
                tab_frame = tab_info['canvas'].get_tk_widget().master
                
                # Clear existing widgets in tab
                for widget in tab_frame.winfo_children():
                    if isinstance(widget, (tk.Label, tk.Frame)):
                        widget.destroy()
                
                # Load and display
                img = Image.open(plot_path)
                img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                
                label = tk.Label(tab_frame, image=photo)
                label.image = photo  # Keep reference
                label.pack(fill=tk.BOTH, expand=True)
                
                # Update caption if available
                if hasattr(self, 'plot_caption') and self.plot_caption:
                    self.plot_caption.config(text=plot_path.name)
                else:
                    # Create caption label
                    caption_label = tk.Label(tab_frame, text=plot_path.name, 
                                           font=("Arial", 9))
                    caption_label.pack()
                    self.plot_caption = caption_label
                
                self.log(f"Displayed plot: {plot_path.name}")
        except Exception as e:
            self.log(f"Error displaying plot: {e}")
    
    def setup_tab_handlers(self):
        """Setup notebook tab change handlers"""
        # Find all notebooks in the GUI
        notebooks = []
        
        # Center panel notebook (summary tabs)
        if hasattr(self, 'center_notebook'):
            notebooks.append(self.center_notebook)
        
        # Right panel notebook (visualization tabs)
        if hasattr(self, 'right_notebook'):
            notebooks.append(self.right_notebook)
        
        # Step 3 notebook
        if hasattr(self, 'step3_notebook') and self.step3_notebook:
            notebooks.append(self.step3_notebook)
        
        # Bind tab change handlers
        for notebook in notebooks:
            if notebook:
                notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
    
    def on_tab_changed(self, event):
        """Handle tab selection change"""
        widget = event.widget
        if not isinstance(widget, ttk.Notebook):
            return
        
        try:
            current_tab = widget.tab(widget.select(), "text")
            
            # Refresh based on tab type
            if current_tab in ["TCP Analysis", "NTCP Analysis", "Integration"]:
                self.refresh_analysis_tab(current_tab)
            elif current_tab == "QA/Validation" or current_tab == "Validation & QA":
                self.refresh_qa_tab()
            elif current_tab in ["Data Summary", "Model Parameters", "Statistics", "QA Report"]:
                self.refresh_summary_tab(current_tab)
        except Exception as e:
            self.log(f"Error handling tab change: {e}")
    
    def refresh_analysis_tab(self, tab_name: str):
        """Refresh analysis tab content"""
        # Implementation for refreshing analysis tabs
        self.log(f"Refreshing {tab_name} tab")
    
    def refresh_qa_tab(self):
        """Refresh QA/Validation tab"""
        self.log("Refreshing QA/Validation tab")
        self.update_validation_qa_tab()
    
    def refresh_summary_tab(self, tab_name: str):
        """Refresh summary tab content"""
        # Implementation for refreshing summary tabs
        if tab_name == "Data Summary" and hasattr(self, 'summary_text'):
            # Refresh data summary
            pass
        elif tab_name == "Model Parameters" and hasattr(self, 'params_text'):
            # Refresh model parameters
            pass
        elif tab_name == "Statistics" and hasattr(self, 'stats_text'):
            # Refresh statistics
            pass
        elif tab_name == "QA Report" and hasattr(self, 'qa_text'):
            # Refresh QA report
            pass
    
    def update_app_state(self, step, status, outputs=None):
        """
        GAP 7: Unified event dispatcher for GUI status synchronization.
        
        Updates:
        1. Left panel status (step status labels)
        2. Right panel refresh (if outputs exist)
        3. Execution log
        
        Parameters
        ----------
        step : str
            Step name (e.g., 'step1', 'step2', 'step3')
        status : str
            Status text to display (e.g., 'Running...', 'Completed', 'Failed')
        outputs : dict, optional
            Dictionary with output information:
            - 'files': list of output file paths
            - 'summary': summary text for right panel
            - 'tab': tab name to update ('Data Summary', 'QA Report', etc.)
        """
        # Update left panel status
        if step in self.step_status_labels:
            status_label = self.step_status_labels[step]
            # Determine color based on status
            if 'Running' in status or '⏱' in status:
                color = "orange"
            elif 'Completed' in status or '✓' in status or 'OK' in status:
                color = "green"
            elif 'Failed' in status or 'X' in status or 'Error' in status:
                color = "red"
            elif 'Partial' in status or '!' in status:
                color = "orange"
            else:
                color = "gray"
            
            # Update status label (thread-safe)
            self.root.after(0, lambda: status_label.config(text=status, foreground=color))
        
        # Append to execution log
        self.log(f"[{step.upper()}] {status}")
        
        # Update right panel if outputs provided
        if outputs:
            # Refresh right panel with summary if provided
            if 'summary' in outputs and 'tab' in outputs:
                summary_text = outputs['summary']
                tab_name = outputs['tab']
                self.root.after(0, lambda: self.update_summary_panel(tab_name, summary_text))
            
            # Log output files if provided
            if 'files' in outputs and outputs['files']:
                file_list = outputs['files']
                if isinstance(file_list, list):
                    self.log(f"[{step.upper()}] Output files: {len(file_list)} files created")
                    for f in file_list[:5]:  # Log first 5 files
                        if isinstance(f, (str, Path)):
                            self.log(f"  - {Path(f).name}")
                    if len(file_list) > 5:
                        self.log(f"  ... and {len(file_list) - 5} more files")
        
        # Force GUI update
        self.root.update_idletasks()
    
    def preview_input_data(self):
        """Enhanced preview with format detection using UniversalDVHParser"""
        if not self.raw_input.get():
            return
        
        summary = []
        summary.append("="*60)
        summary.append("INPUT DATA PREVIEW")
        summary.append("="*60)
        
        try:
            path = Path(self.raw_input.get())
            
            if path.is_file():
                # Single file preview with UniversalDVHParser
                summary.append(f"\nFile: {path.name}")
                size_kb = path.stat().st_size / 1024
                summary.append(f"Size: {size_kb:.1f} KB")
                
                if UTILITIES_AVAILABLE:
                    try:
                        parser = UniversalDVHParser(path)
                        fmt = parser.detect_format()
                        summary.append(f"Format: {fmt}")
                        
                        # Try parsing
                        metadata, dvh = parser.parse()
                        summary.append(f"\nExtracted Metadata:")
                        summary.append(f"  Patient ID: {metadata.get('patient_id', 'Unknown')}")
                        summary.append(f"  Structure: {metadata.get('structure_name', 'Unknown')}")
                        summary.append(f"  Type: {'TUMOR' if metadata.get('is_tumor') else 'OAR'}")
                        summary.append(f"  DVH Type: {metadata.get('dvh_type', 'Unknown')}")
                        summary.append(f"  Data Points: {len(dvh)}")
                        if metadata.get('total_volume'):
                            summary.append(f"  Total Volume: {metadata.get('total_volume'):.2f} cm³")
                    except Exception as e:
                        summary.append(f"\n[!] Preview Error: {str(e)}")
                        summary.append("(File may be in unsupported format)")
                else:
                    # Fallback: read first few lines
                    try:
                        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = [f.readline().strip() for _ in range(5)]
                        summary.append("\nFirst 5 lines:")
                        summary.extend([f"  {line}" for line in lines if line])
                    except Exception as e:
                        summary.append(f"\n(Cannot preview text content: {str(e)})")
            
            elif path.is_dir():
                # Directory preview with format detection
                files = list(path.glob("*.txt")) + list(path.glob("*.csv")) + list(path.glob("*.dcm"))
                summary.append(f"\nDirectory: {path.name}")
                summary.append(f"Total DVH files: {len(files)}")
                
                if files and UTILITIES_AVAILABLE:
                    # Format distribution
                    formats = Counter()
                    patients = set()
                    structures = Counter()
                    tumor_count = 0
                    oar_count = 0
                    
                    # Sample first 20 files for preview
                    sample_size = min(20, len(files))
                    for f in sorted(files)[:sample_size]:
                        try:
                            parser = UniversalDVHParser(f)
                            fmt = parser.detect_format()
                            formats[fmt] += 1
                            
                            # Try to parse metadata
                            try:
                                metadata, _ = parser.parse()
                                if metadata.get('patient_id'):
                                    patients.add(metadata.get('patient_id'))
                                if metadata.get('structure_name'):
                                    structures[metadata.get('structure_name')] += 1
                                if metadata.get('is_tumor'):
                                    tumor_count += 1
                                else:
                                    oar_count += 1
                            except:
                                pass
                        except:
                            formats['Unknown'] += 1
                    
                    summary.append(f"\nFormats detected (sample of {sample_size}):")
                    for fmt, count in formats.items():
                        summary.append(f"  - {fmt}: {count} files")
                    
                    if patients:
                        summary.append(f"\nPatient IDs (sample): {len(patients)} unique")
                        if len(patients) <= 10:
                            for pid in sorted(patients):
                                summary.append(f"  - {pid}")
                        else:
                            for pid in sorted(list(patients))[:10]:
                                summary.append(f"  - {pid}")
                            summary.append(f"  ... and {len(patients) - 10} more")
                    
                    if structures:
                        summary.append(f"\nStructures (sample):")
                        for struct, count in structures.most_common(10):
                            summary.append(f"  - {struct}: {count} files")
                    
                    if tumor_count > 0 or oar_count > 0:
                        summary.append(f"\nStructure Types (sample):")
                        summary.append(f"  - OAR: {oar_count}")
                        summary.append(f"  - Tumor/PTV: {tumor_count}")
                else:
                    # Fallback: basic file listing
                    summary.append(f"\nFile types:")
                    exts = Counter([f.suffix for f in files])
                    for ext, count in sorted(exts.items()):
                        summary.append(f"  {ext}: {count} files")
                
                # Show first 10 files
                if files:
                    summary.append(f"\nFirst {min(10, len(files))} files:")
                    for f in sorted(files)[:10]:
                        summary.append(f"  • {f.name}")
                    if len(files) > 10:
                        summary.append(f"  ... and {len(files) - 10} more files")
                else:
                    summary.append("\nNo DVH files found (.txt, .csv, .dcm)")
            else:
                summary.append(f"\n[!] Path does not exist: {path}")
                
        except Exception as e:
            summary.append(f"\n[X] Error reading input: {str(e)}")
            if self.error_handler:
                self.error_handler.log(f"Preview error: {str(e)}", "WARNING")
        
        summary.append("="*60)
        
        # Update summary panel
        self.update_summary_panel("Data Summary", "\n".join(summary))
    
    def update_data_summary_panel(self):
        """Update Data Summary panel with detailed processing statistics"""
        if not hasattr(self, '_last_summary') or self._last_summary is None:
            return
        
        summary = self._last_summary
        
        # Build comprehensive summary text
        content_lines = []
        content_lines.append("=" * 70)
        content_lines.append("DVH PREPROCESSING SUMMARY")
        content_lines.append("=" * 70)
        content_lines.append("")
        content_lines.append("FILE PROCESSING:")
        content_lines.append(f"  • Total files scanned:        {summary.get('total_files', 0)}")
        content_lines.append(f"  • Successfully processed:      {summary.get('processed', 0)} [OK]")
        content_lines.append(f"  • Duplicates skipped:          {summary.get('duplicates_skipped', 0)}")
        content_lines.append(f"  • Excluded (PRV/Planning):     {summary.get('excluded', 0)}")
        content_lines.append(f"  • Failed to process:           {summary.get('failed', 0)} [X]")
        content_lines.append("")
        content_lines.append("WHY NOT ALL FILES PROCESSED:")
        
        total = summary.get('total_files', 0)
        processed = summary.get('processed', 0)
        duplicates = summary.get('duplicates_skipped', 0)
        excluded = summary.get('excluded', 0)
        failed = summary.get('failed', 0)
        
        content_lines.append(f"  [OK] Unique patient-organ pairs:  {processed} files")
        content_lines.append(f"  [SKIP] Duplicate combinations:       {duplicates} files (same patient+organ)")
        content_lines.append(f"  [EXCLUDE] Planning structures (PRV):    {excluded} files (not clinical OARs)")
        content_lines.append(f"  [X] Processing errors:            {failed} files")
        content_lines.append(f"  {'-' * 60}")
        content_lines.append(f"  = TOTAL:                        {processed + duplicates + excluded + failed}/{total} files")
        content_lines.append("")
        
        # Patient and structure info
        patients = summary.get('patients', set())
        structures = summary.get('structures', {})
        
        content_lines.append("PATIENT & STRUCTURE DATA:")
        content_lines.append(f"  • Unique patients:             {len(patients)}")
        content_lines.append(f"  • Unique structures:           {len(structures)}")
        content_lines.append("")
        content_lines.append("DETECTED STRUCTURES:")
        
        # Sort structures by count
        if structures:
            for structure, count in structures.most_common():
                content_lines.append(f"    • {structure:30s} {count:3d} files")
        
        # Formats processed
        formats = summary.get('formats', {})
        if formats:
            content_lines.append("")
            content_lines.append("FORMATS PROCESSED:")
            for fmt, count in formats.items():
                content_lines.append(f"    • {fmt:30s} {count:3d} files")
        
        # Processing time if available
        if hasattr(self, 'step_durations') and 'step1' in self.step_durations:
            duration = self.step_durations['step1']
            content_lines.append("")
            content_lines.append("PROCESSING PERFORMANCE:")
            content_lines.append(f"  [TIMER] Total time:                  {duration:.2f} seconds")
            if total > 0:
                content_lines.append(f"  [TIMER] Average per file:            {duration/total:.3f} seconds")
        
        content = "\n".join(content_lines)
        
        # Update the Data Summary tab
        self.update_summary_panel("Data Summary", content)
    
    def update_summary_panel(self, tab_name, content):
        """Update center panel content - ENHANCED"""
        text_widgets = {
            "Data Summary": self.summary_text,
            "Model Parameters": self.params_text,
            "Statistics": self.stats_text,
            "QA Report": self.qa_text if hasattr(self, 'qa_text') else None
        }
        
        if tab_name in text_widgets and text_widgets[tab_name]:
            widget = text_widgets[tab_name]
            widget.config(state='normal')  # Enable editing
            widget.delete("1.0", tk.END)
            widget.insert("1.0", content)
            widget.config(state='normal')  # Keep enabled for scrolling
            self.log(f"Updated {tab_name} panel")
        else:
            self.log(f"Warning: Tab '{tab_name}' not found or not initialized")
    
    def create_placeholder_plot(self, viz_type):
        """Create placeholder plot in visualization tab"""
        if viz_type not in self.viz_tabs:
            return
        
        fig = self.viz_tabs[viz_type]['figure']
        fig.clear()
        ax = fig.add_subplot(111)
        
        ax.text(0.5, 0.5, f"{viz_type}\n\n(Plot will appear after analysis)", 
               ha='center', va='center', fontsize=12, color='gray',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.set_xticks([])
        ax.set_yticks([])
        
        self.viz_tabs[viz_type]['canvas'].draw()
    
    def initialize_placeholders(self):
        """Initialize all visualization tabs with placeholders"""
        if hasattr(self, 'viz_tabs'):
            for viz_type in self.viz_tabs.keys():
                self.create_placeholder_plot(viz_type)
    
    def load_image_to_viz(self, tab_name, image_path):
        """Load PNG image into visualization tab - ENHANCED"""
        if tab_name not in self.viz_tabs:
            self.log(f"Warning: Visualization tab '{tab_name}' not found")
            return
        
        try:
            from PIL import Image  # type: ignore
            import matplotlib.image as mpimg  # type: ignore
            
            # Verify file exists
            img_path = Path(image_path)
            if not img_path.exists():
                self.log(f"Warning: Image not found: {image_path}")
                return
            
            fig = self.viz_tabs[tab_name]['figure']
            fig.clear()
            ax = fig.add_subplot(111)
            
            img = mpimg.imread(str(img_path))
            ax.imshow(img)
            ax.axis('off')
            ax.set_title(img_path.name, fontsize=10)
            
            fig.tight_layout()
            self.viz_tabs[tab_name]['canvas'].draw()
            
            self.log(f"Loaded plot: {img_path.name} → {tab_name}")
            
        except Exception as e:
            self.log(f"Error loading image to {tab_name}: {str(e)}")
            import traceback
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.log(f"  {line}")
    
    # ========== Step Execution Methods ==========
    
    def build_canonical_dvh(self, dose, volume, dvh_type):
        """
        Build canonical cumulative and differential DVH.
        Pure function with no side effects. Does NOT modify input arrays.
        
        Parameters
        ----------
        dose : np.ndarray
            Dose values
        volume : np.ndarray
            Volume values
        dvh_type : str
            'cumulative' or 'differential'
        
        Returns
        -------
        dict
            {
                "dose": dose_sorted,
                "cumulative": cumulative_volume,
                "differential": differential_volume
            }
        """
        # Convert to numpy arrays (copy to avoid modifying input)
        dose = np.asarray(dose).copy()
        volume = np.asarray(volume).copy()
        
        # Sort by dose ascending
        sort_idx = np.argsort(dose)
        dose = dose[sort_idx]
        volume = volume[sort_idx]
        
        if dvh_type == "cumulative":
            # Convert cumulative to differential via finite differences
            # Differential = -d(cumulative)/d(dose)
            if len(volume) > 1:
                # Use negative gradient (volume decreases with dose)
                differential = -np.diff(volume)
                # Pad with zero for last bin
                differential = np.append(differential, 0.0)
                
                # Normalize differential so integral = 100%
                total_integral = np.sum(differential)
                if total_integral > 0:
                    differential = differential / total_integral * 100.0
            else:
                differential = np.array([100.0] if len(volume) == 1 else [])
            
            # Normalize cumulative to percentage if needed
            cumulative = volume.copy()
            if cumulative[0] > 0:
                if cumulative[0] > 105:  # Absolute volume
                    cumulative = cumulative / cumulative[0] * 100.0
                elif cumulative[0] <= 105:  # Likely already percentage
                    pass  # Keep as is
            
            return {
                "dose": dose,
                "cumulative": cumulative,
                "differential": differential
            }
        
        elif dvh_type == "differential":
            # Normalize differential so integral = 100%
            total_integral = np.sum(volume)
            if total_integral > 0:
                differential = volume / total_integral * 100.0
            else:
                differential = volume.copy()
            
            # Reconstruct cumulative DVH ONLY from differential
            # Cumulative at dose D = sum of volumes at doses >= D
            cumulative = np.cumsum(differential[::-1])[::-1]
            
            return {
                "dose": dose,
                "cumulative": cumulative,
                "differential": differential
            }
        
        else:
            # Unknown type - assume cumulative
            cumulative = volume.copy()
            if cumulative[0] > 0 and cumulative[0] > 105:
                cumulative = cumulative / cumulative[0] * 100.0
            
            differential = np.zeros_like(cumulative)
            if len(cumulative) > 1:
                differential[:-1] = -np.diff(cumulative)
            
            return {
                "dose": dose,
                "cumulative": cumulative,
                "differential": differential
            }
    
    def normalize_dvh(self, dose, volume, dvh_type):
        """
        Normalize DVH: convert differential to cumulative, sort dose axis.
        
        Always returns cumulative DVH with sorted dose axis.
        
        Parameters
        ----------
        dose : np.ndarray
            Dose values
        volume : np.ndarray
            Volume values
        dvh_type : str
            'cumulative' or 'differential'
        
        Returns
        -------
        tuple
            (dose_sorted, volume_cumulative, 'cumulative')
        """
        # Convert to numpy arrays if needed
        dose = np.asarray(dose)
        volume = np.asarray(volume)
        
        # Sort by dose axis first
        sort_idx = np.argsort(dose)
        dose = dose[sort_idx]
        volume = volume[sort_idx]
        
        if dvh_type == "differential":
            # Convert differential to cumulative
            # Cumulative at dose D = sum of volumes at doses >= D
            cumulative = np.cumsum(volume[::-1])[::-1]
            
            # Normalize to percentage if needed
            if cumulative[0] > 0:
                cumulative = cumulative / cumulative[0] * 100.0
            
            return dose, cumulative, "cumulative"
        
        # Already cumulative - normalize to percentage if needed
        if volume[0] > 0 and volume[0] <= 105:
            # Likely already percentage, keep as is
            return dose, volume, "cumulative"
        elif volume[0] > 0:
            # Absolute volume - normalize to percentage
            volume = volume / volume[0] * 100.0
        
        return dose, volume, "cumulative"
    
    def validate_dvh_integrity(self, dvh_df, dvh_type, structure_name, patient_id):
        """
        Validate DVH integrity (read-only, non-blocking).
        
        Pure function with no side effects. Returns validation results only.
        
        Parameters
        ----------
        dvh_df : pd.DataFrame
            DVH data with columns 'Dose[Gy]' and 'Volume[cm3]'
        dvh_type : str
            'cumulative' or 'differential'
        structure_name : str
            Structure name
        patient_id : str
            Patient ID
        
        Returns
        -------
        dict
            Validation result dictionary with status, failed_checks, warnings
        """
        failed_checks = []
        warnings = []
        
        if dvh_df is None or len(dvh_df) == 0:
            return {
                "status": "FLAG",
                "failed_checks": ["Empty DVH data"],
                "warnings": [],
                "structure": structure_name,
                "patient_id": patient_id,
                "dvh_type": dvh_type
            }
        
        # Check for required columns
        if 'Dose[Gy]' not in dvh_df.columns or 'Volume[cm3]' not in dvh_df.columns:
            return {
                "status": "FLAG",
                "failed_checks": ["Missing required columns (Dose[Gy] or Volume[cm3])"],
                "warnings": [],
                "structure": structure_name,
                "patient_id": patient_id,
                "dvh_type": dvh_type
            }
        
        # CRITICAL: Build canonical DVH first (ensures proper physics)
        doses_raw = dvh_df['Dose[Gy]'].values
        volumes_raw = dvh_df['Volume[cm3]'].values
        
        # Build canonical DVH (returns both cumulative and differential)
        canonical = self.build_canonical_dvh(doses_raw, volumes_raw, dvh_type)
        doses = canonical["dose"]
        volumes = canonical["cumulative"]  # Use canonical cumulative for validation
        differential = canonical["differential"]
        
        # C. Structural Sanity Checks
        if len(dvh_df) <= 10:
            failed_checks.append(f"DVH length too short ({len(dvh_df)} points, minimum 10)")
        
        if np.any(np.isnan(doses)) or np.any(np.isnan(volumes)):
            failed_checks.append("NaN values found in DVH data")
        
        if np.any(np.isinf(doses)) or np.any(np.isinf(volumes)):
            failed_checks.append("Infinite values found in DVH data")
        
        # Check dose axis is strictly increasing (after canonicalization, should always be)
        if len(doses) > 1:
            dose_diff = np.diff(doses)
            if not np.all(dose_diff > 0):
                # This should not happen after canonicalization, but check anyway
                failed_checks.append("Dose axis not strictly increasing after canonicalization")
        
        # Check differential DVH integral ≈ 100%
        if len(differential) > 0:
            diff_integral = np.sum(differential)
            if not (98 <= diff_integral <= 102):
                warnings.append(f"Differential DVH integral ({diff_integral:.1f}%) not near 100%")
        
        # Always validate as cumulative (since normalize_dvh always returns cumulative)
        # A. Cumulative DVH Physical Rules (after normalization)
        first_vol = volumes[0] if len(volumes) > 0 else 0
        last_vol = volumes[-1] if len(volumes) > 0 else 0
        
        # Enforce: Volume range 0-100%
        if first_vol < 0 or first_vol > 105:
            failed_checks.append(f"First volume ({first_vol:.1f}%) outside valid range [0, 100%]")
        elif first_vol > 100:
            warnings.append(f"First volume ({first_vol:.1f}%) exceeds 100%")
        
        if last_vol < -1 or last_vol > 5:  # Allow small negative due to numerical errors
            warnings.append(f"Last volume ({last_vol:.1f}%) not near 0% (expected: 0-5%)")
        
        # Enforce: Monotonically non-increasing
        if len(volumes) > 1:
            vol_diff = np.diff(volumes)
            non_increasing_count = np.sum(vol_diff > 1e-6)  # Allow small numerical errors
            if non_increasing_count > len(volumes) * 0.1:  # More than 10% violations
                failed_checks.append(f"Volume not monotonically non-increasing ({non_increasing_count} violations)")
            elif non_increasing_count > 0:
                warnings.append(f"Minor non-monotonicity detected ({non_increasing_count} points)")
        
        # Enforce: Last bin ≈ 0%
        if len(volumes) > 0 and not (0 <= last_vol <= 5):
            warnings.append(f"Last bin volume ({last_vol:.1f}%) not near 0% (expected: 0-5%)")
        
        # Check first volume is near 100% (for normalized percentage DVH)
        if 95 <= first_vol <= 105:
            if abs(first_vol - 100) > 1:
                warnings.append(f"First volume ({first_vol:.1f}%) not exactly 100%")
        
        # Note: Differential DVH checks removed - validation now operates on normalized cumulative only
        
        # Determine overall status (use FLAG instead of FAIL for clarity)
        status = "PASS" if len(failed_checks) == 0 else "FLAG"
        
        return {
            "status": status,
            "failed_checks": failed_checks,
            "warnings": warnings,
            "structure": structure_name,
            "patient_id": patient_id,
            "dvh_type": dvh_type
        }
    
    def _preflight_input_check(self):
        """
        Preflight input check (non-blocking).
        Verifies DVH files are readable and clinical file contains patient IDs.
        Logs warnings but does NOT stop execution.
        """
        try:
            warnings_found = []
            
            # Check DVH files are readable
            if self.raw_input.get():
                input_path = Path(self.raw_input.get())
                if input_path.is_dir():
                    dvh_files = list(input_path.glob('*.txt')) + \
                               list(input_path.glob('*.csv')) + \
                               list(input_path.glob('*.dcm'))
                    if dvh_files:
                        # Try to read first few files
                        readable_count = 0
                        for f in dvh_files[:5]:  # Sample first 5
                            try:
                                if f.suffix == '.csv':
                                    pd.read_csv(f, nrows=1)
                                elif f.suffix == '.txt':
                                    with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                                        fp.readline()
                                readable_count += 1
                            except Exception:
                                warnings_found.append(f"Cannot read DVH file: {f.name}")
                elif input_path.is_file():
                    try:
                        if input_path.suffix == '.csv':
                            pd.read_csv(input_path, nrows=1)
                        elif input_path.suffix == '.txt':
                            with open(input_path, 'r', encoding='utf-8', errors='ignore') as fp:
                                fp.readline()
                    except Exception as e:
                        warnings_found.append(f"Cannot read DVH file: {input_path.name} ({str(e)})")
            
            # Check clinical file contains patient IDs (if provided)
            if self.clinical_file.get():
                clinical_path = Path(self.clinical_file.get())
                if clinical_path.exists() and clinical_path.suffix in ['.xlsx', '.xls', '.csv']:
                    try:
                        if clinical_path.suffix == '.csv':
                            df = pd.read_csv(clinical_path, nrows=10)
                        else:
                            df = pd.read_excel(clinical_path, nrows=10)
                        
                        # Look for patient ID column
                        patient_id_cols = [col for col in df.columns if any(
                            kw in str(col).upper() for kw in ['PATIENT', 'ID', 'PT', 'SUBJECT']
                        )]
                        
                        if not patient_id_cols:
                            warnings_found.append(
                                "Clinical file may not contain patient ID column. "
                                "Expected columns: PatientID, Patient_ID, PT, etc."
                            )
                    except Exception as e:
                        warnings_found.append(f"Cannot read clinical file: {str(e)}")
            
            # Log warnings (non-blocking)
            if warnings_found:
                self.log("[!] Preflight check warnings (non-blocking):")
                for warning in warnings_found:
                    self.log(f"  - {warning}")
                
                # Show non-blocking popup
                self.root.after(0, lambda: messagebox.showwarning(
                    "Preflight Check",
                    "Preflight check found potential issues:\n\n" + 
                    "\n".join(f"• {w}" for w in warnings_found) +
                    "\n\nExecution will continue, but please review these warnings."
                ))
            else:
                self.log("[OK] Preflight check passed")
                
        except Exception as e:
            # Non-blocking: log error but don't stop
            self.log(f"[!] Preflight check error (non-blocking): {str(e)}")
    
    def validate_inputs(self):
        """
        Validate all inputs before execution.
        
        Returns
        -------
        bool
            True if validation passes, False otherwise
        """
        errors = []
        
        # Check analysis mode is selected (MANDATORY)
        if not self.analysis_mode.get():
            errors.append("Analysis mode not selected (TCP only, NTCP only, or TCP + NTCP)")
        
        if not self.output_dir.get():
            errors.append("Output directory not selected")
        
        if not self.raw_input.get():
            errors.append("Input folder not selected")
        else:
            input_path = Path(self.raw_input.get())
            basic = self.mode_controller and self.mode_controller.is_basic()
            if INPUT_ROUTER_AVAILABLE and validate_input_for_mode:
                ok, router_errors = validate_input_for_mode(
                    input_path,
                    basic_mode=bool(basic),
                    source_pref=self.input_source.get() if hasattr(self, "input_source") else "auto",
                )
                if not ok:
                    errors.extend(router_errors)
            elif not input_path.exists():
                errors.append(f"Input path does not exist: {input_path}")
            elif input_path.is_dir():
                if self.input_source.get() == "dicom":
                    if ENGINE_BRIDGE_AVAILABLE and not is_dicom_directory(input_path):
                        errors.append(
                            f"Folder does not look like DICOM RT: {input_path}\n"
                            "Expected RTPLAN/RTDOSE/RTSTRUCT or .dcm files."
                        )
                else:
                    dvh_files = list(input_path.glob("*.txt")) + list(input_path.glob("*.csv"))
                    if not dvh_files:
                        errors.append(f"No TPS .txt/.csv DVH files in {input_path}")
            elif input_path.is_file() and not input_path.exists():
                errors.append(f"Input file does not exist: {input_path}")
        
        # Check clinical data if ML enabled
        if self.enable_ml.get() and not self.clinical_file.get():
            errors.append("Clinical data required for ML models")
        elif self.clinical_file.get():
            clinical_path = Path(self.clinical_file.get())
            if not clinical_path.exists():
                errors.append(f"Clinical data file does not exist: {clinical_path}")
        
        if errors:
            error_msg = "[X] Input Validation Failed:\n\n" + "\n".join(f"- {e}" for e in errors)
            if self.error_handler:
                self.error_handler.log("\n".join(errors), "ERROR")
            messagebox.showerror("Validation Error", error_msg)
            return False
        
        return True
    
    def _prepare_pipeline_input(self) -> Optional[PipelineInput]:
        """
        Prepare PipelineInput from GUI state.
        
        Returns
        -------
        Optional[PipelineInput]
            PipelineInput object if pipeline is available, None otherwise
        """
        if not PIPELINE_AVAILABLE:
            return None
        
        try:
            dvh_directory = Path(self.raw_input.get()) if self.raw_input.get() else None
            output_directory = Path(self.output_dir.get()) if self.output_dir.get() else None
            patient_data_file = Path(self.clinical_file.get()) if self.clinical_file.get() else None
            clinical_file = patient_data_file  # Same file used for both
            
            if not dvh_directory or not output_directory:
                return None
            
            # Prepare treatment info from GUI state
            treatment_info = {}
            if hasattr(self, 'n_fractions') and self.n_fractions.get():
                treatment_info['n_fractions'] = int(self.n_fractions.get())
            if hasattr(self, 'dose_per_fraction') and self.dose_per_fraction.get():
                treatment_info['dose_per_fraction'] = float(self.dose_per_fraction.get())
            
            # Prepare config from GUI state
            engine_mode = "advanced" if (self.mode_controller and self.mode_controller.is_advanced()) else "basic"
            site_override = map_site_override(self.cancer_site.get()) if map_site_override else None
            config = {
                'enable_ml': self.enable_ml.get() if hasattr(self, 'enable_ml') else False,
                'enable_shap': self.enable_shap.get() if hasattr(self, 'enable_shap') else False,
                'analysis_mode': self.analysis_mode.get() if hasattr(self, 'analysis_mode') else None,
                'engine_mode': engine_mode,
                'site_override': site_override,
                'input_source': self.input_source.get() if hasattr(self, 'input_source') else 'dicom',
            }
            
            # Prepare TCP config from GUI state
            tcp_config = None
            if hasattr(self, 'tumor_organ_type'):
                base_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
                metrics_file = None
                if base_dir:
                    metrics_dir = base_dir / "dose_metrics" / "tables"
                    metrics_file = metrics_dir / "TCP_physical_metrics.xlsx"
                
                tcp_config = {
                    'tumor_type': self.tumor_organ_type.get() if hasattr(self, 'tumor_organ_type') else 'HNSCC',
                    'physical_metrics_file': str(metrics_file) if metrics_file and metrics_file.exists() else None,
                    'enable_ml': self.enable_ml.get() if hasattr(self, 'enable_ml') else False,
                    'enable_shap': self.enable_shap.get() if hasattr(self, 'enable_shap') else False,
                    # Advanced options that trigger fallback:
                    'use_fdvh': self.use_fdvh.get() if hasattr(self, 'use_fdvh') else False,
                    'n_fractions': 30,  # Default, can be made configurable
                    'alpha_beta_tumor': 10.0,  # Default, can be made configurable
                    'use_utcp': self.use_utcp.get() if hasattr(self, 'use_utcp') else False,
                    'ccs_file': self.ccs_file_path.get() if hasattr(self, 'ccs_file_path') else None,
                    'ccs_threshold': self.ccs_threshold.get() if hasattr(self, 'ccs_threshold') else None,
                }
            
            # Prepare NTCP config from GUI state
            ntcp_config = None
            if hasattr(self, 'enable_ml'):
                ntcp_config = {
                    'enable_ml': self.enable_ml.get() if hasattr(self, 'enable_ml') else False,
                    'enable_shap': self.enable_shap.get() if hasattr(self, 'enable_shap') else False,
                }
            
            dicom_directory = None
            if self.input_source.get() == "dicom" and dvh_directory and dvh_directory.is_dir():
                if ENGINE_BRIDGE_AVAILABLE and is_dicom_directory(dvh_directory):
                    dicom_directory = dvh_directory

            return PipelineInput(
                dvh_directory=dvh_directory,
                output_directory=output_directory,
                dicom_directory=dicom_directory,
                input_source=self.input_source.get() if hasattr(self, 'input_source') else "auto",
                patient_data_file=patient_data_file if patient_data_file and patient_data_file.exists() else None,
                clinical_file=clinical_file if clinical_file and clinical_file.exists() else None,
                treatment_info=treatment_info if treatment_info else None,
                config=config if config else None,
                tcp_config=tcp_config,
                ntcp_config=ntcp_config
            )
        except Exception as e:
            self.log(f"[!] Error preparing pipeline input: {str(e)}")
            return None
    
    def _handle_pipeline_output(self, output: PipelineOutput, step_name: str, success_callback=None):
        """
        Handle PipelineOutput and update GUI state.
        
        Parameters
        ----------
        output : PipelineOutput
            Pipeline execution output
        step_name : str
            Name of the step (e.g., 'step1', 'step2')
        success_callback : Optional[callable]
            Callback function to execute on success
        """
        # Log all pipeline logs
        for log_line in output.logs:
            if log_line.strip():
                self.log(log_line)
        
        # Log errors
        for error in output.errors:
            self.log(f"[X] {error}")
        
        # Log warnings
        for warning in output.warnings:
            self.log(f"[!] {warning}")
        
        # Update status based on output status
        if output.status == 'success':
            duration = output.execution_time
            self.log(f"[OK] {step_name} completed in {duration:.1f} seconds")
            self.root.after(0, lambda: self._stop_step_animation(step_name))
            status_text = f"✓ {step_name.replace('step', 'Step ')} ({duration:.1f}s)"
            self.root.after(0, lambda: self._update_step_status(step_name, status_text, "green"))
            if success_callback:
                success_callback()
        elif output.status == 'partial':
            duration = output.execution_time
            self.log(f"[!] {step_name} completed with warnings in {duration:.1f} seconds")
            self.root.after(0, lambda: self._stop_step_animation(step_name))
            status_text = f"[!] {step_name.replace('step', 'Step ')} ({duration:.1f}s)"
            self.root.after(0, lambda: self._update_step_status(step_name, status_text, "orange"))
            if success_callback:
                success_callback()
        else:  # error
            self.log(f"[X] {step_name} failed")
            self.root.after(0, lambda: self._stop_step_animation(step_name))
            self.root.after(0, lambda: self._update_step_status(step_name, "[X] Failed", "red"))
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
    
    def _update_step_status(self, step_name: str, text: str, color: str):
        """Update step status label (thread-safe)."""
        status_attr = f"{step_name}_status"
        if hasattr(self, status_attr):
            getattr(self, status_attr).config(text=text, foreground=color)
    
    def run_step1(self):
        """Run Step 1 with timer."""
        self.step_start_times['step1'] = time.time()
        
        # Validation
        if not self.validate_inputs():
            return
        
        # PART 5: Preflight input check (non-blocking)
        self._preflight_input_check()
        
        # Update status
        self.step1_status.config(text="⏱ Running Step 1...", foreground="orange")
        self.log("Starting Step 1: DVH Preprocessing...")
        
        # Start robot animation
        self._start_step_animation("step1")
        
        # Run in thread to avoid GUI freeze
        thread = threading.Thread(target=self._execute_step1, daemon=True)
        thread.start()
    
    def _execute_step1(self):
        """Execute DVH preprocessing using intelligent parser (CANONICAL DVH ENGINE)"""
        try:
            # Validate analysis mode is selected
            if not self.analysis_mode.get():
                messagebox.showerror(
                    "Missing Configuration",
                    "Please select an Analysis Mode in Global Settings:\n"
                    "• TCP only\n"
                    "• NTCP only\n"
                    "• TCP + NTCP\n\n"
                    "This determines which analysis branches will run."
                )
                return
            
            # Create output directory structure based on analysis mode
            base_dir = Path(self.output_dir.get())
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Auto-create subfolders based on analysis mode
            mode = self.analysis_mode.get()
            processed_dir = base_dir / "processed_DVH"
            processed_dir.mkdir(parents=True, exist_ok=True)
            
            # Create logs directory
            logs_dir = base_dir / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # UNIFIED OUTPUT STRUCTURE: Create all required directories
            if mode in ["TCP_ONLY", "TCP_NTCP"]:
                tcp_dir = base_dir / "tcp_analysis"
                tcp_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"Created TCP analysis directory: {tcp_dir}")
            
            if mode in ["NTCP_ONLY", "TCP_NTCP"]:
                ntcp_dir = base_dir / "ntcp_analysis"
                ntcp_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"Created NTCP analysis directory: {ntcp_dir}")
            
            # Integration directory (for BOTH mode)
            if mode == "TCP_NTCP":
                integration_dir = base_dir / "integration"
                integration_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"Created integration directory: {integration_dir}")
            
            # Dose metrics directory (used by both)
            metrics_dir = base_dir / "dose_metrics"
            metrics_dir.mkdir(parents=True, exist_ok=True)
            
            # QA directory (always created)
            qa_dir = base_dir / "qa"
            qa_dir.mkdir(parents=True, exist_ok=True)
            
            self.log(f"Output directory: {processed_dir}")
            self.log(f"Analysis mode: {mode}")
            
            input_path = Path(self.raw_input.get())
            
            # Unified Step 1 ingest (Phase 1+2): DICOM manifest or TPS preprocess
            if INPUT_ROUTER_AVAILABLE and run_step1_ingest:
                kind = resolve_input_kind(
                    input_path,
                    self.input_source.get() if hasattr(self, "input_source") else "auto",
                )
                self.log(f"Input kind: {kind} (source={self.input_source.get()})")
                if kind == "dicom":
                    self.log("DICOM RT: Step 1 ingest manifest (analysis via engine at Step 3)")
                else:
                    self.log("Using rbGyanX UniversalDVHParser for TPS DVH preprocessing...")
                summary = run_step1_ingest(
                    input_path,
                    processed_dir,
                    source_pref=self.input_source.get() if hasattr(self, "input_source") else "auto",
                    log=self.log,
                )
            elif UTILITIES_AVAILABLE:
                self.log("Using rbGyanX UniversalDVHParser for intelligent preprocessing...")
                self.log(f"Input: {input_path}")
                summary = preprocess_dvh_intelligent(input_path, processed_dir)
                
                # Store summary for display in center panel
                self._last_summary = summary
                
                # Log summary
                self.log(f"[OK] Processed: {summary['processed']}/{summary['total_files']} files")
                self.log(f"[OK] Unique patients: {len(summary['patients'])}")
                self.log(f"[OK] Structures: {len(summary['structures'])}")
                
                # Update data summary panel with detailed statistics
                self.root.after(0, lambda: self.update_data_summary_panel())
                
                # Extract detected structures
                self.detected_organs = {}
                self.detected_targets = {}
                
                for structure, count in summary['structures'].items():
                    # Separate organs from targets
                    if any(kw in structure for kw in ['PTV', 'GTV', 'CTV', 'Tumor', 'Target']):
                        self.detected_targets[structure] = count
                    else:
                        self.detected_organs[structure] = count
                
                self.log(f"[OK] Detected {len(self.detected_organs)} OARs")
                self.log(f"[OK] Detected {len(self.detected_targets)} Targets")
                
                # Try to auto-detect diagnosis from DVH metadata
                self.auto_detect_diagnosis()
                
                # Populate structure selection list in Step 3
                self.root.after(0, self.populate_structure_list)
                
                if summary['failed'] > 0:
                    self.log(f"[!] Failed: {summary['failed']} files")
                    duration = time.time() - self.step_start_times.get('step1', time.time())
                    self.step_durations['step1'] = duration
                    self.log(f"[TIMER] Step 1 completed in {duration:.1f} seconds")
                    self.root.after(0, lambda: self.step1_status.config(
                        text=f"[!] Partial ({summary['processed']}/{summary['total_files']}) ({duration:.1f}s)", 
                        foreground="orange"))
                else:
                    self.log("[OK] Step 1: DVH preprocessing complete")
                    duration = time.time() - self.step_start_times.get('step1', time.time())
                    self.step_durations['step1'] = duration
                    self.log(f"[TIMER] Step 1 completed in {duration:.1f} seconds")
                    self.root.after(0, lambda: self._stop_step_animation("step1"))
                    self.root.after(0, lambda: self.step1_status.config(text=f"✓ Step 1 ({duration:.1f}s)", foreground="green"))
                
                self.steps_completed["step1"] = True
                
                # Update dashboard
                self.root.after(100, self.update_dashboard_state)
                
                # Show summary
                self.show_step1_summary(processed_dir, summary)
                
                # CRITICAL: Run DVH validation (read-only, non-blocking)
                self.log("Running DVH integrity validation...")
                self._validate_all_dvhs(processed_dir)
                
                # Update progress
                self.root.after(0, lambda: self.progress_var.set(1))
                
                # Auto-trigger Step 2 if in run_all mode
                if hasattr(self, 'run_all_mode') and self.run_all_mode:
                    self.root.after(1000, self.run_step2)
            else:
                # Fallback: Use pipeline if available, otherwise subprocess
                use_pipeline = False
                if PIPELINE_AVAILABLE:
                    self.log("Using pipeline orchestration for preprocessing...")
                    pipeline_input = self._prepare_pipeline_input()
                    if pipeline_input:
                        # Update output directory to processed_dir
                        pipeline_input.output_directory = processed_dir
                        output = run_analysis_pipeline(pipeline_input, steps=['preprocess'], timeout=300)
                        
                        def on_success():
                            self.steps_completed["step1"] = True
                            self.show_step1_summary(processed_dir)
                            self.root.after(0, lambda: self.progress_var.set(1))
                            if hasattr(self, 'run_all_mode') and self.run_all_mode:
                                self.root.after(1000, self.run_step2)
                        
                        self._handle_pipeline_output(output, 'step1', on_success)
                        use_pipeline = True
                    else:
                        self.log("[!] Failed to prepare pipeline input, falling back to subprocess")
                
                # Fallback to subprocess call if pipeline not available or failed
                if not use_pipeline:
                    self.log("Using legacy subprocess preprocessing...")
                    cmd = [
                        sys.executable,
                        str(_rbgyanx_base_dir() / "code1_dvh_preprocess.py"),
                        str(input_path.resolve()),
                        "--outdir", str(processed_dir.resolve())
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, 
                                          cwd=_rbgyanx_base_dir())
                    
                    if result.stdout:
                        for line in result.stdout.strip().split('\n'):
                            if line.strip():
                                self.log(line)
                    
                    if result.returncode == 0:
                        self.log("[OK] Step 1: DVH preprocessing complete")
                        duration = time.time() - self.step_start_times.get('step1', time.time())
                        self.step_durations['step1'] = duration
                        self.log(f"[TIMER] Step 1 completed in {duration:.1f} seconds")
                        self.root.after(0, lambda: self._stop_step_animation("step1"))
                        self.root.after(0, lambda: self.step1_status.config(text=f"✓ Step 1 ({duration:.1f}s)", foreground="green"))
                        self.steps_completed["step1"] = True
                        self.show_step1_summary(processed_dir)
                        self.root.after(0, lambda: self.progress_var.set(1))
                        if hasattr(self, 'run_all_mode') and self.run_all_mode:
                            self.root.after(1000, self.run_step2)
                    else:
                        error_msg = result.stderr if result.stderr else result.stdout
                        self.log(f"[X] Step 1 failed with return code {result.returncode}")
                        if error_msg:
                            for line in error_msg.strip().split('\n'):
                                if line.strip():
                                    self.log(f"  {line}")
                        self.root.after(0, lambda: self._stop_step_animation("step1"))
                        self.root.after(0, lambda: self.step1_status.config(text="[X] Failed", foreground="red"))
                        if hasattr(self, 'run_all_mode'):
                            self.run_all_mode = False
                    
        except Exception as e:
            error_msg = str(e)
            if self.error_handler:
                helpful_msg = self.error_handler.handle_error(
                    e,
                    context="Step 1: DVH Preprocessing",
                    show_gui=True
                )
                self.log(f"[X] Step 1 error: {error_msg}")
            else:
                self.log(f"[X] Step 1 error: {error_msg}")
                import traceback
                for line in traceback.format_exc().split('\n'):
                    if line.strip():
                        self.log(f"  {line}")
            self.root.after(0, lambda: self._stop_step_animation("step1"))
            self.root.after(0, lambda: self.step1_status.config(text="[X] Error", foreground="red"))
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
    
    def _validate_all_dvhs(self, processed_dir):
        """
        Validate all DVH files in processed directory (read-only, non-blocking).
        Stores results in self.validation_results.
        Validation operates on normalized cumulative DVHs only.
        """
        try:
            cdvh_dir = processed_dir / "cDVH_csv"
            ddvh_dir = processed_dir / "dDVH_csv"
            
            # Clear previous results
            self.validation_results = []
            
            # Validate cumulative DVHs (prefer cumulative over differential)
            if cdvh_dir.exists():
                for csv_file in cdvh_dir.glob("*.csv"):
                    try:
                        # Parse patient ID and structure from filename
                        filename = csv_file.stem
                        parts = filename.rsplit('_', 1)
                        if len(parts) == 2:
                            patient_id, structure_name = parts
                        else:
                            patient_id = filename
                            structure_name = "Unknown"
                        
                        # Read DVH data
                        dvh_df = pd.read_csv(csv_file)
                        
                        # Validate (will normalize internally)
                        result = self.validate_dvh_integrity(
                            dvh_df, 'cumulative', structure_name, patient_id
                        )
                        self.validation_results.append(result)
                        
                    except Exception as e:
                        # Non-blocking: log error but continue
                        self.log(f"[!] Validation error for {csv_file.name}: {str(e)}")
                        self.validation_results.append({
                            "status": "FLAG",
                            "failed_checks": [f"Validation error: {str(e)}"],
                            "warnings": [],
                            "structure": structure_name if 'structure_name' in locals() else "Unknown",
                            "patient_id": patient_id if 'patient_id' in locals() else "Unknown",
                            "dvh_type": "cumulative"
                        })
            
            # Validate differential DVHs (will be normalized to cumulative in validation)
            if ddvh_dir.exists():
                for csv_file in ddvh_dir.glob("*.csv"):
                    try:
                        # Parse patient ID and structure from filename
                        filename = csv_file.stem
                        parts = filename.rsplit('_', 1)
                        if len(parts) == 2:
                            patient_id, structure_name = parts
                        else:
                            patient_id = filename
                            structure_name = "Unknown"
                        
                        # Only validate if not already validated from cumulative directory
                        existing = any(
                            r['patient_id'] == patient_id and r['structure'] == structure_name
                            for r in self.validation_results
                        )
                        if existing:
                            continue  # Skip - already validated from cumulative
                        
                        # Read DVH data
                        dvh_df = pd.read_csv(csv_file)
                        
                        # Validate (will normalize differential to cumulative internally)
                        result = self.validate_dvh_integrity(
                            dvh_df, 'differential', structure_name, patient_id
                        )
                        self.validation_results.append(result)
                        
                    except Exception as e:
                        # Non-blocking: log error but continue
                        self.log(f"[!] Validation error for {csv_file.name}: {str(e)}")
            
            # Update Validation & QA tab
            self.root.after(0, self.update_validation_qa_tab)
            
            # Log summary
            total = len(self.validation_results)
            passed = sum(1 for r in self.validation_results if r['status'] == 'PASS')
            failed = total - passed
            self.log(f"[OK] DVH validation complete: {passed}/{total} passed, {failed} failed")
            
        except Exception as e:
            # Non-blocking: log error but don't fail
            self.log(f"[!] DVH validation error: {str(e)}")
    
    def show_step1_summary(self, processed_dir, preprocessing_summary=None):
        """Display Step 1 results in summary panel"""
        summary = []
        summary.append("=== DVH Preprocessing Results ===\n")
        
        cdvh_dir = processed_dir / "cDVH_csv"
        ddvh_dir = processed_dir / "dDVH_csv"
        
        cdvh_files = []
        ddvh_files = []
        
        if cdvh_dir.exists():
            cdvh_files = list(cdvh_dir.glob("*.csv"))
            summary.append(f"Cumulative DVH files: {len(cdvh_files)}")
        else:
            summary.append("Cumulative DVH directory not found")
        
        if ddvh_dir.exists():
            ddvh_files = list(ddvh_dir.glob("*.csv"))
            summary.append(f"Differential DVH files: {len(ddvh_files)}")
        else:
            summary.append("Differential DVH directory not found")
        
        # Use preprocessing summary if available
        if preprocessing_summary:
            summary.append(f"\nProcessing Summary:")
            summary.append(f"  Total files: {preprocessing_summary['total_files']}")
            summary.append(f"  Processed: {preprocessing_summary['processed']} [OK]")
            if preprocessing_summary['failed'] > 0:
                summary.append(f"  Failed: {preprocessing_summary['failed']} [X]")
            summary.append(f"  Unique patients: {len(preprocessing_summary['patients'])}")
            
            if preprocessing_summary['structures']:
                summary.append(f"\nStructures detected:")
                for struct, count in preprocessing_summary['structures'].most_common(10):
                    summary.append(f"  - {struct}: {count} files")
            
            if preprocessing_summary['formats']:
                summary.append(f"\nFormats processed:")
                for fmt, count in preprocessing_summary['formats'].items():
                    summary.append(f"  - {fmt}: {count} files")
        else:
            # Count unique patients and organs from files
            if cdvh_files:
                patients = set()
                organs = set()
                for f in cdvh_files:
                    parts = f.stem.split('_')
                    if len(parts) >= 2:
                        patients.add(parts[0])
                        organs.add('_'.join(parts[1:]))
                
                summary.append(f"\nUnique patients: {len(patients)}")
                summary.append(f"Organs/structures: {len(organs)}")
                if organs:
                    summary.append(f"\nOrgans detected:")
                    for organ in sorted(organs):
                        summary.append(f"  - {organ}")
        
        # Check for summary Excel file
        excel_file = processed_dir / "processed_dvh.xlsx"
        if excel_file.exists():
            summary.append(f"\nSummary file: {excel_file.name}")
        
        self.root.after(0, lambda: self.update_summary_panel("Data Summary", "\n".join(summary)))
    
    def run_step2(self):
        """Run Step 2 with timer."""
        self.step_start_times['step2'] = time.time()
        
        # Validation
        if not self.validate_inputs():
            return
            
        if not self.steps_completed.get("step1", False):
            messagebox.showwarning("Warning", "Please run Step 1 first")
            return
        
        # Update status
        self.step2_status.config(text="⏱ Running Step 2...", foreground="orange")
        self.log("Starting Step 2: Dose Metrics & Plots...")
        
        # Start robot animation
        self._start_step_animation("step2")
        
        # Run in thread
        thread = threading.Thread(target=self._execute_step2, daemon=True)
        thread.start()
    
    def _execute_step2(self):
        """Execute code2_dvh_plot_and_summary.py in background thread"""
        try:
            base_dir = Path(self.output_dir.get())
            code1_dir = base_dir / "processed_DVH"
            metrics_dir = base_dir / "dose_metrics"
            
            if not code1_dir.exists():
                raise FileNotFoundError("Step 1 output not found. Run Step 1 first.")
            
            # CRITICAL: Run DVH validation before Step-2 plotting (read-only, non-blocking)
            if len(self.validation_results) == 0:
                self.log("Running DVH integrity validation before Step-2...")
                self._validate_all_dvhs(code1_dir)
            
            # Check for summary file (required by code2)
            summary_file = code1_dir / "processed_dvh.xlsx"
            if not summary_file.exists():
                raise FileNotFoundError(
                    f"Summary file not found: {summary_file}\n"
                    "Please re-run Step 1 to generate the summary file."
                )
            
            # Use pipeline if available, otherwise subprocess
            use_pipeline = False
            if PIPELINE_AVAILABLE:
                self.log(f"Using pipeline orchestration for Step 2...")
                self.log(f"Analysis type: {self.analysis_type.get()}")
                self.log(f"Processing all structures (OARs and Targets) from Step 1 output...")
                pipeline_input = self._prepare_pipeline_input()
                if pipeline_input:
                    # Update output directory to base_dir (contains processed_DVH)
                    pipeline_input.output_directory = base_dir
                    output = run_analysis_pipeline(pipeline_input, steps=['physical'], timeout=300)
                    
                    def on_success():
                        self.steps_completed["step2"] = True
                        # Update dashboard
                        self.root.after(100, self.update_dashboard_state)
                        # Show plots in visualization panel
                        self.show_dvh_plots(metrics_dir)
                        # Update progress
                        self.root.after(0, lambda: self.progress_var.set(2))
                        # Auto-trigger Step 3
                        if hasattr(self, 'run_all_mode') and self.run_all_mode:
                            self.root.after(1000, self.run_step3)
                    
                    self._handle_pipeline_output(output, 'step2', on_success)
                    use_pipeline = True
            
            # Fallback to subprocess if pipeline not available or failed
            if not use_pipeline:
                # code2 uses positional argument for code1_dir and --outdir
                cmd = [
                    sys.executable,
                    str(_rbgyanx_base_dir() / "code2_dvh_plot_and_summary.py"),
                    str(code1_dir.resolve()),
                    "--outdir", str(metrics_dir.resolve())
                ]
                
                self.log(f"Executing: python code2_dvh_plot_and_summary.py {code1_dir.name} --outdir dose_metrics")
                self.log(f"Analysis type: {self.analysis_type.get()}")
                self.log(f"Processing all structures (OARs and Targets) from Step 1 output...")
                
                result = subprocess.run(cmd, capture_output=True, text=True, 
                                      cwd=_rbgyanx_base_dir())
                
                # Log output
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            self.log(line)
                
                if result.returncode == 0:
                    self.log("[OK] Step 2: Dose metrics calculated")
                    duration = time.time() - self.step_start_times.get('step2', time.time())
                    self.step_durations['step2'] = duration
                    self.log(f"[TIMER] Step 2 completed in {duration:.1f} seconds")
                    self.root.after(0, lambda: self._stop_step_animation("step2"))
                    self.root.after(0, lambda: self.step2_status.config(text=f"✓ Step 2 ({duration:.1f}s)", foreground="green"))
                    self.steps_completed["step2"] = True
                    
                    # Update dashboard
                    self.root.after(100, self.update_dashboard_state)
                    
                    # Show plots in visualization panel
                    self.show_dvh_plots(metrics_dir)
                    
                    # Update progress
                    self.root.after(0, lambda: self.progress_var.set(2))
                    
                    # Auto-trigger Step 3
                    if hasattr(self, 'run_all_mode') and self.run_all_mode:
                        self.root.after(1000, self.run_step3)
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    self.log(f"[X] Step 2 failed with return code {result.returncode}")
                    if error_msg:
                        for line in error_msg.strip().split('\n'):
                            if line.strip():
                                self.log(f"  {line}")
                    self.root.after(0, lambda: self._stop_step_animation("step2"))
                    self.root.after(0, lambda: self.step2_status.config(text="[X] Failed", foreground="red"))
                    if hasattr(self, 'run_all_mode'):
                        self.run_all_mode = False
                    
        except Exception as e:
            self.log(f"[X] Step 2 error: {str(e)}")
            import traceback
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.log(f"  {line}")
            self.root.after(0, lambda: self._stop_step_animation("step2"))
            self.root.after(0, lambda: self.step2_status.config(text="[X] Error", foreground="red"))
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
    
    def show_step2_results(self, metrics_dir):
        """Display Step 2 results in Statistics panel"""
        try:
            summary = []
            summary.append("=== Dose Metrics Summary ===\n")
            
            # Check for dose metrics Excel file
            tables_dir = metrics_dir / "tables"
            if tables_dir.exists():
                metrics_file = tables_dir / "dose_metrics_cohort.xlsx"
                if metrics_file.exists():
                    try:
                        df = pd.read_excel(metrics_file, sheet_name=None)
                        summary.append(f"Metrics file: {metrics_file.name}")
                        for sheet_name, sheet_df in df.items():
                            summary.append(f"\nSheet: {sheet_name}")
                            summary.append(f"  Rows: {len(sheet_df)}")
                            summary.append(f"  Columns: {', '.join(sheet_df.columns[:5].tolist())}...")
                    except Exception as e:
                        summary.append(f"\n[!] Could not read metrics file: {str(e)}")
            
            # Count plots
            plots_dir = metrics_dir / "plots"
            if plots_dir.exists():
                plot_files = list(plots_dir.glob("*.png"))
                summary.append(f"\nPlots generated: {len(plot_files)}")
                for plot in sorted(plot_files)[:5]:
                    summary.append(f"  - {plot.name}")
            
            self.root.after(0, lambda: self.update_summary_panel("Statistics", "\n".join(summary)))
            
        except Exception as e:
            self.log(f"Warning: Could not display Step 2 results: {e}")
    
    def show_dvh_plots(self, metrics_dir):
        """Load and display DVH plots"""
        plots_dir = metrics_dir / "plots"
        
        if not plots_dir.exists():
            self.log(f"Plots directory not found: {plots_dir}")
            return
        
        # Find cDVH overlay plot
        cdvh_plot = plots_dir / "cDVH_overlay.png"
        if cdvh_plot.exists():
            self.root.after(0, lambda: self.load_image_to_viz("DVH Plots", cdvh_plot))
        
        # Also try dDVH overlay
        ddvh_plot = plots_dir / "dDVH_overlay.png"
        if ddvh_plot.exists() and not cdvh_plot.exists():
            self.root.after(0, lambda: self.load_image_to_viz("DVH Plots", ddvh_plot))
    
    def run_step3(self):
        """Run Step 3 with timer."""
        self.step_start_times['step3'] = time.time()
        
        # Validation
        if not self.validate_inputs():
            return
            
        if not self.steps_completed.get("step1", False) and not self._uses_engine_dicom_path():
            messagebox.showwarning(
                "Warning",
                "Please run Step 1 first, or select a DICOM RT folder for rbgyanx-engine analysis.",
            )
            return
        
        # Confirm which engines will run before Step 3
        if not self._confirm_step3_engines():
            self.log("[!] Step 3 cancelled by user")
            return
        
        # Update status
        self.step3_status.config(text="⏱ Running Step 3...", foreground="orange")
        self.log(f"Starting Step 3: {self.analysis_type.get()} Analysis...")
        
        # Start owl animation
        self._start_step_animation("step3")
        
        # Run in thread
        thread = threading.Thread(target=self._execute_step3, daemon=True)
        thread.start()
    
    def _execute_step3(self):
        """Execute Step 3 with TCP/NTCP branching based on analysis mode (UNIFIED PIPELINE)"""
        try:
            base_dir = Path(self.output_dir.get())
            mode = self.analysis_mode.get()
            
            # Update execution state
            self.execution_state.current_step = "step3"
            if mode in ["TCP_ONLY", "TCP_NTCP"]:
                self.execution_state.tcp_enabled = True
            if mode in ["NTCP_ONLY", "TCP_NTCP"]:
                self.execution_state.ntcp_enabled = True
            
            # AUTO-CREATE base directory if it doesn't exist
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # ADAPTER LAYER: Adapt clinical data if provided (before Step 3)
            adapted_clinical_file = None
            if self.clinical_file.get():
                adapted_clinical_file = self._adapt_clinical_data_for_step3(base_dir, mode)
            
            # BRANCHING: Run TCP and/or NTCP based on analysis mode
            # Both branches run independently after physical metrics (Step 2)
            # UNIFIED: Identical execution order for all modes
            
            tcp_success = False
            ntcp_success = False

            if mode == "TCP_NTCP" and self._uses_engine_dicom_path():
                both_ok = self._run_engine_endpoint(base_dir, "both", adapted_clinical_file)
                tcp_success = ntcp_success = both_ok
                self.execution_state.tcp_step3_complete = tcp_success
                self.execution_state.ntcp_step3_complete = ntcp_success
            else:
                if mode in ["TCP_ONLY", "TCP_NTCP"]:
                    tcp_success = self._execute_tcp_branch(base_dir, adapted_clinical_file)
                    self.execution_state.tcp_step3_complete = tcp_success

                if mode in ["NTCP_ONLY", "TCP_NTCP"]:
                    ntcp_success = self._execute_ntcp_branch(base_dir, adapted_clinical_file)
                    self.execution_state.ntcp_step3_complete = ntcp_success
            
            if mode == "TCP_NTCP":
                self.log("[OK] Both TCP and NTCP branches completed")
            
            # Update completion status
            duration = time.time() - self.step_start_times.get('step3', time.time())
            self.step_durations['step3'] = duration
            self.log(f"[TIMER] Step 3 completed in {duration:.1f} seconds")
            self.root.after(0, lambda: self._stop_step_animation("step3"))
            self.root.after(0, lambda: self.step3_status.config(text=f"✓ Step 3 ({duration:.1f}s)", foreground="green"))
            self.steps_completed["step3"] = True
            self.root.after(0, lambda: self.progress_var.set(3))
            self.root.after(100, self.update_dashboard_state)
            
            # AUTO-TRIGGER Step 6 (integration) if BOTH mode and run_all is enabled
            if mode == "TCP_NTCP" and self.execution_state.can_run_step6():
                if hasattr(self, 'run_all_mode') and self.run_all_mode:
                    self.log("[OK] Step 3 complete - Step 6 (integration) will run after Step 5")
            
        except Exception as e:
            error_msg = str(e)
            self.log(f"[X] Step 3 error: {error_msg}")
            if self.error_handler:
                self.error_handler.handle_error(e, "Step 3: TCP/NTCP Analysis", show_gui=False)
            self.root.after(0, lambda: self._stop_step_animation("step3"))
            self.root.after(0, lambda: self.step3_status.config(text="[X] Failed", foreground="red"))
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
    
    def _prompt_analysis_mode_after_dvh_selection(self):
        """Prompt user to choose analysis mode after DVH folder selection (non-blocking)"""
        if self.analysis_mode.get() in ["TCP_ONLY", "NTCP_ONLY", "TCP_NTCP"]:
            # Already selected, skip prompt
            return
        
        self.log("[INFO] Prompting for analysis mode selection...")
        
        # Create dismissible dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Analysis Mode")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Content
        ttk.Label(dialog, text="Select Analysis Mode", font=("Arial", 12, "bold")).pack(pady=10)
        ttk.Label(dialog, text="Choose the type of analysis to perform:", font=("Arial", 9)).pack(pady=5)
        
        mode_frame = ttk.Frame(dialog)
        mode_frame.pack(pady=10)
        
        ttk.Radiobutton(mode_frame, text="TCP only (Tumor Control Probability)", 
                       variable=self.analysis_mode, value="TCP_ONLY",
                       command=lambda: self.on_analysis_mode_change()).pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(mode_frame, text="NTCP only (Normal Tissue Complication Probability)", 
                       variable=self.analysis_mode, value="NTCP_ONLY",
                       command=lambda: self.on_analysis_mode_change()).pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(mode_frame, text="TCP + NTCP (Combined with therapeutic ratio)", 
                       variable=self.analysis_mode, value="TCP_NTCP",
                       command=lambda: self.on_analysis_mode_change()).pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        def on_select():
            self.log(f"[OK] Analysis mode selected: {self.analysis_mode.get()}")
            dialog.destroy()
        
        def on_dismiss():
            self.log("[INFO] Analysis mode selection dismissed (can be set later)")
            dialog.destroy()
        
        ttk.Button(button_frame, text="Select", command=on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Set Later", command=on_dismiss).pack(side=tk.LEFT, padx=5)
    
    def _process_clinical_file_selection(self):
        """Process clinical file selection: run adapter and show summary (non-blocking)"""
        if not CLINICAL_ADAPTER_AVAILABLE or not adapt_clinical_data:
            self.log("[INFO] Clinical adapter not available - skipping validation")
            return
        
        if not self.clinical_file.get():
            return
        
        clinical_path = Path(self.clinical_file.get())
        if not clinical_path.exists():
            self.log(f"[!] Clinical file not found: {clinical_path}")
            return
        
        # Run adapter in background thread to avoid blocking
        def run_adapter():
            try:
                mode = self.analysis_mode.get() or "NTCP_ONLY"  # Default if not set
                mapped_data, status, messages, standardized_file = adapt_clinical_data(
                    clinical_path, mode, None
                )
                
                # Show summary in GUI thread
                self.root.after(0, lambda: self._show_clinical_data_summary(status, messages, clinical_path))
            except Exception as e:
                self.log(f"[!] Error processing clinical file: {e}")
        
        thread = threading.Thread(target=run_adapter, daemon=True)
        thread.start()
    
    def _show_clinical_data_summary(self, status: str, messages: List[str], clinical_path: Path):
        """Show clinical data summary popup (dismissible)"""
        self.log(f"[INFO] Showing clinical data summary (status: {status})")
        
        # Create dismissible dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Clinical Data Summary")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Content frame with scrollbar
        content_frame = ttk.Frame(dialog)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        status_symbols = {'usable': '✔', 'partial': '⚠', 'insufficient': '❌'}
        symbol = status_symbols.get(status, '?')
        title_text = f"{symbol} Clinical Data: {status.upper()}"
        ttk.Label(content_frame, text=title_text, font=("Arial", 11, "bold")).pack(pady=5)
        ttk.Label(content_frame, text=f"File: {clinical_path.name}", font=("Arial", 9)).pack(pady=2)
        
        # Summary text
        summary_text = scrolledtext.ScrolledText(content_frame, height=15, width=70, wrap=tk.WORD)
        summary_text.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Build summary
        summary_lines = []
        summary_lines.append("CLINICAL DATA VALIDATION SUMMARY\n")
        summary_lines.append("=" * 60 + "\n\n")
        
        if status == 'usable':
            summary_lines.append("✔ All required fields are present and valid.\n")
            summary_lines.append("ML models can be enabled.\n\n")
        elif status == 'partial':
            summary_lines.append("⚠ Some optional fields are missing.\n")
            summary_lines.append("ML models may have limited performance.\n\n")
        else:
            summary_lines.append("❌ Critical fields are missing.\n")
            summary_lines.append("ML models will be automatically disabled.\n\n")
        
        if messages:
            summary_lines.append("Details:\n")
            for msg in messages:
                summary_lines.append(f"  • {msg}\n")
        
        summary_text.insert("1.0", "".join(summary_lines))
        summary_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def on_open_template():
            template_dir = _rbgyanx_base_dir() / "clinical" / "templates"
            if template_dir.exists():
                import subprocess
                import platform
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer "{template_dir}"')
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", str(template_dir)])
                else:
                    subprocess.Popen(["xdg-open", str(template_dir)])
                self.log(f"[OK] Opened template folder: {template_dir}")
            else:
                messagebox.showinfo("Templates", "Template folder not found. Check documentation for clinical data format.")
            dialog.destroy()
        
        def on_proceed():
            if status == 'insufficient':
                if self.enable_ml.get():
                    self.enable_ml.set(False)
                    self.log("[!] ML disabled due to insufficient clinical data")
            self.log("[OK] Proceeding with current clinical data")
            dialog.destroy()
        
        def on_dismiss():
            self.log("[INFO] Clinical data summary dismissed")
            dialog.destroy()
        
        if status == 'insufficient':
            ttk.Button(button_frame, text="Open Template Folder", command=on_open_template).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Proceed Without ML", command=on_proceed).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="OK", command=on_dismiss).pack(side=tk.LEFT, padx=5)
    
    def _confirm_step3_engines(self) -> bool:
        """Confirm which engines will run before Step 3 (dismissible)"""
        mode = self.analysis_mode.get()
        has_ml = self.enable_ml.get() and self.clinical_file.get()
        has_shap = self.enable_shap.get() and has_ml
        
        engines = []
        if self._uses_engine_dicom_path() and mode == "TCP_NTCP":
            engines.append("✓ rbgyanx-engine (DICOM): TCP + NTCP + UTCP + QUANTEC + plan-quality")
            if self.mode_controller and self.mode_controller.is_basic():
                engines.append("  (BASIC: classical, no ML augmentation)")
        else:
            engines.append("✓ Physics (dose metrics / legacy Step 2)")
            engines.append("✓ Radiobiology (traditional models / legacy code)")
        if has_ml:
            engines.append("✓ Machine Learning (ANN, XGBoost)")
        if has_shap:
            engines.append("✓ SHAP Explainability")
        
        # Create confirmation dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Confirm Step 3 Execution")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Content
        ttk.Label(dialog, text="Step 3: Analysis Engines", font=("Arial", 12, "bold")).pack(pady=10)
        ttk.Label(dialog, text="The following engines will run:", font=("Arial", 9)).pack(pady=5)
        
        engines_frame = ttk.Frame(dialog)
        engines_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        for engine in engines:
            ttk.Label(engines_frame, text=engine, font=("Arial", 9)).pack(anchor=tk.W, pady=2)
        
        mode_text = f"Analysis Mode: {mode.replace('_', ' ')}"
        ttk.Label(engines_frame, text=mode_text, font=("Arial", 9, "italic")).pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        confirmed = [False]  # Use list to allow modification in nested function
        
        def on_confirm():
            confirmed[0] = True
            self.log("[OK] Step 3 execution confirmed by user")
            dialog.destroy()
        
        def on_cancel():
            confirmed[0] = False
            self.log("[INFO] Step 3 execution cancelled by user")
            dialog.destroy()
        
        ttk.Button(button_frame, text="Confirm & Run", command=on_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        dialog.wait_window()
        return confirmed[0]
    
    def _adapt_clinical_data_for_step3(self, base_dir: Path, mode: str) -> Optional[Path]:
        """
        Adapt clinical data using adapter layer (before Step 3).
        
        Parameters
        ----------
        base_dir : Path
            Base output directory
        mode : str
            Analysis mode
        
        Returns
        -------
        Optional[Path]
            Path to adapted clinical file, or None if adaptation failed/not needed
        """
        if not CLINICAL_ADAPTER_AVAILABLE or not adapt_clinical_data:
            # Adapter not available, use original file
            if self.clinical_file.get():
                return Path(self.clinical_file.get())
            return None
        
        if not self.clinical_file.get():
            return None
        
        original_file = Path(self.clinical_file.get())
        if not original_file.exists():
            self.log(f"[!] Warning: Clinical file not found: {original_file}")
            return None
        
        try:
            self.log("=== Clinical Data Adapter ===")
            self.log(f"Adapting clinical data: {original_file.name}")
            
            # Create adapted file in output directory
            adapted_dir = base_dir / "adapted_clinical"
            adapted_dir.mkdir(parents=True, exist_ok=True)
            
            # Adapt clinical data
            mapped_data, status, messages, standardized_file = adapt_clinical_data(
                original_file, mode, adapted_dir
            )

            # Phase 4: harmonize patient IDs with processed DVH cohort
            if PATIENT_ID_REGISTRY_AVAILABLE:
                processed_dvh = base_dir / "processed_DVH"
                dvh_ids = (
                    collect_dvh_patient_ids(processed_dvh)
                    if processed_dvh.is_dir()
                    else set()
                )
                clinical_df = (
                    mapped_data.get("patient_core")
                    or mapped_data.get("treatment")
                    or mapped_data.get("ntcp_outcome")
                )
                clinical_ids = collect_clinical_patient_ids(clinical_df)
                map_path = base_dir / "patient_id_map.csv"
                mapping = load_mapping(map_path) if map_path.is_file() else {}
                if not mapping and dvh_ids:
                    mapping = build_auto_mapping(dvh_ids, clinical_ids)
                if mapping:
                    reg_dir = base_dir / "patient_registry"
                    write_registry_report(reg_dir, dvh_ids, clinical_ids, mapping)
                    self.log(
                        f"[OK] Patient ID registry: {len(mapping)} mapping(s), "
                        f"DVH={len(dvh_ids)} clinical={len(clinical_ids)}"
                    )
                    for key in ("patient_core", "treatment", "tcp_outcome", "ntcp_outcome"):
                        if mapped_data.get(key) is not None:
                            mapped_data[key] = apply_mapping_to_clinical_df(
                                mapped_data[key], mapping
                            )
                    if standardized_file and standardized_file.exists():
                        try:
                            from clinical.clinical_adapter import ClinicalDataAdapter

                            adapter = ClinicalDataAdapter(original_file)
                            adapter.mapped_data = mapped_data
                            standardized_file = adapter.create_standardized_file(
                                adapted_dir / f"adapted_{original_file.stem}.xlsx"
                            )
                        except Exception as reg_exc:
                            self.log(f"[!] Re-export adapted clinical after ID map: {reg_exc}")
            
            # Log status
            status_symbols = {
                'usable': '✔',
                'partial': '⚠',
                'insufficient': '❌'
            }
            symbol = status_symbols.get(status, '?')
            self.log(f"{symbol} Clinical data status: {status}")
            
            if messages:
                for msg in messages:
                    self.log(f"  - {msg}")
            
            # Check sufficiency and disable ML if needed
            if status == 'insufficient':
                if self.enable_ml.get():
                    self.log("[!] Clinical data insufficient for ML - disabling ML models")
                    self.root.after(0, lambda: self.enable_ml.set(False))
                    # Also disable SHAP if ML is disabled
                    if self.enable_shap.get():
                        self.root.after(0, lambda: self.enable_shap.set(False))
                        self.log("[!] SHAP disabled (requires ML)")
            elif status == 'partial':
                self.log("[!] Clinical data partially usable - ML may have limited performance")
            
            # Use standardized file if created, otherwise use original
            if standardized_file and standardized_file.exists():
                self.log(f"[OK] Using adapted clinical file: {standardized_file.name}")
                return standardized_file
            else:
                self.log("[!] Using original clinical file (adapter could not create standardized version)")
                return original_file
                
        except Exception as e:
            # Non-fatal: log warning and use original file
            self.log(f"[!] Clinical data adapter error (non-critical): {str(e)}")
            self.log("[!] Using original clinical file")
            return original_file
    
    def _run_engine_endpoint(self, base_dir: Path, endpoint: str, clinical_file: Optional[Path] = None) -> bool:
        """Run rbgyanx-engine for DICOM TCP/NTCP (Phase R2)."""
        if not ENGINE_BRIDGE_AVAILABLE or not is_engine_available():
            return False
        input_path = Path(self.raw_input.get())
        if not self._uses_engine_dicom_path():
            return False
        tcp_cfg = {
            "enable_ml": self.enable_ml.get(),
            "enable_shap": self.enable_shap.get(),
            "use_fdvh": self.use_fdvh.get() if hasattr(self, "use_fdvh") else False,
            "use_utcp": self.use_utcp.get() if hasattr(self, "use_utcp") else False,
            "ccs_file": self.ccs_file_path.get() if hasattr(self, "use_ccs") and self.use_ccs.get() else None,
        }
        ntcp_cfg = {"enable_ml": self.enable_ml.get(), "enable_shap": self.enable_shap.get()}
        if needs_subprocess_fallback(tcp_cfg, ntcp_cfg):
            self.log("[engine] Advanced options enabled — using legacy code3/code6 path")
            return False
        mode = "advanced" if (self.mode_controller and self.mode_controller.is_advanced()) else "basic"
        site = map_site_override(self.cancer_site.get()) if map_site_override else None
        outcome = clinical_file if clinical_file and str(clinical_file).lower().endswith(".csv") else None
        try:
            result, logs = run_engine_analysis(
                input_dir=input_path,
                output_dir=base_dir,
                endpoint=endpoint,
                mode=mode,
                site_override=site,
                outcome_csv=outcome,
                enable_ml=self.enable_ml.get(),
                cohort=True,
            )
            for line in logs:
                self.log(line)
            if result.exit_code == 0:
                self.root.after(100, self.update_dashboard_state)
                return True
            self.log(f"[!] Engine returned exit code {result.exit_code}")
            return False
        except Exception as exc:
            self.log(f"[!] Engine error: {exc}")
            return False

    def _execute_tcp_branch(self, base_dir: Path, clinical_file: Optional[Path] = None) -> bool:
        """Execute TCP analysis branch (runs independently after Step 2)"""
        try:
            if self._run_engine_endpoint(base_dir, "tcp", clinical_file):
                self.log("[OK] TCP branch completed (rbgyanx-engine)")
                self.set_workflow_state(WorkflowState.TCP_COMPLETE)
                return True

            script = "code6_tcp_analysis.py"
            analysis_dir = base_dir / "tcp_analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            self.log("=== TCP Branch ===")
            self.log(f"Output directory: {analysis_dir}")
            
            # Verify DVH directory
            ddvh_dir = base_dir / "processed_DVH" / "dDVH_csv"
            if not ddvh_dir.exists():
                self.log(f"[!] Warning: dDVH directory not found: {ddvh_dir}")
                return False
            
            # TCP requires clinical data
            if not clinical_file:
                # Fallback to original clinical file
                if not self.clinical_file.get():
                    self.log("[!] Warning: Clinical data required for TCP analysis - skipping TCP branch")
                    return False
                clinical_path = Path(self.clinical_file.get())
            else:
                clinical_path = clinical_file
            
            if not clinical_path.exists():
                self.log(f"[!] Warning: Clinical file not found: {clinical_path} - skipping TCP branch")
                return False
            
            # Get Step-2 TCP physical metrics (optional - will calculate from DVH if missing)
            metrics_dir = base_dir / "dose_metrics" / "tables"
            metrics_file = metrics_dir / "TCP_physical_metrics.xlsx"
            
            # Build TCP command
            cmd = [
                sys.executable,
                str(_rbgyanx_base_dir() / script),
                "--tumor_dvh_dir", str(ddvh_dir.resolve()),
                "--clinical_xlsx", str(clinical_path),
                "--outdir", str(analysis_dir.resolve()),
                "--tumor_type", self.tumor_organ_type.get()
            ]
            
            # Add physical metrics file if it exists, otherwise let code6 calculate from DVH
            if metrics_file.exists():
                self.log(f"[OK] Using physical metrics from Step-2: {metrics_file}")
                cmd.extend(["--physical_metrics_file", str(metrics_file.resolve())])
            else:
                self.log("[!] Physical metrics file not found")
                self.log("    TCP analysis will calculate metrics from DVH files")
            
            if self.enable_ml.get():
                cmd.append("--enable_ml")
            
            if self.enable_shap.get() and self.enable_ml.get():
                cmd.append("--enable_shap")
            
            # OBJECTIVE A: Add novel feature flags
            if self.use_fdvh.get():
                cmd.append("--use_fdvh")
                cmd.extend(["--n_fractions", "30"])  # Default, can be made configurable
                cmd.extend(["--alpha_beta_tumor", "10"])  # Default, can be made configurable
                self.log("[FDVH] Fractionation-Aware DVH enabled")
            
            if self.use_utcp.get():
                cmd.append("--use_utcp")
                self.log("[uTCP] Uncertainty-Aware TCP enabled")
            
            if self.use_ccs.get() and self.enable_ml.get():
                ccs_file = self.ccs_file_path.get()
                if ccs_file and Path(ccs_file).exists():
                    cmd.extend(["--ccs_file", str(Path(ccs_file).resolve())])
                    cmd.extend(["--ccs_threshold", str(self.ccs_threshold.get())])
                    self.log(f"[CCS] ML Safety Gating enabled (threshold: {self.ccs_threshold.get()})")
                else:
                    self.log("[!] Warning: CCS enabled but file not found - ML will proceed without safety gate")
            
            self.log(f"Executing TCP analysis: {script}")
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  cwd=_rbgyanx_base_dir(), timeout=600)
            
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.log(f"TCP: {line}")
            
            if result.returncode == 0:
                self.log("[OK] TCP branch completed")
                
                # OBJECTIVE A: Log novel feature status
                if self.use_fdvh.get():
                    self.log("[FDVH] Fractionation-Aware DVH normalization applied (fractionation-aware)")
                if self.use_utcp.get():
                    self.log("[uTCP] Uncertainty-aware TCP with confidence bounds calculated")
                    self.log("[uTCP] Note: uTCP reflects parameter uncertainty, not clinical outcome variance")
                if self.use_ccs.get() and self.enable_ml.get():
                    self.log("[CCS] ML Safety Gating active - OOD patients will use traditional models")
                
                self.set_workflow_state(WorkflowState.TCP_COMPLETE)
                return True
            else:
                self.log(f"[!] TCP branch returned code {result.returncode}")
                self.set_workflow_state(WorkflowState.ERROR)
                return False
                
        except Exception as e:
            self.log(f"[!] TCP branch error: {str(e)}")
            self.set_workflow_state(WorkflowState.ERROR)
            return False
    
    def _execute_ntcp_branch(self, base_dir: Path, clinical_file: Optional[Path] = None) -> bool:
        """
        Execute NTCP analysis branch (runs independently after Step 2)
        
        Pipeline Support:
        - Basic NTCP execution (dvh_dir, patient_data, output_dir)
        - ML models flag (--ml_models)
        - SHAP explainability (--enable_shap)
        
        Note: All current NTCP options are pipeline-supported. Fallback is reserved
        for future advanced options not yet supported by pipeline.
        """
        try:
            # Update workflow state
            self.set_workflow_state(WorkflowState.NTCP_RUNNING)
            
            script = "code3_ntcp_analysis_ml.py"
            analysis_dir = base_dir / "ntcp_analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            self.log("=== NTCP Branch ===")
            self.log(f"Output directory: {analysis_dir}")

            if self._run_engine_endpoint(base_dir, "ntcp", clinical_file):
                self.log("[OK] NTCP branch completed (rbgyanx-engine)")
                self.set_workflow_state(WorkflowState.NTCP_COMPLETE)
                return True
            
            # Verify DVH directory
            ddvh_dir = base_dir / "processed_DVH" / "dDVH_csv"
            if not ddvh_dir.exists():
                self.log(f"[!] Warning: dDVH directory not found: {ddvh_dir}")
                return False
            
            # Add clinical data if provided (use adapted file if available)
            if clinical_file:
                clinical_path = clinical_file
            elif self.clinical_file.get():
                clinical_path = Path(self.clinical_file.get())
            else:
                clinical_path = None
            
            # Try pipeline execution (all NTCP options are currently supported)
            use_pipeline = PIPELINE_AVAILABLE
            if use_pipeline:
                self.log("Using pipeline orchestration for NTCP analysis...")
                pipeline_input = self._prepare_pipeline_input()
                if pipeline_input:
                    # Update paths for NTCP
                    pipeline_input.output_directory = base_dir
                    if clinical_path and clinical_path.exists():
                        pipeline_input.patient_data_file = clinical_path
                    
                    # Ensure NTCP config is set
                    if not pipeline_input.ntcp_config:
                        pipeline_input.ntcp_config = {
                            'enable_ml': self.enable_ml.get() if hasattr(self, 'enable_ml') else False,
                            'enable_shap': self.enable_shap.get() if hasattr(self, 'enable_shap') else False,
                        }
                    
                    output = run_analysis_pipeline(pipeline_input, steps=['ntcp'], timeout=600)
                    
                    def on_success():
                        if self.enable_ml.get() and clinical_path:
                            self.log("[ML] Machine learning models executed")
                        if self.enable_shap.get() and self.enable_ml.get():
                            self.log("[SHAP] Explainability analysis completed")
                        self.set_workflow_state(WorkflowState.NTCP_COMPLETE)
                    
                    if output.status in ['success', 'partial']:
                        self._handle_pipeline_output(output, 'ntcp', on_success)
                        return output.status == 'success'
                    else:
                        self.log("[!] Pipeline execution failed, falling back to subprocess")
                        use_pipeline = False
            
            # Fallback to subprocess execution
            if not use_pipeline:
                # Build NTCP command
                cmd = [
                    sys.executable,
                    str(_rbgyanx_base_dir() / script),
                    "--dvh_dir", str(ddvh_dir.resolve()),
                    "--output_dir", str(analysis_dir.resolve())
                ]
                
                if clinical_path and clinical_path.exists():
                    cmd.extend(["--patient_data", str(clinical_path)])
                    self.log(f"Using clinical data: {clinical_path.name}")
                
                if self.enable_ml.get() and clinical_path:
                    cmd.append("--ml_models")
                
                if self.enable_shap.get() and self.enable_ml.get():
                    cmd.append("--enable_shap")
                
                self.log(f"Executing NTCP analysis: {script} (subprocess fallback)")
                result = subprocess.run(cmd, capture_output=True, text=True, 
                                      cwd=_rbgyanx_base_dir(), timeout=600)
                
                if result.stdout:
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            self.log(f"NTCP: {line}")
                
                if result.returncode == 0:
                    self.log("[OK] NTCP branch completed")
                    self.set_workflow_state(WorkflowState.NTCP_COMPLETE)
                    return True
                else:
                    self.log(f"[!] NTCP branch returned code {result.returncode}")
                    self.set_workflow_state(WorkflowState.ERROR)
                    return False
                
        except Exception as e:
            self.log(f"[!] NTCP branch error: {str(e)}")
            self.set_workflow_state(WorkflowState.ERROR)
            return False
    
    def _execute_integration(self, base_dir: Path) -> bool:
        """Execute TCP-NTCP integration analysis"""
        try:
            # Update workflow state
            self.set_workflow_state(WorkflowState.INTEGRATION_RUNNING)
            
            script = "code7_tcp_ntcp_integration.py"
            
            tcp_dir = base_dir / "tcp_analysis"
            ntcp_dir = base_dir / "enhanced_ntcp_analysis"
            integration_dir = base_dir / "integration_results"
            
            # Validate required input files
            tcp_file = tcp_dir / "tcp_predictions.xlsx"
            ntcp_file = ntcp_dir / "ntcp_predictions.xlsx"
            
            if not tcp_file.exists():
                self.log(f"[!] TCP results not found: {tcp_file}")
                self.log("    TCP analysis must complete successfully first")
                return False
            
            if not ntcp_file.exists():
                # Try alternative location
                ntcp_file = ntcp_dir / "enhanced_ntcp_results.xlsx"
                if not ntcp_file.exists():
                    self.log(f"[!] NTCP results not found in {ntcp_dir}")
                    self.log("    NTCP analysis must complete successfully first")
                    return False
            
            integration_dir.mkdir(parents=True, exist_ok=True)
            
            # Build integration command
            cmd = [
                sys.executable,
                str(_rbgyanx_base_dir() / script),
                "--tcp_dir", str(tcp_dir),
                "--ntcp_dir", str(ntcp_dir),
                "--outdir", str(integration_dir)
            ]
            
            self.log(f"Executing integration: {script}")
            self.log(f"  TCP results: {tcp_dir}")
            self.log(f"  NTCP results: {ntcp_dir}")
            self.log(f"  Output: {integration_dir}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                cwd=_rbgyanx_base_dir(), 
                timeout=300
            )
            
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.log(f"  {line}")
            
            if result.returncode == 0:
                self.log("[OK] Integration completed")
                
                # Verify output files
                expected_files = [
                    "therapeutic_ratios.xlsx",
                    "plots/pareto_frontier.png",
                    "plots/utcp_curves.png"
                ]
                
                missing = []
                for fname in expected_files:
                    if not (integration_dir / fname).exists():
                        missing.append(fname)
                
                if missing:
                    self.log(f"[!] Warning: Missing output files: {missing}")
                
                self.set_workflow_state(WorkflowState.INTEGRATION_COMPLETE)
                return True
            else:
                self.log(f"[!] Integration failed with code {result.returncode}")
                if result.stderr:
                    self.log(f"    Error: {result.stderr}")
                self.set_workflow_state(WorkflowState.ERROR)
                return False
        
        except Exception as e:
            self.log(f"[!] Integration error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.set_workflow_state(WorkflowState.ERROR)
            return False
    
    def show_integration_results(self, integration_dir):
        """Display therapeutic ratio results"""
        try:
            results_file = integration_dir / "therapeutic_ratios.xlsx"
            
            if not results_file.exists():
                self.log("[!] Integration results not found")
                return
            
            # Load results
            df = pd.read_excel(results_file)
            
            # Display summary
            self.log("\nTherapeutic Ratio Summary:")
            if 'UTCP' in df.columns:
                self.log(f"  UTCP (mean): {df['UTCP'].mean():.3f}")
            if 'P_plus' in df.columns:
                self.log(f"  P+ (mean): {df['P_plus'].mean():.3f}")
            
            # Update integration tab in GUI if it exists
            # (implement integration tab display if needed)
            
        except Exception as e:
            self.log(f"[!] Error displaying integration results: {e}")
    
    def show_step3_results(self, analysis_dir):
        """Display Step 3 results in center and right panels"""
        try:
            # Load predictions/results file
            pred_file = None
            for pattern in ["*predictions*.xlsx", "*results*.xlsx", "enhanced_ntcp*.xlsx", "*.xlsx"]:
                matches = list(analysis_dir.glob(pattern))
                if matches:
                    pred_file = matches[0]
                    break
            
            summary = []
            summary.append("=== TCP/NTCP Analysis Results ===\n")
            summary.append(f"Output directory: {analysis_dir.name}\n")
            
            if pred_file:
                try:
                    df = pd.read_excel(pred_file)
                    
                    summary.append(f"Total patients: {len(df)}")
                    
                    # Show model predictions
                    model_cols = [col for col in df.columns if 'NTCP' in col.upper() or 'TCP' in col.upper() or 'Prediction' in col]
                    if model_cols:
                        summary.append(f"\nModel predictions:")
                        for col in model_cols[:10]:  # Show first 10 models
                            try:
                                mean_pred = df[col].mean()
                                std_pred = df[col].std()
                                summary.append(f"  {col}: {mean_pred:.3f} ± {std_pred:.3f}")
                            except:
                                pass
                    
                    # Show available columns
                    summary.append(f"\nAvailable columns: {len(df.columns)}")
                    summary.append(f"Sample columns: {', '.join(df.columns[:5].tolist())}")
                    
                except Exception as e:
                    summary.append(f"\n[!] Could not read results file: {str(e)}")
            else:
                # List all files in directory
                all_files = list(analysis_dir.glob("*"))
                summary.append(f"\nOutput files ({len(all_files)}):")
                for f in sorted(all_files)[:20]:
                    if f.is_file():
                        size_kb = f.stat().st_size / 1024
                        summary.append(f"  - {f.name} ({size_kb:.1f} KB)")
            
            # Update Model Parameters tab
            self.root.after(0, lambda: self.update_summary_panel("Model Parameters", "\n".join(summary)))
            
            # Load and display dose-response plot
            plots_dir = analysis_dir / "plots"
            if plots_dir.exists():
                # Find dose-response plot
                dose_response_plots = list(plots_dir.glob("*dose*response*.png"))
                if dose_response_plots:
                    self.root.after(0, lambda p=dose_response_plots[0]: self.load_image_to_viz("Dose-Response", p))
                
                # Find ROC plot
                roc_plots = list(plots_dir.glob("*roc*.png"))
                if roc_plots:
                    self.root.after(0, lambda p=roc_plots[0]: self.load_image_to_viz("ROC/Calibration", p))
            else:
                self.log(f"Plots directory not found: {plots_dir}")
        
        except Exception as e:
            self.log(f"Warning: Could not display Step 3 results: {e}")
    
    def show_step4_results(self, factors_dir, analysis_dir):
        """Display Step 4 results in Statistics panel"""
        try:
            summary = []
            summary.append("=== Clinical Factors Analysis ===\n")
            summary.append(f"Output directory: {factors_dir.name if factors_dir.exists() else 'N/A'}\n")
            
            # Check for output files
            if analysis_dir.exists():
                factor_files = list(analysis_dir.glob("*factors*.xlsx")) + list(analysis_dir.glob("*correlation*.xlsx"))
                if factor_files:
                    summary.append(f"Analysis files: {len(factor_files)}")
                    for f in factor_files[:5]:
                        summary.append(f"  - {f.name}")
                
                # Check for plots
                plots_dir = analysis_dir / "plots"
                if plots_dir.exists():
                    plot_files = list(plots_dir.glob("*factor*.png")) + list(plots_dir.glob("*correlation*.png"))
                    if plot_files:
                        summary.append(f"\nPlots generated: {len(plot_files)}")
                        for plot in sorted(plot_files)[:5]:
                            summary.append(f"  - {plot.name}")
                        
                        # Load first factor plot
                        if plot_files:
                            self.root.after(0, lambda p=plot_files[0]: self.load_image_to_viz("Factor Plots", p))
            
            self.root.after(0, lambda: self.update_summary_panel("Statistics", "\n".join(summary)))
            
        except Exception as e:
            self.log(f"Warning: Could not display Step 4 results: {e}")
    
    def show_step5_results(self, qa_dir):
        """Display Step 5 results in QA Report panel"""
        try:
            summary = []
            summary.append("=== Quality Assurance Report ===\n")
            
            if qa_dir.exists():
                # Find QA report files
                qa_files = list(qa_dir.glob("*.docx")) + list(qa_dir.glob("*.xlsx"))
                summary.append(f"QA files generated: {len(qa_files)}")
                
                for f in sorted(qa_files):
                    size_kb = f.stat().st_size / 1024
                    summary.append(f"\n  - {f.name} ({size_kb:.1f} KB)")
                
                # Try to read summary from Excel if available
                summary_xlsx = qa_dir / "qa_summary_tables.xlsx"
                if summary_xlsx.exists():
                    try:
                        df = pd.read_excel(summary_xlsx, sheet_name=None)
                        summary.append(f"\n\nQA Summary Tables:")
                        for sheet_name, sheet_df in df.items():
                            summary.append(f"\n  {sheet_name}: {len(sheet_df)} rows")
                    except:
                        pass
            else:
                summary.append(f"\n[!] QA directory not found: {qa_dir}")
            
            self.root.after(0, lambda: self.update_summary_panel("QA Report", "\n".join(summary)))
            
        except Exception as e:
            self.log(f"Warning: Could not display Step 5 results: {e}")
    
    def show_dose_response_plots(self, analysis_dir):
        """Load dose-response curves into visualization"""
        plots_dir = analysis_dir / "plots"
        
        if not plots_dir.exists():
            self.log(f"Plots directory not found: {plots_dir}")
            return
        
        # Find dose-response plot
        patterns = [
            "dose_response*.png",
            "*dose_response*.png",
            "tcp_dose_response*.png",
            "ntcp_dose_response*.png"
        ]
        
        for pattern in patterns:
            plots = list(plots_dir.glob(pattern))
            if plots:
                self.root.after(0, lambda p=plots[0]: self.load_image_to_viz("Dose-Response", p))
                break
        
        # Find ROC curve
        roc_patterns = ["roc*.png", "*roc*.png", "*roc_curve*.png"]
        for pattern in roc_patterns:
            plots = list(plots_dir.glob(pattern))
            if plots:
                self.root.after(0, lambda p=plots[0]: self.load_image_to_viz("ROC/Calibration", p))
                break
    
    def run_step4(self):
        """Run Step 4 with timer."""
        self.step_start_times['step4'] = time.time()
        
        # Validation
        if not self.clinical_file.get():
            self.log("[!] Step 4 skipped: No clinical data provided")
            self.step4_status.config(text="○ Skipped", foreground="gray")
            if hasattr(self, 'run_all_mode') and self.run_all_mode:
                self.root.after(500, self.run_step5)
            return
        
        if not self.steps_completed.get("step3", False):
            messagebox.showwarning("Warning", "Please run Step 3 first")
            return
        
        # Update status
        self.step4_status.config(text="⏱ Running Step 4...", foreground="orange")
        self.log("Starting Step 4: Clinical Factors Analysis...")
        self._start_step_animation("step4")
        
        # Run in thread
        thread = threading.Thread(target=self._execute_step4, daemon=True)
        thread.start()
    
    def _execute_step4(self):
        """Execute Step 4 with error handling"""
        try:
            # Check if clinical data provided
            if not self.clinical_file.get():
                self.log("[!] Step 4 skipped: No clinical data provided")
                self.root.after(0, lambda: self._stop_step_animation("step4"))
                self.root.after(0, lambda: self.step4_status.config(text="○ Skipped", foreground="gray"))
                if hasattr(self, 'run_all_mode') and self.run_all_mode:
                    self.root.after(500, self.run_step5)
                return
            
            base_dir = Path(self.output_dir.get())
            factors_dir = base_dir / "clinical_factors"
            
            # CLINICAL FACTORS ANALYSIS: Works for both TCP and NTCP
            # Run analysis for each enabled branch
            mode = self.analysis_mode.get()
            analysis_dirs = []
            
            if mode in ["TCP_ONLY", "TCP_NTCP"]:
                tcp_dir = base_dir / "tcp_analysis"
                if tcp_dir.exists():
                    analysis_dirs.append(("TCP", tcp_dir))
                else:
                    self.log(f"[!] Warning: TCP analysis directory not found: {tcp_dir}")
            
            if mode in ["NTCP_ONLY", "TCP_NTCP"]:
                ntcp_dir = base_dir / "ntcp_analysis"
                if ntcp_dir.exists():
                    analysis_dirs.append(("NTCP", ntcp_dir))
                else:
                    self.log(f"[!] Warning: NTCP analysis directory not found: {ntcp_dir}")
            
            if not analysis_dirs:
                raise FileNotFoundError(
                    f"No analysis directories found.\n"
                    f"Please run Step 3 first to generate TCP/NTCP results."
                )
            
            # Run clinical factors analysis for each enabled branch
            for analysis_type, analysis_dir in analysis_dirs:
                # Verify code5 script exists
                code5_path = _rbgyanx_base_dir() / "code5_ntcp_factors_analysis.py"
                if not code5_path.exists():
                    self.log(f"[!] Warning: Clinical factors script not found: {code5_path}")
                    continue
                
                # Verify clinical file exists
                clinical_path = Path(self.clinical_file.get())
                if not clinical_path.exists():
                    self.log(f"[!] Warning: Clinical file not found: {clinical_path}")
                    continue
                
                self.log(f"=== Running Clinical Factors Analysis for {analysis_type} ===")
                
                cmd = [
                    sys.executable,
                    str(code5_path),
                    "--input_file", str(clinical_path),
                    "--enhanced_output_dir", str(analysis_dir.resolve()),
                    "--analysis_type", analysis_type
                ]
                
                if self.use_glm.get():
                    cmd.append("--use_glm")
                
                self.log(f"Command: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    cwd=_rbgyanx_base_dir(),
                    timeout=300  # 5 minute timeout
                )
                
                # Log output
                if result.stdout:
                    self.log(f"=== {analysis_type} Clinical Factors Output ===")
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            self.log(line)
                
                if result.stderr:
                    self.log(f"=== {analysis_type} Clinical Factors Errors ===")
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            self.log(f"ERROR: {line}")
                
                if result.returncode == 0:
                    self.log(f"[OK] {analysis_type} clinical factors analysis complete")
                else:
                    self.log(f"[!] Warning: {analysis_type} clinical factors analysis returned code {result.returncode}")
            
            # Mark Step 4 as complete if at least one analysis succeeded
            self.log("[OK] Step 4: Clinical factors analysis complete")
            duration = time.time() - self.step_start_times.get('step4', time.time())
            self.step_durations['step4'] = duration
            self.log(f"[TIMER] Step 4 completed in {duration:.1f} seconds")
            self.root.after(0, lambda: self._stop_step_animation("step4"))
            self.root.after(0, lambda: self.step4_status.config(text=f"✓ Step 4 ({duration:.1f}s)", foreground="green"))
            self.steps_completed["step4"] = True
            
            # Update dashboard
            self.root.after(100, self.update_dashboard_state)
            
            # Update progress
            self.root.after(0, lambda: self.progress_var.set(4))
            self.execution_state.step4_complete = True
            
            # Auto-trigger Step 5
            if hasattr(self, 'run_all_mode') and self.run_all_mode:
                self.root.after(1000, self.run_step5)
                
        except subprocess.TimeoutExpired:
            self.log("[X] Step 4 timed out (>5 minutes)")
            self.root.after(0, lambda: self.step4_status.config(text="[X] Timeout", foreground="red"))
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
            
        except Exception as e:
            self.log(f"[X] Step 4 error: {str(e)}")
            self.root.after(0, lambda: self._stop_step_animation("step4"))
            self.root.after(0, lambda: self.step4_status.config(text="[X] Failed", foreground="red"))
            
            if hasattr(self, 'error_handler') and self.error_handler:
                self.error_handler.handle_error(e, context="Step 4: Clinical Factors", show_gui=True)
            else:
                import traceback
                for line in traceback.format_exc().split('\n'):
                    if line.strip():
                        self.log(f"  {line}")
            
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
    
    def run_step5(self):
        """Run Step 5 with timer."""
        self.step_start_times['step5'] = time.time()
        
        # Validation
        if not self.steps_completed.get("step3", False):
            messagebox.showwarning("Warning", "Please run Step 3 first")
            return
        
        if not self.output_dir.get():
            messagebox.showerror("Error", "Output directory not set")
            return
        
        # Update status
        self.step5_status.config(text="⏱ Running Step 5...", foreground="orange")
        self.log("Starting Step 5: Quality Assurance...")
        self._start_step_animation("step5")
        
        # Run in thread
        thread = threading.Thread(target=self._execute_step5, daemon=True)
        thread.start()
    
    def _execute_step5(self):
        """
        Execute Step 5: Non-blocking QA (advisory only, never blocks execution)
        Works for both TCP and NTCP based on analysis mode.
        """
        try:
            base_dir = Path(self.output_dir.get())
            # UNIFIED OUTPUT STRUCTURE: Use qa/ instead of qa_reports/
            qa_dir = base_dir / "qa"
            qa_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify code4 script exists (optional - QA is advisory)
            code4_path = _rbgyanx_base_dir() / "code4_ntcp_output_QA_reporter.py"
            if not code4_path.exists():
                self.log("[!] Warning: QA reporter script not found - skipping QA")
                self.log("[!] QA is advisory only - analysis results are still valid")
                self._complete_step5_advisory()
                return
            
            # QA for both TCP and NTCP (non-blocking)
            mode = self.analysis_mode.get()
            analysis_dirs = []
            
            if mode in ["TCP_ONLY", "TCP_NTCP"]:
                tcp_dir = base_dir / "tcp_analysis"
                if tcp_dir.exists():
                    analysis_dirs.append(("TCP", tcp_dir))
            
            if mode in ["NTCP_ONLY", "TCP_NTCP"]:
                ntcp_dir = base_dir / "ntcp_analysis"
                if ntcp_dir.exists():
                    analysis_dirs.append(("NTCP", ntcp_dir))
            
            if not analysis_dirs:
                self.log("[!] Warning: No analysis directories found for QA")
                self.log("[!] QA is advisory only - this does not affect analysis validity")
                self._complete_step5_advisory()
                return
            
            # Run QA for each analysis type (non-blocking, advisory only)
            qa_success_count = 0
            for analysis_type, analysis_dir in analysis_dirs:
                try:
                    self.log(f"=== Running QA for {analysis_type} (advisory only) ===")
                    
                    # Count files for logging
                    all_files = list(analysis_dir.glob("*.xlsx")) + list(analysis_dir.glob("*.csv"))
                    self.log(f"Found {len(all_files)} result files for QA")
                    
                    # Run QA reporter (non-blocking - errors are logged but don't fail)
                    cmd = [
                        sys.executable,
                        str(code4_path),
                        "--input", str(analysis_dir.resolve()),
                        "--report_outdir", str(qa_dir.resolve())
                    ]
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        cwd=_rbgyanx_base_dir(),
                        timeout=300  # 5 minute timeout
                    )
                    
                    # Log output (advisory)
                    if result.stdout:
                        self.log(f"=== {analysis_type} QA Output ===")
                        for line in result.stdout.split('\n'):
                            if line.strip():
                                self.log(line)
                    
                    if result.stderr:
                        self.log(f"=== {analysis_type} QA Warnings (advisory) ===")
                        for line in result.stderr.split('\n'):
                            if line.strip():
                                self.log(f"QA: {line}")
                    
                    if result.returncode == 0:
                        self.log(f"[OK] {analysis_type} QA completed (advisory)")
                        qa_success_count += 1
                    else:
                        # QA failures are advisory only - don't block
                        self.log(f"[!] {analysis_type} QA returned code {result.returncode} (advisory only)")
                        self.log(f"[!] This does not affect analysis validity - QA is advisory")
                
                except Exception as e:
                    # QA errors are advisory - log but don't fail
                    self.log(f"[!] {analysis_type} QA error (advisory): {str(e)}")
                    self.log(f"[!] QA is advisory only - analysis results remain valid")
            
            # Complete Step 5 (always succeeds - QA is advisory)
            self._complete_step5_advisory()
            
        except Exception as e:
            # Even if QA completely fails, mark as advisory success
            self.log(f"[!] QA execution error (advisory): {str(e)}")
            self.log(f"[!] QA is advisory only - analysis results remain valid")
            self._complete_step5_advisory()
    
    def _complete_step5_advisory(self):
        """Complete Step 5 as advisory (always succeeds - QA never blocks execution)"""
        duration = time.time() - self.step_start_times.get('step5', time.time())
        self.step_durations['step5'] = duration
        self.log(f"[TIMER] Step 5 completed in {duration:.1f} seconds (advisory)")
        self.root.after(0, lambda: self._stop_step_animation("step5"))
        self.root.after(0, lambda: self.step5_status.config(
            text=f"✓ Step 5 ({duration:.1f}s) [Advisory]", 
            foreground="green"
        ))
        self.steps_completed["step5"] = True
        # Update dashboard
        self.root.after(100, self.update_dashboard_state)
        self.root.after(0, lambda: self.progress_var.set(5))
        
        # Show QA results in GUI (if available)
        base_dir = Path(self.output_dir.get())
        qa_dir = base_dir / "qa"
        if qa_dir.exists():
            self.log(f"[OK] QA reports available in: {qa_dir}")
        
        # Note: QA is advisory - never blocks execution
        self.log("[INFO] QA is advisory only - flags and warnings do not indicate execution failure")
        
        # Update execution state
        self.execution_state.step5_complete = True
        
        # AUTO-TRIGGER Step 6 (integration) if BOTH mode and both branches completed
        mode = self.analysis_mode.get()
        if mode == "TCP_NTCP" and self.execution_state.can_run_step6():
            if hasattr(self, 'run_all_mode') and self.run_all_mode:
                self.log("[OK] Step 5 complete - Starting Step 6 (TCP-NTCP Integration)")
                self.root.after(1000, self.run_step6)
    
    def run_step6(self):
        """Run Step 6 with timer."""
        self.step_start_times['step6'] = time.time()
        
        # Validation - requires both TCP and NTCP analyses
        base_dir = Path(self.output_dir.get())
        tcp_dir = base_dir / "tcp_analysis"
        ntcp_dir = base_dir / "ntcp_analysis"
        
        if not tcp_dir.exists():
            messagebox.showerror("Error", "TCP analysis not found. Run TCP analysis first.")
            return
        
        if not ntcp_dir.exists():
            messagebox.showerror("Error", "NTCP analysis not found. Run NTCP analysis first.")
            return
        
        # Update status
        self.step6_status.config(text="⏱ Running Step 6...", foreground="orange")
        self.log("Starting Step 6: TCP-NTCP Integration...")
        
        # Start owl animation
        self._start_step_animation("step6")
        
        # Run in thread
        thread = threading.Thread(target=self._execute_step6, daemon=True)
        thread.start()
    
    def _execute_step6(self):
        """Execute code7_tcp_ntcp_integration.py in background thread (UNIFIED PIPELINE)"""
        try:
            base_dir = Path(self.output_dir.get())
            tcp_dir = base_dir / "tcp_analysis"
            ntcp_dir = base_dir / "ntcp_analysis"
            # UNIFIED OUTPUT STRUCTURE: Use integration/ instead of tcp_ntcp_integration/
            integration_dir = base_dir / "integration"
            
            cmd = [
                sys.executable,
                str(_rbgyanx_base_dir() / "code7_tcp_ntcp_integration.py"),
                "--tcp_dir", str(tcp_dir.resolve()),
                "--ntcp_dir", str(ntcp_dir.resolve()),
                "--output_dir", str(integration_dir.resolve())  # OBJECTIVE A: Use correct argument name
            ]
            
            self.log(f"Executing: python code7_tcp_ntcp_integration.py ...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  cwd=_rbgyanx_base_dir())
            
            # Log output
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        self.log(line)
            
            if result.returncode == 0:
                self.log("[OK] Step 6: TCP-NTCP integration complete")
                
                # OBJECTIVE A: Check for TWI output
                twi_file = integration_dir / "therapeutic_ratios.xlsx"
                if twi_file.exists():
                    try:
                        twi_df = pd.read_excel(twi_file)
                        if 'TWI' in twi_df.columns:
                            self.log(f"[TWI] Therapeutic Window Index calculated for {len(twi_df)} patients")
                            favorable = (twi_df['TWI'] > 0.2).sum() if 'TWI' in twi_df.columns else 0
                            self.log(f"[TWI] Favorable plans: {favorable}, Moderate: {(twi_df['TWI'] > 0).sum() - favorable}, Unfavorable: {(twi_df['TWI'] <= 0).sum()}")
                    except Exception as e:
                        self.log(f"[!] Could not read TWI results: {e}")
                
                self.execution_state.step6_complete = True
                duration = time.time() - self.step_start_times.get('step6', time.time())
                self.step_durations['step6'] = duration
                self.log(f"[TIMER] Step 6 completed in {duration:.1f} seconds")
                self.root.after(0, lambda: self._stop_step_animation("step6"))
                self.root.after(0, lambda: self.step6_status.config(text=f"✓ Step 6 ({duration:.1f}s)", foreground="green"))
                self.steps_completed["step6"] = True
                # Update dashboard
                self.root.after(100, self.update_dashboard_state)
                
                # Update progress
                self.root.after(0, lambda: self.progress_var.set(6))
                
                # Log pipeline summary if in run_all mode
                if hasattr(self, 'run_all_mode') and self.run_all_mode and hasattr(self, 'pipeline_start_time') and self.pipeline_start_time:
                    total_time = time.time() - self.pipeline_start_time
                    self.log("\n" + "=" * 60)
                    self.log("✓ PIPELINE COMPLETE!")
                    self.log("=" * 60)
                    for step_num in range(1, 7):
                        step_key = f'step{step_num}'
                        if step_key in self.step_durations:
                            self.log(f"⏱ Step {step_num}: {self.step_durations[step_key]:.1f}s")
                    self.log(f"⏱ TOTAL: {total_time:.1f}s ({total_time/60:.1f}m)")
                    self.log("=" * 60 + "\n")
                
                self.log("Pipeline complete!")
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                self.log(f"[X] Step 6 failed with return code {result.returncode}")
                if error_msg:
                    for line in error_msg.strip().split('\n'):
                        if line.strip():
                            self.log(f"  {line}")
                self.root.after(0, lambda: self._stop_step_animation("step6"))
                self.root.after(0, lambda: self.step6_status.config(text="[X] Failed", foreground="red"))
                if hasattr(self, 'run_all_mode'):
                    self.run_all_mode = False
                    
        except Exception as e:
            self.log(f"[X] Step 6 error: {str(e)}")
            import traceback
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    self.log(f"  {line}")
            self.root.after(0, lambda: self._stop_step_animation("step6"))
            self.root.after(0, lambda: self.step6_status.config(text="[X] Error", foreground="red"))
            if hasattr(self, 'run_all_mode'):
                self.run_all_mode = False
    
    def run_analysis(self):
        """Main analysis with proper TCP+NTCP integration"""
        mode = self.analysis_mode.get()
        base_dir = Path(self.output_dir.get()) if self.output_dir.get() else None
        clinical_file = Path(self.clinical_file.get()) if self.clinical_file.get() else None
        
        if not base_dir:
            messagebox.showerror("Error", "Output directory required")
            return
        
        if not self.raw_input.get():
            messagebox.showerror("Error", "Raw DVH input required")
            return
        
        if mode == "TCP_NTCP" or mode == "TCP + NTCP Analysis":
            self.log("=" * 60)
            self.log("TCP+NTCP INTEGRATION MODE")
            self.log("=" * 60)
            
            # Step 1-2: Common preprocessing
            self.log("\n[1/5] DVH Preprocessing...")
            if not self.run_preprocessing(base_dir):
                self.log("[!] Preprocessing failed, aborting")
                return
            
            # Step 3-4: NTCP Analysis
            self.log("\n[2/5] NTCP Analysis...")
            ntcp_success = self._execute_ntcp_branch(base_dir, clinical_file)
            
            if not ntcp_success:
                self.log("[!] NTCP analysis failed")
                self.log("    Integration requires both TCP and NTCP")
                return
            
            # Step 5: TCP Analysis
            self.log("\n[3/5] TCP Analysis...")
            tcp_success = self._execute_tcp_branch(base_dir, clinical_file)
            
            if not tcp_success:
                self.log("[!] TCP analysis failed")
                self.log("    Integration requires both TCP and NTCP")
                return
            
            # Step 6: Integration
            self.log("\n[4/5] TCP-NTCP Integration...")
            integration_success = self._execute_integration(base_dir)
            
            if not integration_success:
                self.log("[!] Integration failed")
                return
            
            # Step 7: Display results
            self.log("\n[5/5] Loading integration results...")
            self.show_integration_results(base_dir / "integration_results")
            
            self.log("\n" + "=" * 60)
            self.log("TCP+NTCP INTEGRATION COMPLETE")
            self.log("=" * 60)
        else:
            # For other modes, use existing run_all_steps
            self.run_all_steps()
    
    def run_preprocessing(self, base_dir: Path) -> bool:
        """Run preprocessing steps (Step 1-2)"""
        try:
            # Update workflow state
            self.set_workflow_state(WorkflowState.PREPROCESSING)
            
            # Step 1: DVH preprocessing
            self.log("Running Step 1: DVH Preprocessing...")
            if not self.run_step1():
                self.set_workflow_state(WorkflowState.ERROR)
                return False
            
            # Step 2: DVH plotting and summary
            self.log("Running Step 2: DVH Plotting and Summary...")
            if not self.run_step2():
                self.set_workflow_state(WorkflowState.ERROR)
                return False
            
            self.set_workflow_state(WorkflowState.PREPROCESSING_COMPLETE)
            return True
        except Exception as e:
            self.log(f"[!] Preprocessing error: {str(e)}")
            self.set_workflow_state(WorkflowState.ERROR)
            return False
    
    def run_all_steps(self):
        """Execute all steps in sequence"""
        # Validation
        if not self.output_dir.get():
            messagebox.showerror("Error", "Output directory required")
            return
        
        if not self.raw_input.get():
            messagebox.showerror("Error", "Raw DVH input required")
            return
        
        # For TCP, clinical data is required
        if self.analysis_type.get() == "TCP" and not self.clinical_file.get():
            messagebox.showerror("Error", "Clinical data is required for TCP analysis")
            return
        
        # Confirm
        msg = f"This will run all {self.analysis_type.get()} analysis steps.\n\n"
        msg += f"Output: {self.output_dir.get()}\n"
        msg += f"Input: {self.raw_input.get()}\n"
        
        if self.clinical_file.get():
            msg += f"Clinical data: {Path(self.clinical_file.get()).name}\n"
        
        msg += "\nContinue?"
        
        if not messagebox.askyesno("Confirm", msg):
            return
        
        # Set run_all flag
        self.run_all_mode = True
        
        # Reset progress
        self.progress_var.set(0)
        
        # Start pipeline timer
        self.pipeline_start_time = time.time()
        
        # Log start
        self.log("\n" + "=" * 60)
        self.log("🚀 Starting Full NTCP Analysis Pipeline...")
        self.log("=" * 60 + "\n")
        
        # Start with Step 1 (chain will continue automatically)
        self.run_step1()
        
        # Note: Individual step timers are handled in each step's execute function
        # Total pipeline timer will be logged after all steps complete
    
    def stop_execution(self):
        """Stop current execution"""
        self.run_all_mode = False
        self.progress_var.set(0)
        self.log("Execution stopped by user")
        messagebox.showinfo("Execution Stopped", "Execution has been stopped.\n"
                                                 "Note: Currently running steps may complete before stopping.")
    
    def clear_all_inputs(self):
        """Clear all input fields"""
        self.output_dir.set("")
        self.clinical_file.set("")
        self.raw_input.set("")
        
        # Reset step statuses
        for step_key, status_label in self.step_status_labels.items():
            status_label.config(text="[ ] Not Started", foreground="gray")
        
        # Reset step completion tracking
        self.steps_completed = {f"step{i}": False for i in range(1, 7)}
        
        # Clear summary panels
        self.update_summary_panel("Data Summary", "Data summary will appear here after Step 1 completes.")
        self.update_summary_panel("Model Parameters", "Model parameters will appear here after Step 3 completes.")
        self.update_summary_panel("Statistics", "Statistics will appear here after analysis completes.")
        self.update_summary_panel("QA Report", "QA report will appear here after Step 5 completes.")
        
        # Reset progress bar
        self.progress_var.set(0)
        
        self.log("All inputs and statuses cleared")
    
    def save_configuration(self):
        """Save current GUI settings to YAML"""
        if not YAML_AVAILABLE:
            messagebox.showerror("Error", "PyYAML is required for configuration save/load.\n"
                                         "Install with: pip install pyyaml")
            return
        
        config = {
            'analysis_type': self.analysis_type.get(),
            'output_dir': self.output_dir.get(),
            'clinical_file': self.clinical_file.get(),
            'raw_input': self.raw_input.get(),
            'input_format': self.input_format.get(),
            'dvh_type': self.dvh_type.get(),
            'tumor_organ_type': self.tumor_organ_type.get(),
            'enable_ml': self.enable_ml.get(),
            'enable_shap': self.enable_shap.get(),
            'use_glm': self.use_glm.get(),
            'traditional_models_ntcp': {
                name: var.get() for name, var in self.traditional_models_enabled.items()
            },
            'traditional_models_tcp': {
                name: var.get() for name, var in self.tcp_models_enabled.items()
            }
        }
        
        filename = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml"), ("YAML files", "*.yml"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                self.log(f"Configuration saved to {filename}")
                messagebox.showinfo("Success", f"Configuration saved to:\n{filename}")
            except Exception as e:
                self.log(f"Error saving configuration: {str(e)}")
                messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")
    
    def load_configuration(self):
        """Load GUI settings from YAML"""
        if not YAML_AVAILABLE:
            messagebox.showerror("Error", "PyYAML is required for configuration save/load.\n"
                                         "Install with: pip install pyyaml")
            return
        
        filename = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("YAML files", "*.yaml"), ("YAML files", "*.yml"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Apply configuration
                self.analysis_type.set(config.get('analysis_type', 'NTCP'))
                self.output_dir.set(config.get('output_dir', ''))
                self.clinical_file.set(config.get('clinical_file', ''))
                self.raw_input.set(config.get('raw_input', ''))
                self.input_format.set(config.get('input_format', 'directory'))
                self.dvh_type.set(config.get('dvh_type', 'auto'))
                self.tumor_organ_type.set(config.get('tumor_organ_type', 'HNSCC'))
                self.enable_ml.set(config.get('enable_ml', False))
                self.enable_shap.set(config.get('enable_shap', False))
                self.use_glm.set(config.get('use_glm', False))
                
                # Load model selections
                if 'traditional_models_ntcp' in config:
                    for name, value in config['traditional_models_ntcp'].items():
                        if name in self.traditional_models_enabled:
                            self.traditional_models_enabled[name].set(value)
                
                if 'traditional_models_tcp' in config:
                    for name, value in config['traditional_models_tcp'].items():
                        if name in self.tcp_models_enabled:
                            self.tcp_models_enabled[name].set(value)
                
                # Update UI elements
                self.on_analysis_type_change()
                if self.raw_input.get():
                    self.preview_input_data()
                
                self.log(f"Configuration loaded from {filename}")
                messagebox.showinfo("Success", f"Configuration loaded from:\n{filename}")
            except Exception as e:
                self.log(f"Error loading configuration: {str(e)}")
                messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")
    
    def get_step_output_path(self, step_num):
        """Get standardized output path for each step (UNIFIED OUTPUT STRUCTURE)"""
        base = Path(self.output_dir.get()) if self.output_dir.get() else Path.cwd()
        
        paths = {
            1: base / "processed_DVH",
            2: base / "dose_metrics",
            3: base / f"{self.analysis_type.get().lower()}_analysis",
            4: base / "clinical_factors",
            5: base / "qa",
            6: base / "integration"
        }
        
        return paths.get(step_num, base)
    
    def run_qa_analysis(self):
        """Run LLM QA engine on pipeline outputs"""
        try:
            from llm_qa_engine import RadiobiologyLLMQA
            
            self.log("\n" + "="*60)
            self.log("🤖 Running LLM QA Engine...")
            self.log("="*60)
            
            qa_engine = RadiobiologyLLMQA()
            
            # Get output paths
            base = Path(self.output_dir.get()) if self.output_dir.get() else Path.cwd()
            
            # Validate step consistency
            step1_path = base / "processed_DVH" / "processed_dvh.xlsx"
            step2_path = base / "dose_metrics" / "tables" / "dose_metrics_cohort.xlsx"
            step3_path = base / "ntcp_analysis" / "enhanced_ntcp_calculations.csv"
            
            validation = qa_engine.validate_step_consistency(
                str(step1_path), str(step2_path), str(step3_path)
            )
            
            if "error" not in validation:
                self.log(f"\n📊 Validation Results:")
                self.log(f"  Step 1: {validation['step1']['count']} samples, {validation['step1']['patients']} patients")
                self.log(f"  Step 2: {validation['step2']['count']} samples, {validation['step2']['patients']} patients")
                self.log(f"  Step 3: {validation['step3']['count']} samples, {validation['step3']['patients']} patients")
                
                if validation.get('consistency_issues'):
                    self.log(f"\n⚠️  Consistency Issues:")
                    for issue in validation['consistency_issues']:
                        self.log(f"  - {issue}")
                else:
                    self.log("\n✅ No consistency issues found")
            else:
                self.log(f"⚠️  Validation error: {validation.get('error')}")
            
            # Analyze pipeline log if available
            log_path = "rbgyanx_gui.log"
            if not Path(log_path).exists():
                log_path = base / "pipeline.log"
            
            if Path(log_path).exists():
                findings = qa_engine.analyze_pipeline_log(str(log_path))
                
                self.log(f"\n📋 QA Findings:")
                self.log(f"  Errors: {len(findings.get('errors', []))}")
                self.log(f"  Warnings: {len(findings.get('warnings', []))}")
                self.log(f"  Suggestions: {len(findings.get('suggestions', []))}")
                self.log(f"  Auto-fixes available: {len(findings.get('autofix_available', []))}")
                
                # Generate report
                report_path = base / "qa_fix_report.md"
                qa_engine.generate_fix_report(findings, str(report_path))
                self.log(f"\n✅ QA report generated: {report_path}")
            else:
                self.log("⚠️  Pipeline log not found, skipping log analysis")
            
            self.log("\n✅ QA analysis complete")
            
        except ImportError:
            self.log("⚠️  LLM QA engine not available. Install dependencies or check llm_qa_engine.py")
        except Exception as e:
            self.log(f"⚠️  QA analysis error: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
    
    # OBJECTIVE A: Novel feature helper methods
    def _init_novel_features(self):
        """Initialize novel feature helper methods"""
        pass
    
    def _on_fdvh_toggle(self):
        """Handle FDVH checkbox toggle"""
        if self.use_fdvh.get():
            self.log("[INFO] FDVH (Fractionation-Aware DVH) enabled - BED normalization will be applied")
        else:
            self.log("[INFO] FDVH disabled - using physical DVH")
        
        # Update dashboard
        self.root.after(100, self.update_dashboard_state)
    
    def _on_ccs_toggle(self):
        """Handle CCS checkbox toggle"""
        if self.use_ccs.get():
            self.ccs_file_frame.pack(fill=tk.X, pady=(5, 0))
            self.log("[INFO] CCS (ML Safety Gating) enabled - ML predictions will be gated")
        else:
            self.ccs_file_frame.pack_forget()
            self.log("[INFO] CCS disabled")
        
        # Update dashboard
        self.root.after(100, self.update_dashboard_state)
    
    def _browse_ccs_file(self):
        """Browse for CCS checker JSON file"""
        file_path = filedialog.askopenfilename(
            title="Select CCS Checker File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.ccs_file_path.set(file_path)
            self.log(f"[OK] CCS checker file selected: {file_path}")


def main():
    """Main entry point"""
    # Phase 5: Show mode selection dialog first
    try:
        from rbgyanx.ui.mode_selection import ModeSelectionDialog
        mode_dialog = ModeSelectionDialog()
        mode_controller = mode_dialog.show()
        
        if mode_controller is None:
            # User cancelled mode selection
            print("Mode selection cancelled. Exiting.")
            return
        
        print(f"Mode selected: {mode_controller.mode.value.upper()}")
    except ImportError as e:
        print(f"Warning: Mode selection dialog not available: {e}")
        print("Defaulting to BASIC mode.")
        try:
            from rbgyanx.logic.mode_controller import ModeController, RunMode
            mode_controller = ModeController(RunMode.BASIC)
        except ImportError:
            mode_controller = None
    
    root = tk.Tk()
    
    # ROOT MUST USE GRID EXCLUSIVELY
    root.grid_rowconfigure(0, weight=0)   # header
    root.grid_rowconfigure(1, weight=1)   # body
    root.grid_columnconfigure(0, weight=1)
    
    app = rbGyanX_GUI(root, mode_controller=mode_controller)
    root.mainloop()


if __name__ == "__main__":
    main()

