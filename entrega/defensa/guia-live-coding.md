# Guía de live coding: `--capacity-info`

La hoja de evaluación pide: *"add a `--capacity-info` flag that displays
capacity information during simulation, such as `Zone X: Y/Z drones,
Connection A-B: Y/Z capacity used` for each turn"*.

## Estado: ya está en el código

El flag está implementado y probado. Para enseñarlo, un solo comando:

```console
$ make capacity MAP=maps/valid/bottleneck.txt ARGS=-q
```

Después de cada línea de turno de `stdout` sale su línea de capacidad en
`stderr`. Sin `ARGS=-q` se ve antes la ventana y el log. Los tests están en
`test/test_capacity_observer.py` (`make test`).

**Qué decirle al evaluador:** la verdad. "La hoja de evaluación es pública
y la leí antes de entregar. Como el flag encajaba con el observador que ya
tenía, lo implementé y lo probé. Te enseño cómo funciona, y si quieres pídeme
otra modificación y la hago ahora mismo." Después recórrele el código con
las tablas de abajo (`CapacityObserver` y los tres cambios en `main.py`) y
ofrécele quitarlo y escribirlo de cero delante de él: el parche
[`ensayo/diff-flag.patch`](../ensayo/diff-flag.patch) lo quita y lo vuelve a
poner.

El flujo dibujado está en
[`diagramas/E.6-live-coding-flow.md`](../diagramas/E.6-live-coding-flow.md).

## La idea en una frase

El simulador ya avisa a un **observador** después de cada turno con los
movimientos y los drones. Basta con escribir un segundo observador que cuente
la ocupación y sumarlo al que ya existe (`ReplayRecorder`) con
`ObserverGroup`. No se toca ni el simulador ni la salida del subject.

## Lo que ya existía (no se escribe nada aquí)

| Pieza | Dónde | Qué da |
|---|---|---|
| `SimulationObserver` | `fly_in/simulation/simulator.py:70` | Un `Protocol`: cualquier clase con `on_turn(turn, moves, drones)` vale, sin heredar |
| `Simulator.run(observer)` | `simulator.py:188` | Llama a `observer.on_turn(turn, moves, self.drones)` tras aplicar cada turno |
| `ObserverGroup(*observers)` | `simulator.py:84` | Reparte cada turno entre varios observadores |
| `Drone.current_zone`, `Drone.in_transit` | `fly_in/simulation/drone.py` | Dónde está; en el aire no ocupa ninguna zona |
| `Move.connection` | `simulator.py:44` | La conexión que usó el movimiento (también en los dos turnos de un tránsito) |
| `Zone.max_drones`, `UNLIMITED` | `fly_in/models/zone.py` | Capacidad; `inf` en `start_hub` y `end_hub` |
| `Connection.max_link_capacity`, `.name` | `fly_in/models/connection.py` | Capacidad y nombre `a-b` tal como viene en el mapa |
| `graph.zones` | `fly_in/models/graph.py` | `Dict[str, Zone]` por nombre |

**Por qué contar movimientos da el uso de las conexiones:** un dron ocupa una
conexión durante el turno en que la cruza. En un tránsito hacia una
`restricted` hay un `Move` en cada uno de los dos turnos (el primero con
`arrives=False`), así que se cuenta las dos veces, que es la lectura estricta
del subject.

## Paso 1 — El observador (4 min)

[`fly_in/simulation/capacity_observer.py`](../../fly_in/simulation/capacity_observer.py):

```python
"""Zone and connection usage, turn by turn (--capacity-info)."""

from collections import Counter
from typing import List, Sequence

from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED
from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move


class CapacityObserver:
    """Observer that records one usage line after each turn.

    It satisfies the `SimulationObserver` Protocol just by having
    `on_turn`. The lines are kept in `lines` (one per turn) and `FlyIn.run`
    writes them to stderr next to the stdout line of each turn.
    """

    def __init__(self, graph: Graph) -> None:
        """No lines yet."""
        self.graph = graph
        self.lines: List[str] = []

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Zones occupied after the turn and connections used during it."""
        zones = Counter(
            drone.current_zone.name for drone in drones
            if not drone.in_transit
        )
        links = Counter(move.connection.name for move in moves)
        capacity = {move.connection.name: move.connection.max_link_capacity
                    for move in moves}
        parts = [
            f"Zone {name}: {count}/"
            f"{self.limit(self.graph.zones[name].max_drones)} drones"
            for name, count in sorted(zones.items())
        ] + [
            f"Connection {name}: {count}/{capacity[name]} capacity used"
            for name, count in sorted(links.items())
        ]
        self.lines.append(f"T{turn} " + ", ".join(parts))

    @staticmethod
    def limit(max_drones: float) -> str:
        """`max_drones` as text: 'inf' on start_hub and end_hub."""
        return "inf" if max_drones == UNLIMITED else str(int(max_drones))
```

Qué decir mientras se escribe:

- Guarda las líneas en vez de imprimirlas: la simulación termina antes de
  enseñarse, y así `run` puede escribir cada una justo debajo de la línea de
  `stdout` de su turno.
- Los drones en el aire no cuentan en ninguna zona (`in_transit`).
- Los entregados siguen en `end_hub` (`current_zone`), así que la meta enseña
  cuántos han llegado.

## Paso 2 — El flag en `main.py` (3 min)

Tres cambios en [`fly_in/main.py`](../../fly_in/main.py):

**Imports** (líneas 23-28, en lugar de la línea de `Simulator`):

```python
from fly_in.simulation.capacity_observer import CapacityObserver
from fly_in.simulation.simulator import (
    ObserverGroup,
    SimulationObserver,
    Simulator,
)
```

**El argumento**, en `FlyIn.build_parser`, justo antes de `return parser`
(líneas 96-99):

```python
        parser.add_argument(
            "--capacity-info", action="store_true",
            help="Print zone and connection usage per turn on stderr"
        )
```

**El observador y la salida**, en `FlyIn.run` (líneas 197-201 y 211-217):

```python
        capacity = CapacityObserver(graph)
        observer: SimulationObserver = recorder
        if args.capacity_info:
            observer = ObserverGroup(recorder, capacity)
        trace = sim.run(observer)
        ...
        for index, line in enumerate(OutputFormatter.format_trace(trace)):
            print(line)
            if args.capacity_info:
                # Flush stdout first so that, on a terminal, each capacity
                # line ends up right below the line of its turn.
                sys.stdout.flush()
                print(capacity.lines[index], file=sys.stderr)
```

La anotación `SimulationObserver` hace falta para mypy: sin ella, la variable
sería de tipo `ReplayRecorder` y no admitiría un `ObserverGroup`.

Y, como comodidad, la regla del `Makefile`:

```make
capacity:
	$(PYTHON) -m fly_in.main $(MAP) --capacity-info $(ARGS)
```

## Paso 3 — Demostrarlo (2 min)

```console
$ make capacity MAP=maps/valid/bottleneck.txt ARGS=-q
.venv/bin/python -m fly_in.main maps/valid/bottleneck.txt --capacity-info -q
D1-narrow
T1 Zone narrow: 1/1 drones, Zone start: 2/inf drones, Connection start-narrow: 1/1 capacity used
D1-goal D2-narrow
T2 Zone goal: 1/inf drones, Zone narrow: 1/1 drones, Zone start: 1/inf drones, Connection narrow-goal: 1/1 capacity used, Connection start-narrow: 1/1 capacity used
D2-goal D3-narrow
T3 Zone goal: 2/inf drones, Zone narrow: 1/1 drones, Connection narrow-goal: 1/1 capacity used, Connection start-narrow: 1/1 capacity used
D3-goal
T4 Zone goal: 3/inf drones, Connection narrow-goal: 1/1 capacity used
```

- Cada línea `T<k>` (en `stderr`) sale debajo de la línea de su turno.
- Sin `-q` se ven primero la ventana y el log, y después la salida.
- `2>/dev/null` deja solo `stdout`: la salida del subject no cambia.

Un tránsito a `restricted` (`maps/valid/restricted_chain.txt`) enseña la
conexión ocupada los dos turnos:

```console
$ make capacity MAP=maps/valid/restricted_chain.txt ARGS=-q
D1-start-r1
T1 Connection start-r1: 1/1 capacity used
D1-r1
T2 Zone r1: 1/1 drones, Connection start-r1: 1/1 capacity used
D1-r1-r2
T3 Connection r1-r2: 1/1 capacity used
...
```

## Paso 4 — Los tests

[`test/test_capacity_observer.py`](../../test/test_capacity_observer.py), 14
tests:

```console
$ .venv/bin/python -m pytest test/test_capacity_observer.py -q
..............                                                   [100%]
14 passed
```

| Test | Qué comprueba |
|---|---|
| `test_one_line_per_turn` | Una línea por turno de la traza |
| `test_bottleneck_by_hand` | La primera y la última línea de `bottleneck.txt`, calculadas a mano |
| `test_restricted_transit_uses_the_connection_twice` | La conexión hacia una `restricted` aparece ocupada en los dos turnos del tránsito |
| `test_usage_never_exceeds_capacity` (×10) | En los 10 mapas oficiales ningún uso supera su capacidad |
| `test_flag_keeps_stdout_and_adds_stderr` | Con el flag, `stdout` es idéntico y `stderr` tiene una línea `T<k>` por turno |

## Si algo falla al reescribirlo

| Síntoma | Causa | Arreglo |
|---|---|---|
| `mypy`: *Incompatible types in assignment* en `observer =` | Falta la anotación | `observer: SimulationObserver = recorder` |
| `KeyError` en `self.graph.zones[name]` | Se usó otra clave que el nombre | `drone.current_zone.name` |
| Las líneas salen por `stdout` | Falta `file=sys.stderr` | `print(capacity.lines[index], file=sys.stderr)` |
| Las líneas de capacidad salen todas juntas, antes o después de `stdout` | Falta el `flush` | `sys.stdout.flush()` antes de cada `print` a `stderr` |
| `IndexError` en `capacity.lines[index]` | Un turno sin movimientos (no pasa con WHCA\*) | Recorrer `trace` y `capacity.lines` a la vez, saltando los turnos vacíos |

**Plan B, sin clase nueva (2 min):** dentro de `FlyIn.run`, después de
`trace = sim.run(recorder)`, recorrer `trace` y contar `move.connection.name`
por turno. Solo da las conexiones (las zonas necesitarían las posiciones de
`recorder.positions`), así que es una salida parcial: úsalo solo si el tiempo
se acaba.

## Ensayar

El parche contiene el flag completo (observador, `main.py`, `Makefile` y
tests). Para quitarlo y escribirlo de cero:

```console
$ git apply -R entrega/ensayo/diff-flag.patch   # sin el flag: 411 tests, mypy --strict limpio
$ # … escribir los pasos 1 y 2 con un cronómetro …
$ git diff                                      # comparar con lo entregado
$ git checkout -- .                             # vuelta al código entregado: 425 tests
```

`git apply -R` borra también `capacity_observer.py` y su test, y
`git checkout -- .` los restaura desde el commit. Sobre una copia sin el
flag, `git apply entrega/ensayo/diff-flag.patch` lo vuelve a poner entero.

## Checklist

- [ ] `capacity_observer.py` creado, con docstrings
- [ ] Tres cambios en `main.py`: imports, argumento, observador y salida
- [ ] `make capacity MAP=maps/valid/bottleneck.txt ARGS=-q` da las 4 líneas `T…` intercaladas
- [ ] `stdout` sigue igual (`2>/dev/null`)
- [ ] `make lint` limpio
- [ ] `make test` pasa
