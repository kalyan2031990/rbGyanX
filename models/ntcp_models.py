"""
NTCP Models - Backend wrapper for rbGyanX Pro v1.1.0
====================================================

Wraps existing NTCP model implementations.
No GUI dependencies, pure backend logic.
"""

# Import from existing utils if available
# For now, this is a placeholder that can be expanded
# The actual NTCP calculations are in code3_ntcp_analysis_ml.py

from typing import Dict, Optional
import pandas as pd
import numpy as np

__all__ = ['calculate_ntcp_lkb', 'calculate_ntcp_rs']


def calculate_ntcp_lkb(dvh: pd.DataFrame, TD50: float, m: float, n: float) -> float:
    """
    Calculate NTCP using LKB model.
    
    This is a placeholder - actual implementation should import from
    code3_ntcp_analysis_ml.py or utils/ntcp_models.py when available.
    """
    # Placeholder implementation
    return 0.0


def calculate_ntcp_rs(dvh: pd.DataFrame, TD50: float, m: float, s: float) -> float:
    """
    Calculate NTCP using Relative Seriality model.
    
    This is a placeholder - actual implementation should import from
    code3_ntcp_analysis_ml.py or utils/ntcp_models.py when available.
    """
    # Placeholder implementation
    return 0.0

