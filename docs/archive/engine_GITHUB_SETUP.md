# Publish `rbGyanX_cdss` to GitHub

GitHub CLI auth was **invalid** during automated setup. Create the remote repo once, then push from this folder.

## 1. Create empty public repo on GitHub

**Option A — Web:** https://github.com/new  
- Repository name: `rbGyanX_cdss`  
- Public  
- Do **not** add README, .gitignore, or license (this repo already has them)

**Option B — CLI (after `gh auth login`):**

```powershell
gh auth login -h github.com
cd C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss
gh repo create rbGyanX_cdss --public --source=. --remote=origin --description "Open-source TCP/NTCP engine for rbGyanX CDSS"
git push -u origin main
```

## 2. First push (if repo created on web)

```powershell
cd C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss
git init
git add .
git commit -m "feat: rbgyanx-engine R1 — TCP+NTCP, DICOM, multi-site, run_analysis API"
git branch -M main
git remote add origin https://github.com/kalyan2031990/rbGyanX_cdss.git
git push -u origin main
```

## 3. Install from GitHub (consumers)

```bash
pip install "git+https://github.com/kalyan2031990/rbGyanX_cdss.git"
```

Private GUI (`rbgyanx_dual`) should pin:

```
rbgyanx-engine @ git+https://github.com/kalyan2031990/rbGyanX_cdss.git@v0.1.0a0
```
