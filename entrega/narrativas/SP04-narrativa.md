# SP04 — Dijkstra

> **Estado:** implementado en
> [`fly_in/pathfinding/dijkstra.py`](../../fly_in/pathfinding/dijkstra.py) y
> probado en [`test/test_dijkstra.py`](../../test/test_dijkstra.py) (9 tests).

## El problema

Antes de coordinar a muchos drones hace falta resolver bien el caso de uno
solo: la ruta de menor coste de `start_hub` a `end_hub` respetando las reglas
de movimiento del subject (Cap. VII.3):

- entrar en una zona `normal` o `priority` cuesta 1 turno; en una
  `restricted`, 2;
- las `blocked` no se pueden atravesar;
- ante dos rutas igual de cortas, se prefiere la que pasa por zonas
  `priority`.

## La decisión: el coste se paga al entrar

`Dijkstra.find_path(origin, target)` usa un montículo (`heapq`) de tuplas:

```python
(coste_acumulado, -num_priority, contador, zona)
```

| Elemento | Para qué |
|---|---|
| `coste_acumulado` | Lo que se minimiza: turnos |
| `-num_priority` | Desempate: a igual coste, sale antes la ruta con más zonas `priority` |
| `contador` | Desempate final para que Python nunca compare dos `Zone` (daría `TypeError`) |

Al pasar de `A` a `B` se suma `B.movement_cost()`: el coste es el de **entrar**
en la zona destino. Las zonas no atravesables se saltan, y la ruta se
reconstruye con el diccionario `prev`. Si el objetivo es inalcanzable,
devuelve `None` (no lanza): es una respuesta, no un error.

La clase tiene otros dos métodos:

| Método | Para qué |
|---|---|
| `distances_from(origin, reverse=False)` | Coste mínimo a todas las zonas alcanzables. Con `reverse=True` calcula el coste **hacia** `origin`, y lo usa la heurística de SP05 |
| `path_cost(path)` | Suma el coste de entrar en cada zona de la ruta salvo la primera |

## Dónde se usa

En el programa, solo `distances_from`, a través de `AbstractDistance` (SP05).
`find_path` no forma parte del bucle de simulación: es la **referencia** de un
dron solo. `test_single_drone_matches_dijkstra` comprueba que WHCA\* (SP07),
con un único dron y la tabla vacía, da exactamente el coste de Dijkstra en los
19 mapas.

## Alternativa descartada: BFS

Un recorrido en anchura cuenta saltos, no turnos: trataría una `restricted`
como si costara 1 y no podría desempatar por `priority`.

## Tests

`test_linear_path_is_optimal`, `test_single_drone_minimal_path`,
`test_restricted_chain_adds_two_per_zone`,
`test_blocked_zone_is_never_part_of_the_route`,
`test_priority_wins_ties_regardless_of_connection_order` (con las conexiones en
los dos órdenes), `test_unreachable_target_returns_none_not_raises`,
`test_origin_equals_target_returns_single_zone_zero_cost` y
`test_returned_path_is_consistent_with_graph_connections`.

---

Continúa en [SP05](./SP05-narrativa.md): la heurística.
