"""Terminal HUD view (stub)."""

from typing import Any, Optional, Sequence, TextIO

from fly_in.models.graph import Graph
from fly_in.simulation.drone import Drone
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.simulator import Move, SimulationObserver
from fly_in.visualization.palette import Painter


class TerminalRenderer(SimulationObserver):
    """Renderizador de terminal HUD."""

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        stream: TextIO,
        paint: Painter,
        live: bool = True,
        delay: float = 0.4,
        title: str = "",
        window: int = 8,
        target: Optional[int] = None,
    ) -> None:
        """Inicializa el renderer."""
        self.graph = graph
        self.nb_drones = nb_drones
        self.stream = stream
        self.paint = paint
        self.live = live
        self.delay = delay
        self.title = title
        self.window = window
        self.target = target

    def __enter__(self) -> "TerminalRenderer":
        """Contexto: prepara la terminal."""
        return self

    def __exit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """Contexto: restaura la terminal."""
        pass

    def intro(self) -> None:
        """Muestra el intro."""
        pass

    def finish(self, metrics: Metrics) -> None:
        """Muestra el resumen final."""
        pass

    def on_turn(
        self,
        turn: int,
        moves: Sequence[Move],
        drones: Sequence[Drone]
    ) -> None:
        """Se llama después de cada turno."""
        pass
