VENV        := .venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
MAP         ?= maps/valid/linear.txt
ARGS        ?=

# Pantallas de carga: todo va a stderr y se degrada a texto plano sin
# terminal, así que stdout y los códigos de salida no cambian.
UI          := bash scripts/loading.sh

.DEFAULT_GOAL := menu
.PHONY: menu install run bench debug lint lint-strict test clean fclean

menu:
	@$(UI) menu

install:
	@$(UI) header "NEW GAME" "Installing Fly-In · Python >= 3.10"
	@$(UI) step 1/3 "Building the virtual environment" -- python3 -m venv $(VENV)
	@$(UI) step 2/3 "Upgrading pip" -- $(PIP) install --upgrade pip
	@$(UI) step 3/3 "Installing Fly-In, pygame + dev tools" -- $(PIP) install -e ".[dev]"
	@$(UI) finish "★  READY PLAYER ONE  ★" "Next: make run MAP=maps/oficial_maps/easy/01_linear_path.txt"

run:
	@$(UI) launch $(MAP)
	@$(PYTHON) -m fly_in.main $(MAP) $(ARGS)

bench:
	@$(UI) header "HIGH SCORES" "10 official maps · 12 configurations"
	@$(UI) step --show 1/1 "Racing every official map" -- $(PYTHON) -m fly_in.benchmarks

debug:
	@$(UI) header "DEBUG MODE" "pdb · $(MAP)"
	@$(PYTHON) -m pdb -m fly_in.main $(MAP)

lint:
	@$(UI) header "ANTI-CHEAT" "flake8 + mypy"
	@$(UI) step 1/2 "flake8 · style" -- $(PYTHON) -m flake8 .
	@$(UI) step --tail 2/2 "mypy · types" -- $(PYTHON) -m mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
	@$(UI) finish "✔  NO CHEATS DETECTED  ✔"

lint-strict:
	@$(UI) header "ANTI-CHEAT · HARD MODE" "flake8 + mypy --strict"
	@$(UI) step 1/2 "flake8 · style" -- $(PYTHON) -m flake8 .
	@$(UI) step --tail 2/2 "mypy --strict · types" -- $(PYTHON) -m mypy . --strict
	@$(UI) finish "✔  NO CHEATS DETECTED · HARD MODE  ✔"

test:
	@$(UI) header "TRAINING GROUND" "pytest"
	@$(UI) step --tail 1/1 "Running the test suite" -- $(PYTHON) -m pytest -q --ignore=entrega/
	@$(UI) finish "★  ALL CHALLENGES CLEARED  ★"

clean:
	@$(UI) header "SAVE CLEANUP" "caches"
	@$(UI) step 1/2 "Deleting tool caches" -- rm -rf .mypy_cache .pytest_cache *.egg-info
	@$(UI) step 2/2 "Deleting __pycache__" -- find . -path ./$(VENV) -prune -o -type d -name "__pycache__" \
		-exec rm -rf {} +

fclean: clean
	@$(UI) step 1/1 "Deleting the virtual environment" -- rm -rf $(VENV)
	@$(UI) finish "FACTORY RESET COMPLETE" "Start again with: make install"
