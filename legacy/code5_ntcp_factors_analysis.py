#!/usr/bin/env python3
"""
rbGyanX v1.0 - NTCP Clinical Factors Analysis Module
=====================================================
Part of rbGyanX: Radiobiological Analysis Platform
Version: 1.0.0

This script adds robust column standardization and automatic detection/
creation of a numeric binary 'Observed_Toxicity' column to prevent KeyErrors
(e.g., when the column is named slightly differently or has merge suffixes).

Features:
- Standardize clinical column names (e.g., "Technique" -> "Treatment_Technique",
  "DosePerFraction(Gy)" -> "Dose_per_Fraction", "Total_Dose(Gy)" -> "Total_Dose",
  "Duration(wk)" -> "Total_Treatment_Duration", "Follow_up(months)" -> "Follow_up_Duration").
- After merging, auto-detect any variant of an observed-toxicity column and
  create a clean numeric 'Observed_Toxicity' (0/1).
- Guard all analyses to proceed only if 'Observed_Toxicity' exists; otherwise,
  skip toxicity‑dependent steps with a clear console notice.
- Make correlation matrix construction and factor scans resilient to missing columns.

Author: rbGyanX Team
License: MIT

Author: NTCP Clinical Analysis Pipeline (patched)
Version: 1.1-patched
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import scipy.stats as stats
from sklearn.metrics import roc_curve, auc
from sklearn.preprocessing import LabelEncoder
from scipy.stats import chi2_contingency, mannwhitneyu, kruskal
import warnings
warnings.filterwarnings('ignore')

# Statsmodels for GLM (optional but recommended)
try:
    import statsmodels.api as sm
    from statsmodels.genmod.generalized_linear_model import GLM
    from statsmodels.genmod.families import Binomial
    from statsmodels.genmod.families.links import logit
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False
    print("Warning: statsmodels not available. GLM analysis will be skipped. Install with: pip install statsmodels")

# Set publication-quality plotting parameters
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

# Professional color scheme
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#F24236', 
    'tertiary': '#F6AE2D',
    'quaternary': '#8B4B9E',
    'quinary': '#2ECC71',
    'observed': '#C73E1D',
    'predicted': '#592E83',
    'correlation_pos': '#27AE60',
    'correlation_neg': '#E74C3C',
    'neutral': '#95A5A6'
}

# ----------------------- Helper Utilities (NEW) -----------------------

def _strip_and_lower(s: str) -> str:
    return s.strip().lower().replace('\xa0', ' ') if isinstance(s, str) else s

def _standardize_columns_inplace(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize common clinical column names to the internal expected set.
    Performs case-insensitive matching and renaming where appropriate.
    """
    if df is None or df.empty:
        return df

    # Build a mapping by scanning for known variants
    col_map = {}
    cols_lower = {c.lower(): c for c in df.columns}

    def has(name_variants):
        for v in name_variants:
            if v.lower() in cols_lower:
                return cols_lower[v.lower()]
        return None

    # Expected internal names -> variants we may see
    rename_plan = {
        'Treatment_Technique': ['Treatment_Technique', 'Technique', 'Tx_Technique'],
        'Dose_per_Fraction': ['Dose_per_Fraction', 'DosePerFraction(Gy)', 'DosePerFraction', 'Dose/Fraction(Gy)', 'Dose/Fraction', 'DosePerFx(Gy)'],
        'Total_Dose': ['Total_Dose', 'Total_Dose(Gy)', 'TotalDose(Gy)', 'TotalDose'],
        'Total_Treatment_Duration': ['Total_Treatment_Duration', 'Duration(wk)', 'Treatment_Duration(weeks)', 'Duration_weeks'],
        'Follow_up_Duration': ['Follow_up_Duration', 'Follow_up(months)', 'FollowUp(months)', 'Followup_Months'],
        'Age': ['Age'],
        'Sex': ['Sex', 'Gender'],
        'Diagnosis': ['Diagnosis', 'Dx']
    }

    for std, variants in rename_plan.items():
        found = has(variants)
        if found and found != std:
            col_map[found] = std

    if col_map:
        df.rename(columns=col_map, inplace=True)

    return df

def _coerce_observed_toxicity(series: pd.Series) -> pd.Series:
    """
    Convert various encodings of observed toxicity to a binary numeric series (0/1).
    Accepts numeric 0/1, booleans, and common string encodings like 'yes/no', 'true/false', etc.
    Non-matching values will be coerced to NaN, then filled with 0 by default.
    """
    if series is None:
        return None

    # If already numeric 0/1
    if pd.api.types.is_numeric_dtype(series):
        # Coerce to 0/1 explicitly (handle floats like 0.0/1.0)
        return series.astype(float).round().clip(lower=0, upper=1).astype(int)

    # Map common strings to {0,1}
    mapping = {
        'yes': 1, 'y': 1, 'true': 1, 't': 1, '1': 1, 'present': 1, 'toxic': 1,
        'grade>=2': 1, 'grade≥2': 1, 'g2+': 1, '>=g2': 1, 'event': 1, 'positive': 1,
        'no': 0, 'n': 0, 'false': 0, 'f': 0, '0': 0, 'absent': 0, 'non-toxic': 0, 'negative': 0
    }

    s = series.astype(str).str.strip().str.lower()
    mapped = s.map(mapping)
    # For anything unmapped, try to parse numbers, else NaN
    unmapped = mapped.isna()
    if unmapped.any():
        # Try to coerce to numeric
        numeric = pd.to_numeric(s[unmapped], errors='coerce')
        mapped.loc[unmapped & numeric.notna()] = numeric.loc[unmapped & numeric.notna()].round().clip(lower=0, upper=1)
    # Fill remaining NaN with 0 (conservative)
    mapped = mapped.fillna(0).astype(int)
    return mapped

def _ensure_observed_toxicity_column(df: pd.DataFrame, verbose_prefix="") -> pd.DataFrame:
    """
    Detect any column that semantically represents observed toxicity and create a unified
    numeric 'Observed_Toxicity' column. Handles merge suffixes (_x/_y) and spacing/underscore variants.
    """
    if df is None or df.empty:
        return df

    candidates = []
    for c in df.columns:
        lc = c.lower().replace(' ', '_')
        if 'observed' in lc and 'tox' in lc:
            candidates.append(c)
        elif lc in ('toxicity', 'observed_toxicity', 'observedtoxicity', 'toxicity_observed'):
            candidates.append(c)
        elif lc.endswith('_x') or lc.endswith('_y'):
            base = lc[:-2]
            if base in ('observed_toxicity', 'observedtoxicity', 'toxicity_observed', 'toxicity'):
                candidates.append(c)

    # Prefer exact 'Observed_Toxicity' if present
    preferred = [c for c in candidates if c == 'Observed_Toxicity']
    selected = preferred[0] if preferred else (candidates[0] if candidates else None)

    if selected is None:
        print(f"{verbose_prefix}Warning: No observed-toxicity column found after merge. "
              f"Looking for common alternatives failed. Skipping toxicity-based analyses.")
        return df

    df['Observed_Toxicity'] = _coerce_observed_toxicity(df[selected])
    return df

# ----------------------- Main Analyzer Class (patched) -----------------------

class ClinicalFactorsAnalyzer:
    """
    Analyze clinical factors effects on TCP/NTCP predictions and observed outcomes.
    
    UNIFIED: Works for both TCP and NTCP analysis.
    Auto-detects analysis type from results files.
    """

    def __init__(self, input_file, enhanced_output_dir, use_glm=False, analysis_type=None):
        """
        Parameters
        ----------
        input_file : str or Path
            Clinical factors input file
        enhanced_output_dir : str or Path
            Analysis output directory (tcp_analysis or ntcp_analysis)
        use_glm : bool, default False
            Enable GLM analysis
        analysis_type : str, optional
            'TCP' or 'NTCP'. If None, auto-detects from directory structure.
        """
        self.input_file = Path(input_file)
        self.enhanced_output_dir = Path(enhanced_output_dir)
        
        # Auto-detect analysis type if not specified
        if analysis_type is None:
            if 'tcp' in str(self.enhanced_output_dir).lower():
                self.analysis_type = 'TCP'
            elif 'ntcp' in str(self.enhanced_output_dir).lower():
                self.analysis_type = 'NTCP'
            else:
                # Try to detect from files
                if (self.enhanced_output_dir / 'tcp_predictions.xlsx').exists():
                    self.analysis_type = 'TCP'
                elif (self.enhanced_output_dir / 'enhanced_ntcp_calculations.csv').exists():
                    self.analysis_type = 'NTCP'
                else:
                    self.analysis_type = 'NTCP'  # Default to NTCP for backward compatibility
        else:
            self.analysis_type = analysis_type.upper()
        
        self.output_dir = self.enhanced_output_dir / 'clinical_factors_analysis'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir = self.output_dir / 'plots'
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        self.use_glm = use_glm and STATSMODELS_AVAILABLE

        # Load data
        self.clinical_data = None
        self.results = None  # TCP or NTCP results (unified name)
        self.merged_data = None
        self.glm_results = None
        
        # Define minimum standardized factor sets
        if self.analysis_type == 'TCP':
            # GAP 2: TCP tumor-relevant factors
            self.required_factors = {
                'Age': 'Age',
                'Sex': 'Sex',
                'Tumor_Site': ['Tumor_Site', 'TumorSite', 'Site'],
                'Stage': ['Stage', 'Tumor_Stage', 'TNM_Stage'],
                'Treatment_Technique': ['Treatment_Technique', 'Technique'],
                'Total_Dose': ['Total_Dose', 'Total_Dose(Gy)', 'TotalDose'],
                'Dose_per_Fraction': ['Dose_per_Fraction', 'DosePerFraction(Gy)', 'DosePerFraction']
            }
        else:  # NTCP
            # GAP 1: NTCP minimum standardized factors
            self.required_factors = {
                'Age': 'Age',
                'Sex': 'Sex',
                'Treatment_Technique': ['Treatment_Technique', 'Technique'],
                'Total_Dose': ['Total_Dose', 'Total_Dose(Gy)', 'TotalDose'],
                'Dose_per_Fraction': ['Dose_per_Fraction', 'DosePerFraction(Gy)', 'DosePerFraction'],
                'Total_Treatment_Duration': ['Total_Treatment_Duration', 'Duration(wk)', 'Treatment_Duration(weeks)']
            }
        
        self.missing_factors = []
        self.available_factors = []

    def _check_required_factors(self):
        """
        GAP 1 & 2: Check for minimum standardized factors and log missing ones.
        Does not block execution - missing factors are logged and analysis proceeds.
        """
        if self.clinical_data is None or self.clinical_data.empty:
            return
        
        available_cols = [c.lower() for c in self.clinical_data.columns]
        self.available_factors = []
        self.missing_factors = []
        
        for factor_name, factor_variants in self.required_factors.items():
            found = False
            if isinstance(factor_variants, str):
                variants = [factor_variants]
            else:
                variants = factor_variants
            
            for variant in variants:
                if variant.lower() in available_cols:
                    # Find the actual column name (case-insensitive)
                    actual_col = [c for c in self.clinical_data.columns if c.lower() == variant.lower()][0]
                    self.available_factors.append(actual_col)
                    found = True
                    break
            
            if not found:
                self.missing_factors.append(factor_name)
        
        if self.missing_factors:
            print(f"[INFO] Missing factors (analysis will proceed): {', '.join(self.missing_factors)}")
            print(f"[INFO] Available factors: {', '.join(self.available_factors)}")
        else:
            print(f"[OK] All required factors present: {', '.join(self.available_factors)}")
    
    def load_and_merge_data(self):
        """Load clinical factors and TCP/NTCP results, then merge them"""

        print(f" Loading and merging clinical data with {self.analysis_type} results...")

        # Load clinical factors from input file
        try:
            # Load with UTF-8 encoding and handle emojis
            self.clinical_data = pd.read_excel(self.input_file, engine='openpyxl')
            # Standardize clinical columns (NEW)
            _standardize_columns_inplace(self.clinical_data)
            print(f" Loaded clinical data: {len(self.clinical_data)} patient-organ combinations")
            print(f"[INFO] Available clinical factors (standardized): {list(self.clinical_data.columns)}")
            
            # GAP 1 & 2: Check for minimum standardized factors
            self._check_required_factors()
        except Exception as e:
            print(f"Error: Error loading clinical data: {e}")
            return False

        # Load TCP or NTCP results (unified)
        if self.analysis_type == 'TCP':
            # Try multiple possible TCP result files
            tcp_files = [
                self.enhanced_output_dir / 'tcp_predictions.xlsx',
                self.enhanced_output_dir / 'tcp_results.xlsx',
                self.enhanced_output_dir / 'tcp_analysis' / 'tcp_predictions.xlsx'
            ]
            results_file = None
            for f in tcp_files:
                if f.exists():
                    results_file = f
                    break
            
            if results_file is None:
                print(f"[!] Warning: TCP results file not found in {self.enhanced_output_dir}")
                print("[!] Clinical factors analysis requires TCP results from Step 3")
                return False
            
            try:
                if results_file.suffix == '.xlsx':
                    # Try to read 'TCP Predictions' sheet or first sheet
                    try:
                        self.results = pd.read_excel(results_file, sheet_name='TCP Predictions')
                    except:
                        self.results = pd.read_excel(results_file)
                else:
                    self.results = pd.read_csv(results_file)
                print(f" Loaded TCP results: {len(self.results)} rows from {results_file.name}")
            except Exception as e:
                print(f"Error: Error loading TCP results: {e}")
                return False
        else:  # NTCP
            try:
                # Try multiple possible NTCP result files
                ntcp_files = [
                    self.enhanced_output_dir / 'enhanced_ntcp_calculations.csv',
                    self.enhanced_output_dir / 'ntcp_results.xlsx',
                    self.enhanced_output_dir / 'ntcp_analysis' / 'enhanced_ntcp_calculations.csv'
                ]
                results_file = None
                for f in ntcp_files:
                    if f.exists():
                        results_file = f
                        break
                
                if results_file is None:
                    print(f"[!] Warning: NTCP results file not found in {self.enhanced_output_dir}")
                    print("[!] Clinical factors analysis requires NTCP results from Step 3")
                    return False
                
                try:
                    if results_file.suffix == '.xlsx':
                        # Try to read 'NTCP Predictions' sheet or first sheet
                        try:
                            self.results = pd.read_excel(results_file, sheet_name='NTCP Predictions')
                        except:
                            self.results = pd.read_excel(results_file)
                    else:
                        self.results = pd.read_csv(results_file)
                    print(f" Loaded NTCP results: {len(self.results)} rows from {results_file.name}")
                except Exception as e:
                    print(f"Error: Error loading NTCP results: {e}")
                    return False
                print(f" Loaded {self.analysis_type} results: {len(self.results)} patient-organ combinations")

                # Count unique patients correctly
                if 'PatientID' in self.results.columns:
                    unique_patients = self.results['PatientID'].nunique()
                    print(f" Unique patients: {unique_patients}")
                else:
                    print(f"Warning: 'PatientID' column missing in {self.analysis_type} results; unique patient count unavailable.")

            except Exception as e:
                print(f"Error: Error loading NTCP results: {e}")
                return False

        # Merge datasets on PatientID and Organ
        try:
            # ✓ FIXED: Case-insensitive column matching
            def find_patient_id_column(df):
                """Find patient ID column regardless of case."""
                for col in df.columns:
                    if col.lower() in ['patientid', 'patient_id', 'id', 'ptid']:
                        return col
                return None

            def find_organ_column(df):
                """Find organ column regardless of case."""
                for col in df.columns:
                    if col.lower() in ['organ', 'structure', 'oar']:
                        return col
                return None

            # Detect columns
            clinical_patient_col = find_patient_id_column(self.clinical_data)
            clinical_organ_col = find_organ_column(self.clinical_data)
            results_patient_col = find_patient_id_column(self.results)
            results_organ_col = find_organ_column(self.results)

            if not all([clinical_patient_col, clinical_organ_col, results_patient_col, results_organ_col]):
                print(f"[X] Column detection failed:")
                print(f"    Clinical columns: {list(self.clinical_data.columns)}")
                print(f"    {self.analysis_type} columns: {list(self.results.columns)}")
                print("Error: Could not find required PatientID/Organ columns")
                return False

            print(f"[OK] Detected columns:")
            print(f"    Clinical: PatientID='{clinical_patient_col}', Organ='{clinical_organ_col}'")
            print(f"    {self.analysis_type}: PatientID='{results_patient_col}', Organ='{results_organ_col}'")

            # Standardize column names for merging
            clinical_df_renamed = self.clinical_data.rename(columns={
                clinical_patient_col: 'PatientID',
                clinical_organ_col: 'Organ'
            })

            results_df_renamed = self.results.rename(columns={
                results_patient_col: 'PatientID',
                results_organ_col: 'Organ'
            })

            self.merged_data = pd.merge(
                clinical_df_renamed, 
                results_df_renamed, 
                on=['PatientID', 'Organ'], 
                how='inner',
                suffixes=('_clin', f'_{self.analysis_type.lower()}')
            )
            
            print(f"[OK] Merged {len(self.merged_data)} patient-organ combinations")

            # Ensure Observed_Toxicity exists and is numeric (NEW)
            self.merged_data = _ensure_observed_toxicity_column(self.merged_data, verbose_prefix=" ")

            print(f" Successfully merged data: {len(self.merged_data)} records")
            if 'PatientID' in self.merged_data.columns:
                print(f" Unique patients in merged data: {self.merged_data['PatientID'].nunique()}")

            # Display organs distribution
            if 'Organ' in self.merged_data.columns:
                organ_counts = self.merged_data['Organ'].value_counts()
                print(f"[INFO] Organ distribution:")
                for organ, count in organ_counts.items():
                    print(f"  {organ}: {count} cases")

            return True

        except Exception as e:
            print(f"Error: Error merging data: {e}")
            return False

    def analyze_categorical_factors(self):
        """Analyze categorical factors (Diagnosis, Treatment Techniques, Sex)"""

        print("\n Analyzing Categorical Clinical Factors...")

        if 'Observed_Toxicity' not in self.merged_data.columns:
            print("Warning: Skipping categorical analysis: 'Observed_Toxicity' not available.")
            return {}

        categorical_factors = []

        # Identify categorical columns using standardized names first
        for col in ['Diagnosis', 'Treatment_Technique', 'Sex']:
            if col in self.merged_data.columns:
                categorical_factors.append(col)
        # Fallbacks if standard names absent
        for alt in ['Gender', 'Technique']:
            if alt in self.merged_data.columns and alt not in categorical_factors:
                categorical_factors.append(alt)

        if not categorical_factors:
            print("Warning: No categorical factors found in the data")
            return {}

        print(f" Analyzing categorical factors: {categorical_factors}")

        results = {}

        for factor in categorical_factors:
            print(f"\n[ANALYZING] Analyzing {factor}...")

            factor_results = {
                'factor_name': factor,
                'categories': {},
                'statistical_tests': {},
                'ntcp_model_effects': {}
            }

            # Get unique categories
            categories = self.merged_data[factor].dropna().unique()
            print(f"  Categories: {list(categories)}")

            # Analyze each category
            for category in categories:
                category_data = self.merged_data[self.merged_data[factor] == category]

                category_stats = {
                    'n_cases': len(category_data),
                    'n_patients': category_data['PatientID'].nunique() if 'PatientID' in category_data.columns else len(category_data),
                    'observed_toxicity_rate': category_data['Observed_Toxicity'].mean() if 'Observed_Toxicity' in category_data.columns else np.nan,
                    'organs': category_data['Organ'].value_counts().to_dict() if 'Organ' in category_data.columns else {}
                }

                factor_results['categories'][category] = category_stats
                tox_rate = category_stats['observed_toxicity_rate']
                tox_txt = f"{tox_rate:.3f}" if pd.notna(tox_rate) else "NA"
                print(f"    {category}: {category_stats['n_cases']} cases, {category_stats['n_patients']} patients, toxicity rate: {tox_txt}")

            # Statistical tests for observed toxicity
            if len(categories) >= 2:
                try:
                    # Chi-square test for observed toxicity vs factor
                    contingency_table = pd.crosstab(
                        self.merged_data[factor].fillna('Missing'), 
                        self.merged_data['Observed_Toxicity']
                    )

                    if contingency_table.shape[1] == 2:  # Ensure binary
                        chi2, p_value, dof, expected = chi2_contingency(contingency_table)

                        factor_results['statistical_tests']['chi_square'] = {
                            'chi2': chi2,
                            'p_value': p_value,
                            'degrees_of_freedom': dof,
                            'significant': p_value < 0.05
                        }

                        print(f"    Chi-square test: χ² = {chi2:.3f}, p = {p_value:.4f}")
                    else:
                        print("    Warning: Chi-square skipped: Observed_Toxicity is not binary after coercion.")

                except Exception as e:
                    print(f"    Warning: Chi-square test failed: {e}")

            # Analyze NTCP model predictions by factor
            ntcp_cols = [col for col in self.merged_data.columns if col.startswith('NTCP_')]

            for ntcp_col in ntcp_cols:
                if ntcp_col in self.merged_data.columns:
                    model_name = ntcp_col.replace('NTCP_', '')

                    # Calculate mean NTCP by category
                    category_ntcp_means = {}
                    for category in categories:
                        category_data = self.merged_data[self.merged_data[factor] == category]
                        mean_ntcp = category_data[ntcp_col].mean()
                        category_ntcp_means[category] = mean_ntcp

                    factor_results['ntcp_model_effects'][model_name] = category_ntcp_means

            results[factor] = factor_results

        # Save categorical analysis results
        self._save_categorical_results(results)
        self._plot_categorical_analysis(results)

        return results

    def analyze_continuous_factors(self):
        """Analyze continuous factors (Age, Dose per Fraction, Total Dose, etc.)"""

        print("\n Analyzing Continuous Clinical Factors...")

        if 'Observed_Toxicity' not in self.merged_data.columns:
            print("Warning: Skipping continuous analysis: 'Observed_Toxicity' not available.")
            return {}

        # Identify continuous factors
        continuous_factors = []
        potential_continuous = [
            'Age', 'Dose_per_Fraction', 'Total_Dose', 'Total_Treatment_Duration', 
            'Follow_up_Duration', 'age', 'dose_per_fraction', 'total_dose'
        ]

        for col in potential_continuous:
            if col in self.merged_data.columns and pd.api.types.is_numeric_dtype(self.merged_data[col]):
                continuous_factors.append(col)

        if not continuous_factors:
            print("Warning: No continuous factors found in the data")
            return {}

        print(f" Analyzing continuous factors: {continuous_factors}")

        results = {}

        for factor in continuous_factors:
            print(f"\n[ANALYZING] Analyzing {factor}...")

            factor_data = self.merged_data[factor].dropna()

            factor_results = {
                'factor_name': factor,
                'descriptive_stats': {
                    'count': len(factor_data),
                    'mean': float(factor_data.mean()) if len(factor_data) else np.nan,
                    'std': float(factor_data.std()) if len(factor_data) else np.nan,
                    'min': float(factor_data.min()) if len(factor_data) else np.nan,
                    'max': float(factor_data.max()) if len(factor_data) else np.nan,
                    'median': float(factor_data.median()) if len(factor_data) else np.nan,
                    'q25': float(factor_data.quantile(0.25)) if len(factor_data) else np.nan,
                    'q75': float(factor_data.quantile(0.75)) if len(factor_data) else np.nan
                },
                'correlations': {},
                'group_comparisons': {}
            }

            print(f"  Descriptive stats: mean={factor_results['descriptive_stats']['mean']:.2f}, "
                  f"std={factor_results['descriptive_stats']['std']:.2f}, range=[{factor_results['descriptive_stats']['min']:.2f}, {factor_results['descriptive_stats']['max']:.2f}]")

            # Correlation with observed toxicity
            valid_data = self.merged_data[[factor, 'Observed_Toxicity']].dropna()

            if len(valid_data) > 10:
                # Point-biserial correlation (continuous vs binary)
                try:
                    correlation_coef, correlation_p = stats.pointbiserialr(
                        valid_data['Observed_Toxicity'].astype(float), 
                        valid_data[factor].astype(float)
                    )
                    factor_results['correlations']['observed_toxicity'] = {
                        'correlation': float(correlation_coef),
                        'p_value': float(correlation_p),
                        'significant': bool(correlation_p < 0.05)
                    }
                    print(f"  Correlation with observed toxicity: r = {correlation_coef:.3f}, p = {correlation_p:.4f}")
                except Exception as e:
                    print(f"  Warning: Correlation computation failed for {factor}: {e}")

            # Correlations with NTCP model predictions
            ntcp_cols = [col for col in self.merged_data.columns if col.startswith('NTCP_')]

            for ntcp_col in ntcp_cols:
                if ntcp_col in self.merged_data.columns:
                    model_name = ntcp_col.replace('NTCP_', '')

                    valid_data = self.merged_data[[factor, ntcp_col]].dropna()

                    if len(valid_data) > 10:
                        try:
                            corr_coef, corr_p = stats.pearsonr(valid_data[factor].astype(float), valid_data[ntcp_col].astype(float))
                            factor_results['correlations'][model_name] = {
                                'correlation': float(corr_coef),
                                'p_value': float(corr_p),
                                'significant': bool(corr_p < 0.05)
                            }
                        except Exception as e:
                            pass

            # Group comparisons (toxicity vs no toxicity)
            toxicity_group = self.merged_data[self.merged_data['Observed_Toxicity'] == 1][factor].dropna()
            no_toxicity_group = self.merged_data[self.merged_data['Observed_Toxicity'] == 0][factor].dropna()

            if len(toxicity_group) > 0 and len(no_toxicity_group) > 0:
                try:
                    # Mann-Whitney U test (non-parametric)
                    statistic, p_value = mannwhitneyu(toxicity_group, no_toxicity_group, alternative='two-sided')

                    effect_size = np.nan
                    std_all = self.merged_data[factor].std()
                    if pd.notna(std_all) and std_all != 0:
                        effect_size = (toxicity_group.mean() - no_toxicity_group.mean()) / std_all

                    factor_results['group_comparisons']['toxicity_vs_no_toxicity'] = {
                        'toxicity_group_mean': float(toxicity_group.mean()),
                        'no_toxicity_group_mean': float(no_toxicity_group.mean()),
                        'mann_whitney_u': float(statistic),
                        'p_value': float(p_value),
                        'significant': bool(p_value < 0.05),
                        'effect_size': float(effect_size) if pd.notna(effect_size) else np.nan
                    }

                    print(f"  Group comparison (toxicity vs no toxicity):")
                    print(f"    Toxicity group mean: {toxicity_group.mean():.2f}")
                    print(f"    No toxicity group mean: {no_toxicity_group.mean():.2f}")
                    print(f"    Mann-Whitney U test: p = {p_value:.4f}")
                except Exception as e:
                    print(f"  Warning: Mann-Whitney U failed for {factor}: {e}")

            results[factor] = factor_results

        # Save continuous analysis results
        self._save_continuous_results(results)
        self._plot_continuous_analysis(results)

        return results

    def analyze_with_glm(self):
        """
        Perform Generalized Linear Model (GLM) analysis using statsmodels.
        
        Fits logistic regression models to assess the association between clinical factors
        and observed toxicity, providing proper confidence intervals and p-values.
        
        Returns
        -------
        dict
            Dictionary containing GLM results for each factor
        """
        if not self.use_glm:
            return {}
        
        if not STATSMODELS_AVAILABLE:
            print("Warning: statsmodels not available. Skipping GLM analysis.")
            return {}
        
        print("\n" + "="*60)
        print(" Performing GLM (Logistic Regression) Analysis...")
        print("="*60)
        
        if 'Observed_Toxicity' not in self.merged_data.columns:
            print("Warning: Skipping GLM analysis: 'Observed_Toxicity' not available.")
            return {}
        
        # Prepare data
        data = self.merged_data.copy()
        data = data.dropna(subset=['Observed_Toxicity'])
        
        if len(data) < 20:
            print("Warning: Insufficient data for GLM analysis (n < 20). Skipping.")
            return {}
        
        results = {}
        
        # Identify factors to analyze
        continuous_factors = []
        categorical_factors = []
        
        # Continuous factors
        potential_continuous = [
            'Age', 'Dose_per_Fraction', 'Total_Dose', 'Total_Treatment_Duration', 
            'Follow_up_Duration', 'age', 'dose_per_fraction', 'total_dose',
            'mean_dose', 'max_dose', 'gEUD'
        ]
        
        for col in potential_continuous:
            if col in data.columns and pd.api.types.is_numeric_dtype(data[col]):
                if data[col].notna().sum() >= 10:  # At least 10 non-missing values
                    continuous_factors.append(col)
        
        # Categorical factors
        potential_categorical = ['Treatment_Technique', 'Sex', 'Diagnosis']
        for col in potential_categorical:
            if col in data.columns:
                if data[col].notna().sum() >= 10:
                    categorical_factors.append(col)
        
        all_factors = continuous_factors + categorical_factors
        
        if not all_factors:
            print("Warning: No suitable factors found for GLM analysis.")
            return {}
        
        print(f" Analyzing {len(all_factors)} factors with GLM:")
        print(f"  Continuous: {continuous_factors}")
        print(f"  Categorical: {categorical_factors}")
        
        # Univariate GLM for each factor
        for factor in all_factors:
            print(f"\n[ANALYSIS] GLM Analysis for {factor}...")
            
            try:
                # Prepare feature matrix
                factor_data = data[[factor, 'Observed_Toxicity']].dropna()
                
                if len(factor_data) < 10:
                    print(f"  Warning: Insufficient data for {factor} (n={len(factor_data)}). Skipping.")
                    continue
                
                X = factor_data[[factor]].copy()
                y = factor_data['Observed_Toxicity'].astype(int)
                
                # Handle categorical variables (one-hot encoding)
                if factor in categorical_factors:
                    # One-hot encode categorical variable
                    X_encoded = pd.get_dummies(X[factor], prefix=factor, drop_first=True)
                    X = X_encoded
                else:
                    # Standardize continuous variables for better interpretation
                    X_mean = X[factor].mean()
                    X_std = X[factor].std()
                    if X_std > 0:
                        X = (X[factor] - X_mean) / X_std
                        X = pd.DataFrame({factor: X})
                    else:
                        print(f"  Warning: {factor} has zero variance. Skipping.")
                        continue
                
                # Add intercept
                X = sm.add_constant(X)
                
                # Fit GLM (logistic regression)
                try:
                    glm_model = GLM(y, X, family=Binomial(link=logit()))
                    glm_result = glm_model.fit()
                    
                    # Extract results
                    params = glm_result.params
                    conf_int = glm_result.conf_int(alpha=0.05)  # 95% CI
                    pvalues = glm_result.pvalues
                    
                    # Get factor coefficient (skip intercept)
                    factor_coef_idx = 1 if len(params) > 1 else 0
                    factor_name = X.columns[factor_coef_idx] if len(X.columns) > 1 else factor
                    
                    if factor_coef_idx < len(params):
                        coef = params.iloc[factor_coef_idx]
                        ci_lower = conf_int.iloc[factor_coef_idx, 0]
                        ci_upper = conf_int.iloc[factor_coef_idx, 1]
                        p_value = pvalues.iloc[factor_coef_idx]
                        
                        # Calculate odds ratio (for logistic regression)
                        or_value = np.exp(coef)
                        or_ci_lower = np.exp(ci_lower)
                        or_ci_upper = np.exp(ci_upper)
                        
                        results[factor] = {
                            'coefficient': float(coef),
                            'coefficient_ci_lower': float(ci_lower),
                            'coefficient_ci_upper': float(ci_upper),
                            'odds_ratio': float(or_value),
                            'odds_ratio_ci_lower': float(or_ci_lower),
                            'odds_ratio_ci_upper': float(or_ci_upper),
                            'p_value': float(p_value),
                            'significant': bool(p_value < 0.05),
                            'n_samples': int(len(factor_data)),
                            'aic': float(glm_result.aic),
                            'bic': float(glm_result.bic),
                            'pseudo_r2': float(glm_result.pseudo_rsquared(kind='mcfadden')) if hasattr(glm_result, 'pseudo_rsquared') else np.nan
                        }
                        
                        print(f"  Coefficient: {coef:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}])")
                        print(f"  Odds Ratio: {or_value:.4f} (95% CI: [{or_ci_lower:.4f}, {or_ci_upper:.4f}])")
                        print(f"  P-value: {p_value:.4f} {'***' if p_value < 0.001 else '**' if p_value < 0.01 else '*' if p_value < 0.05 else ''}")
                        print(f"  AIC: {glm_result.aic:.2f}, BIC: {glm_result.bic:.2f}")
                        
                except Exception as e:
                    print(f"  Error fitting GLM for {factor}: {e}")
                    continue
                    
            except Exception as e:
                print(f"  Error in GLM analysis for {factor}: {e}")
                continue
        
        # Multivariable GLM (if multiple factors available)
        if len(results) >= 2:
            print(f"\n[ANALYSIS] Multivariable GLM Analysis...")
            try:
                # Prepare multivariable model
                mv_factors = list(results.keys())[:5]  # Limit to 5 factors to avoid overfitting
                mv_data = data[['Observed_Toxicity'] + mv_factors].dropna()
                
                if len(mv_data) >= 20:
                    X_mv = mv_data[mv_factors].copy()
                    
                    # Handle categorical variables
                    for factor in mv_factors:
                        if factor in categorical_factors:
                            X_encoded = pd.get_dummies(X_mv[factor], prefix=factor, drop_first=True)
                            X_mv = X_mv.drop(columns=[factor])
                            X_mv = pd.concat([X_mv, X_encoded], axis=1)
                        else:
                            # Standardize continuous
                            X_mean = X_mv[factor].mean()
                            X_std = X_mv[factor].std()
                            if X_std > 0:
                                X_mv[factor] = (X_mv[factor] - X_mean) / X_std
                    
                    X_mv = sm.add_constant(X_mv)
                    y_mv = mv_data['Observed_Toxicity'].astype(int)
                    
                    glm_mv = GLM(y_mv, X_mv, family=Binomial(link=logit()))
                    glm_mv_result = glm_mv.fit()
                    
                    results['multivariable'] = {
                        'factors': mv_factors,
                        'n_samples': int(len(mv_data)),
                        'aic': float(glm_mv_result.aic),
                        'bic': float(glm_mv_result.bic),
                        'pseudo_r2': float(glm_mv_result.pseudo_rsquared(kind='mcfadden')) if hasattr(glm_mv_result, 'pseudo_rsquared') else np.nan,
                        'summary': str(glm_mv_result.summary())
                    }
                    
                    print(f"  Multivariable model with {len(mv_factors)} factors:")
                    print(f"  AIC: {glm_mv_result.aic:.2f}, BIC: {glm_mv_result.bic:.2f}")
                    print(f"  Pseudo R²: {results['multivariable']['pseudo_r2']:.4f}")
                    
            except Exception as e:
                print(f"  Error in multivariable GLM: {e}")
        
        # Save GLM results
        self._save_glm_results(results)
        self.glm_results = results
        
        return results

    def analyze_organ_specific_effects(self):
        """Analyze how clinical factors affect different organs"""

        print("\n Analyzing Organ-Specific Effects...")

        if 'Organ' not in self.merged_data.columns:
            print("Warning: Skipping organ-specific analysis: 'Organ' column not available.")
            return {}
        if 'Observed_Toxicity' not in self.merged_data.columns:
            print("Warning: Skipping organ-specific analysis: 'Observed_Toxicity' not available.")
            return {}

        organs = self.merged_data['Organ'].unique()
        results = {}

        for organ in organs:
            print(f"\n Analyzing {organ}...")

            organ_data = self.merged_data[self.merged_data['Organ'] == organ].copy()

            if len(organ_data) < 10:
                print(f"  Warning: Insufficient data for {organ} ({len(organ_data)} cases)")
                continue

            organ_results = {
                'organ_name': organ,
                'sample_size': int(len(organ_data)),
                'toxicity_rate': float(organ_data['Observed_Toxicity'].mean()),
                'factor_effects': {}
            }

            print(f"  Sample size: {len(organ_data)}, Toxicity rate: {organ_results['toxicity_rate']:.3f}")

            # Analyze each clinical factor for this organ
            clinical_factors = []
            for col in organ_data.columns:
                if col in ['Diagnosis', 'Treatment_Technique', 'Sex', 'Age', 'Dose_per_Fraction', 
                          'Total_Dose', 'Total_Treatment_Duration', 'Follow_up_Duration']:
                    clinical_factors.append(col)

            for factor in clinical_factors:
                if factor not in organ_data.columns:
                    continue

                factor_data = organ_data[factor].dropna()

                if len(factor_data) < 5:
                    continue

                factor_effect = {
                    'factor_name': factor,
                    'data_type': 'categorical' if organ_data[factor].dtype == 'object' else 'continuous'
                }

                if factor_effect['data_type'] == 'categorical':
                    # Categorical factor analysis
                    categories = factor_data.unique()

                    if len(categories) >= 2:
                        category_effects = {}

                        for category in categories:
                            category_subset = organ_data[organ_data[factor] == category]
                            category_effects[category] = {
                                'n_cases': int(len(category_subset)),
                                'toxicity_rate': float(category_subset['Observed_Toxicity'].mean())
                            }

                        factor_effect['category_effects'] = category_effects

                else:
                    # Continuous factor analysis
                    valid_data = organ_data[[factor, 'Observed_Toxicity']].dropna()

                    if len(valid_data) > 5:
                        try:
                            correlation_coef, correlation_p = stats.pointbiserialr(
                                valid_data['Observed_Toxicity'].astype(float), 
                                valid_data[factor].astype(float)
                            )
                            factor_effect['correlation_with_toxicity'] = {
                                'correlation': float(correlation_coef),
                                'p_value': float(correlation_p),
                                'significant': bool(correlation_p < 0.05)
                            }
                        except Exception as e:
                            pass

                organ_results['factor_effects'][factor] = factor_effect

            results[organ] = organ_results

        # Save organ-specific results
        self._save_organ_specific_results(results)
        self._plot_organ_specific_analysis(results)

        return results

    def create_correlation_matrix(self):
        """Create correlation matrix for all factors and NTCP predictions"""

        print("\n Creating Comprehensive Correlation Matrix...")

        # Select numerical columns for correlation
        numerical_cols = []

        # Clinical factors
        for col in ['Age', 'Dose_per_Fraction', 'Total_Dose', 'Total_Treatment_Duration', 
                   'Follow_up_Duration', 'age', 'dose_per_fraction', 'total_dose']:
            if col in self.merged_data.columns and pd.api.types.is_numeric_dtype(self.merged_data[col]):
                numerical_cols.append(col)

        # Observed toxicity
        if 'Observed_Toxicity' in self.merged_data.columns:
            numerical_cols.append('Observed_Toxicity')

        # NTCP predictions
        ntcp_cols = [col for col in self.merged_data.columns if col.startswith('NTCP_')]
        numerical_cols.extend([c for c in ntcp_cols if pd.api.types.is_numeric_dtype(self.merged_data[c])])

        # Dose metrics (optional; include only if present and numeric)
        dose_cols = ['gEUD', 'mean_dose', 'max_dose', 'total_volume']
        for col in dose_cols:
            if col in self.merged_data.columns and pd.api.types.is_numeric_dtype(self.merged_data[col]):
                numerical_cols.append(col)

        if not numerical_cols:
            print("Warning: No numerical columns available for correlation matrix.")
            return pd.DataFrame()

        # Create correlation matrix
        correlation_data = self.merged_data[numerical_cols].copy()
        correlation_matrix = correlation_data.corr()

        # Create comprehensive correlation plot
        fig, ax = plt.subplots(figsize=(14, 12))

        # Create heatmap
        mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
        sns.heatmap(correlation_matrix, mask=mask, annot=True, cmap='RdBu_r', center=0,
                   square=True, linewidths=0.5, cbar_kws={"shrink": 0.8}, ax=ax,
                   fmt='.3f', annot_kws={'size': 8})

        ax.set_title('Correlation Matrix: Clinical Factors, Dose Metrics, and NTCP Predictions', 
                    fontsize=14, fontweight='bold', pad=20)

        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()

        # Save correlation matrix to plots directory (GAP 1/2)
        correlation_file = self.plots_dir / 'correlation_matrix.png'
        plt.savefig(correlation_file, dpi=600, bbox_inches='tight')
        print(f" Correlation matrix saved: {correlation_file}")
        plt.close()

        # Save correlation matrix as CSV
        correlation_matrix.to_csv(self.output_dir / 'correlation_matrix.csv')

        return correlation_matrix
    
    def _save_unified_outputs(self, categorical_results, continuous_results, 
                              organ_results, correlation_matrix, glm_results=None):
        """
        GAP 1 & 2: Save unified outputs to clinical_factors.xlsx and clinical_correlations.xlsx
        """
        # Create clinical_factors.xlsx with all factor analysis
        factors_file = self.output_dir / 'clinical_factors.xlsx'
        
        with pd.ExcelWriter(factors_file, engine='openpyxl') as writer:
            # Sheet 1: Categorical factors summary
            if categorical_results:
                cat_data = []
                for factor, factor_results in categorical_results.items():
                    for category, stats_d in factor_results['categories'].items():
                        cat_data.append({
                            'Factor': factor,
                            'Category': category,
                            'N_Cases': stats_d['n_cases'],
                            'N_Patients': stats_d.get('n_patients', np.nan),
                            'Toxicity_Rate': stats_d.get('observed_toxicity_rate', np.nan)
                        })
                if cat_data:
                    pd.DataFrame(cat_data).to_excel(writer, sheet_name='Categorical_Factors', index=False)
            
            # Sheet 2: Continuous factors summary
            if continuous_results:
                cont_data = []
                for factor, factor_results in continuous_results.items():
                    stats_d = factor_results['descriptive_stats']
                    cont_data.append({
                        'Factor': factor,
                        'Count': stats_d['count'],
                        'Mean': stats_d['mean'],
                        'Std': stats_d['std'],
                        'Min': stats_d['min'],
                        'Max': stats_d['max'],
                        'Median': stats_d['median']
                    })
                if cont_data:
                    pd.DataFrame(cont_data).to_excel(writer, sheet_name='Continuous_Factors', index=False)
            
            # Sheet 3: Factor availability status
            status_data = []
            for factor_name in self.required_factors.keys():
                status_data.append({
                    'Factor': factor_name,
                    'Status': 'Available' if factor_name not in [f.split('_')[0] if '_' in f else f for f in self.missing_factors] else 'Missing',
                    'Available_Columns': ', '.join([c for c in self.available_factors if factor_name.lower() in c.lower()])
                })
            pd.DataFrame(status_data).to_excel(writer, sheet_name='Factor_Status', index=False)
        
        print(f" Unified clinical factors saved: {factors_file}")
        
        # Create clinical_correlations.xlsx
        if isinstance(correlation_matrix, pd.DataFrame) and not correlation_matrix.empty:
            corr_file = self.output_dir / 'clinical_correlations.xlsx'
            correlation_matrix.to_excel(corr_file, sheet_name='Correlation_Matrix')
            print(f" Clinical correlations saved: {corr_file}")

    # ----------------------- Save/Plot helpers (unchanged) -----------------------
    def _save_categorical_results(self, results):
        """Save categorical analysis results to Excel"""

        excel_file = self.output_dir / 'categorical_factors_analysis.xlsx'

        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:

            # Summary sheet
            summary_data = []
            for factor, factor_results in results.items():
                for category, stats_d in factor_results['categories'].items():
                    summary_data.append({
                        'Factor': factor,
                        'Category': category,
                        'N_Cases': stats_d['n_cases'],
                        'N_Patients': stats_d['n_patients'],
                        'Toxicity_Rate': stats_d['observed_toxicity_rate']
                    })

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

            # Statistical tests sheet
            stats_data = []
            for factor, factor_results in results.items():
                if 'chi_square' in factor_results['statistical_tests']:
                    chi_sq = factor_results['statistical_tests']['chi_square']
                    stats_data.append({
                        'Factor': factor,
                        'Test': 'Chi-square',
                        'Statistic': chi_sq['chi2'],
                        'P_Value': chi_sq['p_value'],
                        'Significant': chi_sq['significant']
                    })

            if stats_data:
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Statistical_Tests', index=False)

        print(f" Categorical analysis saved: {excel_file}")

    def _save_continuous_results(self, results):
        """Save continuous analysis results to Excel"""

        excel_file = self.output_dir / 'continuous_factors_analysis.xlsx'

        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:

            # Descriptive statistics
            desc_data = []
            for factor, factor_results in results.items():
                stats_d = factor_results['descriptive_stats']
                desc_data.append({
                    'Factor': factor,
                    'Count': stats_d['count'],
                    'Mean': stats_d['mean'],
                    'Std': stats_d['std'],
                    'Min': stats_d['min'],
                    'Max': stats_d['max'],
                    'Median': stats_d['median'],
                    'Q25': stats_d['q25'],
                    'Q75': stats_d['q75']
                })

            desc_df = pd.DataFrame(desc_data)
            desc_df.to_excel(writer, sheet_name='Descriptive_Stats', index=False)

            # Correlations
            corr_data = []
            for factor, factor_results in results.items():
                for target, corr_stats in factor_results['correlations'].items():
                    corr_data.append({
                        'Factor': factor,
                        'Target': target,
                        'Correlation': corr_stats['correlation'],
                        'P_Value': corr_stats['p_value'],
                        'Significant': corr_stats['significant']
                    })

            if corr_data:
                corr_df = pd.DataFrame(corr_data)
                corr_df.to_excel(writer, sheet_name='Correlations', index=False)

            # Group comparisons
            group_data = []
            for factor, factor_results in results.items():
                if 'toxicity_vs_no_toxicity' in factor_results['group_comparisons']:
                    comp = factor_results['group_comparisons']['toxicity_vs_no_toxicity']
                    group_data.append({
                        'Factor': factor,
                        'Toxicity_Group_Mean': comp['toxicity_group_mean'],
                        'No_Toxicity_Group_Mean': comp['no_toxicity_group_mean'],
                        'Mann_Whitney_U': comp['mann_whitney_u'],
                        'P_Value': comp['p_value'],
                        'Significant': comp['significant'],
                        'Effect_Size': comp['effect_size']
                    })

            if group_data:
                group_df = pd.DataFrame(group_data)
                group_df.to_excel(writer, sheet_name='Group_Comparisons', index=False)

        print(f" Continuous analysis saved: {excel_file}")

    def _save_glm_results(self, results):
        """Save GLM analysis results to Excel"""
        
        if not results:
            return
        
        excel_file = self.output_dir / 'glm_analysis_results.xlsx'
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Univariate GLM results
            glm_data = []
            for factor, factor_results in results.items():
                if factor == 'multivariable':
                    continue
                
                glm_data.append({
                    'Factor': factor,
                    'Coefficient': factor_results.get('coefficient', np.nan),
                    'Coefficient_CI_Lower': factor_results.get('coefficient_ci_lower', np.nan),
                    'Coefficient_CI_Upper': factor_results.get('coefficient_ci_upper', np.nan),
                    'Odds_Ratio': factor_results.get('odds_ratio', np.nan),
                    'Odds_Ratio_CI_Lower': factor_results.get('odds_ratio_ci_lower', np.nan),
                    'Odds_Ratio_CI_Upper': factor_results.get('odds_ratio_ci_upper', np.nan),
                    'P_Value': factor_results.get('p_value', np.nan),
                    'Significant': factor_results.get('significant', False),
                    'N_Samples': factor_results.get('n_samples', np.nan),
                    'AIC': factor_results.get('aic', np.nan),
                    'BIC': factor_results.get('bic', np.nan),
                    'Pseudo_R2': factor_results.get('pseudo_r2', np.nan)
                })
            
            if glm_data:
                glm_df = pd.DataFrame(glm_data)
                glm_df.to_excel(writer, sheet_name='Univariate_GLM', index=False)
            
            # Multivariable GLM results
            if 'multivariable' in results:
                mv_results = results['multivariable']
                mv_data = [{
                    'Model_Type': 'Multivariable',
                    'Factors': ', '.join(mv_results.get('factors', [])),
                    'N_Samples': mv_results.get('n_samples', np.nan),
                    'AIC': mv_results.get('aic', np.nan),
                    'BIC': mv_results.get('bic', np.nan),
                    'Pseudo_R2': mv_results.get('pseudo_r2', np.nan)
                }]
                mv_df = pd.DataFrame(mv_data)
                mv_df.to_excel(writer, sheet_name='Multivariable_GLM', index=False)
                
                # Save full summary as text
                summary_text = mv_results.get('summary', '')
                if summary_text:
                    summary_file = self.output_dir / 'glm_multivariable_summary.txt'
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        f.write("Multivariable GLM Summary\n")
                        f.write("=" * 60 + "\n\n")
                        f.write(summary_text)
        
        print(f" GLM analysis saved: {excel_file}")

    def _save_organ_specific_results(self, results):
        """Save organ-specific analysis results"""

        excel_file = self.output_dir / 'organ_specific_analysis.xlsx'

        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:

            # Summary by organ
            summary_data = []
            for organ, organ_results in results.items():
                summary_data.append({
                    'Organ': organ,
                    'Sample_Size': organ_results['sample_size'],
                    'Toxicity_Rate': organ_results['toxicity_rate']
                })

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Organ_Summary', index=False)

            # Factor effects by organ
            effect_data = []
            for organ, organ_results in results.items():
                for factor, factor_effect in organ_results['factor_effects'].items():

                    if factor_effect['data_type'] == 'continuous':
                        if 'correlation_with_toxicity' in factor_effect:
                            corr = factor_effect['correlation_with_toxicity']
                            effect_data.append({
                                'Organ': organ,
                                'Factor': factor,
                                'Data_Type': 'Continuous',
                                'Correlation': corr['correlation'],
                                'P_Value': corr['p_value'],
                                'Significant': corr['significant']
                            })

                    elif factor_effect['data_type'] == 'categorical':
                        if 'category_effects' in factor_effect:
                            for category, cat_effect in factor_effect['category_effects'].items():
                                effect_data.append({
                                    'Organ': organ,
                                    'Factor': factor,
                                    'Data_Type': 'Categorical',
                                    'Category': category,
                                    'N_Cases': cat_effect['n_cases'],
                                    'Toxicity_Rate': cat_effect['toxicity_rate']
                                })

            if effect_data:
                effect_df = pd.DataFrame(effect_data)
                effect_df.to_excel(writer, sheet_name='Factor_Effects', index=False)

        print(f" Organ-specific analysis saved: {excel_file}")

    def _plot_categorical_analysis(self, results):
        """Create plots for categorical factors analysis"""

        if not results:
            return

        for factor, factor_results in results.items():
            # Create subplot for this factor
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Categorical Factor Analysis: {factor}', fontsize=16, fontweight='bold')

            # Plot 1: Toxicity rates by category
            categories = list(factor_results['categories'].keys())
            toxicity_rates = [factor_results['categories'][cat]['observed_toxicity_rate'] 
                            for cat in categories]

            bars = ax1.bar(categories, toxicity_rates, color=COLORS['primary'], alpha=0.7)
            ax1.set_title('Observed Toxicity Rate by Category')
            ax1.set_ylabel('Toxicity Rate')
            ax1.set_xlabel(factor)

            # Add value labels
            for bar, rate in zip(bars, toxicity_rates):
                if pd.notna(rate):
                    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                            f'{rate:.3f}', ha='center', va='bottom')

            ax1.tick_params(axis='x', rotation=45)

            # Plot 2: Sample sizes by category
            sample_sizes = [factor_results['categories'][cat]['n_cases'] for cat in categories]

            bars = ax2.bar(categories, sample_sizes, color=COLORS['secondary'], alpha=0.7)
            ax2.set_title('Sample Size by Category')
            ax2.set_ylabel('Number of Cases')
            ax2.set_xlabel(factor)

            # Add value labels
            for bar, size in zip(bars, sample_sizes):
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                        f'{size}', ha='center', va='bottom')

            ax2.tick_params(axis='x', rotation=45)

            # Plot 3: NTCP predictions by category (if available)
            ntcp_models = list(factor_results['ntcp_model_effects'].keys())

            if ntcp_models:
                # Take first NTCP model for visualization
                model = ntcp_models[0]
                ntcp_means = [factor_results['ntcp_model_effects'][model].get(cat, np.nan) 
                            for cat in categories]

                bars = ax3.bar(categories, ntcp_means, color=COLORS['tertiary'], alpha=0.7)
                ax3.set_title(f'Mean {model} NTCP by Category')
                ax3.set_ylabel('Mean NTCP')
                ax3.set_xlabel(factor)

                # Add value labels
                for bar, mean_ntcp in zip(bars, ntcp_means):
                    if pd.notna(mean_ntcp):
                        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                                f'{mean_ntcp:.3f}', ha='center', va='bottom')

                ax3.tick_params(axis='x', rotation=45)

            # Plot 4: Statistical significance
            if 'chi_square' in factor_results['statistical_tests']:
                chi_sq = factor_results['statistical_tests']['chi_square']

                # Create text summary
                significance_text = f"""
Statistical Test Results:
Chi-square test: χ² = {chi_sq['chi2']:.3f}
p-value = {chi_sq['p_value']:.4f}
Significant: {chi_sq['significant']}
Degrees of freedom: {chi_sq['degrees_of_freedom']}
                """

                ax4.text(0.1, 0.5, significance_text, transform=ax4.transAxes, 
                        fontsize=12, verticalalignment='center',
                        bbox=dict(boxstyle='round,pad=0.5', 
                                facecolor='lightblue' if chi_sq['significant'] else 'lightgray',
                                alpha=0.8))
                ax4.set_title('Statistical Significance')
                ax4.axis('off')
            else:
                ax4.axis('off')

            plt.tight_layout()

            # Save plot to plots directory (GAP 1/2)
            plot_file = self.plots_dir / f'categorical_analysis_{factor}.png'
            plt.savefig(plot_file, dpi=600, bbox_inches='tight')
            print(f" Categorical plot saved: {plot_file}")
            plt.close()

    def _plot_continuous_analysis(self, results):
        """Create plots for continuous factors analysis"""

        if not results:
            return

        for factor, factor_results in results.items():
            # Create subplot for this factor
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle(f'Continuous Factor Analysis: {factor}', fontsize=16, fontweight='bold')

            # Plot 1: Distribution of factor
            factor_data = self.merged_data[factor].dropna()

            ax1.hist(factor_data, bins=20, color=COLORS['primary'], alpha=0.7, edgecolor='black')
            ax1.set_title(f'Distribution of {factor}')
            ax1.set_xlabel(factor)
            ax1.set_ylabel('Frequency')
            ax1.grid(True, alpha=0.3)

            # Add statistics text
            stats_d = factor_results['descriptive_stats']
            if pd.notna(stats_d['mean']):
                stats_text = f"Mean: {stats_d['mean']:.2f}\nStd: {stats_d['std']:.2f}\nMedian: {stats_d['median']:.2f}"
                ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, 
                        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

            # Plot 2: Factor by toxicity group
            if 'Observed_Toxicity' in self.merged_data.columns:
                toxicity_data = self.merged_data[self.merged_data['Observed_Toxicity'] == 1][factor].dropna()
                no_toxicity_data = self.merged_data[self.merged_data['Observed_Toxicity'] == 0][factor].dropna()

                ax2.boxplot([no_toxicity_data, toxicity_data], 
                           labels=['No Toxicity', 'Toxicity'],
                           patch_artist=True,
                           boxprops=dict(facecolor=COLORS['secondary'], alpha=0.7),
                           medianprops=dict(color='black', linewidth=2))

                ax2.set_title(f'{factor} by Toxicity Status')
                ax2.set_ylabel(factor)
                ax2.grid(True, alpha=0.3)

                # Add group comparison results
                if 'toxicity_vs_no_toxicity' in factor_results['group_comparisons']:
                    comp = factor_results['group_comparisons']['toxicity_vs_no_toxicity']
                    comp_text = f"p = {comp['p_value']:.4f}\nEffect size: {comp['effect_size']:.3f}" if pd.notna(comp['p_value']) else "p = NA"
                    ax2.text(0.02, 0.98, comp_text, transform=ax2.transAxes, 
                            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            else:
                ax2.axis('off')

            # Plot 3: Scatter plot with observed toxicity
            if 'Observed_Toxicity' in self.merged_data.columns:
                valid_data = self.merged_data[[factor, 'Observed_Toxicity']].dropna()

                # Add jitter to toxicity for better visualization
                jittered_toxicity = valid_data['Observed_Toxicity'].astype(float) + np.random.normal(0, 0.02, len(valid_data))

                ax3.scatter(valid_data[factor], jittered_toxicity, 
                           alpha=0.6, color=COLORS['tertiary'], s=30)
                ax3.set_xlabel(factor)
                ax3.set_ylabel('Observed Toxicity (jittered)')
                ax3.set_title(f'{factor} vs Observed Toxicity')
                ax3.grid(True, alpha=0.3)

                # Add correlation information
                if 'observed_toxicity' in factor_results['correlations']:
                    corr = factor_results['correlations']['observed_toxicity']
                    corr_text = f"r = {corr['correlation']:.3f}\np = {corr['p_value']:.4f}"
                    ax3.text(0.02, 0.98, corr_text, transform=ax3.transAxes, 
                            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            else:
                ax3.axis('off')

            # Plot 4: Correlations with NTCP models
            ntcp_correlations = {k: v for k, v in factor_results['correlations'].items() 
                               if k != 'observed_toxicity'}

            if ntcp_correlations:
                models = list(ntcp_correlations.keys())
                correlations = [ntcp_correlations[model]['correlation'] for model in models]
                p_values = [ntcp_correlations[model]['p_value'] for model in models]

                # Create bar plot
                colors = [COLORS['correlation_pos'] if corr > 0 else COLORS['correlation_neg'] 
                         for corr in correlations]
                bars = ax4.bar(range(len(models)), correlations, color=colors, alpha=0.7)

                ax4.set_title(f'Correlations with NTCP Models')
                ax4.set_ylabel('Correlation Coefficient')
                ax4.set_xlabel('NTCP Models')
                ax4.set_xticks(range(len(models)))
                ax4.set_xticklabels(models, rotation=45, ha='right')
                ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
                ax4.grid(True, alpha=0.3)

                # Add significance indicators
                for i, (bar, p_val) in enumerate(zip(bars, p_values)):
                    if pd.notna(p_val) and p_val < 0.05:
                        ax4.text(bar.get_x() + bar.get_width()/2, 
                                bar.get_height() + 0.01 if bar.get_height() > 0 else bar.get_height() - 0.03,
                                '*', ha='center', va='bottom' if bar.get_height() > 0 else 'top', 
                                fontsize=16, fontweight='bold')
            else:
                ax4.axis('off')

            plt.tight_layout()

            # Save plot to plots directory (GAP 1/2)
            plot_file = self.plots_dir / f'continuous_analysis_{factor}.png'
            plt.savefig(plot_file, dpi=600, bbox_inches='tight')
            print(f" Continuous plot saved: {plot_file}")
            plt.close()

    def _plot_organ_specific_analysis(self, results):
        """Create plots for organ-specific analysis"""

        if not results:
            return

        # Create overview plot
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Organ-Specific Clinical Factors Analysis', fontsize=16, fontweight='bold')

        organs = list(results.keys())
        if not organs:
            plt.close(fig)
            return

        # Plot 1: Sample sizes by organ
        sample_sizes = [results[organ]['sample_size'] for organ in organs]

        bars = axes[0, 0].bar(organs, sample_sizes, color=COLORS['primary'], alpha=0.7)
        axes[0, 0].set_title('Sample Size by Organ')
        axes[0, 0].set_ylabel('Number of Cases')
        axes[0, 0].tick_params(axis='x', rotation=45)

        # Add value labels
        for bar, size in zip(bars, sample_sizes):
            axes[0, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                           f'{size}', ha='center', va='bottom')

        # Plot 2: Toxicity rates by organ
        toxicity_rates = [results[organ]['toxicity_rate'] for organ in organs]

        bars = axes[0, 1].bar(organs, toxicity_rates, color=COLORS['secondary'], alpha=0.7)
        axes[0, 1].set_title('Toxicity Rate by Organ')
        axes[0, 1].set_ylabel('Toxicity Rate')
        axes[0, 1].tick_params(axis='x', rotation=45)

        # Add value labels
        for bar, rate in zip(bars, toxicity_rates):
            axes[0, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                           f'{rate:.3f}', ha='center', va='bottom')

        # Plot 3: Factor significance heatmap (if enough data)
        # Create a matrix of significant correlations by organ
        all_factors = set()
        for organ_result in results.values():
            all_factors.update(organ_result['factor_effects'].keys())

        all_factors = list(all_factors)

        if len(all_factors) > 0 and len(organs) > 0:
            significance_matrix = np.zeros((len(organs), len(all_factors)))

            for i, organ in enumerate(organs):
                for j, factor in enumerate(all_factors):
                    if factor in results[organ]['factor_effects']:
                        factor_effect = results[organ]['factor_effects'][factor]
                        if factor_effect['data_type'] == 'continuous':
                            if 'correlation_with_toxicity' in factor_effect:
                                corr_data = factor_effect['correlation_with_toxicity']
                                if corr_data['significant']:
                                    significance_matrix[i, j] = corr_data['correlation']

            # Create heatmap
            im = axes[1, 0].imshow(significance_matrix, cmap='RdBu_r', aspect='auto', 
                                  vmin=-1, vmax=1)
            axes[1, 0].set_title('Significant Factor Correlations by Organ')
            axes[1, 0].set_yticks(range(len(organs)))
            axes[1, 0].set_yticklabels(organs)
            axes[1, 0].set_xticks(range(len(all_factors)))
            axes[1, 0].set_xticklabels(all_factors, rotation=45, ha='right')

            # Add colorbar
            plt.colorbar(im, ax=axes[1, 0], label='Correlation Coefficient')

        # Plot 4: Summary statistics table
        axes[1, 1].axis('off')

        # Create summary table data
        table_data = []
        for organ in organs:
            table_data.append([
                organ,
                results[organ]['sample_size'],
                f"{results[organ]['toxicity_rate']:.3f}",
                len(results[organ]['factor_effects'])
            ])

        table = axes[1, 1].table(cellText=table_data,
                                colLabels=['Organ', 'Sample Size', 'Toxicity Rate', 'Factors Analyzed'],
                                cellLoc='center',
                                loc='center')

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)

        # Style the table
        for i in range(len(table_data) + 1):
            for j in range(4):
                cell = table[(i, j)]
                if i == 0:  # Header
                    cell.set_facecolor(COLORS['primary'])
                    cell.set_text_props(weight='bold', color='white')
                else:
                    cell.set_facecolor('#f0f0f0' if i % 2 == 0 else 'white')

        axes[1, 1].set_title('Summary by Organ')

        plt.tight_layout()

        # Save plot to plots directory (GAP 1/2)
        plot_file = self.plots_dir / 'organ_specific_overview.png'
        plt.savefig(plot_file, dpi=600, bbox_inches='tight')
        print(f" Organ-specific overview saved: {plot_file}")
        plt.close()

    def create_comprehensive_summary_report(self, categorical_results, continuous_results,
                                           organ_results, correlation_matrix, glm_results=None):
        """Create comprehensive summary report"""

        print("\n[INFO] Creating Comprehensive Summary Report...")

        report_lines = []
        report_lines.append("NTCP CLINICAL FACTORS ANALYSIS REPORT")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total patient-organ combinations: {len(self.merged_data)}")
        if 'PatientID' in self.merged_data.columns:
            report_lines.append(f"Unique patients: {self.merged_data['PatientID'].nunique()}")
        report_lines.append("")

        # Dataset overview
        if 'Organ' in self.merged_data.columns:
            report_lines.append("DATASET OVERVIEW")
            report_lines.append("-" * 20)

            organ_distribution = self.merged_data['Organ'].value_counts()
            for organ, count in organ_distribution.items():
                toxicity_rate = self.merged_data[self.merged_data['Organ'] == organ]['Observed_Toxicity'].mean() if 'Observed_Toxicity' in self.merged_data.columns else np.nan
                tox_txt = f"{toxicity_rate:.3f}" if pd.notna(toxicity_rate) else "NA"
                report_lines.append(f"{organ}: {count} cases, toxicity rate: {tox_txt}")

            overall_toxicity_rate = self.merged_data['Observed_Toxicity'].mean() if 'Observed_Toxicity' in self.merged_data.columns else np.nan
            report_lines.append(f"Overall toxicity rate: {overall_toxicity_rate:.3f}" if pd.notna(overall_toxicity_rate) else "Overall toxicity rate: NA")
            report_lines.append("")

        # Categorical factors summary
        if categorical_results:
            report_lines.append("CATEGORICAL FACTORS ANALYSIS")
            report_lines.append("-" * 30)

            for factor, results in categorical_results.items():
                report_lines.append(f"\n{factor.upper()}:")

                # Category summary
                for category, stats_d in results['categories'].items():
                    tox = stats_d['observed_toxicity_rate']
                    tox_txt = f"{tox:.3f}" if pd.notna(tox) else "NA"
                    report_lines.append(f"  {category}: {stats_d['n_cases']} cases, toxicity rate: {tox_txt}")

                # Statistical significance
                if 'chi_square' in results['statistical_tests']:
                    chi_sq = results['statistical_tests']['chi_square']
                    significance = "SIGNIFICANT" if chi_sq['significant'] else "NOT SIGNIFICANT"
                    report_lines.append(f"  Chi-square test: p = {chi_sq['p_value']:.4f} ({significance})")

        # Continuous factors summary
        if continuous_results:
            report_lines.append("\n\nCONTINUOUS FACTORS ANALYSIS")
            report_lines.append("-" * 32)

            for factor, results in continuous_results.items():
                report_lines.append(f"\n{factor.upper()}:")

                # Descriptive statistics
                stats_d = results['descriptive_stats']
                report_lines.append(f"  Range: {stats_d['min']:.2f} - {stats_d['max']:.2f}")
                report_lines.append(f"  Mean ± SD: {stats_d['mean']:.2f} ± {stats_d['std']:.2f}")

                # Correlation with observed toxicity
                if 'observed_toxicity' in results['correlations']:
                    corr = results['correlations']['observed_toxicity']
                    significance = "SIGNIFICANT" if corr['significant'] else "NOT SIGNIFICANT"
                    report_lines.append(f"  Correlation with toxicity: r = {corr['correlation']:.3f}, "
                                      f"p = {corr['p_value']:.4f} ({significance})")

                # Group comparison
                if 'toxicity_vs_no_toxicity' in results['group_comparisons']:
                    comp = results['group_comparisons']['toxicity_vs_no_toxicity']
                    significance = "SIGNIFICANT" if comp['significant'] else "NOT SIGNIFICANT"
                    report_lines.append(f"  Group difference: toxicity group mean = {comp['toxicity_group_mean']:.2f}, "
                                      f"no toxicity group mean = {comp['no_toxicity_group_mean']:.2f}")
                    report_lines.append(f"  Mann-Whitney U test: p = {comp['p_value']:.4f} ({significance})")
                    report_lines.append(f"  Effect size: {comp['effect_size']:.3f}")

        # Organ-specific findings
        if organ_results:
            report_lines.append("\n\nORGAN-SPECIFIC FINDINGS")
            report_lines.append("-" * 25)

            for organ, results in organ_results.items():
                report_lines.append(f"\n{organ.upper()}:")
                report_lines.append(f"  Sample size: {results['sample_size']}")
                report_lines.append(f"  Toxicity rate: {results['toxicity_rate']:.3f}")

                # Significant factor effects
                significant_factors = []
                for factor, factor_effect in results['factor_effects'].items():
                    if factor_effect['data_type'] == 'continuous':
                        if 'correlation_with_toxicity' in factor_effect:
                            if factor_effect['correlation_with_toxicity']['significant']:
                                corr = factor_effect['correlation_with_toxicity']['correlation']
                                significant_factors.append(f"{factor} (r={corr:.3f})")

                if significant_factors:
                    report_lines.append(f"  Significant factors: {', '.join(significant_factors)}")
                else:
                    report_lines.append("  No significant factor correlations found")

        # Key correlations from correlation matrix
        report_lines.append("\n\nKEY CORRELATIONS")
        report_lines.append("-" * 18)

        # Find strongest correlations with observed toxicity
        if isinstance(correlation_matrix, pd.DataFrame) and not correlation_matrix.empty and \
           'Observed_Toxicity' in correlation_matrix.columns:
            toxicity_correlations = correlation_matrix['Observed_Toxicity'].abs().sort_values(ascending=False)

            report_lines.append("Strongest correlations with observed toxicity:")
            for factor, corr in toxicity_correlations.head(10).items():
                if factor != 'Observed_Toxicity' and not np.isnan(corr):
                    actual_corr = correlation_matrix.loc[factor, 'Observed_Toxicity']
                    report_lines.append(f"  {factor}: r = {actual_corr:.3f}")

        # GLM Analysis Results
        if glm_results and isinstance(glm_results, dict) and len(glm_results) > 0:
            report_lines.append("\n\nGLM (LOGISTIC REGRESSION) ANALYSIS")
            report_lines.append("-" * 35)
            
            # Univariate GLM results
            for factor, factor_results in glm_results.items():
                if factor == 'multivariable':
                    continue
                
                or_value = factor_results.get('odds_ratio', np.nan)
                or_ci_lower = factor_results.get('odds_ratio_ci_lower', np.nan)
                or_ci_upper = factor_results.get('odds_ratio_ci_upper', np.nan)
                p_value = factor_results.get('p_value', np.nan)
                significant = factor_results.get('significant', False)
                
                significance = "SIGNIFICANT" if significant else "NOT SIGNIFICANT"
                report_lines.append(f"\n{factor.upper()}:")
                report_lines.append(f"  Odds Ratio: {or_value:.4f} (95% CI: [{or_ci_lower:.4f}, {or_ci_upper:.4f}])")
                report_lines.append(f"  P-value: {p_value:.4f} ({significance})")
                report_lines.append(f"  N samples: {factor_results.get('n_samples', 'N/A')}")
            
            # Multivariable GLM
            if 'multivariable' in glm_results:
                mv_results = glm_results['multivariable']
                report_lines.append("\nMULTIVARIABLE MODEL:")
                report_lines.append(f"  Factors included: {', '.join(mv_results.get('factors', []))}")
                report_lines.append(f"  N samples: {mv_results.get('n_samples', 'N/A')}")
                report_lines.append(f"  AIC: {mv_results.get('aic', np.nan):.2f}")
                report_lines.append(f"  BIC: {mv_results.get('bic', np.nan):.2f}")
                report_lines.append(f"  Pseudo R²: {mv_results.get('pseudo_r2', np.nan):.4f}")

        # Clinical recommendations
        report_lines.append("\n\nCLINICAL RECOMMENDATIONS")
        report_lines.append("-" * 26)

        # Generate recommendations based on findings
        recommendations = self._generate_clinical_recommendations(
            categorical_results, continuous_results, organ_results, correlation_matrix
        )

        for recommendation in recommendations:
            report_lines.append(f"• {recommendation}")

        # Save report
        report_file = self.output_dir / 'clinical_factors_analysis_report.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        print(f" Comprehensive report saved: {report_file}")

        return report_lines

    def _generate_clinical_recommendations(self, categorical_results, continuous_results, 
                                         organ_results, correlation_matrix):
        """Generate clinical recommendations based on analysis results"""

        recommendations = []

        # Check for significant categorical factors
        for factor, results in categorical_results.items():
            if 'chi_square' in results['statistical_tests']:
                if results['statistical_tests']['chi_square']['significant']:
                    recommendations.append(f"{factor} shows significant association with toxicity outcomes and should be considered in treatment planning")

        # Check for significant continuous factors
        for factor, results in continuous_results.items():
            if 'observed_toxicity' in results['correlations']:
                corr_data = results['correlations']['observed_toxicity']
                if corr_data['significant']:
                    direction = "higher" if corr_data['correlation'] > 0 else "lower"
                    recommendations.append(f"{factor} is significantly correlated with toxicity - {direction} values associated with increased toxicity risk")

        # Organ-specific recommendations
        high_risk_organs = []
        for organ, results in organ_results.items():
            if results['toxicity_rate'] > 0.3:  # 30% threshold
                high_risk_organs.append(organ)

        if high_risk_organs:
            recommendations.append(f"Organs with highest toxicity risk ({', '.join(high_risk_organs)}) require enhanced monitoring and potential dose constraints")

        # Check sample size adequacy
        small_sample_organs = []
        for organ, results in organ_results.items():
            if results['sample_size'] < 20:
                small_sample_organs.append(organ)

        if small_sample_organs:
            recommendations.append(f"Larger datasets needed for {', '.join(small_sample_organs)} to improve statistical power")

        # NTCP model recommendations
        if isinstance(correlation_matrix, pd.DataFrame) and not correlation_matrix.empty and \
           'Observed_Toxicity' in correlation_matrix.columns:
            ntcp_correlations = {}
            for col in correlation_matrix.columns:
                if col.startswith('NTCP_'):
                    corr_val = correlation_matrix.loc['Observed_Toxicity', col]
                    if not np.isnan(corr_val):
                        ntcp_correlations[col] = abs(corr_val)

            if ntcp_correlations:
                best_model = max(ntcp_correlations.items(), key=lambda x: x[1])
                recommendations.append(f"Best performing NTCP model: {best_model[0]} (|r| = {best_model[1]:.3f})")

        # General recommendations
        recommendations.append("Consider multivariable modeling combining significant clinical factors with dose metrics")
        recommendations.append("Validate findings in external cohorts before clinical implementation")
        recommendations.append("Regular model recalibration recommended as more data becomes available")

        return recommendations

    def run_complete_analysis(self):
        """Run the complete clinical factors analysis pipeline"""

        print(f" Starting Comprehensive {self.analysis_type} Clinical Factors Analysis")
        print("=" * 60)

        # Step 1: Load and merge data
        if not self.load_and_merge_data():
            print("Error: Failed to load and merge data. Stopping analysis.")
            return False

        # Step 2: Analyze categorical factors
        print("\n" + "="*60)
        categorical_results = self.analyze_categorical_factors()

        # Step 3: Analyze continuous factors
        print("\n" + "="*60)
        continuous_results = self.analyze_continuous_factors()

        # Step 4: Analyze organ-specific effects
        print("\n" + "="*60)
        organ_results = self.analyze_organ_specific_effects()

        # Step 5: Create correlation matrix
        print("\n" + "="*60)
        correlation_matrix = self.create_correlation_matrix()

        # Step 6: GLM analysis (if enabled)
        glm_results = {}
        if self.use_glm:
            glm_results = self.analyze_with_glm()

        # Step 7: Create comprehensive summary report
        print("\n" + "="*60)
        self.create_comprehensive_summary_report(
            categorical_results, continuous_results, organ_results, correlation_matrix, glm_results
        )
        
        # GAP 1 & 2: Save unified outputs
        print("\n" + "="*60)
        print(" Saving unified outputs...")
        self._save_unified_outputs(
            categorical_results, continuous_results, organ_results, 
            correlation_matrix, glm_results
        )

        print("\n🎉 Clinical Factors Analysis Completed Successfully!")
        print("=" * 60)
        print(f"📁 All outputs saved to: {self.output_dir.absolute()}")
        print("\nGenerated files:")
        print("   clinical_factors.xlsx (GAP 1/2: Unified factor analysis)")
        print("   clinical_correlations.xlsx (GAP 1/2: Correlation matrix)")
        print("   categorical_factors_analysis.xlsx")
        print("   continuous_factors_analysis.xlsx") 
        print("   organ_specific_analysis.xlsx")
        if self.use_glm and self.glm_results:
            print("   glm_analysis_results.xlsx (GLM with confidence intervals)")
        print("   correlation_matrix.png & correlation_matrix.csv")
        print("   clinical_factors_analysis_report.txt")
        print("   Individual factor analysis plots (in plots/)")
        print("   organ_specific_overview.png")

        return True

def main():
    """Main execution function"""

    import argparse

    parser = argparse.ArgumentParser(description='TCP/NTCP Clinical Factors Analysis (Unified)')
    parser.add_argument('--input_file', required=True,
                       help='Clinical factors input file (Excel or CSV)')
    parser.add_argument('--enhanced_output_dir', required=True,
                       help='Analysis output directory (tcp_analysis or ntcp_analysis)')
    parser.add_argument('--analysis_type', choices=['TCP', 'NTCP'], default=None,
                       help='Analysis type (TCP or NTCP). Auto-detected if not specified.')
    parser.add_argument('--use_glm', action='store_true',
                       help='Enable GLM (logistic regression) analysis using statsmodels. Provides proper confidence intervals and p-values.')

    args = parser.parse_args()

    # Validate input files
    input_file = Path(args.input_file)
    enhanced_dir = Path(args.enhanced_output_dir)

    if not input_file.exists():
        print(f"Error: Error: Input file '{input_file}' not found")
        return

    if not enhanced_dir.exists():
        print(f"Error: Error: Enhanced output directory '{enhanced_dir}' not found")
        print("Please run enhanced_ntcp_analysis_ml.py first to generate NTCP results")
        return

    # ✓ FIX: Check for required NTCP results file (multiple possible locations)
    ntcp_results_file = None
    possible_locations = [
        enhanced_dir / 'enhanced_ntcp_calculations.csv',
        enhanced_dir / 'ntcp_results.xlsx',
        enhanced_dir / 'ntcp_analysis' / 'ntcp_results.xlsx',
        enhanced_dir / 'enhanced_ntcp_analysis' / 'enhanced_ntcp_calculations.csv'
    ]
    
    for loc in possible_locations:
        if loc.exists():
            ntcp_results_file = loc
            print(f"[OK] Found NTCP results: {loc}")
            break
    
    if ntcp_results_file is None:
        print(f"[X] Error: NTCP results file not found in any of these locations:")
        for loc in possible_locations:
            print(f"     - {loc}")
        print("[X] Please run Step 3 (NTCP analysis) first to generate NTCP results")
        return

    print(" Input validation passed")
    print(f" Clinical factors file: {input_file}")
    print(f" NTCP results directory: {enhanced_dir}")

    # ✓ CRITICAL: Ensure output directory exists
    output_dir = Path(args.enhanced_output_dir) / 'clinical_factors'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[OK] Output directory: {output_dir}")
    print(f"[OK] Plots directory: {plots_dir}")
    
    try:
        # Initialize analyzer (unified for TCP and NTCP)
        analyzer = ClinicalFactorsAnalyzer(
            input_file, 
            enhanced_dir, 
            use_glm=args.use_glm,
            analysis_type=args.analysis_type
        )
        
        if args.use_glm:
            if not STATSMODELS_AVAILABLE:
                print("Warning: --use_glm specified but statsmodels not available.")
                print("Install with: pip install statsmodels")
            else:
                print("GLM analysis enabled (statsmodels)")

        # Run complete analysis
        success = analyzer.run_complete_analysis()
        
        # ✓ CRITICAL: Verify output files were created
        output_file = output_dir / 'clinical_factors_analysis.xlsx'
        if output_file.exists():
            print(f"\n{'='*70}")
            print(f"[OK] Clinical factors analysis complete!")
            print(f"[OK] Results: {output_file}")
            print(f"[OK] Plots: {len(list(plots_dir.glob('*.png'))) if plots_dir.exists() else 0}")
            print(f"{'='*70}\n")
        else:
            print(f"\n[!] Warning: Output file not created: {output_file}")
            print("[!] Check for errors in the analysis above")

        if success:
            print("\n💡 Next Steps:")
            print("  1. Review clinical_factors_analysis_report.txt for key findings")
            print("  2. Examine correlation_matrix.png for factor relationships")
            print("  3. Check individual factor analysis plots for detailed insights")
            print("  4. Consider multivariable modeling for significant factors")
            print("  5. Validate findings in external cohorts")

    except Exception as e:
        print(f"\n[X] Error in analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
