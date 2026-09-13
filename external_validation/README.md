# External validation — TCIA HNSCC (Head-Neck-CT-Atlas)

Open-access de-identified data for **software pipeline external validation only**.
Data files are **git-ignored**; only acquisition code and provenance templates are tracked.

## Collections

| Item | DOI |
|------|-----|
| HNSCC parent | [10.7937/k9/tcia.2020.a8sh-7363](https://doi.org/10.7937/k9/tcia.2020.a8sh-7363) |
| Head-Neck-CT-Atlas (215 RT) | [10.7937/K9/TCIA.2017.umz8dv6s](https://doi.org/10.7937/K9/TCIA.2017.umz8dv6s) |

## Download

```powershell
pip install tcia-utils
python external_validation/download_hnscc.py --discover-only   # inspect counts first
python external_validation/download_hnscc.py --download      # bulk download (long)
```

Output layout (local, git-ignored):

```
external_validation/data/hnscc/
  CT/
  RTSTRUCT/
  RTDOSE/
  RTPLAN/
  clinical/
  DATA_PROVENANCE.md
  download_manifest.json
```

## Compliance

Use of TCIA data requires attribution per the [TCIA Data Usage Policy](https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/).
Do not redistribute downloaded files.

## Next step

After download, run Prompt B ingestion:

```powershell
python external_validation/run_hnscc_validation.py
```
