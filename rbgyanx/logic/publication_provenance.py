"""
rbgyanx.logic.publication_provenance - Publication & Provenance Toolkit

This module provides journal-ready exports, deterministic replay, provenance bundles,
and reviewer auditability for rbGyanX.

Phase 12: No new scientific analysis, no new AI behavior, no UI redesign.
Publication and reproducibility tools only.

Author: rbGyanX Team
Version: 1.0.0
"""

import json
import hashlib
import shutil
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import numpy as np


@dataclass
class ReplayConfiguration:
    """
    Configuration for deterministic replay.
    
    Phase 12: Enables exact reproduction of analyses.
    """
    provenance_record_path: Path
    output_directory: Path
    random_seed: Optional[int] = None
    overwrite_existing: bool = False
    verify_hashes: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'provenance_record_path': str(self.provenance_record_path),
            'output_directory': str(self.output_directory),
            'random_seed': self.random_seed,
            'overwrite_existing': self.overwrite_existing,
            'verify_hashes': self.verify_hashes,
            'metadata': self.metadata
        }


@dataclass
class ProvenanceBundle:
    """
    Provenance bundle for publication.
    
    Phase 12: Contains all information needed for reproducibility and reviewer audit.
    """
    bundle_id: str
    creation_timestamp: str
    provenance_record: Dict[str, Any]
    input_files: Dict[str, str]  # name -> filepath
    output_files: Dict[str, str]  # name -> filepath
    configuration: Dict[str, Any]
    structured_logs: List[Dict[str, Any]]
    figure_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # figure_name -> metadata
    code_version: str = "1.0.0"
    system_info: Dict[str, Any] = field(default_factory=dict)
    reviewer_notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'bundle_id': self.bundle_id,
            'creation_timestamp': self.creation_timestamp,
            'provenance_record': self.provenance_record,
            'input_files': self.input_files,
            'output_files': self.output_files,
            'configuration': self.configuration,
            'structured_logs': self.structured_logs,
            'figure_metadata': self.figure_metadata,
            'code_version': self.code_version,
            'system_info': self.system_info,
            'reviewer_notes': self.reviewer_notes,
            'metadata': self.metadata
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


@dataclass
class JournalExport:
    """
    Journal-ready export package.
    
    Phase 12: Format suitable for journal submission and review.
    """
    export_id: str
    journal_name: Optional[str]
    manuscript_info: Dict[str, Any]
    provenance_bundle: ProvenanceBundle
    figure_files: List[str]
    supplementary_materials: List[str]
    reproducibility_script: Optional[str] = None
    readme_content: Optional[str] = None
    export_timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'export_id': self.export_id,
            'journal_name': self.journal_name,
            'manuscript_info': self.manuscript_info,
            'provenance_bundle': self.provenance_bundle.to_dict(),
            'figure_files': self.figure_files,
            'supplementary_materials': self.supplementary_materials,
            'reproducibility_script': self.reproducibility_script,
            'readme_content': self.readme_content,
            'export_timestamp': self.export_timestamp or datetime.now().isoformat(),
            'metadata': self.metadata
        }


class PublicationProvenanceToolkit:
    """
    Publication & Provenance Toolkit for rbGyanX.
    
    Phase 12: Provides journal-ready exports, deterministic replay, provenance bundles,
    and reviewer auditability. No new scientific analysis, no new AI behavior, no UI redesign.
    
    Design Principles:
    - Journal-ready export formats
    - Deterministic replay from provenance records
    - Complete provenance bundles for review
    - Reviewer auditability (transparent, traceable)
    - Integration with existing provenance and structured logging
    """
    
    def __init__(self):
        """Initialize publication & provenance toolkit."""
        pass
    
    def create_provenance_bundle(
        self,
        provenance_record: Dict[str, Any],
        input_files: Dict[str, Union[str, Path]],
        output_files: Dict[str, Union[str, Path]],
        structured_logs: List[Dict[str, Any]],
        configuration: Optional[Dict[str, Any]] = None,
        figure_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        code_version: str = "1.0.0",
        system_info: Optional[Dict[str, Any]] = None,
        reviewer_notes: Optional[str] = None
    ) -> ProvenanceBundle:
        """
        Create provenance bundle for publication.
        
        Parameters
        ----------
        provenance_record : Dict[str, Any]
            Provenance record dictionary
        input_files : Dict[str, Union[str, Path]]
            Input files dictionary (name -> path)
        output_files : Dict[str, Union[str, Path]]
            Output files dictionary (name -> path)
        structured_logs : List[Dict[str, Any]]
            Structured log entries
        configuration : Optional[Dict[str, Any]]
            Configuration dictionary
        figure_metadata : Optional[Dict[str, Dict[str, Any]]]
            Figure metadata dictionary
        code_version : str
            Code version string
        system_info : Optional[Dict[str, Any]]
            System information dictionary
        reviewer_notes : Optional[str]
            Reviewer notes
        
        Returns
        -------
        ProvenanceBundle
            Provenance bundle for publication
        """
        # Convert Path objects to strings
        input_files_str = {k: str(Path(v).resolve()) for k, v in input_files.items()}
        output_files_str = {k: str(Path(v).resolve()) for k, v in output_files.items()}
        
        # Generate bundle ID
        bundle_id = f"bundle-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hashlib.sha256(str(provenance_record.get('session_id', '')).encode()).hexdigest()[:8]}"
        
        # Get system info if not provided
        if system_info is None:
            import platform
            import sys
            system_info = {
                'platform': platform.platform(),
                'python_version': sys.version,
                'numpy_version': np.__version__ if 'numpy' in sys.modules else 'unknown'
            }
        
        return ProvenanceBundle(
            bundle_id=bundle_id,
            creation_timestamp=datetime.now().isoformat(),
            provenance_record=provenance_record,
            input_files=input_files_str,
            output_files=output_files_str,
            configuration=configuration or {},
            structured_logs=structured_logs,
            figure_metadata=figure_metadata or {},
            code_version=code_version,
            system_info=system_info,
            reviewer_notes=reviewer_notes
        )
    
    def export_provenance_bundle(
        self,
        bundle: ProvenanceBundle,
        output_directory: Union[str, Path],
        include_files: bool = True,
        create_zip: bool = True
    ) -> Path:
        """
        Export provenance bundle to directory or ZIP archive.
        
        Parameters
        ----------
        bundle : ProvenanceBundle
            Provenance bundle to export
        output_directory : Union[str, Path]
            Output directory path
        include_files : bool
            Include referenced files in export
        create_zip : bool
            Create ZIP archive of bundle
        
        Returns
        -------
        Path
            Path to exported bundle (directory or ZIP file)
        """
        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save bundle metadata
        bundle_file = output_dir / f"{bundle.bundle_id}_bundle.json"
        with open(bundle_file, 'w') as f:
            f.write(bundle.to_json())
        
        # Copy referenced files if requested
        if include_files:
            files_dir = output_dir / f"{bundle.bundle_id}_files"
            files_dir.mkdir(exist_ok=True)
            
            # Copy input files
            input_dir = files_dir / "inputs"
            input_dir.mkdir(exist_ok=True)
            for name, filepath in bundle.input_files.items():
                src = Path(filepath)
                if src.exists():
                    dst = input_dir / f"{name}_{src.name}"
                    shutil.copy2(src, dst)
            
            # Copy output files
            output_files_dir = files_dir / "outputs"
            output_files_dir.mkdir(exist_ok=True)
            for name, filepath in bundle.output_files.items():
                src = Path(filepath)
                if src.exists():
                    dst = output_files_dir / f"{name}_{src.name}"
                    shutil.copy2(src, dst)
        
        # Create ZIP archive if requested
        if create_zip:
            zip_path = output_dir / f"{bundle.bundle_id}_bundle.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add bundle JSON
                zipf.write(bundle_file, bundle_file.name)
                
                # Add files if included
                if include_files and files_dir.exists():
                    for file_path in files_dir.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(output_dir)
                            zipf.write(file_path, arcname)
            
            return zip_path
        
        return output_dir
    
    def create_journal_export(
        self,
        bundle: ProvenanceBundle,
        journal_name: Optional[str] = None,
        manuscript_info: Optional[Dict[str, Any]] = None,
        figure_files: Optional[List[Union[str, Path]]] = None,
        supplementary_materials: Optional[List[Union[str, Path]]] = None,
        reproducibility_script: Optional[str] = None,
        readme_content: Optional[str] = None
    ) -> JournalExport:
        """
        Create journal-ready export package.
        
        Parameters
        ----------
        bundle : ProvenanceBundle
            Provenance bundle
        journal_name : Optional[str]
            Journal name
        manuscript_info : Optional[Dict[str, Any]]
            Manuscript information (title, authors, etc.)
        figure_files : Optional[List[Union[str, Path]]]
            List of figure file paths
        supplementary_materials : Optional[List[Union[str, Path]]]
            List of supplementary material file paths
        reproducibility_script : Optional[str]
            Reproducibility script content
        readme_content : Optional[str]
            README content
        
        Returns
        -------
        JournalExport
            Journal-ready export package
        """
        export_id = f"export-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{bundle.bundle_id[:8]}"
        
        figure_files_str = [str(Path(f).resolve()) for f in (figure_files or [])]
        supplementary_str = [str(Path(f).resolve()) for f in (supplementary_materials or [])]
        
        return JournalExport(
            export_id=export_id,
            journal_name=journal_name,
            manuscript_info=manuscript_info or {},
            provenance_bundle=bundle,
            figure_files=figure_files_str,
            supplementary_materials=supplementary_str,
            reproducibility_script=reproducibility_script,
            readme_content=readme_content
        )
    
    def export_journal_package(
        self,
        journal_export: JournalExport,
        output_directory: Union[str, Path]
    ) -> Path:
        """
        Export journal-ready package to directory.
        
        Parameters
        ----------
        journal_export : JournalExport
            Journal export to export
        output_directory : Union[str, Path]
            Output directory path
        
        Returns
        -------
        Path
            Path to exported package directory
        """
        output_dir = Path(output_directory)
        export_dir = output_dir / f"journal_export_{journal_export.export_id}"
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # Save export metadata
        export_file = export_dir / "export_metadata.json"
        with open(export_file, 'w') as f:
            json.dump(journal_export.to_dict(), f, indent=2, default=str)
        
        # Copy figures
        if journal_export.figure_files:
            figures_dir = export_dir / "figures"
            figures_dir.mkdir(exist_ok=True)
            for fig_path in journal_export.figure_files:
                src = Path(fig_path)
                if src.exists():
                    dst = figures_dir / src.name
                    shutil.copy2(src, dst)
        
        # Copy supplementary materials
        if journal_export.supplementary_materials:
            supp_dir = export_dir / "supplementary_materials"
            supp_dir.mkdir(exist_ok=True)
            for supp_path in journal_export.supplementary_materials:
                src = Path(supp_path)
                if src.exists():
                    dst = supp_dir / src.name
                    shutil.copy2(src, dst)
        
        # Save reproducibility script
        if journal_export.reproducibility_script:
            script_file = export_dir / "reproduce_analysis.py"
            with open(script_file, 'w') as f:
                f.write(journal_export.reproducibility_script)
        
        # Save README
        if journal_export.readme_content:
            readme_file = export_dir / "README.md"
            with open(readme_file, 'w') as f:
                f.write(journal_export.readme_content)
        
        # Export provenance bundle
        self.export_provenance_bundle(
            journal_export.provenance_bundle,
            export_dir / "provenance",
            include_files=True,
            create_zip=True
        )
        
        return export_dir
    
    def load_provenance_bundle(self, bundle_file: Union[str, Path]) -> ProvenanceBundle:
        """
        Load provenance bundle from JSON file.
        
        Parameters
        ----------
        bundle_file : Union[str, Path]
            Bundle JSON file path
        
        Returns
        -------
        ProvenanceBundle
            Loaded provenance bundle
        """
        bundle_path = Path(bundle_file)
        with open(bundle_path, 'r') as f:
            data = json.load(f)
        
        return ProvenanceBundle(**data)
    
    def create_replay_configuration(
        self,
        provenance_record_path: Union[str, Path],
        output_directory: Union[str, Path],
        random_seed: Optional[int] = None,
        overwrite_existing: bool = False,
        verify_hashes: bool = True
    ) -> ReplayConfiguration:
        """
        Create replay configuration for deterministic replay.
        
        Parameters
        ----------
        provenance_record_path : Union[str, Path]
            Path to provenance record JSON file
        output_directory : Union[str, Path]
            Output directory for replay
        random_seed : Optional[int]
            Random seed for deterministic execution
        overwrite_existing : bool
            Overwrite existing outputs
        verify_hashes : bool
            Verify input hashes during replay
        
        Returns
        -------
        ReplayConfiguration
            Replay configuration
        """
        return ReplayConfiguration(
            provenance_record_path=Path(provenance_record_path),
            output_directory=Path(output_directory),
            random_seed=random_seed,
            overwrite_existing=overwrite_existing,
            verify_hashes=verify_hashes
        )
    
    def generate_reproducibility_script(
        self,
        bundle: ProvenanceBundle,
        script_template: Optional[str] = None
    ) -> str:
        """
        Generate Python script for reproducing analysis.
        
        Parameters
        ----------
        bundle : ProvenanceBundle
            Provenance bundle
        script_template : Optional[str]
            Custom script template
        
        Returns
        -------
        str
            Reproducibility script content
        """
        if script_template:
            return script_template
        
        # Generate default script
        script = f"""# rbGyanX Reproducibility Script
# Generated from provenance bundle: {bundle.bundle_id}
# Creation timestamp: {bundle.creation_timestamp}

import sys
from pathlib import Path
from rbgyanx.logic.publication_provenance import PublicationProvenanceToolkit

# Load provenance bundle
bundle_file = Path(__file__).parent / "provenance" / "{bundle.bundle_id}_bundle.json"
toolkit = PublicationProvenanceToolkit()
bundle = toolkit.load_provenance_bundle(bundle_file)

# Replay configuration
replay_config = toolkit.create_replay_configuration(
    provenance_record_path=bundle_file,
    output_directory=Path("./replay_output"),
    random_seed=None,  # Use seed from provenance record if available
    overwrite_existing=True,
    verify_hashes=True
)

# TODO: Implement replay execution using provenance record
# This would reconstruct the pipeline input and execute the analysis
# using the exact same configuration and parameters

print(f"Reproducibility script loaded for bundle: {{bundle.bundle_id}}")
print(f"Code version: {{bundle.code_version}}")
print(f"System info: {{bundle.system_info}}")
"""
        return script
    
    def create_reviewer_readme(
        self,
        bundle: ProvenanceBundle,
        additional_notes: Optional[str] = None
    ) -> str:
        """
        Create README for reviewers.
        
        Parameters
        ----------
        bundle : ProvenanceBundle
            Provenance bundle
        additional_notes : Optional[str]
            Additional reviewer notes
        
        Returns
        -------
        str
            Reviewer README content
        """
        readme = f"""# rbGyanX Provenance Bundle - Reviewer Information

**Bundle ID**: {bundle.bundle_id}  
**Creation Timestamp**: {bundle.creation_timestamp}  
**Code Version**: {bundle.code_version}

## Contents

This bundle contains all information necessary to reproduce and audit the analysis:

1. **Provenance Record**: Complete execution provenance including inputs, configuration, and outputs
2. **Input Files**: All input data files used in the analysis
3. **Output Files**: All output files generated by the analysis
4. **Structured Logs**: Timestamped execution logs for audit trail
5. **Configuration**: All parameter values and settings
6. **Figure Metadata**: Metadata for all figures included in the manuscript

## Reproducibility

To reproduce this analysis:

1. Ensure rbGyanX code version {bundle.code_version} is installed
2. Use the provided `reproduce_analysis.py` script
3. Verify input file hashes match those in the provenance record
4. Execute the analysis with the exact configuration from the bundle

## System Information

{json.dumps(bundle.system_info, indent=2)}

## Reviewer Notes

{bundle.reviewer_notes or 'No additional reviewer notes provided.'}

{additional_notes or ''}

## Contact

For questions about this analysis or the provenance bundle, please contact the corresponding author.
"""
        return readme


__all__ = [
    'ReplayConfiguration',
    'ProvenanceBundle',
    'JournalExport',
    'PublicationProvenanceToolkit'
]
