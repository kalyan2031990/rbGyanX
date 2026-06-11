# rbGyanX paper-figure capsule

Reproduces schematic figures for the Medical Physics manuscript without patient PHI.

```bash
pip install -r paper/requirements.txt
pip install -e ./engine
python paper/reproduce_figures.py
```

Outputs: `paper/figures/*.png`

When `rbgyanx_engine` is importable, ENGINE HOOKs call the real primitives; otherwise
reference implementations are used (printed at runtime).
