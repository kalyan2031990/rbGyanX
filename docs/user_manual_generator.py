"""
Auto-generated User Manual Generator for rbGyanX

This module scans the codebase at runtime to generate an up-to-date HTML user manual
that reflects the actual features, workflow, and structure of rbGyanX_basic.

Author: rbGyanX Team
Version: 1.0.0
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class UserManualGenerator:
    """Generates HTML user manual by scanning codebase and configuration files."""
    
    def __init__(self, repo_root: Path):
        """
        Initialize the generator.
        
        Parameters
        ----------
        repo_root : Path
            Root directory of the rbGyanX repository
        """
        self.repo_root = Path(repo_root)
        self.docs_dir = self.repo_root / "docs"
        self.docs_dir.mkdir(exist_ok=True)
        self.output_file = self.docs_dir / "rbgyanx_user_manual.html"
        
        # Paths to scan
        self.feature_registry_path = self.repo_root / "core" / "feature_registry.json"
        self.version_path = self.repo_root / "VERSION.txt"
        self.clinical_templates_dir = self.repo_root / "clinical" / "templates"
        self.clinical_schema_path = self.repo_root / "clinical" / "clinical_schema.json"
        
        # Load data
        self.feature_registry = self._load_feature_registry()
        self.version, self.edition = self._load_version()
        
    def _load_feature_registry(self) -> Dict:
        """Load feature registry JSON."""
        try:
            with open(self.feature_registry_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _load_version(self) -> tuple:
        """Load version from VERSION.txt (single source of truth)."""
        try:
            from rbgyanx.app_metadata import read_version_from_file

            version = read_version_from_file(self.repo_root)
        except ImportError:
            version = "1.0.0"
        edition = "BASIC"
        try:
            if self.version_path.is_file():
                text = self.version_path.read_text(encoding="utf-8")
                if "Pro" in text:
                    edition = "Pro"
        except OSError:
            pass
        return version, edition
    
    def _scan_templates(self) -> List[str]:
        """Scan for template files in clinical/templates directory."""
        templates = []
        if self.clinical_templates_dir.exists():
            for template_file in self.clinical_templates_dir.glob("*"):
                if template_file.is_file():
                    templates.append(template_file.name)
        return sorted(templates)
    
    def _scan_schema(self) -> Optional[Dict]:
        """Load clinical schema if it exists."""
        if self.clinical_schema_path.exists():
            try:
                with open(self.clinical_schema_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    def _get_output_structure(self) -> Dict[str, List[str]]:
        """Generate output folder structure based on analysis modes."""
        structure = {
            "common": [
                "processed_DVH/",
                "  ├── cDVH_csv/          # Cumulative DVH files",
                "  ├── dDVH_csv/          # Differential DVH files",
                "  └── processed_dvh.xlsx # Summary workbook",
                "dose_metrics/",
                "  ├── tables/            # Excel files with metrics",
                "  └── plots/             # DVH plots (600 DPI)",
                "qa/",
                "  └── qa_summary_tables.xlsx",
                "logs/                   # Execution logs"
            ],
            "tcp_only": [
                "tcp_analysis/",
                "  ├── tcp_predictions.xlsx",
                "  ├── tcp_parameters.xlsx",
                "  ├── tcp_ml_performance.xlsx (if ML enabled)",
                "  └── plots/"
            ],
            "ntcp_only": [
                "ntcp_analysis/",
                "  ├── enhanced_ntcp_calculations.csv",
                "  ├── ntcp_ml_performance.xlsx (if ML enabled)",
                "  └── plots/"
            ],
            "tcp_ntcp": [
                "tcp_analysis/",
                "  ├── tcp_predictions.xlsx",
                "  ├── tcp_parameters.xlsx",
                "  └── plots/",
                "ntcp_analysis/",
                "  ├── enhanced_ntcp_calculations.csv",
                "  └── plots/",
                "integration/",
                "  ├── therapeutic_metrics.xlsx",
                "  └── plots/"
            ]
        }
        return structure
    
    def _get_gui_tabs(self) -> List[Dict[str, str]]:
        """Get GUI tabs information from codebase analysis."""
        tabs = [
            {
                "name": "Patient Cohort",
                "description": "Displays patient cohort summary statistics and demographics",
                "purpose": "Provides overview of analyzed patient population",
                "inputs": "Requires Step 1 completion (DVH preprocessing)",
                "outputs": "Cohort summary tables and statistics"
            },
            {
                "name": "DVH Plots",
                "description": "Visualizes Dose-Volume Histograms for all structures",
                "purpose": "Graphical representation of dose distribution across volumes",
                "inputs": "Requires Step 2 completion (dose metrics calculation)",
                "outputs": "Publication-quality DVH plots (600 DPI)"
            },
            {
                "name": "Dose-Response",
                "description": "Shows dose-response curves for TCP/NTCP models",
                "purpose": "Visualize relationship between dose and probability outcomes",
                "inputs": "Requires Step 3 completion (TCP/NTCP analysis)",
                "outputs": "Dose-response curves for selected models"
            },
            {
                "name": "ROC/Calibration",
                "description": "Receiver Operating Characteristic and calibration plots for ML models",
                "purpose": "Evaluate ML model performance and calibration",
                "inputs": "Requires Step 3 with ML models enabled",
                "outputs": "ROC curves, calibration plots, performance metrics"
            },
            {
                "name": "Factor Plots",
                "description": "Clinical factors analysis and correlation visualizations",
                "purpose": "Explore relationships between clinical factors and outcomes",
                "inputs": "Requires Step 4 completion (clinical factors analysis)",
                "outputs": "Correlation plots, factor importance charts"
            },
            {
                "name": "Therapeutic Window",
                "description": "TCP-NTCP integration showing therapeutic ratio analysis",
                "purpose": "Visualize balance between tumor control and normal tissue complications",
                "inputs": "Requires Step 6 completion (TCP-NTCP integration)",
                "outputs": "UTCP plots, Pareto frontier, therapeutic window visualizations"
            },
            {
                "name": "Validation & QA",
                "description": "Quality assurance metrics and validation flags",
                "purpose": "Display physics consistency checks and QA warnings",
                "inputs": "Requires Step 1 and Step 5 completion",
                "outputs": "Validation metrics, QA flags, overfitting warnings"
            }
        ]
        return tabs
    
    def _get_workflow_steps(self) -> List[Dict[str, str]]:
        """Get workflow steps information."""
        steps = []
        if self.feature_registry and "workflow_stages" in self.feature_registry:
            for step_key, step_info in self.feature_registry["workflow_stages"].items():
                step_num = step_key.replace("step", "")
                steps.append({
                    "number": step_num,
                    "name": step_info.get("name", ""),
                    "description": step_info.get("description", ""),
                    "output": step_info.get("output", "")
                })
        else:
            # Fallback if registry not available
            steps = [
                {"number": "1", "name": "DVH Preprocessing", 
                 "description": "Import and preprocess differential/cumulative DVH files",
                 "output": "Processed DVH data"},
                {"number": "2", "name": "Dose Metrics & Plots",
                 "description": "Calculate dose metrics and generate DVH plots",
                 "output": "Dose metrics, DVH visualizations"},
                {"number": "3", "name": "TCP/NTCP Analysis",
                 "description": "Calculate TCP or NTCP using traditional and ML models",
                 "output": "TCP/NTCP predictions, performance metrics"},
                {"number": "4", "name": "Clinical Factors Analysis",
                 "description": "Analyze clinical factors and their impact on outcomes",
                 "output": "Factor analysis, correlations"},
                {"number": "5", "name": "Quality Assurance",
                 "description": "Comprehensive QA checks including overfitting inspection",
                 "output": "QA report, warnings, flags"},
                {"number": "6", "name": "TCP-NTCP Integration",
                 "description": "Integrate TCP and NTCP for therapeutic ratio analysis",
                 "output": "Therapeutic ratio, integrated metrics"}
            ]
        return steps
    
    def _get_analysis_modes(self) -> List[Dict[str, str]]:
        """Get supported analysis modes."""
        modes = [
            {
                "name": "TCP Only",
                "description": "Tumor Control Probability analysis for target structures (PTV/GTV/CTV)",
                "use_case": "Evaluate probability of tumor control based on dose distribution to targets",
                "required_inputs": "Target DVH files (PTV, GTV, CTV structures)",
                "outputs": "TCP predictions, dose-response curves, ML performance metrics (if enabled)"
            },
            {
                "name": "NTCP Only",
                "description": "Normal Tissue Complication Probability analysis for OAR structures",
                "use_case": "Evaluate probability of normal tissue complications based on dose to OARs",
                "required_inputs": "OAR DVH files (Parotid, Spinal Cord, etc.)",
                "outputs": "NTCP predictions, dose-response curves, ML performance metrics (if enabled)"
            },
            {
                "name": "TCP + NTCP (Combined)",
                "description": "Both TCP and NTCP analyses with therapeutic ratio integration",
                "use_case": "Comprehensive evaluation of treatment plan balancing tumor control and toxicity risk",
                "required_inputs": "Both target and OAR DVH files",
                "outputs": "TCP and NTCP predictions, therapeutic ratios (UTCP, P+, CFTC), integration plots"
            }
        ]
        return modes
    
    def _get_traditional_models(self) -> Dict[str, List[Dict]]:
        """Get traditional radiobiological models."""
        models = {"ntcp": [], "tcp": []}
        
        if self.feature_registry and "enabled_features" in self.feature_registry:
            features = self.feature_registry["enabled_features"]
            if "traditional_models" in features:
                trad_models = features["traditional_models"]
                
                if "ntcp" in trad_models:
                    for model_key, model_info in trad_models["ntcp"].items():
                        models["ntcp"].append({
                            "name": model_key,
                            "description": model_info.get("description", ""),
                            "reference": model_info.get("reference", "")
                        })
                
                if "tcp" in trad_models:
                    for model_key, model_info in trad_models["tcp"].items():
                        models["tcp"].append({
                            "name": model_key,
                            "description": model_info.get("description", ""),
                            "reference": model_info.get("reference", "")
                        })
        
        return models
    
    def _get_ml_features(self) -> Dict:
        """Get ML model features."""
        ml_info = {
            "enabled": False,
            "models": [],
            "shap_enabled": False,
            "description": ""
        }
        
        if self.feature_registry and "enabled_features" in self.feature_registry:
            features = self.feature_registry["enabled_features"]
            if "ml_models" in features:
                ml_info["enabled"] = features["ml_models"].get("enabled", False)
                ml_info["models"] = features["ml_models"].get("models", [])
                ml_info["description"] = features["ml_models"].get("description", "")
            
            if "shap_explainability" in features:
                ml_info["shap_enabled"] = features["shap_explainability"].get("enabled", False)
        
        return ml_info
    
    def generate_html(self) -> str:
        """Generate the complete HTML manual."""
        templates = self._scan_templates()
        schema = self._scan_schema()
        output_structure = self._get_output_structure()
        tabs = self._get_gui_tabs()
        steps = self._get_workflow_steps()
        modes = self._get_analysis_modes()
        models = self._get_traditional_models()
        ml_info = self._get_ml_features()
        
        app_name = self.feature_registry.get("app_info", {}).get("name", "rbGyanX")
        app_version = self.feature_registry.get("app_info", {}).get("version", self.version)
        app_edition = "BASIC"  # OBJECTIVE B: Always BASIC for this version
        description = "Radiobiology-guided Clinical Decision Support System (CDSS) Framework"  # OBJECTIVE B: Canonical text
        disclaimer = self.feature_registry.get("dashboard_text", {}).get("disclaimer",
            "This tool provides decision support and should not replace clinical judgment.")
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="version" content="{app_version}">
    <meta name="edition" content="{app_edition}">
    <title>{app_name} {app_edition} User Manual</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        
        header {{
            background: linear-gradient(135deg, #000080 0%, #4169E1 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 0.5rem;
        }}
        
        header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .meta {{
            background: #f8f9fa;
            padding: 1rem 2rem;
            border-bottom: 2px solid #000080;
            font-size: 0.9em;
            color: #666;
        }}
        
        nav {{
            background: #2c3e50;
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        nav a {{
            color: white;
            text-decoration: none;
            margin-right: 2rem;
            padding: 0.5rem 1rem;
            display: inline-block;
            border-radius: 4px;
            transition: background 0.3s;
        }}
        
        nav a:hover {{
            background: #34495e;
        }}
        
        .content {{
            padding: 2rem;
        }}
        
        .section {{
            margin-bottom: 3rem;
            scroll-margin-top: 80px;
        }}
        
        .section h2 {{
            color: #000080;
            font-size: 2em;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 3px solid #000080;
        }}
        
        .section h3 {{
            color: #4169E1;
            font-size: 1.5em;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
        }}
        
        .section h4 {{
            color: #555;
            font-size: 1.2em;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }}
        
        .info-box {{
            background: #e3f2fd;
            border-left: 4px solid #2196F3;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}
        
        .warning-box {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}
        
        .disclaimer-box {{
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .workflow-box {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        
        .step {{
            background: #f8f9fa;
            border: 2px solid #000080;
            border-radius: 8px;
            padding: 1.5rem;
            transition: transform 0.3s, box-shadow 0.3s;
        }}
        
        .step:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        
        .step-number {{
            display: inline-block;
            background: #000080;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            text-align: center;
            line-height: 40px;
            font-weight: bold;
            margin-right: 1rem;
        }}
        
        .mode-card {{
            background: white;
            border: 2px solid #4169E1;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 1rem 0;
        }}
        
        .mode-card h4 {{
            color: #000080;
            margin-top: 0;
        }}
        
        .tab-card {{
            background: #f8f9fa;
            border-left: 4px solid #4169E1;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}
        
        .tab-card h4 {{
            color: #000080;
            margin-top: 0;
        }}
        
        pre {{
            background: #f4f4f4;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 1rem;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        ul, ol {{
            margin-left: 2rem;
            margin-top: 0.5rem;
        }}
        
        li {{
            margin: 0.5rem 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }}
        
        table th, table td {{
            border: 1px solid #ddd;
            padding: 0.75rem;
            text-align: left;
        }}
        
        table th {{
            background: #000080;
            color: white;
        }}
        
        table tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        
        footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 2rem;
            margin-top: 3rem;
        }}
        
        .model-list {{
            list-style: none;
            margin-left: 0;
        }}
        
        .model-list li {{
            background: #f8f9fa;
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-left: 3px solid #4169E1;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{app_name} (BASIC)</h1>
            <div class="subtitle">{description}</div>
            <div class="subtitle" style="font-size: 0.9em; margin-top: 0.5rem;">Version {app_version} | Edition: BASIC</div>
            <div class="subtitle" style="font-size: 0.8em; margin-top: 0.5rem; opacity: 0.8;">Generated: {datetime.now().strftime('%Y-%m-%d')}</div>
        </header>
        
        <div class="meta">
            <strong>Edition:</strong> BASIC | <strong>Version:</strong> {app_version} | <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 
            <strong>Manual Type:</strong> Auto-generated from codebase
        </div>
        
        <nav>
            <a href="#overview">Overview</a>
            <a href="#analysis-modes">Analysis Modes</a>
            <a href="#workflow">Workflow</a>
            <a href="#tabs">GUI Tabs</a>
            <a href="#radiobiology">Radiobiology Context</a>
            <a href="#inputs">Input Requirements</a>
            <a href="#outputs">Output Structure</a>
            <a href="#limitations">Limitations</a>
        </nav>
        
        <div class="content">
            <section id="overview" class="section">
                <h2>1. What is rbGyanX_basic?</h2>
                
                <div class="disclaimer-box">
                    <strong>⚠️ IMPORTANT DISCLAIMER:</strong><br>
                    {disclaimer}<br>
                    This software is intended for research and educational purposes. 
                    Clinical decisions should be made by qualified medical professionals.
                </div>
                
                <p><strong>rbGyanX_basic</strong> is a radiobiology-guided clinical decision support framework 
                designed for medical physicists, radiation oncologists, and clinical researchers. 
                It provides comprehensive tools for:</p>
                
                <ul>
                    <li><strong>DVH Preprocessing:</strong> Intelligent parsing and canonicalization of 
                    Dose-Volume Histogram files from multiple treatment planning systems</li>
                    <li><strong>Physical Dose Metrics:</strong> Automated calculation of standard 
                    dose metrics for both target structures (PTV/GTV/CTV) and organs at risk (OARs)</li>
                    <li><strong>Radiobiological Modeling:</strong> Traditional models (LKB, RS, Poisson) 
                    and machine learning models (ANN, XGBoost) for TCP and NTCP prediction</li>
                    <li><strong>Clinical Factors Analysis:</strong> Exploration of relationships between 
                    clinical variables and treatment outcomes</li>
                    <li><strong>Quality Assurance:</strong> Automated checks for model reliability, 
                    overfitting detection, and data quality</li>
                    <li><strong>Therapeutic Ratio Analysis:</strong> Integration of TCP and NTCP for 
                    comprehensive treatment plan evaluation</li>
                </ul>
                
                <div class="info-box">
                    <strong>Scope:</strong> rbGyanX_basic focuses on retrospective analysis and research applications. 
                    It does not provide real-time clinical decision support or integrate with treatment planning systems.
                </div>
                
                <div class="disclaimer-box" style="margin-top: 1.5rem;">
                    <strong>⚠️ RESEARCH USE ONLY - NOT FOR CLINICAL DECISIONS</strong><br>
                    This software is intended for research and educational purposes only. 
                    It does NOT provide clinical advice, treatment recommendations, or autonomous decision-making capabilities.
                    All clinical decisions must be made by qualified healthcare professionals based on their clinical judgment.
                </div>
            </section>
            
            <section id="analysis-modes" class="section">
                <h2>2. Supported Analysis Modes</h2>
                
                <p>rbGyanX_basic supports three analysis modes, each tailored for specific use cases:</p>
"""
        
        for mode in modes:
            html += f"""
                <div class="mode-card">
                    <h4>{mode['name']}</h4>
                    <p><strong>Description:</strong> {mode['description']}</p>
                    <p><strong>Use Case:</strong> {mode['use_case']}</p>
                    <p><strong>Required Inputs:</strong> {mode['required_inputs']}</p>
                    <p><strong>Outputs:</strong> {mode['outputs']}</p>
                </div>
"""
        
        html += """
            </section>
            
            <section id="workflow" class="section">
                <h2>3. Step-by-Step Workflow</h2>
                
                <p>The rbGyanX pipeline follows a standardized 6-step workflow. Each step builds upon 
                the previous one, and steps can be run individually or automatically via "Run All" mode.</p>
                
                <div class="workflow-box">
"""
        
        for step in steps:
            html += f"""
                    <div class="step">
                        <span class="step-number">Step {step['number']}</span>
                        <strong>{step['name']}</strong><br>
                        <p style="margin-top: 0.5rem;">{step['description']}</p>
                        <p style="margin-top: 0.5rem; font-size: 0.9em; color: #666;">
                            <strong>Output:</strong> {step['output']}
                        </p>
                    </div>
"""
        
        html += """
                </div>
                
                <div class="info-box">
                    <strong>Execution Order:</strong> Steps must be executed sequentially (Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6). 
                    Step 6 (TCP-NTCP Integration) is only available when both TCP and NTCP analyses are enabled.
                </div>
            </section>
            
            <section id="tabs" class="section">
                <h2>4. GUI Tabs Explanation</h2>
                
                <p>The rbGyanX GUI provides multiple visualization and analysis tabs. Each tab serves a specific 
                purpose and requires completion of specific workflow steps.</p>
"""
        
        for tab in tabs:
            html += f"""
                <div class="tab-card">
                    <h4>{tab['name']}</h4>
                    <p><strong>What it does:</strong> {tab['description']}</p>
                    <p><strong>Why it exists:</strong> {tab['purpose']}</p>
                    <p><strong>Required inputs:</strong> {tab['inputs']}</p>
                    <p><strong>Outputs produced:</strong> {tab['outputs']}</p>
                </div>
"""
        
        html += """
            </section>
            
            <section id="ask-rbgyanx" class="section">
                <h2>5. Ask rbGyanX - Educational Assistant</h2>
                
                <div class="warning-box" style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin: 1rem 0;">
                    <strong>⚠️ EDUCATIONAL USE ONLY - NOT FOR CLINICAL DECISIONS</strong><br>
                    Ask rbGyanX provides educational information only. It does NOT provide clinical advice or treatment recommendations.
                    All clinical decisions must be made by qualified healthcare professionals.
                </div>
                
                <h3>5.1 What the feature does</h3>
                <p><strong>Purpose:</strong> Ask rbGyanX provides educational support and helps interpret rbGyanX outputs. 
                It is designed to assist users in understanding radiobiological concepts and analysis results.</p>
                
                <p><strong>Required inputs:</strong> User questions (text-based queries). No access to patient data or files.</p>
                
                <p><strong>Output interpretation:</strong> Educational explanations, concept clarifications, and guidance on interpreting results. 
                All responses include disclaimers that this is educational support, not clinical decision-making.</p>
                
                <h4>Capabilities:</h4>
                <ul>
                    <li><strong>Explain Concepts:</strong> Radiobiology theory, TCP/NTCP models, physics concepts, statistics</li>
                    <li><strong>Interpret rbGyanX Outputs:</strong> Help understand analysis results, QA warnings, and visualizations</li>
                    <li><strong>Help Draft Text, Tables, Figures:</strong> Assist in research writing (anonymized)</li>
                    <li><strong>Suggest Keywords:</strong> Provide literature search keywords for PubMed and databases</li>
                    <li><strong>Explain QA Warnings:</strong> Clarify quality assurance messages and their meanings</li>
                    <li><strong>Mathematical Calculations:</strong> Scientific calculator for equations and formulas</li>
                    <li><strong>Equation Rendering:</strong> Help draft equations for papers (LaTeX-style)</li>
                </ul>
                
                <p><strong>Limitations:</strong> Ask rbGyanX cannot access patient data, make clinical recommendations, or predict patient outcomes.</p>
                
                <h3>5.2 What Ask rbGyanX CANNOT Do</h3>
                <ul>
                    <li><strong>Prescribe Treatment:</strong> Cannot recommend treatment plans or doses</li>
                    <li><strong>Predict Patient Outcome:</strong> Cannot predict outcomes for specific patients</li>
                    <li><strong>Override Clinician Judgment:</strong> Cannot make autonomous clinical decisions</li>
                    <li><strong>Access Raw Patient Data:</strong> Cannot read DVH files, clinical Excel files, or patient identifiers</li>
                    <li><strong>Make Autonomous Decisions:</strong> Cannot replace human judgment in clinical settings</li>
                </ul>
                
                <h3>5.3 Knowledge Domains</h3>
                <p>Ask rbGyanX covers the following educational topics:</p>
                
                <h4>Radiobiology</h4>
                <ul>
                    <li>TCP/NTCP theory and models</li>
                    <li>LQ model (limitations, extensions)</li>
                    <li>EUD/gEUD (conceptual)</li>
                    <li>BED/EQD2 (conceptual)</li>
                    <li>Hypofractionation principles</li>
                    <li>Re-irradiation concepts</li>
                    <li>Dose-response modeling</li>
                    <li>Therapeutic window concept</li>
                    <li>UTCP concept</li>
                    <li>Normal tissue tolerance (QUANTEC-style)</li>
                </ul>
                
                <h4>Machine Learning (Educational)</h4>
                <ul>
                    <li>ANN, XGBoost, Random Forest, Logistic Regression</li>
                    <li>Bias-variance tradeoff</li>
                    <li>Overfitting & data leakage</li>
                    <li>Cross-validation strategies</li>
                    <li>Internal vs external validation</li>
                    <li>ROC, AUC, calibration curves</li>
                    <li>Feature importance vs causality</li>
                </ul>
                
                <h4>Deep Learning (Conceptual, Future-Ready)</h4>
                <ul>
                    <li>CNNs for DVH anomaly detection</li>
                    <li>Autoencoders for QA</li>
                    <li>Limitations of DL in clinical radiotherapy</li>
                    <li>Why DL ≠ clinical truth</li>
                </ul>
                
                <h4>Statistics & Mathematics</h4>
                <ul>
                    <li>Probability theory (basic)</li>
                    <li>Logistic functions</li>
                    <li>Likelihood</li>
                    <li>Confidence intervals</li>
                    <li>Hypothesis testing</li>
                    <li>Correlation vs causation</li>
                </ul>
                
                <h3>5.4 Built-in Tools</h3>
                
                <h4>Scientific Calculator</h4>
                <p>Ask rbGyanX includes a scientific calculator that works on user-provided numbers only:</p>
                <ul>
                    <li>Arithmetic operations (add, subtract, multiply, divide)</li>
                    <li>Log, exp, power, roots</li>
                    <li>Sigmoid functions</li>
                    <li>Percentages</li>
                </ul>
                <div class="info-box">
                    <strong>Note:</strong> Calculator works on user-provided numbers only. It does NOT read patient files or access data.
                </div>
                
                <h4>Math / Equation Helper</h4>
                <p>Helps with equation rendering and drafting:</p>
                <ul>
                    <li>LaTeX-style equation rendering</li>
                    <li>Symbolic expressions</li>
                    <li>Equation drafting for papers</li>
                </ul>
                <p><strong>Example allowed:</strong> "Write logistic TCP equation"</p>
                <p><strong>Example forbidden:</strong> "Calculate TCP for patient X"</p>
                
                <h3>5.5 Safety & Ethics</h3>
                <div class="warning-box" style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 1rem; margin: 1rem 0;">
                    <strong>Hard Guards:</strong>
                    <ul style="margin-top: 0.5rem;">
                        <li>Ask rbGyanX cannot access DVH files, clinical Excel files, or patient identifiers</li>
                        <li>All AI responses include: "This is educational support, not clinical decision making."</li>
                        <li>External LLM APIs: Disabled by default, user-opt-in only, read-only, no data upload</li>
                    </ul>
                </div>
                
                <h3>5.6 Usage</h3>
                <p>Access Ask rbGyanX from the menu: <strong>Help → Ask rbGyanX</strong></p>
                <p>If you ask out-of-scope questions, Ask rbGyanX will respond with educational guidance and suggest external study sources (textbooks, reviews, PubMed keywords).</p>
            </section>
            
            <section id="radiobiology" class="section">
                <h2>6. Radiobiology & Physics Context</h2>
                
                <h3>5.1 Traditional Radiobiological Models</h3>
                
                <h4>NTCP Models</h4>
                <ul class="model-list">
"""
        
        for model in models.get("ntcp", []):
            html += f"""
                    <li>
                        <strong>{model['name']}:</strong> {model['description']}
                        <br><em>Reference: {model['reference']}</em>
                    </li>
"""
        
        html += """
                </ul>
                
                <h4>TCP Models</h4>
                <ul class="model-list">
"""
        
        for model in models.get("tcp", []):
            html += f"""
                    <li>
                        <strong>{model['name']}:</strong> {model['description']}
                        <br><em>Reference: {model['reference']}</em>
                    </li>
"""
        
        html += f"""
                </ul>
                
                <h3>5.2 Machine Learning Models</h3>
"""
        
        # OBJECTIVE C: Add novel features section
        html += """
                
                <h3>5.3 Novel Features (rbGyanX CDSS Framework)</h3>
                
                <p>rbGyanX includes advanced radiobiological features that extend beyond standard TCP/NTCP calculators:</p>
                
                <h4>FDVH (Fractionation-Aware DVH)</h4>
                <div class="info-box">
                    <strong>What it does:</strong> Converts physical DVH to biologically effective dose (BED)-normalized DVH<br>
                    <strong>Why use it:</strong> Enables hypofractionation modeling (SBRT/SRS), cross-fractionation scheme comparison, and re-irradiation assessment<br>
                    <strong>When to use:</strong> When analyzing non-standard fractionation schemes or comparing different fractionation protocols<br>
                    <strong>Mathematical basis:</strong> BED = n · d · (1 + d/(α/β)) where n = fractions, d = dose per fraction, α/β = tissue parameter<br>
                    <strong>Output:</strong> BED-normalized DVH with columns labeled "BED-DVH" and "DVH_Type = FDVH"
                </div>
                
                <h4>uTCP (Uncertainty-Aware TCP)</h4>
                <div class="info-box">
                    <strong>What it does:</strong> Propagates parameter uncertainty through TCP models to provide confidence bounds<br>
                    <strong>Why use it:</strong> Reports TCP = 0.78 ± 0.11 instead of false precision, enabling honest uncertainty quantification<br>
                    <strong>When to use:</strong> When you need to understand prediction reliability and parameter sensitivity<br>
                    <strong>Mathematical basis:</strong> Monte Carlo sampling of parameter distributions to estimate prediction variance<br>
                    <strong>Output:</strong> Additional columns: TCP_mean, TCP_std, TCP_95CI_low, TCP_95CI_high<br>
                    <strong>Note:</strong> uTCP reflects parameter uncertainty, not clinical outcome variance
                </div>
                
                <h4>TWI (Therapeutic Window Index)</h4>
                <div class="info-box">
                    <strong>What it does:</strong> Intelligent plan comparison with organ-specific risk weighting<br>
                    <strong>Why use it:</strong> Provides a single metric that balances tumor control (TCP) against weighted normal tissue risk (NTCP)<br>
                    <strong>When to use:</strong> When comparing multiple treatment plans or evaluating plan quality<br>
                    <strong>Mathematical basis:</strong> TWI = TCP - Σ(λ_k · NTCP_k) where λ_k = organ-specific risk weight<br>
                    <strong>Risk weights:</strong> Spinal Cord (1.0), Brainstem (1.0), Lung (0.8), Heart (0.9), Pharynx (0.5), Parotid (0.3)<br>
                    <strong>Output:</strong> therapeutic_ratios.xlsx with TWI column and TWI_Interpretation (Favorable/Moderate/Unfavorable)<br>
                    <strong>Limitation:</strong> Decision support only – no automated clinical decisions
                </div>
                
                <h4>CCS (Cohort Consistency Score - ML Safety Gate)</h4>
                <div class="warning-box" style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin: 1rem 0;">
                    <strong>What it does:</strong> Prevents unsafe ML extrapolation by detecting out-of-distribution (OOD) patients<br>
                    <strong>Why use it:</strong> ML models can be overconfident on patients who differ from training data. CCS prevents this.<br>
                    <strong>When to use:</strong> When using ML models, especially with institutional or external training data<br>
                    <strong>Mathematical basis:</strong> CCS = exp(-0.5 · Mahalanobis²) where Mahalanobis distance measures deviation from training cohort<br>
                    <strong>Safety gate:</strong> If CCS < threshold (default 0.1), ML predictions are disabled and traditional models are used<br>
                    <strong>Output:</strong> CCS value in ML output table, warnings when patients are OOD<br>
                    <strong>Action:</strong> ML prediction suppressed due to cohort mismatch → use traditional models only
                </div>
                
                <div class="disclaimer-box" style="margin-top: 1.5rem;">
                    <strong>⚠️ What rbGyanX DOES NOT do:</strong>
                    <ul style="margin-top: 0.5rem;">
                        <li>No treatment optimization</li>
                        <li>No autonomous decisions</li>
                        <li>No outcome prediction guarantee</li>
                        <li>No real-time clinical decision support</li>
                    </ul>
                </div>
"""
        
        if ml_info["enabled"]:
            html += f"""
                <div class="info-box">
                    <strong>ML Models Enabled:</strong> {', '.join(ml_info['models'])}<br>
                    <strong>Description:</strong> {ml_info['description']}
"""
            if ml_info["shap_enabled"]:
                html += "<br><strong>SHAP Explainability:</strong> Enabled for model interpretability"
            html += """
                </div>
"""
        else:
            html += """
                <div class="info-box">
                    <strong>ML Models:</strong> Available but not enabled by default. Enable in Step 3 configuration.
                </div>
"""
        
        html += """
                <h3>5.3 Physical Dose Metrics</h3>
                
                <h4>Target Structure Metrics (PTV/GTV/CTV)</h4>
                <ul>
                    <li><strong>Dmax:</strong> Maximum dose to target</li>
                    <li><strong>D0.03cc, D1cc:</strong> Hotspot metrics</li>
                    <li><strong>D95, D98:</strong> Dose covering 95% and 98% of target volume</li>
                    <li><strong>V95, V100, V107:</strong> Volume receiving ≥95%, ≥100%, ≥107% of prescription dose</li>
                    <li><strong>HI1, HI2:</strong> Homogeneity Indices</li>
                    <li><strong>CI_RTOG:</strong> RTOG Conformity Index</li>
                    <li><strong>GI:</strong> Gradient Index</li>
                </ul>
                
                <h4>OAR Metrics</h4>
                <ul>
                    <li><strong>Dmax:</strong> Maximum dose to organ</li>
                    <li><strong>V5-V50:</strong> Volume receiving ≥5Gy to ≥50Gy (in 5Gy increments)</li>
                    <li><strong>Mean Dose:</strong> Average dose to organ</li>
                </ul>
            </section>
            
            <section id="inputs" class="section">
                <h2>7. Input Requirements</h2>
                
                <h3>6.1 DVH Files</h3>
                <p>rbGyanX accepts DVH files in multiple formats:</p>
                <ul>
                    <li><strong>Format:</strong> CSV, TXT, or directory containing multiple DVH files</li>
                    <li><strong>DVH Type:</strong> Cumulative or differential (auto-detected)</li>
                    <li><strong>Required Columns:</strong> Dose[Gy] and Volume[cm³] or Volume[%]</li>
                    <li><strong>Structure Names:</strong> Automatically detected (PTV/GTV/CTV = TARGET; others = OAR)</li>
                </ul>
                
                <div class="info-box">
                    <strong>File Naming Convention:</strong> Files should be named with patient ID and structure name, 
                    e.g., <code>Patient_001_PTV.csv</code> or <code>Patient_001_Parotid.csv</code>
                </div>
"""
        
        if templates:
            html += """
                <h3>6.2 Input Templates</h3>
                <p>The following templates are available in <code>clinical/templates/</code>:</p>
                <ul>
"""
            for template in templates:
                html += f'                    <li><code>{template}</code></li>\n'
            html += """
                </ul>
"""
        
        if schema:
            html += """
                <h3>6.3 Clinical Data Schema</h3>
                <p>Clinical data should follow the schema defined in <code>clinical/clinical_schema.json</code>.</p>
                <div class="info-box">
                    <strong>Note:</strong> The schema defines required and optional fields for clinical data files.
                </div>
"""
        
        html += """
                <h3>6.4 Clinical Data (Optional but Recommended)</h3>
                <p>Required for ML models and clinical factors analysis:</p>
                <ul>
                    <li><strong>Format:</strong> Excel (.xlsx) or CSV (.csv)</li>
                    <li><strong>Required Column:</strong> PatientID (must match DVH file naming)</li>
                    <li><strong>Optional Columns:</strong> Age, Gender, TumorStage, Treatment, Outcome, etc.</li>
                    <li><strong>Outcome Column:</strong> For supervised ML, include binary outcome (0/1 or No/Yes)</li>
                </ul>
            </section>
            
            <section id="outputs" class="section">
                <h2>7. Output Folder Structure</h2>
                
                <p>All outputs follow a uniform directory structure. The exact folders created depend on the 
                selected analysis mode.</p>
                
                <h3>7.1 Common Structure (All Modes)</h3>
                <pre><code>output_root/
"""
        
        for item in output_structure["common"]:
            html += f"{item}\n"
        
        html += """</code></pre>
"""
        
        html += """
                <h3>7.2 TCP-Only Mode</h3>
                <pre><code>output_root/
"""
        for item in output_structure["common"]:
            html += f"{item}\n"
        for item in output_structure["tcp_only"]:
            html += f"{item}\n"
        html += """</code></pre>
"""
        
        html += """
                <h3>7.3 NTCP-Only Mode</h3>
                <pre><code>output_root/
"""
        for item in output_structure["common"]:
            html += f"{item}\n"
        for item in output_structure["ntcp_only"]:
            html += f"{item}\n"
        html += """</code></pre>
"""
        
        html += """
                <h3>7.4 TCP + NTCP Mode</h3>
                <pre><code>output_root/
"""
        for item in output_structure["common"]:
            html += f"{item}\n"
        for item in output_structure["tcp_ntcp"]:
            html += f"{item}\n"
        html += """</code></pre>
"""
        
        html += """
            </section>
            
            <section id="limitations" class="section">
                <h2>8. Limitations & Cautions</h2>
                
                <div class="disclaimer-box">
                    <h3>⚠️ CRITICAL DISCLAIMERS</h3>
                    <p><strong>rbGyanX_basic is NOT a clinical decision support system (CDSS) for direct patient care.</strong></p>
                    <ul>
                        <li><strong>Research Use Only:</strong> All results are for research and educational purposes only. This tool is not intended for clinical decision-making.</li>
                        <li><strong>No Autonomous Decisions:</strong> rbGyanX_basic does NOT make autonomous clinical decisions. All treatment decisions must be made by qualified healthcare professionals.</li>
                        <li><strong>User Responsibility:</strong> Users are solely responsible for interpretation of results and any clinical decisions made based on this tool.</li>
                        <li><strong>Population-Based Estimates:</strong> Model predictions are estimates based on population data and may not apply to individual patients.</li>
                        <li><strong>No Warranty:</strong> No warranty or guarantee of accuracy is provided. Use at your own risk.</li>
                        <li><strong>Not FDA Approved:</strong> This software is not FDA-approved for clinical use.</li>
                        <li><strong>Validation Required:</strong> All model predictions should be validated against clinical outcomes before use.</li>
                    </ul>
                </div>
                
                <div class="warning-box">
                    <h3>⚠️ Important Limitations</h3>
                    <p><strong>rbGyanX_basic has the following limitations:</strong></p>
                    <ul>
                        <li><strong>Sample Size:</strong> ML models require adequate sample sizes. Small datasets may lead to overfitting.</li>
                        <li><strong>Model Generalization:</strong> Models trained on one population may not generalize to others.</li>
                        <li><strong>DICOM RT:</strong> Primary clinic path — folder with RTPLAN, RTDOSE, and RTSTRUCT. Step 3 (TCP+NTCP) runs rbgyanx-engine on DICOM.</li>
                        <li><strong>TPS text DVH:</strong> Optional legacy path (Steps 1–2 + subprocess scripts); use ADVANCED when ML/SHAP/FDVH are needed.</li>
                        <li><strong>Validation:</strong> Users should validate model predictions against clinical outcomes.</li>
                        <li><strong>Clinical Factors:</strong> Not all clinical factors may be captured in the analysis.</li>
                        <li><strong>Missing Data:</strong> Missing clinical factors are logged but analysis proceeds with available data.</li>
                    </ul>
                </div>
                
                <h3>8.1 Known Limitations</h3>
                <ul>
                    <li><strong>Sample Size:</strong> ML models require adequate sample sizes (minimum 20 samples, 5 events). Small datasets may lead to overfitting.</li>
                    <li><strong>Model Generalization:</strong> Models trained on one population may not generalize to others.</li>
                    <li><strong>DICOM Support:</strong> DICOM RT file support is planned for future versions.</li>
                    <li><strong>Real-time Integration:</strong> No integration with treatment planning systems in this version.</li>
                    <li><strong>Validation:</strong> Users should validate model predictions against clinical outcomes.</li>
                    <li><strong>Clinical Factors:</strong> Missing clinical factors are logged but do not block analysis.</li>
                    <li><strong>Structure Role Detection:</strong> Automatic detection of TARGET vs OAR based on structure names (PTV/GTV/CTV = TARGET).</li>
                </ul>
                
                <h3>8.2 Best Practices</h3>
                <ul>
                    <li><strong>Always review QA reports</strong> before using results</li>
                    <li><strong>Validate model predictions</strong> against known outcomes when possible</li>
                    <li><strong>Use appropriate sample sizes</strong> for ML model training (≥20 samples, ≥5 events)</li>
                    <li><strong>Document all analysis parameters</strong> and assumptions</li>
                    <li><strong>Consult with medical physicists and radiation oncologists</strong> for interpretation</li>
                    <li><strong>Check structure role mapping</strong> to ensure TARGET structures are correctly identified</li>
                    <li><strong>Review clinical factors availability</strong> before running factor analysis</li>
                    <li><strong>Verify output file locations</strong> match expected directory structure</li>
                </ul>
                
                <h3>8.3 Output Interpretation Guidelines</h3>
                <ul>
                    <li><strong>TCP Predictions:</strong> Range from 0 to 1. Higher values indicate higher probability of tumor control.</li>
                    <li><strong>NTCP Predictions:</strong> Range from 0 to 1. Higher values indicate higher probability of normal tissue complications.</li>
                    <li><strong>Therapeutic Metrics:</strong> UTCP, P+, CFTC provide integrated measures balancing tumor control and toxicity.</li>
                    <li><strong>ML Performance:</strong> AUC, Brier score, calibration plots indicate model reliability. Review QA reports for overfitting warnings.</li>
                    <li><strong>Clinical Factors:</strong> Correlation coefficients and p-values indicate factor significance. Missing factors are logged but do not block analysis.</li>
                </ul>
            </section>
        </div>
        
        <footer>
            <p><strong>{app_name} v{app_version}</strong></p>
            <p>Radiobiology-guided Clinical Decision Support Framework</p>
            <p style="font-size: 0.9em; margin-top: 1rem;">
                This manual is auto-generated from the codebase. 
                Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
        </footer>
    </div>
</body>
</html>
"""
        
        return html
    
    def generate(self) -> Tuple[bool, str]:
        """
        Generate the user manual HTML file.
        
        Returns
        -------
        Tuple[bool, str]
            (success, message) - success status and message
        """
        try:
            html_content = self.generate_html()
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return True, f"User manual generated successfully at: {self.output_file}"
        except Exception as e:
            return False, f"Error generating user manual: {str(e)}"


def generate_user_manual(repo_root: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Convenience function to generate user manual.
    
    Parameters
    ----------
    repo_root : Path, optional
        Root directory of rbGyanX repository. If None, uses current working directory.
    
    Returns
    -------
    Tuple[bool, str]
        (success, message) - success status and message
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent
    
    generator = UserManualGenerator(repo_root)
    return generator.generate()


if __name__ == "__main__":
    # Allow running as standalone script
    success, message = generate_user_manual()
    print(message)
    if not success:
        exit(1)

