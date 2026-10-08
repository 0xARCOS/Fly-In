# Documentación de Fly-In

Toda la documentación del proyecto está en esta carpeta, escrita sobre el
código entregado. El `README.md` de la raíz es otra cosa: la carta de
presentación que exige el subject (Cap. VIII), en inglés y dirigida al
evaluador. Aquí vive el detalle, en español.

Qué cambió en la preparación de la entrega (ventana mínima,
`--capacity-info`, comentarios en inglés y esta reorganización):
[`CAMBIOS.md`](./CAMBIOS.md).

## Contenido

```
entrega/
├── README.md          este índice
├── CAMBIOS.md         los cambios de la entrega
├── subject/           el subject (PDF), la hoja de evaluación y el diagrama drawio
├── referencia/        qué se construye y por qué: reglas, arquitectura, algoritmo…
├── build/             cómo se construye cada pieza: una guía por subproyecto
├── narrativas/        cómo quedó cada pieza, contado de principio a fin
├── diagramas/         diagramas Mermaid de los puntos clave para la defensa
├── defensa/           preparación de la evaluación
├── ensayo/            el parche de --capacity-info para el live coding
└── img/               capturas reales de la ventana
```

### `subject/`

| Fichero | Qué es |
|---|---|
| [`Fly-In.pdf`](./subject/Fly-In.pdf) | El subject original. Ante cualquier contradicción con esta documentación, **manda el PDF** |
| [`hoja-evaluacion.md`](./subject/hoja-evaluacion.md) | La hoja de evaluación de la intra |
| [`Fly_in.drawio`](./subject/Fly_in.drawio) | Diagrama de diseño (draw.io) |

### `referencia/` — qué y por qué

| Fichero | Contenido |
|---|---|
| [`00-el-problema.md`](./referencia/00-el-problema.md) | Las reglas del subject extraídas del PDF y ordenadas: ocupación, movimiento, costes, salida, puntuación. **La fuente normativa** |
| [`01-roadmap.md`](./referencia/01-roadmap.md) | Los 12 subproyectos, en orden, con su grafo de dependencias |
| [`02-arquitectura.md`](./referencia/02-arquitectura.md) | Diseño orientado a objetos: módulos, clases y decisiones justificadas |
| [`03-formato-datos.md`](./referencia/03-formato-datos.md) | Gramática del archivo de mapa y formato exacto de la salida |
| [`04-algoritmo.md`](./referencia/04-algoritmo.md) | Teoría: Dijkstra → Cooperative A\* → WHCA\*. Por qué existe cada escalón |
| [`05-plan-de-pruebas.md`](./referencia/05-plan-de-pruebas.md) | Qué se prueba en cada subproyecto, mapas de prueba y matriz de benchmarks |
| [`06-glosario.md`](./referencia/06-glosario.md) | Todos los términos del proyecto definidos |
| [`07-diagramas.md`](./referencia/07-diagramas.md) | Diagramas de flujo de cada subproyecto (SP00–SP11), de cómo se relacionan y de los flujos transversales (`make run` completo, `stdout`/`stderr`, excepciones, estados del dron, replanificación, observadores, hilos y recursos) |

### `build/` — guías de construcción

Un **subproyecto** es una unidad de trabajo que se empieza y se termina:
prerequisitos explícitos, un contrato de código, una lista de pasos y un
criterio de salida verificable.

| Subproyecto | Qué construye |
|---|---|
| [`SP00`](./build/SP00-setup.md) | Repositorio, `Makefile`, entorno, linters |
| [`SP01`](./build/SP01-modelo-dominio.md) | `Zone`, `Connection`, `Graph` |
| [`SP02`](./build/SP02-parser.md) | `MapParser` y mapas de prueba |
| [`SP03`](./build/SP03-cli-y-errores.md) | Lectura de fichero, argumentos, errores limpios |
| [`SP04`](./build/SP04-dijkstra.md) | `Dijkstra`: ruta óptima de **un** dron |
| [`SP05`](./build/SP05-heuristica-abstracta.md) | `AbstractDistance`: la heurística `h(n)` ([guía de corrección](./build/SP05-guia-correccion.md)) |
| [`SP06`](./build/SP06-tabla-reservas.md) | `ReservationTable`: ocupación espacio-temporal |
| [`SP07`](./build/SP07-whca.md) | `WhcaPathfinder`: búsqueda cooperativa con ventana |
| [`SP08`](./build/SP08-drone-y-simulador.md) | `Drone` y `Simulator`: el bucle turno a turno |
| [`SP09`](./build/SP09-formato-salida.md) | `OutputFormatter`: la salida exacta del subject |
| [`SP10`](./build/SP10-visualizacion.md) | Ventana pygame y log de eventos a color |
| [`SP11`](./build/SP11-benchmarks-y-readme.md) | Benchmarks, ajuste y `README.md` final |

Convenciones de las guías: los bloques **⚠️ No lo des por sentado** explican
un concepto donde la gente se atasca; los **🔍 Verifica** son comprobaciones
de un minuto. El código de las guías son **contratos** (firmas y
docstrings), no implementaciones.

### `narrativas/` — una por fase

Qué regla del subject pide cada pieza, qué se decidió, qué se descartó y cómo
se prueba.

| Fichero | Fase |
|---|---|
| [`SP00-narrativa.md`](./narrativas/SP00-narrativa.md) | Setup, `Makefile` y `pyproject.toml` |
| [`SP01-narrativa.md`](./narrativas/SP01-narrativa.md) | Modelo de dominio: `Zone`, `Connection`, `Graph`, errores |
| [`SP02-narrativa.md`](./narrativas/SP02-narrativa.md) | Parser |
| [`SP03-narrativa.md`](./narrativas/SP03-narrativa.md) | Línea de comandos y frontera de excepciones |
| [`SP04-narrativa.md`](./narrativas/SP04-narrativa.md) | Dijkstra |
| [`SP05-narrativa.md`](./narrativas/SP05-narrativa.md) | Heurística abstracta |
| [`SP06-SP07-narrativa.md`](./narrativas/SP06-SP07-narrativa.md) | Tabla de reservas y WHCA\* |
| [`SP08-narrativa.md`](./narrativas/SP08-narrativa.md) | Simulador |
| [`SP09-narrativa.md`](./narrativas/SP09-narrativa.md) | Formato de salida |
| [`SP10-narrativa.md`](./narrativas/SP10-narrativa.md) | Visualización (ventana mínima y log) |
| [`SP11-narrativa.md`](./narrativas/SP11-narrativa.md) | Benchmarks y entrega |

### `diagramas/` — en Mermaid

| Fichero | Qué explica |
|---|---|
| [`E.1-metrics.md`](./diagramas/E.1-metrics.md) | `Metrics.from_trace`: las métricas secundarias desde la traza |
| [`E.2-benchmarks.md`](./diagramas/E.2-benchmarks.md) | `BenchmarkSuite`: los 10 mapas oficiales y las 12 configuraciones |
| [`E.3-whca-spacetime.md`](./diagramas/E.3-whca-spacetime.md) | WHCA\*: A\* en `(zona, turno)`, `plan`, ventana y replanificación |
| [`E.4-render-pipeline.md`](./diagramas/E.4-render-pipeline.md) | De la simulación a la ventana y al log |
| [`E.5-drone-color.md`](./diagramas/E.5-drone-color.md) | Colores de zonas y drones, y su paso a ANSI |
| [`E.6-live-coding-flow.md`](./diagramas/E.6-live-coding-flow.md) | `--capacity-info`: el observador y la salida intercalada |

### `defensa/` — para la evaluación

| Fichero | Para qué |
|---|---|
| [`cumplimiento-hoja-evaluacion.md`](./defensa/cumplimiento-hoja-evaluacion.md) | Cada apartado de la hoja de evaluación con su prueba |
| [`14-cumplimiento-subject.md`](./defensa/14-cumplimiento-subject.md) | Cada norma del subject con el fichero, test o comando que la demuestra; auditoría de docstrings y OOP |
| [`13-defensa-visualizacion.md`](./defensa/13-defensa-visualizacion.md) | La visualización pieza a pieza, preguntas probables con su respuesta, la demo y los tests |
| [`fase-visual.md`](./defensa/fase-visual.md) | La ventana elemento a elemento, con el método que lo dibuja |
| [`guia-live-coding.md`](./defensa/guia-live-coding.md) | `--capacity-info`: cómo enseñarlo y cómo reescribirlo en directo |

### `ensayo/`

[`diff-flag.patch`](./ensayo/diff-flag.patch): el flag `--capacity-info`
completo (observador, `main.py`, `Makefile` y tests) como parche, para
quitarlo y volver a escribirlo delante del evaluador:

```console
$ git apply -R entrega/ensayo/diff-flag.patch   # sin el flag: 411 tests, mypy --strict limpio
$ git checkout -- .                             # vuelta al código entregado: 425 tests
```

## Orden de lectura para la defensa

1. [`cumplimiento-hoja-evaluacion.md`](./defensa/cumplimiento-hoja-evaluacion.md):
   qué se va a comprobar y cómo enseñarlo.
2. SP06-SP07 y SP08: el algoritmo y el simulador, lo más preguntado. Con
   [E.3](./diagramas/E.3-whca-spacetime.md) al lado.
3. SP10, [`fase-visual.md`](./defensa/fase-visual.md) y
   [`13-defensa-visualizacion.md`](./defensa/13-defensa-visualizacion.md): la
   visualización.
4. SP11 y [E.2](./diagramas/E.2-benchmarks.md): los números.
5. [`guia-live-coding.md`](./defensa/guia-live-coding.md), ensayada con
   cronómetro.

## Antes de la defensa

```console
$ make install && make lint && make lint-strict && make test && make bench
```

Debe dar flake8 y mypy limpios (42 ficheros), 425 tests y 10 de 10 mapas en
objetivo (challenger en 43).
