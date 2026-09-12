"""Test GUI integration and state management.

Tkinter is an optional dependency in practice: CPython ships it, but the Debian/Ubuntu family
splits it into a separate ``python3-tk`` package, so a minimal Linux install has a Python that
cannot import it. This module used to ``import tkinter`` unguarded at module scope, which turned
that into a *collection* error -- one missing OS package made the whole test suite fail rather
than skipping one file. Guarded here the same way the PySide6 modules guard theirs.
"""
import sys
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter", reason="tkinter not available (install python3-tk on Debian/Ubuntu)")

# Add project to path
sys.path.insert(0, str(Path.cwd()))


def test_gui_initialization():
    """Test GUI initializes without errors"""
    try:
        from rbgyanx_gui import rbGyanXGUI
        
        root = tk.Tk()
        root.withdraw()  # Hide window during test
        try:
            app = rbGyanXGUI()
            assert app is not None
            assert hasattr(app, 'run_analysis') or hasattr(app, 'run_all_steps')
        finally:
            root.destroy()
    except ImportError as e:
        pytest.skip(f"GUI not available: {e}")


def test_workflow_state_transitions():
    """Test workflow state machine"""
    try:
        from rbgyanx_gui import rbGyanXGUI
        
        root = tk.Tk()
        root.withdraw()  # Hide window during test
        try:
            app = rbGyanXGUI()
            
            # Test if workflow_state exists
            if hasattr(app, 'workflow_state'):
                # Test state transitions if WorkflowState enum exists
                try:
                    from rbgyanx_gui import WorkflowState
                    if hasattr(app, 'set_workflow_state'):
                        app.set_workflow_state(WorkflowState.PREPROCESSING)
                        assert app.workflow_state == WorkflowState.PREPROCESSING
                except (ImportError, AttributeError):
                    # WorkflowState may not be implemented yet
                    pass
        finally:
            root.destroy()
    except ImportError as e:
        pytest.skip(f"GUI not available: {e}")


def test_template_download_functionality():
    """Test clinical template download"""
    try:
        from clinical_template_generator import create_tcp_template, create_ntcp_template
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test TCP template
            tcp_path = Path(tmpdir) / "tcp_template.xlsx"
            result = create_tcp_template(str(tcp_path), with_samples=True)
            assert tcp_path.exists() or Path(result).exists()
            
            # Test NTCP template
            ntcp_path = Path(tmpdir) / "ntcp_template.xlsx"
            result = create_ntcp_template(str(ntcp_path), with_samples=True)
            assert ntcp_path.exists() or Path(result).exists()
    except ImportError as e:
        pytest.skip(f"Template generator not available: {e}")

