# SP00 — Setup del repositorio y Makefile

> **Estado:** implementado. En una copia recién clonada, `make install` y
> después `make run MAP=…` funcionan sin pasos manuales.

## El problema

El subject fija las reglas del `Makefile` (Cap. III.2): `install`, `run`,
`debug`, `clean` y `lint` con unos flags de mypy concretos, y `lint-strict`
como opcional. Si cada regla dependiera de lo que haya instalado en la máquina
(un `flake8` global, un entorno activado a mano), el resultado cambiaría de un
ordenador a otro y no se podría defender.

## La decisión: un entorno propio y comandos explícitos

Todas las reglas usan el Python de `.venv`, nunca el del sistema:

```makefile
VENV        := .venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip

.DEFAULT_GOAL := install

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

lint:
	$(PYTHON) -m flake8 .
	$(PYTHON) -m mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
```

| Regla | Qué ejecuta |
|---|---|
| `install` (y `make` a secas) | Crea `.venv`, actualiza pip e instala el paquete en modo editable con las herramientas de desarrollo |
| `run` | `python -m fly_in.main $(MAP) $(ARGS)` |
| `debug` | El mismo programa bajo `pdb` |
| `lint` | flake8 y mypy con los flags exactos del subject |
| `lint-strict` | flake8 y `mypy --strict` |
| `test` | `pytest -q` |
| `bench` | `python -m fly_in.benchmarks` |
| `clean` | Borra `.mypy_cache`, `.pytest_cache`, `*.egg-info` y los `__pycache__` (sin entrar en `.venv`) |

Cada regla escribe el comando real tal cual: lo que se ve es lo que se
ejecuta, y el código de salida es el del comando.

`pyproject.toml` es la única fuente de dependencias:

```toml
[project]
requires-python = ">=3.10"
dependencies = ["pygame-ce>=2.4"]

[project.optional-dependencies]
dev = ["flake8", "mypy", "pytest"]
```

`pygame-ce` es la única dependencia en tiempo de ejecución, y solo dibuja la
ventana: el programa funciona sin ella (SP10). En el mismo fichero,
`[tool.mypy]` fija `python_version = "3.10"` y `[tool.pytest.ini_options]`
limita los tests a `test/`.

## Alternativa descartada: los flags de mypy en la configuración

Se podrían poner en `[tool.mypy]` y llamar a `mypy .` sin más. No se hizo: el
subject los da literalmente para la regla `lint`, y tenerlos escritos en la
regla deja un solo sitio donde comprobarlos.

## El código

- [`Makefile`](../../Makefile)
- [`pyproject.toml`](../../pyproject.toml)
- [`.flake8`](../../.flake8): solo excluye directorios (`.venv`, cachés,
  `entrega`)
- `.gitignore`: `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`, cachés,
  `build/`, `dist/`

## Verificación

```console
$ make install
$ make lint && make lint-strict      # Success: no issues found in 42 source files
$ make test                          # 425 passed
$ make clean
```

---

Continúa en [SP01](./SP01-narrativa.md): el modelo de dominio.
