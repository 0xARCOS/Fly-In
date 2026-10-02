# Paquete de defensa — Fly-In

Material para preparar la evaluación. No se versiona (`.gitignore`): el
repositorio que se corrige es el código, los tests, los mapas y `docs/`. Todo
lo de aquí está escrito sobre el código actual.

## Contenido

### Narrativas, una por fase

[`narrativas/`](./narrativas/): qué regla del subject pide cada pieza, qué se
decidió, qué se descartó y cómo se prueba.

| Fichero | Fase |
|---|---|
| [`SP00-narrativa.md`](./narrativas/SP00-narrativa.md) | Setup, `Makefile` y `pyproject.toml` |
| [`SP01-narrativa.md`](./narrativas/SP01-narrativa.md) | Modelo de dominio: `Zone`, `Connection`, `Graph`, errores |
| [`SP02-narrativa.md`](./narrativas/SP02-narrativa.md) | Parser |
| [`SP03-narrativa.md`](./narrativas/SP03-narrativa.md) | Línea de comandos y frontera de excepciones |
| [`SP04-narrativa.md`](./narrativas/SP04-narrativa.md) | Dijkstra |
| [`SP05-narrativa.md`](./narrativas/SP05-narrativa.md) | Heurística abstracta |
| [`SP06-SP07-narrativa.md`](./narrativas/SP06-SP07-narrativa.md) | Tabla de reservas y WHCA\* (copia de `docs/08`) |
| [`SP08-narrativa.md`](./narrativas/SP08-narrativa.md) | Simulador (copia de `docs/09`) |
| [`SP09-narrativa.md`](./narrativas/SP09-narrativa.md) | Formato de salida (copia de `docs/10`) |
| [`SP10-narrativa.md`](./narrativas/SP10-narrativa.md) | Visualización (copia de `docs/11`) |
| [`SP11-narrativa.md`](./narrativas/SP11-narrativa.md) | Benchmarks y entrega (copia de `docs/12`) |

Las copias se mantienen idénticas a `docs/`; solo cambian los enlaces
relativos.

### Diagramas

[`diagramas/`](./diagramas/), en Mermaid:

| Fichero | Qué explica |
|---|---|
| [`E.1-metrics.md`](./diagramas/E.1-metrics.md) | `Metrics.from_trace`: las métricas secundarias desde la traza |
| [`E.2-benchmarks.md`](./diagramas/E.2-benchmarks.md) | `BenchmarkSuite`: los 10 mapas oficiales y las 12 configuraciones |
| [`E.3-whca-spacetime.md`](./diagramas/E.3-whca-spacetime.md) | WHCA\*: A\* en `(zona, turno)`, `plan`, ventana y replanificación |
| [`E.4-render-pipeline.md`](./diagramas/E.4-render-pipeline.md) | De la simulación a la ventana y al log |
| [`E.5-drone-color.md`](./diagramas/E.5-drone-color.md) | Colores de zonas y drones, y su paso a ANSI |
| [`E.6-live-coding-flow.md`](./diagramas/E.6-live-coding-flow.md) | La solución de `--capacity-info` |

### Documentos de defensa

| Fichero | Para qué |
|---|---|
| [`cumplimiento-hoja-evaluacion.md`](./cumplimiento-hoja-evaluacion.md) | Cada apartado de la hoja de evaluación con su prueba |
| [`fase-visual.md`](./fase-visual.md) | La ventana elemento a elemento, con el método que lo dibuja |
| [`guia-live-coding.md`](./guia-live-coding.md) | El guion de `--capacity-info` en 10 minutos |

### Ensayo del live coding

[`ensayo/`](./ensayo/): la solución de referencia, probada sobre el código
actual.

| Fichero | Qué es |
|---|---|
| `capacity_observer.py` | El observador nuevo |
| `diff-flag.patch` | Todos los cambios: el observador, los tres de `main.py` y el test |
| `test_capacity_observer.py` | 12 tests |

```console
$ git apply entrega/ensayo/diff-flag.patch      # 423 tests, mypy --strict limpio
$ git apply -R entrega/ensayo/diff-flag.patch   # vuelta al código entregado
```

## Orden de lectura para la defensa

1. [`cumplimiento-hoja-evaluacion.md`](./cumplimiento-hoja-evaluacion.md): qué
   se va a comprobar y cómo enseñarlo.
2. SP06-SP07 y SP08: el algoritmo y el simulador, lo más preguntado. Con
   [E.3](./diagramas/E.3-whca-spacetime.md) al lado.
3. SP10 y [`fase-visual.md`](./fase-visual.md): la visualización.
4. SP11 y [E.2](./diagramas/E.2-benchmarks.md): los números.
5. [`guia-live-coding.md`](./guia-live-coding.md), ensayada con cronómetro.

## Antes de la defensa

```console
$ make install && make lint && make lint-strict && make test && make bench
```

Debe dar flake8 y mypy limpios, 411 tests y 10 de 10 mapas en objetivo.
