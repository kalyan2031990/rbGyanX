"""
LLM-Powered QA and Error Correction Engine for rbGyanX
"""
import json
import pandas as pd
import numpy as np
from pathlib import Path
import re
from typing import Dict, List, Tuple, Optional
import warnings


class RadiobiologyLLMQA:
    """Intelligent QA system with pattern-based error detection"""
    
    def __init__(self, config_path: str = "config/qa_config.json"):
        self.config = self._load_config(config_path)
        self.error_patterns = self._load_error_patterns()
        self.fix_templates = self._load_fix_templates()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load QA configuration"""
        default_config = {
            "validation_checks": {
                "sample_consistency": True,
                "dose_calculation": True,
                "structure_naming": True,
                "biological_dose": True,
                "ml_validation": True
            },
            "thresholds": {
                "min_samples_per_organ": 5,
                "max_eqd2_physical_diff": 0.1,
                "min_ml_auc": 0.6,
                "max_missing_data": 0.2
            },
            "llm_settings": {
                "use_local_llm": False,
                "llm_model": "llama2",
                "confidence_threshold": 0.7
            }
        }
        
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    default_config.update(user_config)
        except Exception as e:
            print(f"⚠️  Using default QA config: {e}")
        
        return default_config
    
    def _load_error_patterns(self) -> List[Dict]:
        """Patterns for common radiobiology pipeline errors"""
        return [
            {
                "pattern": r'Sample size mismatch.*(\d+).*(\d+)',
                "type": "sample_inconsistency",
                "severity": "high",
                "fix": "check_patient_organ_mapping"
            },
            {
                "pattern": r'EQD2.*equal.*physical',
                "type": "biological_dose_missing",
                "severity": "critical",
                "fix": "enable_bed_conversion"
            },
            {
                "pattern": r'combo.*organ',
                "type": "structure_naming_error",
                "severity": "medium",
                "fix": "normalize_organ_names"
            },
            {
                "pattern": r'Warning:.*insufficient.*samples',
                "type": "sample_size_warning",
                "severity": "medium",
                "fix": "adjust_sample_filter"
            },
            {
                "pattern": r'AUC.*[\d\.]+.*need.*[\d\.]+',
                "type": "ml_performance_issue",
                "severity": "high",
                "fix": "check_feature_engineering"
            }
        ]
    
    def _load_fix_templates(self) -> Dict:
        """Templates for automated fixes"""
        return {
            "enable_bed_conversion": {
                "description": "Enable BED/EQD2 conversion",
                "code_change": {
                    "file": "code3_ntcp_analysis_ml.py",
                    "search": "eqd2_mean = mean_dose",
                    "replace": "bio_dose = self._calculate_biological_dose(mean_dose, patient_id, organ)\neqd2_mean = bio_dose['eqd2']"
                }
            },
            "normalize_organ_names": {
                "description": "Fix organ naming inconsistencies",
                "code_change": {
                    "file": "code1_universal_dvh_parser.py",
                    "search": "def _categorize_structure",
                    "insert_after": True,
                    "code": """    # Enhanced normalization
    name_lower = name.lower().strip()
    if 'parotid' in name_lower:
        return 'OAR', 'Parotid'
    elif 'spinal' in name_lower or 'cord' in name_lower:
        return 'OAR', 'SpinalCord'
    elif 'larynx' in name_lower:
        return 'OAR', 'Larynx'"""
                }
            }
        }
    
    def analyze_pipeline_log(self, log_file: str) -> Dict:
        """Analyze pipeline log and suggest fixes"""
        print(f"\n{'='*60}")
        print("🤖 LLM QA ENGINE: Pipeline Analysis")
        print(f"{'='*60}")
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
        except Exception as e:
            print(f"Error reading log file: {e}")
            return {"error": str(e)}
        
        findings = {
            "errors": [],
            "warnings": [],
            "suggestions": [],
            "autofix_available": []
        }
        
        # Pattern-based error detection
        for pattern in self.error_patterns:
            matches = re.findall(pattern["pattern"], log_content, re.IGNORECASE)
            if matches:
                finding = {
                    "type": pattern["type"],
                    "severity": pattern["severity"],
                    "message": f"Found {pattern['type']}: {matches[0] if matches else 'Pattern matched'}",
                    "fix": pattern["fix"],
                    "autofix": pattern["fix"] in self.fix_templates
                }
                
                if pattern["severity"] == "critical":
                    findings["errors"].append(finding)
                elif pattern["severity"] == "high":
                    findings["warnings"].append(finding)
                else:
                    findings["suggestions"].append(finding)
                
                if finding["autofix"]:
                    findings["autofix_available"].append(finding)
        
        return findings
    
    def validate_step_consistency(self, step1_path: str, step2_path: str, step3_path: str) -> Dict:
        """Validate data consistency between pipeline steps"""
        validation_results = {
            "step1": {"count": 0, "patients": 0, "organs": []},
            "step2": {"count": 0, "patients": 0, "organs": []},
            "step3": {"count": 0, "patients": 0, "organs": []},
            "consistency_issues": []
        }
        
        try:
            # Read outputs
            if Path(step1_path).exists():
                df1 = pd.read_excel(step1_path) if step1_path.endswith('.xlsx') else pd.read_csv(step1_path)
                validation_results['step1']['count'] = len(df1)
                validation_results['step1']['patients'] = df1['PatientID'].nunique() if 'PatientID' in df1.columns else 0
                validation_results['step1']['organs'] = df1['Organ'].unique().tolist() if 'Organ' in df1.columns else []
            
            if Path(step2_path).exists():
                df2 = pd.read_excel(step2_path) if step2_path.endswith('.xlsx') else pd.read_csv(step2_path)
                validation_results['step2']['count'] = len(df2)
                validation_results['step2']['patients'] = df2['PatientID'].nunique() if 'PatientID' in df2.columns else 0
                validation_results['step2']['organs'] = df2['Organ'].unique().tolist() if 'Organ' in df2.columns else []
            
            if Path(step3_path).exists():
                df3 = pd.read_excel(step3_path) if step3_path.endswith('.xlsx') else pd.read_csv(step3_path)
                validation_results['step3']['count'] = len(df3)
                validation_results['step3']['patients'] = df3['PatientID'].nunique() if 'PatientID' in df3.columns else 0
                validation_results['step3']['organs'] = df3['Organ'].unique().tolist() if 'Organ' in df3.columns else []
            
            # Check consistency
            if validation_results['step1']['count'] > 0 and validation_results['step2']['count'] > 0:
                if validation_results['step1']['count'] != validation_results['step2']['count']:
                    validation_results['consistency_issues'].append(
                        f"Sample count mismatch: Step1={validation_results['step1']['count']}, Step2={validation_results['step2']['count']}"
                    )
            
            if validation_results['step2']['count'] > 0 and validation_results['step3']['count'] > 0:
                if validation_results['step2']['count'] != validation_results['step3']['count']:
                    validation_results['consistency_issues'].append(
                        f"Sample count mismatch: Step2={validation_results['step2']['count']}, Step3={validation_results['step3']['count']}"
                    )
            
            # Check for "combo" organs
            for step in ['step1', 'step2', 'step3']:
                organs = validation_results[step]['organs']
                combo_organs = [o for o in organs if 'combo' in str(o).lower()]
                if combo_organs:
                    validation_results['consistency_issues'].append(
                        f"Found 'combo' organs in {step}: {combo_organs}"
                    )
            
            return validation_results
            
        except Exception as e:
            return {"error": f"Validation failed: {str(e)}"}
    
    def generate_fix_report(self, findings: Dict, output_path: str = "qa_fix_report.md"):
        """Generate comprehensive fix report"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("# rbGyanX Pipeline Fix Report\n\n")
                f.write(f"Generated: {pd.Timestamp.now()}\n\n")
                
                if findings.get("errors"):
                    f.write("## ❌ Critical Errors\n")
                    for error in findings["errors"]:
                        f.write(f"### {error['type'].replace('_', ' ').title()}\n")
                        f.write(f"- **Message**: {error['message']}\n")
                        f.write(f"- **Severity**: {error['severity']}\n")
                        f.write(f"- **Suggested Fix**: {error['fix']}\n")
                        if error['autofix']:
                            f.write(f"- **🚀 Auto-fix Available**: Yes\n")
                            fix_template = self.fix_templates[error['fix']]
                            f.write(f"  ```python\n{json.dumps(fix_template, indent=2)}\n  ```\n")
                        f.write("\n")
                
                if findings.get("warnings"):
                    f.write("## ⚠️ Warnings\n")
                    for warning in findings["warnings"]:
                        f.write(f"- **{warning['type'].replace('_', ' ').title()}**: {warning['message']}\n")
                
                if findings.get("suggestions"):
                    f.write("## 💡 Suggestions\n")
                    for suggestion in findings["suggestions"]:
                        f.write(f"- {suggestion['message']}\n")
            
            print(f"✅ Fix report generated: {output_path}")
            return True
        except Exception as e:
            print(f"Error generating report: {e}")
            return False
    
    def auto_apply_fixes(self, findings: Dict, dry_run: bool = True) -> List[str]:
        """Automatically apply available fixes"""
        applied_fixes = []
        
        for finding in findings.get("autofix_available", []):
            fix_name = finding["fix"]
            if fix_name in self.fix_templates:
                fix = self.fix_templates[fix_name]
                
                print(f"\n🔧 Applying fix: {fix['description']}")
                print(f"   File: {fix['code_change']['file']}")
                
                if dry_run:
                    print(f"   [DRY RUN] Would modify: {fix['code_change'].get('search', 'N/A')}")
                else:
                    # Actually apply the fix
                    success = self._apply_code_fix(fix['code_change'])
                    if success:
                        applied_fixes.append(fix_name)
                        print(f"   ✅ Fix applied successfully")
                    else:
                        print(f"   ❌ Failed to apply fix")
        
        return applied_fixes
    
    def _apply_code_fix(self, fix: Dict) -> bool:
        """Apply a code fix to a file"""
        try:
            file_path = fix['file']
            if not Path(file_path).exists():
                print(f"File not found: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if fix.get('insert_after'):
                # Insert code after search pattern
                search = fix['search']
                insert_code = fix['code']
                lines = content.split('\n')
                new_lines = []
                
                for line in lines:
                    new_lines.append(line)
                    if search in line:
                        new_lines.append(insert_code)
                
                new_content = '\n'.join(new_lines)
            else:
                # Replace pattern
                search = fix['search']
                replace = fix['replace']
                new_content = content.replace(search, replace)
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True
        except Exception as e:
            print(f"Error applying fix: {e}")
            return False


# Example usage
if __name__ == "__main__":
    qa_engine = RadiobiologyLLMQA()
    
    # Analyze pipeline log
    if Path("pipeline.log").exists():
        findings = qa_engine.analyze_pipeline_log("pipeline.log")
    else:
        print("No pipeline.log found, skipping log analysis")
        findings = {"errors": [], "warnings": [], "suggestions": [], "autofix_available": []}
    
    # Validate consistency
    validation = qa_engine.validate_step_consistency(
        "processed_DVH/processed_dvh.xlsx",
        "dose_metrics/tables/dose_metrics_cohort.xlsx",
        "ntcp_analysis/enhanced_ntcp_calculations.csv"
    )
    
    # Generate report
    qa_engine.generate_fix_report(findings)
    
    # Show summary
    print(f"\n📊 QA Summary:")
    print(f"  Errors: {len(findings.get('errors', []))}")
    print(f"  Warnings: {len(findings.get('warnings', []))}")
    print(f"  Auto-fixes available: {len(findings.get('autofix_available', []))}")

