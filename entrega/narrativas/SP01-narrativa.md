# SP01 — Modelo de dominio

> **Estado:** implementado en [`fly_in/models/`](../../fly_in/models/) y
> probado dentro de [`test/test_parser.py`](../../test/test_parser.py) (los
> tests del grafo se ejercitan a través del parser).

## El problema

El subject habla de zonas, conexiones y capacidades (`max_drones`,
`max_link_capacity`), pero no dice **dónde vive la ocupación**: ¿cada zona
lleva una lista de los drones que tiene, o eso va fuera?

| Opción | Resultado |
|---|---|
| Dentro: `zone.drones` | El grafo se llena de estado que cambia cada turno, y el pathfinding necesita preguntar *"¿estará libre en el turno 17?"*, algo que una zona no sabe |
| Fuera: en `ReservationTable` (SP06) | El grafo no cambia tras el parseo y la tabla es la única que sabe del tiempo |

Se eligió la segunda.

## La decisión: capacidad en el modelo, ocupación fuera

**`Zone` sabe cuántos caben, no cuántos hay**:

```python
class Zone:
    def __init__(self, name: str, x: int, y: int,
                 zone_type: ZoneType = ZoneType.NORMAL,
                 max_drones: float = 1,
                 color: Optional[str] = None) -> None: ...

    def is_traversable(self) -> bool: ...   # False solo en 'blocked'
    def movement_cost(self) -> int: ...     # 1, 1 o 2; ValueError en 'blocked'
```

- `ZoneType` tiene los cuatro tipos del subject: `NORMAL`, `RESTRICTED`,
  `PRIORITY`, `BLOCKED`. Su valor es el texto de `zone=`.
- `MOVEMENT_COST` da el coste de **entrar**: 1 en `normal` y `priority`, 2 en
  `restricted`. `blocked` no está: no se puede entrar.
- `UNLIMITED = float("inf")` es la capacidad de `start_hub` y `end_hub`. Al
  ser infinito, `ocupación < max_drones` es cierto sin casos especiales.

**`Connection`** guarda sus dos zonas y `max_link_capacity`, y ofrece
`other_end(zone)` y `name` (`"a-b"`, tal como viene en el mapa).

**`Graph`** aplica las reglas que dependen de todo el archivo:

| Método | Qué hace |
|---|---|
| `add_zone(zone, role)` | Rol `hub`, `start_hub` o `end_hub`; nombres únicos; como mucho un start y un end |
| `add_connection(origin, destination, max_link_capacity)` | Solo entre zonas ya definidas; sin duplicados en ningún sentido (clave `frozenset`) |
| `neighbors(zone)` | Las conexiones de una zona en O(1), en el orden del archivo (devuelve una copia) |
| `connection_between(a, b)` | La conexión entre dos zonas en O(1), en cualquier sentido |
| `get_zone(name)` | Busca por nombre o falla con un mensaje claro |

Los índices `_adjacency` y `_by_pair` existen porque el pathfinding llama a
`neighbors` en cada expansión: recorrer todas las conexiones cada vez lo haría
O(conexiones) por paso.

## Alternativa descartada: el rol dentro de la zona

`zone.is_start = True` haría que la zona supiera algo que es del mapa. El grafo
guarda `start_hub` y `end_hub` y se compara por identidad
(`zone is graph.end_hub`).

## Los errores

[`fly_in/models/errors.py`](../../fly_in/models/errors.py) define la jerarquía:

```
MapError
├── MapParseError        una línea concreta: número, contenido y causa
└── MapValidationError   el archivo entero: vacío, sin start_hub, sin ruta…
```

`Graph` lanza `ValueError`; el parser lo convierte en `MapParseError` con la
línea (SP02).

## Tests

En `test/test_parser.py`: `test_zone_defaults`,
`test_reversed_connection_is_a_duplicate`,
`test_connection_must_follow_both_zone_definitions`,
`test_neighbors_in_definition_order`, `test_neighbors_returns_a_copy`,
`test_connection_between_works_in_both_directions`,
`test_connection_between_unconnected_zones_raises`.

---

Continúa en [SP02](./SP02-narrativa.md): el parser.
