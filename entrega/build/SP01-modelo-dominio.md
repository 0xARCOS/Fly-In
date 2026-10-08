# SP01 — Modelo de dominio ✅

> **Estado:** hecho. `Zone`, `Connection` y `Graph` existen y funcionan. Quedan
> dos mejoras anotadas al final, que se cierran en SP04.

**Objetivo:** decidir las clases **antes** de escribir lógica. Esto es lo que te
van a pedir justificar en la peer-review, y es lo que determina si el resto del
proyecto es fácil o doloroso.

**Prerequisitos:** [SP00](./SP00-setup.md) verde.

**Criterio de salida:** puedes construir un grafo a mano en el intérprete,
consultar los vecinos de una zona y explicar en voz alta, sin mirar el código,
qué hace cada clase y por qué existe.

---

## La pregunta que decide todo el diseño

*¿Dónde vive el estado de ocupación?*

Hay dos respuestas posibles y solo una funciona:

| Opción | Consecuencia |
|---|---|
| Dentro de `Zone` (`self.drones: list[Drone]`) | El `Graph` se ensucia con el estado de la simulación. Peor: el pathfinding necesita preguntar *"¿estará libre en el turno 17?"*, y una zona no sabe responder a eso |
| Fuera, en `ReservationTable` / `Simulator` | ✅ El `Graph` es inmutable y reutilizable entre tests y replanificaciones. El futuro lo conoce quien tiene que conocerlo |

**Elegimos la segunda.** `Zone` sabe *cuántos drones caben* (`max_drones`), pero
nunca *cuántos hay*. Esa distinción — capacidad vs. ocupación — es la columna
vertebral de la arquitectura.

---

## Paso 1 — `Zone`

`fly_in/models/zone.py`

```python
class ZoneType(Enum):
    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


class Zone:
    """Un nodo del mapa: un hub normal, el start_hub o el end_hub."""

    def __init__(self, name: str, x: int, y: int,
                 zone_type: ZoneType = ZoneType.NORMAL,
                 max_drones: float = 1,
                 color: Optional[str] = None) -> None: ...
```

Atributos: `name`, `x`, `y`, `zone_type`, `max_drones`, `color`.

⚠️ **No lo des por sentado — `Zone` no sabe si es start o end**
No hay `is_start`/`is_end` en `Zone`. El rol de una zona lo conoce el `Graph`
(`graph.start_hub is zone`). Es correcto: el rol es una propiedad **del mapa**,
no de la zona. Una misma zona no podría ser el start de un mapa y un hub normal
de otro si llevara la bandera dentro.

## Paso 2 — `Connection`

`fly_in/models/connection.py`

```python
class Connection:
    def __init__(self, zone_a: Zone, zone_b: Zone,
                 max_link_capacity: int = 1) -> None: ...

    def other_end(self, zone: Zone) -> Zone:
        """Devuelve el extremo opuesto a `zone` en esta conexión."""

    @property
    def name(self) -> str:
        """Nombre de la conexión tal como aparece en la salida: 'a-b'."""
```

Dos decisiones que merecen explicación:

**Guarda objetos `Zone`, no nombres.** Un `dict[str, list[str]]` de adyacencia
sería más corto, pero entonces cada vez que necesitaras el coste o la capacidad
de un vecino tendrías que volver a buscarlo en el grafo por nombre. Guardando
las zonas, `other_end()` te da directamente el objeto con todo lo que necesitas.

**`other_end()` compara con `is`, no con `==`.** Compara identidad de objeto, no
igualdad de contenido. Es correcto y deliberado: el `Graph` garantiza que solo
existe **una** instancia de `Zone` por nombre, así que la identidad es el
criterio más estricto y más rápido. Si algún día dos objetos `Zone` distintos
tuvieran el mismo nombre, esto lo detectaría; `==` lo escondería.

⚠️ **No lo des por sentado — `name` es una propiedad, no un atributo**
`Connection.name` se calcula al vuelo como `f"{zone_a.name}-{zone_b.name}"`. No
se guarda. Así nunca puede quedar desincronizado con los extremos reales, y la
salida `D1-hub-roof1` siempre refleja la conexión de verdad.

## Paso 3 — `Graph` y sus invariantes

`fly_in/models/graph.py`

```python
class Graph:
    def __init__(self) -> None:
        self.zones: Dict[str, Zone] = {}
        self.start_hub: Optional[Zone] = None
        self.end_hub: Optional[Zone] = None
        self.connections: List[Connection] = []

    def add_zone(self, zone: Zone, role: str) -> None: ...
    def add_connection(self, origin: str, destination: str,
                       max_link_capacity: int) -> None: ...
    def get_zone(self, name: str) -> Zone: ...
    def neighbors(self, zone: Zone) -> List[Connection]: ...      # O(1)
    def connection_between(self, a: Zone, b: Zone) -> Connection: ...  # O(1)
```

Internamente guarda dos índices que se rellenan en `add_connection`:
`_adjacency: dict[nombre_zona, list[Connection]]` y
`_by_pair: dict[frozenset[nombre, nombre], Connection]`. El pathfinding llama a
`neighbors()` en cada expansión; recorrer la lista entera de conexiones cada vez
convertiría cada búsqueda en `O(V·E)`.

```python
```

**El `Graph` es el guardián de las reglas que dependen del archivo entero**, no
de una línea suelta:

| Invariante | Dónde se comprueba |
|---|---|
| Nombres de zona únicos | `add_zone` |
| Un solo `start_hub`, un solo `end_hub` | `add_zone` |
| Las conexiones referencian zonas ya definidas | `add_connection` |
| Sin conexiones duplicadas (`a-b` == `b-a`) | `add_connection`, con la clave `frozenset({a, b})` |

⚠️ **No lo des por sentado — por qué estas reglas no van en el parser**
El parser mira **una línea cada vez**. No puede saber si un nombre está
duplicado sin acordarse de todas las líneas anteriores — y si le añades esa
memoria, has reescrito el `Graph` dentro del parser. Poniendo los invariantes en
`Graph`, el parser solo traduce texto a llamadas, y **el grafo es imposible de
construir en estado inválido**, venga de donde venga (parser, test, intérprete).

**Cómo se detecta el duplicado `a-b` == `b-a`:** con un `frozenset` como clave,
porque un conjunto no tiene orden (y `frozenset`, a diferencia de `set`, se
puede usar como clave de diccionario).

```python
pair = frozenset((origin, destination))
if pair in self._by_pair:
    raise ValueError(...)
```

**`neighbors()` devuelve `Connection`, no `Zone`.** Deliberado: quien recorre el
grafo necesita saber **por qué arista** pasa, para consultar su
`max_link_capacity` y para poder nombrarla en la salida. Con el vecino a secas
perderías esa información y tendrías que volver a buscar la conexión.

🔍 **Verifica** — abre el intérprete y construye un grafo a mano:

```console
$ .venv/bin/python
>>> from fly_in.models.graph import Graph
>>> from fly_in.models.zone import Zone
>>> g = Graph()
>>> g.add_zone(Zone("start", 0, 0), "start_hub")
>>> g.add_zone(Zone("goal", 1, 0), "end_hub")
>>> g.add_connection("start", "goal", 1)
>>> g.neighbors(g.get_zone("start"))
[Connection('start'-'goal', max_link_capacity=1)]
>>> g.add_zone(Zone("start", 5, 5), "hub")     # debe fallar
ValueError: Zone name 'start' is already defined
```

Si esto funciona sin tocar el parser, la separación de capas es correcta.

---

## Criterio de salida ✅

- [x] Se puede construir un grafo válido sin pasar por el parser
- [x] Los cuatro invariantes se disparan con un `ValueError` explicativo
- [x] `neighbors()` encuentra conexiones en ambos sentidos
- [x] `make lint-strict` pasa

## Decisiones tomadas

| Decisión | Alternativa | Por qué |
|---|---|---|
| Ocupación fuera de `Zone` | `Zone.drones: list[Drone]` | El pathfinding pregunta por el futuro; `Graph` inmutable y reutilizable |
| `Connection` guarda objetos `Zone` | `dict[str, list[str]]` de adyacencia | Acceso directo a coste y capacidad del vecino, sin re-lookup |
| Invariantes en `Graph`, no en el parser | Validación en `MapParser` | El grafo es inconstruible en estado inválido, venga de donde venga |
| `neighbors()` devuelve conexiones | Devolver zonas vecinas | Hace falta la arista para `max_link_capacity` y para nombrarla en la salida |
| `zone_type` como `Enum ZoneType` | `str` validado contra un `set` | mypy caza erratas (`ZoneType.RESTRICTD`) y comparaciones con texto suelto (`zone_type == "priority"`, siempre falsa) en tiempo de `make lint-strict`, no en ejecución |

## Deuda conocida

**Resuelto: `zone_type` es un `Enum`.** `ZoneType` usa `Enum` y no
`StrEnum` porque `StrEnum` es de Python 3.11 y el proyecto admite 3.10. El
parser convierte el texto con `ZoneType("restricted")`; compara siempre con
`is` (`zone.zone_type is ZoneType.PRIORITY`).

**Resuelto:** `movement_cost()` e `is_traversable()` ya existen en `Zone`
(añadidos en [SP04](./SP04-dijkstra.md)). El antiguo atributo `Zone.neighbors`
(un `set` que nadie leía y con orden no determinista) se eliminó: los vecinos
se consultan siempre con `graph.neighbors(zone)`.

**Capacidad ilimitada.** `max_drones` es `float` porque `start_hub`/`end_hub`
reciben `UNLIMITED = float("inf")` (`zone.py`). Así `ocupación < max_drones` es
cierto para ellas sin ningún `if` especial en SP06/SP07/SP08.
