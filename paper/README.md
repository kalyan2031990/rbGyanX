# rbGyanX paper-figure capsule

Reproduces schematic figures for the Medical Physics manuscript without patient PHI.

`data/cohort.csv` is **synthetic**, generated for this figure capsule: 20 rows with sequential
`P001`-style labels and no patient data of any kind. `data/ground_truth.json` declares the
planted outliers (`ccs_outlier_indices`) that the figures are expected to surface, which is only
meaningful for fabricated data.

```bash
pip install -r paper/requirements.txt
pip install -e ./engine
python paper/reproduce_figures.py
```

Outputs: `paper/figures/*.png`

When `rbgyanx_engine` is importable, ENGINE HOOKs call the real primitives; otherwise
reference implementations are used (printed at runtime).
