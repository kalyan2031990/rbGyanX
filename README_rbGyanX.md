# rbGyanX v1.0
**Radiobiological Clinical Decision Support System**

A comprehensive, production-ready platform for radiobiological analysis including Normal Tissue Complication Probability (NTCP) and Tumor Control Probability (TCP) modeling with integrated machine learning capabilities.

---

## Overview

rbGyanX v1.0 is a clinical decision support system designed for medical physicists, radiation oncologists, and clinical researchers. It provides:

- **Intelligent DVH Preprocessing**: Auto-detects and processes multiple DVH formats (Eclipse TXT, CSV, DICOM)
- **Traditional Radiobiological Models**: LKB Log-Logistic, LKB Probit, RS Poisson (NTCP); Poisson, LKB, Logistic, EUD (TCP)
- **Machine Learning Models**: ANN and XGBoost with proper cross-validation
- **SHAP Explainability**: Integrated ML interpretability with waterfall and beeswarm plots
- **Therapeutic Ratio Analysis**: UTCP, P+, and CFTC metrics with Pareto frontier visualization
- **Publication-Quality Outputs**: All plots at 600 DPI (SHAP plots at 1200 DPI)
- **Comprehensive QA**: Automated quality assurance checks and reporting

---

## Installation

### Requirements

- Python 3.8 or higher
- Windows, Linux, or macOS

### Setup

1. Clone or download the rbGyanX repository:
```bash
cd tcp_ntcp_pipeline_project
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Required Packages

- pandas
- numpy
- matplotlib
- scikit-learn
- xgboost
- openpyxl (for Excel support)
- pydicom (optional, for DICOM support in v1.1)
- rt-utils (optional, for DICOM support in v1.1)
- PyYAML (optional, for configuration save/load)

---

## Quick Start

### Launching the GUI

```bash
python rbgyanx_gui.py
```

### Basic Workflow

1. **Select Output Directory**: Choose where all results will be saved
2. **Select DVH Input**: Choose a single DVH file or directory containing multiple DVH files
3. **Select Clinical Data** (optional): Required for ML models and clinical factors analysis
4. **Choose Analysis Type**: NTCP (Normal Tissue) or TCP (Tumor)
5. **Run Steps**: Execute steps individually or use "Run All" for automated pipeline

### Command Line Usage

#### Step 1: DVH Preprocessing
```bash
python code1_dvh_preprocess.py <input_path> --outdir <output_dir>
```

#### Step 2: Dose Metrics & Plots
```bash
python code2_dvh_plot_and_summary.py <processed_dvh_dir> --outdir <output_dir>
```

#### Step 3: NTCP/TCP Analysis
```bash
# NTCP
python code3_ntcp_analysis_ml.py --dvh_dir <ddvh_dir> --output_dir <output_dir> [--patient_data <clinical.xlsx>] [--ml_models] [--enable_shap]

# TCP
python code6_tcp_analysis.py --tumor_dvh_dir <ddvh_dir> --clinical_xlsx <clinical.xlsx> --outdir <output_dir> [--enable_ml] [--enable_shap]
```

---

## Supported DVH Formats

### Format 1: Varian Eclipse TXT Export
- **Location**: TPS export from Varian Eclipse
- **Characteristics**:
  - Header with patient metadata (Patient Name, ID, Date)
  - Structure name on line 13: "Structure: SPINAL CORD"
  - Volume in line 17: "Volume [cm³]: 19.3"
  - DVH data starts after line 30: "Dose [cGy]    Structure Volume [cm³]"
  - Dose in cGy (automatically converted to Gy)
  - Contains both OAR and PTV data

**Example**: `ABDUL SALAM  CORD.txt`

### Format 2: Simple CSV (dDVH)
- **Location**: Simple CSV export
- **Characteristics**:
  - Header: "Dose[Gy],Volume[cm3]"
  - Clean format, already in Gy and cm³
  - Differential DVH (dDVH)
  - Naming: `PT{number}_{OrganName}.csv`

**Example**: `PT012_Parotid.csv`

### Format 3: PTV-specific TXT (Tumor DVH)
- **Location**: Eclipse export for tumor structures
- **Characteristics**:
  - Same Eclipse format as Format 1
  - Structure name contains "PTV": "Structure: PTV70new"
  - Higher dose ranges (3605-7674 cGy for PTV70)

**Example**: `KASTOORI_PTV70.txt`

### Format 4: DICOM RT Files (Coming in v1.1)
- **Location**: DICOM RT exports
- **Files**: RS.*.dcm (Structure Set), RP.*.dcm (Plan), RD.*.dcm (Dose)
- **Note**: DICOM support will be available in rbGyanX v1.1

---

## Clinical Data Format

### Required Columns

- **Patient ID**: `PatientID`, `Patient_ID`, `PatientId`, `Patient_AnoID`, or `ID`
- **Toxicity Outcome**: `Observed_Toxicity`, `Toxicity`, `Xerostomia_G2plus`, `Dysphagia_G2plus`, etc. (binary: 0/1)

### Optional Columns

- **Organ**: `Organ`, `Structure`, `OAR`, `Site`
- **Treatment Parameters**: `TotalDose`, `Dose_per_Fraction`, `Fractions`, `Technique`
- **Clinical Factors**: `Age`, `Sex`, `ECOG`, `Stage_T`, `Stage_N`, `Smoking`, `Chemo`

### Example Formats

#### Format A: Simple Clinical (30 patients)
```
PatientID, Organ, Observed_Toxicity, Technique, TotalDose, FollowUpMonths
PT001, Parotid, 1, IMRT, 70, 24
PT002, Parotid, 0, VMAT, 70, 18
```

#### Format B: Comprehensive Toxicity (20 patients)
```
PatientID, Site, Age, Sex, Technique, Total_Dose_Gy, Xerostomia_G2plus, Dysphagia_G2plus
PT001, HNSCC, 65, M, IMRT, 70, 1, 0
PT002, HNSCC, 58, F, VMAT, 70, 0, 1
```

#### Format C: Treatment Parameters (Multi-organ)
```
PatientId, Patient_AnoID, Organ, TotalDose_Gy, n_frac, dose_per_frac_Gy, Toxicity
PT001, PT001, Parotid, 70, 35, 2.0, 1
PT001, PT001, Larynx, 70, 35, 2.0, 0
```

**Note**: rbGyanX automatically detects column names and handles variations.

---

## Usage Examples

### Example 1: NTCP Analysis with ML

1. Launch GUI: `python rbgyanx_gui.py`
2. Select output directory
3. Select DVH directory: `C:\path\to\OAR_DVH_files\`
4. Select clinical data: `C:\path\to\clinical_data.xlsx`
5. Choose "NTCP Analysis"
6. Enable "ML Models" checkbox
7. Enable "SHAP Explainability" (optional)
8. Click "Run All NTCP Steps"

### Example 2: TCP Analysis (Tumor)

1. Launch GUI
2. Select output directory
3. Select PTV DVH directory: `C:\path\to\PTV_DVH_files\`
4. Select clinical data (required for TCP)
5. Choose "TCP Analysis"
6. Select tumor type: HNSCC, Prostate, Lung, etc.
7. Click "Run All TCP Steps"

### Example 3: Command Line - Batch Processing

```bash
# Preprocess DVH files
python code1_dvh_preprocess.py C:\input\DVH_files --outdir C:\output\processed

# Calculate dose metrics
python code2_dvh_plot_and_summary.py C:\output\processed --outdir C:\output\metrics

# NTCP analysis with ML
python code3_ntcp_analysis_ml.py --dvh_dir C:\output\processed\dDVH_csv --output_dir C:\output\ntcp --patient_data C:\input\clinical.xlsx --ml_models --enable_shap
```

---

## Output Structure

```
output_directory/
├── processed_DVH/
│   ├── cDVH_csv/          # Cumulative DVH files
│   ├── dDVH_csv/          # Differential DVH files
│   └── processed_dvh.xlsx # Summary workbook
├── dose_metrics/
│   ├── plots/             # DVH plots (600 DPI)
│   └── tables/            # Dose metrics tables
├── ntcp_analysis/         # NTCP results
│   ├── plots/             # Dose-response, ROC, calibration plots
│   ├── models/            # Saved ML models
│   └── results.xlsx       # Comprehensive results
├── tcp_analysis/          # TCP results (if TCP mode)
├── clinical_factors/      # Clinical factors analysis
├── qa_reports/            # Quality assurance reports
└── tcp_ntcp_integration/  # Therapeutic ratio analysis
```

---

## Features

### Intelligent Data Preprocessing
- **Auto-format Detection**: Automatically detects Eclipse TXT, CSV, and DICOM formats
- **Patient ID Extraction**: Handles diverse naming conventions
- **OAR vs PTV Detection**: Automatically identifies tumor vs normal tissue structures
- **Dose Unit Conversion**: Converts cGy to Gy automatically
- **DVH Type Detection**: Detects cumulative vs differential DVH

### Traditional Models
- **NTCP Models**: LKB Log-Logistic, LKB Probit, RS Poisson
- **TCP Models**: Poisson, LKB-adapted, Logistic, EUD-based
- **Literature-Based Parameters**: All models use published parameter values with citations

### Machine Learning
- **ANN (Artificial Neural Network)**: Multi-layer perceptron with dropout
- **XGBoost**: Gradient boosting with hyperparameter optimization
- **Cross-Validation**: Proper k-fold cross-validation to prevent overfitting
- **SHAP Integration**: Explainability analysis for ML predictions

### Quality Assurance
- **Patient Count Validation**: Flags inflated patient counts
- **Unrealistic Value Detection**: Identifies NaNs, constant predictions, out-of-range values
- **Overfitting Detection**: Warns about potential ML overfitting/leakage
- **Comprehensive Reports**: DOCX and Excel QA reports

---

## Citation

If you use rbGyanX in your research, please cite:

```
rbGyanX v1.0 - Radiobiological Clinical Decision Support System
Version: 1.0.0
Release Date: 2025-12-25
```

For specific model citations, refer to the model documentation and parameter files in `config/`.

---

## License

MIT License - See LICENSE file for details.

---

## Contact & Support

- **Repository**: [GitHub Repository URL]
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Documentation**: See `CURSOR_PROMPT_RBGYANX_V1_COMPLETE.md` for detailed specifications

---

## Version History

### v1.0.0 (2025-12-25)
- Initial production release
- Universal DVH parser with format auto-detection
- Integrated GUI with validation and preview
- Comprehensive error handling
- Traditional and ML models for NTCP and TCP
- SHAP explainability integration
- Therapeutic ratio analysis

### Upcoming: v1.1
- DICOM RT support
- Additional TPS format support
- Enhanced visualization options

---

## Acknowledgments

rbGyanX is built on established radiobiological models and methodologies from the literature. All model parameters are sourced from peer-reviewed publications with proper citations.

---

**rbGyanX v1.0** - Empowering Clinical Decision Support Through Radiobiological Analysis

