"""The drone: position, state and the rest of its route (SP08)."""

from enum import Enum, auto
from typing import List, Optional

from fly_in.models.connection import Connection
from fly_in.models.zone import Zone
from fly_in.pathfinding.whca import Step
from fly_in.simulation.errors import SimulationError


class DroneState(Enum):
    """What the drone did in the last executed turn."""

    WAITING = auto()      # in a zone, no move this turn
    MOVING = auto()       # moved to an adjacent zone this turn
    IN_TRANSIT = auto()   # on a connection towards a restricted zone
    ARRIVED = auto()      # at end_hub: delivered, no longer tracked


class Drone:
    """An agent that travels the graph from start_hub to end_hub.

    While IN_TRANSIT, `current_zone` is still the zone it left and
    `transit_connection` is the connection it is on: it occupies no zone
    until it lands.
    """

    def __init__(self, drone_id: int, start: Zone) -> None:
        """Create drone `drone_id` standing at `start`."""
        self.id = drone_id
        self.current_zone = start
        self.state = DroneState.WAITING
        self.path: List[Step] = []
        self.transit_connection: Optional[Connection] = None

    @property
    def is_active(self) -> bool:
        """True until it has been delivered."""
        return self.state is not DroneState.ARRIVED

    @property
    def in_transit(self) -> bool:
        """True if it is in the air, on its way to a restricted zone."""
        return self.state is DroneState.IN_TRANSIT

    def next_step(self, turn: int) -> Optional[Step]:
        """Step the drone starts on turn `turn` (it leaves at instant
        `turn`), or None if its route is exhausted.

        Raises:
            SimulationError: If the next step does not start at `turn`: the
                route and the simulation clock are out of sync.
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
        """Readable representation for debugging."""
        where = (
            self.transit_connection.name
            if self.transit_connection is not None
            else self.current_zone.name
        )
        return f"Drone(D{self.id}, {self.state.name}, at={where!r})"
