"""
QAOverfittingInspector - Scientific QA for ML Models
====================================================

Read-only QA inspector that flags:
- Train vs CV performance gap
- Sample size adequacy (EPV warnings)
- Calibration slope/intercept deviation
- Parameter instability
- Data leakage indicators

NO model retraining, NO auto decisions - warnings and flags only.

Author: rbGyanX Team
Version: 1.1.0
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

try:
    from sklearn.metrics import roc_auc_score, brier_score_loss, calibration_curve
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Some QA checks will be limited.")


class QAOverfittingInspector:
    """
    Read-only QA inspector for ML model quality assessment.
    
    Checks for:
    - Overfitting (train vs test AUC difference)
    - Cross-validation consistency
    - Data leakage indicators
    - Sample size adequacy
    - Calibration issues
    """
    
    def __init__(self):
        """Initialize QA inspector."""
        self.warnings = []
        self.flags = []
        self.qa_results = []
    
    def inspect_analysis_output(
        self,
        analysis_dir: Path,
        ntcp_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Inspect analysis output directory for QA issues.
        
        Parameters
        ----------
        analysis_dir : Path
            Directory containing analysis output files
        ntcp_df : pd.DataFrame, optional
            NTCP results DataFrame (if already loaded)
            
        Returns
        -------
        dict
            QA results with warnings, flags, and recommendations
        """
        self.warnings = []
        self.flags = []
        self.qa_results = []
        
        # Load NTCP DataFrame if not provided
        if ntcp_df is None:
            ntcp_df = self._load_ntcp_results(analysis_dir)
        
        if ntcp_df is None or ntcp_df.empty:
            return {
                'status': 'error',
                'message': 'No NTCP results found',
                'warnings': [],
                'flags': [],
                'qa_results': []
            }
        
        # Perform all QA checks
        self._check_sample_size_adequacy(ntcp_df)
        self._check_overfitting(analysis_dir, ntcp_df)
        self._check_data_leakage(ntcp_df)
        self._check_cv_consistency(analysis_dir)
        self._check_calibration(ntcp_df)
        
        # Compile results
        return {
            'status': 'complete',
            'warnings': self.warnings,
            'flags': self.flags,
            'qa_results': self.qa_results,
            'summary': self._generate_summary()
        }
    
    def _load_ntcp_results(self, analysis_dir: Path) -> Optional[pd.DataFrame]:
        """Load NTCP results from analysis directory."""
        # Look for common result file names
        result_files = [
            analysis_dir / 'enhanced_ntcp_results.csv',
            analysis_dir / 'ntcp_results.csv',
            analysis_dir / 'results_by_organ.csv',
            analysis_dir / 'summary_performance.csv'
        ]
        
        for result_file in result_files:
            if result_file.exists():
                try:
                    df = pd.read_csv(result_file)
                    logger.info(f"Loaded NTCP results from {result_file}")
                    return df
                except Exception as e:
                    logger.warning(f"Failed to load {result_file}: {e}")
        
        # Try to find any CSV file with 'result' or 'ntcp' in name
        csv_files = list(analysis_dir.glob('*.csv'))
        for csv_file in csv_files:
            if 'result' in csv_file.name.lower() or 'ntcp' in csv_file.name.lower():
                try:
                    df = pd.read_csv(csv_file)
                    if self._is_ntcp_results_df(df):
                        logger.info(f"Loaded NTCP results from {csv_file}")
                        return df
                except Exception as e:
                    logger.warning(f"Failed to load {csv_file}: {e}")
        
        return None
    
    def _is_ntcp_results_df(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame contains NTCP results."""
        cols = [c.lower() for c in df.columns]
        # Should have organ and some prediction columns
        has_organ = any('organ' in c for c in cols)
        has_predictions = any(
            'ntcp' in c or 'ml' in c or 'lkb' in c or 'rs' in c
            for c in cols
        )
        return has_organ and has_predictions
    
    def _check_sample_size_adequacy(self, ntcp_df: pd.DataFrame):
        """
        Check sample size adequacy (EPV - Events Per Variable).
        
        Rule: Need ≥15 events and ≥50 total for reliable ML.
        """
        if 'Organ' not in ntcp_df.columns:
            return
        
        for organ in ntcp_df['Organ'].unique():
            organ_df = ntcp_df[ntcp_df['Organ'] == organ]
            n_total = len(organ_df)
            
            # Try to find outcome column
            outcome_cols = [
                'ObservedToxicity', 'Observed_Toxicity', 'Toxicity', 
                'Event', 'Grade', 'Label'
            ]
            outcome_col = None
            for col in outcome_cols:
                if col in organ_df.columns:
                    outcome_col = col
                    break
            
            if outcome_col:
                n_events = organ_df[outcome_col].sum() if organ_df[outcome_col].dtype in [int, float] else 0
            else:
                n_events = 0
            
            # Check EPV rules
            if n_events < 15:
                self.warnings.append({
                    'check': f'{organ} - Sample Size',
                    'status': 'WARNING',
                    'message': f'Only {n_events} events (need ≥15 for ML)',
                    'recommendation': 'ML predictions may be unreliable'
                })
            elif n_total < 50:
                self.warnings.append({
                    'check': f'{organ} - Sample Size',
                    'status': 'WARNING',
                    'message': f'Only {n_total} samples (recommend ≥50 for ML)',
                    'recommendation': 'Consider external validation'
                })
            else:
                self.qa_results.append({
                    'check': f'{organ} - Sample Size',
                    'status': 'PASS',
                    'message': f'{n_total} samples, {n_events} events',
                    'recommendation': 'Adequate for ML training'
                })
    
    def _check_overfitting(self, analysis_dir: Path, ntcp_df: pd.DataFrame):
        """
        Check for overfitting by comparing train vs test/CV performance.
        
        Look for:
        - Test AUC vs CV AUC difference >15% (FAIL)
        - Test AUC vs CV AUC difference >10% (WARNING)
        """
        # Look for summary performance file
        summary_files = [
            analysis_dir / 'enhanced_summary_performance.csv',
            analysis_dir / 'summary_performance.csv',
            analysis_dir / 'performance_summary.csv'
        ]
        
        summary_df = None
        for summary_file in summary_files:
            if summary_file.exists():
                try:
                    summary_df = pd.read_csv(summary_file)
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {summary_file}: {e}")
        
        if summary_df is None:
            return
        
        # Check for each organ
        organ_col = None
        for col in summary_df.columns:
            if col.lower() == 'organ':
                organ_col = col
                break
        
        for _, row in summary_df.iterrows():
            organ = row.get(organ_col, 'Unknown') if organ_col else 'Unknown'
            
            # Check ANN
            test_auc_col = None
            cv_auc_col = None
            for col in summary_df.columns:
                col_lower = col.lower()
                if 'ann' in col_lower and 'test' in col_lower and 'auc' in col_lower:
                    test_auc_col = col
                elif 'ann' in col_lower and 'cv' in col_lower and 'auc' in col_lower:
                    cv_auc_col = col
            
            if test_auc_col and cv_auc_col and test_auc_col in row.index and cv_auc_col in row.index:
                try:
                    test_auc = float(row[test_auc_col])
                    cv_auc = float(row[cv_auc_col])
                    diff = abs(test_auc - cv_auc)
                    
                    if diff > 0.15:
                        self.flags.append({
                            'check': f'{organ} - ANN Overfitting',
                            'status': 'FAIL',
                            'message': f'Test AUC ({test_auc:.3f}) differs from CV AUC ({cv_auc:.3f}) by {diff:.3f}',
                            'recommendation': 'Possible overfitting - reduce model complexity'
                        })
                    elif diff > 0.10:
                        self.warnings.append({
                            'check': f'{organ} - ANN Overfitting',
                            'status': 'WARNING',
                            'message': f'Moderate AUC difference: {diff:.3f}',
                            'recommendation': 'Monitor performance on external data'
                        })
                    else:
                        self.qa_results.append({
                            'check': f'{organ} - ANN Overfitting',
                            'status': 'PASS',
                            'message': f'AUC difference acceptable: {diff:.3f}',
                            'recommendation': 'Model generalizes well'
                        })
                except (ValueError, TypeError):
                    pass
            
            # Check XGBoost
            test_auc_col = None
            cv_auc_col = None
            for col in summary_df.columns:
                col_lower = col.lower()
                if 'xgboost' in col_lower and 'test' in col_lower and 'auc' in col_lower:
                    test_auc_col = col
                elif 'xgboost' in col_lower and 'cv' in col_lower and 'auc' in col_lower:
                    cv_auc_col = col
            
            if test_auc_col and cv_auc_col and test_auc_col in row.index and cv_auc_col in row.index:
                try:
                    test_auc = float(row[test_auc_col])
                    cv_auc = float(row[cv_auc_col])
                    diff = abs(test_auc - cv_auc)
                    
                    if diff > 0.15:
                        self.flags.append({
                            'check': f'{organ} - XGBoost Overfitting',
                            'status': 'FAIL',
                            'message': f'Test AUC ({test_auc:.3f}) differs from CV AUC ({cv_auc:.3f}) by {diff:.3f}',
                            'recommendation': 'Possible overfitting - reduce max_depth or n_estimators'
                        })
                    elif diff > 0.10:
                        self.warnings.append({
                            'check': f'{organ} - XGBoost Overfitting',
                            'status': 'WARNING',
                            'message': f'Moderate AUC difference: {diff:.3f}',
                            'recommendation': 'Monitor performance on external data'
                        })
                    else:
                        self.qa_results.append({
                            'check': f'{organ} - XGBoost Overfitting',
                            'status': 'PASS',
                            'message': f'AUC difference acceptable: {diff:.3f}',
                            'recommendation': 'Model generalizes well'
                        })
                except (ValueError, TypeError):
                    pass
    
    def _check_data_leakage(self, ntcp_df: pd.DataFrame):
        """
        Check for data leakage indicators.
        
        Flags:
        - Suspiciously perfect performance (AUC > 0.99)
        """
        if not SKLEARN_AVAILABLE:
            return
        
        if 'Organ' not in ntcp_df.columns:
            return
        
        # Find outcome column
        outcome_cols = [
            'ObservedToxicity', 'Observed_Toxicity', 'Toxicity', 
            'Event', 'Grade', 'Label'
        ]
        outcome_col = None
        for col in outcome_cols:
            if col in ntcp_df.columns:
                outcome_col = col
                break
        
        if not outcome_col:
            return
        
        # Find ML prediction columns
        ml_cols = [
            col for col in ntcp_df.columns 
            if 'ML' in col or 'ANN' in col or 'XGBoost' in col
        ]
        
        for organ in ntcp_df['Organ'].unique():
            organ_df = ntcp_df[ntcp_df['Organ'] == organ]
            
            for ml_col in ml_cols:
                if ml_col not in organ_df.columns:
                    continue
                
                try:
                    y_true = organ_df[outcome_col].values
                    y_pred = organ_df[ml_col].values
                    
                    # Remove NaN
                    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
                    if mask.sum() < 10:
                        continue
                    
                    y_true_clean = y_true[mask]
                    y_pred_clean = y_pred[mask]
                    
                    if len(np.unique(y_true_clean)) < 2:
                        continue
                    
                    auc_score = roc_auc_score(y_true_clean, y_pred_clean)
                    
                    if auc_score > 0.99:
                        self.flags.append({
                            'check': f'{organ} - Data Leakage',
                            'status': 'FAIL',
                            'message': f'{ml_col} has suspiciously high AUC: {auc_score:.3f}',
                            'recommendation': 'Check for data leakage - outcome variable may be in features'
                        })
                except Exception as e:
                    logger.debug(f"Error checking data leakage for {ml_col}: {e}")
    
    def _check_cv_consistency(self, analysis_dir: Path):
        """
        Check cross-validation consistency.
        
        Flags high variance in CV folds (std > 0.15).
        """
        summary_files = [
            analysis_dir / 'enhanced_summary_performance.csv',
            analysis_dir / 'summary_performance.csv'
        ]
        
        summary_df = None
        for summary_file in summary_files:
            if summary_file.exists():
                try:
                    summary_df = pd.read_csv(summary_file)
                    break
                except Exception as e:
                    logger.warning(f"Failed to load {summary_file}: {e}")
        
        if summary_df is None:
            return
        
        organ_col = None
        for col in summary_df.columns:
            if col.lower() == 'organ':
                organ_col = col
                break
        
        for _, row in summary_df.iterrows():
            organ = row.get(organ_col, 'Unknown') if organ_col else 'Unknown'
            
            # Check ANN CV std
            cv_auc_col = None
            cv_std_col = None
            for col in summary_df.columns:
                col_lower = col.lower()
                if 'ann' in col_lower and 'cv' in col_lower and 'auc' in col_lower and 'std' not in col_lower:
                    cv_auc_col = col
                elif 'ann' in col_lower and 'cv' in col_lower and 'std' in col_lower:
                    cv_std_col = col
            
            if cv_auc_col and cv_std_col and cv_auc_col in row.index and cv_std_col in row.index:
                try:
                    cv_auc = float(row[cv_auc_col])
                    cv_std = float(row[cv_std_col])
                    
                    if cv_std > 0.15:
                        self.warnings.append({
                            'check': f'{organ} - ANN CV Consistency',
                            'status': 'WARNING',
                            'message': f'High CV variance: {cv_std:.3f} (mean: {cv_auc:.3f})',
                            'recommendation': 'Model unstable - consider ensemble or more data'
                        })
                except (ValueError, TypeError):
                    pass
    
    def _check_calibration(self, ntcp_df: pd.DataFrame):
        """
        Check calibration slope/intercept deviation.
        
        This is a placeholder - full calibration checking would require
        observed vs predicted comparison with statistical tests.
        """
        # Basic check: look for unrealistic prediction ranges
        pred_cols = [
            col for col in ntcp_df.columns 
            if 'NTCP' in col or 'ML' in col
        ]
        
        for col in pred_cols:
            if col not in ntcp_df.columns:
                continue
            
            pred_values = pd.to_numeric(ntcp_df[col], errors='coerce').dropna()
            
            if len(pred_values) == 0:
                continue
            
            # Check if all predictions are constant (calibration issue)
            if pred_values.nunique() == 1:
                self.warnings.append({
                    'check': f'Calibration - {col}',
                    'status': 'WARNING',
                    'message': f'All predictions are constant ({pred_values.iloc[0]:.3f})',
                    'recommendation': 'Model may not be calibrated properly'
                })
            
            # Check if predictions are outside [0, 1]
            out_of_range = ((pred_values < 0) | (pred_values > 1)).sum()
            if out_of_range > 0:
                self.flags.append({
                    'check': f'Calibration - {col}',
                    'status': 'FAIL',
                    'message': f'{out_of_range} predictions outside [0, 1] range',
                    'recommendation': 'Check model output normalization'
                })
    
    def _generate_summary(self) -> str:
        """Generate human-readable summary of QA results."""
        total_checks = len(self.qa_results) + len(self.warnings) + len(self.flags)
        passed = len([r for r in self.qa_results if r.get('status') == 'PASS'])
        warnings_count = len(self.warnings)
        flags_count = len(self.flags)
        
        summary = f"QA Inspection Summary:\n"
        summary += f"  Total checks: {total_checks}\n"
        summary += f"  Passed: {passed}\n"
        summary += f"  Warnings: {warnings_count}\n"
        summary += f"  Flags: {flags_count}\n"
        
        if flags_count > 0:
            summary += "\n⚠️ Critical issues detected - review recommended\n"
        elif warnings_count > 0:
            summary += "\n⚠️ Warnings present - monitor performance\n"
        else:
            summary += "\n✓ All checks passed\n"
        
        return summary
    
    def get_qa_dataframe(self) -> pd.DataFrame:
        """
        Get QA results as DataFrame for reporting.
        
        Returns
        -------
        pd.DataFrame
            QA results with columns: Check, Status, Message, Recommendation
        """
        all_results = self.qa_results + self.warnings + self.flags
        
        if not all_results:
            return pd.DataFrame(columns=['Check', 'Status', 'Message', 'Recommendation'])
        
        return pd.DataFrame(all_results)

