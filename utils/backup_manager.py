"""
OBJECTIVE E: Auto-Save & Rollback Safety

Manages automatic backups and rollback functionality for rbGyanX.

Author: rbGyanX Team
Version: 1.0.0
"""

import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd


class BackupManager:
    """Manages automatic backups and rollback operations."""
    
    def __init__(self, backup_dir: Path, repo_root: Path):
        """
        Initialize backup manager.
        
        Parameters
        ----------
        backup_dir : Path
            Directory where backups are stored
        repo_root : Path
            Root directory of rbGyanX repository
        """
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.repo_root = Path(repo_root)
        self.metadata_file = self.backup_dir / 'backup_metadata.json'
        
        # Load metadata
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load backup metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'backups': []}
    
    def _save_metadata(self):
        """Save backup metadata."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save backup metadata: {e}")
    
    def create_backup(self, reason: str = "manual") -> Optional[Path]:
        """
        Create a timestamped backup of critical files.
        
        Parameters
        ----------
        reason : str
            Reason for backup (e.g., "auto_correction", "self_test", "manual")
        
        Returns
        -------
        Path or None
            Path to backup directory, or None if backup failed
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Files/directories to backup
        critical_paths = [
            'code1_dvh_preprocess.py',
            'code2_dvh_plot_and_summary.py',
            'code3_ntcp_analysis_ml.py',
            'code4_ntcp_output_QA_reporter.py',
            'code5_ntcp_factors_analysis.py',
            'code6_tcp_analysis.py',
            'code7_tcp_ntcp_integration.py',
            'rbgyanx_gui.py',
            'core',
            'utils',
            'models',
            'config'
        ]
        
        backed_up = []
        failed = []
        
        for item in critical_paths:
            source = self.repo_root / item
            if source.exists():
                try:
                    dest = backup_path / item
                    if source.is_file():
                        shutil.copy2(source, dest)
                    elif source.is_dir():
                        shutil.copytree(source, dest, dirs_exist_ok=True)
                    backed_up.append(item)
                except Exception as e:
                    failed.append(f"{item}: {str(e)}")
        
        # Save backup metadata
        backup_info = {
            'timestamp': timestamp,
            'backup_path': str(backup_path),
            'reason': reason,
            'backed_up': backed_up,
            'failed': failed,
            'created': datetime.now().isoformat()
        }
        
        self.metadata['backups'].append(backup_info)
        # Keep only last 10 backups
        if len(self.metadata['backups']) > 10:
            # Remove oldest backup
            oldest = self.metadata['backups'].pop(0)
            try:
                old_backup_path = Path(oldest['backup_path'])
                if old_backup_path.exists():
                    shutil.rmtree(old_backup_path)
            except Exception:
                pass
        
        self._save_metadata()
        
        if failed:
            print(f"Warning: Some files failed to backup: {failed}")
        
        return backup_path if backed_up else None
    
    def list_backups(self) -> List[Dict]:
        """
        List all available backups.
        
        Returns
        -------
        List[Dict]
            List of backup information dictionaries
        """
        backups = []
        for backup_info in self.metadata.get('backups', []):
            backup_path = Path(backup_info['backup_path'])
            if backup_path.exists():
                backups.append(backup_info)
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
    
    def restore_backup(self, backup_path: Path, dry_run: bool = False) -> Dict:
        """
        Restore files from a backup.
        
        Parameters
        ----------
        backup_path : Path
            Path to backup directory
        dry_run : bool
            If True, only show what would be restored without actually restoring
        
        Returns
        -------
        Dict
            Dictionary with restore results
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            return {'success': False, 'error': 'Backup path does not exist'}
        
        restored = []
        failed = []
        
        # Restore each backed up item
        for item in backup_path.iterdir():
            if item.name == 'backup_metadata.json':
                continue
            
            source = item
            dest = self.repo_root / item.name
            
            try:
                if not dry_run:
                    if dest.exists():
                        if dest.is_file():
                            dest.unlink()
                        elif dest.is_dir():
                            shutil.rmtree(dest)
                    
                    if source.is_file():
                        shutil.copy2(source, dest)
                    elif source.is_dir():
                        shutil.copytree(source, dest, dirs_exist_ok=True)
                
                restored.append(item.name)
            except Exception as e:
                failed.append(f"{item.name}: {str(e)}")
        
        return {
            'success': len(failed) == 0,
            'restored': restored,
            'failed': failed,
            'dry_run': dry_run
        }


def create_backup_before_operation(repo_root: Path, reason: str) -> Optional[Path]:
    """
    Convenience function to create backup before operations.
    
    Parameters
    ----------
    repo_root : Path
        Repository root directory
    reason : str
        Reason for backup
    
    Returns
    -------
    Path or None
        Backup path if successful
    """
    backup_dir = repo_root / 'backups'
    manager = BackupManager(backup_dir, repo_root)
    return manager.create_backup(reason)

