# SP05 — Guía de corrección y cierre al 100 %

Esta guía parte del estado actual de
[`abstract_distance.py`](../../fly_in/pathfinding/abstract_distance.py) y
[`test_abstract_distance.py`](../../test/test_abstract_distance.py), explica
cada fallo y termina con el código completo que cumple
[SP05](./SP05-heuristica-abstracta.md).

> Los bloques de código de esta guía no se han ejecutado; están escritos contra
> las APIs reales de `Graph`, `Zone`, `Connection`, `MapParser` y `Dijkstra`
> del repo. Ejecuta los tests tras cada paso.

---

## 0. Una corrección a mi revisión anterior

En la revisión dije que la fórmula de coste estaba mal. Era una explicación
confusa. Lo correcto es:

- Al expandir desde `curr` hacia `neighbor`, la fórmula del spec es
  `h(neighbor) = h(curr) + curr.movement_cost()`.
- Tu línea `cost + curr_zone.movement_cost()` **ya usa esa fórmula**. Bien.
- Lo que sobra es el caso especial `1 if curr_zone == end_zone`. Es redundante
  cuando `end_hub` es `normal` o `priority` (su coste ya es 1) y es **incorrecto**
  cuando `end_hub` es `restricted` (entrar cuesta 2, no 1). Además `end_zone` no
  está definido.

Así que el fallo de lógica es solo ese `if`; el resto son errores de
estructura (sangría, `Graph` sin instanciar) y de interfaz.

---

## 1. Inventario de fallos y su arreglo

### `abstract_distance.py`

| # | Fallo | Arreglo |
|---|---|---|
| 1 | `self.graph = Graph` guarda la **clase** | No guardes el grafo; recibe la instancia `graph` y úsala en `_compute` |
| 2 | `end_zone` no existe (`NameError`) | Elimina el `if`; suma siempre `curr.movement_cost()` |
| 3 | Todo tras el `for` está fuera del bucle (sangría) | Mete el cálculo de `new_cost` y el `push` dentro del `for` |
| 4 | Iteras `curr_zone.neighbors` | Usa `graph.neighbors(zone)` + `connection.other_end(zone)`, como SP04 |
| 5 | API `get_distance()` → `Optional` | El spec pide `h(zone)` (lanza `KeyError`) e `is_reachable(zone)` |
| 6 | Atributo `distances` público | Renómbralo `_dist` (privado, `dict[str, int]`) |
| 7 | Dijkstra duplicado | Reutiliza el de SP04 (ver §2) |
| 8 | `Dict`, líneas largas, espacios finales | `dict[str, int]`, ≤ 79 columnas, sin espacios finales |
| 9 | `if not ... is_traversable(): return` deja la tabla vacía sin documentarlo | Es correcto (end bloqueado ⇒ nada alcanzable); déjalo documentado |

### `test_abstract_distance.py`

| # | Fallo | Arreglo |
|---|---|---|
| 1 | `from fly_in.models.Zone` | `fly_in.models.zone` (minúscula) |
| 2 | `unnitest.TestCase` | Usa `pytest` como `test_dijkstra.py` (funciones sueltas) |
| 3 | `graph = Graph` | `Graph()` |
| 4 | `add_zone(z_start, "hub")` duplica `start`; `restricted` nunca se añade | Una `add_zone` por zona con su rol correcto |
| 5 | `add_connection(a, b)` sin capacidad y con nombres inexistentes | `add_connection("start", "a", 1)` |
| 6 | `abd_dist` | Errata de nombre de variable |
| 7 | Solo 1 de los 7 tests | Escribir los 7 (§4) |

---

## 2. Una sutileza que el spec no cuenta: reutilizar Dijkstra requiere `reverse`

El Paso 5 del spec dice que `AbstractDistance` sería "un envoltorio de ocho
líneas" sobre un Dijkstra que devuelva todas las distancias. Casi, pero con un
matiz que hay que entender:

- El Dijkstra normal desde `origin` calcula `coste(origin → X)`, y el coste de
  cada salto es **entrar** en el destino: `neighbor.movement_cost()`.
- Nosotros queremos `h(X) = coste(X → end)`, es decir, el coste **hacia**
  `end`. Como los costes son de entrada, el grafo es simétrico en aristas pero
  **no** en pesos: `coste(end → X)` ≠ `coste(X → end)` en cuanto hay una zona
  `restricted` en medio.

Por eso el método compartido necesita un parámetro `reverse`:

| Modo | Salto `curr → neighbor` suma |
|---|---|
| `reverse=False` (SP04) | `neighbor.movement_cost()` |
| `reverse=True` (SP05) | `curr.movement_cost()` |

Comprobación con `start → a → b(restricted) → goal`, partiendo de `goal` en
modo inverso:

- `h(goal) = 0`
- `h(b) = 0 + goal.cost = 1`
- `h(a) = 1 + b.cost = 3`
- `h(start) = 3 + a.cost = 4`

Coincide con la tabla del spec (`h(b) == 1`, `h(start) == 4`).

---

## 3. Código final

### 3.1 `dijkstra.py`: añadir `distances_from`

Añade este método a la clase `Dijkstra`
([dijkstra.py](../../fly_in/pathfinding/dijkstra.py)), sin tocar `find_path`:

```python
    def distances_from(
        self, origin: Zone, reverse: bool = False
    ) -> Dict[str, int]:
        """
        Coste mínimo de `origin` a cada zona alcanzable, por nombre.

        reverse=False: coste de ir de origin a X (suma el coste de entrar
        en cada zona destino).
        reverse=True: coste de ir de X a origin. Como el coste es de
        *entrada*, al expandir de `current` a `neighbor` se suma el de
        `current`. Las zonas blocked nunca se visitan ni aparecen.
        """
        if not origin.is_traversable():
            return {}

        dist: Dict[str, int] = {origin.name: 0}
        counter = 0
        heap: List[Tuple[int, int, Zone]] = [(0, counter, origin)]

        while heap:
            cost, _, current = heapq.heappop(heap)
            if cost > dist[current.name]:
                continue

            for connection in self.graph.neighbors(current):
                neighbor = connection.other_end(current)
                if not neighbor.is_traversable():
                    continue

                step = (
                    current.movement_cost()
                    if reverse
                    else neighbor.movement_cost()
                )
                new_cost = cost + step
                if (
                    neighbor.name not in dist
                    or new_cost < dist[neighbor.name]
                ):
                    dist[neighbor.name] = new_cost
                    counter += 1
                    heapq.heappush(heap, (new_cost, counter, neighbor))
        return dist
```

Notas:

- El `counter` va antes que `Zone` en la tupla: nunca se comparan dos `Zone`
  (no son ordenables) porque `counter` es único.
- El spec sugiere hacer que `find_path()` también use este método. **No lo
  hagas**: `find_path` lleva un desempate por zonas `priority` y reconstruye la
  ruta con `prev`, cosas que aquí no hacen falta. Anótalo en "Decisiones a
  anotar": se comparte el *criterio de coste*, no el bucle. La duplicación es
  mínima y `test_consistency` (abajo) vigila que no diverjan.

### 3.2 `abstract_distance.py`, completo

```python
"""
Heurística abstracta: coste mínimo real de cada zona hasta end_hub,
ignorando a los demás drones.
"""

from typing import Dict

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.pathfinding.dijkstra import Dijkstra


class AbstractDistance:
    """Coste mínimo real de cada zona al objetivo, ignorando otros drones.

    Se calcula una sola vez al arrancar, con un Dijkstra desde end_hub
    recorriendo el grafo hacia atrás. Es admisible: nunca sobreestima, porque
    los demás drones solo pueden hacer que un dron tarde más, nunca menos.

    Las zonas inalcanzables (blocked o desconectadas) NO están en la tabla:
    esa ausencia es la información. Se consultan con is_reachable().
    """

    def __init__(self, graph: Graph) -> None:
        self._dist: Dict[str, int] = self._compute(graph)

    def _compute(self, graph: Graph) -> Dict[str, int]:
        """Dijkstra desde end_hub. Las zonas 'blocked' no se expanden."""
        if graph.end_hub is None:
            return {}
        return Dijkstra(graph).distances_from(graph.end_hub, reverse=True)

    def h(self, zone: Zone) -> int:
        """Heurística admisible: turnos mínimos de `zone` al objetivo.

        Raises:
            KeyError: si la zona es inalcanzable desde el objetivo.
        """
        return self._dist[zone.name]

    def is_reachable(self, zone: Zone) -> bool:
        """True si existe alguna ruta de `zone` al objetivo."""
        return zone.name in self._dist
```

Detalles que conviene entender:

- Se indexa por `zone.name`, no por el objeto `Zone`, porque `Zone` no define
  `__hash__`/`__eq__` (hash por identidad) y un test que cree una `Zone("goal")`
  nueva fallaría de forma desconcertante.
- Si `end_hub` es `blocked`, `distances_from` devuelve `{}` y todo es
  inalcanzable. Es coherente con SP04, cuyo `find_path` devuelve `None` si el
  destino no es transitable.
- No se rellena con `float("inf")`: rompería `mypy --strict` y propagaría
  infinitos por `g + h`.

---

## 4. `test_abstract_distance.py`, completo (los 7 tests)

Sigue el estilo de [test_dijkstra.py](../../test/test_dijkstra.py) (pytest,
`MAPS_DIR`, `load_graph`, `path_cost`). Puedes copiar esos helpers tal cual o,
mejor, moverlos a un `test/helpers.py` compartido.

```python
from pathlib import Path
from typing import List

import pytest

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.dijkstra import Dijkstra

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps" / "valid"


def load_graph(filename: str) -> Graph:
    _, graph = MapParser.parse((MAPS_DIR / filename).read_text())
    return graph


def path_cost(path: List[Zone]) -> int:
    return sum(zone.movement_cost() for zone in path[1:])


def linear_graph(b_type: str = "normal") -> Graph:
    """start -> a -> b -> goal; `b_type` cambia el tipo de la zona b."""
    graph = Graph()
    graph.add_zone(Zone("start", 0, 0), "start_hub")
    graph.add_zone(Zone("a", 1, 0), "hub")
    graph.add_zone(Zone("b", 2, 0, zone_type=b_type), "hub")
    graph.add_zone(Zone("goal", 3, 0), "end_hub")
    graph.add_connection("start", "a", 1)
    graph.add_connection("a", "b", 1)
    graph.add_connection("b", "goal", 1)
    return graph


# --- 1. h(end_hub) == 0 -------------------------------------------------

def test_h_of_end_hub_is_zero() -> None:
    graph = linear_graph()
    assert graph.end_hub is not None
    assert AbstractDistance(graph).h(graph.end_hub) == 0


# --- 2. Lineal todo normal: h(start) == 3 -------------------------------

def test_linear_all_normal() -> None:
    graph = linear_graph()
    dist = AbstractDistance(graph)
    assert dist.h(graph.get_zone("start")) == 3
    assert dist.h(graph.get_zone("a")) == 2
    assert dist.h(graph.get_zone("b")) == 1


# --- 3. b restricted: h(start) == 4 y h(b) == 1  (el test clave) --------

def test_restricted_middle_zone_cost_is_paid_by_the_one_entering() -> None:
    graph = linear_graph(b_type="restricted")
    dist = AbstractDistance(graph)
    assert dist.h(graph.get_zone("b")) == 1      # NO 2: b la paga quien entra
    assert dist.h(graph.get_zone("a")) == 3
    assert dist.h(graph.get_zone("start")) == 4


# --- 4 y 6. blocked: fuera del dict e is_reachable False ----------------

def test_blocked_zone_is_absent_and_unreachable() -> None:
    graph = linear_graph(b_type="blocked")
    dist = AbstractDistance(graph)
    blocked = graph.get_zone("b")
    assert "b" not in dist._dist
    assert not dist.is_reachable(blocked)
    with pytest.raises(KeyError):
        dist.h(blocked)
    # y corta el camino: start y a quedan aisladas del objetivo
    assert not dist.is_reachable(graph.get_zone("a"))
    assert not dist.is_reachable(graph.get_zone("start"))


# --- 5 y 6. zona aislada: fuera del dict e is_reachable False -----------

def test_isolated_zone_is_absent_and_unreachable() -> None:
    graph = linear_graph()
    graph.add_zone(Zone("island", 9, 9), "hub")     # sin conexiones
    dist = AbstractDistance(graph)
    island = graph.get_zone("island")
    assert "island" not in dist._dist
    assert not dist.is_reachable(island)
    with pytest.raises(KeyError):
        dist.h(island)


# --- 7. Coherencia con SP04, zona por zona, en todos los mapas ----------

@pytest.mark.parametrize(
    "map_file", sorted(p.name for p in MAPS_DIR.glob("*.txt"))
)
def test_consistency_with_dijkstra(map_file: str) -> None:
    graph = load_graph(map_file)
    assert graph.end_hub is not None
    dijkstra = Dijkstra(graph)
    dist = AbstractDistance(graph)

    for zone in graph.zones.values():
        path = dijkstra.find_path(zone, graph.end_hub)
        assert dist.is_reachable(zone) == (path is not None), zone.name
        if path is not None:
            assert dist.h(zone) == path_cost(path), zone.name
```

Por qué `test_consistency_with_dijkstra` es el definitivo: una implementación
va hacia delante (SP04) y la otra hacia atrás (SP05). Si coinciden en cada
zona de cada mapa, es muy improbable que ambas tengan el mismo bug.

Mapas que lo ejercitan bien (ya los tienes sin seguimiento en git):
`blocked_detour.txt` (desvío por bloqueo), `restricted_chain.txt` (costes 2
encadenados) y `priority_tie.txt` (desempate de SP04; aquí `h` solo mira el
coste, no la prioridad).

---

## 5. Orden de trabajo recomendado

1. Añade `distances_from` a `Dijkstra`. Ejecuta `pytest test/test_dijkstra.py`:
   debe seguir verde (no has tocado `find_path`).
2. Reescribe `abstract_distance.py` (§3.2).
3. Reescribe `test_abstract_distance.py` (§4). Ejecuta
   `pytest test/test_abstract_distance.py -v`; deben salir 6 tests fijos más
   uno por cada mapa de `maps/valid`.
4. Si el test 3 falla con `h(b) == 2`, estás sumando el coste equivocado
   (`neighbor` en vez de `current` en modo `reverse`).
5. `make lint-strict` (flake8 + `mypy --strict`). Vigila:
   - líneas > 79 columnas (`.flake8` del repo),
   - `dist._dist` en los tests: acceso a atributo privado, mypy no se queja,
     flake8 tampoco; si no te gusta, sustitúyelo por
     `not dist.is_reachable(...)`.
6. `make test` completo para comprobar que no rompiste el parser ni SP04.

## 6. Criterio de salida (checklist)

- [ ] `pytest` verde, incluido el de coherencia en **todos** los mapas
- [ ] `make lint-strict` sin errores
- [ ] Sabes explicar sin mirar por qué en modo inverso se suma el coste de la
      zona que **expandes** (`current`) y no el del vecino: porque el dron irá
      de `neighbor` a `current` y paga por **entrar en `current`**; el coste de
      `neighbor` ya lo pagó al llegar a él
- [ ] Decisiones anotadas (abajo)

## 7. Decisiones a anotar

- **Inalcanzable = ausencia de clave.** `h()` lanza `KeyError`; se consulta
  antes con `is_reachable()`. Sin `inf` ni centinela.
- **No se recalcula nunca:** el grafo es inmutable y los `blocked` no cambian.
- **Reutilización parcial de Dijkstra:** `distances_from(reverse=...)` comparte
  el criterio de coste, pero `find_path` conserva su bucle propio por el
  desempate de prioridad y la reconstrucción de ruta.
- **Indexado por nombre**, no por objeto `Zone`.
