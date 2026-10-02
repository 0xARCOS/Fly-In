"""Ocupación de zonas y conexiones turno a turno (--capacity-info)."""

from collections import Counter
from typing import Sequence, TextIO

from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED
from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move


class CapacityObserver:
    """Observador que escribe una línea de ocupación tras cada turno.

    Cumple el Protocol `SimulationObserver` solo con tener `on_turn`.
    """

    def __init__(self, graph: Graph, stream: TextIO) -> None:
        """Escribe en `stream`: stderr, porque stdout es del subject."""
        self.graph = graph
        self.stream = stream

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Zonas ocupadas tras el turno y conexiones usadas durante él."""
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
        print(f"T{turn} " + ", ".join(parts), file=self.stream)

    @staticmethod
    def limit(max_drones: float) -> str:
        """`max_drones` como texto: 'inf' en start_hub y end_hub."""
        return "inf" if max_drones == UNLIMITED else str(int(max_drones))
