"""
rbgyanx.logic.benchmark_integration - Data & Benchmark Integration

This module provides read-only DICOM data import and literature benchmark
integration (QUANTEC, RTOG, ESTRO, ICRU) as contextual reference only.

Phase 8: ADVANCED mode only. Contextual reference only.
No enforcement, no pass/fail logic, no clinical workflow integration.

Author: rbGyanX Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
from enum import Enum
import warnings


class BenchmarkSource(Enum):
    """Literature benchmark sources."""
    QUANTEC = "QUANTEC"  # Quantitative Analysis of Normal Tissue Effects in the Clinic
    RTOG = "RTOG"  # Radiation Therapy Oncology Group
    ESTRO = "ESTRO"  # European Society for Radiotherapy and Oncology
    ICRU = "ICRU"  # International Commission on Radiation Units and Measurements


@dataclass
class BenchmarkReference:
    """
    Literature benchmark reference (contextual only, no enforcement).
    
    Phase 8: Contextual reference only. No enforcement, no pass/fail logic.
    """
    source: BenchmarkSource
    organ_name: str
    metric_name: str
    reference_value: Optional[float] = None
    reference_range: Optional[Tuple[float, float]] = None
    citation: Optional[str] = None
    context: Optional[str] = None
    note: str = "Contextual reference only - not a constraint or recommendation"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'source': self.source.value,
            'organ_name': self.organ_name,
            'metric_name': self.metric_name,
            'reference_value': self.reference_value,
            'reference_range': list(self.reference_range) if self.reference_range else None,
            'citation': self.citation,
            'context': self.context,
            'note': self.note
        }


@dataclass
class BenchmarkComparison:
    """
    Comparison between calculated values and literature benchmarks (contextual only).
    
    Phase 8: Contextual reference only. No enforcement, no pass/fail logic.
    """
    metric_name: str
    calculated_value: float
    benchmark_references: List[BenchmarkReference] = field(default_factory=list)
    contextual_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'metric_name': self.metric_name,
            'calculated_value': self.calculated_value,
            'benchmark_references': [ref.to_dict() for ref in self.benchmark_references],
            'contextual_notes': self.contextual_notes
        }


@dataclass
class BenchmarkIntegrationResult:
    """
    Result of benchmark integration (contextual reference only).
    
    Phase 8: Contextual reference only. No enforcement, no pass/fail logic.
    """
    comparisons: List[BenchmarkComparison] = field(default_factory=list)
    dicom_metadata: Optional[Dict[str, Any]] = None
    benchmark_sources_used: List[BenchmarkSource] = field(default_factory=list)
    contextual_summary: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'comparisons': [comp.to_dict() for comp in self.comparisons],
            'dicom_metadata': self.dicom_metadata,
            'benchmark_sources_used': [source.value for source in self.benchmark_sources_used],
            'contextual_summary': self.contextual_summary
        }


class BenchmarkIntegration:
    """
    Literature benchmark integration for contextual reference.
    
    Phase 8: ADVANCED mode only. Contextual reference only.
    No enforcement, no pass/fail logic, no clinical workflow integration.
    
    Design Principles:
    - Read-only contextual reference
    - No enforcement or constraints
    - No pass/fail logic
    - No clinical workflow integration
    - Informative only
    """
    
    # Literature benchmark data (contextual reference only)
    # These are simplified examples - full implementation would include comprehensive data
    BENCHMARK_DATA: Dict[str, List[BenchmarkReference]] = {
        # QUANTEC references (simplified examples)
        'parotid': [
            BenchmarkReference(
                source=BenchmarkSource.QUANTEC,
                organ_name='Parotid',
                metric_name='Mean Dose',
                reference_value=26.0,  # Gy
                citation='QUANTEC (2010)',
                context='Mean dose threshold for xerostomia risk'
            ),
        ],
        'spinal_cord': [
            BenchmarkReference(
                source=BenchmarkSource.QUANTEC,
                organ_name='Spinal Cord',
                metric_name='Dmax',
                reference_value=50.0,  # Gy
                citation='QUANTEC (2010)',
                context='Maximum dose limit for myelopathy risk'
            ),
        ],
        # RTOG references (simplified examples)
        'lung': [
            BenchmarkReference(
                source=BenchmarkSource.RTOG,
                organ_name='Lung',
                metric_name='V20',
                reference_range=(20.0, 35.0),  # %
                citation='RTOG 0617',
                context='Volume receiving 20 Gy as predictor of pneumonitis'
            ),
        ],
        # ESTRO references (simplified examples)
        'rectum': [
            BenchmarkReference(
                source=BenchmarkSource.ESTRO,
                organ_name='Rectum',
                metric_name='V75',
                reference_value=15.0,  # %
                citation='ESTRO ACROP (2020)',
                context='Volume receiving 75 Gy for prostate treatments'
            ),
        ],
        # ICRU references (simplified examples)
        'ptv': [
            BenchmarkReference(
                source=BenchmarkSource.ICRU,
                organ_name='PTV',
                metric_name='D95',
                reference_value=95.0,  # % of prescribed dose
                citation='ICRU Report 83',
                context='Dose coverage metric'
            ),
        ],
    }
    
    def __init__(self):
        """Initialize benchmark integration."""
        pass
    
    def get_benchmark_references(
        self,
        organ_name: str,
        metric_name: Optional[str] = None
    ) -> List[BenchmarkReference]:
        """
        Get literature benchmark references for an organ and optional metric.
        
        Parameters
        ----------
        organ_name : str
            Organ name (normalized)
        metric_name : Optional[str]
            Specific metric name (optional)
            
        Returns
        -------
        List[BenchmarkReference]
            Benchmark references (contextual only, no enforcement)
        """
        # Normalize organ name
        normalized_organ = organ_name.lower().replace(' ', '_')
        
        # Get references for this organ
        references = self.BENCHMARK_DATA.get(normalized_organ, [])
        
        # Filter by metric if specified
        if metric_name:
            references = [
                ref for ref in references
                if ref.metric_name.lower() == metric_name.lower()
            ]
        
        return references
    
    def compare_with_benchmarks(
        self,
        metric_name: str,
        calculated_value: float,
        organ_name: str
    ) -> BenchmarkComparison:
        """
        Compare calculated value with literature benchmarks (contextual only).
        
        Parameters
        ----------
        metric_name : str
            Metric name
        calculated_value : float
            Calculated value
        organ_name : str
            Organ name
            
        Returns
        -------
        BenchmarkComparison
            Comparison result (contextual only, no enforcement)
        """
        # Get benchmark references
        benchmark_references = self.get_benchmark_references(organ_name, metric_name)
        
        # Build contextual notes (informative only, no enforcement)
        contextual_notes = []
        contextual_notes.append(
            f"Comparison with literature benchmarks for {organ_name} ({metric_name}) - "
            f"contextual reference only, not a constraint or recommendation"
        )
        
        for ref in benchmark_references:
            note_parts = [f"{ref.source.value}: {ref.citation}"]
            if ref.reference_value:
                diff = calculated_value - ref.reference_value
                note_parts.append(f"Reference value: {ref.reference_value}, Difference: {diff:.2f}")
            elif ref.reference_range:
                note_parts.append(f"Reference range: {ref.reference_range}")
                if ref.reference_range[0] <= calculated_value <= ref.reference_range[1]:
                    note_parts.append("(within reference range - contextual only)")
            
            if ref.context:
                note_parts.append(f"Context: {ref.context}")
            
            contextual_notes.append(" | ".join(note_parts))
        
        return BenchmarkComparison(
            metric_name=metric_name,
            calculated_value=calculated_value,
            benchmark_references=benchmark_references,
            contextual_notes=contextual_notes
        )


class DICOMImporter:
    """
    Read-only DICOM data importer.
    
    Phase 8: Read-only import. No modification, no enforcement.
    """
    
    def __init__(self):
        """Initialize DICOM importer."""
        pass
    
    def import_dicom_metadata(
        self,
        dicom_file_path: Path
    ) -> Dict[str, Any]:
        """
        Import DICOM file metadata (read-only).
        
        Parameters
        ----------
        dicom_file_path : Path
            Path to DICOM file
            
        Returns
        -------
        Dict[str, Any]
            DICOM metadata (read-only)
            
        Raises
        ------
        ImportError
            If pydicom is not available
        FileNotFoundError
            If DICOM file does not exist
        """
        try:
            import pydicom
        except ImportError:
            raise ImportError(
                "DICOM import requires pydicom: pip install pydicom"
            )
        
        if not dicom_file_path.exists():
            raise FileNotFoundError(f"DICOM file not found: {dicom_file_path}")
        
        # Read DICOM file (read-only)
        try:
            ds = pydicom.dcmread(str(dicom_file_path), stop_before_pixels=True)
        except Exception as e:
            raise ValueError(f"Failed to read DICOM file: {str(e)}")
        
        # Extract relevant metadata (read-only, no modification)
        metadata = {
            'file_path': str(dicom_file_path),
            'sop_class_uid': str(ds.SOPClassUID) if hasattr(ds, 'SOPClassUID') else None,
            'modality': str(ds.Modality) if hasattr(ds, 'Modality') else None,
            'study_date': str(ds.StudyDate) if hasattr(ds, 'StudyDate') else None,
            'series_description': str(ds.SeriesDescription) if hasattr(ds, 'SeriesDescription') else None,
            'patient_id': str(ds.PatientID) if hasattr(ds, 'PatientID') else None,
            'patient_name': str(ds.PatientName) if hasattr(ds, 'PatientName') else None,
            'institution_name': str(ds.InstitutionName) if hasattr(ds, 'InstitutionName') else None,
            'import_timestamp': datetime.now().isoformat(),
            'note': 'Read-only import - no modification, no enforcement'
        }
        
        return metadata
    
    def validate_dicom_file(self, dicom_file_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate DICOM file (read-only validation).
        
        Parameters
        ----------
        dicom_file_path : Path
            Path to DICOM file
            
        Returns
        -------
        Tuple[bool, List[str]]
            (is_valid, validation_notes)
            Note: Validation is informational only, not enforcement
        """
        notes = []
        
        if not dicom_file_path.exists():
            return False, [f"File not found: {dicom_file_path}"]
        
        try:
            import pydicom
            ds = pydicom.dcmread(str(dicom_file_path), stop_before_pixels=True)
            notes.append("DICOM file readable (validation only, not enforcement)")
            return True, notes
        except ImportError:
            return False, ["pydicom not available"]
        except Exception as e:
            return False, [f"DICOM read error: {str(e)}"]


__all__ = [
    'BenchmarkSource',
    'BenchmarkReference',
    'BenchmarkComparison',
    'BenchmarkIntegrationResult',
    'BenchmarkIntegration',
    'DICOMImporter'
]

