VENV        := .venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip

.PHONY: install run debug lint lint-strict test clean

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

run:
	$(PYTHON) -m fly_in.main

debug:
	$(PYTHON) -m pdb -m fly_in.main

lint:
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --strict

test:
	$(PYTHON) -m pytest

clean:
	rm -rf $(VENV) .mypy_cache .pytest_cache *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
