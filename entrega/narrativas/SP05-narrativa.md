# SP05 — Heurística abstracta

> **Estado:** implementado en
> [`fly_in/pathfinding/abstract_distance.py`](../../fly_in/pathfinding/abstract_distance.py)
> y probado en
> [`test/test_abstract_distance.py`](../../test/test_abstract_distance.py)
> (14 tests).

## El problema

WHCA\* (SP07) es un A\*: ordena los estados por `f = g + h`, donde `h` estima
cuánto le falta a un dron para llegar. Para que A\* no se equivoque, `h` tiene
que ser **admisible**: no puede sobreestimar nunca. Y cuanto más se acerque al
coste real, menos estados explora.

La distancia en línea recta entre coordenadas no sirve: el mapa no es
euclídeo (las coordenadas solo sirven para dibujar) y no sabe nada de
`restricted`, `blocked` ni callejones sin salida.

## La decisión: el coste real ignorando a los demás drones

`AbstractDistance(graph)` hace **un** Dijkstra desde `end_hub` recorriendo el
grafo hacia atrás (`Dijkstra.distances_from(end_hub, reverse=True)`) y guarda
el coste mínimo de cada zona al objetivo:

```python
class AbstractDistance:
    def __init__(self, graph: Graph) -> None:
        self._dist: Dict[str, int] = self._compute(graph)

    def h(self, zone: Zone) -> int:            # KeyError si es inalcanzable
        return self._dist[zone.name]

    def is_reachable(self, zone: Zone) -> bool:
        return zone.name in self._dist
```

- **Es admisible**: es el coste exacto si el dron estuviera solo, y los demás
  drones solo pueden retrasarlo.
- **Conoce la topología**: una zona `blocked`, aislada o en un callejón sin
  salida no aparece en la tabla. Esa ausencia es la información, y
  `is_reachable` la consulta.
- **Se calcula una vez**, al crear el simulador: `O((Z + C) log Z)`.

## El detalle del recorrido hacia atrás

El coste es de **entrar** en una zona. Al recorrer desde el objetivo hacia
atrás, el paso de `current` a `neighbor` representa ir de `neighbor` a
`current`, así que se suma `current.movement_cost()`, no el del vecino. En una
cadena `start → a → b(restricted) → goal`: `h(goal) = 0`, `h(b) = 1` (entrar
en `goal`) y `h(a) = 3` (entrar en `b` cuesta 2). Es el caso de
`test_restricted_middle_zone_cost_is_paid_by_the_one_entering`.

## Dónde se usa

- `FlyIn.run` (SP03): `is_reachable(start_hub)` detecta un mapa sin solución
  antes de simular.
- `WhcaPathfinder` (SP07): `h(zona)` en cada expansión, y para descartar
  vecinos que no llevan al objetivo.
- Los criterios de orden `nearest_first` y `farthest_first` (SP07): ordenan
  los drones por `h`.

## Tests

`test_h_of_end_hub_is_zero`, `test_linear_all_normal`,
`test_restricted_middle_zone_cost_is_paid_by_the_one_entering`,
`test_blocked_zone_is_absent_and_unreachable`,
`test_isolated_zone_is_absent_and_unreachable` y
`test_consistency_with_dijkstra`, que en los 9 mapas válidos compara `h` de
cada zona con el coste de `Dijkstra.find_path` hasta `end_hub`.

---

Continúa en [SP06 y SP07](./SP06-SP07-narrativa.md): la tabla de reservas y
WHCA\*.
