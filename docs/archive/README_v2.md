# TCP_NTCP Pipeline v2.0.0

A comprehensive radiotherapy outcome modeling system that integrates **Tumor Control Probability (TCP)** alongside **Normal Tissue Complication Probability (NTCP)** analysis. This pipeline is part of the **rbGyanX** clinical decision support ecosystem.

**Maintainer:** K. Mondal  
**Version:** v2.0.0  
**Previous Version:** v1.0.1  
**License:** MIT

---

## 🎯 Key Features

### Core Capabilities
- **NTCP Modeling:** LKB Log-Logit, LKB Probit, RS Poisson models with literature-based parameters
- **TCP Modeling:** Poisson, LKB-adapted, Logistic, and EUD-based TCP models
- **Machine Learning:** ANN and XGBoost models for both NTCP and TCP prediction
- **SHAP Explainability:** Integrated ML explainability with waterfall plots, beeswarm plots, and patient-specific explanations
- **Therapeutic Ratio Analysis:** UTCP, P+, and CFTC metrics with Pareto frontier visualization
- **Publication Quality:** All plots at 600 DPI (SHAP plots at 1200 DPI)

### Scientific Rigor
- Every model cites source literature (author, year, DOI)
- Parameter ranges documented from published studies
- Deterministic outputs with versioned parameters
- Comprehensive validation and QA checks

---

## 📁 Repository Structure

```
TCP_NTCP_Pipeline_v2/
├── code1_dvh_preprocess.py          # DVH parsing from TPS exports
├── code2_dvh_plot_and_summary.py   # Dose metrics visualization
├── code3_ntcp_analysis_ml.py        # NTCP modeling (LKB/RS + ML + SHAP)
├── code4_ntcp_output_QA_reporter.py # Quality assurance checks
├── code5_ntcp_factors_analysis.py  # Clinical factors correlation
├── code6_tcp_analysis.py            # TCP analysis (NEW in v2.0)
├── code7_tcp_ntcp_integration.py   # Therapeutic ratio analysis (NEW in v2.0)
├── shap_suppl.py                    # Standalone SHAP script (backward compatible)
├── utils/
│   ├── tcp_models.py               # TCP model implementations
│   ├── ntcp_models.py              # NTCP models
│   ├── ml_models.py                # ML pipeline
│   ├── shap_utils.py               # SHAP utilities (NEW in v2.0)
│   ├── dvh_utils.py                # DVH operations
│   ├── plotting_utils.py           # Plotting functions
│   ├── stats_utils.py              # Statistical helpers
│   └── validation_utils.py         # QA utilities
├── config/
│   ├── tcp_parameters.yaml         # Literature-based TCP parameters
│   ├── ntcp_parameters.yaml       # Literature-based NTCP parameters
│   └── ml_hyperparameters.yaml    # ML model configs
├── tests/
│   ├── test_tcp_models.py          # TCP unit tests
│   ├── test_ntcp_models.py         # NTCP unit tests
│   ├── test_shap_workflow.py       # SHAP integration tests
│   └── test_integration.py         # End-to-end tests
├── requirements.txt                # Python dependencies
├── README.md                        # Original v1.0.1 README
├── README_v2.md                     # This file (v2.0 documentation)
├── MIGRATION_v1_to_v2.md           # Migration guide
└── IMPLEMENTATION_SUMMARY.md        # What changed in v2.0
```

---

## 🚀 Quick Start

### Installation

```bash
# 1. Create virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Verify installation
python -c "import shap, pandas, numpy; print('Installation OK')"
```

### Basic Workflow

#### 1. Preprocess DVH Data
```bash
python code1_dvh_preprocess.py --src ./raw_DVH --dst ./processed_DVH
```

#### 2. Generate Dose Metrics
```bash
python code2_dvh_plot_and_summary.py --cdvh_dir ./processed_DVH/cDVH_csv --outdir ./analysis_out
```

#### 3. NTCP Analysis (with integrated SHAP)
```bash
# Basic NTCP analysis
python code3_ntcp_analysis_ml.py --dDVH_dir ./processed_DVH/dDVH_csv \
    --clinical_xlsx ./clinical_input.xlsx --outdir ./analysis_out

# With SHAP explainability (RECOMMENDED)
python code3_ntcp_analysis_ml.py --dDVH_dir ./processed_DVH/dDVH_csv \
    --clinical_xlsx ./clinical_input.xlsx --outdir ./analysis_out --enable_shap
```

#### 4. Quality Assurance
```bash
python code4_ntcp_output_QA_reporter.py --input ./analysis_out --report_outdir ./QA_results
```

#### 5. Clinical Factors Analysis
```bash
python code5_ntcp_factors_analysis.py --input_file ./clinical_input.xlsx --enhanced_output_dir ./analysis_out
```

#### 6. TCP Analysis (NEW in v2.0)
```bash
# Basic TCP analysis
python code6_tcp_analysis.py --tumor_dvh_dir ./tumor_dvh --clinical_xlsx ./clinical_input.xlsx --outdir ./tcp_out

# With ML and SHAP
python code6_tcp_analysis.py --tumor_dvh_dir ./tumor_dvh --clinical_xlsx ./clinical_input.xlsx \
    --outdir ./tcp_out --enable_ml --enable_shap
```

#### 7. Therapeutic Ratio Analysis (NEW in v2.0)
```bash
python code7_tcp_ntcp_integration.py --tcp_dir ./tcp_out --ntcp_dir ./analysis_out \
    --outdir ./integration_out --generate_pareto
```

---

## 📊 Output Structure

### NTCP Analysis (code3)
```
analysis_out/
├── enhanced_ntcp_calculations.csv    # All model predictions
├── ntcp_results.xlsx                 # Comprehensive Excel file
├── plots/                            # Publication-quality plots (600 DPI)
│   ├── comprehensive_analysis.png
│   ├── model_performance_analysis.png
│   └── [organ]_*.png
└── shap_analysis/                    # SHAP outputs (if --enable_shap)
    ├── ANN/
    │   ├── summary_bar.png
    │   ├── beeswarm.png
    │   └── metrics.json
    └── XGBoost/
        ├── summary_bar.png
        ├── beeswarm.png
        └── metrics.json
```

### TCP Analysis (code6)
```
tcp_analysis_out/
├── tcp_predictions.xlsx              # Patient-level TCP predictions
├── tcp_parameters.xlsx                # Model parameters
├── tcp_ml_performance.xlsx            # ML model metrics
├── plots/                             # TCP plots (600 DPI)
│   ├── tcp_dose_response_curves.png
│   ├── tcp_roc_curves.png
│   └── tcp_calibration_plots.png
└── shap_analysis/                     # SHAP outputs (if --enable_shap)
```

### Integration Analysis (code7)
```
integration_out/
├── therapeutic_ratio_results.xlsx    # All therapeutic metrics
├── clinical_recommendation.docx      # Automated report
└── plots/
    ├── pareto_frontier.png           # TCP vs NTCP trade-off
    ├── therapeutic_ratio_curves.png  # UTCP vs dose
    └── plan_comparison_matrix.png     # Heatmap comparison
```

---

## 🔬 Scientific Models

### NTCP Models
1. **LKB Log-Logit** (Lyman, 1985)
2. **LKB Probit** (Lyman, 1985)
3. **RS Poisson** (Relative Seriality, 1991)

### TCP Models
1. **Poisson TCP** (Webb & Nahum, 1993)
   - Reference: Webb S, Nahum AE. Phys Med Biol. 1993;38(6):653-666
2. **LKB-Adapted TCP** (Okunieff et al., 1995)
   - Reference: Okunieff P, et al. Int J Radiat Oncol Biol Phys. 1995;33(1):179-190
3. **Logistic TCP** (Brahme, 1984)
   - Reference: Brahme A. Acta Radiol Oncol. 1984;23(5):379-391
4. **EUD-Based TCP** (Niemierko, 1997)
   - Reference: Niemierko A. Med Phys. 1997;24(1):103-110

### Therapeutic Metrics
1. **UTCP** (Uncomplicated TCP) = TCP × (1 - NTCP_composite)
   - Reference: Ågren Cronqvist AK. Radiother Oncol. 1995;34(1):14-20
2. **P+** (Brahme metric) = TCP - NTCP_critical
   - Reference: Brahme A. Int J Radiat Oncol Biol Phys. 1984;10(11):2095-2104
3. **CFTC** (Complication-Free Tumor Control) = TCP × ∏(1 - NTCP_i)

---

## 🎨 SHAP Explainability

### Integrated Workflow (Recommended)
SHAP is now integrated into the main ML workflow:

```bash
# NTCP with SHAP
python code3_ntcp_analysis_ml.py ... --enable_shap

# TCP with SHAP
python code6_tcp_analysis.py ... --enable_shap
```

### Standalone Workflow (Backward Compatible)
For batch processing or post-hoc analysis:

```bash
python shap_suppl.py --features_csv ./ml_features.csv --outdir ./shap_outputs --organ Parotid
```

### SHAP Outputs
- **Summary Bar Plot:** Global feature importance (1200 DPI)
- **Beeswarm Plot:** Feature directionality and distribution (1200 DPI)
- **Metrics JSON:** Quantitative importance scores
- **Captions:** Automatic caption generation for publications

---

## 📈 Advanced Features

### Multi-Objective Optimization
The `code7` integration module provides:
- **Pareto Frontier:** Visualize optimal TCP vs NTCP trade-offs
- **Isoeffect Curves:** BED-based dose-fractionation nomograms
- **Plan Comparison:** Matrix visualization of multiple treatment plans
- **Clinical Recommendations:** Automated DOCX reports

### Machine Learning
- **Cross-Validation:** 5-fold stratified CV for robust evaluation
- **Anti-Overfitting:** Early stopping, regularization, validation splits
- **Metrics:** AUC, Brier score, calibration plots, ROC curves
- **Explainability:** SHAP integration for all ML models

---

## 🔧 Dependencies

### Core Dependencies
```
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
seaborn>=0.12.0
scipy>=1.10.0
scikit-learn>=1.3.0
xgboost>=2.0.0
shap>=0.44.0                    # NEW in v2.0 (was missing in v1.0.1)
python-docx>=0.8.11
openpyxl>=3.1.0
```

### Enhanced Dependencies (Optional)
```
pydicom>=2.4.0                  # DICOM support (future)
SimpleITK>=2.3.0                # Image processing (future)
rt-utils>=1.2.0                  # RTSTRUCT parsing (future)
PyMedPhys>=0.40.0                # Medical physics utilities (future)
statsmodels>=0.14.0               # Statistical modeling
mlflow>=2.9.0                    # Experiment tracking
```

See `requirements.txt` for complete list.

---

## 🧪 Testing

### Run Tests
```bash
# Unit tests
pytest tests/test_tcp_models.py -v
pytest tests/test_ntcp_models.py -v
pytest tests/test_shap_workflow.py -v

# Integration tests
pytest tests/test_integration.py -v
```

### Backward Compatibility
All v1.0.1 workflows produce **identical outputs** in v2.0.0:
- code1-code5 work exactly as before
- code3 without `--enable_shap` produces identical outputs
- shap_suppl.py produces identical outputs (refactored internally)

---

## 📚 Documentation

- **README_v2.md** (this file) - Complete v2.0 documentation
- **MIGRATION_v1_to_v2.md** - Migration guide for upgrading from v1.0.1
- **IMPLEMENTATION_SUMMARY.md** - Detailed changelog
- **README.md** - Original v1.0.1 documentation

---

## 🔄 Version History

### v2.0.0 (Current)
- ✅ Added TCP modeling (code6)
- ✅ Integrated SHAP into ML workflow
- ✅ Added therapeutic ratio analysis (code7)
- ✅ Refactored SHAP utilities (utils/shap_utils.py)
- ✅ Added SHAP to requirements.txt (was missing)
- ✅ Enhanced code organization (utils/, config/, tests/)
- ✅ Backward compatible with v1.0.1

### v1.0.1 (Previous)
- NTCP modeling (LKB, RS)
- ML models (ANN, XGBoost)
- SHAP analysis (standalone script)
- Clinical factors analysis
- QA reporting

---

## 🤝 Contributing

This pipeline is part of a PhD dissertation and manuscript under review. For questions or issues:
- **GitHub Issues:** Report bugs or request features
- **GitHub Discussions:** Ask questions
- **Contact:** Via project maintainer

---

## 📄 Citation

If you use this pipeline in your research, please cite:

```
Mondal, K., et al. (2025). TCP_NTCP Pipeline v2.0.0: A Comprehensive 
Radiotherapy Outcome Modeling System [Computer software]. 
Zenodo. https://doi.org/10.5281/zenodo.xxxxxxx
```

---

## ⚠️ Important Notes

### Backward Compatibility
- **All v1.0.1 workflows work identically in v2.0.0**
- **No breaking changes** - all changes are additive
- **SHAP integration is opt-in** via `--enable_shap` flag

### Scientific Rigor
- Every model has literature citations
- All parameters documented with ranges
- Deterministic outputs with fixed random seeds
- Comprehensive validation and QA checks

### Clinical Use
- This is a research tool, not a clinical decision support system
- All outputs should be reviewed by qualified medical physicists
- Model parameters should be validated for your institution

---

## 📞 Support

- **Documentation:** See `MIGRATION_v1_to_v2.md` for upgrade guide
- **Issues:** GitHub Issues
- **Questions:** GitHub Discussions

---

**Version:** 2.0.0  
**Last Updated:** 2025-01-XX  
**Maintainer:** K. Mondal  
**License:** MIT

