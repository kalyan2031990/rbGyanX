"""
Plotting utilities for rbGyanX
"""
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List

# This module provides plotting utilities
# Most plotting is done in plot-specific classes in:
# - plots/dvh_plots.py
# - plots/dose_response.py
# - code6_tcp_analysis.py (TCPPlotter)
# - code3_ntcp_analysis_ml.py (NTCPPlotter)

__all__ = ['apply_rbgyanx_style', 'save_publication_plot']


def apply_rbgyanx_style(fig: Optional[plt.Figure] = None, 
                      ax: Optional[plt.Axes] = None) -> None:
    """
    Apply rbGyanX publication-quality style to plot
    
    Parameters
    ----------
    fig : plt.Figure, optional
        Figure to style
    ax : plt.Axes, optional
        Axes to style
    """
    if fig is None:
        fig = plt.gcf()
    if ax is None:
        ax = plt.gca()
    
    # Apply style
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, alpha=0.3, linewidth=0.8)
    ax.set_axisbelow(True)


def save_publication_plot(fig: plt.Figure, 
                          output_path: Path,
                          dpi: int = 600,
                          bbox_inches: str = 'tight') -> None:
    """
    Save plot in publication-quality format
    
    Parameters
    ----------
    fig : plt.Figure
        Figure to save
    output_path : Path
        Output file path
    dpi : int
        Resolution (default: 600)
    bbox_inches : str
        Bounding box setting (default: 'tight')
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches=bbox_inches, 
                facecolor='white', edgecolor='none')

