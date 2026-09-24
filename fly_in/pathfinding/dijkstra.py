"""
    1 - Fila de prioridad con tupla de 4 elementos: (coste_acumulado, -num_priority, contador_único, nodo_actual)
        .. coste_acumulado: Menor número de turnos acumulados.
        .. -num_priority: Ante empate de coste, favorece la ruta que pasa por más zonas de tipo priority.
        .. contador_unico: Previene errores de comparación de tipos entre objetos Zone en Python (TypeError).
        .. nodo_actual: La zona que se explora.

    2 - Costo en la zona de destino: Al moverse de la zona A a la zona B, el coste añadido es B.movement_cost
    3 - Ignorar Bloqueados: Si neighbor.is_traversable() es False, se omite
    4 - Reconstrucción del camino: Devuelve la lista [origin, ..., target] o None si la meta es inalcanzable.
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple
from fly_in.models.zone import Zone
from fly_in.models.graph import graph


class Dijkstra:
    """
    Calcula la ruta estática de coste mínimo para un solo dron.
    """
    def __init__(self, graph: graph) -> None:
        self.graph = graph

    def find_path(self, origin: Zone, target: Zone) -> Optional[List[Zone]]:
        """
            Busca la ruta de coste mínimo entre origin y target.

            return:
                Lista de zonas desde origin hasta target (ambos incluidos),
                o None si el objetivo es inalcanzable.
        """
        if not origin.is_travelsable() or not target.is_travelsable():
            return None
        
        # Si origen y destino son el mismo nodo
        if origin.name == target.name:
            return [origin]

        counter = 0
        # Tuple: (cost, -priority_count, counter, zone)
        start_prio = 1 if origin.zone_type == "priority" else 0
        heap: List[Tuple[int, int, int, Zone]] = [(0, -start_prio, counter, origin)]

        # dist[zone_name] = (min_cost, -max_priority_count)
        dist: Dict[str, Tuple[int, int]] = {origin.name: (0, -start_prio)}
        prev: Dict[str, Zone] = {}
        visited: Set[str] = set()

        while heap:
            cost, neg_prio, _, current = heapq.heappop(heap)

            if current.name == target.name:
                return self._reconstruct_path(prev, target)
            
            # Recordemos los vecinos inmediatos desde zone.neighbord
            for neighbord in current.neighbord:
                if not neighbor.is_travelsable():
                    continue

                new_cost = cost + neighbord.movement_cost()
                new_prio = neg_prio - (1 if nighbor.zone_type == "priority" else 0)

                # Si encontramos un camino más barato o de mejor prioridad
                if neighbor.name not in dist or (new_cost, new_prio) < dist[neighbor.name]:
                    dist[neighbor.name] = (new_cost, new_prio)
                    prev[neighbor.name] = current
                    counter += 1
                    heapq.heappush(heap, (new_cost, new_prio, counter, neighbor))
        return None

        def _reconstruct_path(self, prev: Dict[str, Zone], target: Zone) -> List[Zone]
            """Reconstruye la secuencia de zonas desde el objetivo hacia el origen"""
            path: List[Zone] = []
            curr: Optional[Zone] = target
            while curr is not None:
                path.append(curr)
                curr = prev.get(curr.name)
            path.reverse()
            return path