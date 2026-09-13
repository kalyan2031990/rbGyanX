.PHONY: install-dev lint type test verify cov synthetic

install-dev:
	pip install --upgrade pip
	pip install -e "./engine[ml]" -e "./engine_advanced[pinn,dose3d]" -e "./engine_advanced_f[bayesian,pinn]" -e ".[dev,ml,torch,bayesian]"

lint:
	ruff check .
	black --check .

type:
	mypy engine/radiobiology

test:
	pytest --import-mode=importlib

cov:
	pytest --import-mode=importlib --cov --cov-report=term-missing --cov-fail-under=85

synthetic:
	pytest tests/synthetic --import-mode=importlib -v

verify: lint type cov
