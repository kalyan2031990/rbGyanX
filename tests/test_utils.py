"""Test utility modules"""
import pandas as pd
import pytest


def test_plot_config_application():
    """Test plot configuration applies correctly"""
    try:
        import matplotlib.pyplot as plt
        from utils.plot_config import apply_rbgyanx_style, get_model_color
        
        apply_rbgyanx_style()
        
        assert plt.rcParams['savefig.dpi'] == 600
        assert plt.rcParams['font.size'] == 12
        
        # Test color retrieval
        color = get_model_color('TCP_Poisson')
        assert color == '#2E86AB'
        
        # Test fallback
        color = get_model_color('Unknown_Model')
        assert color == '#333333'
    except ImportError:
        pytest.skip("plot_config module not available")


def test_validation_utils():
    """Test validation utilities"""
    try:
        from utils.validation_utils import validate_dataframe_columns, validate_numeric_columns
        
        df = pd.DataFrame({
            'PatientID': ['P1', 'P2'],
            'Age': [50, 60],
            'Score': [0.8, 0.9]
        })
        
        # Test column validation
        assert validate_dataframe_columns(df, ['PatientID', 'Age'])
        assert not validate_dataframe_columns(df, ['Missing'])
        
        # Test numeric validation
        assert validate_numeric_columns(df, ['Age', 'Score'])
    except ImportError:
        pytest.skip("validation_utils module not available")

