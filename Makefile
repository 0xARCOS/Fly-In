VENV        := .venv
PYTHON      := $(VENV)/bin/python
STAMP       := $(VENV)/.installed
MAP         ?= maps/valid/linear.txt
ARGS        ?=
MYPY_FLAGS  := --warn-return-any --warn-unused-ignores --ignore-missing-imports \
               --disallow-untyped-defs --check-untyped-defs

.DEFAULT_GOAL := install
.PHONY: install run capacity bench debug lint lint-strict test clean

# The virtual environment is a real target: every rule that needs it builds it
# first, and it is rebuilt when pyproject.toml changes.
install: $(STAMP)

$(STAMP): pyproject.toml
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	touch $(STAMP)

run: $(STAMP)
	$(PYTHON) -m fly_in.main $(MAP) $(ARGS)

capacity: $(STAMP)
	$(PYTHON) -m fly_in.main $(MAP) --capacity-info $(ARGS)

bench: $(STAMP)
	$(PYTHON) -m fly_in.benchmarks

debug: $(STAMP)
	$(PYTHON) -m pdb -m fly_in.main $(MAP) $(ARGS)

lint: $(STAMP)
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . $(MYPY_FLAGS)

lint-strict: $(STAMP)
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --strict

test: $(STAMP)
	$(PYTHON) -m pytest -q

clean:
	rm -rf $(VENV) .mypy_cache .pytest_cache build dist
	find . -name "*.egg-info" -prune -exec rm -rf {} +
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.py[co]" -type f -delete
