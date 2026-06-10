# Contributing to rbGyanX

## Development setup

```bash
git clone https://github.com/kalyan2031990/rbGyanX.git
cd rbGyanX
pip install -e "./engine[ml]" -e "./engine_advanced[pinn,dose3d]" -e "./engine_advanced_f[bayesian,pinn]" -e ".[dev,ml,torch,bayesian]"
pytest
```

Windows: `.\scripts\install_dev.ps1`

## Ground rules

1. **Do not change classical model numerics** without an analytic test citing the literature.
2. Every production change needs a test.
3. BASIC mode must remain ML-free; empty inputs return **NaN**, not 0.
4. No new required ML dependencies in `engine/` core.

## Quality gate (matches CI)

```bash
make verify   # ruff + black + mypy + pytest --cov
```

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `test:`, `docs:`, `ci:`.
