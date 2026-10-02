"""Observador de capacidades (stub)."""

from typing import Sequence

from fly_in.models.graph import Graph
from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move, SimulationObserver


class CapacityObserver(SimulationObserver):
    """Observa capacidades durante la simulación."""

    def __init__(self, graph: Graph) -> None:
        """Inicializa el observador."""
        self.graph = graph

    def on_turn(
        self,
        turn: int,
        moves: Sequence[Move],
        drones: Sequence[Drone]
    ) -> None:
        """Se llama después de cada turno."""
        pass
