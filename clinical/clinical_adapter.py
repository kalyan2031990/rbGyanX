"""
Clinical Data Adapter for rbGyanX_basic

This module provides an adapter layer for reading standardized clinical Excel templates
with multiple sheets. It maps sheets to internal variables and provides data sufficiency
assessment for ML model training.

Author: rbGyanX Team
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import logging
import tempfile
import shutil
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ClinicalDataAdapter:
    """
    Adapter for reading and mapping standardized clinical Excel templates.
    
    Handles:
    - Multi-sheet Excel files
    - Sheet detection and mapping
    - Column standardization
    - Data sufficiency assessment
    - Missing value handling
    """
    
    # Expected sheet names (case-insensitive matching)
    SHEET_MAPPINGS = {
        'patient_core': ['patient_core', 'patient', 'patients', 'core', 'demographics'],
        'treatment': ['treatment', 'tx', 'therapy', 'treatment_params', 'treatment_parameters'],
        'tcp_outcome': ['tcp_outcome', 'tcp', 'tumor_outcome', 'tumor_control'],
        'ntcp_outcome': ['ntcp_outcome', 'ntcp', 'toxicity', 'complications', 'normal_tissue']
    }
    
    def __init__(self, excel_file: Path):
        """
        Initialize the Clinical Data Adapter.
        
        Parameters
        ----------
        excel_file : Path
            Path to Excel file with clinical data
        """
        self.excel_file = Path(excel_file)
        self.sheets_data = {}
        self.available_sheets = []
        self.mapped_data = {
            'patient_core': None,
            'treatment': None,
            'tcp_outcome': None,
            'ntcp_outcome': None
        }
        self.schema = self._load_schema()
    
    def _load_schema(self) -> Optional[Dict]:
        """
        Load clinical schema from JSON file.
        
        Returns
        -------
        Optional[Dict]
            Schema dictionary or None if schema file not found
        """
        schema_path = Path(__file__).parent / "clinical_schema.json"
        if schema_path.exists():
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[!] Could not load clinical schema: {e}")
                return None
        return None
        
    def read_excel(self) -> Dict[str, pd.DataFrame]:
        """
        Read Excel file and detect available sheets.
        
        Returns
        -------
        Dict[str, pd.DataFrame]
            Dictionary with sheet names as keys and DataFrames as values
        """
        if not self.excel_file.exists():
            logger.warning(f"[!] Excel file not found: {self.excel_file}")
            return {}
        
        try:
            # Read all sheets
            excel_data = pd.read_excel(self.excel_file, sheet_name=None, engine='openpyxl')
            self.available_sheets = list(excel_data.keys())
            self.sheets_data = excel_data
            
            logger.info(f"[OK] Loaded Excel file: {len(self.available_sheets)} sheet(s) found")
            for sheet_name in self.available_sheets:
                logger.info(f"  - {sheet_name}: {len(excel_data[sheet_name])} rows")
            
            return excel_data
        except Exception as e:
            logger.error(f"[X] Error reading Excel file: {e}")
            return {}
    
    def map_sheets(self) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Map detected sheets to standardized internal structure.
        
        Returns
        -------
        Dict[str, Optional[pd.DataFrame]]
            Dictionary with keys: patient_core, treatment, tcp_outcome, ntcp_outcome
        """
        if not self.sheets_data:
            self.read_excel()
        
        # Reset mapped data
        self.mapped_data = {
            'patient_core': None,
            'treatment': None,
            'tcp_outcome': None,
            'ntcp_outcome': None
        }
        
        # Map sheets by name matching (case-insensitive)
        for sheet_name, df in self.sheets_data.items():
            sheet_lower = sheet_name.lower().strip()
            
            # Try to match to known sheet types
            for target_key, possible_names in self.SHEET_MAPPINGS.items():
                if sheet_lower in [name.lower() for name in possible_names]:
                    if self.mapped_data[target_key] is None:
                        self.mapped_data[target_key] = df.copy()
                        logger.info(f"[OK] Mapped sheet '{sheet_name}' -> {target_key}")
                    else:
                        logger.warning(f"[!] Multiple sheets match {target_key}, using first match")
                    break
        
        # If no explicit mapping found, try to infer from content
        for sheet_name, df in self.sheets_data.items():
            if sheet_name not in [s for s in self.available_sheets if any(
                s.lower() in names for names in self.SHEET_MAPPINGS.values()
            )]:
                # Try to infer sheet type from columns
                cols_lower = [c.lower() for c in df.columns]
                
                # Check for patient ID columns
                patient_id_keywords = ['patientid', 'patient_id', 'id', 'patient']
                has_patient_id = any(kw in ' '.join(cols_lower) for kw in patient_id_keywords)
                
                # Check for outcome columns
                outcome_keywords = ['outcome', 'toxicity', 'complication', 'event', 'tcp', 'ntcp']
                has_outcome = any(kw in ' '.join(cols_lower) for kw in outcome_keywords)
                
                # Check for treatment columns
                treatment_keywords = ['dose', 'fraction', 'technique', 'treatment', 'tx']
                has_treatment = any(kw in ' '.join(cols_lower) for kw in treatment_keywords)
                
                # Infer mapping
                if has_patient_id and not has_outcome and not has_treatment:
                    if self.mapped_data['patient_core'] is None:
                        self.mapped_data['patient_core'] = df.copy()
                        logger.info(f"[OK] Inferred sheet '{sheet_name}' -> patient_core (from columns)")
                elif has_treatment:
                    if self.mapped_data['treatment'] is None:
                        self.mapped_data['treatment'] = df.copy()
                        logger.info(f"[OK] Inferred sheet '{sheet_name}' -> treatment (from columns)")
                elif has_outcome and 'tcp' in ' '.join(cols_lower):
                    if self.mapped_data['tcp_outcome'] is None:
                        self.mapped_data['tcp_outcome'] = df.copy()
                        logger.info(f"[OK] Inferred sheet '{sheet_name}' -> tcp_outcome (from columns)")
                elif has_outcome:
                    if self.mapped_data['ntcp_outcome'] is None:
                        self.mapped_data['ntcp_outcome'] = df.copy()
                        logger.info(f"[OK] Inferred sheet '{sheet_name}' -> ntcp_outcome (from columns)")
        
        # Phase 3: split single combined clinical sheets (HN toxicity tables)
        self._split_combined_clinical_sheets()
        
        # Fill missing values with NaN
        for key, df in self.mapped_data.items():
            if df is not None:
                self.mapped_data[key] = df.fillna(np.nan)
        
        return self.mapped_data

    def _split_combined_clinical_sheets(self) -> None:
        """
        Phase 3: one real-world sheet with demographics + dose + toxicity -> logical sheets.
        """
        if (
            self.mapped_data.get("patient_core")
            and self.mapped_data.get("ntcp_outcome")
            and self.mapped_data.get("tcp_outcome")
        ):
            return

        combined = self.mapped_data.get("treatment")
        if combined is None:
            for df in self.sheets_data.values():
                cols_lower = " ".join(c.lower() for c in df.columns)
                if any(k in cols_lower for k in ("toxicity", "xerostomia", "complication")) and any(
                    k in cols_lower for k in ("patientid", "patient_id", "patient_anoid")
                ):
                    combined = df
                    break
        if combined is None:
            return

        cols = list(combined.columns)
        cols_lower_map = {c: c.lower() for c in cols}
        col_blob = " ".join(cols_lower_map.values())

        def pick_cols(keywords):
            return [c for c in cols if any(kw in cols_lower_map[c] for kw in keywords)]

        id_cols = pick_cols(
            ("patientid", "patient_id", "patient_anoid", "patientid", "anoid", "patientid")
        )
        demo_cols = pick_cols(("age", "sex", "gender", "ecog", "stage", "diagnosis", "smoking", "chemo"))
        tx_cols = pick_cols(
            ("dose", "fraction", "technique", "total", "n_frac", "duration", "organ", "alpha_beta")
        )
        def is_tcp_outcome_col(col: str) -> bool:
            cl = cols_lower_map[col]
            return any(
                kw in cl
                for kw in (
                    "tumoroutcome",
                    "tumor_outcome",
                    "tumorcontrol",
                    "tumor_control",
                    "local_control",
                    "recurrence",
                    "tcp",
                )
            ) and "toxicity" not in cl

        tox_cols = [
            c
            for c in pick_cols(
                ("toxicity", "xerostomia", "complication", "ntcp", "follow_up", "outcome", "event")
            )
            if not is_tcp_outcome_col(c)
        ]
        tcp_cols = pick_cols(
            (
                "tumoroutcome",
                "tumor_outcome",
                "tumorcontrol",
                "tumor_control",
                "local_control",
                "recurrence",
                "tcp",
            )
        )

        pid = id_cols[0] if id_cols else None
        if not pid:
            return

        demo_keep = [pid] + [c for c in demo_cols if c != pid]

        if self.mapped_data["patient_core"] is None:
            self.mapped_data["patient_core"] = combined[demo_keep].drop_duplicates(subset=[pid]).copy()
            logger.info("[OK] Split combined sheet -> patient_core")

        if self.mapped_data["treatment"] is None or self.mapped_data["treatment"] is combined:
            tx_keep = [pid] + [c for c in tx_cols if c not in demo_keep and c != pid]
            if len(tx_keep) > 1:
                self.mapped_data["treatment"] = combined[tx_keep].drop_duplicates(subset=[pid]).copy()
                logger.info("[OK] Split combined sheet -> treatment")

        if self.mapped_data["tcp_outcome"] is None and tcp_cols:
            self.mapped_data["tcp_outcome"] = combined[[pid] + tcp_cols].drop_duplicates(subset=[pid]).copy()
            logger.info("[OK] Split combined sheet -> tcp_outcome")

        if self.mapped_data["ntcp_outcome"] is None and tox_cols:
            ntcp_keep = [pid] + tox_cols
            if "organ" in combined.columns and "organ" not in ntcp_keep:
                ntcp_keep.append("organ")
            self.mapped_data["ntcp_outcome"] = combined[ntcp_keep].drop_duplicates().copy()
            logger.info("[OK] Split combined sheet -> ntcp_outcome")
        elif self.mapped_data["ntcp_outcome"] is not None and tcp_cols:
            # Re-split if TumorOutcome was previously grouped with toxicity columns
            drop_tcp = [c for c in tcp_cols if c in self.mapped_data["ntcp_outcome"].columns]
            if drop_tcp:
                ntcp_keep = [c for c in self.mapped_data["ntcp_outcome"].columns if c not in drop_tcp]
                self.mapped_data["ntcp_outcome"] = self.mapped_data["ntcp_outcome"][ntcp_keep].copy()
                if self.mapped_data["tcp_outcome"] is None:
                    self.mapped_data["tcp_outcome"] = combined[[pid] + tcp_cols].drop_duplicates(
                        subset=[pid]
                    ).copy()
                    logger.info("[OK] Split combined sheet -> tcp_outcome (from ntcp cleanup)")

        # If treatment was only sheet and we still have full combined as treatment, trim
        if self.mapped_data["treatment"] is combined and tx_cols:
            self.mapped_data["treatment"] = combined[[pid] + tx_cols].drop_duplicates(subset=[pid]).copy()
    
    def validate_against_schema(self, sheet_name: str, df: pd.DataFrame) -> List[str]:
        """
        Validate a DataFrame against the clinical schema.
        
        Parameters
        ----------
        sheet_name : str
            Name of the sheet (patient_core, treatment, tcp_outcome, ntcp_outcome)
        df : pd.DataFrame
            DataFrame to validate
        
        Returns
        -------
        List[str]
            List of validation messages (empty if valid)
        """
        messages = []
        
        if not self.schema or 'sheets' not in self.schema:
            return messages  # No schema available, skip validation
        
        if sheet_name not in self.schema['sheets']:
            return messages  # Sheet not in schema, skip
        
        sheet_schema = self.schema['sheets'][sheet_name]
        if 'fields' not in sheet_schema:
            return messages
        
        # Check required fields
        for field_name, field_spec in sheet_schema['fields'].items():
            if field_spec.get('required', False):
                # Check if any alias exists in columns
                aliases = field_spec.get('aliases', []) + [field_name]
                found = False
                for alias in aliases:
                    if alias in df.columns:
                        found = True
                        break
                
                if not found:
                    messages.append(f"{sheet_name}: Missing required field '{field_name}' (or aliases: {', '.join(aliases[:3])})")
        
        # Check data types for found fields
        for field_name, field_spec in sheet_schema['fields'].items():
            aliases = field_spec.get('aliases', []) + [field_name]
            found_col = None
            for alias in aliases:
                if alias in df.columns:
                    found_col = alias
                    break
            
            if found_col:
                expected_type = field_spec.get('data_type', 'string')
                actual_dtype = str(df[found_col].dtype)
                
                # Basic type checking
                if expected_type == 'numeric' and not ('int' in actual_dtype or 'float' in actual_dtype):
                    messages.append(f"{sheet_name}.{found_col}: Expected numeric, got {actual_dtype}")
                elif expected_type == 'integer' and 'int' not in actual_dtype:
                    messages.append(f"{sheet_name}.{found_col}: Expected integer, got {actual_dtype}")
                elif expected_type == 'binary' and df[found_col].nunique() > 2:
                    messages.append(f"{sheet_name}.{found_col}: Expected binary (0/1), got {df[found_col].nunique()} unique values")
        
        return messages
    
    def assess_sufficiency(self, analysis_mode: str) -> Tuple[str, List[str]]:
        """
        Assess data sufficiency for ML model training.
        
        Parameters
        ----------
        analysis_mode : str
            Analysis mode: 'TCP_ONLY', 'NTCP_ONLY', or 'TCP_NTCP'
        
        Returns
        -------
        Tuple[str, List[str]]
            (status, messages) where status is 'usable', 'partial', or 'insufficient'
        """
        messages = []
        has_patient_core = self.mapped_data['patient_core'] is not None
        has_treatment = self.mapped_data['treatment'] is not None
        has_tcp_outcome = self.mapped_data['tcp_outcome'] is not None
        has_ntcp_outcome = self.mapped_data['ntcp_outcome'] is not None
        
        # Validate against schema if available
        if self.schema:
            for sheet_name, df in self.mapped_data.items():
                if df is not None:
                    schema_messages = self.validate_against_schema(sheet_name, df)
                    messages.extend(schema_messages)
        
        # patient_core from split sheet or demographics on treatment
        if not has_patient_core and has_treatment:
            tx = self.mapped_data["treatment"]
            demo_cols = [
                c
                for c in tx.columns
                if any(kw in c.lower() for kw in ("age", "sex", "gender", "patient"))
            ]
            if demo_cols:
                has_patient_core = True
                messages.append(
                    "patient_core inferred from treatment sheet (combined clinical table)"
                )

        if not has_patient_core:
            messages.append("Missing patient_core sheet")
        elif self.mapped_data["patient_core"] is not None:
            df = self.mapped_data['patient_core']
            # Check for patient ID column
            patient_id_cols = [c for c in df.columns if any(
                kw in c.lower() for kw in ['patientid', 'patient_id', 'id', 'patient']
            )]
            if not patient_id_cols:
                messages.append("patient_core: No patient ID column detected")
            else:
                # Check for sufficient patients
                patient_id_col = patient_id_cols[0]
                unique_patients = df[patient_id_col].nunique()
                if unique_patients < 10:
                    messages.append(f"patient_core: Only {unique_patients} unique patients (need ≥10 for ML)")
        
        # Mode-specific checks
        if analysis_mode in ['TCP_ONLY', 'TCP_NTCP']:
            if not has_tcp_outcome:
                messages.append("Missing tcp_outcome sheet (required for TCP analysis)")
            else:
                df = self.mapped_data['tcp_outcome']
                # Check for outcome column
                outcome_cols = [c for c in df.columns if any(
                    kw in c.lower() for kw in ['outcome', 'tcp', 'control', 'event']
                )]
                if outcome_cols:
                    outcome_col = outcome_cols[0]
                    # Check for binary outcomes
                    unique_vals = df[outcome_col].dropna().unique()
                    positive_events = (df[outcome_col] == 1).sum() if len(unique_vals) <= 2 else 0
                    if positive_events < 5:
                        messages.append(f"tcp_outcome: Only {positive_events} positive events (need ≥5 for ML)")
        
        if analysis_mode in ['NTCP_ONLY', 'TCP_NTCP']:
            if not has_ntcp_outcome and has_treatment:
                tx = self.mapped_data["treatment"]
                if any(
                    kw in c.lower()
                    for c in tx.columns
                    for kw in ("toxicity", "xerostomia", "complication", "ntcp")
                ):
                    has_ntcp_outcome = True
            if not has_ntcp_outcome:
                messages.append("Missing ntcp_outcome sheet (required for NTCP analysis)")
            elif self.mapped_data["ntcp_outcome"] is not None:
                df = self.mapped_data['ntcp_outcome']
                # Check for outcome column
                outcome_cols = [c for c in df.columns if any(
                    kw in c.lower() for kw in ['outcome', 'toxicity', 'ntcp', 'complication', 'event']
                )]
                if outcome_cols:
                    outcome_col = outcome_cols[0]
                    # Check for binary outcomes
                    unique_vals = df[outcome_col].dropna().unique()
                    positive_events = (df[outcome_col] == 1).sum() if len(unique_vals) <= 2 else 0
                    if positive_events < 5:
                        messages.append(f"ntcp_outcome: Only {positive_events} positive events (need ≥5 for ML)")
        
        # Determine status
        if not messages:
            status = 'usable'
        elif len(messages) <= 2 and has_patient_core:
            status = 'partial'
        else:
            status = 'insufficient'
        
        return status, messages
    
    def create_standardized_file(self, output_path: Optional[Path] = None) -> Path:
        """
        Create a standardized single-sheet Excel file compatible with existing code.
        
        This merges all available sheets into a single sheet that downstream code
        can process using ClinicalDataHandler.
        
        Parameters
        ----------
        output_path : Path, optional
            Path for output file. If None, creates temporary file.
        
        Returns
        -------
        Path
            Path to created standardized file
        """
        if output_path is None:
            # Create temporary file
            temp_dir = Path(tempfile.gettempdir()) / 'rbgyanx_adapted'
            temp_dir.mkdir(exist_ok=True)
            output_path = temp_dir / f"adapted_{self.excel_file.stem}.xlsx"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Start with patient_core as base
        if self.mapped_data['patient_core'] is not None:
            merged_df = self.mapped_data['patient_core'].copy()
        else:
            # If no patient_core, try to create from first available sheet
            first_sheet = next(iter(self.sheets_data.values()), None)
            if first_sheet is None:
                raise ValueError("No data available to create standardized file")
            merged_df = first_sheet.copy()
        
        # Merge treatment data
        if self.mapped_data['treatment'] is not None:
            # Find patient ID columns for merging
            patient_id_cols_base = [c for c in merged_df.columns if any(
                kw in c.lower() for kw in ['patientid', 'patient_id', 'id', 'patient']
            )]
            patient_id_cols_tx = [c for c in self.mapped_data['treatment'].columns if any(
                kw in c.lower() for kw in ['patientid', 'patient_id', 'id', 'patient']
            )]
            
            if patient_id_cols_base and patient_id_cols_tx:
                merged_df = merged_df.merge(
                    self.mapped_data['treatment'],
                    left_on=patient_id_cols_base[0],
                    right_on=patient_id_cols_tx[0],
                    how='left',
                    suffixes=('', '_tx')
                )
        
        # Merge outcome data (both TCP and NTCP)
        for outcome_type in ['tcp_outcome', 'ntcp_outcome']:
            if self.mapped_data[outcome_type] is not None:
                df_outcome = self.mapped_data[outcome_type]
                patient_id_cols_base = [c for c in merged_df.columns if any(
                    kw in c.lower() for kw in ['patientid', 'patient_id', 'id', 'patient']
                )]
                patient_id_cols_outcome = [c for c in df_outcome.columns if any(
                    kw in c.lower() for kw in ['patientid', 'patient_id', 'id', 'patient']
                )]
                
                if patient_id_cols_base and patient_id_cols_outcome:
                    suffix = '_tcp' if outcome_type == 'tcp_outcome' else '_ntcp'
                    merged_df = merged_df.merge(
                        df_outcome,
                        left_on=patient_id_cols_base[0],
                        right_on=patient_id_cols_outcome[0],
                        how='left',
                        suffixes=('', suffix)
                    )
        
        # Fill NaN values
        merged_df = merged_df.fillna(np.nan)
        
        # Save to Excel
        try:
            merged_df.to_excel(output_path, index=False, engine='openpyxl')
            logger.info(f"[OK] Created standardized file: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"[X] Error creating standardized file: {e}")
            raise
    
    def get_summary(self) -> Dict:
        """
        Get summary of mapped data.
        
        Returns
        -------
        Dict
            Summary dictionary
        """
        summary = {
            'excel_file': str(self.excel_file),
            'available_sheets': self.available_sheets,
            'mapped_sheets': {},
            'row_counts': {}
        }
        
        for key, df in self.mapped_data.items():
            if df is not None:
                summary['mapped_sheets'][key] = True
                summary['row_counts'][key] = len(df)
            else:
                summary['mapped_sheets'][key] = False
                summary['row_counts'][key] = 0
        
        return summary


def adapt_clinical_data(excel_file: Path, analysis_mode: str, 
                       output_dir: Optional[Path] = None) -> Tuple[Dict, str, List[str], Optional[Path]]:
    """
    Convenience function to adapt clinical data.
    
    Parameters
    ----------
    excel_file : Path
        Path to input Excel file
    analysis_mode : str
        Analysis mode: 'TCP_ONLY', 'NTCP_ONLY', or 'TCP_NTCP'
    output_dir : Path, optional
        Directory for output file. If None, uses temp directory.
    
    Returns
    -------
    Tuple[Dict, str, List[str], Optional[Path]]
        (mapped_data, status, messages, standardized_file_path)
    """
    adapter = ClinicalDataAdapter(excel_file)
    
    # Read and map
    adapter.read_excel()
    mapped_data = adapter.map_sheets()
    
    # Assess sufficiency
    status, messages = adapter.assess_sufficiency(analysis_mode)
    
    # Create standardized file
    standardized_file = None
    try:
        if output_dir:
            output_path = output_dir / f"adapted_{excel_file.stem}.xlsx"
        else:
            output_path = None  # Will use temp directory
        
        standardized_file = adapter.create_standardized_file(output_path)
    except Exception as e:
        logger.warning(f"[!] Could not create standardized file: {e}")
    
    return mapped_data, status, messages, standardized_file

