# Guía de live coding: `--capacity-info` en 10 minutos

La hoja de evaluación pide: *"add a `--capacity-info` flag that displays
capacity information during simulation, such as `Zone X: Y/Z drones,
Connection A-B: Y/Z capacity used` for each turn"*. El flag **no está** en el
código entregado: se programa delante del evaluador. Esta guía es el guion,
escrito contra el código actual y probado aplicando el parche de
[`ensayo/diff-flag.patch`](./ensayo/diff-flag.patch).

## La idea en una frase

El simulador ya avisa a un **observador** después de cada turno con los
movimientos y los drones. Basta con escribir un segundo observador que cuente
la ocupación y sumarlo al que ya existe (`ReplayRecorder`) con
`ObserverGroup`. No se toca ni el simulador ni la salida del subject.

## Lo que ya existe (no se escribe nada aquí)

| Pieza | Dónde | Qué da |
|---|---|---|
| `SimulationObserver` | `fly_in/simulation/simulator.py:69` | Un `Protocol`: cualquier clase con `on_turn(turn, moves, drones)` vale, sin heredar |
| `Simulator.run(observer)` | `simulator.py:187` | Llama a `observer.on_turn(turn, moves, self.drones)` tras aplicar cada turno |
| `ObserverGroup(*observers)` | `simulator.py:83` | Reparte cada turno entre varios observadores |
| `Drone.current_zone`, `Drone.in_transit` | `fly_in/simulation/drone.py` | Dónde está; en el aire no ocupa ninguna zona |
| `Move.connection` | `simulator.py:43` | La conexión que usó el movimiento (también en los dos turnos de un tránsito) |
| `Zone.max_drones`, `UNLIMITED` | `fly_in/models/zone.py` | Capacidad; `inf` en `start_hub` y `end_hub` |
| `Connection.max_link_capacity`, `.name` | `fly_in/models/connection.py` | Capacidad y nombre `a-b` tal como viene en el mapa |
| `graph.zones` | `fly_in/models/graph.py` | `Dict[str, Zone]` por nombre |

**Por qué contar movimientos da el uso de las conexiones:** un dron ocupa una
conexión durante el turno en que la cruza. En un tránsito hacia una
`restricted` hay un `Move` en cada uno de los dos turnos (el primero con
`arrives=False`), así que se cuenta las dos veces, que es la lectura estricta
del subject.

## Paso 1 — El observador (4 min)

Crear `fly_in/simulation/capacity_observer.py`:

```python
"""Ocupación de zonas y conexiones turno a turno (--capacity-info)."""

from collections import Counter
from typing import Sequence, TextIO

from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED
from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move


class CapacityObserver:
    """Observador que escribe una línea de ocupación tras cada turno.

    Cumple el Protocol `SimulationObserver` solo con tener `on_turn`.
    """

    def __init__(self, graph: Graph, stream: TextIO) -> None:
        """Escribe en `stream`: stderr, porque stdout es del subject."""
        self.graph = graph
        self.stream = stream

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Zonas ocupadas tras el turno y conexiones usadas durante él."""
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
        print(f"T{turn} " + ", ".join(parts), file=self.stream)

    @staticmethod
    def limit(max_drones: float) -> str:
        """`max_drones` como texto: 'inf' en start_hub y end_hub."""
        return "inf" if max_drones == UNLIMITED else str(int(max_drones))
```

Qué decir mientras se escribe:

- Va a `stderr` porque `stdout` solo puede llevar las líneas del subject.
- Los drones en el aire no cuentan en ninguna zona (`in_transit`).
- Los entregados siguen en `end_hub` (`current_zone`), así que la meta enseña
  cuántos han llegado.

## Paso 2 — El flag en `main.py` (3 min)

Tres cambios en [`fly_in/main.py`](../fly_in/main.py):

**Imports** (línea 23, sustituye la línea de `Simulator`):

```python
from fly_in.simulation.capacity_observer import CapacityObserver
from fly_in.simulation.simulator import (
    ObserverGroup,
    SimulationObserver,
    Simulator,
)
```

**El argumento**, en `FlyIn.build_parser`, justo antes de `return parser`
(línea 91):

```python
        parser.add_argument(
            "--capacity-info", action="store_true",
            help="Print zone and connection usage per turn on stderr"
        )
```

**El observador**, en `FlyIn.run`, en lugar de `trace = sim.run(recorder)`
(línea 188):

```python
        observer: SimulationObserver = recorder
        if args.capacity_info:
            observer = ObserverGroup(
                recorder, CapacityObserver(graph, sys.stderr)
            )
        trace = sim.run(observer)
```

La anotación `SimulationObserver` hace falta para mypy: sin ella, la variable
sería de tipo `ReplayRecorder` y no admitiría un `ObserverGroup`.

## Paso 3 — Demostrarlo (2 min)

```console
$ python -m fly_in.main maps/valid/bottleneck.txt --capacity-info -q
T1 Zone narrow: 1/1 drones, Zone start: 2/inf drones, Connection start-narrow: 1/1 capacity used
T2 Zone goal: 1/inf drones, Zone narrow: 1/1 drones, Zone start: 1/inf drones, Connection narrow-goal: 1/1 capacity used, Connection start-narrow: 1/1 capacity used
T3 Zone goal: 2/inf drones, Zone narrow: 1/1 drones, Connection narrow-goal: 1/1 capacity used, Connection start-narrow: 1/1 capacity used
T4 Zone goal: 3/inf drones, Connection narrow-goal: 1/1 capacity used
D1-narrow
D1-goal D2-narrow
D2-goal D3-narrow
D3-goal
```

- Con `-q` se ven las líneas de capacidad y después la salida del subject.
- Sin `-q`, las líneas de capacidad salen primero (el programa simula entero
  y luego enseña la animación) y después se abre la ventana o el log.
- `2>/dev/null` deja solo `stdout`: la salida del subject no cambia.

Un tránsito a `restricted` (`maps/valid/restricted_chain.txt`) enseña la
conexión ocupada los dos turnos:

```console
$ python -m fly_in.main maps/valid/restricted_chain.txt --capacity-info -q 2>&1 | head -3
T1 Connection start-r1: 1/1 capacity used
T2 Zone r1: 1/1 drones, Connection start-r1: 1/1 capacity used
T3 Connection r1-r2: 1/1 capacity used
```

## Paso 4 — El test (opcional, 1 min)

Copiar [`ensayo/test_capacity_observer.py`](./ensayo/test_capacity_observer.py)
a `test/` y ejecutar:

```console
$ python -m pytest test/test_capacity_observer.py -q
............                                                     [100%]
12 passed
```

Comprueba una línea por turno, el ejemplo de `bottleneck.txt` a mano y que en
los 10 mapas oficiales ningún uso supera su capacidad.

## Si algo falla

| Síntoma | Causa | Arreglo |
|---|---|---|
| `mypy`: *Incompatible types in assignment* en `observer =` | Falta la anotación | `observer: SimulationObserver = recorder` |
| `KeyError` en `self.graph.zones[name]` | Se usó otra clave que el nombre | `drone.current_zone.name` |
| Las líneas salen por `stdout` | Falta `file=self.stream` o se pasó `sys.stdout` | `CapacityObserver(graph, sys.stderr)` |
| `NameError: sys` | — | `sys` ya está importado en `main.py`; revisa la ortografía |

**Plan B, sin clase nueva (2 min):** dentro de `FlyIn.run`, después de
`trace = sim.run(recorder)`, recorrer `trace` y contar `move.connection.name`
por turno. Solo da las conexiones (las zonas necesitarían las posiciones de
`recorder.positions`), así que es una salida parcial: úsalo solo si el tiempo
se acaba.

## Ensayar

```console
$ git apply entrega/ensayo/diff-flag.patch      # la solución completa
$ make test && make lint-strict                 # 423 tests, mypy --strict limpio
$ git apply -R entrega/ensayo/diff-flag.patch   # vuelta al código entregado (411 tests)
```

Para ensayar de verdad, no apliques el parche: escribe los pasos 1 y 2 con un
cronómetro y compara al final con `git diff` contra el parche.

## Checklist

- [ ] `capacity_observer.py` creado, con docstrings
- [ ] Tres cambios en `main.py`: imports, argumento y observador
- [ ] `python -m fly_in.main maps/valid/bottleneck.txt --capacity-info -q` da las 4 líneas `T…`
- [ ] `stdout` sigue igual (`2>/dev/null`)
- [ ] `make lint` limpio
- [ ] (opcional) `test_capacity_observer.py` pasa
