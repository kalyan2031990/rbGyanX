"""
Unified plotting configuration for rbGyanX
All plots use 600 DPI publication quality with unified color scheme

Author: rbGyanX Team
Version: 1.0.0
"""

import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional, Dict

# Publication-quality plot settings
PUBLICATION_CONFIG = {
    'font.size': 12,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 1.2,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linewidth': 0.8,
    'legend.frameon': False,
    'legend.fontsize': 10,
    'xtick.major.size': 6,
    'ytick.major.size': 6,
    'xtick.minor.size': 3,
    'ytick.minor.size': 3,
    'lines.linewidth': 2.5,
    'lines.markersize': 6,
    'figure.dpi': 100,
    'savefig.dpi': 600,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
    'savefig.facecolor': 'white'
}

# Unified color scheme
RBGYANX_COLORS = {
    # TCP models
    'TCP_Poisson': '#2E86AB',
    'TCP_LKB': '#F24236',
    'TCP_Logistic': '#F6AE2D',
    'TCP_EUD': '#55A630',
    
    # NTCP models
    'NTCP_LKB_LogLogit': '#1E90FF',
    'NTCP_LKB_Probit': '#FF6347',
    'NTCP_RS_Poisson': '#32CD32',
    'LKB_LogLogit': '#1E90FF',
    'LKB_Probit': '#FF6347',
    'RS_Poisson': '#32CD32',
    
    # ML models
    'ML_ANN': '#8B4B9E',
    'ML_XGBoost': '#2ECC71',
    'ML_RandomForest': '#E67E22',
    
    # Integration
    'UTCP': '#2E86AB',
    'P_plus': '#F24236',
    'CFTC': '#55A630',
    'TCP': '#8B4B9E',
    'NTCP': '#F6AE2D',
    
    # Common
    'observed': '#C73E1D',
    'predicted': '#3498DB',
    'confidence': '#95A5A6',
    'grid': '#E8E8E8',
    'literature': '#592E83'
}

# Line styles for different models
LINE_STYLES = {
    'TCP_Poisson': '-',
    'TCP_LKB': '--',
    'TCP_Logistic': '-.',
    'TCP_EUD': ':',
    'NTCP_LKB_LogLogit': '-',
    'NTCP_LKB_Probit': '--',
    'NTCP_RS_Poisson': '-.',
    'ML_ANN': (0, (3, 1, 1, 1, 1, 1)),
    'ML_XGBoost': (0, (5, 2))
}

# Markers for scatter plots
MARKERS = {
    'TCP_Poisson': 'o',
    'TCP_LKB': 's',
    'TCP_Logistic': '^',
    'TCP_EUD': 'D',
    'NTCP_LKB_LogLogit': 'o',
    'NTCP_LKB_Probit': 's',
    'NTCP_RS_Poisson': '^',
    'ML_ANN': 'v',
    'ML_XGBoost': 'X'
}


def apply_rbgyanx_style():
    """Apply rbGyanX plotting style"""
    plt.rcParams.update(PUBLICATION_CONFIG)


def get_model_color(model_name: str) -> str:
    """Get color for model, with fallback"""
    return RBGYANX_COLORS.get(model_name, '#333333')


def get_model_line_style(model_name: str) -> str:
    """Get line style for model"""
    return LINE_STYLES.get(model_name, '-')


def get_model_marker(model_name: str) -> str:
    """Get marker for model"""
    return MARKERS.get(model_name, 'o')


def save_publication_plot(fig, filepath: Path, **kwargs):
    """Save plot with publication settings"""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    fig.savefig(
        filepath,
        dpi=600,
        bbox_inches='tight',
        facecolor='white',
        **kwargs
    )

