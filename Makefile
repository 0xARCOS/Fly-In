VENV        := .venv
STAMP       := $(VENV)/.installed
MAP         ?= maps/valid/linear.txt
ARGS        ?=

.DEFAULT_GOAL := install
.PHONY: install run debug clean fclean lint lint-strict

# These rules use the tools of $(VENV) when it exists; only install creates it.
run debug lint lint-strict: export PATH := $(CURDIR)/$(VENV)/bin:$(PATH)

install: $(STAMP)

$(STAMP): pyproject.toml
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"
	touch $(STAMP)

run:
	python3 -m fly_in.main $(MAP) $(ARGS)

debug:
	python3 -m pdb -m fly_in.main $(MAP) $(ARGS)

clean:
	rm -rf .mypy_cache .pytest_cache build dist
	find . -path ./$(VENV) -prune -o -name "*.egg-info" -prune \
		-exec rm -rf {} +
	find . -path ./$(VENV) -prune -o -name "__pycache__" -type d -prune \
		-exec rm -rf {} +
	find . -path ./$(VENV) -prune -o -name "*.py[co]" -type f -exec rm -f {} +

fclean: clean
	rm -rf $(VENV)

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict
