# -*- coding: utf-8 -*-
"""
rbGyanX v1.0 - Smart Clinical Data Handler
===========================================
Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

Intelligent clinical data preprocessing with automatic column mapping.
Handles:
- Multiple toxicity columns
- Different column naming conventions
- Patient ID normalization
- Multi-organ data (one patient, multiple rows)

Author: rbGyanX Team
License: MIT
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re
import logging
import sys
from typing import Optional, List, Dict

# Configure logging to handle Unicode properly
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set stdout encoding to UTF-8 if possible
try:
    if sys.stdout.encoding != 'utf-8':
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    # Fallback: use ASCII-safe logging
    pass


class ClinicalDataHandler:
    """
    Intelligent clinical data preprocessing with automatic column mapping.
    
    Handles:
    - Multiple toxicity columns
    - Different column naming conventions
    - Patient ID normalization
    - Multi-organ data (one patient, multiple rows)
    
    Attributes
    ----------
    clinical_file : Path
        Path to clinical data file
    df : pd.DataFrame
        Loaded clinical data
    patient_id_col : str
        Detected patient ID column name
    toxicity_cols : List[str]
        List of detected toxicity column names
    organ_col : Optional[str]
        Detected organ column name (if multi-organ data)
    """
    
    def __init__(self, clinical_file):
        """
        Initialize the Clinical Data Handler.
        
        Parameters
        ----------
        clinical_file : str or Path
            Path to clinical data file (Excel or CSV)
        """
        self.clinical_file = Path(clinical_file)
        self.df = None
        self.patient_id_col = None
        self.toxicity_cols = []
        self.organ_col = None
        
    def detect_columns(self, interactive: bool = False):
        """
        Auto-detect column mappings.
        
        Parameters
        ----------
        interactive : bool, default False
            If True, prompt user for column selection when auto-detection fails
        
        Returns
        -------
        dict
            Dictionary with detected column mappings
        """
        # Load data
        if self.clinical_file.suffix == '.xlsx':
            self.df = pd.read_excel(self.clinical_file)
        else:
            self.df = pd.read_csv(self.clinical_file)
        
        # Detect Patient ID column
        patient_id_candidates = ['PatientID', 'Patient_ID', 'PatientId', 'Patient_AnoID', 
                                'ID', 'patient_id', 'patientid']
        for col in self.df.columns:
            if col in patient_id_candidates:
                self.patient_id_col = col
                break
        
        # If not found, check case-insensitive
        if not self.patient_id_col:
            for col in self.df.columns:
                if col.upper() in [c.upper() for c in patient_id_candidates]:
                    self.patient_id_col = col
                    break
        
        # If still not found and interactive mode
        if not self.patient_id_col:
            if interactive:
                logging.warning("\n[!] Could not auto-detect Patient ID column.")
                logging.warning("Available columns:")
                for i, col in enumerate(self.df.columns, 1):
                    logging.warning(f"  {i}. {col}")
                try:
                    choice = input("Select Patient ID column number: ")
                    self.patient_id_col = self.df.columns[int(choice)-1]
                except (ValueError, IndexError):
                    raise ValueError("Invalid column selection")
            else:
                # Try first column as fallback
                self.patient_id_col = self.df.columns[0]
                logging.warning(f"[!] Using first column as Patient ID: {self.patient_id_col}")
        
        # Detect Toxicity columns
        toxicity_keywords = ['Toxicity', 'Observed', 'Xerostomia', 'Dysphagia', 
                           'Dermatitis', 'Mucositis', 'Complication', 'Event']
        for col in self.df.columns:
            col_upper = col.upper()
            if any(kw.upper() in col_upper for kw in toxicity_keywords):
                # Check if binary (0/1) or numeric
                unique_vals = self.df[col].dropna().unique()
                if len(unique_vals) <= 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0, np.nan}):
                    self.toxicity_cols.append(col)
                elif self.df[col].dtype in [np.int64, np.float64] and len(unique_vals) <= 10:
                    # Could be grade-based (0-4), check if mostly 0/1
                    if (self.df[col] == 1).sum() > 0 or (self.df[col] == 0).sum() > 0:
                        self.toxicity_cols.append(col)
        
        # If no toxicity columns found and interactive mode
        if not self.toxicity_cols:
            if interactive:
                logging.warning("\n[!] Could not auto-detect toxicity columns.")
                logging.warning("Which column contains toxicity outcomes (0=no, 1=yes)?")
                for i, col in enumerate(self.df.columns, 1):
                    sample = self.df[col].dropna().unique()[:5]
                    logging.warning(f"  {i}. {col} (sample: {sample})")
                try:
                    choice = input("Select toxicity column number: ")
                    self.toxicity_cols = [self.df.columns[int(choice)-1]]
                except (ValueError, IndexError):
                    raise ValueError("Invalid column selection")
            else:
                # Try to find any binary column
                for col in self.df.columns:
                    unique_vals = self.df[col].dropna().unique()
                    if len(unique_vals) == 2 and set(unique_vals).issubset({0, 1, 0.0, 1.0}):
                        self.toxicity_cols.append(col)
                        break
        
        # Detect Organ column
        organ_candidates = ['Organ', 'Structure', 'OAR', 'Site', 'ROI', 
                          'organ', 'structure', 'oar']
        for col in self.df.columns:
            if col in organ_candidates:
                self.organ_col = col
                break
        
        # If not found, check case-insensitive
        if not self.organ_col:
            for col in self.df.columns:
                if col.upper() in [c.upper() for c in organ_candidates]:
                    self.organ_col = col
                    break
        
        result = {
            'patient_id_col': self.patient_id_col,
            'toxicity_cols': self.toxicity_cols,
            'organ_col': self.organ_col
        }
        
        logging.info(f"\n[OK] Detected columns:")
        logging.info(f"  Patient ID: {self.patient_id_col}")
        logging.info(f"  Toxicity: {', '.join(self.toxicity_cols) if self.toxicity_cols else 'None detected'}")
        logging.info(f"  Organ: {self.organ_col if self.organ_col else 'None (single organ)'}")
        
        return result
    
    def normalize_patient_ids(self):
        """
        Normalize patient IDs for matching with DVH files.
        
        Removes spaces, special characters, and standardizes format.
        """
        if not self.patient_id_col:
            raise ValueError("Patient ID column not detected. Call detect_columns() first.")
        
        # Convert to string and normalize
        self.df[self.patient_id_col] = self.df[self.patient_id_col].astype(str)
        
        # Remove spaces, replace special characters with underscore
        self.df[self.patient_id_col] = self.df[self.patient_id_col].str.replace(' ', '_')
        self.df[self.patient_id_col] = self.df[self.patient_id_col].str.replace('/', '_')
        self.df[self.patient_id_col] = self.df[self.patient_id_col].str.replace('\\', '_')
        
        # Remove leading/trailing whitespace
        self.df[self.patient_id_col] = self.df[self.patient_id_col].str.strip()
        
    def validate_data(self) -> List[str]:
        """
        Validate clinical data quality.
        
        Returns
        -------
        List[str]
            List of validation issues (empty if no issues)
        """
        issues = []
        
        if not self.patient_id_col:
            issues.append("Patient ID column not detected")
            return issues
        
        # Check for missing patient IDs
        missing_ids = self.df[self.patient_id_col].isna().sum()
        if missing_ids > 0:
            issues.append(f"Missing Patient ID: {missing_ids}/{len(self.df)} rows")
        
        # Check for missing toxicity
        for tox_col in self.toxicity_cols:
            missing = self.df[tox_col].isna().sum()
            if missing > 0:
                issues.append(f"Missing {tox_col}: {missing}/{len(self.df)} rows")
        
        # Check toxicity distribution
        for tox_col in self.toxicity_cols:
            pos = (self.df[tox_col] == 1).sum()
            neg = (self.df[tox_col] == 0).sum()
            total = pos + neg
            
            if total < 5:
                issues.append(f"[!] Very few valid entries for {tox_col}: {total} (need >=5)")
            elif pos < 5:
                issues.append(f"[!] Low positive events for {tox_col}: {pos} (need >=5 for ML)")
            elif pos == 0:
                issues.append(f"[X] No positive events for {tox_col}: {pos} (cannot model)")
        
        # Check patient ID uniqueness (if single organ)
        if not self.organ_col:
            duplicates = self.df[self.patient_id_col].duplicated().sum()
            if duplicates > 0:
                issues.append(f"[!] Duplicate patient IDs: {duplicates} (expected for multi-organ data)")
        
        return issues
    
    def prepare_for_analysis(self, primary_toxicity: Optional[str] = None, 
                            interactive: bool = False) -> pd.DataFrame:
        """
        Prepare clinical data for NTCP/TCP analysis.
        
        Parameters
        ----------
        primary_toxicity : str, optional
            Primary toxicity endpoint to use (if multiple available)
        interactive : bool, default False
            If True, prompt user for selection when needed
        
        Returns
        -------
        pd.DataFrame
            Cleaned and standardized clinical data with 'Observed_Toxicity' column
        """
        # Detect columns if not already done
        if self.patient_id_col is None:
            self.detect_columns(interactive=interactive)
        
        # Normalize patient IDs
        self.normalize_patient_ids()
        
        # Validate data
        issues = self.validate_data()
        if issues:
            logging.warning("\n[!] Data Quality Issues:")
            for issue in issues:
                logging.warning(f"  - {issue}")
            
            if any('need >=5' in issue for issue in issues):
                logging.error("\n[X] Insufficient events for ML modeling. Consider:")
                logging.error("  1. Combine toxicity grades")
                logging.error("  2. Use traditional models only")
                logging.error("  3. Collect more data")
        
        # Select primary toxicity
        if primary_toxicity:
            if primary_toxicity not in self.toxicity_cols:
                raise ValueError(f"Primary toxicity '{primary_toxicity}' not found in toxicity columns: {self.toxicity_cols}")
            target_col = primary_toxicity
        elif len(self.toxicity_cols) == 1:
            target_col = self.toxicity_cols[0]
        elif len(self.toxicity_cols) > 1:
            if interactive:
                print(f"\nMultiple toxicity endpoints detected: {self.toxicity_cols}")
                print("Select primary endpoint:")
                for i, col in enumerate(self.toxicity_cols, 1):
                    pos = (self.df[col] == 1).sum()
                    print(f"  {i}. {col} (events: {pos})")
                try:
                    choice = input("Selection: ")
                    target_col = self.toxicity_cols[int(choice)-1]
                except (ValueError, IndexError):
                    raise ValueError("Invalid selection")
            else:
                # Use first toxicity column
                target_col = self.toxicity_cols[0]
                logging.warning(f"[!] Multiple toxicity columns found. Using first: {target_col}")
        else:
            raise ValueError("No toxicity columns detected. Cannot prepare for analysis.")
        
        # Create analysis dataframe with standardized column name
        analysis_df = self.df.copy()
        analysis_df['Observed_Toxicity'] = analysis_df[target_col]
        
        # Ensure binary (0/1)
        analysis_df['Observed_Toxicity'] = analysis_df['Observed_Toxicity'].replace({np.nan: 0})
        analysis_df['Observed_Toxicity'] = (analysis_df['Observed_Toxicity'] > 0).astype(int)
        
        return analysis_df
    
    def get_summary(self) -> Dict:
        """
        Get summary statistics of clinical data.
        
        Returns
        -------
        dict
            Summary statistics
        """
        if self.df is None:
            return {}
        
        summary = {
            'total_rows': len(self.df),
            'total_columns': len(self.df.columns),
            'patient_id_col': self.patient_id_col,
            'toxicity_cols': self.toxicity_cols,
            'organ_col': self.organ_col,
        }
        
        if self.patient_id_col:
            summary['unique_patients'] = self.df[self.patient_id_col].nunique()
        
        if self.toxicity_cols:
            summary['toxicity_stats'] = {}
            for col in self.toxicity_cols:
                pos = (self.df[col] == 1).sum()
                neg = (self.df[col] == 0).sum()
                total = pos + neg
                summary['toxicity_stats'][col] = {
                    'positive': int(pos),
                    'negative': int(neg),
                    'total': int(total),
                    'prevalence': f"{pos/total*100:.1f}%" if total > 0 else "N/A"
                }
        
        return summary

