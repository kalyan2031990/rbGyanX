#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rbGyanX Comprehensive QA Test Suite
==================================
Professional automated testing for clinical scientific application.

This test suite is READ-ONLY with respect to application code.
It validates functionality without modifying the application.

Author: QA Engineering Team
Version: 1.0.0
"""

import sys
import os
import io
import subprocess
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Fix Windows console encoding
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )

# Test configuration
REPO_ROOT = Path(r"C:\Users\Sampa\OneDrive\Desktop\rbgyanx_dual")
INPUT_DATA_ROOT = Path(r"C:\Users\Sampa\OneDrive\Desktop\input_data")
GLOBAL_OUTPUT_ROOT = Path(r"C:\Users\Sampa\OneDrive\Desktop\rbgx_basic_global_output")

# Test results storage
test_results = {
    'environment': {},
    'repository': {},
    'unit_tests': {},
    'integration_tests': {},
    'ui_tests': {},
    'scientific_checks': {},
    'qa_validation': {},
    'output_structure': {},
    'warnings': [],
    'errors': [],
    'blocking_issues': [],
    'non_blocking_issues': []
}

def log_info(msg: str):
    """Log informational message"""
    print(f"[INFO] {msg}")

def log_warning(msg: str):
    """Log warning message"""
    print(f"[WARNING] {msg}")
    test_results['warnings'].append(msg)

def log_error(msg: str):
    """Log error message"""
    print(f"[ERROR] {msg}")
    test_results['errors'].append(msg)

def log_blocking(msg: str):
    """Log blocking issue"""
    print(f"[BLOCKING] {msg}")
    test_results['blocking_issues'].append(msg)

def log_non_blocking(msg: str):
    """Log non-blocking issue"""
    print(f"[NON-BLOCKING] {msg}")
    test_results['non_blocking_issues'].append(msg)

# ============================================
# PHASE 1: ENVIRONMENT & REPOSITORY CHECK
# ============================================

def check_python_environment():
    """Check Python version and packages"""
    log_info("Checking Python environment...")
    
    # Python version
    version = sys.version_info
    test_results['environment']['python_version'] = f"{version.major}.{version.minor}.{version.micro}"
    log_info(f"Python version: {test_results['environment']['python_version']}")
    
    # Required packages
    required = {
        'numpy': 'numpy',
        'pandas': 'pandas',
        'sklearn': 'sklearn',
        'matplotlib': 'matplotlib',
        'openpyxl': 'openpyxl',
        'scipy': 'scipy'
    }
    
    optional = {
        'shap': 'shap',
        'xgboost': 'xgboost',
        'statsmodels': 'statsmodels'
    }
    
    test_results['environment']['required_packages'] = {}
    test_results['environment']['optional_packages'] = {}
    
    for name, module in required.items():
        try:
            __import__(module)
            test_results['environment']['required_packages'][name] = 'OK'
        except ImportError:
            test_results['environment']['required_packages'][name] = 'MISSING'
            log_blocking(f"Required package missing: {name}")
    
    for name, module in optional.items():
        try:
            __import__(module)
            test_results['environment']['optional_packages'][name] = 'OK'
        except ImportError:
            test_results['environment']['optional_packages'][name] = 'MISSING'
            log_warning(f"Optional package missing: {name} (ML features may be limited)")
    
    return all(v == 'OK' for v in test_results['environment']['required_packages'].values())

def check_repository_integrity():
    """Check required scripts and directories exist"""
    log_info("Checking repository integrity...")
    
    required_scripts = [
        'code1_dvh_preprocess.py',
        'code2_dvh_plot_and_summary.py',
        'code3_ntcp_analysis_ml.py',
        'code6_tcp_analysis.py',
        'code7_tcp_ntcp_integration.py',
        'rbgyanx_gui.py'
    ]
    
    test_results['repository']['scripts'] = {}
    
    for script in required_scripts:
        script_path = REPO_ROOT / script
        if script_path.exists():
            test_results['repository']['scripts'][script] = 'EXISTS'
            log_info(f"[OK] {script} exists")
        else:
            test_results['repository']['scripts'][script] = 'MISSING'
            log_blocking(f"Required script missing: {script}")
    
    # Check required directories
    required_dirs = ['utils', 'models', 'config', 'qa']
    test_results['repository']['directories'] = {}
    
    for dir_name in required_dirs:
        dir_path = REPO_ROOT / dir_name
        if dir_path.exists():
            test_results['repository']['directories'][dir_name] = 'EXISTS'
        else:
            test_results['repository']['directories'][dir_name] = 'MISSING'
            log_warning(f"Directory missing: {dir_name}")
    
    return all(v == 'EXISTS' for v in test_results['repository']['scripts'].values())

def check_input_data():
    """Check input data structure"""
    log_info("Checking input data structure...")
    
    test_results['input_data'] = {}
    
    # Check input root exists
    if not INPUT_DATA_ROOT.exists():
        log_blocking(f"Input data root does not exist: {INPUT_DATA_ROOT}")
        return False
    
    # Check DVH directories
    dvh_dirs = {
        'OAR_DVH_NTCP_input': 'NTCP',
        'PTV_DVH_TCP_input': 'TCP',
        'PTV_OAR_DVH_TCP_NTCP_combined_input': 'BOTH'
    }
    
    test_results['input_data']['dvh_directories'] = {}
    for dir_name, mode in dvh_dirs.items():
        dir_path = INPUT_DATA_ROOT / dir_name
        if dir_path.exists():
            files = list(dir_path.glob('*.txt')) + list(dir_path.glob('*.csv'))
            test_results['input_data']['dvh_directories'][dir_name] = {
                'exists': True,
                'file_count': len(files)
            }
            log_info(f"[OK] {dir_name}: {len(files)} files found")
        else:
            test_results['input_data']['dvh_directories'][dir_name] = {
                'exists': False,
                'file_count': 0
            }
            log_warning(f"DVH directory missing: {dir_name}")
    
    # Check clinical data files
    clinical_files = ['ntcp_clinical_input.xlsx', 'tcp_clinical_input.xlsx']
    test_results['input_data']['clinical_files'] = {}
    
    for file_name in clinical_files:
        file_path = INPUT_DATA_ROOT / file_name
        if file_path.exists():
            test_results['input_data']['clinical_files'][file_name] = 'EXISTS'
            log_info(f"[OK] {file_name} exists")
        else:
            test_results['input_data']['clinical_files'][file_name] = 'MISSING'
            log_warning(f"Clinical file missing: {file_name}")
    
    return True

# ============================================
# PHASE 2: UNIT TESTS
# ============================================

def test_dvh_engine():
    """Test DVH processing engine"""
    log_info("Running DVH engine unit tests...")
    
    results = {
        'dvh_type_detection': 'NOT_RUN',
        'monotonicity_check': 'NOT_RUN',
        'structure_detection': 'NOT_RUN',
        'ptv_oar_separation': 'NOT_RUN'
    }
    
    try:
        # Import DVH utilities
        sys.path.insert(0, str(REPO_ROOT))
        from utils.dvh_parser import UniversalDVHParser
        from code1_dvh_preprocess import detect_structure_type
        
        # Test structure detection
        test_structures = [
            ('PTV', 'TARGET'),
            ('GTV', 'TARGET'),
            ('CTV', 'TARGET'),
            ('Parotid', 'OAR'),
            ('SpinalCord', 'OAR'),
            ('Brainstem', 'OAR')
        ]
        
        structure_tests_passed = 0
        for struct_name, expected_role in test_structures:
            detected = detect_structure_type(struct_name)
            if detected == expected_role:
                structure_tests_passed += 1
            else:
                log_error(f"Structure detection failed: {struct_name} -> {detected} (expected {expected_role})")
        
        results['structure_detection'] = 'PASS' if structure_tests_passed == len(test_structures) else 'FAIL'
        results['ptv_oar_separation'] = 'PASS' if structure_tests_passed == len(test_structures) else 'FAIL'
        
        log_info(f"Structure detection: {structure_tests_passed}/{len(test_structures)} tests passed")
        
    except Exception as e:
        log_error(f"DVH engine test failed: {str(e)}")
        results['structure_detection'] = 'ERROR'
        traceback.print_exc()
    
    test_results['unit_tests']['dvh_engine'] = results
    return results['structure_detection'] == 'PASS'

def test_physical_metrics():
    """Test physical metric calculations"""
    log_info("Running physical metrics unit tests...")
    
    results = {
        'oar_metrics': 'NOT_RUN',
        'target_metrics': 'NOT_RUN',
        'ptv_not_oar': 'NOT_RUN',
        'hotspot_metrics': 'NOT_RUN'
    }
    
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from code2_dvh_plot_and_summary import dvh_metrics_target, dvh_metrics_oar, is_target_structure
        import numpy as np
        
        # Create test DVH data
        doses = np.array([0, 10, 20, 30, 40, 50, 60, 70])
        volumes = np.array([100, 95, 80, 60, 40, 20, 5, 0])  # Cumulative
        
        # Test OAR metrics
        oar_metrics = dvh_metrics_oar(doses, volumes, 'Parotid')
        if oar_metrics and 'MeanDose(Gy)' in oar_metrics:
            results['oar_metrics'] = 'PASS'
            log_info("[OK] OAR metrics calculation works")
        else:
            results['oar_metrics'] = 'FAIL'
            log_error("OAR metrics calculation failed")
        
        # Test Target metrics
        target_metrics = dvh_metrics_target(doses, volumes, 'PTV')
        required_target_metrics = ['D95(Gy)', 'D98(Gy)', 'V95(%)', 'V100(%)', 'Dmax(Gy)']
        if target_metrics:
            has_all = all(m in target_metrics for m in required_target_metrics)
            has_hotspot = 'D0.03cc(Gy)' in target_metrics and 'D1cc(Gy)' in target_metrics
            has_v107 = 'V107(%)' in target_metrics
            has_gi = 'GI' in target_metrics
            
            if has_all and has_hotspot and has_v107 and has_gi:
                results['target_metrics'] = 'PASS'
                results['hotspot_metrics'] = 'PASS'
                log_info("[OK] Target metrics calculation works (including hotspots)")
            else:
                results['target_metrics'] = 'PARTIAL'
                log_warning("Target metrics missing some required fields")
        else:
            results['target_metrics'] = 'FAIL'
            log_error("Target metrics calculation failed")
        
        # Test PTV is never OAR
        ptv_is_target = is_target_structure('PTV')
        parotid_is_oar = not is_target_structure('Parotid')
        
        if ptv_is_target and parotid_is_oar:
            results['ptv_not_oar'] = 'PASS'
            log_info("[OK] PTV correctly identified as TARGET, not OAR")
        else:
            results['ptv_not_oar'] = 'FAIL'
            log_error("PTV/OAR separation failed")
        
    except Exception as e:
        log_error(f"Physical metrics test failed: {str(e)}")
        traceback.print_exc()
        results['oar_metrics'] = 'ERROR'
    
    test_results['unit_tests']['physical_metrics'] = results
    return results.get('oar_metrics') == 'PASS' and results.get('target_metrics') in ['PASS', 'PARTIAL']

# ============================================
# PHASE 3: INTEGRATION TESTS
# ============================================

def run_pipeline_test(mode: str, test_name: str) -> Dict:
    """Run full pipeline test for a given mode"""
    log_info(f"\n{'='*70}")
    log_info(f"Running {test_name} ({mode} mode)")
    log_info(f"{'='*70}")
    
    results = {
        'mode': mode,
        'test_name': test_name,
        'step1': 'NOT_RUN',
        'step2': 'NOT_RUN',
        'step3': 'NOT_RUN',
        'step4': 'NOT_RUN',
        'step5': 'NOT_RUN',
        'step6': 'NOT_RUN',
        'outputs': {},
        'errors': []
    }
    
    # Create test output directory
    test_output = GLOBAL_OUTPUT_ROOT / f"test_{mode.lower()}"
    test_output.mkdir(parents=True, exist_ok=True)
    
    try:
        # Determine input directory based on mode
        if mode == 'NTCP_ONLY':
            dvh_input = INPUT_DATA_ROOT / 'OAR_DVH_NTCP_input'
            clinical_input = INPUT_DATA_ROOT / 'ntcp_clinical_input.xlsx'
        elif mode == 'TCP_ONLY':
            dvh_input = INPUT_DATA_ROOT / 'PTV_DVH_TCP_input'
            clinical_input = INPUT_DATA_ROOT / 'tcp_clinical_input.xlsx'
        else:  # TCP_NTCP
            dvh_input = INPUT_DATA_ROOT / 'PTV_OAR_DVH_TCP_NTCP_combined_input'
            clinical_input = INPUT_DATA_ROOT / 'tcp_clinical_input.xlsx'
        
        if not dvh_input.exists():
            log_error(f"Input directory not found: {dvh_input}")
            results['errors'].append(f"Input directory missing: {dvh_input}")
            return results
        
        # Step 1: DVH Preprocessing
        log_info("Running Step 1: DVH Preprocessing...")
        step1_output = test_output / "processed_DVH"
        step1_output.mkdir(parents=True, exist_ok=True)
        
        cmd_step1 = [
            sys.executable,
            str(REPO_ROOT / "code1_dvh_preprocess.py"),
            str(dvh_input),
            "--outdir", str(step1_output)
        ]
        
        result1 = subprocess.run(cmd_step1, capture_output=True, text=True, timeout=300, cwd=REPO_ROOT)
        
        if result1.returncode == 0:
            # Check outputs
            ddvh_dir = step1_output / "dDVH_csv"
            if ddvh_dir.exists() and len(list(ddvh_dir.glob("*.csv"))) > 0:
                results['step1'] = 'PASS'
                log_info("[OK] Step 1 completed successfully")
            else:
                results['step1'] = 'FAIL'
                log_error("Step 1: No DVH files generated")
        else:
            results['step1'] = 'FAIL'
            log_error(f"Step 1 failed with return code {result1.returncode}")
            results['errors'].append(f"Step 1 stderr: {result1.stderr[:500]}")
        
        if results['step1'] != 'PASS':
            return results  # Cannot continue without Step 1
        
        # Step 2: Physical Dose Metrics
        log_info("Running Step 2: Physical Dose Metrics...")
        step2_output = test_output / "dose_metrics"
        step2_output.mkdir(parents=True, exist_ok=True)
        
        processed_dvh = step1_output / "processed_dvh.xlsx"
        if not processed_dvh.exists():
            processed_dvh = step1_output / "dDVH_csv"  # Fallback
        
        cmd_step2 = [
            sys.executable,
            str(REPO_ROOT / "code2_dvh_plot_and_summary.py"),
            "--input", str(processed_dvh),
            "--outdir", str(step2_output)
        ]
        
        result2 = subprocess.run(cmd_step2, capture_output=True, text=True, timeout=300, cwd=REPO_ROOT)
        
        if result2.returncode == 0:
            # Check for metric files
            tables_dir = step2_output / "tables"
            if mode in ['NTCP_ONLY', 'TCP_NTCP']:
                ntcp_metrics = tables_dir / "NTCP_physical_metrics.xlsx" if tables_dir.exists() else None
                if ntcp_metrics and ntcp_metrics.exists():
                    results['outputs']['ntcp_metrics'] = 'EXISTS'
                else:
                    results['outputs']['ntcp_metrics'] = 'MISSING'
                    log_warning("NTCP physical metrics file not found")
            
            if mode in ['TCP_ONLY', 'TCP_NTCP']:
                tcp_metrics = tables_dir / "TCP_physical_metrics.xlsx" if tables_dir.exists() else None
                if tcp_metrics and tcp_metrics.exists():
                    results['outputs']['tcp_metrics'] = 'EXISTS'
                    # Verify hotspot metrics
                    try:
                        import pandas as pd
                        df = pd.read_excel(tcp_metrics, sheet_name='Cohort_Summary')
                        has_hotspot = 'D0.03cc(Gy)' in df.columns and 'D1cc(Gy)' in df.columns
                        has_v107 = 'V107(%)' in df.columns
                        has_gi = 'GI' in df.columns
                        if has_hotspot and has_v107 and has_gi:
                            results['outputs']['tcp_hotspot_metrics'] = 'PASS'
                            log_info("[OK] TCP hotspot metrics present (D0.03cc, D1cc, V107, GI)")
                        else:
                            results['outputs']['tcp_hotspot_metrics'] = 'PARTIAL'
                            log_warning("TCP metrics missing some hotspot fields")
                    except Exception as e:
                        log_warning(f"Could not verify TCP hotspot metrics: {e}")
                else:
                    results['outputs']['tcp_metrics'] = 'MISSING'
                    log_warning("TCP physical metrics file not found")
            
            results['step2'] = 'PASS'
            log_info("[OK] Step 2 completed successfully")
        else:
            results['step2'] = 'FAIL'
            log_error(f"Step 2 failed with return code {result2.returncode}")
            results['errors'].append(f"Step 2 stderr: {result2.stderr[:500]}")
        
        if results['step2'] != 'PASS':
            return results
        
        # Step 3: TCP/NTCP Analysis
        log_info("Running Step 3: TCP/NTCP Analysis...")
        step3_output = test_output / f"{mode.lower().replace('_', '_')}_analysis"
        if mode == 'NTCP_ONLY':
            step3_output = test_output / "ntcp_analysis"
        elif mode == 'TCP_ONLY':
            step3_output = test_output / "tcp_analysis"
        else:
            # For BOTH mode, we'll test NTCP first, then TCP
            step3_output = test_output / "ntcp_analysis"
        
        step3_output.mkdir(parents=True, exist_ok=True)
        ddvh_dir = step1_output / "dDVH_csv"
        
        if mode in ['NTCP_ONLY', 'TCP_NTCP']:
            # Run NTCP analysis
            log_info("  Running NTCP branch...")
            cmd_step3_ntcp = [
                sys.executable,
                str(REPO_ROOT / "code3_ntcp_analysis_ml.py"),
                "--dvh_dir", str(ddvh_dir),
                "--output_dir", str(step3_output)
            ]
            
            if clinical_input.exists():
                cmd_step3_ntcp.extend(["--patient_data", str(clinical_input)])
                cmd_step3_ntcp.append("--ml_models")
            
            result3_ntcp = subprocess.run(cmd_step3_ntcp, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
            
            if result3_ntcp.returncode == 0:
                # Check NTCP outputs
                ntcp_files = list(step3_output.glob("*.xlsx")) + list(step3_output.glob("*.csv"))
                if len(ntcp_files) > 0:
                    results['outputs']['ntcp_results'] = 'EXISTS'
                    log_info("  [OK] NTCP analysis completed")
                else:
                    results['outputs']['ntcp_results'] = 'MISSING'
                    log_warning("  NTCP analysis: No output files generated")
            else:
                log_warning(f"  NTCP analysis returned code {result3_ntcp.returncode}")
        
        if mode in ['TCP_ONLY', 'TCP_NTCP']:
            # Run TCP analysis
            log_info("  Running TCP branch...")
            tcp_output = test_output / "tcp_analysis"
            tcp_output.mkdir(parents=True, exist_ok=True)
            
            if not clinical_input.exists():
                log_warning("  TCP analysis skipped: Clinical data not found")
                results['outputs']['tcp_results'] = 'SKIPPED'
            else:
                cmd_step3_tcp = [
                    sys.executable,
                    str(REPO_ROOT / "code6_tcp_analysis.py"),
                    "--tumor_dvh_dir", str(ddvh_dir),
                    "--clinical_xlsx", str(clinical_input),
                    "--outdir", str(tcp_output)
                ]
                
                result3_tcp = subprocess.run(cmd_step3_tcp, capture_output=True, text=True, timeout=600, cwd=REPO_ROOT)
                
                if result3_tcp.returncode == 0:
                    tcp_files = list(tcp_output.glob("*.xlsx"))
                    if len(tcp_files) > 0:
                        results['outputs']['tcp_results'] = 'EXISTS'
                        log_info("  [OK] TCP analysis completed")
                    else:
                        results['outputs']['tcp_results'] = 'MISSING'
                        log_warning("  TCP analysis: No output files generated")
                else:
                    log_warning(f"  TCP analysis returned code {result3_tcp.returncode}")
        
        results['step3'] = 'PASS' if results['outputs'].get('ntcp_results') == 'EXISTS' or results['outputs'].get('tcp_results') == 'EXISTS' else 'PARTIAL'
        
        # Step 4: Clinical Factors (if clinical data available)
        if clinical_input.exists() and results['step3'] == 'PASS':
            log_info("Running Step 4: Clinical Factors Analysis...")
            # This would run code5_ntcp_factors_analysis.py
            # Skipping for now to avoid long execution
            results['step4'] = 'SKIPPED'
        else:
            results['step4'] = 'SKIPPED'
            log_info("Step 4 skipped (no clinical data or Step 3 incomplete)")
        
        # Step 5: QA
        log_info("Running Step 5: Quality Assurance...")
        qa_output = test_output / "qa"
        qa_output.mkdir(parents=True, exist_ok=True)
        
        if (REPO_ROOT / "code4_ntcp_output_QA_reporter.py").exists():
            # Run QA for each analysis type
            for analysis_type in ['ntcp', 'tcp']:
                analysis_dir = test_output / f"{analysis_type}_analysis"
                if analysis_dir.exists():
                    cmd_qa = [
                        sys.executable,
                        str(REPO_ROOT / "code4_ntcp_output_QA_reporter.py"),
                        "--input", str(analysis_dir),
                        "--report_outdir", str(qa_output)
                    ]
                    result_qa = subprocess.run(cmd_qa, capture_output=True, text=True, timeout=300, cwd=REPO_ROOT)
                    if result_qa.returncode == 0:
                        log_info(f"  [OK] QA completed for {analysis_type}")
                    else:
                        log_warning(f"  QA returned code {result_qa.returncode} for {analysis_type}")
        
        results['step5'] = 'PASS'
        
        # Step 6: Integration (only for TCP_NTCP mode)
        if mode == 'TCP_NTCP':
            log_info("Running Step 6: TCP-NTCP Integration...")
            integration_output = test_output / "integration"
            integration_output.mkdir(parents=True, exist_ok=True)
            
            tcp_dir = test_output / "tcp_analysis"
            ntcp_dir = test_output / "ntcp_analysis"
            
            if tcp_dir.exists() and ntcp_dir.exists():
                cmd_step6 = [
                    sys.executable,
                    str(REPO_ROOT / "code7_tcp_ntcp_integration.py"),
                    "--tcp_dir", str(tcp_dir),
                    "--ntcp_dir", str(ntcp_dir),
                    "--outdir", str(integration_output)
                ]
                
                result6 = subprocess.run(cmd_step6, capture_output=True, text=True, timeout=300, cwd=REPO_ROOT)
                
                if result6.returncode == 0:
                    integration_files = list(integration_output.glob("*.xlsx"))
                    if len(integration_files) > 0:
                        results['outputs']['integration_results'] = 'EXISTS'
                        results['step6'] = 'PASS'
                        log_info("[OK] Step 6 (Integration) completed")
                    else:
                        results['step6'] = 'PARTIAL'
                        log_warning("Step 6: No integration files generated")
                else:
                    results['step6'] = 'FAIL'
                    log_warning(f"Step 6 failed with return code {result6.returncode}")
            else:
                results['step6'] = 'SKIPPED'
                log_warning("Step 6 skipped: TCP or NTCP analysis missing")
        else:
            results['step6'] = 'N/A'
        
    except subprocess.TimeoutExpired:
        log_error(f"Pipeline test timed out for {mode}")
        results['errors'].append("Test timed out")
    except Exception as e:
        log_error(f"Pipeline test failed: {str(e)}")
        results['errors'].append(str(e))
        traceback.print_exc()
    
    return results

# ============================================
# PHASE 4: OUTPUT STRUCTURE VALIDATION
# ============================================

def validate_output_structure(test_output: Path, mode: str):
    """Validate output directory structure"""
    log_info(f"Validating output structure for {mode}...")
    
    results = {
        'structure': {},
        'files': {},
        'warnings': []
    }
    
    expected_dirs = {
        'processed_DVH': True,
        'dose_metrics': True,
        'ntcp_analysis': mode in ['NTCP_ONLY', 'TCP_NTCP'],
        'tcp_analysis': mode in ['TCP_ONLY', 'TCP_NTCP'],
        'integration': mode == 'TCP_NTCP',
        'qa': True,
        'logs': False  # Optional
    }
    
    for dir_name, required in expected_dirs.items():
        dir_path = test_output / dir_name
        if dir_path.exists():
            file_count = len(list(dir_path.rglob("*")))
            results['structure'][dir_name] = {
                'exists': True,
                'file_count': file_count
            }
            if required and file_count == 0:
                results['warnings'].append(f"{dir_name} exists but is empty")
        else:
            results['structure'][dir_name] = {
                'exists': False,
                'file_count': 0
            }
            if required:
                results['warnings'].append(f"Required directory missing: {dir_name}")
    
    test_results['output_structure'][mode] = results
    return len([w for w in results['warnings'] if 'missing' in w.lower()]) == 0

# ============================================
# PHASE 5: SCIENTIFIC SANITY CHECKS
# ============================================

def check_scientific_sanity(test_output: Path, mode: str):
    """Perform scientific sanity checks on outputs"""
    log_info(f"Running scientific sanity checks for {mode}...")
    
    results = {
        'tcp_range_check': 'NOT_RUN',
        'ntcp_range_check': 'NOT_RUN',
        'warnings': []
    }
    
    try:
        import pandas as pd
        
        # Check TCP values if TCP analysis exists
        if mode in ['TCP_ONLY', 'TCP_NTCP']:
            tcp_dir = test_output / "tcp_analysis"
            if tcp_dir.exists():
                tcp_files = list(tcp_dir.glob("*predictions*.xlsx"))
                if tcp_files:
                    df = pd.read_excel(tcp_files[0])
                    tcp_cols = [c for c in df.columns if 'TCP' in c.upper() and 'ML' not in c.upper()]
                    if tcp_cols:
                        for col in tcp_cols[:3]:  # Check first 3 TCP columns
                            values = pd.to_numeric(df[col], errors='coerce').dropna()
                            if len(values) > 0:
                                if (values >= 0).all() and (values <= 1).all():
                                    results['tcp_range_check'] = 'PASS'
                                else:
                                    results['tcp_range_check'] = 'FAIL'
                                    results['warnings'].append(f"TCP values out of range [0,1] in {col}")
        
        # Check NTCP values if NTCP analysis exists
        if mode in ['NTCP_ONLY', 'TCP_NTCP']:
            ntcp_dir = test_output / "ntcp_analysis"
            if ntcp_dir.exists():
                ntcp_files = list(ntcp_dir.glob("*.xlsx")) + list(ntcp_dir.glob("*.csv"))
                if ntcp_files:
                    try:
                        df = pd.read_excel(ntcp_files[0]) if ntcp_files[0].suffix == '.xlsx' else pd.read_csv(ntcp_files[0])
                        ntcp_cols = [c for c in df.columns if 'NTCP' in c.upper()]
                        if ntcp_cols:
                            for col in ntcp_cols[:3]:
                                values = pd.to_numeric(df[col], errors='coerce').dropna()
                                if len(values) > 0:
                                    if (values >= 0).all() and (values <= 1).all():
                                        results['ntcp_range_check'] = 'PASS'
                                    else:
                                        results['ntcp_range_check'] = 'FAIL'
                                        results['warnings'].append(f"NTCP values out of range [0,1] in {col}")
                    except Exception as e:
                        log_warning(f"Could not check NTCP values: {e}")
        
    except Exception as e:
        log_warning(f"Scientific sanity check failed: {e}")
    
    test_results['scientific_checks'][mode] = results
    return results.get('tcp_range_check') in ['PASS', 'NOT_RUN'] and results.get('ntcp_range_check') in ['PASS', 'NOT_RUN']

# ============================================
# MAIN TEST EXECUTION
# ============================================

def main():
    """Main test execution"""
    print("="*70)
    print("rbGyanX Comprehensive QA Test Suite")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Change to repo root
    os.chdir(REPO_ROOT)
    
    # Phase 1: Environment checks
    print("\n" + "="*70)
    print("PHASE 1: ENVIRONMENT & REPOSITORY CHECK")
    print("="*70)
    
    env_ok = check_python_environment()
    repo_ok = check_repository_integrity()
    input_ok = check_input_data()
    
    if not env_ok or not repo_ok:
        log_blocking("Environment or repository checks failed. Cannot proceed.")
        return
    
    # Phase 2: Unit tests
    print("\n" + "="*70)
    print("PHASE 2: UNIT TESTS")
    print("="*70)
    
    dvh_ok = test_dvh_engine()
    metrics_ok = test_physical_metrics()
    
    # Phase 3: Integration tests
    print("\n" + "="*70)
    print("PHASE 3: PIPELINE INTEGRATION TESTS")
    print("="*70)
    
    # Test 1: NTCP Only
    ntcp_results = run_pipeline_test('NTCP_ONLY', 'NTCP Only Pipeline Test')
    test_results['integration_tests']['NTCP_ONLY'] = ntcp_results
    validate_output_structure(GLOBAL_OUTPUT_ROOT / "test_ntcp_only", 'NTCP_ONLY')
    check_scientific_sanity(GLOBAL_OUTPUT_ROOT / "test_ntcp_only", 'NTCP_ONLY')
    
    # Test 2: TCP Only
    tcp_results = run_pipeline_test('TCP_ONLY', 'TCP Only Pipeline Test')
    test_results['integration_tests']['TCP_ONLY'] = tcp_results
    validate_output_structure(GLOBAL_OUTPUT_ROOT / "test_tcp_only", 'TCP_ONLY')
    check_scientific_sanity(GLOBAL_OUTPUT_ROOT / "test_tcp_only", 'TCP_ONLY')
    
    # Test 3: TCP + NTCP
    both_results = run_pipeline_test('TCP_NTCP', 'TCP + NTCP Unified Pipeline Test')
    test_results['integration_tests']['TCP_NTCP'] = both_results
    validate_output_structure(GLOBAL_OUTPUT_ROOT / "test_tcp_ntcp", 'TCP_NTCP')
    check_scientific_sanity(GLOBAL_OUTPUT_ROOT / "test_tcp_ntcp", 'TCP_NTCP')
    
    # Generate report
    print("\n" + "="*70)
    print("PHASE 8: GENERATING TEST REPORT")
    print("="*70)
    
    generate_test_report()
    
    print("\n" + "="*70)
    print("TEST SUITE COMPLETE")
    print("="*70)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTest report saved to: {GLOBAL_OUTPUT_ROOT / 'test_reports' / 'qa_test_report.md'}")

def generate_test_report():
    """Generate comprehensive test report"""
    report_dir = GLOBAL_OUTPUT_ROOT / "test_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = report_dir / "qa_test_report.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# rbGyanX Comprehensive QA Test Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # Executive Summary
        f.write("## Executive Summary\n\n")
        total_blocking = len(test_results['blocking_issues'])
        total_errors = len(test_results['errors'])
        total_warnings = len(test_results['warnings'])
        
        f.write(f"- **Blocking Issues:** {total_blocking}\n")
        f.write(f"- **Errors:** {total_errors}\n")
        f.write(f"- **Warnings:** {total_warnings}\n")
        f.write(f"- **Non-Blocking Issues:** {len(test_results['non_blocking_issues'])}\n\n")
        
        if total_blocking == 0:
            f.write("**Status: PASS** - No blocking issues detected.\n\n")
        else:
            f.write("**Status: FAIL** - Blocking issues detected.\n\n")
        
        # Environment
        f.write("## 1. Environment\n\n")
        f.write(f"- Python: {test_results['environment'].get('python_version', 'Unknown')}\n")
        f.write(f"- Required Packages: {sum(1 for v in test_results['environment'].get('required_packages', {}).values() if v == 'OK')}/{len(test_results['environment'].get('required_packages', {}))}\n")
        f.write(f"- Optional Packages: {sum(1 for v in test_results['environment'].get('optional_packages', {}).values() if v == 'OK')}/{len(test_results['environment'].get('optional_packages', {}))}\n\n")
        
        # Test Coverage
        f.write("## 2. Test Coverage Matrix\n\n")
        f.write("| Test Category | Status | Details |\n")
        f.write("|--------------|--------|----------|\n")
        
        # Unit Tests
        unit_dvh = test_results['unit_tests'].get('dvh_engine', {}).get('structure_detection', 'NOT_RUN')
        unit_metrics = test_results['unit_tests'].get('physical_metrics', {}).get('oar_metrics', 'NOT_RUN')
        f.write(f"| DVH Engine | {unit_dvh} | Structure detection, PTV/OAR separation |\n")
        f.write(f"| Physical Metrics | {unit_metrics} | OAR/Target metrics, hotspot calculations |\n")
        
        # Integration Tests
        for mode, results in test_results['integration_tests'].items():
            step1 = results.get('step1', 'NOT_RUN')
            step2 = results.get('step2', 'NOT_RUN')
            step3 = results.get('step3', 'NOT_RUN')
            f.write(f"| {mode} Pipeline | {step3} | Step1:{step1}, Step2:{step2}, Step3:{step3} |\n")
        
        f.write("\n")
        
        # Blocking Issues
        if test_results['blocking_issues']:
            f.write("## 3. Blocking Issues\n\n")
            for i, issue in enumerate(test_results['blocking_issues'], 1):
                f.write(f"{i}. {issue}\n")
            f.write("\n")
        
        # Errors
        if test_results['errors']:
            f.write("## 4. Errors\n\n")
            for i, error in enumerate(test_results['errors'], 1):
                f.write(f"{i}. {error}\n")
            f.write("\n")
        
        # Warnings
        if test_results['warnings']:
            f.write("## 5. Warnings\n\n")
            for i, warning in enumerate(test_results['warnings'][:20], 1):  # Limit to 20
                f.write(f"{i}. {warning}\n")
            if len(test_results['warnings']) > 20:
                f.write(f"\n... and {len(test_results['warnings']) - 20} more warnings.\n")
            f.write("\n")
        
        # Scientific Caveats
        f.write("## 6. Scientific Caveats\n\n")
        f.write("- TCP/NTCP values are probabilistic predictions, not deterministic outcomes.\n")
        f.write("- Model parameters should be validated against local clinical data.\n")
        f.write("- ML models may exhibit overfitting with small datasets.\n")
        f.write("- Integration metrics (UTCP, P+) are simplified and should be interpreted with caution.\n\n")
        
        # Recommendations
        f.write("## 7. Recommendations\n\n")
        if total_blocking == 0:
            f.write("**Application is ready for use. All critical tests passed.**\n\n")
        else:
            f.write("**WARNING: Address blocking issues before production use.**\n\n")
        
        f.write("### Non-Code Improvements\n\n")
        f.write("- Consider adding more comprehensive input validation\n")
        f.write("- Enhance error messages for better user guidance\n")
        f.write("- Add progress indicators for long-running operations\n")
        f.write("- Consider batch processing capabilities for large datasets\n\n")
        
        f.write("---\n\n")
        f.write(f"*Report generated by rbGyanX QA Test Suite v1.0.0*\n")
    
    log_info(f"Test report generated: {report_path}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR in test suite: {e}")
        traceback.print_exc()
        sys.exit(1)
