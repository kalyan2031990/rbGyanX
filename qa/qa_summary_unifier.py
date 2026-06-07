"""
GAP 4: Unified QA Summary Generator

Creates a single qa_summary.xlsx file that unifies QA outputs across
TCP, NTCP, and Combined modes.

Author: rbGyanX Team
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def create_unified_qa_summary(
    output_root: Path,
    mode: str,
    steps_executed: List[str],
    validation_flags: Optional[Dict] = None,
    ml_status: Optional[Dict] = None,
    tcp_qa_path: Optional[Path] = None,
    ntcp_qa_path: Optional[Path] = None
) -> Path:
    """
    GAP 4: Create unified QA summary file.
    
    Parameters
    ----------
    output_root : Path
        Root output directory
    mode : str
        Analysis mode: 'NTCP_ONLY', 'TCP_ONLY', or 'TCP_NTCP'
    steps_executed : List[str]
        List of steps that were executed (e.g., ['step1', 'step2', 'step3'])
    validation_flags : dict, optional
        Dictionary with validation flags and status
    ml_status : dict, optional
        Dictionary with ML model status for TCP and/or NTCP
    tcp_qa_path : Path, optional
        Path to TCP QA report if available
    ntcp_qa_path : Path, optional
        Path to NTCP QA report if available
    
    Returns
    -------
    Path
        Path to created qa_summary.xlsx file
    """
    qa_dir = output_root / 'qa'
    qa_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = qa_dir / 'qa_summary.xlsx'
    
    # Prepare summary data
    summary_data = {
        'Mode': [mode],
        'Steps_Executed': [', '.join(steps_executed)],
        'Timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    }
    
    # Add validation flags
    if validation_flags:
        for key, value in validation_flags.items():
            summary_data[f'Validation_{key}'] = [value]
    
    # Add ML status
    if ml_status:
        for key, value in ml_status.items():
            summary_data[f'ML_{key}'] = [value]
    
    summary_df = pd.DataFrame(summary_data)
    
    # Load TCP QA data if available
    tcp_qa_data = {}
    if tcp_qa_path and tcp_qa_path.exists():
        try:
            if tcp_qa_path.suffix == '.xlsx':
                tcp_qa_data['TCP_QA_Available'] = ['Yes']
                # Try to read summary sheet if exists
                try:
                    tcp_summary = pd.read_excel(tcp_qa_path, sheet_name='Summary', engine='openpyxl')
                    tcp_qa_data['TCP_QA_Rows'] = [len(tcp_summary)]
                except:
                    tcp_qa_data['TCP_QA_Rows'] = ['N/A']
            else:
                tcp_qa_data['TCP_QA_Available'] = ['No']
        except Exception as e:
            tcp_qa_data['TCP_QA_Available'] = [f'Error: {str(e)[:50]}']
    else:
        tcp_qa_data['TCP_QA_Available'] = ['No']
    
    # Load NTCP QA data if available
    ntcp_qa_data = {}
    if ntcp_qa_path and ntcp_qa_path.exists():
        try:
            if ntcp_qa_path.suffix == '.xlsx':
                ntcp_qa_data['NTCP_QA_Available'] = ['Yes']
                # Try to read summary sheet if exists
                try:
                    ntcp_summary = pd.read_excel(ntcp_qa_path, sheet_name='PerOrganSummary', engine='openpyxl')
                    ntcp_qa_data['NTCP_QA_Organs'] = [len(ntcp_summary)]
                except:
                    ntcp_qa_data['NTCP_QA_Organs'] = ['N/A']
            else:
                ntcp_qa_data['NTCP_QA_Available'] = ['No']
        except Exception as e:
            ntcp_qa_data['NTCP_QA_Available'] = [f'Error: {str(e)[:50]}']
    else:
        ntcp_qa_data['NTCP_QA_Available'] = ['No']
    
    # Combine all data
    for key, value in tcp_qa_data.items():
        summary_data[key] = value
    for key, value in ntcp_qa_data.items():
        summary_data[key] = value
    
    summary_df = pd.DataFrame(summary_data)
    
    # Create Excel file with multiple sheets
    with pd.ExcelWriter(summary_file, engine='openpyxl') as writer:
        # Sheet 1: Summary
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Sheet 2: Steps executed
        steps_df = pd.DataFrame({
            'Step': steps_executed,
            'Status': ['Completed'] * len(steps_executed)
        })
        steps_df.to_excel(writer, sheet_name='Steps_Executed', index=False)
        
        # Sheet 3: Validation flags
        if validation_flags:
            validation_df = pd.DataFrame([validation_flags])
            validation_df.to_excel(writer, sheet_name='Validation_Flags', index=False)
        else:
            pd.DataFrame({'Note': ['No validation flags provided']}).to_excel(
                writer, sheet_name='Validation_Flags', index=False
            )
        
        # Sheet 4: ML status
        if ml_status:
            ml_df = pd.DataFrame([ml_status])
            ml_df.to_excel(writer, sheet_name='ML_Status', index=False)
        else:
            pd.DataFrame({'Note': ['No ML models executed']}).to_excel(
                writer, sheet_name='ML_Status', index=False
            )
    
    print(f"[OK] Unified QA summary created: {summary_file}")
    return summary_file


def auto_detect_qa_files(output_root: Path) -> tuple:
    """
    Auto-detect TCP and NTCP QA files in output directory.
    
    Parameters
    ----------
    output_root : Path
        Root output directory
    
    Returns
    -------
    tuple
        (tcp_qa_path, ntcp_qa_path)
    """
    tcp_qa_path = None
    ntcp_qa_path = None
    
    # Look for TCP QA
    tcp_qa_candidates = [
        output_root / 'tcp_analysis' / 'qa_summary_tables.xlsx',
        output_root / 'qa' / 'tcp_qa_summary.xlsx',
        output_root / 'tcp_analysis' / 'qa' / 'qa_summary_tables.xlsx'
    ]
    for candidate in tcp_qa_candidates:
        if candidate.exists():
            tcp_qa_path = candidate
            break
    
    # Look for NTCP QA
    ntcp_qa_candidates = [
        output_root / 'ntcp_analysis' / 'qa_summary_tables.xlsx',
        output_root / 'qa' / 'ntcp_qa_summary.xlsx',
        output_root / 'ntcp_analysis' / 'qa' / 'qa_summary_tables.xlsx',
        output_root / 'qa' / 'qa_summary_tables.xlsx'  # Common location
    ]
    for candidate in ntcp_qa_candidates:
        if candidate.exists():
            ntcp_qa_path = candidate
            break
    
    return tcp_qa_path, ntcp_qa_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create unified QA summary')
    parser.add_argument('--output_root', required=True, help='Root output directory')
    parser.add_argument('--mode', required=True, choices=['NTCP_ONLY', 'TCP_ONLY', 'TCP_NTCP'],
                       help='Analysis mode')
    parser.add_argument('--steps', nargs='+', default=[],
                       help='Steps executed (e.g., step1 step2 step3)')
    
    args = parser.parse_args()
    
    output_root = Path(args.output_root)
    tcp_qa_path, ntcp_qa_path = auto_detect_qa_files(output_root)
    
    summary_file = create_unified_qa_summary(
        output_root=output_root,
        mode=args.mode,
        steps_executed=args.steps,
        tcp_qa_path=tcp_qa_path,
        ntcp_qa_path=ntcp_qa_path
    )
    
    print(f"Unified QA summary created: {summary_file}")

