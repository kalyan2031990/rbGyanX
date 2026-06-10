# Publishing rbGyanX test data on Zenodo

Publish **two Zenodo records** linked to the GitHub software. Software stays on GitHub; data and frozen test logs go to Zenodo for DOI-backed reproduction.

## Prerequisites

1. Zenodo account: https://zenodo.org/signup  
2. Link GitHub (optional, for software releases): Zenodo → Account → GitHub  
3. Build bundles:

```powershell
cd C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx
.\scripts\build_zenodo_bundle.ps1
```

## Record A — Synthetic (public)

**File:** `reproducibility/dist/rbGyanX_synthetic_test_data_v1.0.0.zip`

1. Zenodo → **New upload** → Upload zip.  
2. **Upload type:** Dataset  
3. **Title:** `rbGyanX synthetic test data and validation logs v1.0.0`  
4. **Authors:** Mondal, Kalyan (and co-authors)  
5. **Description:** Paste summary from `reproducibility/README_SYNTHETIC.md`.  
6. **License:** MIT  
7. **Keywords:** radiotherapy, NTCP, TCP, synthetic data, reproducibility  
8. **Related identifiers:**  
   - Relation: *Is supplement to*  
   - Identifier: `https://github.com/kalyan2031990/rbGyanX`  
9. **Publish** → copy DOI (e.g. `10.5281/zenodo.xxxxx`).

## Record B — Real de-identified cohort (restricted)

**File:** `reproducibility/dist/rbGyanX_real_test_data_v1.0.0.zip` (~1.5 GB)

1. **New upload** → upload zip.  
2. **Upload type:** Dataset  
3. **Title:** `rbGyanX de-identified real test cohort v1.0.0`  
4. **Access right:** **Restricted** (Zenodo access request workflow).  
5. **Description:** Paste from `reproducibility/README_REAL_DATA.md`; state ethics/DUA.  
6. **Related identifiers:**  
   - *Is supplement to* → GitHub repo URL  
   - *Is supplement to* → Record A DOI  
7. Publish → copy DOI.

## Wire DOIs into the repository

After both records are published:

```yaml
# CITATION.cff (example)
version: "1.0.0"
doi: "10.5281/zenodo.SOFTWARE_DOI"
```

Add a `references` block or note in README:

```markdown
- Software: https://github.com/kalyan2031990/rbGyanX
- Synthetic data: https://doi.org/10.5281/zenodo.SYNTHETIC
- Real cohort (restricted): https://doi.org/10.5281/zenodo.REAL
```

Commit, tag, and push:

```powershell
git add CITATION.cff README.md reproducibility/
git commit -m "Link Zenodo DOIs for reproduction datasets."
git tag -a v1.0.0 -m "rbGyanX 1.0.0"
git push origin main
git push origin v1.0.0
```

## Optional: GitHub release from tag

GitHub → Releases → **Draft new release** → choose `v1.0.0` → attach `rbGyanX-1.0.0-full-Setup.exe` if built locally (`packaging/build_rbGyanX.ps1`).

## Checklist

- [ ] Record A public on Zenodo  
- [ ] Record B restricted on Zenodo  
- [ ] DOIs in `CITATION.cff` and README  
- [ ] Git tag `v1.0.0` pushed  
- [ ] `docs/validation_report.json` matches bundled copy  
