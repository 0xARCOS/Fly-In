# Cumplimiento de la hoja de evaluación

Cada apartado de la hoja ([`subject/hoja-evaluacion.md`](../subject/hoja-evaluacion.md))
con la prueba que se puede enseñar en la defensa: el comando, el fichero o el
test. Todo lo de esta página se ha ejecutado sobre el código actual.

## Estado

| Comprobación | Resultado |
|---|---|
| `make test` | 425 tests, todos pasan |
| `make lint` y `make lint-strict` | `Success: no issues found in 42 source files`; flake8 sin avisos |
| Funciones o clases sin docstring en `fly_in/` | 0 (auditoría con `ast` de [`14-cumplimiento-subject.md`](./14-cumplimiento-subject.md)) |
| Comentarios y docstrings | Todos en inglés (`fly_in/`, `test/` y los mapas propios) |
| Funciones fuera de una clase en `fly_in/` | 0 |
| `make bench` | 10 de 10 mapas dentro del objetivo; challenger en 43 |

---

## Preliminaries

**Work submission.** El repositorio solo lleva código, tests, mapas,
`README.md`, `Makefile`, `pyproject.toml`, `.gitignore`, `.flake8` y la
carpeta `entrega/`, que reúne toda la documentación (guía de construcción,
narrativas, diagramas, defensa y el subject).

## README.md

| Pide | Dónde |
|---|---|
| Description | `## Description` |
| Instructions | `## Instructions`: `make install`, `make run`, opciones, `stdout` limpio |
| Algorithm explanation | `## Algorithm and implementation strategy`: el pipeline, decisiones, complejidad, benchmarks y límites |
| Visual representation | `## Visual representation`: la ventana y el log, con capturas, y por qué ayudan |
| Example input and output | `## Example`: `bottleneck.txt` y `restricted_chain.txt` con su salida exacta |

## Project Structure and Requirements

**OOP.** Todo el código vive en clases (0 funciones de módulo). Instancias con
estado: `Graph`, `Simulator`, `Drone`, `ReservationTable`, `WhcaPathfinder`,
`Session`, `EventLog`, `PygameView`. Polimorfismo por interfaz: los
`Protocol` `SimulationObserver` (lo cumplen `ReplayRecorder` y
`ObserverGroup`), `DroneLike` y `AnimatedView`. Herencia en las excepciones:
`MapParseError` y `MapValidationError` heredan de `MapError`.

**Type safe.** `make lint-strict` → `mypy --strict` sin errores en los 42
ficheros, tests incluidos.

**Graph implementation.** `Graph`, `Dijkstra`, `AbstractDistance`,
`ReservationTable` y `WhcaPathfinder` son código propio; la única dependencia
es `pygame-ce`, que solo dibuja. `grep -rn "networkx\|graphlib" fly_in` no
encuentra nada.

## Parser Implementation

**Input files (5 de 5).**

| Formato | Prueba |
|---|---|
| `nb_drones: <n>` | `test_nb_drones_must_be_a_positive_integer` |
| `start_hub:`, `end_hub:`, `hub:` | `test_valid_maps_parse`, `test_official_maps_parse` |
| `connection: a-b` | `test_connection_default_and_explicit_capacity` |
| Metadatos con valores por defecto (`zone=normal`, `max_drones=1`, `max_link_capacity=1`) | `test_zone_defaults`, `test_connection_default_and_explicit_capacity` |
| Comentarios con `#` | `test_comments_and_blank_lines_keep_original_line_numbers` |

**Error handling (5 de 5).** Todos salen como `Error: …` en `stderr`, con la
línea cuando la hay, y código 1:

| Caso | Mapa | Mensaje |
|---|---|---|
| Sin `nb_drones` | `maps/errors/missing_nb_drones.txt` | `Line 1: … -> First line must define 'nb_drones: <positive_integer>'` |
| Tipo de zona inválido | `maps/errors/invalid_zone_type.txt` | `Invalid zone type 'invalido', must be one of [...]` |
| Sin `start_hub` | `maps/errors/no_start.txt` | `Map needs a 'start_hub'` |
| Capacidad no positiva | `maps/errors/negative_capacity.txt` | `max_drones must be a positive integer, got -1` |
| Zona o conexión duplicada | `maps/errors/duplicate_zone_name.txt`, `duplicate_connection.txt` | `Zone name 'mid' is already defined` / `Duplicate connection between 'mid' and 'start'` |

`test_error_maps_fail_with_the_right_cause` recorre los 10 mapas de error.

## Zone and Movement Mechanics

**Zone occupancy.** `max_drones` por zona (1 por defecto), `start_hub` y
`end_hub` sin límite. Lo impide `ReservationTable.can_move` al planificar y lo
vuelve a comprobar `Simulator._verify` en cada turno, contando de forma
independiente: si algo no cuadrara, la simulación se pararía con
`SimulationError`. Tests: `test_invariants_hold_on_valid_maps`,
`test_invariants_hold_on_official_maps`,
`test_capacity_violation_is_caught_at_the_turn_it_happens`.

**Movement costs.** `MOVEMENT_COST` en `models/zone.py`: `normal` 1,
`priority` 1 (y preferida en los empates), `restricted` 2, `blocked`
inaccesible. En la salida, un tránsito a `restricted` son dos líneas:

```
D1-start-r1
D1-r1
```

Tests: `test_restricted_chain_adds_two_per_zone`,
`test_priority_wins_ties_regardless_of_connection_order`,
`test_blocked_zone_is_never_part_of_the_route`,
`test_transit_prints_connection_then_zone`.

**Connection capacity.** `max_link_capacity` (1 por defecto) en cada turno del
trayecto, también en los dos de un tránsito; sin cruces de frente
(`would_swap`). Tests en `test/test_reservation_table.py` (27) y
`test_restricted_transit_reserves_link_two_consecutive_turns`.

## Visual Representation

Ventana pygame mínima: el mapa en sus coordenadas sobre fondo blanco, las
zonas como círculos pastel con los colores de `color=` (o el de su tipo), la
ocupación de cada zona como `ocupados/max_drones` (borde y etiqueta en rojo
cuando está llena), los drones como puntos numerados que se deslizan entre
zonas (y esperan en el centro de la conexión durante un tránsito a
`restricted`) y una línea de estado con turno y entregados; y en la terminal,
a la vez, un log a color con la línea de `stdout` de cada turno, quién espera
y por qué. Con `--capacity-info`, además, el uso de zonas y conexiones de
cada turno. Defensa completa en
[`13-defensa-visualizacion.md`](./13-defensa-visualizacion.md) y
[`fase-visual.md`](./fase-visual.md).

## Basic Functionality Tests

| Pide | Prueba |
|---|---|
| Un dron, camino lineal | `make run MAP=maps/valid/single_drone.txt` → `D1-goal` |
| Varios drones por caminos distintos | `maps/valid/two_corridors.txt` (`D1-a1 D2-b1`, cada uno por su pasillo); `test_drones_split_between_equal_corridors` |
| Mapas de ejemplo | Los 10 oficiales: `make bench` |
| Formato `D<ID>-<zona>` / `D<ID>-<conexión>` | `test_every_line_has_the_subject_format` (19 mapas) |
| Los que no se mueven se omiten | `test_turn_without_moves_produces_no_line` |

**Simulation ends correctly.** La salida acaba en la línea en que entrega el
último dron, y los entregados no reaparecen
(`test_delivered_drones_never_reappear`).

## Pathfinding Algorithm

**Valid path.** WHCA\* encuentra solución en los 19 mapas (9 válidos y 10
oficiales), con bifurcaciones, cuellos de botella y los cuatro tipos de zona.

**Conflict resolution.** Cada dron busca en `(zona, turno)` contra la tabla de
reservas de los que planificaron antes; esperar es un movimiento más; la
reserva provisional evita que alguien quede encerrado. Tests:
`test_two_drones_never_share_narrow`, `test_three_drones_all_arrive_taking_turns`,
`test_swap_corridor_both_planned_never_meet_head_on`,
`test_second_drone_cannot_enter_link_mid_transit`.

## Performance and Optimization

**Efficiency.** El challenger (25 drones, 54 zonas) se calcula en ~0,25 s; los
10 mapas oficiales, en `make bench`.

**Algorithm explanation.** README, sección *Algorithm and implementation
strategy* (complejidad incluida), y
[`diagramas/E.3-whca-spacetime.md`](../diagramas/E.3-whca-spacetime.md).

## Performance Benchmarks

| Mapa | Drones | Objetivo | **Turnos** |
|---|---|---|---|
| easy/01_linear_path | 2 | ≤ 6 | **4** |
| easy/02_simple_fork | 4 | ≤ 8 | **4** |
| easy/03_basic_capacity | 4 | ≤ 6 | **4** |
| medium/01_dead_end_trap | 5 | ≤ 12 | **8** |
| medium/02_circular_loop | 6 | ≤ 15 | **15** |
| medium/03_priority_puzzle | 5 | ≤ 12 | **7** |
| hard/01_maze_nightmare | 8 | ≤ 30 | **13** |
| hard/02_capacity_hell | 12 | ≤ 35 | **16** |
| hard/03_ultimate_challenge | 15 | ≤ 45 | **26** |
| challenger/01_the_impossible_dream | 25 | batir 45 | **43** |

| Pregunta de la hoja | Media | ¿Cumple? |
|---|---|---|
| Easy en menos de 10 turnos de media | 4,0 | Sí |
| Medium entre 10 y 30 de media | 10,0 | Sí, en el límite inferior: los mapas se resuelven antes de lo que espera la hoja |
| Hard en menos de 60 de media | 18,3 | Sí |

**Bonus: exceptional performance.** Los 9 mapas con objetivo lo cumplen o lo
mejoran. **Challenger:** 43 turnos, por debajo del récord de 45.

**Sobre medium/02 (15 de 15):** con la lectura estricta de `restricted` (la
conexión está ocupada los dos turnos del tránsito) es el óptimo: la conexión
`loop_b-exit_point`, de capacidad 1, admite un dron cada dos turnos.

## Edge Cases and Error Handling

| Caso | Resultado |
|---|---|
| Un solo dron | `maps/valid/single_drone.txt` → `D1-goal` |
| Cuellos de botella | `maps/valid/bottleneck.txt`: se turnan, 4 turnos (óptimo) |
| Grafo desconectado | `Error: 'e' is unreachable from 's'`, antes de simular |
| Conexiones inválidas | Zona desconocida, duplicada o una zona consigo misma: `A zone can't connect to itself: 's'` |
| Capacidad 0 o muy alta | `max_drones=0` → `must be a positive integer, got 0`; `max_drones=1000` y `max_link_capacity=1000` con 5 drones → todos a la vez, 2 turnos |

Además: `start_hub` `blocked`, fichero inexistente, carpeta, no UTF-8,
`--window 0`, `--delay nan`, Ctrl+C y `stderr` cerrado salen con un mensaje y
sin traceback (`test/test_cli.py`).

## Code Quality

Módulos pequeños por responsabilidad (`models`, `parsing`, `pathfinding`,
`simulation`, `output`, `visualization`), docstrings y comentarios en
inglés en todo, flake8 y `mypy --strict` limpios. La visualización solo lee
la grabación del simulador.

## Live coding: `--capacity-info`

El flag **ya está** en el código entregado y probado (14 tests en
`test/test_capacity_observer.py`): `make capacity MAP=… ARGS=-q`. Guion para
enseñarlo, o para quitarlo y reescribirlo delante del evaluador, en
[`guia-live-coding.md`](./guia-live-coding.md); el parche
[`ensayo/diff-flag.patch`](../ensayo/diff-flag.patch) lo quita
(`git apply -R` → 411 tests y `mypy --strict` limpio) y lo vuelve a poner.

---

## Antes de la defensa

```console
$ git clone <repo> /tmp/flyin && cd /tmp/flyin
$ make install
$ make lint && make lint-strict
$ make test
$ make bench
$ make run MAP=maps/oficial_maps/medium/02_circular_loop.txt
$ make capacity MAP=maps/valid/bottleneck.txt ARGS=-q
$ make clean
```
