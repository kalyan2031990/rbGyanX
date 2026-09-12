"""
TCP Models - Backend wrapper for rbGyanX Pro v1.1.0
===================================================

Wraps existing TCP model implementations from utils/.
No GUI dependencies, pure backend logic.
"""


import pandas as pd
from utils.tcp_models import TCPCalculator

__all__ = ['TCPCalculator', 'calculate_tcp', 'get_tcp_parameters']


def calculate_tcp(
    model_name: str,
    dvh: pd.DataFrame | None = None,
    dose_metrics: dict | None = None,
    tumor_type: str = 'HNSCC',
    config_file: str | None = None
) -> float:
    """
    Calculate TCP using specified model.
    
    Parameters
    ----------
    model_name : str
        Model name: 'Poisson_TCP', 'LKB_TCP', 'Logistic_TCP', 'EUD_TCP'
    dvh : pd.DataFrame, optional
        DVH DataFrame (required for Poisson_TCP and EUD_TCP)
    dose_metrics : dict, optional
        Dose metrics dict (required for LKB_TCP and Logistic_TCP)
    tumor_type : str
        Tumor type for parameter lookup
    config_file : str, optional
        Path to TCP parameters YAML file
        
    Returns
    -------
    float
        TCP value (0-1)
    """
    calculator = TCPCalculator(config_file)
    
    # Get parameters for tumor type
    params = calculator.literature_params.get(tumor_type, {})
    model_params = params.get(model_name, {})
    
    if not model_params:
        return 0.0
    
    # Calculate based on model type
    if model_name == 'Poisson_TCP':
        if dvh is None:
            return 0.0
        return calculator.tcp_poisson(
            dvh,
            D50=model_params.get('D50', 50.0),
            gamma50=model_params.get('gamma50', 2.0),
            alpha_beta=model_params.get('alpha_beta', 10)
        )
    
    elif model_name == 'LKB_TCP':
        if dose_metrics is None:
            return 0.0
        return calculator.tcp_lkb(
            dose_metrics,
            TD50=model_params.get('TD50', 50.0),
            m=model_params.get('m', 0.15),
            n=model_params.get('n', 0.12),
            alpha_beta=model_params.get('alpha_beta', 10)
        )
    
    elif model_name == 'Logistic_TCP':
        if dose_metrics is None:
            return 0.0
        return calculator.tcp_logistic(
            dose_metrics,
            D50=model_params.get('D50', 50.0),
            k=model_params.get('k', 0.35),
            alpha_beta=model_params.get('alpha_beta', 10)
        )
    
    elif model_name == 'EUD_TCP':
        if dvh is None:
            return 0.0
        return calculator.tcp_eud(
            dvh,
            D50=model_params.get('D50', 50.0),
            gamma50=model_params.get('gamma50', 2.0),
            a=model_params.get('a', -10),
            alpha_beta=model_params.get('alpha_beta', 10)
        )
    
    return 0.0


def get_tcp_parameters(tumor_type: str = 'HNSCC', config_file: str | None = None) -> dict:
    """
    Get TCP parameters for specified tumor type.
    
    Parameters
    ----------
    tumor_type : str
        Tumor type
    config_file : str, optional
        Path to TCP parameters YAML file
        
    Returns
    -------
    dict
        Dictionary of model parameters
    """
    calculator = TCPCalculator(config_file)
    return calculator.literature_params.get(tumor_type, {})

