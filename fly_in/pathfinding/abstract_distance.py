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
        """Precalcula la tabla de distancias al end_hub (una sola vez)."""
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
