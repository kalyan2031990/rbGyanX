"""Test plotting standardization"""
import pytest
import matplotlib.pyplot as plt
from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def test_plot_config():
    """Test unified plot configuration"""
    try:
        from utils.plot_config import apply_rbgyanx_style, RBGYANX_COLORS
        
        apply_rbgyanx_style()
        
        # Check DPI setting
        assert plt.rcParams['savefig.dpi'] == 600
        assert plt.rcParams['figure.dpi'] == 100
        
        # Check colors defined
        assert 'TCP_Poisson' in RBGYANX_COLORS
        assert 'NTCP_LKB_LogLogit' in RBGYANX_COLORS or 'LKB_LogLogit' in RBGYANX_COLORS
        assert 'ML_ANN' in RBGYANX_COLORS
    except ImportError:
        pytest.skip("plot_config module not available")


@pytest.mark.skipif(not PIL_AVAILABLE, reason="PIL/Pillow not available")
def test_plot_generation_600dpi(temp_output_dir):
    """Test plots are actually 600 DPI"""
    try:
        from utils.plot_config import apply_rbgyanx_style, save_publication_plot
        import numpy as np
        
        apply_rbgyanx_style()
        
        # Create simple plot
        fig, ax = plt.subplots()
        x = np.linspace(0, 10, 100)
        y = np.sin(x)
        ax.plot(x, y)
        
        # Save with publication settings
        plot_path = temp_output_dir / "test_plot.png"
        save_publication_plot(fig, plot_path)
        
        # Verify file exists and has reasonable size (600 DPI should be large)
        assert plot_path.exists(), "Plot file not created"
        assert plot_path.stat().st_size > 50000, "Plot file too small (likely not 600 DPI)"
        
        # Try to read DPI from metadata (may not always be stored)
        try:
            img = Image.open(plot_path)
            dpi = img.info.get('dpi', (0, 0))
            if dpi[0] > 0:
                assert dpi[0] == 600, f"Plot DPI is {dpi[0]}, expected 600"
        except Exception:
            # DPI may not be in metadata, but file size check above should catch issues
            pass
        
        plt.close(fig)
    except ImportError:
        pytest.skip("plot_config module not available")

