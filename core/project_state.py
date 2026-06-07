"""
ProjectStateManager - Safe, non-PHI project persistence
=======================================================

Tracks project configuration and state without storing patient data or DVH.
Supports project save/load, auto-save, and state restoration.

Author: rbGyanX Team
Version: 1.1.0
"""

import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ProjectStateManager:
    """
    Manages project state persistence (configuration only, NO PHI).
    
    Tracks:
    - project_type (retrospective / prospective / plan_comparison)
    - enabled features
    - analysis stage
    - configuration snapshot (NO DVH, NO patient data)
    
    Supports:
    - new project
    - open project
    - save / save as
    - auto-save every 5 minutes (config only)
    """
    
    def __init__(self, project_path: Optional[Path] = None):
        """
        Initialize ProjectStateManager.
        
        Parameters
        ----------
        project_path : Path, optional
            Path to project file (.rbgyanx.json). If None, no project loaded.
        """
        self.project_path = project_path
        self.state = {
            'version': '1.1.0',
            'created': datetime.now().isoformat(),
            'last_modified': datetime.now().isoformat(),
            'project_type': 'retrospective',  # retrospective / prospective / plan_comparison
            'enabled_features': {
                'ml_models': False,
                'shap_explainability': False,
                'glm_analysis': False,
                'qa_checks': True,
                'overfitting_inspector': True
            },
            'analysis_stage': 'not_started',  # not_started / step1 / step2 / step3 / step4 / step5 / step6 / completed
            'configuration': {
                'analysis_type': 'NTCP',  # NTCP or TCP
                'output_dir': '',
                'clinical_file': '',
                'raw_input': '',
                'input_format': 'directory',  # file or directory
                'dvh_type': 'auto',  # auto / cumulative / differential
                'tumor_organ_type': 'HNSCC',
                'model_selections': {
                    'ntcp': {
                        'LKB_LogLogistic': True,
                        'LKB_Probit': True,
                        'RS_Poisson': True
                    },
                    'tcp': {
                        'Poisson_TCP': True,
                        'LKB_TCP': True,
                        'Logistic_TCP': True,
                        'EUD_TCP': True
                    }
                }
            },
            'metadata': {
                'description': '',
                'notes': '',
                'tags': []
            }
        }
        
        self.auto_save_enabled = True
        self.auto_save_interval = 300  # 5 minutes in seconds
        self._auto_save_timer = None
        self._lock = threading.Lock()
        
        # Load existing project if path provided
        if project_path and project_path.exists():
            self.load_project(project_path)
    
    def new_project(self, project_path: Path, project_type: str = 'retrospective'):
        """
        Create a new project.
        
        Parameters
        ----------
        project_path : Path
            Path where project will be saved (.rbgyanx.json)
        project_type : str
            Type of project: 'retrospective', 'prospective', or 'plan_comparison'
        """
        with self._lock:
            self.project_path = project_path
            self.state['created'] = datetime.now().isoformat()
            self.state['last_modified'] = datetime.now().isoformat()
            self.state['project_type'] = project_type
            self.state['analysis_stage'] = 'not_started'
            
            # Reset configuration
            self.state['configuration'] = {
                'analysis_type': 'NTCP',
                'output_dir': '',
                'clinical_file': '',
                'raw_input': '',
                'input_format': 'directory',
                'dvh_type': 'auto',
                'tumor_organ_type': 'HNSCC',
                'model_selections': {
                    'ntcp': {
                        'LKB_LogLogistic': True,
                        'LKB_Probit': True,
                        'RS_Poisson': True
                    },
                    'tcp': {
                        'Poisson_TCP': True,
                        'LKB_TCP': True,
                        'Logistic_TCP': True,
                        'EUD_TCP': True
                    }
                }
            }
            
            self.save_project()
            logger.info(f"New project created: {project_path}")
    
    def load_project(self, project_path: Path) -> bool:
        """
        Load an existing project.
        
        Parameters
        ----------
        project_path : Path
            Path to project file (.rbgyanx.json)
            
        Returns
        -------
        bool
            True if loaded successfully, False otherwise
        """
        try:
            with self._lock:
                if not project_path.exists():
                    logger.error(f"Project file not found: {project_path}")
                    return False
                
                with open(project_path, 'r', encoding='utf-8') as f:
                    loaded_state = json.load(f)
                
                # Validate version compatibility
                if 'version' not in loaded_state:
                    logger.warning("Project file missing version, assuming compatibility")
                
                # Merge loaded state (preserve structure)
                self.state.update(loaded_state)
                self.project_path = project_path
                
                logger.info(f"Project loaded: {project_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            return False
    
    def save_project(self, project_path: Optional[Path] = None) -> bool:
        """
        Save project to file.
        
        Parameters
        ----------
        project_path : Path, optional
            Path to save project. If None, uses self.project_path
            
        Returns
        -------
        bool
            True if saved successfully, False otherwise
        """
        try:
            with self._lock:
                save_path = project_path or self.project_path
                if not save_path:
                    logger.error("No project path specified for save")
                    return False
                
                # Update last modified
                self.state['last_modified'] = datetime.now().isoformat()
                
                # Ensure directory exists
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save to file
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(self.state, f, indent=2, ensure_ascii=False)
                
                # Update project path if save_as
                if project_path:
                    self.project_path = project_path
                
                logger.debug(f"Project saved: {save_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving project: {e}")
            return False
    
    def save_as(self, project_path: Path) -> bool:
        """
        Save project with new path (save as).
        
        Parameters
        ----------
        project_path : Path
            New path for project file
            
        Returns
        -------
        bool
            True if saved successfully, False otherwise
        """
        return self.save_project(project_path)
    
    def update_configuration(self, config_updates: Dict[str, Any]):
        """
        Update project configuration.
        
        Parameters
        ----------
        config_updates : dict
            Dictionary of configuration updates to merge
        """
        with self._lock:
            self.state['configuration'].update(config_updates)
            self.state['last_modified'] = datetime.now().isoformat()
    
    def update_analysis_stage(self, stage: str):
        """
        Update current analysis stage.
        
        Parameters
        ----------
        stage : str
            Analysis stage: 'not_started', 'step1', 'step2', 'step3', 
                           'step4', 'step5', 'step6', 'completed'
        """
        with self._lock:
            self.state['analysis_stage'] = stage
            self.state['last_modified'] = datetime.now().isoformat()
    
    def update_enabled_features(self, features: Dict[str, bool]):
        """
        Update enabled features.
        
        Parameters
        ----------
        features : dict
            Dictionary of feature flags to update
        """
        with self._lock:
            self.state['enabled_features'].update(features)
            self.state['last_modified'] = datetime.now().isoformat()
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current project state (read-only copy).
        
        Returns
        -------
        dict
            Copy of current project state
        """
        with self._lock:
            return self.state.copy()
    
    def start_auto_save(self):
        """Start auto-save timer (saves every 5 minutes)."""
        if not self.auto_save_enabled or not self.project_path:
            return
        
        def auto_save_worker():
            if self.project_path:
                self.save_project()
                # Schedule next auto-save
                if self.auto_save_enabled:
                    self._auto_save_timer = threading.Timer(
                        self.auto_save_interval, 
                        auto_save_worker
                    )
                    self._auto_save_timer.daemon = True
                    self._auto_save_timer.start()
        
        # Start first auto-save
        self._auto_save_timer = threading.Timer(
            self.auto_save_interval,
            auto_save_worker
        )
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()
    
    def stop_auto_save(self):
        """Stop auto-save timer."""
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
            self._auto_save_timer = None
    
    def set_auto_save_interval(self, seconds: int):
        """
        Set auto-save interval.
        
        Parameters
        ----------
        seconds : int
            Auto-save interval in seconds
        """
        self.auto_save_interval = seconds
        # Restart auto-save if running
        if self._auto_save_timer:
            self.stop_auto_save()
            self.start_auto_save()

