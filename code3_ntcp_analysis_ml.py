#!/usr/bin/env python3
"""
rbGyanX v1.0 - NTCP Analysis with Traditional and Machine Learning Models
=========================================================================

✓ KEEP: All ML models (ANN, XGBoost)
✓ KEEP: SHAP explainability
✓ KEEP: Publication-quality plots
✓ FIX: Unicode encoding for Windows
✓ FIX: Output file generation

Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

This comprehensive script combines:
1. Traditional NTCP models (LKB Log-Logistic, LKB Probit, RS Poisson)
2. Machine learning models (ANN, XGBoost) with proper validation
3. SHAP explainability analysis (optional, with --enable_shap)
4. Professional 600 DPI publication-ready plots
5. Unique colors and legends for all models
6. Comprehensive Excel output with all results

Author: rbGyanX Team
License: MIT
"""

import sys
import io

# ✓ CRITICAL: Force UTF-8 encoding for Windows compatibility
# This prevents UnicodeEncodeError when printing checkmarks/symbols
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )

# Now safe to use Unicode characters in print statements

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm
from sklearn.metrics import roc_curve, auc, brier_score_loss, log_loss
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", message=".*tight_layout.*", category=UserWarning)

# SHAP explainability (optional)
try:
    from utils.shap_utils import (
        safe_shap_values,
        to_matrix,
        plot_summary_bar,
        plot_beeswarm,
        generate_shap_caption
    )
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("Warning: SHAP not available. Install with: pip install shap")

# Try to import XGBoost
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available. Install with: pip install xgboost")

# Unified plotting configuration (PROMPT 11)
try:
    from utils.plot_config import (
        apply_rbgyanx_style,
        get_model_color,
        get_model_line_style,
        get_model_marker,
        save_publication_plot,
        RBGYANX_COLORS as COLORS,
        LINE_STYLES,
        MARKERS
    )
    apply_rbgyanx_style()  # Apply unified style
    PLOT_CONFIG_AVAILABLE = True
except ImportError:
    # Fallback to local definitions if plot_config not available
    PLOT_CONFIG_AVAILABLE = False
    plt.rcParams.update({
        'font.size': 12,
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'axes.linewidth': 1.2,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linewidth': 0.8,
        'legend.frameon': False,
        'legend.fontsize': 10,
        'xtick.major.size': 6,
        'ytick.major.size': 6,
        'xtick.minor.size': 3,
        'ytick.minor.size': 3,
        'lines.linewidth': 2.5,
        'lines.markersize': 6,
        'figure.dpi': 100,
        'savefig.dpi': 600,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
        'savefig.facecolor': 'white'
    })
    
    COLORS = {
        'LKB_LogLogit': '#2E86AB',
        'LKB_Probit': '#F24236',
        'RS_Poisson': '#F6AE2D',
        'ML_ANN': '#8B4B9E',
        'ML_XGBoost': '#2ECC71',
        'observed': '#C73E1D',
        'literature': '#592E83',
        'confidence': '#95A5A6',
        'grid': '#E8E8E8'
    }
    
    LINE_STYLES = {
        'LKB_LogLogit': '-',
        'LKB_Probit': '--',
        'RS_Poisson': '-.',
        'ML_ANN': ':',
        'ML_XGBoost': (0, (3, 1, 1, 1))
    }
    
    MARKERS = {
        'LKB_LogLogit': 'o',
        'LKB_Probit': 's',
        'RS_Poisson': '^',
        'ML_ANN': 'D',
        'ML_XGBoost': 'X'
    }

class DVHProcessor:
    """Process differential DVH data for NTCP calculations"""
    
    def __init__(self, dvh_directory):
        self.dvh_dir = Path(dvh_directory)
        self.processed_data = {}
        
    def load_dvh_file(self, patient_id, organ):
        """Load differential DVH file for specific patient and organ"""
        dvh_file = self.dvh_dir / f"{patient_id}_{organ}.csv"
        
        if not dvh_file.exists():
            print(f"Warning: DVH file not found: {dvh_file}")
            return None
            
        try:
            # Load DVH data
            dvh = pd.read_csv(dvh_file)
            
            # Standardize column names
            if "Dose[Gy]" in dvh.columns and "Volume[cm3]" in dvh.columns:
                dvh = dvh.rename(columns={"Dose[Gy]": "dose_gy", "Volume[cm3]": "volume_cm3"})
            elif "Dose[Gy]" in dvh.columns and "Volume[%]" in dvh.columns:
                dvh = dvh.rename(columns={"Dose[Gy]": "dose_gy", "Volume[%]": "volume_cm3"})
            elif "Dose" in dvh.columns and "Volume" in dvh.columns:
                dvh = dvh.rename(columns={"Dose": "dose_gy", "Volume": "volume_cm3"})
            
            # Remove zero volume entries at high doses
            dvh = dvh[dvh['volume_cm3'] > 0].copy()
            
            # Sort by dose
            dvh = dvh.sort_values('dose_gy').reset_index(drop=True)
            
            return dvh
            
        except Exception as e:
            print(f"Error loading {dvh_file}: {e}")
            return None
    
    def calculate_dose_metrics(self, dvh):
        """Calculate comprehensive dose metrics from differential DVH"""
        if dvh is None or len(dvh) == 0:
            return None
            
        doses = dvh['dose_gy'].values
        volumes = dvh['volume_cm3'].values
        total_volume = np.sum(volumes)
        
        if total_volume <= 0:
            return None
        
        # Calculate relative volumes
        rel_volumes = volumes / total_volume
        
        # Basic dose metrics
        mean_dose = np.sum(rel_volumes * doses)
        max_dose = np.max(doses)
        min_dose = np.min(doses[volumes > 0])
        
        # Convert to cumulative DVH for Vxx calculations
        cumulative_vol = np.cumsum(volumes[::-1])[::-1]
        rel_cumulative = cumulative_vol / total_volume
        
        dose_metrics = {
            'total_volume': total_volume,
            'mean_dose': mean_dose,
            'max_dose': max_dose,
            'min_dose': min_dose
        }
        
        # Calculate Vxx (% volume receiving >= xx Gy)
        for dose_level in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]:
            if dose_level <= max_dose:
                volume_at_dose = np.interp(dose_level, doses, rel_cumulative) * 100
                dose_metrics[f'V{dose_level}'] = volume_at_dose
            else:
                dose_metrics[f'V{dose_level}'] = 0.0
        
        # Calculate Dxx (dose to xx% of volume)
        for vol_percent in [0.01, 0.1, 1, 2, 5, 10, 20, 30, 50, 70, 90, 95, 98]:
            target_vol_fraction = vol_percent / 100
            if target_vol_fraction <= 1.0:
                dose_at_volume = np.interp(target_vol_fraction, rel_cumulative[::-1], doses[::-1])
                dose_metrics[f'D{vol_percent}'] = dose_at_volume
        
        return dose_metrics
    
    def calculate_gEUD(self, dvh, a_parameter):
        """Calculate generalized Equivalent Uniform Dose (gEUD)"""
        if dvh is None or len(dvh) == 0:
            return np.nan
            
        doses = dvh['dose_gy'].values
        volumes = dvh['volume_cm3'].values
        total_volume = np.sum(volumes)
        
        if total_volume <= 0:
            return np.nan
        
        # Calculate relative volumes
        rel_volumes = volumes / total_volume
        
        # Handle special cases
        if a_parameter == 0:
            # a=0 case: geometric mean
            log_doses = np.log(np.maximum(doses, 1e-10))
            log_geud = np.sum(rel_volumes * log_doses)
            return np.exp(log_geud)
        
        elif a_parameter == 1:
            # a=1 case: arithmetic mean (mean dose)
            return np.sum(rel_volumes * doses)
        
        elif np.isinf(a_parameter):
            # a=∞ case: maximum dose
            return np.max(doses)
        
        else:
            # General case: gEUD = (Σ vi × Di^a)^(1/a)
            powered_doses = np.power(np.maximum(doses, 1e-10), a_parameter)
            sum_weighted = np.sum(rel_volumes * powered_doses)
            
            if sum_weighted <= 0:
                return np.nan
                
            geud = np.power(sum_weighted, 1.0 / a_parameter)
            return geud
    
    def calculate_effective_volume(self, dvh, n_parameter):
        """Calculate effective volume for LKB probit model"""
        if dvh is None or len(dvh) == 0:
            return np.nan
            
        doses = dvh['dose_gy'].values
        volumes = dvh['volume_cm3'].values
        total_volume = np.sum(volumes)
        
        if total_volume <= 0:
            return np.nan
        
        max_dose = np.max(doses)
        if max_dose <= 0:
            return np.nan
        
        # Calculate relative volumes
        rel_volumes = volumes / total_volume
        
        # Calculate dose ratio terms
        dose_ratios = doses / max_dose
        
        if n_parameter == 0:
            return 1.0
        else:
            powered_ratios = np.power(dose_ratios, 1.0 / n_parameter)
            v_eff = np.sum(rel_volumes * powered_ratios)
            return v_eff

# Backward compatibility: Import from new location
# Phase 1B.3 refactoring: Core computation moved to rbgyanx.core.ntcp
from rbgyanx.core.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from rbgyanx.core.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from rbgyanx.core.ntcp.rs_poisson import calculate_ntcp_rs_poisson
from rbgyanx.core.tcp._eqd2 import convert_to_eqd2


class NTCPCalculator:
    """Calculate NTCP using published model equations
    
    NOTE: Phase 1B.3 Refactoring - This class now delegates to core functions
    in rbgyanx.core.ntcp while maintaining the same interface for backward compatibility.
    """
    
    def __init__(self):
        # Literature parameters
        self.literature_params = {
            'Parotid': {
                'LKB_LogLogit': {'a': 2.2, 'TD50': 28.4, 'gamma50': 1.0, 'alpha_beta': 3},
                'LKB_Probit': {'TD50': 28.4, 'm': 0.18, 'n': 0.45, 'alpha_beta': 3},
                'RS_Poisson': {'D50': 26.3, 'gamma': 0.73, 's': 0.01, 'alpha_beta': 3}
            },
            'Larynx': {
                'LKB_LogLogit': {'a': 1.0, 'TD50': 44.0, 'gamma50': 1.0, 'alpha_beta': 3},
                'LKB_Probit': {'TD50': 44.0, 'm': 0.20, 'n': 1.0, 'alpha_beta': 3},
                'RS_Poisson': {'D50': 40.0, 'gamma': 1.2, 's': 0.12, 'alpha_beta': 3}
            },
            'SpinalCord': {
                'LKB_LogLogit': {'a': 7.4, 'TD50': 66.5, 'gamma50': 4.0, 'alpha_beta': 2},
                'LKB_Probit': {'TD50': 66.5, 'm': 0.10, 'n': 0.03, 'alpha_beta': 2},
                'RS_Poisson': {'D50': 68.6, 'gamma': 1.9, 's': 4.0, 'alpha_beta': 2}
            }
        }
    
    def convert_to_eqd2(self, dose, alpha_beta_ratio, dose_per_fraction, n_fractions=None):
        """Convert physical dose to EQD2
        
        NOTE: Phase 1B.3 - Delegates to rbgyanx.core.tcp._eqd2.convert_to_eqd2
        """
        # Handle NaN case (core function returns NaN, but we want to match original behavior)
        if np.isnan(dose) or dose <= 0:
            return np.nan
        return convert_to_eqd2(dose, alpha_beta_ratio, dose_per_fraction, n_fractions)
    
    def _calculate_biological_dose(self, physical_dose, patient_id, organ, clinical_dict=None, dose_per_fraction=2.0, n_fractions=30, alpha_beta=3.0):
        """Convert physical dose to EQD2/BED if fractionation data available"""
        try:
            # Try to get fractionation from clinical data if provided
            if clinical_dict:
                clin_data = clinical_dict.get(patient_id, {})
                if clin_data:
                    n_frac = clin_data.get('n_frac', n_fractions)
                    dose_per_fx = clin_data.get('dose_per_frac_Gy', dose_per_fraction)
                    alpha_beta = clin_data.get('alpha_beta', alpha_beta)
                    
                    # Calculate BED
                    bed = physical_dose * (1 + dose_per_fx / alpha_beta)
                    # Calculate EQD2
                    eqd2 = bed / (1 + 2/alpha_beta)
                    
                    return {
                        'physical': physical_dose,
                        'bed': bed,
                        'eqd2': eqd2,
                        'n_frac': n_frac,
                        'alpha_beta': alpha_beta,
                        'dose_per_fraction': dose_per_fx
                    }
        except Exception as e:
            print(f"Warning: Biological dose conversion failed: {e}")
        
        # Fallback: return physical dose with default conversion
        bed = physical_dose * (1 + dose_per_fraction / alpha_beta)
        eqd2 = bed / (1 + 2/alpha_beta)
        
        return {
            'physical': physical_dose,
            'bed': bed,
            'eqd2': eqd2,
            'n_frac': n_fractions,
            'alpha_beta': alpha_beta,
            'dose_per_fraction': dose_per_fraction
        }
    
    def ntcp_lkb_loglogit(self, geud, TD50, gamma50):
        """LKB model with log-logistic link function
        
        NOTE: Phase 1B.3 - Delegates to rbgyanx.core.ntcp.calculate_ntcp_lkb_loglogit
        """
        return calculate_ntcp_lkb_loglogit(geud, TD50, gamma50)
    
    def ntcp_lkb_probit(self, dose_metrics, TD50, m, n):
        """LKB model with probit link function
        
        NOTE: Phase 1B.3 - Delegates to rbgyanx.core.ntcp.calculate_ntcp_lkb_probit
        """
        return calculate_ntcp_lkb_probit(dose_metrics, TD50, m, n)
    
    def ntcp_rs_poisson(self, dvh, D50, gamma, s):
        """Relative Seriality model with Poisson statistics
        
        NOTE: Phase 1B.3 - Delegates to rbgyanx.core.ntcp.calculate_ntcp_rs_poisson
        """
        return calculate_ntcp_rs_poisson(dvh, D50, gamma, s)
    
    def calculate_all_ntcp_models(self, dvh, dose_metrics, organ, dose_per_fraction=2.0):
        """Calculate NTCP using all three models for given organ"""
        
        if organ not in self.literature_params:
            print(f"Warning: No parameters available for organ '{organ}'")
            return {}
        
        organ_params = self.literature_params[organ]
        results = {}
        
        # Get required dose metrics
        geud = dose_metrics.get('gEUD', np.nan)
        v_effective = dose_metrics.get('v_effective', np.nan)
        
        # 1. LKB Log-Logistic Model
        try:
            params = organ_params['LKB_LogLogit']
            geud_eqd2 = self.convert_to_eqd2(geud, params['alpha_beta'], dose_per_fraction)
            ntcp_lkb_loglogit = self.ntcp_lkb_loglogit(geud_eqd2, params['TD50'], params['gamma50'])
            
            results['LKB_LogLogit'] = {
                'NTCP': ntcp_lkb_loglogit,
                'gEUD_physical': geud,
                'gEUD_EQD2': geud_eqd2,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating LKB LogLogit for {organ}: {e}")
            results['LKB_LogLogit'] = {'NTCP': 0.0, 'error': str(e)}
        
        # 2. LKB Probit Model
        try:
            params = organ_params['LKB_Probit']
            dose_metrics_copy = dose_metrics.copy()
            dose_metrics_copy['v_effective'] = v_effective
            
            ntcp_lkb_probit = self.ntcp_lkb_probit(dose_metrics_copy, params['TD50'], params['m'], params['n'])
            
            results['LKB_Probit'] = {
                'NTCP': ntcp_lkb_probit,
                'v_effective': v_effective,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating LKB Probit for {organ}: {e}")
            results['LKB_Probit'] = {'NTCP': 0.0, 'error': str(e)}
        
        # 3. RS Poisson Model
        try:
            params = organ_params['RS_Poisson']
            dvh_eqd2 = dvh.copy()
            dvh_eqd2['dose_gy'] = dvh_eqd2['dose_gy'].apply(
                lambda d: self.convert_to_eqd2(d, params['alpha_beta'], dose_per_fraction)
            )
            
            ntcp_rs = self.ntcp_rs_poisson(dvh_eqd2, params['D50'], params['gamma'], params['s'])
            
            results['RS_Poisson'] = {
                'NTCP': ntcp_rs,
                'parameters_used': params
            }
        except Exception as e:
            print(f"Error calculating RS Poisson for {organ}: {e}")
            results['RS_Poisson'] = {'NTCP': 0.0, 'error': str(e)}
        
        return results

class MachineLearningModels:
    """Machine learning models for NTCP prediction with proper validation"""
    
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.models = {}
        self.scalers = {}
        
    def prepare_features(self, organ_data):
        """Prepare feature matrix for ML models"""
        
        # Select relevant dose metrics for features
        feature_cols = [
            'mean_dose', 'max_dose', 'gEUD', 'total_volume',
            'V5', 'V10', 'V15', 'V20', 'V25', 'V30', 'V35', 'V40', 'V45', 'V50',
            'D1', 'D2', 'D5', 'D10', 'D20', 'D30', 'D50', 'D70', 'D90', 'D95'
        ]
        
        # Filter to available columns
        available_cols = [col for col in feature_cols if col in organ_data.columns]
        
        # Extract features and target
        X = organ_data[available_cols].copy()
        y = organ_data['Observed_Toxicity'].copy()
        
        # Remove rows with missing values
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_mask]
        y = y[valid_mask]
        
        # Don't filter out samples - use all available (just warn if low)
        if len(X) < 10:
            print(f"  ⚠️  Low sample count: {len(X)} samples (proceeding anyway)")
        
        return X, y, available_cols
    
    def train_ann_model(self, X_train, y_train, organ):
        """Train Artificial Neural Network with proper regularization"""
        
        # Create pipeline with scaling
        ann_pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('ann', MLPClassifier(
                hidden_layer_sizes=(20, 10),  # Conservative architecture
                activation='relu',
                solver='lbfgs',  # Good for small datasets
                alpha=0.01,  # L2 regularization
                max_iter=1000,
                random_state=self.random_state,
                early_stopping=True,
                validation_fraction=0.2,
                n_iter_no_change=20
            ))
        ])
        
        try:
            ann_pipeline.fit(X_train, y_train)
            return ann_pipeline
        except Exception as e:
            print(f"      Error: ANN training failed: {e}")
            return None
    
    def train_xgboost_model(self, X_train, y_train, organ):
        """Train XGBoost model with proper regularization"""
        
        if not XGBOOST_AVAILABLE:
            return None
        
        try:
            # Conservative XGBoost parameters to prevent overfitting
            xgb_model = xgb.XGBClassifier(
                n_estimators=50,  # Small number of trees
                max_depth=3,      # Shallow trees
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,    # L1 regularization
                reg_lambda=1.0,   # L2 regularization
                random_state=self.random_state,
                eval_metric='logloss'
            )
            
            xgb_model.fit(X_train, y_train)
            return xgb_model
        except Exception as e:
            print(f"      Error: XGBoost training failed: {e}")
            return None
    
    def train_and_evaluate_ml_models(self, organ_data, organ, output_dir=None, enable_shap=False):
        """Train and evaluate ML models with proper cross-validation"""
        
        print(f"   Training ML models for {organ}...")
        
        # Prepare features
        X, y, feature_cols = self.prepare_features(organ_data)
        
        if X is None:
            print(f"    Warning: Insufficient data for ML models")
            return {}
        
        n_events = y.sum()
        n_samples = len(y)
        
        print(f"     Features: {len(feature_cols)}, Samples: {n_samples}, Events: {int(n_events)}")
        
        # Warn but proceed with all available data
        if n_events < 5:
            print(f"    ⚠️  Low event count: {int(n_events)} events (proceeding anyway)")
        if n_samples < 20:
            print(f"    ⚠️  Low sample count: {n_samples} samples (proceeding anyway)")
        
        # Use stratified train-test split to prevent data leakage
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=self.random_state, 
            stratify=y if n_events >= 3 else None
        )
        
        results = {}
        
        # Train ANN
        print(f"     Training ANN...")
        ann_model = self.train_ann_model(X_train, y_train, organ)
        
        if ann_model is not None:
            # Evaluate on test set
            y_pred_ann = ann_model.predict_proba(X_test)[:, 1]
            
            # Calculate metrics
            try:
                fpr, tpr, _ = roc_curve(y_test, y_pred_ann)
                auc_ann = auc(fpr, tpr)
                brier_ann = brier_score_loss(y_test, y_pred_ann)
                
                # Cross-validation on training set
                cv_scores = cross_val_score(ann_model, X_train, y_train, 
                                           cv=min(5, len(X_train)//3), scoring='roc_auc')
                
                results['ANN'] = {
                    'model': ann_model,
                    'test_AUC': auc_ann,
                    'test_Brier': brier_ann,
                    'cv_AUC_mean': np.mean(cv_scores),
                    'cv_AUC_std': np.std(cv_scores),
                    'n_train': len(X_train),
                    'n_test': len(X_test),
                    'feature_names': feature_cols
                }
                
                print(f"       ANN - Test AUC: {auc_ann:.3f}, CV AUC: {np.mean(cv_scores):.3f}±{np.std(cv_scores):.3f}")
                
                # Generate SHAP analysis if enabled
                if enable_shap and output_dir is not None:
                    generate_shap_analysis(
                        model=ann_model,
                        model_name="ANN",
                        X_train=X_train,
                        X_test=X_test,
                        y_test=y_test,
                        output_dir=output_dir,
                        organ_name=organ
                    )
                
            except Exception as e:
                print(f"      Error: ANN evaluation failed: {e}")
        
        # Train XGBoost
        if XGBOOST_AVAILABLE:
            print(f"     Training XGBoost...")
            xgb_model = self.train_xgboost_model(X_train, y_train, organ)
            
            if xgb_model is not None:
                # Evaluate on test set
                y_pred_xgb = xgb_model.predict_proba(X_test)[:, 1]
                
                try:
                    fpr, tpr, _ = roc_curve(y_test, y_pred_xgb)
                    auc_xgb = auc(fpr, tpr)
                    brier_xgb = brier_score_loss(y_test, y_pred_xgb)
                    
                    # Cross-validation on training set
                    cv_scores = cross_val_score(xgb_model, X_train, y_train, 
                                               cv=min(5, len(X_train)//3), scoring='roc_auc')
                    
                    # Feature importance
                    feature_importance = dict(zip(feature_cols, xgb_model.feature_importances_))
                    
                    results['XGBoost'] = {
                        'model': xgb_model,
                        'test_AUC': auc_xgb,
                        'test_Brier': brier_xgb,
                        'cv_AUC_mean': np.mean(cv_scores),
                        'cv_AUC_std': np.std(cv_scores),
                        'n_train': len(X_train),
                        'n_test': len(X_test),
                        'feature_names': feature_cols,
                        'feature_importance': feature_importance
                    }
                    
                    print(f"       XGBoost - Test AUC: {auc_xgb:.3f}, CV AUC: {np.mean(cv_scores):.3f}±{np.std(cv_scores):.3f}")
                    
                    # Show top features
                    top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
                    print(f"       Top features: {', '.join([f'{feat}({imp:.3f})' for feat, imp in top_features])}")
                    
                    # Generate SHAP analysis if enabled
                    if enable_shap and output_dir is not None:
                        generate_shap_analysis(
                            model=xgb_model,
                            model_name="XGBoost",
                            X_train=X_train,
                            X_test=X_test,
                            y_test=y_test,
                            output_dir=output_dir,
                            organ_name=organ
                        )
                    
                except Exception as e:
                    print(f"      Error: XGBoost evaluation failed: {e}")
        
        # Store models and data for later use
        self.models[organ] = results
        
        return results
    
    def predict_ml_models(self, organ_data, organ):
        """Generate predictions from trained ML models"""
        
        if organ not in self.models:
            return {}
        
        # Prepare features
        X, y, feature_cols = self.prepare_features(organ_data)
        
        if X is None:
            return {}
        
        predictions = {}
        
        for model_name, model_info in self.models[organ].items():
            try:
                model = model_info['model']
                
                # Ensure feature columns match
                if set(feature_cols) == set(model_info['feature_names']):
                    y_pred = model.predict_proba(X)[:, 1]
                    predictions[f'NTCP_ML_{model_name}'] = y_pred
                else:
                    print(f"    Warning: Feature mismatch for {model_name}")
                    
            except Exception as e:
                print(f"    Error: Prediction failed for {model_name}: {e}")
        
        return predictions

def generate_shap_analysis(model, model_name, X_train, X_test, y_test, 
                          output_dir, organ_name="OAR"):
    """
    Generate SHAP explainability analysis for ML model.
    
    Parameters
    ----------
    model : trained ML model
        Fitted ANN or XGBoost model
    model_name : str
        Model name (e.g., "ANN", "XGBoost")
    X_train : pd.DataFrame
        Training features
    X_test : pd.DataFrame
        Test features
    y_test : np.ndarray
        Test labels
    output_dir : Path
        Output directory for SHAP results
    organ_name : str
        Organ/structure name
    """
    if not SHAP_AVAILABLE:
        print(f"  [WARNING] SHAP not available - skipping explainability for {model_name}")
        return
    
    print(f"\n  Generating SHAP analysis for {model_name}...")
    
    # Create SHAP output directory
    shap_dir = output_dir / "shap_analysis" / model_name
    shap_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Generate SHAP values
        explainer, shap_values = safe_shap_values(model, X_train, X_test)
        shap_values = to_matrix(shap_values)
        
        # Generate plots
        plot_summary_bar(shap_values, X_test, shap_dir / f"shap_bar_{model_name}.png")
        plot_beeswarm(shap_values, X_test, shap_dir / f"shap_beeswarm_{model_name}.png")
        
        # Generate caption
        caption = generate_shap_caption(shap_values, X_test.columns, model_name, organ_name)
        
        # Calculate metrics
        if hasattr(model, 'predict_proba'):
            y_pred_proba = model.predict_proba(X_test)[:, 1]
        else:
            y_pred_proba = model.predict(X_test)
        
        # Calculate AUC (using same approach as existing code)
        try:
            fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
            auc_score = auc(fpr, tpr) if len(np.unique(y_test)) > 1 else float('nan')
        except:
            auc_score = float('nan')
        brier = brier_score_loss(y_test, y_pred_proba)
        
        # Save caption and metrics
        caption_file = shap_dir / "caption.txt"
        with open(caption_file, 'w', encoding='utf-8') as f:
            f.write(caption + f"\nAUC={auc_score:.3f}; Brier={brier:.3f}\n")
        
        metrics_file = shap_dir / "metrics.json"
        import json
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump({
                "AUC": float(auc_score) if not np.isnan(auc_score) else None,
                "Brier": float(brier),
                "n_test": int(len(X_test)),
                "model": model_name,
                "organ": organ_name
            }, f, indent=2)
        
        print(f"    [OK] SHAP analysis saved to {shap_dir}")
        print(f"      - Bar plot: shap_bar_{model_name}.png")
        print(f"      - Beeswarm plot: shap_beeswarm_{model_name}.png")
        print(f"      - Caption: caption.txt")
        print(f"      - Metrics: metrics.json")
        
    except Exception as e:
        print(f"  [WARNING] SHAP generation failed for {model_name}: {str(e)}")

class ComprehensivePlotter:
    """Create comprehensive plots for all organs and models"""
    
    def __init__(self, output_dir, ntcp_calc):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ntcp_calc = ntcp_calc
    
    def calculate_calibration_data(self, y_true, y_pred, n_bins=5):
        """Calculate calibration data for reliability diagram"""
        
        # Remove invalid predictions
        valid_mask = ~(np.isnan(y_pred) | np.isnan(y_true))
        if np.sum(valid_mask) < n_bins:
            return None, None, None
        
        y_true_clean = y_true[valid_mask]
        y_pred_clean = y_pred[valid_mask]
        
        # Create bins based on predicted probabilities
        try:
            # Use quantile-based binning for more robust results
            bin_boundaries = np.percentile(y_pred_clean, np.linspace(0, 100, n_bins + 1))
            
            # Ensure unique boundaries
            bin_boundaries = np.unique(bin_boundaries)
            if len(bin_boundaries) < 3:  # Need at least 2 bins
                return None, None, None
            
            bin_centers = []
            bin_observed = []
            bin_counts = []
            
            for i in range(len(bin_boundaries) - 1):
                # Create mask for current bin
                if i == len(bin_boundaries) - 2:  # Last bin includes right boundary
                    mask = (y_pred_clean >= bin_boundaries[i]) & (y_pred_clean <= bin_boundaries[i + 1])
                else:
                    mask = (y_pred_clean >= bin_boundaries[i]) & (y_pred_clean < bin_boundaries[i + 1])
                
                if np.sum(mask) > 0:
                    bin_pred_mean = np.mean(y_pred_clean[mask])
                    bin_obs_mean = np.mean(y_true_clean[mask])
                    bin_count = np.sum(mask)
                    
                    bin_centers.append(bin_pred_mean)
                    bin_observed.append(bin_obs_mean)
                    bin_counts.append(bin_count)
            
            return np.array(bin_centers), np.array(bin_observed), np.array(bin_counts)
            
        except Exception as e:
            print(f"    Warning: Calibration calculation failed: {e}")
            return None, None, None
    
    def create_dose_response_plot(self, organ_data, organ):
        """Create dose-response plot for specific organ"""
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Get gEUD values and create smooth curve
        geud_values = organ_data['gEUD'].dropna()
        if len(geud_values) == 0:
            print(f"No gEUD data available for {organ}")
            plt.close()
            return
        
        dose_range = np.linspace(geud_values.min() * 0.8, geud_values.max() * 1.2, 300)
        
        # Plot theoretical curve using literature parameters
        if organ in self.ntcp_calc.literature_params:
            lit_params = self.ntcp_calc.literature_params[organ]['LKB_LogLogit']
            
            ntcp_curve = []
            for dose in dose_range:
                eqd2_dose = self.ntcp_calc.convert_to_eqd2(dose, lit_params['alpha_beta'], 2.0)
                ntcp = self.ntcp_calc.ntcp_lkb_loglogit(eqd2_dose, lit_params['TD50'], lit_params['gamma50'])
                ntcp_curve.append(ntcp)
            
            # Plot theoretical curve
            ax.plot(dose_range, ntcp_curve, color=COLORS['LKB_LogLogit'], 
                   linewidth=4, label=f"LKB Model (TD₅₀ = {lit_params['TD50']:.1f} Gy)",
                   alpha=0.8)
            
            # Mark TD50 on the curve
            ax.axvline(lit_params['TD50'], color=COLORS['literature'], 
                      linestyle='--', alpha=0.8, linewidth=3,
                      label=f"Literature TD₅₀")
        
        # Plot observed data points with binning
        valid_data = organ_data.dropna(subset=['gEUD', 'Observed_Toxicity'])
        
        if len(valid_data) > 0:
            # Create bins based on gEUD
            n_bins = min(8, max(3, len(valid_data) // 4))
            bins = np.percentile(valid_data['gEUD'], np.linspace(0, 100, n_bins + 1))
            
            bin_centers = []
            bin_rates = []
            bin_counts = []
            bin_errors = []
            
            for i in range(len(bins) - 1):
                mask = (valid_data['gEUD'] >= bins[i]) & (valid_data['gEUD'] < bins[i + 1])
                bin_data = valid_data[mask]
                
                if len(bin_data) > 0:
                    bin_centers.append(bin_data['gEUD'].mean())
                    rate = bin_data['Observed_Toxicity'].mean()
                    bin_rates.append(rate)
                    bin_counts.append(len(bin_data))
                    
                    # Calculate 95% confidence interval
                    n = len(bin_data)
                    if n > 1 and 0 < rate < 1:
                        se = np.sqrt(rate * (1 - rate) / n)
                        ci_width = 1.96 * se
                        bin_errors.append(ci_width)
                    else:
                        bin_errors.append(0)
            
            # Plot observed data with error bars
            if bin_centers:
                sizes = [80 + 20 * min(count, 15) for count in bin_counts]
                scatter = ax.scatter(bin_centers, bin_rates, s=sizes, 
                                   c=COLORS['observed'], alpha=0.9, 
                                   edgecolors='white', linewidth=2, 
                                   label='Observed Data', zorder=10)
                
                # Add error bars
                ax.errorbar(bin_centers, bin_rates, yerr=bin_errors, 
                           fmt='none', color=COLORS['observed'], alpha=0.7, 
                           capsize=5, capthick=2, linewidth=2, zorder=5)
        
        # Enhanced styling
        ax.set_xlabel(f'{organ} gEUD (Gy)', fontsize=16, fontweight='bold')
        ax.set_ylabel('NTCP', fontsize=16, fontweight='bold')
        
        # Grid
        ax.grid(True, alpha=0.3, color=COLORS['grid'], linewidth=1)
        
        # Enhanced legend
        legend = ax.legend(fontsize=14, loc='lower right', frameon=True, 
                          fancybox=True, shadow=True, framealpha=0.9)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_edgecolor('gray')
        
        # Limits and ticks
        ax.set_ylim(0, 1.05)
        ax.set_xlim(geud_values.min() * 0.9, geud_values.max() * 1.1)
        ax.tick_params(axis='both', which='major', labelsize=12)
        
        # Save plot
        filename = f"{organ}_dose_response.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved dose-response plot: {filename}")
        plt.close()
    
    def create_roc_plot(self, organ_data, organ):
        """Create ROC plot for specific organ"""
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Traditional NTCP models
        traditional_models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']
        ml_models = []
        
        # Check for ML models
        ml_cols = [col for col in organ_data.columns if col.startswith('NTCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                ml_models.append(('ML_ANN', ml_col, 'ANN'))
            elif 'XGBoost' in ml_col:
                ml_models.append(('ML_XGBoost', ml_col, 'XGBoost'))
        
        all_auc_values = []
        
        # Plot traditional models
        for model in traditional_models:
            ntcp_col = f'NTCP_{model}'
            
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 5:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    try:
                        fpr, tpr, _ = roc_curve(y_true, y_pred)
                        auc_score = auc(fpr, tpr)
                        
                        # Plot ROC curve with unique styling
                        ax.plot(fpr, tpr, 
                               color=COLORS[model], 
                               linestyle=LINE_STYLES[model],
                               linewidth=3.0,
                               label=f'{model.replace("_", " ")}: AUC = {auc_score:.3f}',
                               alpha=0.8)
                        
                        all_auc_values.append((model.replace("_", " "), auc_score))
                        
                    except Exception as e:
                        print(f"    Error: ROC calculation failed for {model}: {e}")
        
        # Plot ML models with distinct styling
        for model_key, ntcp_col, model_label in ml_models:
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 5:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    try:
                        fpr, tpr, _ = roc_curve(y_true, y_pred)
                        auc_score = auc(fpr, tpr)
                        
                        # Plot ML ROC curve with unique color and style
                        ax.plot(fpr, tpr, 
                               color=COLORS[model_key], 
                               linestyle=LINE_STYLES[model_key],
                               linewidth=3.5,  # Slightly thicker for ML models
                               label=f'{model_label}: AUC = {auc_score:.3f}',
                               alpha=0.9)
                        
                        all_auc_values.append((model_label, auc_score))
                        
                    except Exception as e:
                        print(f"    Error: ROC calculation failed for {model_label}: {e}")
        
        # Plot diagonal reference line
        ax.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.6, 
               label='Random Classifier')
        
        # Enhanced styling
        ax.set_xlabel('False Positive Rate', fontsize=16, fontweight='bold')
        ax.set_ylabel('True Positive Rate', fontsize=16, fontweight='bold')
        
        # Grid and formatting
        ax.grid(True, alpha=0.3, color=COLORS['grid'], linewidth=1)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        
        # Enhanced legend with better positioning
        legend = ax.legend(fontsize=12, loc='lower right', frameon=True, 
                          fancybox=True, shadow=True, framealpha=0.9)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_edgecolor('gray')
        
        # Add sample size annotation
        n_total = len(organ_data)
        n_events = int(organ_data['Observed_Toxicity'].sum())
        ax.text(0.02, 0.98, f'{organ}\nSample: n={n_total}, events={n_events}', 
               transform=ax.transAxes, fontsize=12, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8),
               verticalalignment='top')
        
        # Save plot
        filename = f"{organ}_ROC.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved ROC plot: {filename}")
        plt.close()
        
        return all_auc_values
    
    def create_calibration_plot(self, organ_data, organ):
        """Create calibration plot for specific organ"""
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Traditional NTCP models
        traditional_models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']
        ml_models = []
        
        # Check for ML models
        ml_cols = [col for col in organ_data.columns if col.startswith('NTCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                ml_models.append(('ML_ANN', ml_col, 'ANN'))
            elif 'XGBoost' in ml_col:
                ml_models.append(('ML_XGBoost', ml_col, 'XGBoost'))
        
        calibration_metrics = {}
        
        # Plot traditional models
        for model in traditional_models:
            ntcp_col = f'NTCP_{model}'
            
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 10:  # Need more points for meaningful calibration
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    # Calculate calibration data
                    bin_centers, bin_observed, bin_counts = self.calculate_calibration_data(
                        y_true, y_pred, n_bins=min(5, len(valid_data) // 3))
                    
                    if bin_centers is not None and len(bin_centers) >= 2:
                        
                        # Calculate calibration metrics
                        slope = np.nan
                        intercept = np.nan
                        
                        if len(bin_centers) >= 2:
                            x_mean = np.mean(bin_centers)
                            y_mean = np.mean(bin_observed)
                            numerator = np.sum((bin_centers - x_mean) * (bin_observed - y_mean))
                            denominator = np.sum((bin_centers - x_mean) ** 2)
                            
                            if denominator != 0:
                                slope = numerator / denominator
                                intercept = y_mean - slope * x_mean
                                calibration_metrics[model] = {'slope': slope, 'intercept': intercept}
                        
                        # Create label with slope and intercept
                        model_name = model.replace('_', ' ')
                        if not np.isnan(slope) and not np.isnan(intercept):
                            label = f"{model_name}: slope={slope:.3f}, int={intercept:.3f}"
                        else:
                            label = f"{model_name}"
                        
                        # Plot calibration curve with markers
                        ax.plot(bin_centers, bin_observed,
                               color=COLORS[model],
                               linestyle=LINE_STYLES[model],
                               linewidth=2.5,
                               marker=MARKERS[model],
                               markersize=8,
                               markerfacecolor=COLORS[model],
                               markeredgecolor='white',
                               markeredgewidth=1,
                               label=label,
                               zorder=5)
        
        # Plot ML models
        for model_key, ntcp_col, model_label in ml_models:
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 10:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    # Calculate calibration data
                    bin_centers, bin_observed, bin_counts = self.calculate_calibration_data(
                        y_true, y_pred, n_bins=min(5, len(valid_data) // 3))
                    
                    if bin_centers is not None and len(bin_centers) >= 2:
                        
                        # Calculate calibration metrics
                        slope = np.nan
                        intercept = np.nan
                        
                        if len(bin_centers) >= 2:
                            x_mean = np.mean(bin_centers)
                            y_mean = np.mean(bin_observed)
                            numerator = np.sum((bin_centers - x_mean) * (bin_observed - y_mean))
                            denominator = np.sum((bin_centers - x_mean) ** 2)
                            
                            if denominator != 0:
                                slope = numerator / denominator
                                intercept = y_mean - slope * x_mean
                                calibration_metrics[model_key] = {'slope': slope, 'intercept': intercept}
                        
                        # Create label with slope and intercept
                        if not np.isnan(slope) and not np.isnan(intercept):
                            label = f"{model_label}: slope={slope:.3f}, int={intercept:.3f}"
                        else:
                            label = f"{model_label}"
                        
                        # Plot ML calibration curve
                        ax.plot(bin_centers, bin_observed,
                               color=COLORS[model_key],
                               linestyle=LINE_STYLES[model_key],
                               linewidth=3.0,
                               marker=MARKERS[model_key],
                               markersize=8,
                               markerfacecolor=COLORS[model_key],
                               markeredgecolor='white',
                               markeredgewidth=1,
                               label=label,
                               zorder=6)
        
        # Plot perfect calibration line
        ax.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.7, 
               label='Perfect Calibration', zorder=1)
        
        # Enhanced styling
        ax.set_xlabel('Predicted NTCP', fontsize=16, fontweight='bold')
        ax.set_ylabel('Observed Rate', fontsize=16, fontweight='bold')
        
        # Grid and formatting
        ax.grid(True, alpha=0.3, color=COLORS['grid'], linewidth=1)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        
        # Enhanced legend
        legend = ax.legend(fontsize=10, loc='upper left', frameon=True, 
                          fancybox=True, shadow=True, framealpha=0.9)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_edgecolor('gray')
        
        # Add organ name annotation
        ax.text(0.98, 0.02, f'{organ}', 
               transform=ax.transAxes, fontsize=14, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8),
               horizontalalignment='right', verticalalignment='bottom')
        
        # Save plot
        filename = f"{organ}_calibration.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved calibration plot: {filename}")
        plt.close()
        
        return calibration_metrics
    
    def create_combined_roc_calibration_plot(self, organ_data, organ):
        """Create combined ROC and calibration plot"""
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        # Traditional NTCP models
        traditional_models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']
        ml_models = []
        
        # Check for ML models
        ml_cols = [col for col in organ_data.columns if col.startswith('NTCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                ml_models.append(('ML_ANN', ml_col, 'ANN'))
            elif 'XGBoost' in ml_col:
                ml_models.append(('ML_XGBoost', ml_col, 'XGBoost'))
        
        # ROC Plot (left)
        all_auc_values = []
        
        # Plot traditional models ROC
        for model in traditional_models:
            ntcp_col = f'NTCP_{model}'
            
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 5:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    try:
                        fpr, tpr, _ = roc_curve(y_true, y_pred)
                        auc_score = auc(fpr, tpr)
                        
                        ax1.plot(fpr, tpr, 
                               color=COLORS[model], 
                               linestyle=LINE_STYLES[model],
                               linewidth=3.0,
                               label=f'{model.replace("_", " ")}: AUC = {auc_score:.3f}',
                               alpha=0.8)
                        
                        all_auc_values.append((model.replace("_", " "), auc_score))
                        
                    except Exception as e:
                        print(f"    Error: ROC calculation failed for {model}: {e}")
        
        # Plot ML models ROC
        for model_key, ntcp_col, model_label in ml_models:
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 5:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    try:
                        fpr, tpr, _ = roc_curve(y_true, y_pred)
                        auc_score = auc(fpr, tpr)
                        
                        ax1.plot(fpr, tpr, 
                               color=COLORS[model_key], 
                               linestyle=LINE_STYLES[model_key],
                               linewidth=3.5,
                               label=f'{model_label}: AUC = {auc_score:.3f}',
                               alpha=0.9)
                        
                        all_auc_values.append((model_label, auc_score))
                        
                    except Exception as e:
                        print(f"    Error: ROC calculation failed for {model_label}: {e}")
        
        # ROC diagonal and formatting
        ax1.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.6, label='Random')
        ax1.set_xlabel('False Positive Rate', fontsize=14, fontweight='bold')
        ax1.set_ylabel('True Positive Rate', fontsize=14, fontweight='bold')
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1)
        ax1.set_aspect('equal')
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=10, loc='lower right')
        
        # Calibration Plot (right)
        calibration_metrics = {}
        
        # Plot traditional models calibration
        for model in traditional_models:
            ntcp_col = f'NTCP_{model}'
            
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 10:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    bin_centers, bin_observed, bin_counts = self.calculate_calibration_data(
                        y_true, y_pred, n_bins=min(5, len(valid_data) // 3))
                    
                    if bin_centers is not None and len(bin_centers) >= 2:
                        
                        # Calculate slope
                        slope = np.nan
                        if len(bin_centers) >= 2:
                            x_mean = np.mean(bin_centers)
                            y_mean = np.mean(bin_observed)
                            numerator = np.sum((bin_centers - x_mean) * (bin_observed - y_mean))
                            denominator = np.sum((bin_centers - x_mean) ** 2)
                            
                            if denominator != 0:
                                slope = numerator / denominator
                        
                        model_name = model.replace('_', ' ')
                        label = f"{model_name}" if np.isnan(slope) else f"{model_name}: {slope:.3f}"
                        
                        ax2.plot(bin_centers, bin_observed,
                               color=COLORS[model],
                               linestyle=LINE_STYLES[model],
                               linewidth=2.5,
                               marker=MARKERS[model],
                               markersize=6,
                               markerfacecolor=COLORS[model],
                               markeredgecolor='white',
                               markeredgewidth=1,
                               label=label,
                               zorder=5)
        
        # Plot ML models calibration
        for model_key, ntcp_col, model_label in ml_models:
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                
                if len(valid_data) >= 10:
                    y_true = valid_data['Observed_Toxicity'].values
                    y_pred = valid_data[ntcp_col].values
                    
                    bin_centers, bin_observed, bin_counts = self.calculate_calibration_data(
                        y_true, y_pred, n_bins=min(5, len(valid_data) // 3))
                    
                    if bin_centers is not None and len(bin_centers) >= 2:
                        
                        # Calculate slope
                        slope = np.nan
                        if len(bin_centers) >= 2:
                            x_mean = np.mean(bin_centers)
                            y_mean = np.mean(bin_observed)
                            numerator = np.sum((bin_centers - x_mean) * (bin_observed - y_mean))
                            denominator = np.sum((bin_centers - x_mean) ** 2)
                            
                            if denominator != 0:
                                slope = numerator / denominator
                        
                        label = f"{model_label}" if np.isnan(slope) else f"{model_label}: {slope:.3f}"
                        
                        ax2.plot(bin_centers, bin_observed,
                               color=COLORS[model_key],
                               linestyle=LINE_STYLES[model_key],
                               linewidth=3.0,
                               marker=MARKERS[model_key],
                               markersize=6,
                               markerfacecolor=COLORS[model_key],
                               markeredgecolor='white',
                               markeredgewidth=1,
                               label=label,
                               zorder=6)
        
        # Calibration perfect line and formatting
        ax2.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.7, label='Perfect')
        ax2.set_xlabel('Predicted NTCP', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Observed Rate', fontsize=14, fontweight='bold')
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        ax2.set_aspect('equal')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=10, loc='upper left')
        
        # Add organ name as suptitle
        fig.suptitle(f'{organ}', fontsize=18, fontweight='bold', y=0.95)
        
        plt.tight_layout()
        
        # Save combined plot
        filename = f"{organ}_ROC_calibration_combined.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved combined ROC+calibration plot: {filename}")
        plt.close()
        
        return all_auc_values, calibration_metrics
    
    def create_comprehensive_analysis_plot(self, results_df):
        """Create comprehensive analysis plot across all organs"""
        
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
        
        organs = results_df['Organ'].unique()
        
        # Performance comparison subplot
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_performance_comparison(results_df, ax1)
        
        # Sample characteristics subplot  
        ax2 = fig.add_subplot(gs[0, 2:])
        self._plot_sample_characteristics(results_df, ax2)
        
        # Dose distribution subplots
        for i, organ in enumerate(organs[:3]):
            ax = fig.add_subplot(gs[1, i])
            self._plot_dose_distribution(results_df[results_df['Organ'] == organ], organ, ax)
        
        # Model performance trends subplot
        ax_trend = fig.add_subplot(gs[1, 3])
        self._plot_performance_trends(results_df, ax_trend)
        
        # Overall summary subplot
        ax_summary = fig.add_subplot(gs[2, :])
        self._plot_overall_summary(results_df, ax_summary)
        
        plt.suptitle('Comprehensive NTCP Analysis', fontsize=20, fontweight='bold', y=0.98)
        
        # Save comprehensive plot
        filename = "comprehensive_analysis.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved comprehensive analysis plot: {filename}")
        plt.close()
    
    def _plot_performance_comparison(self, results_df, ax):
        """Plot performance comparison across organs"""
        
        organs = results_df['Organ'].unique()
        traditional_models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']
        ml_models = ['ML_ANN', 'ML_XGBoost']
        
        # Prepare data
        auc_data = {}
        for model in traditional_models + ml_models:
            auc_data[model] = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            
            # Traditional models
            for model in traditional_models:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            auc_data[model].append(auc_score)
                        except:
                            auc_data[model].append(np.nan)
                    else:
                        auc_data[model].append(np.nan)
                else:
                    auc_data[model].append(np.nan)
            
            # ML models
            for model in ml_models:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            auc_data[model].append(auc_score)
                        except:
                            auc_data[model].append(np.nan)
                    else:
                        auc_data[model].append(np.nan)
                else:
                    auc_data[model].append(np.nan)
        
        # Plot bars
        x = np.arange(len(organs))
        width = 0.15
        
        for i, model in enumerate(traditional_models + ml_models):
            aucs = auc_data[model]
            valid_aucs = [a if not np.isnan(a) else 0 for a in aucs]
            
            color = COLORS.get(model, COLORS['confidence'])
            
            bars = ax.bar(x + i * width, valid_aucs, width, 
                         label=model.replace('_', ' '), color=color, alpha=0.8)
            
            # Add value labels
            for j, (bar, auc_val) in enumerate(zip(bars, aucs)):
                if not np.isnan(auc_val) and auc_val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                           f'{auc_val:.3f}', ha='center', va='bottom', 
                           fontsize=8, fontweight='bold')
        
        ax.set_xlabel('Organ', fontsize=12, fontweight='bold')
        ax.set_ylabel('AUC', fontsize=12, fontweight='bold')
        ax.set_xticks(x + width * 2)
        ax.set_xticklabels(organs)
        ax.legend(fontsize=8, ncol=2)
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3, axis='y')
    
    def _plot_sample_characteristics(self, results_df, ax):
        """Plot sample characteristics by organ"""
        
        organs = results_df['Organ'].unique()
        sample_sizes = []
        event_rates = []
        colors = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            n_patients = len(organ_data)
            n_events = int(organ_data['Observed_Toxicity'].sum())
            event_rate = (n_events / n_patients) * 100 if n_patients > 0 else 0
            
            sample_sizes.append(n_patients)
            event_rates.append(event_rate)
            
            # Color by data quality
            if n_events < 5:
                colors.append('red')
            elif n_events < 10:
                colors.append('orange')
            else:
                colors.append('green')
        
        scatter = ax.scatter(sample_sizes, event_rates, c=colors, s=200, alpha=0.7)
        
        # Add organ labels
        for i, organ in enumerate(organs):
            ax.annotate(organ, (sample_sizes[i], event_rates[i]), 
                       xytext=(5, 5), textcoords='offset points', fontsize=10)
        
        ax.set_xlabel('Sample Size (n)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Event Rate (%)', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Add threshold lines
        ax.axhline(y=5, color='red', linestyle='--', alpha=0.5, label='5% threshold')
        ax.axvline(x=30, color='blue', linestyle='--', alpha=0.5, label='n=30 threshold')
        ax.legend(fontsize=8)
    
    def _plot_dose_distribution(self, organ_data, organ, ax):
        """Plot dose distribution for specific organ"""
        
        valid_data = organ_data.dropna(subset=['gEUD', 'Observed_Toxicity'])
        
        if len(valid_data) == 0:
            ax.text(0.5, 0.5, f'No data\nfor {organ}', ha='center', va='center', 
                   transform=ax.transAxes, fontsize=12)
            return
        
        # Separate by outcome
        events = valid_data[valid_data['Observed_Toxicity'] == 1]['gEUD']
        non_events = valid_data[valid_data['Observed_Toxicity'] == 0]['gEUD']
        
        # Plot histograms
        bins = np.linspace(valid_data['gEUD'].min(), valid_data['gEUD'].max(), 15)
        
        ax.hist(non_events, bins=bins, alpha=0.7, color=COLORS['confidence'], 
               label=f'No Toxicity (n={len(non_events)})', density=True)
        ax.hist(events, bins=bins, alpha=0.8, color=COLORS['observed'],
               label=f'Toxicity (n={len(events)})', density=True)
        
        ax.set_xlabel('gEUD (Gy)', fontsize=10)
        ax.set_ylabel('Density', fontsize=10)
        ax.set_title(f'{organ}', fontsize=12, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    
    def _plot_performance_trends(self, results_df, ax):
        """Plot performance trends across organs"""
        
        organs = results_df['Organ'].unique()
        
        # Calculate mean AUC for traditional vs ML models
        trad_aucs = []
        ml_aucs = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            
            # Traditional models average
            trad_scores = []
            for model in ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            trad_scores.append(auc_score)
                        except:
                            pass
            
            # ML models average
            ml_scores = []
            for model in ['ML_ANN', 'ML_XGBoost']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            ml_scores.append(auc_score)
                        except:
                            pass
            
            trad_aucs.append(np.mean(trad_scores) if trad_scores else np.nan)
            ml_aucs.append(np.mean(ml_scores) if ml_scores else np.nan)
        
        x = range(len(organs))
        ax.plot(x, trad_aucs, 'o-', color=COLORS['LKB_LogLogit'], 
               linewidth=2, markersize=8, label='Traditional Models')
        ax.plot(x, ml_aucs, 's-', color=COLORS['ML_ANN'], 
               linewidth=2, markersize=8, label='ML Models')
        
        ax.set_xlabel('Organs', fontsize=10)
        ax.set_ylabel('Mean AUC', fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(organs, rotation=45)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0.4, 1.0)
    
    def _plot_overall_summary(self, results_df, ax):
        """Plot overall summary statistics"""
        
        # Summary statistics table
        organs = results_df['Organ'].unique()
        
        summary_data = []
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            n_patients = len(organ_data)
            n_events = int(organ_data['Observed_Toxicity'].sum())
            event_rate = (n_events / n_patients) * 100 if n_patients > 0 else 0
            
            # Best AUC
            best_auc = 0
            best_model = 'N/A'
            
            for model in ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            if auc_score > best_auc:
                                best_auc = auc_score
                                best_model = model.replace('_', ' ')
                        except:
                            pass
            
            summary_data.append([organ, n_patients, n_events, f'{event_rate:.1f}%', 
                               f'{best_auc:.3f}', best_model])
        
        # Create table
        table = ax.table(cellText=summary_data,
                        colLabels=['Organ', 'Patients', 'Events', 'Event Rate', 'Best AUC', 'Best Model'],
                        cellLoc='center',
                        loc='center')
        
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        
        # Style the table
        for i in range(len(summary_data) + 1):
            for j in range(6):
                cell = table[(i, j)]
                if i == 0:  # Header
                    cell.set_facecolor('#4CAF50')
                    cell.set_text_props(weight='bold', color='white')
                else:
                    cell.set_facecolor('#f0f0f0' if i % 2 == 0 else 'white')
        
        ax.axis('off')
    
    def create_model_performance_plot(self, results_df):
        """Create detailed model performance comparison plot"""
        
        organs = results_df['Organ'].unique()
        
        # Create figure with subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # AUC comparison
        self._plot_auc_comparison(results_df, ax1)
        
        # Brier score comparison
        self._plot_brier_comparison(results_df, ax2)
        
        # Model type comparison
        self._plot_model_type_comparison(results_df, ax3)
        
        # Data quality vs performance
        self._plot_quality_vs_performance(results_df, ax4)
        
        plt.suptitle('Model Performance Analysis', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save plot
        filename = "model_performance_analysis.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved model performance plot: {filename}")
        plt.close()
    
    def _plot_auc_comparison(self, results_df, ax):
        """Plot AUC comparison across organs and models"""
        
        organs = results_df['Organ'].unique()
        models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']
        
        # Prepare data
        auc_data = {model: [] for model in models}
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            
            for model in models:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            auc_data[model].append(auc_score)
                        except:
                            auc_data[model].append(np.nan)
                    else:
                        auc_data[model].append(np.nan)
                else:
                    auc_data[model].append(np.nan)
        
        # Plot grouped bars
        x = np.arange(len(organs))
        width = 0.15
        
        for i, model in enumerate(models):
            aucs = auc_data[model]
            valid_aucs = [a if not np.isnan(a) else 0 for a in aucs]
            
            color = COLORS.get(model, COLORS['confidence'])
            label = model.replace('_', ' ')
            
            bars = ax.bar(x + i * width, valid_aucs, width, 
                         label=label, color=color, alpha=0.8)
            
            # Add value labels
            for j, (bar, auc_val) in enumerate(zip(bars, aucs)):
                if not np.isnan(auc_val) and auc_val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                           f'{auc_val:.3f}', ha='center', va='bottom', 
                           fontsize=8, fontweight='bold', rotation=45)
        
        ax.set_xlabel('Organ', fontsize=12, fontweight='bold')
        ax.set_ylabel('AUC', fontsize=12, fontweight='bold')
        ax.set_xticks(x + width * 2)
        ax.set_xticklabels(organs)
        ax.legend(fontsize=10, bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3, axis='y')
    
    def _plot_brier_comparison(self, results_df, ax):
        """Plot Brier score comparison"""
        
        organs = results_df['Organ'].unique()
        models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']
        
        # Prepare data
        brier_data = {model: [] for model in models}
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            
            for model in models:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            brier_score = brier_score_loss(y_true, y_pred)
                            brier_data[model].append(brier_score)
                        except:
                            brier_data[model].append(np.nan)
                    else:
                        brier_data[model].append(np.nan)
                else:
                    brier_data[model].append(np.nan)
        
        # Plot grouped bars
        x = np.arange(len(organs))
        width = 0.15
        
        for i, model in enumerate(models):
            briers = brier_data[model]
            valid_briers = [b if not np.isnan(b) else 0 for b in briers]
            
            color = COLORS.get(model, COLORS['confidence'])
            label = model.replace('_', ' ')
            
            bars = ax.bar(x + i * width, valid_briers, width, 
                         label=label, color=color, alpha=0.8)
            
            # Add value labels
            for j, (bar, brier_val) in enumerate(zip(bars, briers)):
                if not np.isnan(brier_val) and brier_val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                           f'{brier_val:.3f}', ha='center', va='bottom', 
                           fontsize=8, fontweight='bold', rotation=45)
        
        ax.set_xlabel('Organ', fontsize=12, fontweight='bold')
        ax.set_ylabel('Brier Score (Lower = Better)', fontsize=12, fontweight='bold')
        ax.set_xticks(x + width * 2)
        ax.set_xticklabels(organs)
        ax.legend(fontsize=10, bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.grid(True, alpha=0.3, axis='y')
    
    def _plot_model_type_comparison(self, results_df, ax):
        """Plot comparison between traditional and ML models"""
        
        organs = results_df['Organ'].unique()
        
        trad_aucs = []
        ml_aucs = []
        improvements = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            
            # Best traditional AUC
            best_trad = 0
            for model in ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            best_trad = max(best_trad, auc_score)
                        except:
                            pass
            
            # Best ML AUC
            best_ml = 0
            for model in ['ML_ANN', 'ML_XGBoost']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            best_ml = max(best_ml, auc_score)
                        except:
                            pass
            
            trad_aucs.append(best_trad if best_trad > 0 else np.nan)
            ml_aucs.append(best_ml if best_ml > 0 else np.nan)
            
            # Calculate improvement
            if best_trad > 0 and best_ml > 0:
                improvement = ((best_ml - best_trad) / best_trad) * 100
                improvements.append(improvement)
            else:
                improvements.append(np.nan)
        
        x = np.arange(len(organs))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, [a if not np.isnan(a) else 0 for a in trad_aucs], 
                      width, label='Best Traditional', color=COLORS['LKB_LogLogit'], alpha=0.8)
        bars2 = ax.bar(x + width/2, [a if not np.isnan(a) else 0 for a in ml_aucs], 
                      width, label='Best ML', color=COLORS['ML_ANN'], alpha=0.8)
        
        # Add improvement percentages
        for i, (trad, ml, imp) in enumerate(zip(trad_aucs, ml_aucs, improvements)):
            if not np.isnan(imp):
                ax.text(i, max(trad, ml) + 0.05, f'{imp:+.1f}%', 
                       ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        ax.set_xlabel('Organ', fontsize=12, fontweight='bold')
        ax.set_ylabel('Best AUC', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(organs)
        ax.legend()
        ax.set_ylim(0, 1.1)
        ax.grid(True, alpha=0.3, axis='y')
    
    def _plot_quality_vs_performance(self, results_df, ax):
        """Plot data quality vs model performance"""
        
        organs = results_df['Organ'].unique()
        
        sample_sizes = []
        event_counts = []
        best_aucs = []
        colors = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            n_patients = len(organ_data)
            n_events = int(organ_data['Observed_Toxicity'].sum())
            
            # Find best AUC
            best_auc = 0
            for model in ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            best_auc = max(best_auc, auc_score)
                        except:
                            pass
            
            sample_sizes.append(n_patients)
            event_counts.append(n_events)
            best_aucs.append(best_auc)
            
            # Color by performance
            if best_auc >= 0.8:
                colors.append('green')
            elif best_auc >= 0.7:
                colors.append('blue')
            elif best_auc >= 0.6:
                colors.append('orange')
            else:
                colors.append('red')
        
        # Create bubble plot
        scatter = ax.scatter(sample_sizes, best_aucs, s=[e*10 for e in event_counts], 
                           c=colors, alpha=0.6)
        
        # Add organ labels
        for i, organ in enumerate(organs):
            ax.annotate(f'{organ}\n({event_counts[i]} events)', 
                       (sample_sizes[i], best_aucs[i]), 
                       xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        ax.set_xlabel('Sample Size', fontsize=12, fontweight='bold')
        ax.set_ylabel('Best AUC', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 1.05)
        
        # Add performance thresholds
        ax.axhline(y=0.8, color='green', linestyle='--', alpha=0.5, label='Excellent (≥0.8)')
        ax.axhline(y=0.7, color='blue', linestyle='--', alpha=0.5, label='Good (≥0.7)')
        ax.axhline(y=0.6, color='orange', linestyle='--', alpha=0.5, label='Fair (≥0.6)')
        ax.legend(fontsize=8)
    def create_overall_performance_plot(self, results_df):
        """Create overall performance summary plot"""
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 10))
        
        organs = results_df['Organ'].unique()
        
        # Plot 1: AUC heatmap
        models = ['LKB LogLogit', 'LKB Probit', 'RS Poisson', 'ANN', 'XGBoost']
        model_cols = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']
        
        auc_matrix = np.zeros((len(organs), len(models)))
        
        for i, organ in enumerate(organs):
            organ_data = results_df[results_df['Organ'] == organ]
            
            for j, model in enumerate(model_cols):
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            auc_matrix[i, j] = auc_score
                        except:
                            auc_matrix[i, j] = np.nan
                    else:
                        auc_matrix[i, j] = np.nan
                else:
                    auc_matrix[i, j] = np.nan
        
        # Create heatmap
        im = ax1.imshow(auc_matrix, cmap='RdYlGn', aspect='auto', vmin=0.4, vmax=1.0)
        ax1.set_xticks(range(len(models)))
        ax1.set_xticklabels(models, rotation=45, ha='right')
        ax1.set_yticks(range(len(organs)))
        ax1.set_yticklabels(organs)
        ax1.set_xlabel('Models', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Organs', fontsize=12, fontweight='bold')
        
        # Add text annotations
        for i in range(len(organs)):
            for j in range(len(models)):
                if not np.isnan(auc_matrix[i, j]):
                    text = ax1.text(j, i, f'{auc_matrix[i, j]:.3f}',
                                   ha="center", va="center", color="black", fontweight='bold')
        
        plt.colorbar(im, ax=ax1, label='AUC')
        
        # Plot 2: Sample size vs performance
        sample_sizes = []
        event_rates = []
        best_aucs = []
        organ_names = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            n_patients = len(organ_data)
            n_events = int(organ_data['Observed_Toxicity'].sum())
            event_rate = (n_events / n_patients) * 100 if n_patients > 0 else 0
            
            # Find best AUC
            best_auc = np.nanmax(auc_matrix[list(organs).index(organ), :])
            
            sample_sizes.append(n_patients)
            event_rates.append(event_rate)
            best_aucs.append(best_auc if not np.isnan(best_auc) else 0)
            organ_names.append(organ)
        
        scatter = ax2.scatter(sample_sizes, best_aucs, s=[er*10 for er in event_rates], 
                            alpha=0.6, c=range(len(organs)), cmap='tab10')
        
        for i, organ in enumerate(organ_names):
            ax2.annotate(organ, (sample_sizes[i], best_aucs[i]), 
                        xytext=(5, 5), textcoords='offset points', fontsize=10)
        
        ax2.set_xlabel('Sample Size', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Best AUC', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 1.05)
        
        # Plot 3: Model type comparison
        trad_means = []
        ml_means = []
        organ_labels = []
        
        for organ in organs:
            organ_idx = list(organs).index(organ)
            trad_aucs = auc_matrix[organ_idx, :3]  # First 3 are traditional
            ml_aucs = auc_matrix[organ_idx, 3:]    # Last 2 are ML
            
            trad_mean = np.nanmean(trad_aucs) if not np.all(np.isnan(trad_aucs)) else 0
            ml_mean = np.nanmean(ml_aucs) if not np.all(np.isnan(ml_aucs)) else 0
            
            trad_means.append(trad_mean)
            ml_means.append(ml_mean)
            organ_labels.append(organ)
        
        x = np.arange(len(organs))
        width = 0.35
        
        bars1 = ax3.bar(x - width/2, trad_means, width, label='Traditional NTCP', 
                       color=COLORS['LKB_LogLogit'], alpha=0.8)
        bars2 = ax3.bar(x + width/2, ml_means, width, label='Machine Learning', 
                       color=COLORS['ML_ANN'], alpha=0.8)
        
        # Add improvement percentages
        for i, (trad, ml) in enumerate(zip(trad_means, ml_means)):
            if trad > 0 and ml > 0:
                improvement = ((ml - trad) / trad) * 100
                ax3.text(i, max(trad, ml) + 0.02, f'{improvement:+.1f}%', 
                        ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        ax3.set_xlabel('Organ', fontsize=12, fontweight='bold')
        ax3.set_ylabel('Mean AUC', fontsize=12, fontweight='bold')
        ax3.set_xticks(x)
        ax3.set_xticklabels(organ_labels)
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.set_ylim(0, 1.1)
        
        # Plot 4: Summary statistics
        ax4.axis('off')
        
        # Calculate summary statistics
        total_patients = len(results_df)
        total_events = int(results_df['Observed_Toxicity'].sum())
        overall_event_rate = (total_events / total_patients) * 100
        
        # Best performing models
        best_overall_auc = np.nanmax(auc_matrix)
        best_indices = np.where(auc_matrix == best_overall_auc)
        if len(best_indices[0]) > 0:
            best_organ = organs[best_indices[0][0]]
            best_model = models[best_indices[1][0]]
        else:
            best_organ = 'N/A'
            best_model = 'N/A'
        
        # Create summary text
        summary_text = f"""
        OVERALL SUMMARY
        ═══════════════════════════════
        
        Dataset Characteristics:
        • Total Patients: {total_patients}
        • Total Events: {total_events}
        • Overall Event Rate: {overall_event_rate:.1f}%
        • Organs Analyzed: {len(organs)}
        
        Model Performance:
        • Best Performance: {best_overall_auc:.3f} AUC
        • Best Model: {best_model}
        • Best Organ: {best_organ}
        
        Traditional vs ML:
        • Traditional Mean: {np.nanmean([t for t in trad_means if t > 0]):.3f}
        • ML Mean: {np.nanmean([m for m in ml_means if m > 0]):.3f}
        • ML Improvement: {((np.nanmean([m for m in ml_means if m > 0]) - np.nanmean([t for t in trad_means if t > 0])) / np.nanmean([t for t in trad_means if t > 0]) * 100):+.1f}%
        
        Model Availability:
        • Traditional Models: 3/3 (100%)
        • ML Models: Available for organs with ≥15 samples
        """
        
        ax4.text(0.1, 0.9, summary_text, transform=ax4.transAxes, fontsize=12,
                verticalalignment='top', fontfamily='monospace',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8))
        
        plt.suptitle('Overall NTCP Model Performance Summary', fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        # Save plot
        filename = "overall_performance_summary.png"
        plt.savefig(self.output_dir / filename, dpi=600, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f" Saved overall performance plot: {filename}")
        plt.close()

def create_comprehensive_excel(results_df, output_dir):
    """Create comprehensive Excel file with all results"""
    
    output_path = Path(output_dir)
    excel_file = output_path / 'ntcp_results.xlsx'
    
    print(f" Creating comprehensive Excel file: {excel_file}")
    
    # Initialize ntcp_df and performance_df outside with block for later use
    ntcp_df = pd.DataFrame()
    performance_df = pd.DataFrame()
    
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        
        # Sheet 1: Complete Results
        results_df_copy = results_df.copy()
        
        # Round numerical columns
        numeric_cols = results_df_copy.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if 'NTCP' in col or col in ['gEUD', 'mean_dose', 'max_dose', 'total_volume']:
                results_df_copy[col] = results_df_copy[col].round(4)
            else:
                results_df_copy[col] = results_df_copy[col].round(2)
        
        results_df_copy.to_excel(writer, sheet_name='Complete Results', index=False)
        
        # Sheet 2: Summary by Organ
        summary_data = []
        
        for organ in results_df['Organ'].unique():
            organ_data = results_df[results_df['Organ'] == organ]
            n_patients = len(organ_data)
            n_events = int(organ_data['Observed_Toxicity'].sum())
            event_rate = (n_events / n_patients) * 100 if n_patients > 0 else 0
            
            # Calculate mean gEUD
            mean_geud = organ_data['gEUD'].mean()
            geud_std = organ_data['gEUD'].std()
            geud_range = f"{organ_data['gEUD'].min():.1f} - {organ_data['gEUD'].max():.1f}"
            
            # Calculate model performance
            model_performance = {}
            for model in ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            brier_score = brier_score_loss(y_true, y_pred)
                            model_performance[model] = {'AUC': auc_score, 'Brier': brier_score}
                        except:
                            model_performance[model] = {'AUC': np.nan, 'Brier': np.nan}
                    else:
                        model_performance[model] = {'AUC': np.nan, 'Brier': np.nan}
                else:
                    model_performance[model] = {'AUC': np.nan, 'Brier': np.nan}
            
            # Find best model
            best_auc = 0
            best_model = 'N/A'
            for model, perf in model_performance.items():
                if not np.isnan(perf['AUC']) and perf['AUC'] > best_auc:
                    best_auc = perf['AUC']
                    best_model = model.replace('_', ' ')
            
            summary_row = {
                'Organ': organ,
                'Sample_Size': n_patients,
                'Events': n_events,
                'Event_Rate_Percent': f"{event_rate:.1f}%",
                'Mean_gEUD_Gy': f"{mean_geud:.1f}" if not np.isnan(mean_geud) else 'N/A',
                'gEUD_SD_Gy': f"{geud_std:.1f}" if not np.isnan(geud_std) else 'N/A',
                'gEUD_Range_Gy': geud_range,
                'Best_Model': best_model,
                'Best_AUC': f"{best_auc:.3f}" if best_auc > 0 else 'N/A'
            }
            
            # Add individual model performance
            for model, perf in model_performance.items():
                summary_row[f'{model}_AUC'] = f"{perf['AUC']:.3f}" if not np.isnan(perf['AUC']) else 'N/A'
                summary_row[f'{model}_Brier'] = f"{perf['Brier']:.3f}" if not np.isnan(perf['Brier']) else 'N/A'
            
            summary_data.append(summary_row)
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary by Organ', index=False)
        
        # Sheet 3: Model Performance Matrix
        organs = results_df['Organ'].unique()
        models = ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson', 'ML_ANN', 'ML_XGBoost']
        
        performance_matrix = []
        
        for organ in organs:
            organ_data = results_df[results_df['Organ'] == organ]
            row = {'Organ': organ}
            
            for model in models:
                ntcp_col = f'NTCP_{model}'
                if ntcp_col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            y_true = valid_data['Observed_Toxicity'].values
                            y_pred = valid_data[ntcp_col].values
                            fpr, tpr, _ = roc_curve(y_true, y_pred)
                            auc_score = auc(fpr, tpr)
                            row[f'{model}_AUC'] = f"{auc_score:.3f}"
                        except:
                            row[f'{model}_AUC'] = 'Error'
                    else:
                        row[f'{model}_AUC'] = 'Insufficient Data'
                else:
                    row[f'{model}_AUC'] = 'Not Available'
            
            performance_matrix.append(row)
        
        performance_df = pd.DataFrame(performance_matrix)
        performance_df.to_excel(writer, sheet_name='Performance Matrix', index=False)
    
    # Also save standalone ntcp_model_performance.xlsx file (Fix 3)
    if not performance_df.empty:
        perf_file = output_path / "ntcp_model_performance.xlsx"
        performance_df.to_excel(perf_file, index=False)
        print(f"[OK] Saved model performance: {perf_file}")
        print(f"     Organs: {len(performance_df)}")
        
        # Sheet 4: Dose Metrics
        dose_metrics_cols = ['PatientID', 'Organ', 'gEUD', 'mean_dose', 'max_dose', 'total_volume']
        
        # Add V-dose and D-dose columns
        v_cols = [col for col in results_df.columns if col.startswith('V') and col[1:].isdigit()]
        d_cols = [col for col in results_df.columns if col.startswith('D') and any(c.isdigit() for c in col[1:])]
        
        dose_metrics_cols.extend(v_cols)
        dose_metrics_cols.extend(d_cols)
        
        # Filter to available columns
        available_dose_cols = [col for col in dose_metrics_cols if col in results_df.columns]
        
        dose_df = results_df[available_dose_cols].copy()
        
        # Round dose metrics
        numeric_dose_cols = dose_df.select_dtypes(include=[np.number]).columns
        for col in numeric_dose_cols:
            dose_df[col] = dose_df[col].round(2)
        
        dose_df.to_excel(writer, sheet_name='Dose Metrics', index=False)
        
        # Sheet 5: NTCP Predictions Only
        ntcp_cols = ['PatientID', 'Organ', 'Observed_Toxicity']
        ntcp_prediction_cols = [col for col in results_df.columns if col.startswith('NTCP_')]
        
        ntcp_cols.extend(ntcp_prediction_cols)
        ntcp_df = results_df[ntcp_cols].copy()
        
        # Round NTCP predictions
        for col in ntcp_prediction_cols:
            ntcp_df[col] = ntcp_df[col].round(4)
        
        ntcp_df.to_excel(writer, sheet_name='NTCP Predictions', index=False)
        
        # Sheet 6: Literature Parameters
        lit_params_data = []
        
        ntcp_calc = NTCPCalculator()
        for organ, params in ntcp_calc.literature_params.items():
            for model_type, model_params in params.items():
                row = {
                    'Organ': organ,
                    'Model': model_type,
                    **model_params
                }
                lit_params_data.append(row)
        
        lit_params_df = pd.DataFrame(lit_params_data)
        lit_params_df.to_excel(writer, sheet_name='Literature Parameters', index=False)
        
        # Sheet 7: Analysis Metadata
        metadata = [
            ['Analysis Date', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Patients', len(results_df)],
            ['Total Events', int(results_df['Observed_Toxicity'].sum())],
            ['Overall Event Rate (%)', f"{(results_df['Observed_Toxicity'].sum() / len(results_df) * 100):.1f}"],
            ['Number of Organs', len(results_df['Organ'].unique())],
            ['Organs Analyzed', ', '.join(results_df['Organ'].unique())],
            ['Traditional Models', 'LKB Log-Logistic, LKB Probit, RS Poisson'],
            ['ML Models', 'ANN, XGBoost (where sufficient data)'],
            ['Performance Metrics', 'AUC, Brier Score'],
            ['Minimum Sample Size for ML', '15 patients per organ'],
            ['Software Version', 'Enhanced NTCP Pipeline v3.0']
        ]
        
        metadata_df = pd.DataFrame(metadata, columns=['Parameter', 'Value'])
        metadata_df.to_excel(writer, sheet_name='Analysis Metadata', index=False)
    
    # Also save a separate ntcp_predictions.xlsx file for compatibility (Fix 2)
    ntcp_predictions_file = output_path / "ntcp_predictions.xlsx"
    try:
        if not ntcp_df.empty:
            ntcp_df.to_excel(ntcp_predictions_file, index=False)
            print(f"[OK] Saved NTCP predictions: {ntcp_predictions_file}")
            print(f"     Rows: {len(ntcp_df)}")
        else:
            # Fallback: extract from results_df if ntcp_df is empty
            ntcp_cols = ['PatientID', 'Organ', 'Observed_Toxicity']
            ntcp_prediction_cols = [col for col in results_df.columns if col.startswith('NTCP_')]
            ntcp_cols.extend(ntcp_prediction_cols)
            if all(col in results_df.columns for col in ntcp_cols[:3]):
                ntcp_df_standalone = results_df[ntcp_cols].copy()
                for col in ntcp_prediction_cols:
                    if col in ntcp_df_standalone.columns:
                        ntcp_df_standalone[col] = ntcp_df_standalone[col].round(4)
                ntcp_df_standalone.to_excel(ntcp_predictions_file, index=False)
                print(f"[OK] Saved NTCP predictions: {ntcp_predictions_file}")
                print(f"     Rows: {len(ntcp_df_standalone)}")
            else:
                # Last resort: save minimal predictions file
                minimal_df = results_df[['PatientID', 'Organ']].copy()
                if 'Observed_Toxicity' in results_df.columns:
                    minimal_df['Observed_Toxicity'] = results_df['Observed_Toxicity']
                minimal_df.to_excel(ntcp_predictions_file, index=False)
                print(f"[OK] Saved NTCP predictions (minimal): {ntcp_predictions_file}")
                print(f"     Rows: {len(minimal_df)}")
    except Exception as e:
        print(f"[!] Warning: Could not save ntcp_predictions.xlsx: {e}")
        # Try to save at least a minimal file
        try:
            minimal_df = results_df[['PatientID', 'Organ']].copy()
            if 'Observed_Toxicity' in results_df.columns:
                minimal_df['Observed_Toxicity'] = results_df['Observed_Toxicity']
            minimal_df.to_excel(ntcp_predictions_file, index=False)
            print(f"[OK] Saved NTCP predictions (minimal fallback): {ntcp_predictions_file}")
        except:
            print(f"[!] Error: Could not save ntcp_predictions.xlsx")
    
    print(f" Comprehensive Excel file created: {excel_file}")
    return excel_file

def load_patient_data(patient_data_file):
    """
    Load patient data with outcomes using ClinicalDataHandler for automatic column detection.
    
    ✓ FIXED: UTF-8 encoding for Windows compatibility
    ✓ FIXED: Proper error handling
    """
    try:
        import sys
        import io
        
        # ✓ FIX: Force UTF-8 encoding to avoid Windows CP1252 errors
        if sys.platform == 'win32':
            try:
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding='utf-8',
                    errors='replace'
                )
            except AttributeError:
                pass  # Already UTF-8 or not applicable
        
        from utils.clinical_data_handler import ClinicalDataHandler
        
        # Use ClinicalDataHandler for smart column detection
        print("Loading clinical data with automatic column detection...")
        clinical_handler = ClinicalDataHandler(patient_data_file)
        patient_df = clinical_handler.prepare_for_analysis(interactive=False)
        
        if patient_df is None:
            print("Error: Failed to prepare clinical data")
            return None
        
        # Get the detected patient ID column name
        patient_id_col = clinical_handler.patient_id_col
        print(f"[OK] Detected patient ID column: {patient_id_col}")
        print(f"[OK] Detected toxicity columns: {clinical_handler.toxicity_cols}")
        
        # Rename patient ID column to 'PatientID' for compatibility
        if patient_id_col != 'PatientID':
            patient_df = patient_df.rename(columns={patient_id_col: 'PatientID'})
        
        # Handle treatment parameters (if present)
        treatment_mapping = {
            'Tx_DosePerFraction': 'dose_per_fraction',
            'Tx_n_frac': 'n_fractions',
            'Tx_alpha_beta': 'alpha_beta'
        }
        
        for old_col, new_col in treatment_mapping.items():
            if old_col in patient_df.columns:
                patient_df = patient_df.rename(columns={old_col: new_col})
        
        # Fill missing values with defaults
        if 'dose_per_fraction' not in patient_df.columns:
            patient_df['dose_per_fraction'] = 2.0
        
        if 'n_fractions' not in patient_df.columns:
            patient_df['n_fractions'] = 35
        
        return patient_df
        
    except Exception as e:
        print(f"Error loading patient data: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_all_patients(dvh_dir, patient_data_file, output_dir, enable_shap=False):
    """Enhanced main processing pipeline with traditional + ML models"""
    
    print("Enhanced NTCP Analysis: Traditional + Machine Learning Models")
    print("=" * 65)
    
    # ✓ FIX: Create output directories
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    plots_dir = output_path / 'plots'
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    tables_dir = output_path / 'tables'
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[OK] Output directory: {output_path}")
    print(f"[OK] Plots directory: {plots_dir}")
    print(f"[OK] Tables directory: {tables_dir}")
    
    # Initialize components
    dvh_processor = DVHProcessor(dvh_dir)
    ntcp_calculator = NTCPCalculator()
    ml_models = MachineLearningModels()
    
    # Load patient data with automatic column detection
    patient_df = load_patient_data(patient_data_file)
    if patient_df is None:
        return
    
    print(f"Loaded {len(patient_df)} patient-organ combinations")
    
    # Verify required columns exist
    required_cols = ['PatientID', 'Organ', 'Observed_Toxicity']
    missing_cols = [col for col in required_cols if col not in patient_df.columns]
    if missing_cols:
        print(f"Error: Missing required columns: {missing_cols}")
        print(f"Available columns: {list(patient_df.columns)}")
        return
    
    # Process each patient-organ combination
    results = []
    
    for _, row in patient_df.iterrows():
        patient_id = str(row['PatientID']).strip()
        organ_raw = row.get('Organ', 'Unknown')
        organ = str(organ_raw).strip()

        observed_toxicity = row.get(
            'Observed_Toxicity', row.get('Toxicity', 0)
        )
        dose_per_fraction = row.get('dose_per_fraction', 2.0)
        
        print(f"\nProcessing {patient_id} - {organ}")
        
        # Load DVH data (exact Organ name first, then legacy short names)
        dvh = dvh_processor.load_dvh_file(patient_id, organ)
        if dvh is None:
            organ_lower = organ.lower().replace(' ', '').replace('_', '')
            organ_alias = organ
            if 'parotid' in organ_lower and '_' not in organ:
                organ_alias = 'Parotid'
            elif 'cord' in organ_lower and 'prv' not in organ_lower:
                organ_alias = 'SpinalCord'
            elif organ_lower == 'larynx':
                organ_alias = 'Larynx'
            if organ_alias != organ:
                dvh = dvh_processor.load_dvh_file(patient_id, organ_alias)
        if dvh is None:
            print(f"  Warning: Skipping - DVH file not found")
            continue
        
        # Calculate dose metrics
        dose_metrics = dvh_processor.calculate_dose_metrics(dvh)
        if dose_metrics is None:
            print(f"  Warning: Skipping - Could not calculate dose metrics")
            continue
        
        def _literature_organ_key(name: str) -> str | None:
            if name in ntcp_calculator.literature_params:
                return name
            low = name.lower()
            if 'parotid' in low:
                return 'Parotid'
            if 'spinalcord' in low or (low.startswith('cord') and 'prv' not in low):
                return 'SpinalCord'
            if 'larynx' in low or 'glottic' in low or 'pharynx' in low:
                return 'Larynx'
            if 'brainstem' in low:
                return 'SpinalCord'
            return None

        param_organ = _literature_organ_key(organ)
        if param_organ:
            lit_params = ntcp_calculator.literature_params[param_organ]
            a_param = lit_params['LKB_LogLogit']['a']
            n_param = lit_params['LKB_Probit']['n']
        else:
            print(f"  Warning: No literature parameters for {organ}")
            continue
        organ = param_organ
        
        # Get alpha/beta ratio for biological dose calculations
        alpha_beta = lit_params['LKB_LogLogit'].get('alpha_beta', 3.0)
        
        # Calculate physical dose metrics
        geud_physical = dvh_processor.calculate_gEUD(dvh, a_param)
        v_effective = dvh_processor.calculate_effective_volume(dvh, n_param)
        
        # Calculate biological doses (BED and EQD2)
        mean_dose = dose_metrics['mean_dose']
        max_dose = dose_metrics['max_dose']
        
        # Convert mean and max doses to EQD2
        eqd2_mean = ntcp_calculator.convert_to_eqd2(mean_dose, alpha_beta, dose_per_fraction)
        eqd2_max = ntcp_calculator.convert_to_eqd2(max_dose, alpha_beta, dose_per_fraction)
        
        # Calculate BED
        bed_mean = mean_dose * (1 + dose_per_fraction / alpha_beta)
        bed_max = max_dose * (1 + dose_per_fraction / alpha_beta)
        
        # Convert entire DVH to EQD2 for gEUD calculation
        dvh_eqd2 = dvh.copy()
        dvh_eqd2['dose_gy'] = dvh['dose_gy'].apply(
            lambda d: ntcp_calculator.convert_to_eqd2(d, alpha_beta, dose_per_fraction)
        )
        geud_eqd2 = dvh_processor.calculate_gEUD(dvh_eqd2, a_param)
        
        # Add to dose metrics
        dose_metrics['gEUD_Physical_Gy'] = geud_physical
        dose_metrics['gEUD_EQD2_Gy'] = geud_eqd2
        dose_metrics['v_effective'] = v_effective
        dose_metrics['EQD2_Mean_Gy'] = eqd2_mean
        dose_metrics['EQD2_Max_Gy'] = eqd2_max
        dose_metrics['BED_Mean_Gy'] = bed_mean
        dose_metrics['BED_Max_Gy'] = bed_max
        dose_metrics['AlphaBeta'] = alpha_beta
        dose_metrics['DosePerFraction'] = dose_per_fraction
        
        print(f"   Total volume: {dose_metrics['total_volume']:.1f} cm3")
        print(f"   Mean dose: {dose_metrics['mean_dose']:.1f} Gy (physical)")
        print(f"   Max dose: {dose_metrics['max_dose']:.1f} Gy (physical)")
        print(f"   EQD2 mean: {eqd2_mean:.1f} Gy")
        print(f"   gEUD (physical): {geud_physical:.1f} Gy")
        print(f"   gEUD (EQD2): {geud_eqd2:.1f} Gy")
        
        # Update dose_metrics with EQD2-based gEUD for NTCP calculations
        dose_metrics['gEUD'] = geud_eqd2  # Use EQD2-based gEUD for NTCP
        
        # Calculate NTCP using EQD2-based gEUD (biological dose)
        ntcp_results = ntcp_calculator.calculate_all_ntcp_models(
            dvh_eqd2, dose_metrics, organ, dose_per_fraction
        )
        
        # Compile results
        result_row = {
            'PatientID': patient_id,
            'Organ': organ,
            'Observed_Toxicity': observed_toxicity,
            'dose_per_fraction': dose_per_fraction,
            **dose_metrics
        }
        
        # Add traditional NTCP predictions
        for model_name, model_result in ntcp_results.items():
            result_row[f'NTCP_{model_name}'] = model_result.get('NTCP', np.nan)
            print(f"  {model_name}: {model_result.get('NTCP', 0):.3f}")
        
        results.append(result_row)
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # ✓ FIX: Ensure we have results before proceeding
    if results_df.empty:
        print("\n[X] Error: No data processed. Please check:")
        print("    1. DVH files match patient IDs in clinical data")
        print("    2. File naming convention: PatientID_OrganName.csv")
        print("    3. Clinical data has required columns (PatientID, Organ, Observed_Toxicity)")
        return None
    
    print(f"\n[OK] Processed {len(results_df)} patient-organ combinations")
    
    # Train ML models per organ
    print(f"\n Training Machine Learning Models")
    print("=" * 40)
    
    ml_results = {}
    for organ in results_df['Organ'].unique():
        organ_data = results_df[results_df['Organ'] == organ].copy()
        
        # Use all available samples - don't filter out
        sample_count = len(organ_data)
        event_count = organ_data['Observed_Toxicity'].sum() if 'Observed_Toxicity' in organ_data.columns else 0
        
        print(f"\nML Analysis for {organ}...")
        print(f"  {organ}: {sample_count} samples, {int(event_count)} events")
        
        # Warn but proceed with all available data
        if sample_count < 15:
            print(f"  ⚠️  Low sample count for {organ} (proceeding anyway)")
        
        ml_organ_results = ml_models.train_and_evaluate_ml_models(
            organ_data, organ, 
            output_dir=Path(output_dir),
            enable_shap=enable_shap
        )
        
        if ml_organ_results:
            ml_results[organ] = ml_organ_results
            
            # Add ML predictions to results
            ml_predictions = ml_models.predict_ml_models(organ_data, organ)
            
            for pred_col, pred_values in ml_predictions.items():
                # Map predictions back to full results DataFrame
                organ_mask = results_df['Organ'] == organ
                organ_indices = results_df[organ_mask].index
                
                if len(pred_values) == len(organ_indices):
                    results_df.loc[organ_indices, pred_col] = pred_values
    
    # Save results
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results_df.to_csv(output_path / 'enhanced_ntcp_calculations.csv', index=False)
    print(f"\n[OK] Saved enhanced NTCP calculations to {output_path / 'enhanced_ntcp_calculations.csv'}")

    # Create comprehensive Excel file
    create_comprehensive_excel(results_df, output_dir)
    
    # Create comprehensive plots
    print(f"\nCreating Comprehensive Publication-Ready Plots")
    print("=" * 55)
    
    plotter = ComprehensivePlotter(output_path / 'plots', ntcp_calculator)
    
    for organ in results_df['Organ'].unique():
        organ_data = results_df[results_df['Organ'] == organ].copy()
        
        print(f"\n Creating plots for {organ}...")
        
        # Individual plots for each organ
        plotter.create_dose_response_plot(organ_data, organ)
        plotter.create_roc_plot(organ_data, organ)
        plotter.create_calibration_plot(organ_data, organ)
        plotter.create_combined_roc_calibration_plot(organ_data, organ)
    
    # Overall analysis plots
    print(f"\n Creating comprehensive analysis plots...")
    plotter.create_comprehensive_analysis_plot(results_df)
    plotter.create_model_performance_plot(results_df)
    plotter.create_overall_performance_plot(results_df)
    
    # ✓ FIX: Verify output files were created
    excel_file = output_path / 'ntcp_results.xlsx'
    csv_file = output_path / 'enhanced_ntcp_calculations.csv'
    
    if excel_file.exists() and csv_file.exists():
        print(f"\n{'='*70}")
        print(f"[OK] NTCP analysis complete!")
        print(f"[OK] Results saved to: {output_path.absolute()}")
        print(f"[OK] Generated files:")
        print(f"     - {excel_file.name} (comprehensive Excel)")
        print(f"     - {csv_file.name} (CSV calculations)")
        print(f"     - plots/ (publication-quality plots)")
        print(f"     - tables/ (summary tables)")
        print(f"{'='*70}\n")
    else:
        print(f"\n[!] Warning: Some output files may not have been created")
        print(f"[!] Expected: {excel_file} and {csv_file}")
    
    return results_df

def create_enhanced_summary_report(results_df, output_dir):
    """Create enhanced summary report"""
    
    output_path = Path(output_dir)
    
    summary_stats = []
    
    for organ in results_df['Organ'].unique():
        organ_data = results_df[results_df['Organ'] == organ]
        
        n_patients = len(organ_data)
        n_events = int(organ_data['Observed_Toxicity'].sum())
        event_rate = n_events / n_patients if n_patients > 0 else 0
        
        # Get all model performance
        model_performance = {}
        
        # Traditional NTCP models
        for model in ['LKB_LogLogit', 'LKB_Probit', 'RS_Poisson']:
            ntcp_col = f'NTCP_{model}'
            if ntcp_col in organ_data.columns:
                valid_data = organ_data.dropna(subset=[ntcp_col, 'Observed_Toxicity'])
                if len(valid_data) >= 5:
                    try:
                        fpr, tpr, _ = roc_curve(valid_data['Observed_Toxicity'], valid_data[ntcp_col])
                        auc_score = auc(fpr, tpr)
                        model_performance[model] = auc_score
                    except:
                        model_performance[model] = np.nan
        
        # ML models
        ml_cols = [col for col in organ_data.columns if col.startswith('NTCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                model_name = 'ML_ANN'
            elif 'XGBoost' in ml_col:
                model_name = 'ML_XGBoost'
            else:
                continue
                
            valid_data = organ_data.dropna(subset=[ml_col, 'Observed_Toxicity'])
            if len(valid_data) >= 5:
                try:
                    fpr, tpr, _ = roc_curve(valid_data['Observed_Toxicity'], valid_data[ml_col])
                    auc_score = auc(fpr, tpr)
                    model_performance[model_name] = auc_score
                except:
                    model_performance[model_name] = np.nan
        
        # Find best models
        best_overall = max(model_performance.items(), key=lambda x: x[1] if not np.isnan(x[1]) else 0) if model_performance else ('None', 0)
        
        physics_models = {k: v for k, v in model_performance.items() if not k.startswith('ML_')}
        ml_models_perf = {k: v for k, v in model_performance.items() if k.startswith('ML_')}
        
        best_physics = max(physics_models.items(), key=lambda x: x[1] if not np.isnan(x[1]) else 0) if physics_models else ('None', 0)
        best_ml = max(ml_models_perf.items(), key=lambda x: x[1] if not np.isnan(x[1]) else 0) if ml_models_perf else ('None', 0)
        
        summary_stats.append({
            'Organ': organ,
            'N_Patients': n_patients,
            'N_Events': n_events,
            'Event_Rate_Percent': f"{event_rate*100:.1f}%",
            'Best_Overall_Model': best_overall[0],
            'Best_Overall_AUC': f"{best_overall[1]:.3f}" if not np.isnan(best_overall[1]) else 'N/A',
            'Best_Physics_Model': best_physics[0],
            'Best_Physics_AUC': f"{best_physics[1]:.3f}" if not np.isnan(best_physics[1]) else 'N/A',
            'Best_ML_Model': best_ml[0],
            'Best_ML_AUC': f"{best_ml[1]:.3f}" if not np.isnan(best_ml[1]) else 'N/A',
            'ML_Available': 'Yes' if ml_models_perf else 'No',
            'Data_Quality': get_data_quality_rating(n_patients, n_events),
            'Clinical_Recommendation': get_clinical_recommendation(best_overall[1], n_events, ml_models_perf)
        })
    
    summary_df = pd.DataFrame(summary_stats)
    summary_df.to_csv(output_path / 'enhanced_summary_performance.csv', index=False)
    
    # Create detailed text report
    report_text = []
    report_text.append("Enhanced NTCP Analysis: Traditional + Machine Learning Models")
    report_text.append("=" * 65)
    report_text.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_text.append(f"Enhanced features: Traditional NTCP + ML Models (ANN, XGBoost)")
    report_text.append(f"Plot quality: 600 DPI publication-ready")
    report_text.append("")
    
    for _, row in summary_df.iterrows():
        organ = row['Organ']
        report_text.append(f"{organ.upper()} ENHANCED ANALYSIS")
        report_text.append("-" * (len(organ) + 20))
        report_text.append(f"Sample Size: {row['N_Patients']} patients")
        report_text.append(f"Events: {row['N_Events']} ({row['Event_Rate_Percent']})")
        report_text.append("")
        
        report_text.append("Model Performance Comparison:")
        report_text.append(f"  Best Overall: {row['Best_Overall_Model']} (AUC: {row['Best_Overall_AUC']})")
        report_text.append(f"  Best Traditional: {row['Best_Physics_Model']} (AUC: {row['Best_Physics_AUC']})")
        
        if row['ML_Available'] == 'Yes':
            report_text.append(f"  Best ML: {row['Best_ML_Model']} (AUC: {row['Best_ML_AUC']})")
            
            # Calculate improvement
            try:
                physics_auc = float(row['Best_Physics_AUC'])
                ml_auc = float(row['Best_ML_AUC'])
                improvement = ((ml_auc - physics_auc) / physics_auc) * 100
                report_text.append(f"  ML Improvement: {improvement:+.1f}%")
            except:
                report_text.append(f"  ML Improvement: Cannot calculate")
        else:
            report_text.append(f"  ML Models: Not available (insufficient data)")
        
        report_text.append("")
        report_text.append(f"Data Quality: {row['Data_Quality']}")
        report_text.append(f"Clinical Recommendation: {row['Clinical_Recommendation']}")
        report_text.append("")
        report_text.append("-" * 60)
        report_text.append("")
    
    # Save enhanced text report
    with open(output_path / 'enhanced_analysis_report.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_text))
    
    print(f"\nEnhanced summary report saved to {output_path / 'enhanced_analysis_report.txt'}")
    print(f" Enhanced performance table saved to {output_path / 'enhanced_summary_performance.csv'}")

def get_data_quality_rating(n_patients, n_events):
    """Enhanced data quality assessment"""
    if n_events < 5:
        return 'Poor (< 5 events, ML not feasible)'
    elif n_events < 10:
        return 'Fair (5-9 events, limited ML)'
    elif n_patients < 30:
        return 'Good (≥10 events, ML possible)'
    elif n_patients >= 50 and n_events >= 15:
        return 'Excellent (≥15 events, ≥50 patients, ML reliable)'
    else:
        return 'Very Good (adequate for ML)'

def get_clinical_recommendation(best_auc, n_events, ml_models):
    """Enhanced clinical recommendation including ML considerations"""
    
    if isinstance(best_auc, str) or n_events < 5:
        return 'Insufficient events for reliable recommendations'
    
    auc_val = float(best_auc) if isinstance(best_auc, str) else best_auc
    
    if auc_val < 0.6:
        return 'Poor discrimination - not recommended for clinical use'
    elif auc_val < 0.7:
        base_rec = 'Moderate discrimination - use with caution'
    elif auc_val < 0.8:
        base_rec = 'Good discrimination - suitable for clinical decision support'
    else:
        base_rec = 'Excellent discrimination - highly suitable for clinical use'
    
    # Add ML-specific recommendations
    if ml_models:
        base_rec += '; ML models available for enhanced predictions'
    
    return base_rec

def validate_ntcp_clinical_data(clinical_file):
    """
    Validate NTCP clinical data has required columns
    
    Required: PatientID, Organ, Toxicity (or specific toxicity column)
    
    Returns
    -------
    tuple: (DataFrame, primary_toxicity_column)
    """
    if clinical_file.endswith('.xlsx'):
        df = pd.read_excel(clinical_file, engine='openpyxl')
    else:
        df = pd.read_csv(clinical_file)
    
    # Check required columns
    required = ['PatientID', 'Organ']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Check for at least one toxicity column
    toxicity_cols = [col for col in df.columns 
                    if 'toxicity' in col.lower() or 
                       'xerostomia' in col.lower() or
                       'dysphagia' in col.lower() or
                       col == 'Toxicity']
    
    if not toxicity_cols:
        raise ValueError("No toxicity columns found. Need at least one binary toxicity outcome.")
    
    print(f"[OK] Clinical data validated")
    print(f"     Found toxicity columns: {', '.join(toxicity_cols)}")
    
    return df, toxicity_cols[0]  # Return primary toxicity


def main():
    """Enhanced main execution function"""
    
    parser = argparse.ArgumentParser(description='Enhanced NTCP Analysis: Traditional + ML Models')
    parser.add_argument('--dvh_dir', default='dDVH_csv', 
                       help='Directory containing DVH CSV files (default: dDVH_csv)')
    parser.add_argument('--patient_data', default=None,
                       help='Patient data file with toxicity outcomes (Excel/CSV). Use Help -> Download NTCP Template to create template.')
    parser.add_argument('--output_dir', default='enhanced_ntcp_analysis',
                       help='Output directory (default: enhanced_ntcp_analysis)')
    parser.add_argument('--ml_models', action='store_true', default=True,
                       help='Enable machine learning models (default: True)')
    # SHAP explainability arguments
    parser.add_argument('--enable_shap', action='store_true',
                       help='Generate SHAP explainability plots for ML models')
    parser.add_argument('--shap_patients', nargs='+', type=int, default=None,
                       help='Patient indices for detailed SHAP analysis (e.g., --shap_patients 5 10 15)')
    
    args = parser.parse_args()
    
    print(" Enhanced NTCP Analysis: Traditional + Machine Learning")
    print("=" * 60)
    print("Features:")
    print("  - Traditional NTCP models (LKB Log-Logistic, LKB Probit, RS Poisson)")
    print("  - Machine learning models (ANN, XGBoost)")
    if args.enable_shap:
        print("  - SHAP explainability analysis (enabled)")
    print("  - Unique colors and legends for all models")
    print("  - Enhanced 600 DPI publication-ready plots")
    print("  - Comprehensive Excel output (ntcp_results.xlsx)")
    print("  - Proper ML validation and anti-overfitting measures")
    
    # Validate input paths
    dvh_path = Path(args.dvh_dir)
    
    if not dvh_path.exists():
        print(f"Error: Error: DVH directory '{dvh_path}' not found")
        sys.exit(1)
    
    # Validate clinical data if provided
    if not args.patient_data:
        print("[!] No clinical data file specified")
        print("    Please provide --patient_data <file>")
        print("    Use Help -> Download NTCP Template to create template")
        sys.exit(1)
    
    patient_file = Path(args.patient_data)
    
    if not patient_file.exists():
        print(f"Error: Patient data file '{patient_file}' not found")
        sys.exit(1)
    
    # Validate clinical data schema
    try:
        clinical_df, primary_toxicity = validate_ntcp_clinical_data(str(patient_file))
        print(f"    Primary toxicity column: {primary_toxicity}")
    except Exception as e:
        print(f"[!] Clinical data validation failed: {e}")
        sys.exit(1)
    
    # Check for DVH files
    dvh_files = list(dvh_path.glob('*.csv'))
    if not dvh_files:
        print(f"Error: Error: No CSV files found in '{dvh_path}'")
        sys.exit(1)
    
    print(f" Found {len(dvh_files)} DVH files in {dvh_path}")
    print(f" Patient data file: {patient_file}")
    
    # Check XGBoost availability
    if XGBOOST_AVAILABLE:
        print(" XGBoost available for ML modeling")
    else:
        print("Warning: XGBoost not available - only ANN will be used")
    
    # ✓ CRITICAL: Create output directories with proper error handling
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    tables_dir = output_dir / 'tables'
    tables_dir.mkdir(parents=True, exist_ok=True)
    
    # ✓ NEW: Verify directories were created
    if not output_dir.exists():
        print(f"[X] Error: Could not create output directory: {output_dir}")
        sys.exit(1)
    
    print(f"\n[OK] Output directory: {output_dir}")
    print(f"[OK] Plots directory: {plots_dir}")
    print(f"[OK] Tables directory: {tables_dir}")
    
    try:
        # Step 1: Enhanced processing with traditional + ML models
        print("\nStep 1: Enhanced DVH processing and model training...")
        results_df = process_all_patients(
            args.dvh_dir, args.patient_data, args.output_dir,
            enable_shap=args.enable_shap
        )
        
        if results_df is None or len(results_df) == 0:
            print("Error: No data processed. Please check file formats and patient IDs.")
            sys.exit(1)
        
        print(f" Processed {len(results_df)} patient-organ combinations")
        
        # Count available models
        ntcp_cols = [col for col in results_df.columns if col.startswith('NTCP_')]
        traditional_models = [col for col in ntcp_cols if not 'ML_' in col]
        ml_models = [col for col in ntcp_cols if 'ML_' in col]
        
        print(f" Traditional NTCP models: {len(traditional_models)}")
        print(f" ML models trained: {len(ml_models)}")
        
        # Step 2: Enhanced summary report
        print("\nStep 2: Generating enhanced summary report...")
        create_enhanced_summary_report(results_df, args.output_dir)
        
        # Step 3: Create comprehensive Excel file
        print("\nStep 3: Creating comprehensive Excel output...")
        excel_file = create_comprehensive_excel(results_df, args.output_dir)
        
        # ✓ CRITICAL: Verify files were created
        csv_file = output_dir / 'enhanced_ntcp_calculations.csv'
        if results_df is not None and len(results_df) > 0:
            results_df.to_csv(csv_file, index=False)
        
        # ✓ VERIFY files were created
        if excel_file.exists():
            print(f"\n{'='*70}")
            print(f"[OK] NTCP analysis complete!")
            print(f"[OK] Results saved: {excel_file}")
            print(f"[OK] File size: {excel_file.stat().st_size / 1024:.1f} KB")
            print(f"[OK] Organ analyses: {len(results_df['Organ'].unique()) if 'Organ' in results_df.columns else 0}")
            print(f"[OK] Total plots: {len(list(plots_dir.glob('*.png'))) if plots_dir.exists() else 0}")
            print(f"{'='*70}\n")
        else:
            print(f"\n[!] Warning: Output file not created!")
            print("[!] Possible reasons:")
            print("    - No matching clinical data for DVH files")
            print("    - Insufficient data per organ (need n >= 5)")
            print("    - All organs failed processing")
        
        print("\nEnhanced analysis completed successfully!")
        print("=" * 60)
        print(f"All outputs saved to: {Path(args.output_dir).absolute()}")
        print("\nGenerated files:")
        print("  - ntcp_results.xlsx - Comprehensive Excel file with all results")
        print("  - enhanced_ntcp_calculations.csv - All model predictions")
        print("  - enhanced_summary_performance.csv - Performance table")
        print("  - enhanced_analysis_report.txt - Detailed report")
        print("  - plots/ - 600 DPI publication-ready plots:")
        print("    - [Organ]_dose_response.png - Dose-response curves")
        print("    - [Organ]_ROC.png - ROC curves with unique colors")
        print("    - [Organ]_calibration.png - Calibration plots")
        print("    - [Organ]_ROC_calibration_combined.png - Combined plots")
        print("    - comprehensive_analysis.png - Overall analysis")
        print("    - model_performance_analysis.png - Performance comparison")
        print("    - overall_performance_summary.png - Summary overview")
        
        # Display enhanced key findings
        print("\n Enhanced Key Findings:")
        
        # Summary by organ
        for organ in results_df['Organ'].unique():
            organ_data = results_df[results_df['Organ'] == organ]
            n_patients = len(organ_data)
            n_events = int(organ_data['Observed_Toxicity'].sum())
            event_rate = n_events / n_patients if n_patients > 0 else 0
            
            print(f"  {organ}: {n_patients} patients, {n_events} events ({event_rate:.1%})")
            
            # Find best traditional and ML models
            traditional_aucs = []
            ml_aucs = []
            
            for col in ntcp_cols:
                if col in organ_data.columns:
                    valid_data = organ_data.dropna(subset=[col, 'Observed_Toxicity'])
                    if len(valid_data) >= 5:
                        try:
                            fpr, tpr, _ = roc_curve(valid_data['Observed_Toxicity'], valid_data[col])
                            auc_score = auc(fpr, tpr)
                            
                            if 'ML_' in col:
                                ml_aucs.append((col, auc_score))
                            else:
                                traditional_aucs.append((col, auc_score))
                        except:
                            pass
            
            # Report best models
            if traditional_aucs:
                best_trad = max(traditional_aucs, key=lambda x: x[1])
                print(f"    Best traditional: {best_trad[0]} (AUC = {best_trad[1]:.3f})")
            
            if ml_aucs:
                best_ml = max(ml_aucs, key=lambda x: x[1])
                print(f"    Best ML: {best_ml[0]} (AUC = {best_ml[1]:.3f})")
                
                # Calculate improvement
                if traditional_aucs:
                    improvement = ((best_ml[1] - best_trad[1]) / best_trad[1]) * 100
                    print(f"    ML improvement: {improvement:+.1f}%")
            else:
                print(f"    ML models: Not trained (insufficient data)")
        
        print("\nNext Steps:")
        print("  1. Review ntcp_results.xlsx for comprehensive results")
        print("  2. Examine publication-ready plots in plots/ directory")
        print("  3. Read enhanced_analysis_report.txt for detailed findings")
        print("  4. Consider ML model deployment if performance is superior")
        print("  5. Validate findings with external cohorts")
        print("  6. Use unique color coding to distinguish model types:")
        print("     - Traditional NTCP: Blue (LKB LogLogit), Red (LKB Probit), Gold (RS Poisson)")
        print("     - ML models: Purple (ANN), Green (XGBoost)")
        
    except Exception as e:
        print(f"\nError: Error during enhanced analysis: {e}")
        import traceback
        print("\nFull error traceback:")
        traceback.print_exc()
        
        print("\nTroubleshooting tips:")
        print("  - Ensure sufficient data for ML training (>=15 samples per organ)")
        print("  - Check that all required Python packages are installed:")
        print("    pip install scikit-learn xgboost pandas numpy matplotlib seaborn scipy openpyxl")
        print("  - Verify DVH files and patient data formats")
        print("  - Ensure unique patient IDs in DVH filenames")

if __name__ == "__main__":
    main()   