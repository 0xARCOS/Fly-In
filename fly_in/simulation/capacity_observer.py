"""Zone and connection usage, turn by turn (--capacity-info)."""

from collections import Counter
from typing import List, Sequence

from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED
from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move


class CapacityObserver:
    """Observer that records one usage line after each turn.

    It satisfies the `SimulationObserver` Protocol just by having
    `on_turn`. The lines are kept in `lines` (one per turn) and `FlyIn.run`
    writes them to stderr next to the stdout line of each turn.
    """

    def __init__(self, graph: Graph) -> None:
        """No lines yet."""
        self.graph = graph
        self.lines: List[str] = []

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Zones occupied after the turn and connections used during it."""
        zones = Counter(
            drone.current_zone.name for drone in drones
            if not drone.in_transit
        )
        links = Counter(move.connection.name for move in moves)
        capacity = {move.connection.name: move.connection.max_link_capacity
                    for move in moves}
        parts = [
            f"Zone {name}: {count}/"
            f"{self.limit(self.graph.zones[name].max_drones)} drones"
            for name, count in sorted(zones.items())
        ] + [
            f"Connection {name}: {count}/{capacity[name]} capacity used"
            for name, count in sorted(links.items())
        ]
        self.lines.append(f"T{turn} " + ", ".join(parts))

    @staticmethod
    def limit(max_drones: float) -> str:
        """`max_drones` as text: 'inf' on start_hub and end_hub."""
        return "inf" if max_drones == UNLIMITED else str(int(max_drones))
