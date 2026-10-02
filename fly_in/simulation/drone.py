"""El dron: posición, estado y la ruta que le queda por ejecutar (SP08)."""

from enum import Enum, auto
from typing import List, Optional

from fly_in.models.connection import Connection
from fly_in.models.zone import Zone
from fly_in.pathfinding.whca import Step
from fly_in.simulation.errors import SimulationError


class DroneState(Enum):
    """Qué hizo el dron en el último turno ejecutado."""

    WAITING = auto()      # en una zona, sin movimiento este turno
    MOVING = auto()       # se movió a una zona adyacente este turno
    IN_TRANSIT = auto()   # en una conexión hacia una restricted: llega ya
    ARRIVED = auto()      # en end_hub: entregado, deja de rastrearse


class Drone:
    """Un agente que recorre el grafo de start_hub a end_hub.

    Mientras está IN_TRANSIT, `current_zone` sigue siendo la zona de la que
    salió y `transit_connection` la conexión en la que está: no ocupa
    ninguna zona hasta aterrizar.
    """

    def __init__(self, drone_id: int, start: Zone) -> None:
        """Crea el dron `drone_id` parado en `start`."""
        self.id = drone_id
        self.current_zone = start
        self.state = DroneState.WAITING
        self.path: List[Step] = []
        self.transit_connection: Optional[Connection] = None

    @property
    def is_active(self) -> bool:
        """True mientras no se haya entregado."""
        return self.state is not DroneState.ARRIVED

    @property
    def in_transit(self) -> bool:
        """True si está en el aire, camino de una zona restricted."""
        return self.state is DroneState.IN_TRANSIT

    def next_step(self, turn: int) -> Optional[Step]:
        """Paso que el dron empieza en el turno `turn` (sale del instante
        `turn`), o None si su ruta se ha agotado.

        Raises:
            SimulationError: Si el siguiente paso no empieza en `turn`: la
                ruta y el reloj de la simulación se han desincronizado.
        """
        if not self.path:
            return None
        step = self.path[0]
        departure = step.arrival_turn - step.cost
        if departure != turn:
            raise SimulationError(
                f"D{self.id}: next step to {step.zone.name} leaves at turn "
                f"{departure}, but the simulation is at turn {turn}"
            )
        return step

    def __repr__(self) -> str:
        """Representación legible para depurar."""
        where = (
            self.transit_connection.name
            if self.transit_connection is not None
            else self.current_zone.name
        )
        return f"Drone(D{self.id}, {self.state.name}, at={where!r})"
