# project_rbGyanx — rbGyanX 1.0 (unified)

Single desktop distribution combining:

| Path | Contents |
|------|----------|
| **/** | Tkinter app (`rbgyanx_gui.py`), legacy code1–7, packaging |
| **engine/** | `rbgyanx-engine` (TCP/NTCP/UTCP/QUANTEC/physical metrics) |
| **test_data/dicom_input/** | Standard 4-patient DICOM cohort |
| **dist/** | `rbGyanX-1.0.0-full-Setup.exe` after build |

## Quick start (developers)

```powershell
cd $env:USERPROFILE\OneDrive\Desktop\project_rbGyanx
.\Install-rbGyanX.ps1
python rbgyanx_gui.py
```

## Build full installer (TensorFlow bundled)

```powershell
.\packaging\build_rbGyanX.ps1 -BuildInstaller
# Output: dist\rbGyanX-1.0.0-full-Setup.exe
```

## Engine CLI

```powershell
$env:RBGYANX_ENGINE_PATH = "$PWD\engine"
python -m rbgyanx_engine --dicom-dir test_data\dicom_input --endpoint both --cohort --output-dir out --no-uncertainty
```
