"""
Synthetic Clinical Data Generator for rbGyanX Testing
======================================================
Generates realistic synthetic data matching real clinical dataset structure

Based on typical head-neck cancer radiotherapy data:
- DVH files (differential dose-volume histograms)
- Clinical data (patient demographics, outcomes, toxicities)
- Multi-organ structures (parotids, submandibular glands, oral cavity, etc.)

Author: rbGyanX Team
Version: 1.0.0
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class SyntheticClinicalDataGenerator:
    """
    Generate synthetic clinical data for rbGyanX testing
    
    Mimics real clinical data structure from head-neck cancer patients
    """
    
    def __init__(self, n_patients=50, random_seed=42):
        """
        Initialize synthetic data generator
        
        Parameters
        ----------
        n_patients : int
            Number of patients to generate
        random_seed : int
            Random seed for reproducibility
        """
        self.n_patients = n_patients
        np.random.seed(random_seed)
        
        # Organ structures commonly in head-neck DVH data
        self.organs = {
            'parotid': ['Parotid_L', 'Parotid_R'],
            'submandibular': ['Submandibular_L', 'Submandibular_R'],
            'oral_cavity': ['Oral_Cavity'],
            'pharynx': ['Pharynx_Constrictor_S', 'Pharynx_Constrictor_M', 'Pharynx_Constrictor_I'],
            'larynx': ['Larynx', 'Glottic_Area'],
            'spinal_cord': ['SpinalCord'],
            'brainstem': ['Brainstem'],
            'tumor': ['GTV', 'CTV', 'PTV']
        }
    
    def generate_complete_dataset(self, output_dir):
        """
        Generate complete synthetic dataset
        
        Creates:
        - DVH CSV files for each patient-organ combination
        - Clinical data Excel file with outcomes
        - Metadata file
        
        Parameters
        ----------
        output_dir : Path or str
            Output directory for synthetic data
        
        Returns
        -------
        dict
            Paths to generated files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Generating synthetic dataset for {self.n_patients} patients...")
        
        # Create subdirectories
        dvh_dir = output_dir / "DVH_files"
        dvh_dir.mkdir(exist_ok=True)
        
        tumor_dvh_dir = output_dir / "tumor_DVH"
        tumor_dvh_dir.mkdir(exist_ok=True)
        
        # Generate patient metadata
        patient_metadata = self._generate_patient_metadata()
        
        # Generate DVH files
        print("Generating DVH files...")
        dvh_files = self._generate_dvh_files(dvh_dir, tumor_dvh_dir, patient_metadata)
        
        # Generate clinical data
        print("Generating clinical data...")
        clinical_file = self._generate_clinical_data(output_dir, patient_metadata)
        
        # Generate metadata file
        print("Generating metadata...")
        metadata_file = self._generate_metadata_file(output_dir, patient_metadata)
        
        print(f"\n[OK] Synthetic dataset created in: {output_dir}")
        print(f"     - {len(dvh_files)} DVH files")
        print(f"     - Clinical data: {clinical_file.name}")
        print(f"     - Metadata: {metadata_file.name}")
        
        return {
            'dvh_dir': dvh_dir,
            'tumor_dvh_dir': tumor_dvh_dir,
            'clinical_file': clinical_file,
            'metadata_file': metadata_file,
            'patient_metadata': patient_metadata
        }
    
    def _generate_patient_metadata(self):
        """Generate patient demographics and clinical characteristics"""
        patients = []
        
        for i in range(self.n_patients):
            patient_id = f"Patient_{i+1:03d}"
            
            # Demographics
            age = int(np.random.normal(62, 12))
            age = np.clip(age, 30, 85)
            
            gender = np.random.choice(['M', 'F'], p=[0.70, 0.30])
            
            # Tumor characteristics
            tumor_sites = ['Oropharynx', 'Larynx', 'Hypopharynx', 'Nasopharynx', 'Oral_Cavity']
            tumor_site = np.random.choice(tumor_sites, p=[0.40, 0.25, 0.15, 0.10, 0.10])
            
            stage = np.random.choice(['I', 'II', 'III', 'IVA', 'IVB'], 
                                    p=[0.05, 0.10, 0.25, 0.40, 0.20])
            
            # HPV status (mainly for oropharynx)
            if tumor_site == 'Oropharynx':
                hpv_status = np.random.choice(['Positive', 'Negative', 'Unknown'], 
                                             p=[0.65, 0.25, 0.10])
            else:
                hpv_status = np.random.choice(['Negative', 'Unknown'], p=[0.85, 0.15])
            
            # Tumor volume (log-normal distribution)
            tumor_volume = np.random.lognormal(3.7, 0.8)
            tumor_volume = np.clip(tumor_volume, 5, 300)
            
            # Treatment parameters
            total_dose = np.random.choice([66, 70, 72], p=[0.15, 0.70, 0.15])
            fractions = total_dose // 2  # 2 Gy per fraction
            
            technique = np.random.choice(['IMRT', 'VMAT', 'Tomotherapy'], 
                                        p=[0.35, 0.55, 0.10])
            
            # Chemotherapy (more common in advanced stages)
            if stage in ['III', 'IVA', 'IVB']:
                chemo_used = np.random.binomial(1, 0.75)
            else:
                chemo_used = np.random.binomial(1, 0.30)
            
            # Smoking
            smoking_py = 0
            if np.random.random() < 0.65:  # 65% smokers
                smoking_py = np.random.gamma(3, 10)
            
            smoking_status = 'Never' if smoking_py == 0 else \
                           ('Current' if np.random.random() < 0.40 else 'Former')
            
            # ECOG performance status
            ecog = np.random.choice([0, 1, 2], p=[0.50, 0.40, 0.10])
            
            # Outcomes - TCP (tumor control probability)
            # Better outcomes for: HPV+, early stage, younger age
            tcp_base_prob = 0.70
            
            if hpv_status == 'Positive':
                tcp_base_prob += 0.15
            if stage in ['I', 'II']:
                tcp_base_prob += 0.10
            if stage in ['IVB']:
                tcp_base_prob -= 0.15
            if age > 70:
                tcp_base_prob -= 0.05
            if smoking_status == 'Current':
                tcp_base_prob -= 0.08
            
            tcp_base_prob = np.clip(tcp_base_prob, 0.30, 0.95)
            tumor_control = np.random.binomial(1, tcp_base_prob)
            
            # Time to failure (if control = 0)
            if tumor_control == 0:
                failure_time = int(np.random.gamma(2, 6))
                failure_time = np.clip(failure_time, 3, 36)
            else:
                failure_time = np.nan
            
            # Follow-up time
            followup = int(np.random.gamma(4, 6))
            followup = np.clip(followup, 6, 60)
            
            patients.append({
                'PatientID': patient_id,
                'Age': age,
                'Gender': gender,
                'TumorSite': tumor_site,
                'Stage': stage,
                'HPV_Status': hpv_status,
                'TumorVolume_cc': round(tumor_volume, 1),
                'TotalDose_Gy': total_dose,
                'Fractions': fractions,
                'Technique': technique,
                'ChemotherapyUsed': chemo_used,
                'Smoking_PackYears': round(smoking_py, 1),
                'Smoking_Status': smoking_status,
                'ECOG_Performance': ecog,
                'TumorControl': tumor_control,
                'LocalFailure_Time_Months': failure_time,
                'FollowUp_Months': followup
            })
        
        return pd.DataFrame(patients)
    
    def _generate_dvh_files(self, dvh_dir, tumor_dvh_dir, patient_metadata):
        """Generate DVH CSV files for each patient-organ combination"""
        dvh_files = []
        
        for idx, patient in patient_metadata.iterrows():
            patient_id = patient['PatientID']
            total_dose = patient['TotalDose_Gy']
            
            # Generate OAR DVHs
            for organ_type, organ_list in self.organs.items():
                if organ_type == 'tumor':
                    continue  # Handle tumor separately
                
                for organ in organ_list:
                    dvh_file = dvh_dir / f"{patient_id}_{organ}.csv"
                    dvh_data = self._generate_single_dvh(organ, total_dose, is_tumor=False)
                    dvh_data.to_csv(dvh_file, index=False)
                    dvh_files.append(dvh_file)
            
            # Generate tumor DVHs
            for tumor_vol in self.organs['tumor']:
                tumor_file = tumor_dvh_dir / f"{patient_id}_{tumor_vol}.csv"
                tumor_dvh = self._generate_single_dvh(tumor_vol, total_dose, is_tumor=True)
                tumor_dvh.to_csv(tumor_file, index=False)
                dvh_files.append(tumor_file)
        
        return dvh_files
    
    def _generate_single_dvh(self, organ, prescription_dose, is_tumor=False):
        """
        Generate differential DVH for single organ
        
        DVH format:
        Dose (Gy) | Relative Volume (%)
        """
        # Dose bins (0 to 110% of prescription)
        max_dose = prescription_dose * 1.10
        dose_bins = np.linspace(0, max_dose, 200)
        
        if is_tumor:
            # Tumor DVH - should receive prescription dose
            # Peak around prescription dose with some heterogeneity
            mean_dose = prescription_dose * 0.98
            std_dose = prescription_dose * 0.05
            
            # Create DVH distribution
            dvh_volumes = np.zeros_like(dose_bins)
            
            for i, dose in enumerate(dose_bins):
                if dose < prescription_dose * 0.85:
                    # Most of tumor gets high dose
                    dvh_volumes[i] = 0
                elif dose < prescription_dose * 0.95:
                    dvh_volumes[i] = np.random.uniform(0, 5)
                elif dose < prescription_dose * 1.03:
                    # Peak at prescription dose
                    dvh_volumes[i] = np.random.uniform(80, 100)
                else:
                    # Small hot spots
                    dvh_volumes[i] = np.random.uniform(0, 10)
        
        else:
            # OAR DVH - should be spared
            # Exponentially decreasing with dose
            
            if 'Parotid' in organ:
                # Parotid: mean dose ~25-35 Gy
                mean_dose = np.random.uniform(20, 35)
                std_dose = 8
            elif 'Submandibular' in organ:
                mean_dose = np.random.uniform(30, 45)
                std_dose = 10
            elif 'Oral_Cavity' in organ:
                mean_dose = np.random.uniform(25, 40)
                std_dose = 12
            elif 'Pharynx' in organ:
                mean_dose = np.random.uniform(40, 55)
                std_dose = 8
            elif 'SpinalCord' in organ:
                mean_dose = np.random.uniform(15, 35)
                std_dose = 5
            elif 'Brainstem' in organ:
                mean_dose = np.random.uniform(10, 30)
                std_dose = 5
            else:
                mean_dose = np.random.uniform(20, 40)
                std_dose = 10
            
            # Create dose distribution (exponential decay)
            dvh_volumes = np.zeros_like(dose_bins)
            
            for i, dose in enumerate(dose_bins):
                # Volume receiving >= dose
                if dose < 5:
                    dvh_volumes[i] = 100
                else:
                    # Exponential decay
                    dvh_volumes[i] = 100 * np.exp(-(dose - 5) / mean_dose)
                    # Add noise
                    dvh_volumes[i] += np.random.normal(0, 2)
                    dvh_volumes[i] = np.clip(dvh_volumes[i], 0, 100)
        
        # Convert to differential DVH (dV/dD)
        cumulative_volumes = dvh_volumes.copy()
        differential_volumes = -np.diff(cumulative_volumes, prepend=100)
        
        # Normalize
        differential_volumes = np.abs(differential_volumes)
        if differential_volumes.sum() > 0:
            differential_volumes = differential_volumes / differential_volumes.sum() * 100
        
        # Create DataFrame
        dvh_df = pd.DataFrame({
            'Dose[Gy]': dose_bins,
            'Volume[%]': differential_volumes
        })
        
        return dvh_df
    
    def _generate_clinical_data(self, output_dir, patient_metadata):
        """Generate clinical data file with TCP and NTCP outcomes"""
        
        # Create TCP clinical data
        tcp_data = patient_metadata.copy()
        
        # Create NTCP clinical data (multi-organ)
        ntcp_rows = []
        
        for idx, patient in patient_metadata.iterrows():
            patient_id = patient['PatientID']
            age = patient['Age']
            gender = patient['Gender']
            stage = patient['Stage']
            chemo = patient['ChemotherapyUsed']
            smoking = patient['Smoking_Status']
            total_dose = patient['TotalDose_Gy']
            
            # Generate toxicities for each organ
            # Parotids - Xerostomia
            for side in ['L', 'R']:
                organ = f'Parotid_{side}'
                
                # Xerostomia risk increases with dose
                # Base risk ~40%, higher with chemo
                xero_base_risk = 0.40
                if chemo == 1:
                    xero_base_risk += 0.15
                if smoking == 'Current':
                    xero_base_risk += 0.10
                if age > 65:
                    xero_base_risk += 0.05
                
                xero_base_risk = np.clip(xero_base_risk, 0.20, 0.80)
                xerostomia = np.random.binomial(1, xero_base_risk)
                
                if xerostomia:
                    xero_grade = np.random.choice([2, 3, 4], p=[0.60, 0.30, 0.10])
                else:
                    xero_grade = np.random.choice([0, 1], p=[0.70, 0.30])
                
                ntcp_rows.append({
                    'PatientID': patient_id,
                    'Organ': organ,
                    'Age': age,
                    'Gender': gender,
                    'Stage': stage,
                    'ChemotherapyUsed': chemo,
                    'Smoking_Status': smoking,
                    'TotalDose_Gy': total_dose,
                    'Xerostomia_Binary': xerostomia,
                    'Xerostomia_Grade': xero_grade,
                    'Toxicity': xerostomia  # Primary endpoint
                })
            
            # Pharyngeal constrictors - Dysphagia
            for level in ['S', 'M', 'I']:
                organ = f'Pharynx_Constrictor_{level}'
                
                dysphagia_base_risk = 0.35
                if chemo == 1:
                    dysphagia_base_risk += 0.20
                if age > 70:
                    dysphagia_base_risk += 0.10
                
                dysphagia_base_risk = np.clip(dysphagia_base_risk, 0.15, 0.75)
                dysphagia = np.random.binomial(1, dysphagia_base_risk)
                
                if dysphagia:
                    dysph_grade = np.random.choice([2, 3, 4], p=[0.55, 0.35, 0.10])
                else:
                    dysph_grade = np.random.choice([0, 1], p=[0.65, 0.35])
                
                ntcp_rows.append({
                    'PatientID': patient_id,
                    'Organ': organ,
                    'Age': age,
                    'Gender': gender,
                    'Stage': stage,
                    'ChemotherapyUsed': chemo,
                    'Smoking_Status': smoking,
                    'TotalDose_Gy': total_dose,
                    'Dysphagia_Binary': dysphagia,
                    'Dysphagia_Grade': dysph_grade,
                    'Toxicity': dysphagia
                })
        
        ntcp_data = pd.DataFrame(ntcp_rows)
        
        # Save files
        tcp_file = output_dir / "clinical_data_TCP.xlsx"
        ntcp_file = output_dir / "clinical_data_NTCP.xlsx"
        
        tcp_data.to_excel(tcp_file, index=False)
        ntcp_data.to_excel(ntcp_file, index=False)
        
        print(f"     TCP clinical data: {len(tcp_data)} patients")
        print(f"     NTCP clinical data: {len(ntcp_data)} organ entries")
        
        return tcp_file
    
    def _generate_metadata_file(self, output_dir, patient_metadata):
        """Generate metadata documentation file"""
        metadata = {
            'Dataset': 'Synthetic Head-Neck Cancer Radiotherapy Data',
            'Purpose': 'Testing rbGyanX Clinical Decision Support System',
            'n_patients': len(patient_metadata),
            'tumor_control_rate': f"{patient_metadata['TumorControl'].mean()*100:.1f}%",
            'median_followup_months': patient_metadata['FollowUp_Months'].median(),
            'prescription_doses': patient_metadata['TotalDose_Gy'].value_counts().to_dict(),
            'tumor_sites': patient_metadata['TumorSite'].value_counts().to_dict(),
            'stage_distribution': patient_metadata['Stage'].value_counts().to_dict(),
            'organs_included': list(self.organs.keys()),
            'data_generation_date': pd.Timestamp.now().strftime('%Y-%m-%d'),
            'notes': 'This is synthetic data for software testing. Do not use for clinical decisions.'
        }
        
        metadata_file = output_dir / "dataset_metadata.txt"
        
        with open(metadata_file, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("SYNTHETIC CLINICAL DATASET METADATA\n")
            f.write("=" * 70 + "\n\n")
            
            for key, value in metadata.items():
                f.write(f"{key}:\n  {value}\n\n")
        
        return metadata_file


# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate synthetic clinical data for rbGyanX testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python synthetic_data_generator.py --output ./test_data --patients 50
        """
    )
    
    parser.add_argument('--output', type=str, default='synthetic_clinical_data',
                       help='Output directory for synthetic data')
    parser.add_argument('--patients', type=int, default=50,
                       help='Number of patients to generate (default: 50)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility (default: 42)')
    
    args = parser.parse_args()
    
    # Generate dataset
    generator = SyntheticClinicalDataGenerator(
        n_patients=args.patients,
        random_seed=args.seed
    )
    
    result = generator.generate_complete_dataset(args.output)
    
    print("\n" + "=" * 70)
    print("SYNTHETIC DATASET GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nOutput directory: {args.output}")
    print(f"DVH files: {result['dvh_dir']}")
    print(f"Tumor DVH files: {result['tumor_dvh_dir']}")
    print(f"Clinical data: {result['clinical_file']}")
    print(f"Metadata: {result['metadata_file']}")
    print("\nYou can now use this data to test rbGyanX!")
