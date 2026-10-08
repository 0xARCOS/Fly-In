"""
    1 - Priority queue with a 4-element tuple:
        (accumulated_cost, -num_priority, unique_counter, current_node)
        .. accumulated_cost: Fewest accumulated turns.
        .. -num_priority: On a cost tie, favors the route that goes
           through more priority zones.
        .. unique_counter: Prevents type comparison errors between
           Zone objects in Python (TypeError).
        .. current_node: The zone being explored.

    2 - Cost at the destination zone: When moving from zone A to zone B,
        the added cost is B.movement_cost
    3 - Skip blocked zones: If neighbor.is_traversable() is False, skip it
    4 - Path reconstruction: Returns the list [origin, ..., target]
        or None if the goal is unreachable.
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple
from fly_in.models.zone import Zone, ZoneType
from fly_in.models.graph import Graph


class Dijkstra:
    """
    Compute the static minimum-cost route for a single drone.
    """
    def __init__(self, graph: Graph) -> None:
        """Store the graph the searches will run on."""
        self.graph = graph

    def find_path(self, origin: Zone, target: Zone) -> Optional[List[Zone]]:
        """
            Find the minimum-cost route between origin and target.

            return:
                List of zones from origin to target (both included),
                or None if the goal is unreachable.
        """
        if not origin.is_traversable() or not target.is_traversable():
            return None

        # If origin and target are the same node
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

                # If we found a cheaper path or one with better priority
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
        Minimum cost from `origin` to each reachable zone, by name.

        reverse=False: cost of going from origin to X (adds the cost of
        entering each destination zone).
        reverse=True: cost of going from X to origin. Since the cost is an
        *entry* cost, expanding from `current` to `neighbor` adds the cost
        of `current`. Blocked zones are never visited and never appear.
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
        """Sum the movement_cost() of each zone on the route but the origin."""
        return sum(zone.movement_cost() for zone in path[1:])

    def _reconstruct_path(
        self, prev: Dict[str, Zone], target: Zone
    ) -> List[Zone]:
        """Rebuild the sequence of zones, from the goal back to the origin."""
        path: List[Zone] = []
        curr: Optional[Zone] = target
        while curr is not None:
            path.append(curr)
            curr = prev.get(curr.name)
        path.reverse()
        return path
