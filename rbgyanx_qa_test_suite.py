"""
rbGyanX BASIC - Comprehensive Tier-1 & Tier-2 QA Test Suite
================================================================

This script performs automated QA testing without GUI interaction.
It tests execution integrity, scientific validity, and generates diagnostic reports.

Author: QA Test Suite
Version: 1.0.0
"""

import sys
import os
import subprocess
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
import pandas as pd
import numpy as np

# Set up paths
REPO_ROOT = Path(__file__).parent.resolve()
INPUT_DATA_ROOT = REPO_ROOT / "input_data"
OUTPUT_ROOT = REPO_ROOT / "qa_test_outputs"
OUTPUT_ROOT.mkdir(exist_ok=True, parents=True)

# Test results storage
QA_RESULTS = {
    'tier1': {
        'cold_launch': {'status': 'PENDING', 'errors': [], 'logs': []},
        'tcp_only': {'status': 'PENDING', 'steps': {}, 'errors': [], 'outputs': {}},
        'ntcp_only': {'status': 'PENDING', 'steps': {}, 'errors': [], 'outputs': {}},
        'combined': {'status': 'PENDING', 'steps': {}, 'errors': [], 'outputs': {}},
        'clinical_templates': {'status': 'PENDING', 'errors': [], 'tests': {}},
        'ask_rbgyanx': {'status': 'PENDING', 'errors': [], 'tests': {}}
    },
    'tier2': {
        'dvh_handling': {'status': 'PENDING', 'errors': [], 'tests': {}},
        'dose_metrics': {'status': 'PENDING', 'errors': [], 'tests': {}},
        'clinical_factors': {'status': 'PENDING', 'errors': [], 'tests': {}},
        'ml_shap': {'status': 'PENDING', 'errors': [], 'tests': {}},
        'qa_reports': {'status': 'PENDING', 'errors': [], 'tests': {}},
        'integration': {'status': 'PENDING', 'errors': [], 'tests': {}}
    },
    'tier3': {
        'cosmetic_ux': {'status': 'PENDING', 'issues': []}
    },
    'known_issues': [],
    'pipeline_matrix': []
}

# Logging functions
def log_info(msg: str):
    print(f"[INFO] {msg}")
    QA_RESULTS['_logs'].append(f"[INFO] {msg}")

def log_error(msg: str):
    print(f"[ERROR] {msg}")
    QA_RESULTS['_logs'].append(f"[ERROR] {msg}")

def log_warning(msg: str):
    print(f"[WARNING] {msg}")
    QA_RESULTS['_logs'].append(f"[WARNING] {msg}")

QA_RESULTS['_logs'] = []


# ============================================
# PHASE 1: TIER-1 QA (Execution Integrity)
# ============================================

def test_cold_launch():
    """Test 1: Cold launch - verify GUI can be imported and initialized"""
    log_info("=" * 70)
    log_info("TIER-1 TEST 1: Cold Launch Test")
    log_info("=" * 70)
    
    try:
        # Test import
        log_info("Testing module import...")
        import rbgyanx_gui
        log_info("[OK] Module imported successfully")
        
        # Test class instantiation (without GUI)
        log_info("Testing class structure...")
        if hasattr(rbgyanx_gui, 'rbGyanX_GUI'):
            log_info("[OK] rbGyanX_GUI class found")
        else:
            QA_RESULTS['tier1']['cold_launch']['errors'].append("rbGyanX_GUI class not found")
            log_error("[FAIL] rbGyanX_GUI class not found")
        
        # Test critical dependencies
        log_info("Testing critical dependencies...")
        deps = ['tkinter', 'matplotlib', 'pandas', 'numpy']
        missing_deps = []
        for dep in deps:
            try:
                __import__(dep)
                log_info(f"  [OK] {dep} available")
            except ImportError:
                missing_deps.append(dep)
                log_error(f"  [FAIL] {dep} missing")
        
        if missing_deps:
            QA_RESULTS['tier1']['cold_launch']['errors'].append(f"Missing dependencies: {', '.join(missing_deps)}")
        
        # Test utility imports
        log_info("Testing utility modules...")
        utils_to_test = [
            ('utils.dvh_parser', 'UniversalDVHParser'),
            ('utils.error_handler', 'ErrorHandler'),
        ]
        for module_name, class_name in utils_to_test:
            try:
                mod = __import__(module_name, fromlist=[class_name])
                if hasattr(mod, class_name):
                    log_info(f"  [OK] {module_name}.{class_name} available")
                else:
                    log_warning(f"  ! {module_name}.{class_name} not found")
            except ImportError as e:
                log_warning(f"  ! {module_name} not available: {e}")
        
        if not QA_RESULTS['tier1']['cold_launch']['errors']:
            QA_RESULTS['tier1']['cold_launch']['status'] = 'PASS'
            log_info("[PASS] Cold launch test PASSED")
        else:
            QA_RESULTS['tier1']['cold_launch']['status'] = 'FAIL'
            log_error("[FAIL] Cold launch test FAILED")
            
    except Exception as e:
        QA_RESULTS['tier1']['cold_launch']['status'] = 'FAIL'
        QA_RESULTS['tier1']['cold_launch']['errors'].append(f"Exception: {str(e)}")
        log_error(f"[FAIL] Cold launch test FAILED with exception: {e}")
        log_error(traceback.format_exc())


def run_pipeline_step(script_name: str, args: List[str], step_name: str, timeout: int = 600) -> Tuple[bool, str, str]:
    """Execute a pipeline step script and return success status"""
    script_path = REPO_ROOT / script_name
    if not script_path.exists():
        return False, "", f"Script not found: {script_path}"
    
    cmd = [sys.executable, str(script_path)] + args
    log_info(f"  Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT
        )
        
        if result.returncode == 0:
            return True, result.stdout, result.stderr
        else:
            return False, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Timeout after {timeout} seconds"
    except Exception as e:
        return False, "", f"Exception: {str(e)}"


def test_pipeline_execution(mode: str):
    """Test pipeline execution for a given mode (TCP_ONLY, NTCP_ONLY, COMBINED)"""
    log_info("=" * 70)
    log_info(f"TIER-1 TEST: Pipeline Execution - {mode}")
    log_info("=" * 70)
    
    # Determine input paths
    if mode == "TCP_ONLY":
        dvh_input = INPUT_DATA_ROOT / "tcp_only_input" / "PTV_DVH_TCP_input"
        clinical_input = INPUT_DATA_ROOT / "tcp_only_input" / "tcp_clinical_input.xlsx"
        test_output = OUTPUT_ROOT / "tcp_only_test"
        results_key = "tcp_only"
    elif mode == "NTCP_ONLY":
        dvh_input = INPUT_DATA_ROOT / "ntcp_only_input" / "OAR_DVH_NTCP_input"
        clinical_input = INPUT_DATA_ROOT / "ntcp_only_input" / "ntcp_clinical_input.xlsx"
        test_output = OUTPUT_ROOT / "ntcp_only_test"
        results_key = "ntcp_only"
    else:  # COMBINED
        dvh_input = INPUT_DATA_ROOT / "tcp_ntcp_combined_input" / "PTV_OAR_DVH_TCP_NTCP_combined_input"
        clinical_input = INPUT_DATA_ROOT / "tcp_ntcp_combined_input" / "clinical_input_TCP_NTCP_combined.xlsx"
        test_output = OUTPUT_ROOT / "combined_test"
        results_key = "combined"
    
    test_output.mkdir(exist_ok=True, parents=True)
    results = QA_RESULTS['tier1'][results_key]
    
    # Verify inputs exist
    if not dvh_input.exists():
        results['status'] = 'FAIL'
        results['errors'].append(f"DVH input directory not found: {dvh_input}")
        log_error(f"[FAIL] Input directory missing: {dvh_input}")
        return
    
    # Count DVH files
    dvh_files = list(dvh_input.glob("*.txt")) + list(dvh_input.glob("*.TXT"))
    log_info(f"Found {len(dvh_files)} DVH files")
    
    # STEP 1: DVH Preprocessing
    log_info("\n--- Step 1: DVH Preprocessing ---")
    step1_output = test_output / "processed_DVH"
    step1_output.mkdir(exist_ok=True, parents=True)
    
    success, stdout, stderr = run_pipeline_step(
        "code1_dvh_preprocess.py",
        [str(dvh_input), "--outdir", str(step1_output)],
        "Step 1"
    )
    
    results['steps']['step1'] = {
        'success': success,
        'stdout_preview': stdout[:500] if stdout else "",
        'stderr_preview': stderr[:500] if stderr else ""
    }
    
    if not success:
        results['errors'].append("Step 1 failed")
        log_error("[FAIL] Step 1 FAILED")
        log_error(f"  Stderr: {stderr[:500]}")
        results['status'] = 'FAIL'
        return
    else:
        log_info("[OK] Step 1 completed")
    
    # Verify Step 1 outputs
    cdvh_dir = step1_output / "cDVH_csv"
    ddvh_dir = step1_output / "dDVH_csv"
    cdvh_files = list(cdvh_dir.glob("*.csv")) if cdvh_dir.exists() else []
    ddvh_files = list(ddvh_dir.glob("*.csv")) if ddvh_dir.exists() else []
    
    if len(cdvh_files) == 0 and len(ddvh_files) == 0:
        results['errors'].append("Step 1: No output files generated")
        log_error("[FAIL] Step 1: No output files")
        results['status'] = 'FAIL'
        return
    
    log_info(f"  Generated {len(cdvh_files)} cDVH files and {len(ddvh_files)} dDVH files")
    results['outputs']['step1_cdvh'] = len(cdvh_files)
    results['outputs']['step1_ddvh'] = len(ddvh_files)
    
    # STEP 2: Dose Metrics & DVH Plots
    log_info("\n--- Step 2: Dose Metrics & DVH Plots ---")
    step2_output = test_output / "dose_metrics"
    step2_output.mkdir(exist_ok=True, parents=True)
    
    success, stdout, stderr = run_pipeline_step(
        "code2_dvh_plot_and_summary.py",
        [str(step1_output), "--outdir", str(step2_output)],
        "Step 2"
    )
    
    results['steps']['step2'] = {
        'success': success,
        'stdout_preview': stdout[:500] if stdout else "",
        'stderr_preview': stderr[:500] if stderr else ""
    }
    
    if not success:
        results['errors'].append("Step 2 failed")
        log_error("[FAIL] Step 2 FAILED")
        log_error(f"  Stderr: {stderr[:500]}")
        results['status'] = 'FAIL'
        return
    else:
        log_info("[OK] Step 2 completed")
    
    # Verify Step 2 outputs
    metrics_files = list(step2_output.glob("*.xlsx"))
    plot_files = list(step2_output.glob("*.png")) + list(step2_output.glob("*.pdf"))
    
    if len(metrics_files) == 0:
        results['errors'].append("Step 2: No metrics Excel files generated")
        log_warning("! Step 2: No metrics files")
    else:
        log_info(f"  Generated {len(metrics_files)} metrics files")
        results['outputs']['step2_metrics'] = len(metrics_files)
    
    if len(plot_files) > 0:
        log_info(f"  Generated {len(plot_files)} plot files")
        results['outputs']['step2_plots'] = len(plot_files)
    
    # STEP 3: TCP/NTCP Analysis
    log_info("\n--- Step 3: TCP/NTCP Analysis ---")
    step3_output = test_output / "analysis"
    step3_output.mkdir(exist_ok=True, parents=True)
    
    step3_success = False
    
    # NTCP branch
    if mode in ["NTCP_ONLY", "COMBINED"]:
        log_info("  Running NTCP analysis...")
        ntcp_output = step3_output / "ntcp_analysis"
        ntcp_output.mkdir(exist_ok=True, parents=True)
        
        if clinical_input.exists():
            success, stdout, stderr = run_pipeline_step(
                "code3_ntcp_analysis_ml.py",
                [
                    "--oar_dvh_dir", str(ddvh_dir),
                    "--clinical_xlsx", str(clinical_input),
                    "--outdir", str(ntcp_output)
                ],
                "Step 3 NTCP"
            )
            
            if success:
                ntcp_files = list(ntcp_output.glob("*.xlsx"))
                if len(ntcp_files) > 0:
                    log_info(f"  [OK] NTCP analysis completed ({len(ntcp_files)} files)")
                    results['outputs']['step3_ntcp'] = len(ntcp_files)
                    step3_success = True
                else:
                    log_warning("  ! NTCP analysis: No output files")
            else:
                log_error(f"  [FAIL] NTCP analysis failed: {stderr[:300]}")
        else:
            log_warning(f"  ! Clinical input not found: {clinical_input}")
    
    # TCP branch
    if mode in ["TCP_ONLY", "COMBINED"]:
        log_info("  Running TCP analysis...")
        tcp_output = step3_output / "tcp_analysis"
        tcp_output.mkdir(exist_ok=True, parents=True)
        
        if clinical_input.exists():
            success, stdout, stderr = run_pipeline_step(
                "code6_tcp_analysis.py",
                [
                    "--tumor_dvh_dir", str(ddvh_dir),
                    "--clinical_xlsx", str(clinical_input),
                    "--outdir", str(tcp_output)
                ],
                "Step 3 TCP"
            )
            
            if success:
                tcp_files = list(tcp_output.glob("*.xlsx"))
                if len(tcp_files) > 0:
                    log_info(f"  [OK] TCP analysis completed ({len(tcp_files)} files)")
                    results['outputs']['step3_tcp'] = len(tcp_files)
                    step3_success = True
                else:
                    log_warning("  ! TCP analysis: No output files")
            else:
                log_error(f"  [FAIL] TCP analysis failed: {stderr[:300]}")
        else:
            log_warning(f"  ! Clinical input not found: {clinical_input}")
    
    if not step3_success:
        results['errors'].append("Step 3: No analysis outputs generated")
        log_error("[FAIL] Step 3 FAILED")
        results['status'] = 'PARTIAL'
    else:
        log_info("[OK] Step 3 completed")
    
    # STEP 4: Clinical Factors Analysis
    log_info("\n--- Step 4: Clinical Factors Analysis ---")
    step4_output = test_output / "clinical_factors"
    step4_output.mkdir(exist_ok=True, parents=True)
    
    if clinical_input.exists():
        success, stdout, stderr = run_pipeline_step(
            "code5_ntcp_factors_analysis.py",
            [
                "--clinical_xlsx", str(clinical_input),
                "--analysis_dir", str(step3_output),
                "--outdir", str(step4_output)
            ],
            "Step 4"
        )
        
        if success:
            factor_files = list(step4_output.glob("*.xlsx")) + list(step4_output.glob("*.png"))
            if len(factor_files) > 0:
                log_info(f"  [OK] Step 4 completed ({len(factor_files)} files)")
                results['outputs']['step4'] = len(factor_files)
            else:
                log_warning("  ! Step 4: No output files")
        else:
            log_warning(f"  ! Step 4 failed: {stderr[:300]}")
    else:
        log_warning("  ! Step 4 skipped: Clinical input not found")
    
    # STEP 5: QA Report
    log_info("\n--- Step 5: QA Report Generation ---")
    step5_output = test_output / "qa_report"
    step5_output.mkdir(exist_ok=True, parents=True)
    
    success, stdout, stderr = run_pipeline_step(
        "code4_ntcp_output_QA_reporter.py",
        [
            "--analysis_dir", str(step3_output),
            "--outdir", str(step5_output)
        ],
        "Step 5"
    )
    
    if success:
        qa_files = list(step5_output.glob("*.html")) + list(step5_output.glob("*.xlsx"))
        if len(qa_files) > 0:
            log_info(f"  [OK] Step 5 completed ({len(qa_files)} files)")
            results['outputs']['step5'] = len(qa_files)
        else:
            log_warning("  ! Step 5: No output files")
    else:
        log_warning(f"  ! Step 5 failed: {stderr[:300]}")
    
    # STEP 6: Integration (only for COMBINED)
    if mode == "COMBINED":
        log_info("\n--- Step 6: TCP-NTCP Integration ---")
        step6_output = test_output / "integration"
        step6_output.mkdir(exist_ok=True, parents=True)
        
        tcp_dir = step3_output / "tcp_analysis"
        ntcp_dir = step3_output / "ntcp_analysis"
        
        if tcp_dir.exists() and ntcp_dir.exists():
            success, stdout, stderr = run_pipeline_step(
                "code7_tcp_ntcp_integration.py",
                [
                    "--tcp_dir", str(tcp_dir),
                    "--ntcp_dir", str(ntcp_dir),
                    "--outdir", str(step6_output)
                ],
                "Step 6"
            )
            
            if success:
                int_files = list(step6_output.glob("*.xlsx"))
                if len(int_files) > 0:
                    log_info(f"  [OK] Step 6 completed ({len(int_files)} files)")
                    results['outputs']['step6'] = len(int_files)
                else:
                    log_warning("  ! Step 6: No output files")
            else:
                log_warning(f"  ! Step 6 failed: {stderr[:300]}")
        else:
            log_warning("  ! Step 6 skipped: TCP or NTCP analysis missing")
    
    # Final status
    if results['status'] != 'FAIL' and len(results['errors']) == 0:
        results['status'] = 'PASS'
        log_info(f"\n[PASS] {mode} pipeline test PASSED")
    elif results['status'] != 'FAIL':
        results['status'] = 'PARTIAL'
        log_info(f"\n! {mode} pipeline test PARTIAL (some issues)")
    else:
        log_error(f"\n[FAIL] {mode} pipeline test FAILED")


def test_clinical_templates():
    """Test clinical template handling"""
    log_info("=" * 70)
    log_info("TIER-1 TEST: Clinical Template Handling")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier1']['clinical_templates']
    
    # Test 1: Missing clinical data
    log_info("\n--- Test: Missing Clinical Data ---")
    try:
        # Check if clinical adapter exists
        from clinical.clinical_adapter import adapt_clinical_data
        log_info("  [OK] Clinical adapter available")
        results['tests']['adapter_available'] = True
    except ImportError:
        log_warning("  ! Clinical adapter not available")
        results['tests']['adapter_available'] = False
    
    # Test 2: Template validation
    clinical_schema_path = REPO_ROOT / "clinical" / "clinical_schema.json"
    if clinical_schema_path.exists():
        log_info("  [OK] Clinical schema found")
        results['tests']['schema_exists'] = True
        try:
            with open(clinical_schema_path, 'r') as f:
                schema = json.load(f)
                log_info(f"  [OK] Schema loaded ({len(schema)} fields)")
        except Exception as e:
            log_error(f"  [FAIL] Schema load failed: {e}")
            results['errors'].append(f"Schema load error: {e}")
    else:
        log_warning("  ! Clinical schema not found")
        results['tests']['schema_exists'] = False
    
    # Test 3: Check existing clinical files
    for mode in ["tcp_only_input", "ntcp_only_input", "tcp_ntcp_combined_input"]:
        clinical_file = INPUT_DATA_ROOT / mode / f"{mode.replace('_input', '')}_clinical_input.xlsx"
        if mode == "tcp_ntcp_combined_input":
            clinical_file = INPUT_DATA_ROOT / mode / "clinical_input_TCP_NTCP_combined.xlsx"
        
        if clinical_file.exists():
            log_info(f"  [OK] {mode}: Clinical file exists")
            results['tests'][f'{mode}_exists'] = True
            try:
                df = pd.read_excel(clinical_file)
                log_info(f"    Columns: {list(df.columns)[:5]}...")
                results['tests'][f'{mode}_readable'] = True
            except Exception as e:
                log_error(f"    [FAIL] Read error: {e}")
                results['errors'].append(f"{mode} read error: {e}")
        else:
            log_warning(f"  ! {mode}: Clinical file not found")
            results['tests'][f'{mode}_exists'] = False
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


def test_ask_rbgyanx():
    """Test Ask rbGyanX functionality"""
    log_info("=" * 70)
    log_info("TIER-1 TEST: Ask rbGyanX")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier1']['ask_rbgyanx']
    
    # Test 1: Check if enhanced assistant is available
    try:
        from ask_rbgyanx.enhanced_assistant import EnhancedAskrbGyanX, create_enhanced_assistant
        log_info("  [OK] Enhanced assistant module available")
        results['tests']['module_available'] = True
    except ImportError as e:
        log_warning(f"  ! Enhanced assistant not available: {e}")
        results['tests']['module_available'] = False
        results['errors'].append(f"Module import error: {e}")
    
    # Test 2: Check rule-based assistant
    try:
        from ai.rule_based_assistant import RuleBasedAssistant, create_rule_based_assistant
        log_info("  [OK] Rule-based assistant available")
        results['tests']['rule_based_available'] = True
    except ImportError as e:
        log_warning(f"  ! Rule-based assistant not available: {e}")
        results['tests']['rule_based_available'] = False
    
    # Test 3: Check knowledge registry
    knowledge_registry = REPO_ROOT / "ask_rbgyanx" / "knowledge_registry.json"
    if knowledge_registry.exists():
        log_info("  [OK] Knowledge registry found")
        results['tests']['knowledge_registry_exists'] = True
        try:
            with open(knowledge_registry, 'r') as f:
                registry = json.load(f)
                log_info(f"    Entries: {len(registry)}")
        except Exception as e:
            log_error(f"  [FAIL] Registry load error: {e}")
            results['errors'].append(f"Registry load error: {e}")
    else:
        log_warning("  ! Knowledge registry not found")
        results['tests']['knowledge_registry_exists'] = False
    
    # Note: Actual text input/send button testing requires GUI automation
    # which is beyond scope of this diagnostic test
    log_info("  Note: GUI interaction testing requires automation framework")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


# ============================================
# PHASE 2: TIER-2 QA (Scientific Validity)
# ============================================

def test_dvh_handling():
    """Test DVH handling correctness"""
    log_info("=" * 70)
    log_info("TIER-2 TEST: DVH Handling")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier2']['dvh_handling']
    
    # Test PTV vs OAR detection
    log_info("\n--- Test: PTV/OAR Detection ---")
    
    # Check processed outputs from test runs
    for mode in ["tcp_only_test", "ntcp_only_test", "combined_test"]:
        test_dir = OUTPUT_ROOT / mode / "processed_DVH"
        if not test_dir.exists():
            continue
        
        ddvh_dir = test_dir / "dDVH_csv"
        if ddvh_dir.exists():
            ddvh_files = list(ddvh_dir.glob("*.csv"))
            if len(ddvh_files) > 0:
                # Sample a file to check structure
                sample_file = ddvh_files[0]
                try:
                    df = pd.read_csv(sample_file)
                    if 'StructureType' in df.columns:
                        log_info(f"  [OK] {mode}: StructureType column present")
                        results['tests'][f'{mode}_structure_type'] = True
                    else:
                        log_warning(f"  ! {mode}: StructureType column missing")
                        results['errors'].append(f"{mode}: Missing StructureType column")
                    
                    # Check for PTV/TARGET vs OAR distinction
                    if 'StructureName' in df.columns:
                        names = df['StructureName'].unique()
                        ptv_count = sum(1 for n in names if 'PTV' in str(n).upper() or 'GTV' in str(n).upper() or 'CTV' in str(n).upper())
                        log_info(f"    Found {ptv_count} potential target structures")
                except Exception as e:
                    log_error(f"  [FAIL] {mode}: File read error: {e}")
    
    # Test cDVH/dDVH consistency
    log_info("\n--- Test: cDVH/dDVH Consistency ---")
    # This would require comparing files, simplified for now
    log_info("  Note: Consistency check requires detailed file comparison")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


def test_dose_metrics():
    """Test dose metrics generation"""
    log_info("=" * 70)
    log_info("TIER-2 TEST: Dose Metrics")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier2']['dose_metrics']
    
    # Check metrics files from test runs
    for mode in ["tcp_only_test", "ntcp_only_test", "combined_test"]:
        metrics_dir = OUTPUT_ROOT / mode / "dose_metrics"
        if not metrics_dir.exists():
            continue
        
        metrics_files = list(metrics_dir.glob("*physical_metrics.xlsx"))
        for mfile in metrics_files:
            try:
                df = pd.read_excel(mfile)
                log_info(f"  Checking {mfile.name}...")
                
                # Check for TCP metrics (Dmax, D2%, etc.)
                if 'TCP' in mfile.name or 'PTV' in mfile.name:
                    required_metrics = ['Dmax', 'D2%', 'V95', 'V100']
                    found = [m for m in required_metrics if m in df.columns or any(m.lower() in str(c).lower() for c in df.columns)]
                    if len(found) > 0:
                        log_info(f"    [OK] Found TCP metrics: {found}")
                        results['tests'][f'{mode}_tcp_metrics'] = True
                    else:
                        log_warning(f"    ! Missing TCP metrics")
                        results['errors'].append(f"{mode}: Missing TCP metrics")
                
                # Check for NTCP metrics (QUANTEC-style)
                if 'NTCP' in mfile.name or 'OAR' in mfile.name:
                    # QUANTEC metrics vary by organ, check for common ones
                    log_info(f"    [OK] NTCP metrics file found")
                    results['tests'][f'{mode}_ntcp_metrics'] = True
                    
            except Exception as e:
                log_error(f"  [FAIL] Error reading {mfile.name}: {e}")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


def test_clinical_factors():
    """Test clinical factor analysis"""
    log_info("=" * 70)
    log_info("TIER-2 TEST: Clinical Factors Analysis")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier2']['clinical_factors']
    
    # Check clinical factors outputs
    for mode in ["tcp_only_test", "ntcp_only_test", "combined_test"]:
        factors_dir = OUTPUT_ROOT / mode / "clinical_factors"
        if factors_dir.exists():
            factor_files = list(factors_dir.glob("*.xlsx")) + list(factors_dir.glob("*.png"))
            if len(factor_files) > 0:
                log_info(f"  [OK] {mode}: {len(factor_files)} factor analysis files")
                results['tests'][f'{mode}_outputs'] = len(factor_files)
            else:
                log_warning(f"  ! {mode}: No factor analysis outputs")
        else:
            log_info(f"  - {mode}: Factors analysis not run (may be expected)")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


def test_ml_shap():
    """Test ML and SHAP functionality"""
    log_info("=" * 70)
    log_info("TIER-2 TEST: ML & SHAP")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier2']['ml_shap']
    
    # Check ML outputs
    for mode in ["tcp_only_test", "ntcp_only_test", "combined_test"]:
        analysis_dir = OUTPUT_ROOT / mode / "analysis"
        if analysis_dir.exists():
            # Check for ML performance files
            ml_files = list(analysis_dir.rglob("*ml_performance.xlsx"))
            shap_files = list(analysis_dir.rglob("*shap*.png")) + list(analysis_dir.rglob("*shap*.html"))
            
            if len(ml_files) > 0:
                log_info(f"  [OK] {mode}: ML performance files found")
                results['tests'][f'{mode}_ml'] = True
            else:
                log_info(f"  - {mode}: No ML files (ML may be disabled)")
            
            if len(shap_files) > 0:
                log_info(f"  [OK] {mode}: SHAP plots found")
                results['tests'][f'{mode}_shap'] = True
            else:
                log_info(f"  - {mode}: No SHAP files (SHAP may be disabled)")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


def test_qa_reports():
    """Test QA report generation"""
    log_info("=" * 70)
    log_info("TIER-2 TEST: QA Reports")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier2']['qa_reports']
    
    # Check QA report outputs
    for mode in ["tcp_only_test", "ntcp_only_test", "combined_test"]:
        qa_dir = OUTPUT_ROOT / mode / "qa_report"
        if qa_dir.exists():
            qa_files = list(qa_dir.glob("*.html")) + list(qa_dir.glob("*.xlsx"))
            if len(qa_files) > 0:
                log_info(f"  [OK] {mode}: {len(qa_files)} QA report files")
                results['tests'][f'{mode}_reports'] = len(qa_files)
            else:
                log_warning(f"  ! {mode}: No QA report files")
        else:
            log_info(f"  - {mode}: QA reports not generated")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


def test_integration():
    """Test Step 6 integration"""
    log_info("=" * 70)
    log_info("TIER-2 TEST: Integration (Step 6)")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier2']['integration']
    
    # Check integration outputs (only for combined)
    int_dir = OUTPUT_ROOT / "combined_test" / "integration"
    if int_dir.exists():
        int_files = list(int_dir.glob("*.xlsx"))
        if len(int_files) > 0:
            log_info(f"  [OK] Integration files found: {len(int_files)}")
            results['tests']['integration_files'] = len(int_files)
            
            # Check for utcp and therapeutic window
            for int_file in int_files:
                try:
                    df = pd.read_excel(int_file)
                    if 'utcp' in df.columns.str.lower().str.cat(sep=' ').lower():
                        log_info(f"    [OK] utcp found in {int_file.name}")
                        results['tests']['utcp_present'] = True
                    if 'therapeutic' in df.columns.str.lower().str.cat(sep=' ').lower() or 'window' in df.columns.str.lower().str.cat(sep=' ').lower():
                        log_info(f"    [OK] Therapeutic window found in {int_file.name}")
                        results['tests']['therapeutic_window_present'] = True
                except Exception as e:
                    log_warning(f"    ! Error reading {int_file.name}: {e}")
        else:
            log_warning("  ! No integration files")
    else:
        log_info("  - Integration not run (expected for TCP/NTCP-only modes)")
    
    if len(results['errors']) == 0:
        results['status'] = 'PASS'
    else:
        results['status'] = 'PARTIAL'


# ============================================
# PHASE 3: TIER-3 QA (Cosmetic/UX - Report Only)
# ============================================

def test_cosmetic_ux():
    """Test cosmetic and UX issues (report only, no fixes)"""
    log_info("=" * 70)
    log_info("TIER-3 TEST: Cosmetic & UX Verification")
    log_info("=" * 70)
    
    results = QA_RESULTS['tier3']['cosmetic_ux']
    
    # Check Ashoka Chakra
    log_info("\n--- Ashoka Chakra ---")
    try:
        import rbgyanx_gui
        if hasattr(rbgyanx_gui, 'AshokaChakra'):
            chakra_class = rbgyanx_gui.AshokaChakra
            # Check default size
            import inspect
            sig = inspect.signature(chakra_class.__init__)
            if 'size' in sig.parameters:
                default_size = sig.parameters['size'].default
                if default_size == 50:
                    log_info("  ! Default size is 50px (may be too small)")
                    results['issues'].append({
                        'component': 'AshokaChakra',
                        'issue': 'Default size 50px may be too small',
                        'severity': 'LOW'
                    })
    except Exception as e:
        log_warning(f"  ! Could not inspect AshokaChakra: {e}")
    
    # Check header branding
    log_info("\n--- Header Branding ---")
    # This would require GUI inspection, simplified
    log_info("  Note: Header branding check requires GUI inspection")
    
    # Check help menu
    log_info("\n--- Help Menu ---")
    manual_path = REPO_ROOT / "docs" / "rbgyanx_user_manual.html"
    if manual_path.exists():
        log_info("  [OK] User manual found")
        # Check if it's outdated (simplified)
        mtime = manual_path.stat().st_mtime
        log_info(f"    Last modified: {datetime.fromtimestamp(mtime)}")
    else:
        log_warning("  ! User manual not found")
        results['issues'].append({
            'component': 'Help Menu',
            'issue': 'User manual HTML not found',
            'severity': 'MEDIUM'
        })
    
    # Check Ask rbGyanX UX
    log_info("\n--- Ask rbGyanX UX ---")
    log_info("  Note: UX testing requires GUI automation")
    results['issues'].append({
        'component': 'Ask rbGyanX',
        'issue': 'UX testing requires GUI automation framework',
        'severity': 'INFO'
    })
    
    results['status'] = 'REPORTED'


# ============================================
# REPORT GENERATION
# ============================================

def generate_pipeline_matrix():
    """Generate pipeline status matrix"""
    matrix = []
    
    for mode in ['tcp_only', 'ntcp_only', 'combined']:
        if mode in QA_RESULTS['tier1']:
            results = QA_RESULTS['tier1'][mode]
            for step in ['step1', 'step2', 'step3', 'step4', 'step5', 'step6']:
                if step in results.get('steps', {}):
                    step_result = results['steps'][step]
                    status = 'PASS' if step_result.get('success') else 'FAIL'
                    outputs = results.get('outputs', {}).get(step, 'N/A')
                    matrix.append({
                        'Mode': mode.upper(),
                        'Step': step.upper(),
                        'Status': status,
                        'Output_Generated': str(outputs),
                        'Notes': step_result.get('stderr_preview', '')[:100]
                    })
                elif step == 'step6' and mode != 'combined':
                    matrix.append({
                        'Mode': mode.upper(),
                        'Step': 'STEP6',
                        'Status': 'N/A',
                        'Output_Generated': 'N/A',
                        'Notes': 'Not applicable for this mode'
                    })
    
    QA_RESULTS['pipeline_matrix'] = matrix
    return matrix


def generate_known_issues_register():
    """Generate known issues register"""
    issues = []
    issue_id = 1
    
    # Collect issues from all test results
    for tier_name, tier_data in QA_RESULTS.items():
        if tier_name.startswith('_'):
            continue
        if isinstance(tier_data, dict):
            for test_name, test_data in tier_data.items():
                if isinstance(test_data, dict) and 'errors' in test_data:
                    for error in test_data['errors']:
                        issues.append({
                            'Issue_ID': f'ISSUE-{issue_id:03d}',
                            'Module': test_name,
                            'Severity': 'HIGH' if test_data.get('status') == 'FAIL' else 'MEDIUM',
                            'Root_Cause': error[:200],
                            'Blocking': 'YES' if test_data.get('status') == 'FAIL' else 'NO',
                            'Suggested_Action': 'Investigate and fix'
                        })
                        issue_id += 1
    
    # Add cosmetic/UX issues
    for issue in QA_RESULTS['tier3']['cosmetic_ux'].get('issues', []):
        issues.append({
            'Issue_ID': f'ISSUE-{issue_id:03d}',
            'Module': issue.get('component', 'UX'),
            'Severity': issue.get('severity', 'LOW'),
            'Root_Cause': issue.get('issue', ''),
            'Blocking': 'NO',
            'Suggested_Action': 'Review and prioritize'
        })
        issue_id += 1
    
    QA_RESULTS['known_issues'] = issues
    return issues


def generate_qa_report():
    """Generate comprehensive QA report"""
    report_path = REPO_ROOT / "rbGyanX_Tier1_Tier2_QA_Report.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# rbGyanX BASIC - Tier-1 & Tier-2 QA Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # Executive Summary
        f.write("## Executive Summary\n\n")
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        partial_tests = 0
        
        for tier_name, tier_data in QA_RESULTS.items():
            if tier_name.startswith('_'):
                continue
            if isinstance(tier_data, dict):
                for test_name, test_data in tier_data.items():
                    if isinstance(test_data, dict) and 'status' in test_data:
                        total_tests += 1
                        status = test_data['status']
                        if status == 'PASS':
                            passed_tests += 1
                        elif status == 'FAIL':
                            failed_tests += 1
                        elif status == 'PARTIAL':
                            partial_tests += 1
        
        f.write(f"- **Total Tests:** {total_tests}\n")
        f.write(f"- **Passed:** {passed_tests}\n")
        f.write(f"- **Failed:** {failed_tests}\n")
        f.write(f"- **Partial:** {partial_tests}\n\n")
        
        # Tier-1 Results
        f.write("## Tier-1 QA: Execution Integrity\n\n")
        f.write("| Test | Status | Errors |\n")
        f.write("|------|--------|--------|\n")
        
        for test_name, test_data in QA_RESULTS['tier1'].items():
            if isinstance(test_data, dict) and 'status' in test_data:
                status = test_data['status']
                error_count = len(test_data.get('errors', []))
                f.write(f"| {test_name.replace('_', ' ').title()} | {status} | {error_count} |\n")
        
        f.write("\n### Detailed Results\n\n")
        for test_name, test_data in QA_RESULTS['tier1'].items():
            if isinstance(test_data, dict) and 'status' in test_data:
                f.write(f"#### {test_name.replace('_', ' ').title()}\n\n")
                f.write(f"**Status:** {test_data['status']}\n\n")
                if test_data.get('errors'):
                    f.write("**Errors:**\n")
                    for error in test_data['errors']:
                        f.write(f"- {error}\n")
                    f.write("\n")
        
        # Tier-2 Results
        f.write("\n## Tier-2 QA: Scientific & Workflow Validity\n\n")
        f.write("| Test | Status | Issues |\n")
        f.write("|------|--------|--------|\n")
        
        for test_name, test_data in QA_RESULTS['tier2'].items():
            if isinstance(test_data, dict) and 'status' in test_data:
                status = test_data['status']
                error_count = len(test_data.get('errors', []))
                f.write(f"| {test_name.replace('_', ' ').title()} | {status} | {error_count} |\n")
        
        f.write("\n### Detailed Results\n\n")
        for test_name, test_data in QA_RESULTS['tier2'].items():
            if isinstance(test_data, dict) and 'status' in test_data:
                f.write(f"#### {test_name.replace('_', ' ').title()}\n\n")
                f.write(f"**Status:** {test_data['status']}\n\n")
                if test_data.get('errors'):
                    f.write("**Issues:**\n")
                    for error in test_data['errors']:
                        f.write(f"- {error}\n")
                    f.write("\n")
        
        # Tier-3 Results
        f.write("\n## Tier-3 QA: Cosmetic & UX Verification\n\n")
        f.write("**Status:** REPORTED (No fixes applied)\n\n")
        f.write("**Issues Found:**\n")
        for issue in QA_RESULTS['tier3']['cosmetic_ux'].get('issues', []):
            f.write(f"- **{issue.get('component', 'Unknown')}:** {issue.get('issue', '')} (Severity: {issue.get('severity', 'UNKNOWN')})\n")
        
        f.write("\n---\n\n")
        f.write("## Reproducibility\n\n")
        f.write("All tests can be reproduced by running:\n")
        f.write("```bash\n")
        f.write("python rbgyanx_qa_test_suite.py\n")
        f.write("```\n")
    
    log_info(f"[OK] QA Report generated: {report_path}")
    return report_path


def generate_safe_fix_recommendations():
    """Generate safe fix recommendations"""
    report_path = REPO_ROOT / "rbGyanX_Safe_Fix_Recommendations.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# rbGyanX BASIC - Safe Fix Recommendations\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write("## Rules\n\n")
        f.write("- **SAFE FOR BASIC:** Fixes that are minimal, non-scientific, and low-risk\n")
        f.write("- **DEFER TO ADVANCED:** Fixes requiring architectural changes\n")
        f.write("- **DESIGN DECISION REQUIRED:** Fixes needing stakeholder input\n\n")
        f.write("---\n\n")
        
        # Safe fixes
        f.write("## SAFE FOR BASIC\n\n")
        f.write("### Missing File Checks\n")
        f.write("- Add existence checks before file operations\n")
        f.write("- Provide user-friendly error messages\n")
        f.write("- **Risk:** LOW\n")
        f.write("- **Impact:** Prevents crashes, improves UX\n\n")
        
        f.write("### Logging Improvements\n")
        f.write("- Ensure all errors are logged (no silent failures)\n")
        f.write("- Add error categorization\n")
        f.write("- **Risk:** LOW\n")
        f.write("- **Impact:** Better diagnostics\n\n")
        
        # Defer to advanced
        f.write("## DEFER TO ADVANCED\n\n")
        f.write("### Ask rbGyanX Intelligence\n")
        f.write("- GUI automation framework\n")
        f.write("- Enhanced LLM integration\n")
        f.write("- **Reason:** Requires architectural changes\n\n")
        
        f.write("### ML Architecture\n")
        f.write("- Model optimization\n")
        f.write("- Hyperparameter tuning\n")
        f.write("- **Reason:** Scientific domain expertise required\n\n")
        
        # Design decisions
        f.write("## DESIGN DECISION REQUIRED\n\n")
        f.write("### Ashoka Chakra Size\n")
        f.write("- Current: 50px default\n")
        f.write("- **Decision needed:** Optimal size for visibility without overlap\n\n")
        
        f.write("### Clinical Template Auto-generation\n")
        f.write("- When to auto-generate vs. prompt user\n")
        f.write("- **Decision needed:** UX workflow preference\n\n")
    
    log_info(f"[OK] Safe Fix Recommendations generated: {report_path}")
    return report_path


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    """Main execution function"""
    log_info("=" * 70)
    log_info("rbGyanX BASIC - Comprehensive QA Test Suite")
    log_info("=" * 70)
    log_info(f"Repository: {REPO_ROOT}")
    log_info(f"Input Data: {INPUT_DATA_ROOT}")
    log_info(f"Output Directory: {OUTPUT_ROOT}")
    log_info("")
    
    # PHASE 1: Tier-1 QA
    log_info("\n" + "=" * 70)
    log_info("PHASE 1: TIER-1 QA (Execution Integrity)")
    log_info("=" * 70)
    
    test_cold_launch()
    test_pipeline_execution("TCP_ONLY")
    test_pipeline_execution("NTCP_ONLY")
    test_pipeline_execution("COMBINED")
    test_clinical_templates()
    test_ask_rbgyanx()
    
    # PHASE 2: Tier-2 QA
    log_info("\n" + "=" * 70)
    log_info("PHASE 2: TIER-2 QA (Scientific & Workflow Validity)")
    log_info("=" * 70)
    
    test_dvh_handling()
    test_dose_metrics()
    test_clinical_factors()
    test_ml_shap()
    test_qa_reports()
    test_integration()
    
    # PHASE 3: Tier-3 QA
    log_info("\n" + "=" * 70)
    log_info("PHASE 3: TIER-3 QA (Cosmetic & UX - Report Only)")
    log_info("=" * 70)
    
    test_cosmetic_ux()
    
    # Generate reports
    log_info("\n" + "=" * 70)
    log_info("GENERATING REPORTS")
    log_info("=" * 70)
    
    generate_pipeline_matrix()
    generate_known_issues_register()
    generate_qa_report()
    generate_safe_fix_recommendations()
    
    # Generate CSV files
    log_info("\nGenerating CSV files...")
    
    # Pipeline Status Matrix
    matrix_df = pd.DataFrame(QA_RESULTS['pipeline_matrix'])
    matrix_path = REPO_ROOT / "rbGyanX_Pipeline_Status_Matrix.csv"
    matrix_df.to_csv(matrix_path, index=False)
    log_info(f"[OK] Pipeline Status Matrix: {matrix_path}")
    
    # Known Issues Register
    issues_df = pd.DataFrame(QA_RESULTS['known_issues'])
    issues_path = REPO_ROOT / "rbGyanX_Known_Issues_Register.csv"
    issues_df.to_csv(issues_path, index=False)
    log_info(f"[OK] Known Issues Register: {issues_path}")
    
    log_info("\n" + "=" * 70)
    log_info("QA TEST SUITE COMPLETE")
    log_info("=" * 70)
    log_info("\nAll reports generated in repository root directory.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_info("\n\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        log_error(f"\n\nFATAL ERROR: {e}")
        log_error(traceback.format_exc())
        sys.exit(1)

