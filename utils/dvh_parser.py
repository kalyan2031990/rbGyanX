"""
rbGyanX v1.0 - Universal DVH Parser
====================================
Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

Intelligent DVH parser supporting multiple formats:
- Eclipse TXT (Varian Eclipse TPS)
- Simple CSV (Dose, Volume)
- DICOM RT (RTSTRUCT + RTDOSE) - Coming in v1.1
- Other TPS exports

Author: rbGyanX Team
License: MIT

NOTE: Phase 1B.4 Refactoring - Core computation moved to rbgyanx.core.dvh
This module maintains backward compatibility by delegating to core functions.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re
from collections import Counter
from datetime import datetime
from typing import Tuple, Dict, Optional

# Backward compatibility: Import from new location
# Phase 1B.4 refactoring: Core computation moved to rbgyanx.core.dvh
from rbgyanx.core.dvh.conversions import (
    convert_to_cumulative as _convert_to_cumulative,
    convert_to_differential as _convert_to_differential,
)
from rbgyanx.utils.numeric_compat import trapz as _trapz


class UniversalDVHParser:
    """
    Intelligent DVH parser supporting multiple formats with structure normalization.
    
    Supported Formats:
    - Eclipse TXT (Varian Eclipse TPS)
    - Simple CSV (Dose, Volume)
    - DICOM RT (RTSTRUCT + RTDOSE) - Coming in v1.1
    - Other TPS exports
    
    Attributes
    ----------
    file_path : Path
        Path to the DVH file
    format : str
        Detected format type
    patient_id : str
        Extracted patient ID
    structure_name : str
        Extracted structure name (normalized)
    dvh_type : str
        Type of DVH: 'cumulative' or 'differential'
    is_tumor : bool
        Whether the structure is a tumor/PTV
    """
    
    # Structure normalization mapping
    STRUCTURE_NORMALIZATION = {
        # Parotid glands - Combined/Bilateral
        'parotid': {
            'patterns': [
                # Explicit "combined" variations
                r'comb.*pa?r.*t.*d',      # COMB PRTD, COMB_PRTD, Combined Parotid
                r'com\s+p.*r.*t.*d',      # COM PRTD (with space)
                r'comd.*p.*r.*t.*d',      # COMD PRTD (typo variation)
                r'combo.*pa?r.*t.*d',     # COMBO PAROTID, COMBO PRTD
                r'combo\s*$',             # Just "COMBO" alone
                
                # "Total" variations
                r'total.*pa?r.*t.*d',     # TOTAL PRTD, TOTAL_PAROTID, TOTAL PAROTID
                r'tot.*pa?r.*t.*d',       # TOT PAROTD, TOT PAROTID, TOT_PRTD
                
                # Generic "parotid" (when no laterality specified)
                r'^parotid$',             # Just "Parotid" alone (exact match)
                r'^pa?r.*t.*d$',          # PRTD, PAROTD (standalone)
            ],
            'normalized': 'Parotid_Combined',
            'laterality': None
        },
        
        # Parotid - Right
        'parotid_right': {
            'patterns': [
                r'\brt\b.*pa?r.*t.*d',     # Rt Parotid, RT PAROTID, RT_PRTD
                r'\bright\b.*pa?r.*t.*d',  # Right Parotid, RIGHT_PAROTID
                r'pa?r.*t.*d.*\brt\b',     # PAROTID RT, PRTD_RT (reversed order)
                r'pa?r.*t.*d.*\bright\b',  # PAROTID RIGHT (reversed)
            ],
            'normalized': 'Parotid_Right',
            'laterality': 'R'
        },
        
        # Parotid - Left  
        'parotid_left': {
            'patterns': [
                r'\blt\b.*pa?r.*t.*d',     # Lt Parotid, LT PAROTID, LT_PRTD
                r'\bleft\b.*pa?r.*t.*d',   # Left Parotid, LEFT_PAROTID
                r'pa?r.*t.*d.*\blt\b',     # PAROTID LT, PRTD_LT (reversed)
                r'pa?r.*t.*d.*\bleft\b',   # PAROTID LEFT (reversed)
            ],
            'normalized': 'Parotid_Left',
            'laterality': 'L'
        },
        
        # Spinal Cord (exclude PRV)
        'spinalcord': {
            'patterns': [
                r'\bspinal.*cord\b',       # Spinal Cord, SPINAL CORD, spinal cord
                r'\bcord\b',               # CORD, Cord, cord (as standalone word)
            ],
            'exclude_patterns': [
                r'\bprv\b.*cord',          # PRV Cord, PRV_CORD (planning risk volume)
                r'cord.*\bprv\b',          # CORD_PRV (reversed)
            ],
            'normalized': 'SpinalCord',
            'laterality': None
        },
        
        # Larynx
        'larynx': {
            'patterns': [
                r'larynx',  # Removed \b word boundaries - matches Larynx, LARYNX_T, Larynx_Total, etc.
            ],
            'normalized': 'Larynx',
            'laterality': None
        },
        
        # Target structures (PTV, GTV, CTV) - explicitly include for TCP analysis
        'ptv': {
            'patterns': [
                r'\bptv\b',           # PTV, PTV_70, etc.
                r'\bptv\d+',          # PTV70, PTV50, etc.
                r'ptv.*\d+',          # PTV 70, PTV-70, etc.
            ],
            'normalized': 'PTV',
            'laterality': None
        },
        'gtv': {
            'patterns': [
                r'\bgtv\b',           # GTV, GTV_T, etc.
                r'\bgtv\d+',          # GTV70, etc.
            ],
            'normalized': 'GTV',
            'laterality': None
        },
        'ctv': {
            'patterns': [
                r'\bctv\b',           # CTV, CTV_T, etc.
                r'\bctv\d+',          # CTV70, etc.
            ],
            'normalized': 'CTV',
            'laterality': None
        },
        'tumor': {
            'patterns': [
                r'\btumor\b',         # Tumor, TUMOR, etc.
                r'\btarget\b',        # Target, TARGET, etc.
            ],
            'normalized': 'Tumor',
            'laterality': None
        },
    }
    
    def normalize_structure_name(self, structure_name: str, for_file_naming: bool = False) -> Optional[str]:
        """
        Intelligently normalize structure names to standard format.
        
        Parameters
        ----------
        structure_name : str
            Raw structure name from DVH file
        for_file_naming : bool, default False
            If True, normalize Parotid variants to just "Parotid" for consistent file naming
        
        Returns
        -------
        str or None
            Normalized structure name, or None if structure should be excluded
        
        Examples
        --------
        >>> parser.normalize_structure_name("COMB PRTD")
        'Parotid_Combined'
        
        >>> parser.normalize_structure_name("COMB PRTD", for_file_naming=True)
        'Parotid'
        
        >>> parser.normalize_structure_name("Rt Parotid")
        'Parotid_Right'
        
        >>> parser.normalize_structure_name("SPINAL CORD")
        'SpinalCord'
        
        >>> parser.normalize_structure_name("PRV Cord")
        None  # Excluded
        """
        # Convert to lowercase for pattern matching
        structure_lower = structure_name.lower().strip()
        
        # Check each normalization rule
        for organ_key, rules in self.STRUCTURE_NORMALIZATION.items():
            # Check exclusion patterns first
            if 'exclude_patterns' in rules:
                for exclude_pattern in rules['exclude_patterns']:
                    if re.search(exclude_pattern, structure_lower, re.IGNORECASE):
                        print(f"  [EXCLUDE] {structure_name} (PRV/planning structure)")
                        return None  # Exclude this structure
            
            # Check inclusion patterns
            if 'patterns' in rules:
                for pattern in rules['patterns']:
                    if re.search(pattern, structure_lower, re.IGNORECASE):
                        normalized_name = rules['normalized']
                        
                        # For file naming, normalize all Parotid variants to "Parotid"
                        if for_file_naming and 'Parotid' in normalized_name:
                            normalized_name = 'Parotid'
                        
                        if structure_name != normalized_name:
                            print(f"  [NORMALIZE] {structure_name} -> {normalized_name}")
                        return normalized_name
        
        # If no match found, return cleaned original name
        cleaned = structure_name.replace('_', ' ').strip()
        if structure_name != cleaned:
            print(f"  [INFO] No normalization rule for: {structure_name} (using: {cleaned})")
        return cleaned
    
    def __init__(self, file_path):
        """
        Initialize the Universal DVH Parser.
        
        Parameters
        ----------
        file_path : str or Path
            Path to the DVH file to parse
        """
        self.file_path = Path(file_path)
        self.format = None
        self.patient_id = None
        self.structure_name = None
        self.dvh_type = None  # 'cumulative' or 'differential'
        self.is_tumor = False
        self.total_volume = None
        
    def detect_format(self) -> str:
        """
        Auto-detect file format based on extension and content.
        
        Returns
        -------
        str
            Format type: 'Eclipse_TXT', 'Simple_CSV', 'DICOM', 'Generic_TXT', 
            'Generic_CSV', or 'Unknown'
        """
        ext = self.file_path.suffix.lower()
        
        if ext == '.dcm':
            return 'DICOM'
        elif ext in ['.txt', '.text']:
            # Check if Eclipse format
            try:
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_lines = [f.readline() for _ in range(5)]
                
                if any('Patient Name' in line or 'Patient ID' in line for line in first_lines):
                    return 'Eclipse_TXT'
                else:
                    return 'Generic_TXT'
            except Exception:
                return 'Generic_TXT'
        elif ext == '.csv':
            # Check header
            try:
                df = pd.read_csv(self.file_path, nrows=1)
                cols = [col.lower() for col in df.columns]
                if any('dose' in col for col in cols) and any('volume' in col for col in cols):
                    return 'Simple_CSV'
                else:
                    return 'Generic_CSV'
            except Exception:
                return 'Generic_CSV'
        else:
            return 'Unknown'
    
    def parse_eclipse_txt(self) -> Tuple[Dict, pd.DataFrame]:
        """
        Parse Varian Eclipse TXT export.
        
        Extracts:
        - Patient ID from header
        - Structure name
        - Total volume
        - DVH data with dose unit conversion (cGy → Gy)
        
        Returns
        -------
        metadata : dict
            Extracted metadata (patient_id, structure_name, dvh_type, is_tumor, total_volume)
        dvh_data : pd.DataFrame
            DVH data with columns: Dose[Gy], Volume[cm3]
        """
        metadata = {}
        dvh_data = None
        
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Extract metadata
        data_start = None
        for i, line in enumerate(lines[:50]):  # Check first 50 lines for header
            if 'Patient ID' in line or 'PatientID' in line:
                # "Patient ID           : 2019-1927" or "PatientID: 2019-1927"
                parts = line.split(':', 1)
                if len(parts) > 1:
                    metadata['patient_id'] = parts[1].strip()
            
            elif 'Structure:' in line:
                # "Structure: SPINAL CORD"
                raw_structure = line.split(':', 1)[1].strip()
                
                # NORMALIZE STRUCTURE NAME
                normalized_structure = self.normalize_structure_name(raw_structure)
                
                if normalized_structure is None:
                    # Structure should be excluded (e.g., PRV Cord)
                    raise ValueError(f"Structure {raw_structure} excluded (planning structure)")
                
                metadata['structure_name'] = normalized_structure
                metadata['structure_name_original'] = raw_structure  # Keep original for reference
                
                # Detect if tumor/PTV (use normalized name)
                tumor_keywords = ['PTV', 'GTV', 'CTV', 'TUMOR', 'TARG']
                metadata['is_tumor'] = any(kw in normalized_structure.upper() for kw in tumor_keywords)
            
            elif 'Volume [cm' in line or 'Volume[cm' in line:
                # "Volume [cm³]: 19.3" or "Volume[cm3]: 19.3"
                vol_str = re.search(r'[\d.]+', line.split(':')[1] if ':' in line else line)
                if vol_str:
                    metadata['total_volume'] = float(vol_str.group())
            
            elif 'Type' in line and 'DVH' in line:
                # "Type                 : Cumulative Dose Volume Histogram"
                if 'Cumulative' in line:
                    metadata['dvh_type'] = 'cumulative'
                elif 'Differential' in line:
                    metadata['dvh_type'] = 'differential'
            
            elif 'Dose [cGy]' in line or 'Dose[cGy]' in line:
                # Found data section start
                data_start = i + 1
                break
        
        # If data_start not found, look for numeric data lines
        if data_start is None:
            for i, line in enumerate(lines):
                # Look for lines starting with numbers (dose values)
                stripped = line.strip()
                if stripped and (stripped[0].isdigit() or stripped[0] == '-'):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        try:
                            float(parts[0])
                            float(parts[1])
                            data_start = i
                            break
                        except ValueError:
                            continue
        
        if data_start is None:
            raise ValueError(f"Could not find DVH data section in {self.file_path.name}")
        
        # Parse DVH data (dose in cGy, volume in cm³)
        dose_data = []
        volume_data = []
        
        for line in lines[data_start:]:
            line = line.strip()
            if not line or line.startswith('-') and len(line) > 10:
                # Skip separator lines
                continue
            
            # Handle various separators: spaces, tabs, commas
            parts = re.split(r'[,\s\t]+', line)
            if len(parts) >= 2:
                try:
                    dose = float(parts[0])
                    volume = float(parts[1])
                    
                    # Convert cGy to Gy if dose > 150 (typical threshold)
                    if dose > 150:
                        dose = dose / 100.0
                    
                    dose_data.append(dose)
                    volume_data.append(volume)
                except (ValueError, IndexError):
                    continue
        
        if not dose_data:
            raise ValueError(f"No valid DVH data found in {self.file_path.name}")
        
        dvh_data = pd.DataFrame({
            'Dose[Gy]': dose_data,
            'Volume[cm3]': volume_data
        })
        
        # Detect DVH type if not specified in header
        if 'dvh_type' not in metadata:
            metadata['dvh_type'] = self._detect_dvh_type(volume_data)
        
        return metadata, dvh_data
    
    def parse_simple_csv(self) -> Tuple[Dict, pd.DataFrame]:
        """
        Parse simple CSV format with Dose and Volume columns.
        
        Expected format:
        - Header: "Dose[Gy],Volume[cm3]" or similar
        - Data: numeric values
        
        Returns
        -------
        metadata : dict
            Extracted metadata (patient_id, structure_name, dvh_type, is_tumor)
        dvh_data : pd.DataFrame
            DVH data with standardized columns: Dose[Gy], Volume[cm3]
        """
        try:
            df = pd.read_csv(self.file_path)
        except Exception as e:
            raise ValueError(f"Could not read CSV file: {str(e)}")
        
        # Standardize column names (case-insensitive)
        col_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'dose' in col_lower:
                col_map[col] = 'Dose[Gy]'
            elif 'volume' in col_lower or 'vol' in col_lower:
                col_map[col] = 'Volume[cm3]'
        
        if len(col_map) < 2:
            raise ValueError(f"Could not identify Dose and Volume columns in {self.file_path.name}")
        
        df = df.rename(columns=col_map)
        
        # Ensure we have the required columns
        if 'Dose[Gy]' not in df.columns or 'Volume[cm3]' not in df.columns:
            raise ValueError(f"Missing required columns (Dose[Gy], Volume[cm3]) in {self.file_path.name}")
        
        # Extract metadata from filename
        # Example: PT012_Parotid.csv or Patient_001_Parotid.csv
        filename = self.file_path.stem
        parts = filename.split('_')
        
        # Extract and normalize structure name
        raw_structure = '_'.join(parts[1:]) if len(parts) > 1 else 'Unknown'
        normalized_structure = self.normalize_structure_name(raw_structure)
        
        if normalized_structure is None:
            raise ValueError(f"Structure {raw_structure} excluded")
        
        metadata = {
            'patient_id': parts[0] if len(parts) > 0 else 'Unknown',
            'structure_name': normalized_structure,
            'structure_name_original': raw_structure,
            'dvh_type': 'differential',  # Assume differential for simple CSV
            'is_tumor': any(kw in normalized_structure.upper() for kw in ['PTV', 'GTV', 'CTV', 'TUMOR', 'TARG'])
        }
        
        # Detect DVH type from data
        metadata['dvh_type'] = self._detect_dvh_type(df['Volume[cm3]'].values)
        
        return metadata, df[['Dose[Gy]', 'Volume[cm3]']]
    
    def parse_dicom_rt(self) -> Tuple[Dict, pd.DataFrame]:
        """
        Parse DICOM RT files and calculate DVH.
        
        Requires:
        - RTSTRUCT file (structure set)
        - RTDOSE file (dose distribution)
        
        Note: This is a placeholder for v1.1 implementation.
        
        Returns
        -------
        metadata : dict
            Extracted metadata
        dvh_data : pd.DataFrame
            DVH data
        
        Raises
        ------
        NotImplementedError
            DICOM support is planned for v1.1
        """
        try:
            import pydicom
            from rt_utils import RTStructBuilder
        except ImportError:
            raise ImportError(
                "DICOM support requires: pip install pydicom rt-utils\n"
                "DICOM DVH extraction will be available in rbGyanX v1.1"
            )
        
        # Implementation for DICOM DVH extraction
        # (Complex - requires dose grid + structure contours)
        raise NotImplementedError(
            "DICOM DVH extraction is planned for rbGyanX v1.1.\n"
            "For now, please export DVH data from your TPS as TXT or CSV format."
        )
    
    def _detect_dvh_type(self, volume_data: np.ndarray) -> str:
        """
        Detect whether DVH is cumulative or differential.
        
        Heuristic: cumulative DVH is monotonically non-increasing.
        
        Parameters
        ----------
        volume_data : np.ndarray
            Volume values from DVH
        
        Returns
        -------
        str
            'cumulative' or 'differential'
        """
        if len(volume_data) < 2:
            return 'unknown'
        
        # Check if monotonically non-increasing (cumulative)
        # Allow small numerical errors
        diff = np.diff(volume_data)
        if np.all(diff <= 1e-6):
            return 'cumulative'
        else:
            return 'differential'
    
    def parse(self) -> Tuple[Dict, pd.DataFrame]:
        """
        Universal parse method that auto-detects format and parses accordingly.
        
        Returns
        -------
        metadata : dict
            Patient ID, structure name, DVH type, is_tumor, etc.
        dvh_data : pd.DataFrame
            Columns: Dose[Gy], Volume[cm3]
        
        Raises
        ------
        ValueError
            If format is unsupported or file cannot be parsed
        FileNotFoundError
            If file does not exist
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"DVH file not found: {self.file_path}")
        
        self.format = self.detect_format()
        
        if self.format == 'Eclipse_TXT':
            metadata, dvh_data = self.parse_eclipse_txt()
        elif self.format == 'Simple_CSV':
            metadata, dvh_data = self.parse_simple_csv()
        elif self.format == 'DICOM':
            metadata, dvh_data = self.parse_dicom_rt()
        elif self.format == 'Generic_TXT':
            # Try Eclipse parser as fallback
            try:
                metadata, dvh_data = self.parse_eclipse_txt()
            except Exception:
                raise ValueError(
                    f"Could not parse generic TXT file: {self.file_path.name}\n"
                    "Please ensure it follows Eclipse TXT format or convert to CSV."
                )
        elif self.format == 'Generic_CSV':
            # Try simple CSV parser as fallback
            try:
                metadata, dvh_data = self.parse_simple_csv()
            except Exception:
                raise ValueError(
                    f"Could not parse CSV file: {self.file_path.name}\n"
                    "Please ensure it has 'Dose' and 'Volume' columns."
                )
        else:
            raise ValueError(
                f"Unsupported file format: {self.format}\n"
                f"File: {self.file_path.name}\n"
                "Supported formats: .txt (Eclipse), .csv (Dose/Volume), .dcm (v1.1)"
            )
        
        # Store in instance
        self.patient_id = metadata.get('patient_id')
        self.structure_name = metadata.get('structure_name')
        self.dvh_type = metadata.get('dvh_type', 'unknown')
        self.is_tumor = metadata.get('is_tumor', False)
        self.total_volume = metadata.get('total_volume')
        
        return metadata, dvh_data
    
    def convert_to_cumulative(self, ddvh: pd.DataFrame) -> pd.DataFrame:
        """
        Convert differential DVH to cumulative DVH.
        
        ✓ FIXED: Properly handles dV/dD (normalized) vs dV (absolute) differential DVH
        
        NOTE: Phase 1B.4 - Delegates to rbgyanx.core.dvh.convert_to_cumulative
        
        Parameters
        ----------
        ddvh : pd.DataFrame
            Differential DVH with columns: Dose[Gy], Volume[cm3]
        
        Returns
        -------
        pd.DataFrame
            Cumulative DVH with columns: Dose[Gy], Volume[cm3]
        """
        return _convert_to_cumulative(ddvh)
    
    def convert_to_differential(self, cdvh: pd.DataFrame) -> pd.DataFrame:
        """
        Convert cumulative DVH to differential DVH.
        
        NOTE: Phase 1B.4 - Delegates to rbgyanx.core.dvh.convert_to_differential
        
        Parameters
        ----------
        cdvh : pd.DataFrame
            Cumulative DVH with columns: Dose[Gy], Volume[cm3]
        
        Returns
        -------
        pd.DataFrame
            Differential DVH with columns: Dose[Gy], Volume[cm3]
        """
        return _convert_to_differential(cdvh)


# ── Intelligent Preprocessing Function ──────────────────────────────────────────

def preprocess_dvh_intelligent(
    input_path: Path,
    output_dir: Path,
    file_list: Optional[list] = None,
) -> Dict:
    """
    Intelligent DVH preprocessing with format auto-detection.
    
    Handles:
    - Multiple file formats (Eclipse TXT, CSV, DICOM)
    - Patient ID extraction from diverse naming
    - OAR vs PTV detection
    - Dose unit conversion (cGy → Gy)
    - Both cDVH and dDVH generation
    
    Parameters
    ----------
    input_path : Path or str
        Path to input file or directory containing DVH files
    output_dir : Path or str
        Path to output directory
    
    Returns
    -------
    dict
        Summary dictionary with processing statistics
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    
    cdvh_dir = output_dir / 'cDVH_csv'
    ddvh_dir = output_dir / 'dDVH_csv'
    cdvh_dir.mkdir(parents=True, exist_ok=True)
    ddvh_dir.mkdir(parents=True, exist_ok=True)
    
    # Summary report
    summary = {
        'total_files': 0,
        'processed': 0,
        'failed': 0,
        'duplicates_skipped': 0,
        'excluded': 0,
        'patients': set(),
        'structures': Counter(),
        'formats': Counter(),
        'errors': [],
        'warnings': []  # Track validation warnings
    }
    
    # Track unique patient-structure combinations to detect duplicates
    processed_combinations = set()
    
    # CREATE THE patient_organs DICTIONARY FOR DEDUPLICATION
    patient_organs = {}  # {patient_id: {structure_file: (dvh_data, metadata, file_path)}}
    
    # Find all DVH files (flat or recursive via input_router)
    if file_list is not None:
        files = [Path(f) for f in file_list]
    elif input_path.is_file():
        files = [input_path]
    else:
        try:
            from rbgyanx.logic.input_router import discover_dvh_files

            files = [
                f
                for f in discover_dvh_files(input_path, recursive=True)
                if f.suffix.lower() in {".txt", ".csv"}
            ]
        except ImportError:
            files = list(input_path.glob("*.txt")) + list(input_path.glob("*.csv"))
    
    summary['total_files'] = len(files)
    
    print(f"\n{'='*70}")
    print(f"rbGyanX v1.0 - Intelligent DVH Preprocessing")
    print(f"{'='*70}")
    print(f"Input: {input_path}")
    print(f"Output: {output_dir}")
    print(f"Files found: {len(files)}")
    print(f"{'='*70}\n")
    
    for i, file_path in enumerate(files, 1):
        try:
            print(f"[{i}/{len(files)}] Processing: {file_path.name}")
            
            # Parse with universal parser
            parser = UniversalDVHParser(file_path)
            metadata, dvh_data = parser.parse()
            
            # Create unique key for duplicate detection
            patient_id = str(metadata.get('patient_id', 'Unknown')).replace(' ', '_').replace('/', '_')
            
            # Normalize structure name (for display/tracking)
            structure_display = str(metadata.get('structure_name', 'Unknown'))
            
            # Normalize structure name for file naming (Parotid variants -> "Parotid")
            structure_file = parser.normalize_structure_name(
                metadata.get('structure_name_original', structure_display), 
                for_file_naming=True
            )
            
            if structure_file is None:
                print(f"  [EXCLUDE] {file_path.name} - structure excluded")
                summary['excluded'] += 1
                continue
            
            # Initialize patient entry if needed
            if patient_id not in patient_organs:
                patient_organs[patient_id] = {}
            
            # Handle Parotid combining logic
            if 'Parotid' in structure_file:
                # If we already have a Parotid for this patient, keep the better one
                if 'Parotid' in patient_organs[patient_id]:
                    existing_data, existing_meta, existing_file = patient_organs[patient_id]['Parotid']
                    # Keep the one with more data points (better quality)
                    if len(dvh_data) > len(existing_data):
                        print(f"  [REPLACE] Replacing existing Parotid with better quality data")
                        patient_organs[patient_id]['Parotid'] = (dvh_data, metadata, file_path)
                    else:
                        print(f"  [SKIP] Keeping existing Parotid (better quality)")
                        summary['duplicates_skipped'] += 1
                else:
                    patient_organs[patient_id]['Parotid'] = (dvh_data, metadata, file_path)
            else:
                # For non-Parotid organs, check for duplicates
                if structure_file in patient_organs[patient_id]:
                    existing_data, existing_meta, existing_file = patient_organs[patient_id][structure_file]
                    # Keep the one with more data points
                    if len(dvh_data) > len(existing_data):
                        print(f"  [REPLACE] Replacing existing {structure_file} with better quality data")
                        patient_organs[patient_id][structure_file] = (dvh_data, metadata, file_path)
                    else:
                        print(f"  [SKIP] Keeping existing {structure_file} (better quality)")
                        summary['duplicates_skipped'] += 1
                else:
                    patient_organs[patient_id][structure_file] = (dvh_data, metadata, file_path)
            
            # Skip to next file - we'll process all at the end
            continue
        
        except ValueError as e:
            # Handle excluded structures (PRV, etc.)
            if "excluded" in str(e).lower():
                print(f"  [!] {str(e)} - Skipped")
                summary['excluded'] += 1
            else:
                print(f"  [X] Error: {str(e)}\n")
                summary['failed'] += 1
                summary['errors'].append({
                    'file': file_path.name,
                    'error': str(e)
                })
        except Exception as e:
            print(f"  [X] Error: {str(e)}\n")
            summary['failed'] += 1
            summary['errors'].append({
                'file': file_path.name,
                'error': str(e)
            })
    
    # Now process all deduplicated patient-organ combinations
    print(f"\n{'='*70}")
    print(f"Processing deduplicated patient-organ combinations...")
    print(f"{'='*70}\n")
    
    for patient_id, organs in patient_organs.items():
        for structure_file, (dvh_data, metadata, file_path) in organs.items():
            try:
                print(f"Processing: {patient_id} - {structure_file}")
                
                # Get display name for tracking
                structure_display = metadata.get('structure_name', structure_file)
                
                # Create unique key for final tracking
                unique_key = f"{patient_id}_{structure_file}"
                processed_combinations.add(unique_key)
                
                # Get parser format from metadata
                parser_format = metadata.get('format', 'Unknown')
                
                # Log detection
                print(f"  Format: {parser_format}")
                print(f"  Patient: {patient_id}")
                
                # Show normalization if occurred
                original_name = metadata.get('structure_name_original', structure_display)
                if original_name != structure_display:
                    print(f"  Structure: {original_name} -> {structure_display} (file: {structure_file})")
                else:
                    print(f"  Structure: {structure_display} (file: {structure_file})")
                
                print(f"  Type: {'TUMOR' if metadata.get('is_tumor') else 'OAR'}")
                print(f"  DVH Type: {metadata.get('dvh_type', 'unknown')}")
                
                # Standardize filename - use structure_file (normalized for file naming)
                output_filename = f"{patient_id}_{structure_file}.csv"
                
                # Create parser instance for conversions
                parser = UniversalDVHParser(file_path)
                
                # Get total volume from metadata (preferred source)
                total_volume_from_metadata = metadata.get('total_volume')
                
                # Save cDVH with proper volume normalization
                if metadata.get('dvh_type') == 'differential':
                    cdvh = parser.convert_to_cumulative(dvh_data)
                else:
                    cdvh = dvh_data.copy()
                
                # CRITICAL FIX: Normalize volumes using TPS metadata total_volume
                # Rule: Use absolute volume from TPS metadata (preferred) OR cumulative % × structure volume
                # Never: Integrate % DVH as absolute volume, assume voxel volume = 1 cm³, re-scale already-absolute volumes
                first_volume = cdvh['Volume[cm3]'].iloc[0] if len(cdvh) > 0 else 0
                
                if total_volume_from_metadata is not None and total_volume_from_metadata > 0:
                    # Use TPS metadata total_volume (preferred source)
                    # Check if volumes are percentages (cumulative starts ~100) vs absolute
                    if 95 <= first_volume <= 105:
                        # Likely percentage DVH - convert to absolute using metadata
                        print(f"  [NORMALIZE] Converting percentage DVH (starts at {first_volume:.1f}%) to absolute using total_volume={total_volume_from_metadata:.1f} cm³")
                        cdvh['Volume[cm3]'] = (cdvh['Volume[cm3]'] / 100.0) * total_volume_from_metadata
                    elif first_volume > 1000 and total_volume_from_metadata < first_volume / 10:
                        # Unrealistically large volume (e.g., 42028 cm³) - likely incorrectly scaled percentage
                        print(f"  [NORMALIZE] Correcting unrealistically large volume ({first_volume:.1f} cm³) to {total_volume_from_metadata:.1f} cm³ using TPS metadata")
                        scale_factor = total_volume_from_metadata / first_volume
                        cdvh['Volume[cm3]'] = cdvh['Volume[cm3]'] * scale_factor
                    elif abs(first_volume - total_volume_from_metadata) / max(first_volume, total_volume_from_metadata) > 0.1:
                        # Significant difference (>10%) - trust metadata
                        print(f"  [NORMALIZE] Adjusting volume from {first_volume:.1f} cm³ to {total_volume_from_metadata:.1f} cm³ using TPS metadata")
                        scale_factor = total_volume_from_metadata / first_volume
                        cdvh['Volume[cm3]'] = cdvh['Volume[cm3]'] * scale_factor
                    # Otherwise, volumes match metadata - keep as-is (already correct)
                elif first_volume > 0 and (95 <= first_volume <= 105):
                    # Percentage DVH but no metadata - cannot normalize properly, warn
                    print(f"  [!] Warning: DVH appears to be percentage (starts at {first_volume:.1f}%) but no total_volume in metadata")
                    print(f"  [!] Cannot convert to absolute volume - keeping as percentage (may cause issues)")
                
                # CRITICAL FIX: Validate DVH integrity before saving
                # 1. Check cumulative DVH starts at reasonable volume
                if len(cdvh) > 0:
                    first_vol = cdvh['Volume[cm3]'].iloc[0]
                    last_vol = cdvh['Volume[cm3]'].iloc[-1]
                    
                    # For PTV/tumor structures, check for unrealistic volumes
                    is_tumor = metadata.get('is_tumor', False)
                    if is_tumor:
                        # PTV volumes should typically be < 1000 cm³ (unrealistic if > 5000 cm³)
                        if first_vol > 5000:
                            print(f"  [!] WARNING: Unrealistic PTV volume ({first_vol:.1f} cm³) - may be incorrectly normalized")
                            print(f"  [!] Marking DVH as potentially invalid")
                            # Mark for exclusion but don't fail completely
                            summary['warnings'] = summary.get('warnings', [])
                            summary['warnings'].append({
                                'file': output_filename,
                                'issue': f'Unrealistic PTV volume: {first_vol:.1f} cm³'
                            })
                    
                    # 2. Check monotonic decrease (cumulative should decrease)
                    if len(cdvh) > 1:
                        volumes = cdvh['Volume[cm3]'].values
                        is_monotonic = np.all(np.diff(volumes) <= 1e-6)  # Allow small numerical errors
                        if not is_monotonic:
                            # Check if it's just noise or a real problem
                            non_monotonic_count = np.sum(np.diff(volumes) > 1e-6)
                            if non_monotonic_count > len(volumes) * 0.1:  # More than 10% non-monotonic
                                print(f"  [!] WARNING: DVH is not monotonic decreasing ({non_monotonic_count} violations)")
                                print(f"  [!] This may indicate data quality issues")
                                summary['warnings'] = summary.get('warnings', [])
                                summary['warnings'].append({
                                    'file': output_filename,
                                    'issue': 'DVH not monotonic decreasing'
                                })
                
                cdvh.to_csv(cdvh_dir / output_filename, index=False)
                
                # Save dDVH with proper volume normalization
                if metadata.get('dvh_type') == 'cumulative':
                    # Use normalized cdvh to ensure consistency
                    ddvh = parser.convert_to_differential(cdvh)
                else:
                    ddvh = dvh_data.copy()
                    # If we normalized cdvh above, normalize ddvh to match
                    if total_volume_from_metadata is not None and total_volume_from_metadata > 0:
                        total_dv_sum = ddvh['Volume[cm3]'].sum()
                        if total_dv_sum > 0 and abs(total_dv_sum - total_volume_from_metadata) / total_volume_from_metadata > 0.05:
                            # Normalize differential volumes to match total_volume
                            scale_factor = total_volume_from_metadata / total_dv_sum
                            ddvh['Volume[cm3]'] = ddvh['Volume[cm3]'] * scale_factor
                
                # 3. Validate differential DVH integrates back to total volume
                if len(ddvh) > 0 and total_volume_from_metadata is not None and total_volume_from_metadata > 0:
                    total_dv_sum = ddvh['Volume[cm3]'].sum()
                    integration_error = abs(total_dv_sum - total_volume_from_metadata) / total_volume_from_metadata
                    if integration_error > 0.1:  # More than 10% error
                        print(f"  [!] WARNING: Differential DVH integration error ({integration_error*100:.1f}%)")
                        print(f"  [!] Sum: {total_dv_sum:.1f} cm³, Expected: {total_volume_from_metadata:.1f} cm³")
                        summary['warnings'] = summary.get('warnings', [])
                        summary['warnings'].append({
                            'file': output_filename,
                            'issue': f'Differential DVH integration error: {integration_error*100:.1f}%'
                        })
                
                ddvh.to_csv(ddvh_dir / output_filename, index=False)
                
                # Update summary
                summary['processed'] += 1
                summary['patients'].add(patient_id)
                summary['structures'][structure_file] += 1
                summary['formats'][parser_format] += 1
                
                print(f"  [OK] Saved: {output_filename}\n")
                
            except Exception as e:
                print(f"  [X] Error processing {patient_id}_{structure_file}: {str(e)}\n")
                summary['failed'] += 1
                summary['errors'].append({
                    'file': f"{patient_id}_{structure_file}",
                    'error': str(e)
                })
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"PREPROCESSING SUMMARY")
    print(f"{'='*70}")
    print(f"Total files: {summary['total_files']}")
    print(f"Processed: {summary['processed']} [OK]")
    if summary.get('duplicates_skipped', 0) > 0:
        print(f"Duplicates skipped: {summary['duplicates_skipped']}")
    if summary.get('excluded', 0) > 0:
        print(f"Excluded (PRV): {summary['excluded']}")
    print(f"Failed: {summary['failed']} [X]")
    print(f"Unique patients: {len(summary['patients'])}")
    print(f"\nStandardized structures:")
    for struct, count in summary['structures'].most_common():
        print(f"  - {struct}: {count} patients")
    print(f"\nFormats processed:")
    for fmt, count in summary['formats'].items():
        print(f"  - {fmt}: {count} files")
    
    if summary['failed'] > 0:
        print(f"\n[!] ERRORS ENCOUNTERED:")
        for err in summary['errors']:
            print(f"  - {err['file']}: {err['error']}")
    
    if summary.get('warnings', []):
        print(f"\n[!] VALIDATION WARNINGS ({len(summary['warnings'])}):")
        for warn in summary['warnings']:
            print(f"  - {warn['file']}: {warn['issue']}")
    
    print(f"{'='*70}\n")
    
    # Save summary report
    summary_file = output_dir / 'preprocessing_summary.txt'
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(f"rbGyanX v1.0 - DVH Preprocessing Summary\n")
        f.write(f"{'='*70}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Input: {input_path}\n")
        f.write(f"Output: {output_dir}\n\n")
        f.write(f"Files processed: {summary['processed']}/{summary['total_files']}\n")
        f.write(f"Unique patients: {len(summary['patients'])}\n")
        f.write(f"\nPatient IDs:\n")
        for pid in sorted(summary['patients']):
            f.write(f"  - {pid}\n")
    
    # CREATE EXCEL SUMMARY FILE FOR STEP 2 (processed_dvh.xlsx)
    try:
        import pandas as pd
        
        summary_data = []
        
        # Read all processed cDVH files to build summary
        for csv_file in sorted(cdvh_dir.glob('*.csv')):
            # Parse filename: PatientID_StructureName.csv
            filename = csv_file.stem
            parts = filename.rsplit('_', 1)
            
            if len(parts) == 2:
                patient_id, structure = parts
            else:
                # Fallback: try to split on first underscore
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    patient_id, structure = parts
                else:
                    patient_id = filename
                    structure = 'Unknown'
            
            # Read DVH data
            try:
                dvh_df = pd.read_csv(csv_file)
                
                # Validate columns
                if 'Dose[Gy]' not in dvh_df.columns or 'Volume[cm3]' not in dvh_df.columns:
                    print(f"  [!] Warning: Invalid columns in {csv_file.name} - Skipping")
                    continue
                
                # Calculate comprehensive metrics
                if not dvh_df.empty and len(dvh_df) > 0:
                    # Extract dose and volume arrays
                    doses = dvh_df['Dose[Gy]'].values
                    volumes = dvh_df['Volume[cm3]'].values
                    
                    # Remove NaN values
                    valid_mask = ~(np.isnan(doses) | np.isnan(volumes))
                    doses = doses[valid_mask]
                    volumes = volumes[valid_mask]
                    
                    if len(doses) == 0:
                        continue
                    
                    # Basic metrics
                    initial_volume = volumes[0]
                    max_dose = doses.max()
                    min_dose = doses[doses > 0].min() if (doses > 0).any() else 0.0
                    
                    # Mean dose (trapezoidal integration)
                    if len(doses) > 1 and initial_volume > 0:
                        rel_volumes = (volumes / initial_volume) * 100.0
                        mean_dose = _trapz(rel_volumes * doses, doses) / _trapz(rel_volumes, doses)
                    else:
                        mean_dose = doses[0] if len(doses) > 0 else 0.0
                    
                    # Median dose (50% volume point)
                    if initial_volume > 0:
                        rel_volumes = (volumes / initial_volume) * 100.0
                        if rel_volumes.min() <= 50:
                            median_dose = np.interp(50, rel_volumes[::-1], doses[::-1])
                        else:
                            median_dose = np.nan
                    else:
                        median_dose = np.nan
                    
                    # Modal dose (peak of differential DVH)
                    if len(volumes) > 1:
                        diff_vol = -np.diff(volumes)
                        modal_dose = doses[:-1][np.argmax(diff_vol)] if len(diff_vol) > 0 else doses[0]
                    else:
                        modal_dose = doses[0]
                    
                    # Build summary row with all metrics
                    summary_data.append({
                        'PatientID': patient_id,
                        'PatientId': patient_id,  # Alternative column name for compatibility
                        'Patient_AnoID': patient_id,
                        'Organ': structure,
                        'Structure': structure,
                        'OrganType': 'serial' if 'Cord' in structure else 'parallel',
                        'Volume[cm3]': round(initial_volume, 2),
                        'MeanDose[Gy]': round(mean_dose, 2),
                        'MeanDose(Gy)': round(mean_dose, 2),
                        'MaxDose[Gy]': round(max_dose, 2),
                        'MaxDose(Gy)': round(max_dose, 2),
                        'MinDose[Gy]': round(min_dose, 2),
                        'MinDose(Gy)': round(min_dose, 2),
                        'MedianDose[Gy]': round(median_dose, 2) if not np.isnan(median_dose) else np.nan,
                        'MedianDose(Gy)': round(median_dose, 2) if not np.isnan(median_dose) else np.nan,
                        'ModalDose[Gy]': round(modal_dose, 2),
                        'ModalDose(Gy)': round(modal_dose, 2),
                        'DVHFile': csv_file.name,
                        'Format': 'Cumulative',
                        'ProcessedDate': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                else:
                    print(f"  [!] Warning: Empty DVH file {csv_file.name} - Skipping")
                
            except Exception as e:
                print(f"  [!] Warning: Could not read {csv_file.name}: {str(e)}")
                continue
        
        # Create DataFrame
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            
            # Save to Excel with multiple sheets
            excel_summary_file = output_dir / 'processed_dvh.xlsx'
            
            # Sort by patient and organ
            summary_df = summary_df.sort_values(['PatientID', 'Organ'])
            
            with pd.ExcelWriter(excel_summary_file, engine='openpyxl') as writer:
                # Main summary sheet
                summary_df.to_excel(writer, sheet_name='DVH_Summary', index=False)
                
                # Metadata sheet
                metadata_df = pd.DataFrame([{
                    'ProcessingDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'TotalFiles': summary['total_files'],
                    'ProcessedFiles': summary['processed'],
                    'FailedFiles': summary['failed'],
                    'DuplicatesSkipped': summary['duplicates_skipped'],
                    'ExcludedFiles': summary['excluded'],
                    'UniquePatients': len(summary['patients']),
                    'UniqueStructures': len(summary['structures']),
                    'rbGyanXVersion': '1.0.0'
                }])
                metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
                
                # Structure summary
                structure_summary = summary_df.groupby('Structure').agg({
                    'PatientID': 'count',
                    'Volume[cm3]': ['mean', 'std', 'min', 'max'],
                    'MeanDose[Gy]': ['mean', 'std', 'min', 'max']
                }).reset_index()
                structure_summary.columns = ['_'.join(col).strip('_') for col in structure_summary.columns]
                structure_summary.to_excel(writer, sheet_name='Structure_Summary', index=False)
            
            print(f"\n[OK] Creating Excel summary for Step 2...")
            print(f"[OK] Summary file created: {excel_summary_file}")
            print(f"[OK] Summary contains {len(summary_df)} DVH entries")
            print(f"[OK] Structures: {sorted(summary_df['Structure'].unique())}")
            
            # Add to summary dict
            summary['summary_file'] = str(excel_summary_file)
            summary['summary_entries'] = len(summary_df)
        else:
            print(f"\n[!] Warning: No data to write to summary file")
            
    except ImportError:
        print("\n[!] Warning: pandas or openpyxl not available - summary file not created")
        print("[!] Install with: pip install pandas openpyxl")
        
    except Exception as e:
        print(f"\n[!] Warning: Could not create summary file: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return summary

