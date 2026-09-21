# SP00 — Setup del repositorio ✅

> **Estado:** hecho. Este documento registra *qué* se construyó y *por qué*, para
> que puedas reproducirlo desde cero o justificarlo en la review.

**Objetivo:** que un `make install && make run` funcione en un repositorio
recién clonado, aunque el programa todavía no haga nada.

**Prerequisitos:** ninguno. Es el primer subproyecto.

**Criterio de salida:** `make lint` y `make lint-strict` pasan sin errores.

---

## Paso 1 — La estructura de carpetas

```
Fly-In/
├── fly_in/              # el paquete Python (todo el código va aquí)
│   ├── __init__.py
│   ├── models/
│   └── parsing/
├── test/                # tests (no se entregan, ver 05-plan-de-pruebas.md)
├── maps/                # mapas de prueba
├── docs/                # esta guía
├── Makefile
├── pyproject.toml
├── .flake8
├── .gitignore
└── README.md
```

⚠️ **No lo des por sentado — qué convierte una carpeta en paquete**
Una carpeta con archivos `.py` no es importable por sí sola. Necesita un
`__init__.py` (puede estar vacío) para que Python la reconozca como paquete y
`from fly_in.models.zone import Zone` funcione. Cada vez que crees una carpeta
nueva dentro de `fly_in/`, crea su `__init__.py` en el mismo momento.

## Paso 2 — El `Makefile`

El subject fija los comandos de `lint` y `lint-strict` **de forma literal**
*(Cap. III.2)*. No son "flags equivalentes": son esos comandos exactos, porque un
evaluador puede comprobarlos a ojo.

| Target | Qué hace | Por qué |
|---|---|---|
| `install` | `python3 -m venv .venv`, actualiza pip, `pip install -e ".[dev]"` | Un solo comando, sin depender de que el desarrollador tenga `flake8`/`mypy` globales |
| `run` | `python -m fly_in.main` | Ejecuta el **módulo del paquete**, no un script suelto: sigue funcionando aunque `main.py` cambie de sitio dentro del paquete |
| `debug` | `python -m pdb -m fly_in.main` | Depuración sin montar configuración de IDE |
| `lint` | `flake8 .` + `mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs` | **Literal del subject**, mandatory |
| `lint-strict` | `flake8 .` + `mypy . --strict` | **Literal del subject**, marcado opcional pero se mantiene |
| `clean` | Borra `.venv`, `.mypy_cache`, `.pytest_cache`, `*.egg-info`, todos los `__pycache__` | Devuelve el repo al estado "recién clonado" |
| `test` | `pytest` | Extra, no pedido por el subject. Se añadió porque SP02 lo necesita de inmediato |

⚠️ **No lo des por sentado — usa `$(VENV)/bin/python` explícito**
Si escribes `python -m flake8`, el resultado depende de si el desarrollador
activó el entorno virtual a mano. Con la ruta explícita (`.venv/bin/python`),
`make lint` da el mismo resultado siempre. Es la diferencia entre "en mi máquina
funciona" y "funciona".

⚠️ **No lo des por sentado — los targets van en `.PHONY`**
`make` asume que un target produce un archivo con ese nombre. Si algún día
existiera un archivo llamado `test` o `clean`, `make test` diría *"nothing to be
done"* y no ejecutaría nada. `.PHONY: install run debug lint lint-strict test
clean` lo evita.

## Paso 3 — `pyproject.toml` y `.flake8`

**Por qué `pyproject.toml` y no `requirements.txt`:** al ser `fly_in/` un
paquete instalable, `pip install -e ".[dev]"` deja el proyecto instalado en modo
editable *y* trae las herramientas de desarrollo en un solo comando. Con
`requirements.txt` harían falta dos archivos diciendo cosas parecidas, con el
riesgo de que divergieran. El subject permite explícitamente cualquier gestor
de paquetes *(Cap. III.2)*.

**Por qué los flags de mypy viven en el `Makefile` y no en `[tool.mypy]`:**
porque el subject los fija literalmente. Duplicarlos en los dos sitios es
pedir que algún día divergan. `[tool.mypy]` guarda solo lo que el subject **no**
especifica: `python_version`, `no_implicit_optional`, la exclusión de `.venv/`.

**Por qué existe un archivo `.flake8` aparte:** a diferencia de `mypy`, flake8
no lee configuración de `pyproject.toml` de forma nativa (haría falta un plugin
externo). Su config va en su propio archivo.

## Paso 4 — `.gitignore`

Python estándar (`__pycache__/`, `*.pyc`, `.venv/`, `build/`, `*.egg-info/`) más
los caches de herramientas (`.mypy_cache/`, `.pytest_cache/`) y ruido de
editor/SO.

⚠️ **No lo des por sentado — `.gitignore` no destrackea nada**
`.gitignore` solo afecta a archivos que **todavía no están trackeados**. Si unos
`.pyc` ya se colaron en un commit anterior, añadirlos al `.gitignore` no los
saca del repositorio. Hay que hacerlo a mano:

```console
$ git rm -r --cached '**/__pycache__'   # deja de versionarlos, los mantiene en disco
```

Esto pasó de verdad en este repo: el `.gitignore` estaba vacío desde el commit
inicial y había `.pyc` versionados. Están destrackeados en el commit de SP00.

## Paso 5 — `main.py` mínimo

El criterio es que `make run` funcione "aunque no haga nada". Se creó un `main()`
que solo imprime un mensaje. El punto de entrada real (argumentos, lectura de
fichero) es [SP03](./SP03-cli-y-errores.md); escribirlo ahora sería adelantar
lógica de un subproyecto posterior.

---

## Verificación del criterio de salida

```console
$ make install
$ make lint
.venv/bin/python -m flake8 .
.venv/bin/python -m mypy . --warn-return-any --warn-unused-ignores \
    --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
Success: no issues found in 9 source files
$ make lint-strict
Success: no issues found in 9 source files
$ make run
Fly-In: proyecto inicializado (Fase 0). Aun no simula nada.
$ make clean
```

`make lint` detectó un fallo de tipos real y preexistente: `Graph.__init__` sin
anotar `-> None` en [`graph.py`](../../fly_in/models/graph.py). Se corrigió en
el mismo commit — sin anotar, `lint-strict` habría fallado desde el primer día.

## Decisiones tomadas

| Decisión | Por qué |
|---|---|
| `pyproject.toml` + extras `[dev]` en vez de `requirements.txt` | Un solo archivo, un solo comando de instalación |
| Flags de mypy literales en el `Makefile` | El subject los fija así; evitar duplicación con `[tool.mypy]` |
| `max-line-length = 100` en `.flake8` | 79 (el defecto de PEP 8) es incómodo con nombres largos y type hints; 100 sigue siendo legible en pantalla partida |
| Target `test` aunque no lo pida el subject | SP02 lo necesita inmediatamente y no cuesta nada dejarlo listo |
