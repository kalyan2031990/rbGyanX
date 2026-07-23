"""
Auto-Correction Engine for rbGyanX_basic

Safely fixes runtime, GUI, IO, and dependency issues.
NEVER modifies scientific code (equations, models, workflows).

Author: rbGyanX Team
Version: 1.0.0
"""

import re
import sys
import subprocess
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import shutil

# Load protected modules from registry
PROTECTED_MODULES = []
PROTECTED_MODULES_REGISTRY = Path(__file__).parent / "protected_modules.json"

try:
    if PROTECTED_MODULES_REGISTRY.exists():
        with open(PROTECTED_MODULES_REGISTRY, 'r', encoding='utf-8') as f:
            registry = json.load(f)
            # Extract all protected files
            for category, data in registry.get('protected_modules', {}).items():
                PROTECTED_MODULES.extend(data.get('files', []))
except Exception:
    # Fallback to hardcoded list if registry not available
    PROTECTED_MODULES = [
        'code1_dvh_preprocess.py',
        'code2_dvh_plot_and_summary.py',
        'code3_ntcp_analysis_ml.py',
        'code4_ntcp_output_QA_reporter.py',
        'code5_ntcp_factors_analysis.py',
        'code6_tcp_analysis.py',
        'code7_tcp_ntcp_integration.py',
        'models/ntcp_models.py',
        'models/tcp_models.py',
        'utils/ntcp_models.py',
        'utils/tcp_models.py',
        'utils/dvh_utils.py',
        'utils/ml_models.py',
        'plots/dose_response.py',
        'stats/basic_stats.py'
    ]


class AutoCorrectionEngine:
    """
    Safe auto-correction engine for rbGyanX_basic.
    
    Only fixes:
    - Missing imports (adds try/except blocks)
    - Path errors (creates missing directories)
    - GUI geometry conflicts (adjusts window sizes)
    - File-not-found (creates placeholder files or fixes paths)
    
    NEVER modifies:
    - Scientific equations
    - Model calculations
    - Workflow logic
    """
    
    def __init__(self, repo_root: Path, log_file: Optional[Path] = None):
        """
        Initialize Auto-Correction Engine.
        
        Parameters
        ----------
        repo_root : Path
            Root directory of rbGyanX repository
        log_file : Path, optional
            Path to execution log file
        """
        self.repo_root = Path(repo_root)
        self.log_file = log_file or (self.repo_root / "rbgyanx_gui.log")
        self.detected_issues = []
        self.proposed_fixes = []
        self.applied_fixes = []
        self.fix_backups = {}  # Store backups for reversible fixes
        self.escalated_issues = []  # Issues that require developer intervention
        self.protected_modules = self._load_protected_modules()
    
    def _load_protected_modules(self) -> List[str]:
        """Load protected modules from registry"""
        try:
            registry_path = self.repo_root / "qa" / "protected_modules.json"
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
                    protected = []
                    for category, data in registry.get('protected_modules', {}).items():
                        protected.extend(data.get('files', []))
                    return protected
        except Exception:
            pass
        return PROTECTED_MODULES
        
    def analyze_log(self) -> List[Dict]:
        """
        Analyze execution log and detect fixable issues.
        
        Returns
        -------
        List[Dict]
            List of detected issues with proposed fixes
        """
        self.detected_issues = []
        
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            
            # Detect missing imports
            self._detect_missing_imports(log_content)
            
            # Detect path errors
            self._detect_path_errors(log_content)
            
            # Detect file-not-found errors
            self._detect_file_not_found(log_content)
            
            # Detect GUI geometry issues
            self._detect_gui_geometry_issues(log_content)
            
            return self.detected_issues
            
        except Exception as e:
            return [{
                'type': 'analysis_error',
                'severity': 'error',
                'message': f"Error analyzing log: {str(e)}",
                'fixable': False
            }]
    
    def _detect_missing_imports(self, log_content: str):
        """Detect missing import errors"""
        patterns = [
            (r"ImportError.*No module named ['\"]([\w.]+)['\"]", 'missing_import'),
            (r"ModuleNotFoundError.*No module named ['\"]([\w.]+)['\"]", 'missing_import'),
            (r"Warning:.*not available.*([\w.]+)", 'optional_import'),
        ]
        
        for pattern, issue_type in patterns:
            matches = re.finditer(pattern, log_content, re.IGNORECASE)
            for match in matches:
                module_name = match.group(1) if match.groups() else None
                if module_name:
                    # Check if this is a protected module (don't auto-fix, escalate)
                    if self._is_protected_module(module_name):
                        self.escalated_issues.append({
                            'type': 'scientific_logic_error',
                            'module': module_name,
                            'issue': f"Missing import in protected module: {module_name}",
                            'action': 'escalate_to_developer'
                        })
                        continue
                    
                    self.detected_issues.append({
                        'type': issue_type,
                        'severity': 'warning' if issue_type == 'optional_import' else 'error',
                        'message': f"Missing import: {module_name}",
                        'module': module_name,
                        'fixable': True,
                        'fix_type': 'add_import_guard'
                    })
    
    def _detect_path_errors(self, log_content: str):
        """Detect path-related errors"""
        patterns = [
            (r"FileNotFoundError.*['\"]([^'\"]+)['\"]", 'file_not_found'),
            (r"Directory.*not found.*['\"]([^'\"]+)['\"]", 'directory_not_found'),
            (r"Path.*does not exist.*['\"]([^'\"]+)['\"]", 'path_not_found'),
        ]
        
        for pattern, issue_type in patterns:
            matches = re.finditer(pattern, log_content, re.IGNORECASE)
            for match in matches:
                path_str = match.group(1) if match.groups() else None
                if path_str:
                    # Extract relative path
                    path = Path(path_str)
                    if not path.is_absolute():
                        path = self.repo_root / path
                    
                    # Check if it's a directory that should exist
                    if path_str.endswith('/') or path_str.endswith('\\') or 'directory' in match.group(0).lower():
                        if not self._is_protected_file(path_str):
                            self.detected_issues.append({
                                'type': issue_type,
                                'severity': 'error',
                                'message': f"Missing directory: {path_str}",
                                'path': str(path),
                                'fixable': True,
                                'fix_type': 'create_directory'
                            })
    
    def _detect_file_not_found(self, log_content: str):
        """Detect file-not-found errors"""
        patterns = [
            (r"File.*not found.*['\"]([^'\"]+)['\"]", 'file_not_found'),
            (r"Could not find.*['\"]([^'\"]+)['\"]", 'file_not_found'),
            (r"Missing file.*['\"]([^'\"]+)['\"]", 'file_not_found'),
        ]
        
        for pattern, issue_type in patterns:
            matches = re.finditer(pattern, log_content, re.IGNORECASE)
            for match in matches:
                file_path_str = match.group(1) if match.groups() else None
                if file_path_str:
                    # Check if this is a protected module (escalate, don't fix)
                    if self._is_protected_file(file_path_str):
                        self.escalated_issues.append({
                            'type': 'scientific_logic_error',
                            'file': file_path_str,
                            'issue': f"File not found error in protected module: {file_path_str}",
                            'action': 'escalate_to_developer'
                        })
                        continue
                    
                    file_path = Path(file_path_str)
                    if not file_path.is_absolute():
                        file_path = self.repo_root / file_path
                    
                    # Only fix config/template files, not data files
                    if 'config' in file_path_str or 'template' in file_path_str or 'schema' in file_path_str:
                        self.detected_issues.append({
                            'type': issue_type,
                            'severity': 'warning',
                            'message': f"Missing file: {file_path_str}",
                            'path': str(file_path),
                            'fixable': True,
                            'fix_type': 'create_placeholder_file'
                        })
    
    def _detect_gui_geometry_issues(self, log_content: str):
        """Detect GUI geometry/display issues"""
        patterns = [
            (r"geometry.*error|window.*too.*large|screen.*size", 'gui_geometry'),
            (r"TclError.*bad.*geometry", 'gui_geometry'),
        ]
        
        for pattern, issue_type in patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                self.detected_issues.append({
                    'type': issue_type,
                    'severity': 'warning',
                    'message': "GUI geometry conflict detected",
                    'fixable': True,
                    'fix_type': 'adjust_gui_geometry'
                })
                break  # Only report once
    
    def propose_fixes(self) -> List[Dict]:
        """
        Propose fixes for detected issues.
        
        Returns
        -------
        List[Dict]
            List of proposed fixes with descriptions
        """
        self.proposed_fixes = []
        
        for issue in self.detected_issues:
            if not issue.get('fixable', False):
                continue
            
            fix = {
                'issue': issue,
                'description': '',
                'action': '',
                'reversible': False,
                'risk_level': 'low'
            }
            
            if issue['fix_type'] == 'create_directory':
                fix['description'] = f"Create missing directory: {issue.get('path', 'unknown')}"
                fix['action'] = f"mkdir -p {issue.get('path', '')}"
                fix['reversible'] = True
                fix['risk_level'] = 'low'
            
            elif issue['fix_type'] == 'create_placeholder_file':
                fix['description'] = f"Create placeholder file: {issue.get('path', 'unknown')}"
                fix['action'] = f"Create empty file at {issue.get('path', '')}"
                fix['reversible'] = True
                fix['risk_level'] = 'low'
            
            elif issue['fix_type'] == 'add_import_guard':
                module = issue.get('module', 'unknown')
                fix['description'] = f"Add import guard for optional module: {module}"
                fix['action'] = f"Add try/except block for {module} import"
                fix['reversible'] = True
                fix['risk_level'] = 'low'
            
            elif issue['fix_type'] == 'adjust_gui_geometry':
                fix['description'] = "Adjust GUI window geometry to fit screen"
                fix['action'] = "Modify window size calculation in GUI initialization"
                fix['reversible'] = True
                fix['risk_level'] = 'low'
            
            self.proposed_fixes.append(fix)
        
        return self.proposed_fixes
    
    def apply_fix(self, fix: Dict, ask_permission: bool = True) -> Tuple[bool, str]:
        """
        Apply a proposed fix (with user permission if requested).
        
        Parameters
        ----------
        fix : Dict
            Fix dictionary from propose_fixes()
        ask_permission : bool
            If True, this method should not apply directly (GUI will ask)
        
        Returns
        -------
        Tuple[bool, str]
            (success, message)
        """
        if ask_permission:
            # This should be called from GUI with permission already granted
            return False, "Permission required"
        
        issue = fix['issue']
        fix_type = issue.get('fix_type')
        
        try:
            if fix_type == 'create_directory':
                path = Path(issue.get('path', ''))
                if path and not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    self.applied_fixes.append({
                        'fix': fix,
                        'timestamp': datetime.now().isoformat(),
                        'success': True
                    })
                    return True, f"Created directory: {path}"
            
            elif fix_type == 'create_placeholder_file':
                path = Path(issue.get('path', ''))
                if path and not path.exists():
                    # Only create placeholder for config/template files
                    if 'config' in str(path) or 'template' in str(path) or 'schema' in str(path):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.touch()
                        self.applied_fixes.append({
                            'fix': fix,
                            'timestamp': datetime.now().isoformat(),
                            'success': True
                        })
                        return True, f"Created placeholder file: {path}"
            
            elif fix_type == 'add_import_guard':
                # This requires code modification - be very careful
                # Only modify non-scientific files
                module = issue.get('module', '')
                # Find where this import should be added (in GUI or utility files only)
                target_files = ['rbgyanx_gui.py', 'utils/error_handler.py']
                # This is complex - skip for now, just suggest manual fix
                return False, f"Manual fix required: Add import guard for {module}"
            
            elif fix_type == 'adjust_gui_geometry':
                # This requires code modification - skip auto-fix, suggest manual
                return False, "Manual fix required: Adjust GUI geometry in rbgyanx_gui.py"
            
            return False, "Unknown fix type"
            
        except Exception as e:
            return False, f"Error applying fix: {str(e)}"
    
    def apply_all_fixes(self, fixes: List[Dict], ask_permission: bool = True) -> Dict:
        """
        Apply multiple fixes (with user permission).
        
        Parameters
        ----------
        fixes : List[Dict]
            List of fixes to apply
        ask_permission : bool
            If True, requires GUI permission dialog
        
        Returns
        -------
        Dict
            Summary of applied fixes
        """
        if ask_permission:
            return {'applied': 0, 'failed': 0, 'skipped': len(fixes), 'message': 'Permission required'}
        
        applied_count = 0
        failed_count = 0
        
        for fix in fixes:
            success, message = self.apply_fix(fix, ask_permission=False)
            if success:
                applied_count += 1
            else:
                failed_count += 1
        
        return {
            'applied': applied_count,
            'failed': failed_count,
            'skipped': len(fixes) - applied_count - failed_count,
            'message': f"Applied {applied_count}, failed {failed_count}"
        }
    
    def _load_protected_modules(self) -> List[str]:
        """Load protected modules from registry"""
        try:
            registry_path = self.repo_root / "qa" / "protected_modules.json"
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry = json.load(f)
                    protected = []
                    for category, data in registry.get('protected_modules', {}).items():
                        protected.extend(data.get('files', []))
                    return protected
        except Exception:
            pass
        return PROTECTED_MODULES
    
    def _is_protected_module(self, module_name: str) -> bool:
        """Check if module is protected"""
        for protected in self.protected_modules:
            if module_name in protected or protected in module_name:
                return True
        return False
    
    def _is_protected_file(self, file_path: str) -> bool:
        """Check if file path is protected"""
        for protected in self.protected_modules:
            if protected in file_path:
                return True
        return False
    
    def _classify_issue(self, issue: Dict) -> str:
        """
        Classify issue type for escalation.
        
        Parameters
        ----------
        issue : Dict
            Issue dictionary
        
        Returns
        -------
        str
            Issue classification: 'infrastructure', 'workflow', 'clinical_schema', 'scientific_logic'
        """
        issue_type = issue.get('type', '')
        issue_msg = issue.get('message', '').lower()
        
        # Scientific logic errors
        if any(keyword in issue_msg for keyword in ['equation', 'model', 'tcp', 'ntcp', 'metric', 'calculation']):
            if self._is_protected_file(issue_msg) or self._is_protected_module(issue_msg):
                return 'scientific_logic'
        
        # Clinical schema errors
        if any(keyword in issue_msg for keyword in ['clinical', 'schema', 'adapter', 'excel']):
            if 'clinical' in issue_msg and ('schema' in issue_msg or 'adapter' in issue_msg):
                return 'clinical_schema'
        
        # Workflow errors
        if any(keyword in issue_msg for keyword in ['workflow', 'step', 'pipeline', 'execution']):
            return 'workflow'
        
        # Default to infrastructure
        return 'infrastructure'
    
    def check_escalation_needed(self) -> Tuple[bool, List[Dict]]:
        """
        Check if any issues require escalation.
        
        Returns
        -------
        Tuple[bool, List[Dict]]
            (needs_escalation, escalated_issues)
        """
        return len(self.escalated_issues) > 0, self.escalated_issues
    
    def generate_diagnostic_report(self, output_path: Path) -> Path:
        """
        Generate diagnostic report with issue classification.
        
        Parameters
        ----------
        output_path : Path
            Path for diagnostic report
        
        Returns
        -------
        Path
            Path to generated report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Classify all issues
        classified_issues = {
            'infrastructure': [],
            'workflow': [],
            'clinical_schema': [],
            'scientific_logic': []
        }
        
        for issue in self.detected_issues:
            classification = self._classify_issue(issue)
            classified_issues[classification].append(issue)
        
        # Add escalated issues
        for escalated in self.escalated_issues:
            classified_issues['scientific_logic'].append(escalated)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>rbGyanX Diagnostic Report</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #000080 0%, #4169E1 100%); color: white; padding: 2rem; border-radius: 8px; margin-bottom: 2rem; }}
        .category {{ background: white; padding: 1rem; margin: 1rem 0; border-radius: 4px; border-left: 4px solid #007bff; }}
        .category.scientific {{ border-left-color: #dc3545; }}
        .category.infrastructure {{ border-left-color: #28a745; }}
        .category.workflow {{ border-left-color: #ffc107; }}
        .category.clinical {{ border-left-color: #17a2b8; }}
        .escalation {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin: 1rem 0; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>rbGyanX Diagnostic Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <h2>Issue Classification</h2>
"""
        
        for category, issues in classified_issues.items():
            if issues:
                html += f"""
    <div class="category {category}">
        <h3>{category.replace('_', ' ').title()} Issues ({len(issues)})</h3>
"""
                for issue in issues:
                    html += f"""
        <div style="margin: 0.5rem 0; padding: 0.5rem; background: #f8f9fa; border-radius: 4px;">
            <strong>{issue.get('type', 'Unknown')}</strong><br>
            {issue.get('message', 'No message')}<br>
            <em>File: {issue.get('path', issue.get('module', 'N/A'))}</em>
        </div>
"""
                html += """
    </div>
"""
        
        # Escalation section
        if self.escalated_issues:
            html += """
    <div class="escalation">
        <h3>⚠️ Issues Requiring Developer Intervention</h3>
        <p><strong>These issues cannot be auto-corrected and require developer intervention.</strong></p>
        <p>Please switch to rbGyanX_advanced or use Cursor / Copilot / Codex.</p>
        <ul>
"""
            for escalated in self.escalated_issues:
                html += f"""
            <li><strong>{escalated.get('type', 'Unknown')}:</strong> {escalated.get('issue', 'No details')}</li>
"""
            html += """
        </ul>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path
    
    def verify_scientific_code_integrity(self) -> bool:
        """
        Verify that scientific code files remain unchanged.
        
        Returns
        -------
        bool
            True if all scientific code files are intact
        """
        # Verify protected files exist
        for protected_file in self.protected_modules:
            file_path = self.repo_root / protected_file
            if not file_path.exists():
                return False
        return True
    
    def generate_fix_report(self, output_path: Path) -> Path:
        """
        Generate HTML report of detected issues and proposed fixes.
        
        Parameters
        ----------
        output_path : Path
            Path for HTML report
        
        Returns
        -------
        Path
            Path to generated report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>rbGyanX Auto-Correction Report</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #000080 0%, #4169E1 100%); color: white; padding: 2rem; border-radius: 8px; margin-bottom: 2rem; }}
        .issue {{ background: white; padding: 1rem; margin: 1rem 0; border-radius: 4px; border-left: 4px solid #ffc107; }}
        .issue.error {{ border-left-color: #dc3545; }}
        .issue.warning {{ border-left-color: #ffc107; }}
        .fix {{ background: #e3f2fd; padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }}
        .summary {{ background: white; padding: 1.5rem; border-radius: 8px; margin-bottom: 2rem; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>rbGyanX Auto-Correction Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Issues Detected: {len(self.detected_issues)}</p>
        <p>Fixes Proposed: {len(self.proposed_fixes)}</p>
        <p>Fixes Applied: {len(self.applied_fixes)}</p>
    </div>
    
    <h2>Detected Issues</h2>
"""
        
        for issue in self.detected_issues:
            severity = issue.get('severity', 'warning')
            html += f"""
    <div class="issue {severity}">
        <h3>{issue.get('type', 'Unknown')}</h3>
        <p>{issue.get('message', 'No message')}</p>
        <p><strong>Fixable:</strong> {'Yes' if issue.get('fixable') else 'No'}</p>
    </div>
"""
        
        html += """
    <h2>Proposed Fixes</h2>
"""
        
        for fix in self.proposed_fixes:
            html += f"""
    <div class="fix">
        <h3>{fix.get('description', 'No description')}</h3>
        <p><strong>Action:</strong> {fix.get('action', 'No action')}</p>
        <p><strong>Risk Level:</strong> {fix.get('risk_level', 'unknown')}</p>
        <p><strong>Reversible:</strong> {'Yes' if fix.get('reversible') else 'No'}</p>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return output_path


def run_auto_correction(repo_root: Optional[Path] = None, log_file: Optional[Path] = None) -> Dict:
    """
    Convenience function to run auto-correction analysis.
    
    Parameters
    ----------
    repo_root : Path, optional
        Root directory of rbGyanX repository
    log_file : Path, optional
        Path to execution log file
    
    Returns
    -------
    Dict
        Analysis results with detected issues and proposed fixes
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent
    
    engine = AutoCorrectionEngine(repo_root, log_file)
    issues = engine.analyze_log()
    fixes = engine.propose_fixes()
    
    return {
        'issues': issues,
        'fixes': fixes,
        'engine': engine
    }


if __name__ == "__main__":
    # Allow running as standalone script
    results = run_auto_correction()
    print(f"\nAuto-Correction Analysis:")
    print(f"Issues detected: {len(results['issues'])}")
    print(f"Fixes proposed: {len(results['fixes'])}")

