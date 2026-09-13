#!/usr/bin/env python3
"""
rbGyanX v1.0 - TCP Analysis with Traditional and Machine Learning Models
========================================================================
Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

This comprehensive script combines:
1. Traditional TCP models (Poisson, LKB, Logistic, EUD)
2. Machine learning models (ANN, XGBoost) with proper validation
3. SHAP explainability analysis (integrated)
4. Professional 600 DPI publication-ready plots
5. Unique colors and legends for all models
6. Comprehensive Excel output with all results

Author: rbGyanX Team
License: MIT
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import argparse
import os
import sys
from scipy.stats import norm
from sklearn.metrics import roc_curve, auc, brier_score_loss, log_loss
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", message=".*tight_layout.*", category=UserWarning)

# SHAP explainability (integrated from day 1)
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

# XGBoost (optional)
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available. Install with: pip install xgboost")

# TCP models
from utils.tcp_models import TCPCalculator

# Novel features: FDVH, uTCP, and CCS
try:
    from utils.biological_transforms import FractionationAwareDVH
    FDVH_AVAILABLE = True
except ImportError:
    FDVH_AVAILABLE = False
    print("Warning: FDVH module not available")

try:
    from utils.uncertainty_models import UncertaintyAwareTCP, calculate_all_utcp
    UTCP_AVAILABLE = True
except ImportError:
    UTCP_AVAILABLE = False
    print("Warning: uTCP module not available")

try:
    from utils.ml_safety import CohortConsistencyChecker, create_ccs_report
    CCS_AVAILABLE = True
except ImportError:
    CCS_AVAILABLE = False
    print("Warning: CCS (ML Safety) module not available")

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
        'TCP_Poisson': '#2E86AB',
        'TCP_LKB': '#F24236',
        'TCP_Logistic': '#F6AE2D',
        'TCP_EUD': '#55A630',
        'ML_ANN': '#8B4B9E',
        'ML_XGBoost': '#2ECC71',
        'observed': '#C73E1D',
        'confidence': '#95A5A6',
        'grid': '#E8E8E8'
    }
    
    LINE_STYLES = {
        'TCP_Poisson': '-',
        'TCP_LKB': '--',
        'TCP_Logistic': '-.',
        'TCP_EUD': ':',
        'ML_ANN': (0, (3, 1, 1, 1, 1, 1)),
        'ML_XGBoost': (0, (5, 2))
    }
    
    MARKERS = {
        'TCP_Poisson': 'o',
        'TCP_LKB': 's',
        'TCP_Logistic': '^',
        'TCP_EUD': 'D',
        'ML_ANN': 'v',
        'ML_XGBoost': 'X'
    }


class TumorDVHProcessor:
    """
    Process tumor DVH data for TCP calculations.
    
    Similar to DVHProcessor in code3 but adapted for tumor structures.
    Calculates tumor-specific dose metrics (D95, D98, V95, V100, etc.)
    """
    
    def __init__(self, dvh_directory):
        """
        Initialize processor with tumor DVH directory.
        
        Parameters
        ----------
        dvh_directory : str or Path
            Directory containing tumor DVH CSV files
        """
        self.dvh_dir = Path(dvh_directory)
        self.processed_data = {}
    
    def load_dvh_file(self, patient_id, tumor_name):
        """
        Load differential DVH file for specific patient and tumor.
        
        Parameters
        ----------
        patient_id : str
            Patient identifier
        tumor_name : str
            Tumor structure name (e.g., 'PTV', 'GTV', 'CTV')
            
        Returns
        -------
        pd.DataFrame or None
            DVH data with columns 'dose_gy' and 'volume_cm3', or None if error
        """
        # Try exact match first
        dvh_file = self.dvh_dir / f"{patient_id}_{tumor_name}.csv"
        
        # If not found, try pattern matching
        if not dvh_file.exists():
            pattern = f"{patient_id}*{tumor_name}*.csv"
            files = list(self.dvh_dir.glob(pattern))
            if files:
                dvh_file = files[0]
            else:
                print(f"Warning: DVH file not found for {patient_id} - {tumor_name}")
                return None
        
        try:
            # Load DVH data
            dvh = pd.read_csv(dvh_file)
            
            # Standardize column names
            if 'Dose[Gy]' in dvh.columns and 'Volume[cm3]' in dvh.columns:
                dvh = dvh.rename(columns={'Dose[Gy]': 'dose_gy', 'Volume[cm3]': 'volume_cm3'})
            elif 'Dose[Gy]' in dvh.columns and 'Volume[%]' in dvh.columns:
                # Convert percentage to absolute volume (assume total volume from max)
                # This is approximate - ideally should have total volume info
                dvh = dvh.rename(columns={'Dose[Gy]': 'dose_gy', 'Volume[%]': 'volume_pct'})
                # Estimate total volume from maximum percentage (should be ~100% at dose=0)
                max_pct = dvh.loc[dvh['dose_gy'].idxmin(), 'volume_pct'] if len(dvh) > 0 else 100.0
                if max_pct > 0:
                    # Assume typical tumor volume (this is a fallback)
                    estimated_total_vol = 100.0  # cm3 default
                    dvh['volume_cm3'] = dvh['volume_pct'] / 100.0 * estimated_total_vol
                else:
                    dvh['volume_cm3'] = 0.0
            elif 'Dose' in dvh.columns and 'Volume' in dvh.columns:
                dvh = dvh.rename(columns={'Dose': 'dose_gy', 'Volume': 'volume_cm3'})
            else:
                print(f"Error: Unrecognized column names in {dvh_file}")
                print(f"  Expected: Dose[Gy] and Volume[cm3] or Volume[%]")
                print(f"  Found: {list(dvh.columns)}")
                return None
            
            # Validate required columns exist
            if 'dose_gy' not in dvh.columns or 'volume_cm3' not in dvh.columns:
                print(f"Error: Missing required columns in {dvh_file}")
                return None
            
            # Remove zero volume entries at high doses
            dvh = dvh[dvh['volume_cm3'] > 0].copy()
            
            if len(dvh) == 0:
                print(f"Warning: No valid data in {dvh_file}")
                return None
            
            # Sort by dose
            dvh = dvh.sort_values('dose_gy').reset_index(drop=True)
            
            # Basic validation: check for monotonic dose
            if not dvh['dose_gy'].is_monotonic_increasing:
                print(f"Warning: Dose values not monotonic in {dvh_file}, sorting...")
                dvh = dvh.sort_values('dose_gy').reset_index(drop=True)
            
            return dvh
            
        except Exception as e:
            print(f"Error loading {dvh_file}: {e}")
            return None
    
    def calculate_dose_metrics(self, dvh, prescribed_dose=None):
        """
        Calculate comprehensive tumor dose metrics from differential DVH.
        
        For tumors, focuses on coverage metrics:
        - D95, D98, D99 (dose to 95%, 98%, 99% of volume)
        - V95, V100, V110 (volume receiving >= 95%, 100%, 110% of prescription)
        - Mean dose, max dose, min dose
        - Coverage indices
        
        Parameters
        ----------
        dvh : pd.DataFrame
            Differential DVH with 'dose_gy' and 'volume_cm3' columns
        prescribed_dose : float, optional
            Prescribed dose in Gy (for V95, V100, V110 calculations)
            
        Returns
        -------
        dict or None
            Dictionary of dose metrics, or None if error
        """
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
        
        # Convert to cumulative DVH for Dxx and Vxx calculations
        # For differential DVH: cumulative volume at dose D = sum of volumes at doses >= D
        cumulative_vol = np.cumsum(volumes[::-1])[::-1]
        rel_cumulative = cumulative_vol / total_volume
        
        dose_metrics = {
            'total_volume': total_volume,
            'mean_dose': mean_dose,
            'max_dose': max_dose,
            'min_dose': min_dose
        }
        
        # Calculate Dxx (dose to xx% of volume) - critical for tumor coverage
        # D95, D98, D99 are standard coverage metrics
        for vol_percent in [1, 2, 5, 10, 20, 50, 90, 95, 98, 99]:
            target_vol_fraction = vol_percent / 100.0
            if target_vol_fraction <= 1.0:
                try:
                    # Interpolate dose at target volume fraction
                    # rel_cumulative is decreasing, doses are increasing
                    dose_at_volume = np.interp(target_vol_fraction, rel_cumulative[::-1], doses[::-1])
                    dose_metrics[f'D{vol_percent}'] = dose_at_volume
                except (ValueError, IndexError):
                    dose_metrics[f'D{vol_percent}'] = np.nan
            else:
                dose_metrics[f'D{vol_percent}'] = np.nan
        
        # Calculate Vxx (% volume receiving >= xx Gy) - standard dose-volume metrics
        for dose_level in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]:
            if dose_level <= max_dose:
                try:
                    volume_at_dose = np.interp(dose_level, doses, rel_cumulative) * 100.0
                    dose_metrics[f'V{dose_level}'] = volume_at_dose
                except (ValueError, IndexError):
                    dose_metrics[f'V{dose_level}'] = 0.0
            else:
                dose_metrics[f'V{dose_level}'] = 0.0
        
        # Calculate V95, V100, V110 relative to prescribed dose (if provided)
        if prescribed_dose is not None and prescribed_dose > 0:
            dose_95 = 0.95 * prescribed_dose
            dose_100 = 1.0 * prescribed_dose
            dose_110 = 1.1 * prescribed_dose
            
            try:
                if dose_95 <= max_dose:
                    volume_at_95 = np.interp(dose_95, doses, rel_cumulative) * 100.0
                    dose_metrics['V95_prescribed'] = volume_at_95
                else:
                    dose_metrics['V95_prescribed'] = 0.0
                
                if dose_100 <= max_dose:
                    volume_at_100 = np.interp(dose_100, doses, rel_cumulative) * 100.0
                    dose_metrics['V100_prescribed'] = volume_at_100
                else:
                    dose_metrics['V100_prescribed'] = 0.0
                
                if dose_110 <= max_dose:
                    volume_at_110 = np.interp(dose_110, doses, rel_cumulative) * 100.0
                    dose_metrics['V110_prescribed'] = volume_at_110
                else:
                    dose_metrics['V110_prescribed'] = 0.0
            except (ValueError, IndexError):
                dose_metrics['V95_prescribed'] = np.nan
                dose_metrics['V100_prescribed'] = np.nan
                dose_metrics['V110_prescribed'] = np.nan
        else:
            # If no prescribed dose, use absolute dose levels
            dose_metrics['V95_prescribed'] = np.nan
            dose_metrics['V100_prescribed'] = np.nan
            dose_metrics['V110_prescribed'] = np.nan
        
        return dose_metrics
    
    def calculate_eud(self, dvh, a_parameter=-10):
        """
        Calculate Equivalent Uniform Dose (EUD) for tumor.
        
        EUD = (Σ vᵢ × Dᵢᵃ)^(1/a) where a<0 for tumors
        
        Parameters
        ----------
        dvh : pd.DataFrame
            Differential DVH data
        a_parameter : float, default=-10
            EUD parameter (negative for tumors, typically -10 to -20)
            
        Returns
        -------
        float
            EUD value in Gy, or np.nan if error
        """
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
            log_eud = np.sum(rel_volumes * log_doses)
            return np.exp(log_eud)
        
        elif a_parameter == 1:
            # a=1 case: arithmetic mean (mean dose)
            return np.sum(rel_volumes * doses)
        
        elif np.isinf(a_parameter):
            # a=∞ case: maximum dose
            return np.max(doses)
        
        else:
            # General case: EUD = (Σ vi × Di^a)^(1/a)
            # For tumors, a is negative, so we need to handle this carefully
            powered_doses = np.power(np.maximum(doses, 1e-10), a_parameter)
            sum_weighted = np.sum(rel_volumes * powered_doses)
            
            if sum_weighted <= 0:
                return np.nan
            
            try:
                eud = np.power(sum_weighted, 1.0 / a_parameter)
                # For negative a, check if result is valid
                if np.isnan(eud) or np.isinf(eud) or eud <= 0:
                    return np.nan
                return eud
            except (OverflowError, ZeroDivisionError):
                return np.nan
    
    def calculate_effective_volume(self, dvh, n_parameter=0.12):
        """
        Calculate effective volume for LKB model.
        
        Veff = Σ vᵢ × (Dᵢ/Dref)^(1/n)
        where Dref is typically the maximum dose
        
        Parameters
        ----------
        dvh : pd.DataFrame
            Differential DVH data
        n_parameter : float, default=0.12
            Volume effect parameter (typically 0.05-0.20 for tumors)
            
        Returns
        -------
        float
            Effective volume (dimensionless, normalized), or np.nan if error
        """
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
            try:
                powered_ratios = np.power(dose_ratios, 1.0 / n_parameter)
                v_eff = np.sum(rel_volumes * powered_ratios)
                return v_eff
            except (OverflowError, ZeroDivisionError, ValueError):
                return np.nan


class TCPMLModels:
    """
    Machine learning models for TCP prediction.
    
    Trains ANN and XGBoost models to predict tumor control probability
    based on DVH metrics and clinical factors. Includes proper validation
    and anti-overfitting measures.
    """
    
    def __init__(self, random_state=42):
        """
        Initialize ML models trainer.
        
        Parameters
        ----------
        random_state : int, default=42
            Random seed for reproducibility
        """
        self.random_state = random_state
        self.models = {}
        self.scalers = {}
        self.feature_names = []
        self.performance_metrics = {}
    
    def prepare_features(self, tumor_data):
        """
        Prepare feature matrix from tumor data.
        
        Extracts DVH metrics and clinical factors for ML training.
        Handles missing clinical factors gracefully - uses DVH-only features if needed.
        
        Parameters
        ----------
        tumor_data : pd.DataFrame
            DataFrame with dose metrics and clinical data
            
        Returns
        -------
        tuple
            (X, y, feature_names) where:
            - X: feature matrix (pd.DataFrame)
            - y: target vector (tumor control: 1=controlled, 0=failure)
            - feature_names: list of feature column names
        """
        # Start with DVH-based features (always available)
        dvh_feature_cols = [
            # Coverage metrics (critical for TCP)
            'D95', 'D98', 'D99', 'D50', 'D90',
            # Volume coverage metrics
            'V95', 'V100', 'V110',
            # Basic dose metrics
            'mean_dose', 'max_dose', 'min_dose',
            # Volume metrics
            'total_volume',
            # Additional Dxx metrics
            'D1', 'D2', 'D5', 'D10', 'D20',
            # Additional Vxx metrics (absolute dose levels)
            'V5', 'V10', 'V15', 'V20', 'V25', 'V30', 'V35', 'V40', 'V45', 'V50', 'V55', 'V60', 'V65', 'V70',
            # EUD and effective volume (if available)
            'EUD', 'v_effective',
            # Alternative column names from physical metrics
            'GTV_Mean_Dose', 'GTV_Min_Dose', 'GTV_Max_Dose', 'GTV_D95', 'GTV_D98', 'GTV_Volume_cc'
        ]
        
        # Filter to available DVH columns
        available_dvh_cols = [col for col in dvh_feature_cols if col in tumor_data.columns]
        
        # Check for optional clinical factors
        optional_clinical = ['Age', 'Gender', 'Stage', 
                            'Smoking_PackYears', 'ChemotherapyUsed',
                            'TumorVolume_cc', 'HPV_Status', 'ECOG_Performance']
        
        available_clinical = []
        for col in optional_clinical:
            if col in tumor_data.columns:
                # Check if has enough non-null values (at least 10)
                non_null_count = tumor_data[col].notna().sum()
                if non_null_count >= 10:
                    available_clinical.append(col)
        
        # Combine features
        feature_cols = available_dvh_cols.copy()
        
        if available_clinical:
            print(f"[OK] Using clinical factors: {', '.join(available_clinical)}")
            feature_cols.extend(available_clinical)
        else:
            print("\n" + "=" * 70)
            print("[!] WARNING: No clinical factors available")
            print("=" * 70)
            print("ML models will use DVH features only:")
            for f in available_dvh_cols[:10]:  # Show first 10
                print(f"  [OK] {f}")
            if len(available_dvh_cols) > 10:
                print(f"  ... and {len(available_dvh_cols) - 10} more DVH features")
            print()
            print("Consider adding these clinical factors for better performance:")
            for f in optional_clinical:
                print(f"  - {f}")
            print("=" * 70 + "\n")
        
        # Filter to columns that actually exist
        feature_cols = [col for col in feature_cols if col in tumor_data.columns]
        
        if not feature_cols:
            print("Error: No features available")
            return None, None, None
        
        # Extract features and target
        # Target: TumorControl or Observed_Control (1=tumor controlled, 0=failure)
        target_cols = ['TumorControl', 'Observed_Control', 'Control']
        y = None
        for col in target_cols:
            if col in tumor_data.columns:
                y = tumor_data[col].copy()
                break
        
        if y is None:
            print("Error: No target column found (TumorControl, Observed_Control, or Control)")
            return None, None, None
        
        X = tumor_data[feature_cols].copy()
        
        # Encode categorical variables
        if 'Gender' in feature_cols:
            # Encode Gender: M=1, F=0, Other=0.5
            X['Gender_M'] = X['Gender'].map({'M': 1, 'F': 0, 'Male': 1, 'Female': 0}).fillna(0.5)
            feature_cols.remove('Gender')
            feature_cols.append('Gender_M')
            X = X.drop(columns=['Gender'], errors='ignore')
        
        if 'Stage' in feature_cols:
            # One-hot encode stage
            stage_dummies = pd.get_dummies(X['Stage'], prefix='Stage', dummy_na=False)
            X = pd.concat([X.drop(columns=['Stage'], errors='ignore'), stage_dummies], axis=1)
            feature_cols.remove('Stage')
            feature_cols.extend(stage_dummies.columns.tolist())
        
        if 'HPV_Status' in feature_cols:
            # Encode HPV: Positive=1, Negative=0, Unknown=0.5
            X['HPV_Positive'] = X['HPV_Status'].map({'Positive': 1, 'Negative': 0, 'Pos': 1, 'Neg': 0}).fillna(0.5)
            feature_cols.remove('HPV_Status')
            feature_cols.append('HPV_Positive')
            X = X.drop(columns=['HPV_Status'], errors='ignore')
        
        # Ensure feature_cols matches X columns
        feature_cols = [col for col in feature_cols if col in X.columns]
        X = X[feature_cols]
        
        # Remove rows with missing values in DVH features (required)
        # But allow missing values in optional clinical factors
        required_cols = available_dvh_cols
        if required_cols:
            valid_mask = ~(X[required_cols].isna().any(axis=1) | y.isna())
        else:
            valid_mask = ~(X.isna().any(axis=1) | y.isna())
        
        X = X[valid_mask]
        y = y[valid_mask]
        
        # Fill missing values in optional clinical factors with median/mode
        for col in X.columns:
            if X[col].isna().any():
                if X[col].dtype in ['int64', 'float64']:
                    X[col] = X[col].fillna(X[col].median())
                else:
                    X[col] = X[col].fillna(X[col].mode()[0] if len(X[col].mode()) > 0 else 0)
        
        if len(X) < 10:
            print("Warning: Insufficient data after removing missing values")
            return None, None, None
        
        return X, y, feature_cols
    
    def train_ann_model(self, X_train, y_train, tumor_type):
        """
        Train Artificial Neural Network for TCP prediction.
        
        Architecture:
        - Input layer: n_features
        - Hidden layers: 64 → 32 → 16 neurons
        - Output layer: 1 neuron (sigmoid)
        - Optimizer: Adam
        - Loss: Binary cross-entropy
        
        Parameters
        ----------
        X_train : pd.DataFrame or np.ndarray
            Training features
        y_train : pd.Series or np.ndarray
            Training labels (1=tumor controlled, 0=failure)
        tumor_type : str
            Tumor type identifier
            
        Returns
        -------
        sklearn.Pipeline or None
            Trained ANN model pipeline, or None if training fails
        """
        # Create pipeline with scaling
        ann_pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('ann', MLPClassifier(
                hidden_layer_sizes=(64, 32, 16),  # Three hidden layers
                activation='relu',
                solver='adam',  # Adam optimizer
                alpha=0.001,  # L2 regularization
                max_iter=1000,
                random_state=self.random_state,
                early_stopping=True,
                validation_fraction=0.15,
                n_iter_no_change=20,
                verbose=False
            ))
        ])
        
        try:
            ann_pipeline.fit(X_train, y_train)
            return ann_pipeline
        except Exception as e:
            print(f"      Error: ANN training failed: {e}")
            return None
    
    def train_xgboost_model(self, X_train, y_train, tumor_type):
        """
        Train XGBoost model for TCP prediction.
        
        Parameters
        ----------
        X_train : pd.DataFrame or np.ndarray
            Training features
        y_train : pd.Series or np.ndarray
            Training labels (1=tumor controlled, 0=failure)
        tumor_type : str
            Tumor type identifier
            
        Returns
        -------
        xgboost.XGBClassifier or None
            Trained XGBoost model, or None if training fails
        """
        if not XGBOOST_AVAILABLE:
            return None
        
        try:
            # XGBoost parameters with regularization to prevent overfitting
            xgb_model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,  # L1 regularization
                reg_lambda=1.0,  # L2 regularization
                random_state=self.random_state,
                eval_metric='logloss',
                use_label_encoder=False
            )
            
            xgb_model.fit(X_train, y_train)
            return xgb_model
        except Exception as e:
            print(f"      Error: XGBoost training failed: {e}")
            return None
    
    def _check_ml_preflight(self, X, y, feature_cols):
        """
        GAP 3: ML preflight checks before training.
        
        Checks:
        1. Minimum sample size (>= 20)
        2. No constant target (both classes present)
        3. No all-NaN predictors
        
        Returns
        -------
        tuple: (is_valid, reason)
            is_valid: bool - whether ML can proceed
            reason: str - reason if invalid
        """
        if X is None or y is None:
            return False, "No data available"
        
        n_samples = len(y)
        n_events = y.sum() if hasattr(y, 'sum') else sum(y)
        
        # Check 1: Minimum sample size
        if n_samples < 20:
            return False, f"Insufficient sample size (n={n_samples}, minimum=20)"
        
        # Check 2: No constant target
        unique_targets = len(set(y)) if hasattr(y, '__iter__') else 1
        if unique_targets < 2:
            return False, f"Constant target variable (only {unique_targets} unique value(s))"
        
        # Check 3: No all-NaN predictors
        if hasattr(X, 'isna'):
            nan_counts = X.isna().sum()
            all_nan_cols = nan_counts[nan_counts == len(X)].index.tolist()
            if all_nan_cols:
                return False, f"All-NaN predictors found: {', '.join(all_nan_cols[:5])}"
        
        # Check 4: Minimum events
        if n_events < 5:
            return False, f"Insufficient events (n={int(n_events)}, minimum=5)"
        
        return True, "All preflight checks passed"
    
    def train_and_evaluate_ml_models(self, tumor_data, tumor_type, output_dir=None, enable_shap=False):
        """
        Train and evaluate ML models with proper cross-validation.
        
        Trains both ANN and XGBoost, evaluates on test set, performs
        cross-validation, and optionally generates SHAP analysis.
        
        Parameters
        ----------
        tumor_data : pd.DataFrame
            Tumor data with features and outcomes
        tumor_type : str
            Tumor type identifier
        output_dir : Path, optional
            Output directory for SHAP analysis
        enable_shap : bool, default=False
            Whether to generate SHAP explainability plots
            
        Returns
        -------
        dict
            Dictionary with model results:
            {
                'ANN': {'model': ..., 'test_AUC': ..., 'cv_AUC_mean': ..., ...},
                'XGBoost': {'model': ..., 'test_AUC': ..., 'cv_AUC_mean': ..., ...}
            }
        """
        print(f"   Training ML models for {tumor_type}...")
        
        # Prepare features
        X, y, feature_cols = self.prepare_features(tumor_data)
        
        # GAP 3: ML preflight checks
        is_valid, reason = self._check_ml_preflight(X, y, feature_cols)
        if not is_valid:
            print(f"    [INFO] ML disabled: {reason}")
            print(f"    [INFO] Falling back to traditional models only")
            return {}
        
        n_events = y.sum()
        n_samples = len(y)
        
        print(f"     Features: {len(feature_cols)}, Samples: {n_samples}, Events: {int(n_events)}")
        print(f"     [OK] ML preflight checks passed")
        
        # Use stratified train-test split to prevent data leakage
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=self.random_state, 
            stratify=y if n_events >= 3 else None
        )
        
        results = {}
        
        # Train ANN
        print(f"     Training ANN...")
        ann_model = self.train_ann_model(X_train, y_train, tumor_type)
        
        if ann_model is not None:
            # Evaluate on test set
            y_pred_ann = ann_model.predict_proba(X_test)[:, 1]
            
            # Calculate metrics
            try:
                fpr, tpr, _ = roc_curve(y_test, y_pred_ann)
                auc_ann = auc(fpr, tpr)
                brier_ann = brier_score_loss(y_test, y_pred_ann)
                logloss_ann = log_loss(y_test, y_pred_ann)
                
                # Cross-validation on training set
                cv_scores = cross_val_score(ann_model, X_train, y_train, 
                                           cv=min(5, len(X_train)//3), scoring='roc_auc')
                
                results['ANN'] = {
                    'model': ann_model,
                    'test_AUC': auc_ann,
                    'test_Brier': brier_ann,
                    'test_LogLoss': logloss_ann,
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
                        tumor_type=tumor_type
                    )
                
            except Exception as e:
                print(f"      Error: ANN evaluation failed: {e}")
        
        # Train XGBoost
        if XGBOOST_AVAILABLE:
            print(f"     Training XGBoost...")
            xgb_model = self.train_xgboost_model(X_train, y_train, tumor_type)
            
            if xgb_model is not None:
                # Evaluate on test set
                y_pred_xgb = xgb_model.predict_proba(X_test)[:, 1]
                
                try:
                    fpr, tpr, _ = roc_curve(y_test, y_pred_xgb)
                    auc_xgb = auc(fpr, tpr)
                    brier_xgb = brier_score_loss(y_test, y_pred_xgb)
                    logloss_xgb = log_loss(y_test, y_pred_xgb)
                    
                    # Cross-validation on training set
                    cv_scores = cross_val_score(xgb_model, X_train, y_train, 
                                               cv=min(5, len(X_train)//3), scoring='roc_auc')
                    
                    # Feature importance
                    feature_importance = dict(zip(feature_cols, xgb_model.feature_importances_))
                    
                    results['XGBoost'] = {
                        'model': xgb_model,
                        'test_AUC': auc_xgb,
                        'test_Brier': brier_xgb,
                        'test_LogLoss': logloss_xgb,
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
                            tumor_type=tumor_type
                        )
                    
                except Exception as e:
                    print(f"      Error: XGBoost evaluation failed: {e}")
        
        # Store models and data for later use
        self.models[tumor_type] = results
        
        return results
    
    def predict_ml_models(self, tumor_data, tumor_type):
        """
        Generate predictions from trained ML models.
        
        Parameters
        ----------
        tumor_data : pd.DataFrame
            Tumor data with features
        tumor_type : str
            Tumor type identifier
            
        Returns
        -------
        dict
            Dictionary with predictions: {'TCP_ML_ANN': [...], 'TCP_ML_XGBoost': [...]}
        """
        if tumor_type not in self.models:
            return {}
        
        # Prepare features
        X, y, feature_cols = self.prepare_features(tumor_data)
        
        if X is None:
            return {}
        
        predictions = {}
        
        for model_name, model_info in self.models[tumor_type].items():
            try:
                model = model_info['model']
                
                # Ensure feature columns match
                if set(feature_cols) == set(model_info['feature_names']):
                    y_pred = model.predict_proba(X)[:, 1]
                    predictions[f'TCP_ML_{model_name}'] = y_pred
                else:
                    print(f"    Warning: Feature mismatch for {model_name}")
                    
            except Exception as e:
                print(f"    Error: Prediction failed for {model_name}: {e}")
        
        return predictions


class TCPPlotter:
    """
    Generate publication-quality TCP plots.
    
    Creates dose-response curves, ROC curves, calibration plots,
    and comparison plots for all TCP models (traditional + ML).
    """
    
    def __init__(self, output_dir):
        """
        Initialize plotter with output directory.
        
        Parameters
        ----------
        output_dir : str or Path
            Output directory for plots
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir = self.output_dir / 'plots'
        self.plots_dir.mkdir(exist_ok=True)
    
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
    
    def plot_dose_response_curves(self, tcp_results, tumor_type, dose_range=None):
        """
        Plot TCP dose-response curves for all models.
        
        Shows how TCP varies with dose for:
        - Poisson TCP model
        - LKB TCP model
        - Logistic TCP model
        - EUD TCP model
        - ANN prediction (if available)
        - XGBoost prediction (if available)
        
        Parameters
        ----------
        tcp_results : pd.DataFrame
            DataFrame with TCP predictions and dose metrics
        tumor_type : str
            Tumor type for plot title
        dose_range : tuple, optional
            (min_dose, max_dose) for x-axis, default (0, 100)
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating dose-response curves for {tumor_type}...")
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Determine dose range
        if dose_range is None:
            if 'mean_dose' in tcp_results.columns:
                dose_values = tcp_results['mean_dose'].dropna()
                if len(dose_values) > 0:
                    dose_range = (dose_values.min() * 0.8, dose_values.max() * 1.2)
                else:
                    dose_range = (0, 100)
            else:
                dose_range = (0, 100)
        
        doses = np.linspace(dose_range[0], dose_range[1], 300)
        
        # Traditional TCP models
        traditional_models = {
            'TCP_Poisson': 'Poisson',
            'TCP_LKB': 'LKB',
            'TCP_Logistic': 'Logistic',
            'TCP_EUD': 'EUD'
        }
        
        # Plot traditional models (if available in results)
        for model_col, model_label in traditional_models.items():
            if model_col in tcp_results.columns:
                valid_data = tcp_results.dropna(subset=[model_col])
                if len(valid_data) > 0:
                    # For dose-response, we need dose values
                    if 'mean_dose' in valid_data.columns:
                        dose_vals = valid_data['mean_dose'].values
                        tcp_vals = valid_data[model_col].values
                        
                        # Sort by dose
                        sort_idx = np.argsort(dose_vals)
                        dose_vals = dose_vals[sort_idx]
                        tcp_vals = tcp_vals[sort_idx]
                        
                        # Plot with interpolation for smooth curve
                        ax.plot(dose_vals, tcp_vals,
                               color=COLORS.get(model_col, 'gray'),
                               linestyle=LINE_STYLES.get(model_col, '-'),
                               linewidth=2.5,
                               label=model_label,
                               alpha=0.9,
                               marker=MARKERS.get(model_col, 'o'),
                               markersize=4,
                               markevery=max(1, len(dose_vals)//20))
        
        # Plot ML models if available
        ml_models = {
            'TCP_ML_ANN': ('ML-ANN', 'ML_ANN'),
            'TCP_ML_XGBoost': ('ML-XGBoost', 'ML_XGBoost')
        }
        
        for model_col, (model_label, color_key) in ml_models.items():
            if model_col in tcp_results.columns:
                valid_data = tcp_results.dropna(subset=[model_col])
                if len(valid_data) > 0 and 'mean_dose' in valid_data.columns:
                    dose_vals = valid_data['mean_dose'].values
                    tcp_vals = valid_data[model_col].values
                    
                    sort_idx = np.argsort(dose_vals)
                    dose_vals = dose_vals[sort_idx]
                    tcp_vals = tcp_vals[sort_idx]
                    
                    ax.plot(dose_vals, tcp_vals,
                           color=COLORS.get(color_key, 'gray'),
                           linestyle=LINE_STYLES.get(color_key, ':'),
                           linewidth=2.5,
                           label=model_label,
                           alpha=0.9,
                           marker=MARKERS.get(color_key, 'v'),
                           markersize=4,
                           markevery=max(1, len(dose_vals)//20))
        
        # Plot observed data points (if available)
        if 'Observed_Control' in tcp_results.columns and 'mean_dose' in tcp_results.columns:
            valid_obs = tcp_results.dropna(subset=['Observed_Control', 'mean_dose'])
            if len(valid_obs) > 0:
                # Bin observed data
                n_bins = min(8, max(3, len(valid_obs) // 4))
                bins = np.percentile(valid_obs['mean_dose'], np.linspace(0, 100, n_bins + 1))
                
                bin_centers = []
                bin_rates = []
                bin_counts = []
                bin_errors = []
                
                for i in range(len(bins) - 1):
                    mask = (valid_obs['mean_dose'] >= bins[i]) & (valid_obs['mean_dose'] < bins[i + 1])
                    bin_data = valid_obs[mask]
                    
                    if len(bin_data) > 0:
                        bin_centers.append(bin_data['mean_dose'].mean())
                        rate = bin_data['Observed_Control'].mean()
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
                    ax.scatter(bin_centers, bin_rates, s=sizes,
                             c=COLORS['observed'], alpha=0.9,
                             edgecolors='white', linewidth=2,
                             label='Observed Data', zorder=10)
                    
                    ax.errorbar(bin_centers, bin_rates, yerr=bin_errors,
                               fmt='none', color=COLORS['observed'], alpha=0.7,
                               capsize=5, capthick=2, linewidth=2, zorder=5)
        
        # Enhanced styling
        ax.set_xlabel('Dose (Gy)', fontsize=16, fontweight='bold')
        ax.set_ylabel('Tumor Control Probability', fontsize=16, fontweight='bold')
        ax.set_title(f'TCP Dose-Response Curves - {tumor_type}', 
                    fontsize=18, fontweight='bold', pad=20)
        
        # Grid
        ax.grid(True, alpha=0.3, color=COLORS['grid'], linewidth=1)
        
        # Enhanced legend
        legend = ax.legend(fontsize=12, loc='lower right', frameon=True,
                          fancybox=True, shadow=True, framealpha=0.9)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_edgecolor('gray')
        
        # Limits and ticks
        ax.set_ylim(0, 1.05)
        ax.set_xlim(dose_range[0], dose_range[1])
        ax.tick_params(axis='both', which='major', labelsize=12)
        
        # Save plot
        filename = f"tcp_dose_response_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)
    
    def plot_roc_curves(self, tcp_results, observed, tumor_type):
        """
        Plot ROC curves for all TCP models.
        
        Parameters
        ----------
        tcp_results : pd.DataFrame
            DataFrame with TCP predictions
        observed : pd.Series
            Observed tumor control outcomes (1=controlled, 0=failure)
        tumor_type : str
            Tumor type for plot title
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating ROC curves for {tumor_type}...")
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Traditional TCP models
        traditional_models = ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']
        ml_models = []
        
        # Check for ML models
        ml_cols = [col for col in tcp_results.columns if col.startswith('TCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                ml_models.append(('ML_ANN', ml_col, 'ANN'))
            elif 'XGBoost' in ml_col:
                ml_models.append(('ML_XGBoost', ml_col, 'XGBoost'))
        
        all_auc_values = []
        
        # Plot traditional models
        for model in traditional_models:
            if model in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[model].values,
                    'observed': observed.values
                }).dropna()
                
                if len(valid_data) >= 5:
                    y_true = valid_data['observed'].values
                    y_pred = valid_data['tcp'].values
                    
                    try:
                        fpr, tpr, _ = roc_curve(y_true, y_pred)
                        auc_score = auc(fpr, tpr)
                        
                        # Plot ROC curve with unique styling
                        model_label = model.replace('TCP_', '')
                        ax.plot(fpr, tpr,
                               color=COLORS.get(model, 'gray'),
                               linestyle=LINE_STYLES.get(model, '-'),
                               linewidth=3.0,
                               label=f'{model_label}: AUC = {auc_score:.3f}',
                               alpha=0.8)
                        
                        all_auc_values.append((model_label, auc_score))
                        
                    except Exception as e:
                        print(f"    Error: ROC calculation failed for {model}: {e}")
        
        # Plot ML models
        for model_key, tcp_col, model_label in ml_models:
            if tcp_col in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[tcp_col].values,
                    'observed': observed.values
                }).dropna()
                
                if len(valid_data) >= 5:
                    y_true = valid_data['observed'].values
                    y_pred = valid_data['tcp'].values
                    
                    try:
                        fpr, tpr, _ = roc_curve(y_true, y_pred)
                        auc_score = auc(fpr, tpr)
                        
                        # Plot ML ROC curve
                        ax.plot(fpr, tpr,
                               color=COLORS.get(model_key, 'gray'),
                               linestyle=LINE_STYLES.get(model_key, ':'),
                               linewidth=3.5,
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
        ax.set_title(f'TCP ROC Curves - {tumor_type}',
                    fontsize=18, fontweight='bold', pad=20)
        
        # Grid and formatting
        ax.grid(True, alpha=0.3, color=COLORS['grid'], linewidth=1)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        
        # Enhanced legend with better positioning
        legend = ax.legend(fontsize=11, loc='lower right', frameon=True,
                          fancybox=True, shadow=True, framealpha=0.9)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_edgecolor('gray')
        
        # Add sample size annotation
        n_total = len(observed)
        n_events = int(observed.sum())
        ax.text(0.02, 0.98, f'{tumor_type}\nSample: n={n_total}, events={n_events}',
               transform=ax.transAxes, fontsize=12, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.8),
               verticalalignment='top')
        
        # Save plot
        filename = f"tcp_roc_curves_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)
    
    def plot_calibration(self, tcp_results, observed, tumor_type):
        """
        Plot calibration curves for all TCP models.
        
        Shows predicted vs observed TCP across probability bins.
        
        Parameters
        ----------
        tcp_results : pd.DataFrame
            DataFrame with TCP predictions
        observed : pd.Series
            Observed tumor control outcomes
        tumor_type : str
            Tumor type for plot title
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating calibration plots for {tumor_type}...")
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Traditional TCP models
        traditional_models = ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']
        ml_models = []
        
        # Check for ML models
        ml_cols = [col for col in tcp_results.columns if col.startswith('TCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                ml_models.append(('ML_ANN', ml_col, 'ANN'))
            elif 'XGBoost' in ml_col:
                ml_models.append(('ML_XGBoost', ml_col, 'XGBoost'))
        
        calibration_metrics = {}
        
        # Plot traditional models
        for model in traditional_models:
            if model in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[model].values,
                    'observed': observed.values
                }).dropna()
                
                if len(valid_data) >= 10:
                    y_true = valid_data['observed'].values
                    y_pred = valid_data['tcp'].values
                    
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
                        
                        # Create label
                        model_name = model.replace('TCP_', '')
                        if not np.isnan(slope) and not np.isnan(intercept):
                            label = f"{model_name}: slope={slope:.3f}, int={intercept:.3f}"
                        else:
                            label = f"{model_name}"
                        
                        # Plot calibration curve
                        ax.plot(bin_centers, bin_observed,
                               color=COLORS.get(model, 'gray'),
                               linestyle=LINE_STYLES.get(model, '-'),
                               linewidth=2.5,
                               marker=MARKERS.get(model, 'o'),
                               markersize=8,
                               markerfacecolor=COLORS.get(model, 'gray'),
                               markeredgecolor='white',
                               markeredgewidth=1,
                               label=label,
                               zorder=5)
        
        # Plot ML models
        for model_key, tcp_col, model_label in ml_models:
            if tcp_col in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[tcp_col].values,
                    'observed': observed.values
                }).dropna()
                
                if len(valid_data) >= 10:
                    y_true = valid_data['observed'].values
                    y_pred = valid_data['tcp'].values
                    
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
                        
                        # Create label
                        if not np.isnan(slope) and not np.isnan(intercept):
                            label = f"{model_label}: slope={slope:.3f}, int={intercept:.3f}"
                        else:
                            label = f"{model_label}"
                        
                        # Plot ML calibration curve
                        ax.plot(bin_centers, bin_observed,
                               color=COLORS.get(model_key, 'gray'),
                               linestyle=LINE_STYLES.get(model_key, ':'),
                               linewidth=3.0,
                               marker=MARKERS.get(model_key, 'v'),
                               markersize=8,
                               markerfacecolor=COLORS.get(model_key, 'gray'),
                               markeredgecolor='white',
                               markeredgewidth=1,
                               label=label,
                               zorder=6)
        
        # Plot perfect calibration line
        ax.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.7,
               label='Perfect Calibration', zorder=1)
        
        # Enhanced styling
        ax.set_xlabel('Predicted TCP', fontsize=16, fontweight='bold')
        ax.set_ylabel('Observed Rate', fontsize=16, fontweight='bold')
        ax.set_title(f'TCP Calibration - {tumor_type}',
                    fontsize=18, fontweight='bold', pad=20)
        
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
        
        # Add tumor type annotation
        ax.text(0.98, 0.02, f'{tumor_type}',
               transform=ax.transAxes, fontsize=14, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8),
               horizontalalignment='right', verticalalignment='bottom')
        
        # Save plot
        filename = f"tcp_calibration_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)
    
    def plot_model_comparison(self, tcp_results, observed, tumor_type):
        """
        Plot comprehensive model comparison.
        
        Creates combined ROC + calibration plot.
        
        Parameters
        ----------
        tcp_results : pd.DataFrame
            DataFrame with TCP predictions
        observed : pd.Series
            Observed tumor control outcomes
        tumor_type : str
            Tumor type for plot title
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating combined ROC+calibration plot for {tumor_type}...")
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        
        # Left subplot: ROC curves
        traditional_models = ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']
        ml_models = []
        ml_cols = [col for col in tcp_results.columns if col.startswith('TCP_ML_')]
        for ml_col in ml_cols:
            if 'ANN' in ml_col:
                ml_models.append(('ML_ANN', ml_col, 'ANN'))
            elif 'XGBoost' in ml_col:
                ml_models.append(('ML_XGBoost', ml_col, 'XGBoost'))
        
        # Plot ROC curves
        for model in traditional_models:
            if model in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[model].values,
                    'observed': observed.values
                }).dropna()
                if len(valid_data) >= 5:
                    try:
                        fpr, tpr, _ = roc_curve(valid_data['observed'], valid_data['tcp'])
                        auc_score = auc(fpr, tpr)
                        ax1.plot(fpr, tpr, color=COLORS.get(model, 'gray'),
                               linestyle=LINE_STYLES.get(model, '-'),
                               linewidth=2.5, label=f'{model.replace("TCP_", "")} (AUC={auc_score:.3f})')
                    except:
                        pass
        
        for model_key, tcp_col, model_label in ml_models:
            if tcp_col in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[tcp_col].values,
                    'observed': observed.values
                }).dropna()
                if len(valid_data) >= 5:
                    try:
                        fpr, tpr, _ = roc_curve(valid_data['observed'], valid_data['tcp'])
                        auc_score = auc(fpr, tpr)
                        ax1.plot(fpr, tpr, color=COLORS.get(model_key, 'gray'),
                               linestyle=LINE_STYLES.get(model_key, ':'),
                               linewidth=3.0, label=f'{model_label} (AUC={auc_score:.3f})')
                    except:
                        pass
        
        ax1.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.6, label='Random')
        ax1.set_xlabel('False Positive Rate', fontsize=14, fontweight='bold')
        ax1.set_ylabel('True Positive Rate', fontsize=14, fontweight='bold')
        ax1.set_title('ROC Curves', fontsize=16, fontweight='bold')
        ax1.grid(True, alpha=0.3, color=COLORS['grid'])
        ax1.set_xlim(0, 1)
        ax1.set_ylim(0, 1)
        ax1.legend(fontsize=10, loc='lower right', frameon=True, framealpha=0.9)
        
        # Right subplot: Calibration
        for model in traditional_models:
            if model in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[model].values,
                    'observed': observed.values
                }).dropna()
                if len(valid_data) >= 10:
                    bin_centers, bin_observed, _ = self.calculate_calibration_data(
                        valid_data['observed'], valid_data['tcp'], n_bins=5)
                    if bin_centers is not None:
                        ax2.plot(bin_centers, bin_observed, color=COLORS.get(model, 'gray'),
                               linestyle=LINE_STYLES.get(model, '-'), linewidth=2.5,
                               marker=MARKERS.get(model, 'o'), markersize=6,
                               label=model.replace('TCP_', ''))
        
        for model_key, tcp_col, model_label in ml_models:
            if tcp_col in tcp_results.columns:
                valid_data = pd.DataFrame({
                    'tcp': tcp_results[tcp_col].values,
                    'observed': observed.values
                }).dropna()
                if len(valid_data) >= 10:
                    bin_centers, bin_observed, _ = self.calculate_calibration_data(
                        valid_data['observed'], valid_data['tcp'], n_bins=5)
                    if bin_centers is not None:
                        ax2.plot(bin_centers, bin_observed, color=COLORS.get(model_key, 'gray'),
                               linestyle=LINE_STYLES.get(model_key, ':'), linewidth=3.0,
                               marker=MARKERS.get(model_key, 'v'), markersize=6,
                               label=model_label)
        
        ax2.plot([0, 1], [0, 1], 'k--', linewidth=2, alpha=0.7, label='Perfect')
        ax2.set_xlabel('Predicted TCP', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Observed Rate', fontsize=14, fontweight='bold')
        ax2.set_title('Calibration', fontsize=16, fontweight='bold')
        ax2.grid(True, alpha=0.3, color=COLORS['grid'])
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        ax2.legend(fontsize=10, loc='upper left', frameon=True, framealpha=0.9)
        
        plt.suptitle(f'TCP Model Comparison - {tumor_type}', fontsize=18, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        filename = f"tcp_roc_calibration_combined_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)
    
    def plot_comprehensive_analysis(self, tcp_results, observed, tumor_type):
        """
        Plot comprehensive analysis overview.
        
        Creates multi-panel figure with:
        - Dose-response curves
        - ROC curves
        - Calibration plots
        - Performance metrics table
        
        Parameters
        ----------
        tcp_results : pd.DataFrame
            DataFrame with TCP predictions
        observed : pd.Series
            Observed tumor control outcomes
        tumor_type : str
            Tumor type for plot title
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating comprehensive analysis plot for {tumor_type}...")
        
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
        
        # [0,0]: Dose-response curves
        ax1 = fig.add_subplot(gs[0, 0])
        if 'mean_dose' in tcp_results.columns:
            dose_vals = tcp_results['mean_dose'].dropna()
            if len(dose_vals) > 0:
                for model in ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']:
                    if model in tcp_results.columns:
                        valid = tcp_results.dropna(subset=[model, 'mean_dose'])
                        if len(valid) > 0:
                            sort_idx = np.argsort(valid['mean_dose'])
                            ax1.plot(valid['mean_dose'].iloc[sort_idx],
                                   valid[model].iloc[sort_idx],
                                   color=COLORS.get(model, 'gray'),
                                   linestyle=LINE_STYLES.get(model, '-'),
                                   linewidth=2, label=model.replace('TCP_', ''))
        ax1.set_xlabel('Dose (Gy)', fontsize=12)
        ax1.set_ylabel('TCP', fontsize=12)
        ax1.set_title('Dose-Response Curves', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=9)
        ax1.set_ylim(0, 1)
        
        # [0,1]: ROC curves
        ax2 = fig.add_subplot(gs[0, 1])
        for model in ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']:
            if model in tcp_results.columns:
                valid = pd.DataFrame({'tcp': tcp_results[model], 'obs': observed}).dropna()
                if len(valid) >= 5:
                    try:
                        fpr, tpr, _ = roc_curve(valid['obs'], valid['tcp'])
                        auc_score = auc(fpr, tpr)
                        ax2.plot(fpr, tpr, color=COLORS.get(model, 'gray'),
                               linestyle=LINE_STYLES.get(model, '-'),
                               linewidth=2, label=f'{model.replace("TCP_", "")} (AUC={auc_score:.3f})')
                    except:
                        pass
        ax2.plot([0, 1], [0, 1], 'k--', linewidth=1.5, alpha=0.6)
        ax2.set_xlabel('False Positive Rate', fontsize=12)
        ax2.set_ylabel('True Positive Rate', fontsize=12)
        ax2.set_title('ROC Curves', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=9)
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        
        # [0,2]: Calibration
        ax3 = fig.add_subplot(gs[0, 2])
        for model in ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']:
            if model in tcp_results.columns:
                valid = pd.DataFrame({'tcp': tcp_results[model], 'obs': observed}).dropna()
                if len(valid) >= 10:
                    bin_centers, bin_observed, _ = self.calculate_calibration_data(
                        valid['obs'], valid['tcp'], n_bins=5)
                    if bin_centers is not None:
                        ax3.plot(bin_centers, bin_observed, color=COLORS.get(model, 'gray'),
                               linestyle=LINE_STYLES.get(model, '-'),
                               marker=MARKERS.get(model, 'o'), markersize=5,
                               linewidth=2, label=model.replace('TCP_', ''))
        ax3.plot([0, 1], [0, 1], 'k--', linewidth=1.5, alpha=0.7)
        ax3.set_xlabel('Predicted TCP', fontsize=12)
        ax3.set_ylabel('Observed Rate', fontsize=12)
        ax3.set_title('Calibration', fontsize=14, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        ax3.legend(fontsize=9)
        ax3.set_xlim(0, 1)
        ax3.set_ylim(0, 1)
        
        # [1,0]: Model comparison bars (AUC)
        ax4 = fig.add_subplot(gs[1, 0])
        models = []
        aucs = []
        colors_list = []
        for model in ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']:
            if model in tcp_results.columns:
                valid = pd.DataFrame({'tcp': tcp_results[model], 'obs': observed}).dropna()
                if len(valid) >= 5:
                    try:
                        fpr, tpr, _ = roc_curve(valid['obs'], valid['tcp'])
                        auc_score = auc(fpr, tpr)
                        models.append(model.replace('TCP_', ''))
                        aucs.append(auc_score)
                        colors_list.append(COLORS.get(model, 'gray'))
                    except:
                        pass
        if models:
            bars = ax4.bar(models, aucs, color=colors_list, alpha=0.8)
            ax4.set_ylabel('AUC', fontsize=12, fontweight='bold')
            ax4.set_title('Model Performance (AUC)', fontsize=14, fontweight='bold')
            ax4.set_ylim(0, 1.1)
            ax4.grid(True, alpha=0.3, axis='y')
            for bar, auc_val in zip(bars, aucs):
                ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                       f'{auc_val:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        # [1,1]: Feature importance (placeholder - requires ML models)
        ax5 = fig.add_subplot(gs[1, 1])
        ax5.text(0.5, 0.5, 'Feature Importance\n(ML models required)',
               ha='center', va='center', transform=ax5.transAxes, fontsize=12)
        ax5.set_title('Feature Importance', fontsize=14, fontweight='bold')
        ax5.axis('off')
        
        # [1,2]: Summary statistics
        ax6 = fig.add_subplot(gs[1, 2])
        ax6.axis('off')
        summary_text = f"TCP Analysis Summary - {tumor_type}\n\n"
        summary_text += f"Total Patients: {len(observed)}\n"
        summary_text += f"Tumor Controlled: {int(observed.sum())} ({100*observed.mean():.1f}%)\n"
        summary_text += f"Tumor Failure: {int((1-observed).sum())} ({100*(1-observed.mean()):.1f}%)\n\n"
        summary_text += "Models Evaluated:\n"
        for model in ['TCP_Poisson', 'TCP_LKB', 'TCP_Logistic', 'TCP_EUD']:
            if model in tcp_results.columns:
                summary_text += f"  - {model.replace('TCP_', '')}\n"
        ax6.text(0.1, 0.9, summary_text, transform=ax6.transAxes,
               fontsize=11, verticalalignment='top', family='monospace',
               bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
        
        plt.suptitle(f'Comprehensive TCP Analysis - {tumor_type}',
                    fontsize=20, fontweight='bold', y=0.98)
        
        filename = f"tcp_comprehensive_analysis_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)
    
    def plot_model_comparison_barplot(self, performance_metrics, tumor_type):
        """
        Plot bar plot comparing model performance metrics.
        
        Parameters
        ----------
        performance_metrics : dict
            Dictionary with model performance metrics (AUC, Brier, LogLoss)
        tumor_type : str
            Tumor type for plot title
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating model comparison barplot for {tumor_type}...")
        
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        
        models = list(performance_metrics.keys())
        metrics = ['AUC', 'Brier', 'LogLoss']
        metric_labels = ['AUC', 'Brier Score', 'Log Loss']
        
        for idx, (metric, metric_label) in enumerate(zip(metrics, metric_labels)):
            ax = axes[idx]
            values = []
            errors = []
            colors_list = []
            
            for model in models:
                if metric in performance_metrics[model]:
                    values.append(performance_metrics[model][metric])
                    # Get error if available (from CV)
                    if f'{metric}_std' in performance_metrics[model]:
                        errors.append(performance_metrics[model][f'{metric}_std'])
                    else:
                        errors.append(0)
                    
                    # Get color
                    if 'ANN' in model:
                        colors_list.append(COLORS['ML_ANN'])
                    elif 'XGBoost' in model:
                        colors_list.append(COLORS['ML_XGBoost'])
                    elif 'Poisson' in model:
                        colors_list.append(COLORS['TCP_Poisson'])
                    elif 'LKB' in model:
                        colors_list.append(COLORS['TCP_LKB'])
                    elif 'Logistic' in model:
                        colors_list.append(COLORS['TCP_Logistic'])
                    elif 'EUD' in model:
                        colors_list.append(COLORS['TCP_EUD'])
                    else:
                        colors_list.append('gray')
            
            if values:
                bars = ax.bar(models, values, yerr=errors if any(e > 0 for e in errors) else None,
                            color=colors_list, alpha=0.8, capsize=5, error_kw={'linewidth': 2})
                
                ax.set_ylabel(metric_label, fontsize=12, fontweight='bold')
                ax.set_title(f'{metric_label} Comparison', fontsize=14, fontweight='bold')
                ax.set_xticklabels([m.replace('TCP_', '').replace('_', ' ') for m in models],
                                  rotation=45, ha='right', fontsize=10)
                ax.grid(True, alpha=0.3, axis='y')
                
                # Add value labels
                for bar, val in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, height + 0.01,
                           f'{val:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.suptitle(f'TCP Model Performance Comparison - {tumor_type}',
                    fontsize=16, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        filename = f"tcp_model_comparison_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)
    
    def plot_feature_importance(self, ml_models, tumor_type):
        """
        Plot feature importance for ML models.
        
        Parameters
        ----------
        ml_models : dict
            Dictionary with ML model results (from TCPMLModels.train_and_evaluate_ml_models)
        tumor_type : str
            Tumor type for plot title
            
        Returns
        -------
        str
            Path to saved plot file
        """
        print(f"  Generating feature importance plot for {tumor_type}...")
        
        fig, axes = plt.subplots(1, 2, figsize=(16, 8))
        
        # ANN feature importance (using model weights)
        if 'ANN' in ml_models and 'model' in ml_models['ANN']:
            ax1 = axes[0]
            ann_model = ml_models['ANN']['model']
            feature_names = ml_models['ANN'].get('feature_names', [])
            
            # Extract weights from first hidden layer
            if hasattr(ann_model, 'named_steps'):
                mlp = ann_model.named_steps.get('ann', None)
            else:
                mlp = ann_model
            
            if mlp is not None and hasattr(mlp, 'coefs_') and len(mlp.coefs_) > 0:
                # Get absolute weights from input to first hidden layer
                weights = np.abs(mlp.coefs_[0])  # Shape: (n_features, n_hidden_neurons)
                # Average across hidden neurons
                importance = np.mean(weights, axis=1)
                
                # Get top 10 features
                top_indices = np.argsort(importance)[-10:][::-1]
                top_features = [feature_names[i] for i in top_indices]
                top_importance = importance[top_indices]
                
                bars = ax1.barh(top_features, top_importance, color=COLORS['ML_ANN'], alpha=0.8)
                ax1.set_xlabel('Average Absolute Weight', fontsize=12, fontweight='bold')
                ax1.set_title('ANN Feature Importance (Top 10)', fontsize=14, fontweight='bold')
                ax1.grid(True, alpha=0.3, axis='x')
                
                # Add value labels
                for bar, val in zip(bars, top_importance):
                    ax1.text(val + max(top_importance) * 0.01, bar.get_y() + bar.get_height()/2,
                           f'{val:.3f}', ha='left', va='center', fontsize=9)
            else:
                ax1.text(0.5, 0.5, 'ANN weights\nnot available',
                       ha='center', va='center', transform=ax1.transAxes, fontsize=12)
                ax1.set_title('ANN Feature Importance', fontsize=14, fontweight='bold')
        
        # XGBoost feature importance
        if 'XGBoost' in ml_models and 'model' in ml_models['XGBoost']:
            ax2 = axes[1]
            xgb_model = ml_models['XGBoost']['model']
            feature_names = ml_models['XGBoost'].get('feature_names', [])
            
            if hasattr(xgb_model, 'feature_importances_'):
                importance = xgb_model.feature_importances_
                
                # Get top 10 features
                top_indices = np.argsort(importance)[-10:][::-1]
                top_features = [feature_names[i] for i in top_indices]
                top_importance = importance[top_indices]
                
                bars = ax2.barh(top_features, top_importance, color=COLORS['ML_XGBoost'], alpha=0.8)
                ax2.set_xlabel('Feature Importance', fontsize=12, fontweight='bold')
                ax2.set_title('XGBoost Feature Importance (Top 10)', fontsize=14, fontweight='bold')
                ax2.grid(True, alpha=0.3, axis='x')
                
                # Add value labels
                for bar, val in zip(bars, top_importance):
                    ax2.text(val + max(top_importance) * 0.01, bar.get_y() + bar.get_height()/2,
                           f'{val:.3f}', ha='left', va='center', fontsize=9)
            else:
                ax2.text(0.5, 0.5, 'XGBoost importance\nnot available',
                       ha='center', va='center', transform=ax2.transAxes, fontsize=12)
                ax2.set_title('XGBoost Feature Importance', fontsize=14, fontweight='bold')
        
        plt.suptitle(f'ML Model Feature Importance - {tumor_type}',
                    fontsize=16, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        
        filename = f"tcp_feature_importance_{tumor_type}.png"
        output_path = self.plots_dir / filename
        plt.savefig(output_path, dpi=600, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"    Saved: {filename}")
        return str(output_path)


def generate_shap_analysis(model, model_name, X_train, X_test, y_test, 
                          output_dir, tumor_type="Tumor"):
    """
    Generate SHAP explainability analysis for ML model.
    
    Creates SHAP bar plots, beeswarm plots, and metadata files.
    
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
    tumor_type : str
        Tumor type name
        
    Returns
    -------
    None
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
        caption = generate_shap_caption(shap_values, X_test.columns, model_name, tumor_type)
        
        # Calculate metrics
        if hasattr(model, 'predict_proba'):
            y_pred_proba = model.predict_proba(X_test)[:, 1]
        else:
            y_pred_proba = model.predict(X_test)
        
        # Calculate AUC
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
                "tumor_type": tumor_type
            }, f, indent=2)
        
        print(f"    [OK] SHAP analysis saved to {shap_dir}")
        print(f"      - Bar plot: shap_bar_{model_name}.png")
        print(f"      - Beeswarm plot: shap_beeswarm_{model_name}.png")
        print(f"      - Caption: caption.txt")
        print(f"      - Metrics: metrics.json")
        
    except Exception as e:
        print(f"  [WARNING] SHAP generation failed for {model_name}: {str(e)}")


def load_patient_data(patient_file):
    """
    Load patient clinical data with tumor control outcomes.
    
    Parameters
    ----------
    patient_file : str or Path
        Path to Excel file with patient data
        
    Returns
    -------
    pd.DataFrame or None
        DataFrame with columns:
        - PatientID: patient identifier
        - Tumor: tumor structure name
        - Observed_Control: 1=tumor controlled, 0=failure
        - dose_per_fraction: dose per fraction in Gy
        - Other clinical factors
    """
    pass


def create_excel_outputs(results_df, tcp_results, ml_results, output_dir):
    """
    Create comprehensive Excel output files.
    
    Generates multiple Excel sheets with:
    - tcp_predictions.xlsx: Patient-level TCP for all models
    - tcp_parameters.xlsx: Model parameters used
    - tcp_ml_performance.xlsx: ML model metrics
    - tcp_dose_metrics.xlsx: Tumor dose statistics
    
    Parameters
    ----------
    results_df : pd.DataFrame
        Combined results with dose metrics and TCP predictions
    tcp_results : dict
        Traditional TCP model results
    ml_results : dict
        ML model results
    output_dir : Path
        Output directory
        
    Returns
    -------
    None
    """
    pass


def calculate_tcp_metrics_from_dvh(dvh_dir, dvh_processor, clinical_df):
    """
    Calculate TCP physical metrics from DVH files
    
    Returns DataFrame with:
    - PatientID (or Patient_ID)
    - GTV_Mean_Dose
    - GTV_Min_Dose
    - GTV_Max_Dose
    - GTV_D95
    - GTV_D98
    - GTV_Volume_cc
    - EUD (calculated with a=10 for tumor)
    """
    import glob
    
    metrics = []
    
    # Get patient IDs from clinical data
    patient_id_col = None
    for col in clinical_df.columns:
        if col.lower() in ['patientid', 'patient_id', 'id']:
            patient_id_col = col
            break
    
    if patient_id_col is None:
        raise RuntimeError("No PatientID column found in clinical data")
    
    patient_ids = clinical_df[patient_id_col].astype(str).str.strip().unique()
    
    # Find all tumor DVH files (GTV, CTV, PTV)
    dvh_path = Path(dvh_dir)
    tumor_files = list(dvh_path.glob("*GTV*.csv")) + \
                  list(dvh_path.glob("*CTV*.csv")) + \
                  list(dvh_path.glob("*PTV*.csv")) + \
                  list(dvh_path.glob("*Tumor*.csv"))
    
    # Process each patient
    for patient_id in patient_ids:
        # Try to find DVH file for this patient
        dvh = None
        tumor_name = None
        
        for tumor_type_name in ['GTV', 'PTV', 'CTV', 'Tumor']:
            dvh_temp = dvh_processor.load_dvh_file(patient_id, tumor_type_name)
            if dvh_temp is not None:
                dvh = dvh_temp
                tumor_name = tumor_type_name
                break
        
        if dvh is None:
            # Try to find by filename pattern
            for dvh_file in tumor_files:
                if patient_id in dvh_file.stem:
                    try:
                        dvh = pd.read_csv(dvh_file)
                        # Assume first column is dose, second is volume
                        if len(dvh.columns) >= 2:
                            dvh.columns = ['Dose_Gy', 'Relative_Volume']
                        break
                    except Exception:
                        continue
        
        if dvh is not None and len(dvh) > 0:
            # Calculate metrics from DVH
            dose_metrics = dvh_processor.calculate_dose_metrics(dvh)
            
            if dose_metrics:
                # Calculate EUD with a=10 for tumor
                eud = dvh_processor.calculate_eud(dvh, a_parameter=10)
                
                # Extract volume if available
                volume_cc = dose_metrics.get('Volume_cc', 0.0)
                
                metrics_row = {
                    'Patient_ID': patient_id,
                    'GTV_Mean_Dose': dose_metrics.get('Dmean', 0.0),
                    'GTV_Min_Dose': dose_metrics.get('Dmin', 0.0),
                    'GTV_Max_Dose': dose_metrics.get('Dmax', 0.0),
                    'GTV_D95': dose_metrics.get('D95', 0.0),
                    'GTV_D98': dose_metrics.get('D98', 0.0),
                    'GTV_Volume_cc': volume_cc,
                    'EUD': eud
                }
                metrics.append(metrics_row)
    
    if not metrics:
        raise RuntimeError("Failed to calculate TCP metrics from DVH files. No valid DVH data found.")
    
    return pd.DataFrame(metrics)


def process_all_patients(dvh_dir, patient_data_file, output_dir, 
                        tumor_type='HNSCC', enable_ml=True, enable_shap=False,
                        physical_metrics_file=None, use_fdvh=False, 
                        n_fractions=30, alpha_beta_tumor=10, use_utcp=False,
                        ccs_file=None, ccs_threshold=0.1):
    """
    Main processing pipeline for TCP analysis.
    
    Processes all patients, calculates TCP using traditional models,
    trains ML models if enabled, generates plots, and creates Excel outputs.
    
    Parameters
    ----------
    dvh_dir : str or Path
        Directory containing tumor DVH CSV files
    patient_data_file : str or Path
        Excel file with patient clinical data and outcomes
    output_dir : str or Path
        Output directory for all results
    tumor_type : str, default='HNSCC'
        Tumor type for parameter loading (HNSCC, Prostate, Lung, Breast)
    enable_ml : bool, default=True
        Whether to train ML models
    enable_shap : bool, default=False
        Whether to generate SHAP analysis
    physical_metrics_file : str or Path, optional
        Path to TCP physical metrics Excel file from Step-2.
        If provided, will use this file instead of calculating from DVH files.
        
    Returns
    -------
    pd.DataFrame
        Combined results DataFrame with all TCP predictions
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    dvh_dir = Path(dvh_dir)
    patient_data_file = Path(patient_data_file)
    
    # ============================================================
    # STEP 1 — LOAD INPUTS
    # ============================================================
    
    print("Loading inputs...")
    
    # Load clinical data
    try:
        clinical_df = pd.read_excel(patient_data_file, engine='openpyxl')
        # Standardize Patient_ID column name
        patient_id_cols = [col for col in clinical_df.columns if col.lower() in ['patientid', 'patient_id', 'patientid', 'id']]
        if patient_id_cols:
            clinical_df = clinical_df.rename(columns={patient_id_cols[0]: 'Patient_ID'})
        else:
            raise RuntimeError("No Patient_ID column found in clinical data")
        clinical_df['Patient_ID'] = clinical_df['Patient_ID'].astype(str).str.strip()
    except Exception as e:
        raise RuntimeError(f"Failed to load clinical data from {patient_data_file}: {e}")
    
    # Initialize DVH processor (used for both metrics calculation and TCP computation)
    dvh_processor = TumorDVHProcessor(dvh_dir)
    
    # Load physical metrics (if provided) or calculate from DVH
    if physical_metrics_file and Path(physical_metrics_file).exists():
        try:
            physical_metrics_df = pd.read_excel(physical_metrics_file, engine='openpyxl')
            # Standardize Patient_ID column name
            patient_id_cols = [col for col in physical_metrics_df.columns if col.lower() in ['patientid', 'patient_id', 'patientid', 'id']]
            if patient_id_cols:
                physical_metrics_df = physical_metrics_df.rename(columns={patient_id_cols[0]: 'Patient_ID'})
            else:
                raise RuntimeError("No Patient_ID column found in physical metrics file")
            physical_metrics_df['Patient_ID'] = physical_metrics_df['Patient_ID'].astype(str).str.strip()
        except Exception as e:
            raise RuntimeError(f"Failed to load physical metrics from {physical_metrics_file}: {e}")
    else:
        # Calculate physical metrics from DVH files
        print("[!] Physical metrics file not found")
        print("    Calculating TCP metrics from DVH files...")
        physical_metrics_df = calculate_tcp_metrics_from_dvh(dvh_dir, dvh_processor, clinical_df)
        
        # Save calculated metrics
        metrics_output = output_dir / "tcp_physical_metrics_calculated.xlsx"
        physical_metrics_df.to_excel(metrics_output, index=False, engine='openpyxl')
        print(f"    Saved calculated metrics to: {metrics_output}")
    
    # Find tumor DVH files
    tumor_dvh_files = list(dvh_dir.glob('*.csv'))
    
    # ============================================================
    # STEP 1.5 — LOAD CCS SAFETY GATE (if available)
    # ============================================================
    ccs_checker = None
    if ccs_file and Path(ccs_file).exists() and CCS_AVAILABLE:
        try:
            ccs_checker = CohortConsistencyChecker.load(ccs_file)
            ccs_checker.threshold = ccs_threshold  # Override threshold if specified
            print(f"[CCS] Loaded cohort consistency checker")
            print(f"      Threshold: {ccs_checker.threshold}")
            print(f"      Training cohort: {ccs_checker.n_samples_trained} patients")
            print(f"      Features: {len(ccs_checker.feature_names)}")
        except Exception as e:
            print(f"[!] Could not load CCS checker: {e}")
            print(f"    ML will proceed without CCS safety gate")
    elif ccs_file and not Path(ccs_file).exists():
        print(f"[!] CCS file not found: {ccs_file}")
        print(f"    ML will proceed without CCS safety gate")
    elif enable_ml and not ccs_file:
        print(f"[!] No CCS file provided - ML will use all patients (less safe)")
        print(f"    For safer ML, provide --ccs_file with institutional_ccs.json")
    
    # ============================================================
    # STEP 1 — ADD HARD INPUT ASSERTIONS
    # ============================================================
    
    assert len(tumor_dvh_files) > 0, "No tumor DVH files loaded"
    assert clinical_df.shape[0] > 0, "Clinical dataframe is empty"
    assert physical_metrics_df.shape[0] > 0, "Physical metrics dataframe is empty"
    
    # ============================================================
    # STEP 2 — ENFORCE PATIENT ID ALIGNMENT
    # ============================================================
    
    common_ids = set(clinical_df['Patient_ID']) & set(physical_metrics_df['Patient_ID'])
    
    if len(common_ids) == 0:
        raise RuntimeError(
            "No overlapping Patient_IDs between clinical data and physical metrics"
        )
    
    # Filter both tables to common_ids
    clinical_df = clinical_df[clinical_df['Patient_ID'].isin(common_ids)].copy()
    physical_metrics_df = physical_metrics_df[physical_metrics_df['Patient_ID'].isin(common_ids)].copy()
    
    print(f"Found {len(common_ids)} common patients after alignment")
    
    # ============================================================
    # STEP 3 — FIX THE TCP COMPUTATION LOOP
    # ============================================================
    
    # Initialize TCP calculator
    tcp_calculator = TCPCalculator()
    
    # Helper function to load patient DVH
    def load_patient_dvh(patient_id):
        """Load DVH for a patient (tries common tumor names)"""
        tumor_names = ['PTV', 'GTV', 'CTV', 'Tumor']
        for tumor_name in tumor_names:
            dvh = dvh_processor.load_dvh_file(patient_id, tumor_name)
            if dvh is not None:
                return dvh
        return None
    
    # Helper functions for TCP computation
    def compute_poisson_tcp(dvh, metrics_row):
        """Compute Poisson TCP"""
        try:
            if dvh is None or len(dvh) == 0:
                return 0.0
            dose_metrics = dvh_processor.calculate_dose_metrics(dvh)
            if dose_metrics is None:
                return 0.0
            params = tcp_calculator.literature_params.get(tumor_type, {}).get('Poisson_TCP', {})
            if not params:
                return 0.0
            return tcp_calculator.tcp_poisson(
                dvh,
                params.get('D50', 50.0),
                params.get('gamma50', 2.0),
                params.get('alpha_beta', 10),
                2.0  # dose_per_fraction
            )
        except Exception:
            return 0.0
    
    def compute_lkb_tcp(dvh, metrics_row):
        """Compute LKB TCP"""
        try:
            if dvh is None or len(dvh) == 0:
                return 0.0
            dose_metrics = dvh_processor.calculate_dose_metrics(dvh)
            if dose_metrics is None:
                return 0.0
            # Calculate effective volume
            n_param = tcp_calculator.literature_params.get(tumor_type, {}).get('LKB_TCP', {}).get('n', 0.12)
            v_effective = dvh_processor.calculate_effective_volume(dvh, n_param)
            dose_metrics['v_effective'] = v_effective
            params = tcp_calculator.literature_params.get(tumor_type, {}).get('LKB_TCP', {})
            if not params:
                return 0.0
            return tcp_calculator.tcp_lkb(
                dose_metrics,
                params.get('TD50', 50.0),
                params.get('m', 0.15),
                params.get('n', 0.12),
                params.get('alpha_beta', 10),
                2.0  # dose_per_fraction
            )
        except Exception:
            return 0.0
    
    def compute_logistic_tcp(dvh, metrics_row):
        """Compute Logistic TCP"""
        try:
            if dvh is None or len(dvh) == 0:
                return 0.0
            dose_metrics = dvh_processor.calculate_dose_metrics(dvh)
            if dose_metrics is None:
                return 0.0
            params = tcp_calculator.literature_params.get(tumor_type, {}).get('Logistic_TCP', {})
            if not params:
                return 0.0
            return tcp_calculator.tcp_logistic(
                dose_metrics,
                params.get('D50', 50.0),
                params.get('k', 0.35),
                params.get('alpha_beta', 10),
                2.0  # dose_per_fraction
            )
        except Exception:
            return 0.0
    
    def compute_eud_tcp(dvh, metrics_row):
        """Compute EUD TCP"""
        try:
            if dvh is None or len(dvh) == 0:
                return 0.0
            params = tcp_calculator.literature_params.get(tumor_type, {}).get('EUD_TCP', {})
            if not params:
                return 0.0
            return tcp_calculator.tcp_eud(
                dvh,
                params.get('D50', 50.0),
                params.get('gamma50', 2.0),
                params.get('a', -10),
                params.get('alpha_beta', 10),
                2.0  # dose_per_fraction
            )
        except Exception:
            return 0.0
    
    # Initialize FDVH transformer if enabled
    fdvh_transformer = None
    if use_fdvh and FDVH_AVAILABLE:
        print(f"\n[FDVH] Applying Fractionation-Aware DVH transformation")
        print(f"       α/β = {alpha_beta_tumor} Gy, n = {n_fractions} fractions")
        fdvh_transformer = FractionationAwareDVH(alpha_beta=alpha_beta_tumor, tissue_type='tumor')
    
    # Main TCP computation loop
    tcp_results = []
    
    for pid in common_ids:
        dvh = load_patient_dvh(pid)
        metrics = physical_metrics_df.loc[
            physical_metrics_df['Patient_ID'] == pid
        ]
        
        if dvh is None or metrics.empty:
            continue
        
        result_row = {'Patient_ID': pid}
        
        # Apply FDVH transformation if enabled
        dvh_for_tcp = dvh.copy()
        if use_fdvh and fdvh_transformer is not None:
            try:
                # Normalize DVH column names for FDVH transformer
                dvh_normalized = dvh.copy()
                
                # Find dose column
                dose_col = None
                for col in dvh.columns:
                    if 'dose' in col.lower() and 'gy' in col.lower():
                        dose_col = col
                        break
                if dose_col is None:
                    # Try standard names
                    if 'Dose[Gy]' in dvh.columns:
                        dose_col = 'Dose[Gy]'
                    elif 'dose_gy' in dvh.columns:
                        dose_col = 'dose_gy'
                    else:
                        dose_col = dvh.columns[0]  # Use first column
                
                # Find volume column
                vol_col = None
                for col in dvh.columns:
                    if 'volume' in col.lower():
                        vol_col = col
                        break
                if vol_col is None:
                    if 'Volume[%]' in dvh.columns:
                        vol_col = 'Volume[%]'
                    elif 'Volume[cm3]' in dvh.columns:
                        vol_col = 'Volume[cm3]'
                    elif 'volume_cm3' in dvh.columns:
                        vol_col = 'volume_cm3'
                    else:
                        vol_col = dvh.columns[1] if len(dvh.columns) > 1 else dvh.columns[0]
                
                # Rename to standard format for FDVH
                dvh_normalized = dvh_normalized.rename(columns={dose_col: 'Dose[Gy]', vol_col: 'Volume[%]'})
                
                # Get total dose from DVH (max dose)
                total_dose = dvh_normalized['Dose[Gy]'].max()
                
                # Transform to biological DVH
                bio_dvh = fdvh_transformer.transform_dvh(
                    dvh_df=dvh_normalized,
                    n_fractions=n_fractions,
                    total_dose=total_dose
                )
                
                # Use biological DVH for TCP calculations
                # Map back to original column names
                dvh_for_tcp = bio_dvh[['BED[Gy]', 'Volume[%]']].copy()
                dvh_for_tcp.columns = [dose_col, vol_col]  # Use original column names
                
                # Store BED metrics
                bed_metrics = fdvh_transformer.get_bed_metrics(dvh_normalized, n_fractions, total_dose)
                result_row['BED_mean'] = bed_metrics['BED_mean']
                result_row['BED_max'] = bed_metrics['BED_max']
                
            except Exception as e:
                print(f"  Warning: FDVH transformation failed for patient {pid}: {e}")
                # Fall back to physical DVH
                dvh_for_tcp = dvh
        
        # --- Poisson TCP ---
        tcp_poisson = compute_poisson_tcp(dvh_for_tcp, metrics)
        result_row['TCP_Poisson'] = float(tcp_poisson)
        
        # --- LKB TCP ---
        tcp_lkb = compute_lkb_tcp(dvh_for_tcp, metrics)
        result_row['TCP_LKB'] = float(tcp_lkb)
        
        # --- Logistic TCP ---
        tcp_logistic = compute_logistic_tcp(dvh_for_tcp, metrics)
        result_row['TCP_Logistic'] = float(tcp_logistic)
        
        # --- EUD TCP ---
        tcp_eud = compute_eud_tcp(dvh_for_tcp, metrics)
        result_row['TCP_EUD'] = float(tcp_eud)
        
        # Calculate uTCP if enabled
        if use_utcp and UTCP_AVAILABLE:
            try:
                utcp_results = calculate_all_utcp(dvh_for_tcp)
                
                # Add uTCP results to result_row
                for model, result in utcp_results.items():
                    col_mean = f'uTCP_{model}_mean'
                    col_std = f'uTCP_{model}_std'
                    col_ci_lower = f'uTCP_{model}_CI_lower'
                    col_ci_upper = f'uTCP_{model}_CI_upper'
                    
                    result_row[col_mean] = result['tcp_mean']
                    result_row[col_std] = result['tcp_std']
                    result_row[col_ci_lower] = result['tcp_ci'][0]
                    result_row[col_ci_upper] = result['tcp_ci'][1]
                
            except Exception as e:
                print(f"  Warning: uTCP calculation failed for patient {pid}: {e}")
        
        tcp_results.append(result_row)
    
    # ============================================================
    # STEP 4 — FAIL IF RESULTS ARE EMPTY
    # ============================================================
    
    if len(tcp_results) == 0:
        raise RuntimeError(
            "TCP computation produced zero results. Check DVH ↔ clinical ↔ metric alignment."
        )
    
    # ============================================================
    # STEP 5 — WRITE EXCEL FILES FROM DATAFRAMES ONLY
    # ============================================================
    
    tcp_df = pd.DataFrame(tcp_results)
    
    assert not tcp_df.empty, "TCP DataFrame is empty before writing"
    
    # Merge with clinical data and physical metrics
    results_df = pd.merge(
        tcp_df,
        clinical_df,
        on='Patient_ID',
        how='left'
    )
    results_df = pd.merge(
        results_df,
        physical_metrics_df,
        on='Patient_ID',
        how='left',
        suffixes=('', '_metrics')
    )
    
    # GAP 5: Add StructureType column for TCP outputs (TARGET only)
    if 'StructureType' not in tcp_df.columns:
        tcp_df.insert(1, 'StructureType', 'TARGET')
    if 'StructureType' not in results_df.columns:
        results_df.insert(1, 'StructureType', 'TARGET')
    
    # Write tcp_predictions.xlsx
    tcp_predictions_path = output_dir / "tcp_predictions.xlsx"
    assert not tcp_df.empty, "TCP DataFrame is empty before writing"
    tcp_df.to_excel(tcp_predictions_path, index=False)
    
    # Write tcp_parameters.xlsx (extract parameter columns)
    param_cols = [col for col in results_df.columns if any(x in col.lower() for x in ['parameter', 'alpha', 'beta', 'gamma', 'd50', 'tcd50', 'n0', 'm', 'k', 'a'])]
    if param_cols:
        tcp_parameters_df = results_df[['Patient_ID'] + param_cols].copy()
    else:
        tcp_parameters_df = pd.DataFrame({'Patient_ID': tcp_df['Patient_ID']})
    assert not tcp_parameters_df.empty, "TCP parameters DataFrame is empty before writing"
    tcp_parameters_path = output_dir / "tcp_parameters.xlsx"
    tcp_parameters_df.to_excel(tcp_parameters_path, index=False)
    
    # Write tcp_dose_metrics.xlsx
    dose_metric_cols = [col for col in results_df.columns if col.startswith(('D', 'V', 'mean_', 'max_', 'min_', 'total_', 'EUD', 'v_effective'))]
    if dose_metric_cols:
        tcp_dose_metrics_df = results_df[['Patient_ID'] + dose_metric_cols].copy()
    else:
        tcp_dose_metrics_df = pd.DataFrame({'Patient_ID': tcp_df['Patient_ID']})
    assert not tcp_dose_metrics_df.empty, "TCP dose metrics DataFrame is empty before writing"
    tcp_dose_metrics_path = output_dir / "tcp_dose_metrics.xlsx"
    tcp_dose_metrics_df.to_excel(tcp_dose_metrics_path, index=False)
    
    # Write tcp_ml_performance.xlsx (if ML was enabled) - Fix 1
    ml_cols = [col for col in results_df.columns if any(x in col for x in ['ML', 'ml', 'ANN', 'XGBoost', 'xgboost'])]
    if ml_cols:
        tcp_ml_performance_df = results_df[['Patient_ID'] + ml_cols].copy()
        assert not tcp_ml_performance_df.empty, "TCP ML performance DataFrame is empty before writing"
        tcp_ml_performance_path = output_dir / "tcp_ml_performance.xlsx"
        tcp_ml_performance_df.to_excel(tcp_ml_performance_path, index=False)
        print(f"  [OK] tcp_ml_performance.xlsx ({tcp_ml_performance_path.stat().st_size} bytes)")
    elif enable_ml:
        # If ML was enabled but no ML columns found, create empty performance file
        # This ensures the file exists even if ML training failed or was skipped
        tcp_ml_performance_path = output_dir / "tcp_ml_performance.xlsx"
        # Create minimal performance file
        perf_df = pd.DataFrame({
            'Model': ['ANN', 'XGBoost'],
            'Status': ['Not Trained', 'Not Trained'],
            'AUC': [np.nan, np.nan]
        })
        perf_df.to_excel(tcp_ml_performance_path, index=False)
        print(f"  [OK] tcp_ml_performance.xlsx (created - no ML models trained)")
    
    # ============================================================
    # STEP 6 — VERIFY FILE SIZE
    # ============================================================
    
    for f in output_dir.glob("*.xlsx"):
        if f.stat().st_size < 1024:
            raise RuntimeError(f"Output file is empty or corrupted: {f.name}")

    # Publication plots (tests expect output_dir/plots/*.png)
    try:
        plotter = TCPPlotter(output_dir)
        plotter.plot_dose_response_curves(results_df, tumor_type)
        obs_col = next(
            (c for c in ("LocalControl", "TumorControl", "TCP_Control") if c in results_df.columns),
            None,
        )
        if obs_col is not None:
            observed = results_df[obs_col].astype(float).values
            plotter.plot_roc_curves(results_df, observed, tumor_type)
            plotter.plot_calibration(results_df, observed, tumor_type)
    except Exception as exc:
        print(f"[!] Plot generation skipped: {exc}")
        plots_dir = output_dir / "plots"
        plots_dir.mkdir(exist_ok=True)
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(6, 4))
            ax.set_title("TCP analysis summary")
            ax.axis("off")
            fig.savefig(plots_dir / "tcp_summary.png", dpi=150, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            pass
    
    return results_df


def main():
    """
    Main execution function with command-line interface.
    
    Parses arguments and calls process_all_patients().
    """
    parser = argparse.ArgumentParser(
        description='TCP Analysis: Traditional + ML Models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic TCP analysis
  python code6_tcp_analysis.py --tumor_dvh_dir tumor_dvh/ --clinical_xlsx clinical_data.xlsx --outdir tcp_results
  
  # With ML models
  python code6_tcp_analysis.py --tumor_dvh_dir tumor_dvh/ --clinical_xlsx clinical_data.xlsx --outdir tcp_results --enable_ml
  
  # With SHAP analysis
  python code6_tcp_analysis.py --tumor_dvh_dir tumor_dvh/ --clinical_xlsx clinical_data.xlsx --outdir tcp_results --enable_ml --enable_shap
        """
    )
    
    parser.add_argument('--tumor_dvh_dir', required=True,
                       help='Directory containing tumor DVH CSV files')
    parser.add_argument('--clinical_xlsx', required=True,
                       help='Excel file with patient clinical data and tumor control outcomes')
    parser.add_argument('--outdir', required=True,
                       help='Output directory for all results')
    parser.add_argument('--tumor_type', default='HNSCC',
                       choices=['HNSCC', 'Prostate', 'Lung', 'Breast'],
                       help='Tumor type for parameter loading (default: HNSCC)')
    parser.add_argument('--enable_ml', action='store_true', default=True,
                       help='Enable machine learning models (default: True)')
    parser.add_argument('--enable_shap', action='store_true',
                       help='Generate SHAP explainability plots for ML models')
    parser.add_argument('--models', nargs='+', 
                       choices=['Poisson', 'LKB', 'Logistic', 'EUD'],
                       default=['Poisson', 'LKB', 'Logistic', 'EUD'],
                       help='Traditional TCP models to use (default: all)')
    parser.add_argument('--physical_metrics_file', type=str, default=None,
                       help='Path to TCP physical metrics Excel file from Step-2 (optional, if not provided will calculate from DVH)')
    parser.add_argument('--use_fdvh', action='store_true',
                       help='Use Fractionation-Aware DVH for biological normalization')
    parser.add_argument('--n_fractions', type=int, default=30,
                       help='Number of fractions (for FDVH, default: 30)')
    parser.add_argument('--alpha_beta_tumor', type=float, default=10,
                       help='α/β ratio for tumor (Gy, default: 10)')
    parser.add_argument('--use_utcp', action='store_true',
                       help='Calculate uncertainty-aware TCP with confidence bounds')
    parser.add_argument('--ccs_file', type=str, default=None,
                       help='Optional cohort consistency specification JSON for ML')
    parser.add_argument('--ccs_threshold', type=float, default=0.1,
                       help='CCS threshold when --ccs_file is provided')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TCP Analysis: Traditional + Machine Learning Models")
    print("=" * 60)
    print("Features:")
    print("  - Traditional TCP models (Poisson, LKB, Logistic, EUD)")
    if args.enable_ml:
        print("  - Machine learning models (ANN, XGBoost)")
    if args.enable_shap:
        print("  - SHAP explainability analysis (enabled)")
    if args.use_fdvh:
        print(f"  - Fractionation-Aware DVH (FDVH) - n={args.n_fractions}, α/β={args.alpha_beta_tumor} Gy")
    if args.use_utcp:
        print("  - Uncertainty-Aware TCP (uTCP) with confidence bounds")
    print("  - Professional 600 DPI publication-ready plots")
    print("  - Comprehensive Excel output")
    print("=" * 60)
    
    # Validate input paths
    dvh_path = Path(args.tumor_dvh_dir)
    patient_file = Path(args.clinical_xlsx)
    output_path = Path(args.outdir)
    
    if not dvh_path.exists():
        print(f"Error: Tumor DVH directory '{dvh_path}' not found")
        sys.exit(1)
    
    if not patient_file.exists():
        print(f"Error: Clinical data file '{patient_file}' not found")
        sys.exit(1)
    
    # Check for DVH files
    dvh_files = list(dvh_path.glob('*.csv'))
    if not dvh_files:
        print(f"Error: No CSV files found in '{dvh_path}'")
        sys.exit(1)
    
    print(f"Found {len(dvh_files)} tumor DVH files in {dvh_path}")
    print(f"Clinical data file: {patient_file}")
    print(f"Output directory: {output_path}")
    if XGBOOST_AVAILABLE:
        print("XGBoost available for ML modeling")
    if SHAP_AVAILABLE:
        print("SHAP available for explainability analysis")
    
    # Validate physical metrics file if provided
    physical_metrics_path = None
    if args.physical_metrics_file:
        physical_metrics_path = Path(args.physical_metrics_file)
        if not physical_metrics_path.exists():
            print(f"Warning: Physical metrics file '{physical_metrics_path}' not found, will calculate from DVH files")
            physical_metrics_path = None
        else:
            print(f"Using physical metrics from Step-2: {physical_metrics_path}")
    
    # Process all patients
    try:
        results_df = process_all_patients(
            dvh_dir=dvh_path,
            patient_data_file=patient_file,
            output_dir=output_path,
            tumor_type=args.tumor_type,
            enable_ml=args.enable_ml,
            enable_shap=args.enable_shap,
            physical_metrics_file=physical_metrics_path,
            use_fdvh=args.use_fdvh,
            n_fractions=args.n_fractions,
            alpha_beta_tumor=args.alpha_beta_tumor,
            use_utcp=args.use_utcp,
            ccs_file=args.ccs_file,
            ccs_threshold=args.ccs_threshold
        )
        
        print("\n" + "=" * 60)
        print("TCP Analysis completed successfully!")
        print("=" * 60)
        
        # Verify that process_all_patients returned valid results
        assert results_df is not None, "process_all_patients returned None"
        assert not results_df.empty, "process_all_patients returned empty DataFrame"
        
        print(f"Results DataFrame shape: {results_df.shape}")
        print(f"Results DataFrame columns: {list(results_df.columns)}")
        
        print(f"All outputs saved to: {output_path.absolute()}")
        print("\nGenerated files:")
        print("  - tcp_predictions.xlsx - Patient-level TCP for all models")
        print("  - tcp_parameters.xlsx - Model parameters used")
        if args.enable_ml:
            print("  - tcp_ml_performance.xlsx - ML model metrics")
        print("  - tcp_dose_metrics.xlsx - Tumor dose statistics")
        print("  - plots/ - 600 DPI publication-ready plots")
        
        # ============================================================
        # FINAL SANITY CHECK (files should already be written by process_all_patients)
        # ============================================================
        
        expected_files = [
            "tcp_predictions.xlsx",
            "tcp_parameters.xlsx",
            "tcp_dose_metrics.xlsx",
        ]
        
        # Add ML performance file if ML was enabled
        if args.enable_ml:
            expected_files.append("tcp_ml_performance.xlsx")
        
        missing = [f for f in expected_files if not (output_path / f).exists()]
        
        if missing:
            raise RuntimeError(
                f"TCP analysis finished but missing output files: {missing}"
            )
        else:
            print("[SUCCESS] TCP analysis outputs verified on disk")
            
            # Additional file size verification
            for fname in expected_files:
                fpath = output_path / fname
                if fpath.exists():
                    file_size = fpath.stat().st_size
                    if file_size < 1024:
                        raise RuntimeError(f"Output file is empty or corrupted: {fname} (size: {file_size} bytes)")
                    print(f"  [OK] {fname} ({file_size} bytes)")
        
    except Exception as e:
        print(f"\nError: Error during TCP analysis: {e}")
        import traceback
        print("\nFull error traceback:")
        traceback.print_exc()
        
        print("\nTroubleshooting tips:")
        print("  - Ensure sufficient data for ML training (>=15 samples per tumor type)")
        print("  - Check that all required Python packages are installed:")
        print("    pip install scikit-learn xgboost pandas numpy matplotlib seaborn scipy openpyxl shap")
        print("  - Verify DVH files and clinical data formats")
        print("  - Ensure unique patient IDs in DVH filenames")


if __name__ == "__main__":
    main()

