"""
    1 - Fila de prioridad con tupla de 4 elementos:
        (coste_acumulado, -num_priority, contador_único, nodo_actual)
        .. coste_acumulado: Menor número de turnos acumulados.
        .. -num_priority: Ante empate de coste, favorece la ruta que pasa
           por más zonas de tipo priority.
        .. contador_unico: Previene errores de comparación de tipos entre
           objetos Zone en Python (TypeError).
        .. nodo_actual: La zona que se explora.

    2 - Costo en la zona de destino: Al moverse de la zona A a la zona B,
        el coste añadido es B.movement_cost
    3 - Ignorar Bloqueados: Si neighbor.is_traversable() es False, se omite
    4 - Reconstrucción del camino: Devuelve la lista [origin, ..., target]
        o None si la meta es inalcanzable.
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple
from fly_in.models.zone import Zone, ZoneType
from fly_in.models.graph import Graph


class Dijkstra:
    """
    Calcula la ruta estática de coste mínimo para un solo dron.
    """
    def __init__(self, graph: Graph) -> None:
        """Guarda el grafo sobre el que se harán las búsquedas."""
        self.graph = graph

    def find_path(self, origin: Zone, target: Zone) -> Optional[List[Zone]]:
        """
            Busca la ruta de coste mínimo entre origin y target.

            return:
                Lista de zonas desde origin hasta target (ambos incluidos),
                o None si el objetivo es inalcanzable.
        """
        if not origin.is_traversable() or not target.is_traversable():
            return None

        # Si origen y destino son el mismo nodo
        if origin.name == target.name:
            return [origin]

        counter = 0
        # Tuple: (cost, -priority_count, counter, zone)
        start_prio = 1 if origin.zone_type is ZoneType.PRIORITY else 0
        heap: List[Tuple[int, int, int, Zone]] = [
            (0, -start_prio, counter, origin)
        ]

        # dist[zone_name] = (min_cost, -max_priority_count)
        dist: Dict[str, Tuple[int, int]] = {origin.name: (0, -start_prio)}
        prev: Dict[str, Zone] = {}
        visited: Set[str] = set()

        while heap:
            cost, neg_prio, _, current = heapq.heappop(heap)

            if current.name in visited:
                continue
            visited.add(current.name)

            if current.name == target.name:
                return self._reconstruct_path(prev, target)

            for connection in self.graph.neighbors(current):
                neighbor = connection.other_end(current)
                if not neighbor.is_traversable():
                    continue

                new_cost = cost + neighbor.movement_cost()
                is_priority = neighbor.zone_type is ZoneType.PRIORITY
                new_prio = neg_prio - (1 if is_priority else 0)
                new_key = (new_cost, new_prio)

                # Si encontramos un camino más barato o de mejor prioridad
                if neighbor.name not in dist or new_key < dist[neighbor.name]:
                    dist[neighbor.name] = new_key
                    prev[neighbor.name] = current
                    counter += 1
                    heapq.heappush(
                        heap, (new_cost, new_prio, counter, neighbor)
                    )
        return None

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

    def path_cost(self, path: List[Zone]) -> int:
        """Suma el movement_cost() de cada zona de la ruta salvo el origen."""
        return sum(zone.movement_cost() for zone in path[1:])

    def _reconstruct_path(
        self, prev: Dict[str, Zone], target: Zone
    ) -> List[Zone]:
        """Reconstruye la secuencia de zonas desde el objetivo al origen."""
        path: List[Zone] = []
        curr: Optional[Zone] = target
        while curr is not None:
            path.append(curr)
            curr = prev.get(curr.name)
        path.reverse()
        return path
