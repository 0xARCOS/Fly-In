"""
Abstract heuristic: real minimum cost from each zone to end_hub,
ignoring the other drones.
"""

from typing import Dict

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.pathfinding.dijkstra import Dijkstra


class AbstractDistance:
    """Real minimum cost from each zone to the goal, ignoring other drones.

    It is computed only once at startup, with a Dijkstra from end_hub that
    walks the graph backwards. It is admissible: it never overestimates,
    because the other drones can only make a drone take longer, never less.

    Unreachable zones (blocked or disconnected) are NOT in the table: that
    absence is the information. Query them with is_reachable().
    """

    def __init__(self, graph: Graph) -> None:
        """Precompute the table of distances to end_hub (only once)."""
        self._dist: Dict[str, int] = self._compute(graph)

    def _compute(self, graph: Graph) -> Dict[str, int]:
        """Dijkstra from end_hub. 'blocked' zones are not expanded."""
        if graph.end_hub is None:
            return {}
        return Dijkstra(graph).distances_from(graph.end_hub, reverse=True)

    def h(self, zone: Zone) -> int:
        """Admissible heuristic: minimum turns from `zone` to the goal.

        Raises:
            KeyError: if the zone is unreachable from the goal.
        """
        return self._dist[zone.name]

    def is_reachable(self, zone: Zone) -> bool:
        """True if there is some route from `zone` to the goal."""
        return zone.name in self._dist
