"""
Pytest fixtures for rbGyanX testing
"""
import os
import pytest
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

dicom_available = os.path.isdir("test_data/dicom_input") and any(
    f.endswith(".dcm")
    for _root, _, files in os.walk("test_data/dicom_input")
    for f in files
)
requires_dicom = pytest.mark.skipif(
    not dicom_available,
    reason="No DICOM test data in test_data/dicom_input",
)

try:
    from clinical_template_generator import create_tcp_template, create_ntcp_template
    TEMPLATE_GENERATOR_AVAILABLE = True
except ImportError:
    TEMPLATE_GENERATOR_AVAILABLE = False
    create_tcp_template = None
    create_ntcp_template = None


@pytest.fixture(scope="session")
def tcp_template():
    """Create TCP clinical template"""
    if not TEMPLATE_GENERATOR_AVAILABLE:
        pytest.skip("Template generator not available")
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        template_path = create_tcp_template(f.name, with_samples=True, n_samples=30)
        yield template_path
        try:
            Path(template_path).unlink(missing_ok=True)
        except PermissionError:
            pass


@pytest.fixture(scope="session")
def ntcp_template():
    """Create NTCP clinical template"""
    if not TEMPLATE_GENERATOR_AVAILABLE:
        pytest.skip("Template generator not available")
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        template_path = create_ntcp_template(f.name, with_samples=True, n_samples=30)
        yield template_path
        try:
            Path(template_path).unlink(missing_ok=True)
        except PermissionError:
            pass


@pytest.fixture
def temp_output_dir():
    """Temporary output directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="session")
def synthetic_data_dir():
    """Generate synthetic clinical data for testing"""
    try:
        from synthetic_data_generator import SyntheticClinicalDataGenerator
        SYNTHETIC_GENERATOR_AVAILABLE = True
    except ImportError:
        SYNTHETIC_GENERATOR_AVAILABLE = False
    
    if not SYNTHETIC_GENERATOR_AVAILABLE:
        pytest.skip("Synthetic data generator not available")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nGenerating synthetic test data in {tmpdir}...")
        
        try:
            generator = SyntheticClinicalDataGenerator(n_patients=30, random_seed=42)
            result = generator.generate_complete_dataset(tmpdir)
            
            print(f"Generated {len(result.get('patient_metadata', []))} synthetic patients")
            
            result['output_dir'] = Path(tmpdir)
            result['tcp_clinical_file'] = Path(tmpdir) / "clinical_data_TCP.xlsx"
            result['ntcp_clinical_file'] = Path(tmpdir) / "clinical_data_NTCP.xlsx"
            
            # Ensure required directories exist
            if 'tumor_dvh_dir' not in result:
                result['tumor_dvh_dir'] = Path(tmpdir) / "tumor_dvh"
            if 'dvh_dir' not in result:
                result['dvh_dir'] = Path(tmpdir) / "dvh"
            
            yield result
        except Exception as e:
            pytest.skip(f"Could not generate synthetic data: {e}")

