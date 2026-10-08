"""The turn-by-turn loop (SP08).

Each turn has three moments:

1. Replan, when due: at the start of every half window, or earlier if
   some drone has run out of route.
2. Phase 1, DECIDE: each drone says what it will do this turn. Nobody
   moves.
3. Phase 2, APPLY: every move at once, and a check that the new state
   honors the capacities.

It uses the time convention of ReservationTable (SP06): turn `t` goes from
instant `t` to `t+1`, and it is line `t+1` of the output.
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from fly_in.models.connection import Connection
from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.reservation_table import (
    ReservationError,
    ReservationTable,
)
from fly_in.pathfinding.whca import (
    DEFAULT_WINDOW,
    PlanningOrder,
    Step,
    WhcaPathfinder,
)
from fly_in.simulation.drone import Drone, DroneState
from fly_in.simulation.errors import SimulationError

# Max turns = nb_drones * zones * MAX_TURNS_FACTOR. A lone drone takes at
# most 2 per zone (restricted); in single file, nb_drones times that.
# Factor 4 leaves twice the margin over that reasonable worst case.
MAX_TURNS_FACTOR = 4


@dataclass(frozen=True)
class Move:
    """What a drone did in a turn, as the output needs it.

    `arrives` is False only on the first turn of a transit towards a
    restricted zone: the drone ends the turn on `connection` (it prints
    `D<id>-<connection>`). In every other case it ends at `target`
    (`D<id>-<zone>`).
    """

    drone_id: int
    origin: Zone
    target: Zone
    connection: Connection
    arrives: bool


@dataclass(frozen=True)
class Replan:
    """A replan: when, for how many drones and how long it took."""

    turn: int         # instant at which it replans
    grounded: int     # replanned drones
    airborne: int     # drones in the air, kept with keep
    seconds: float    # compute time of plan()


class SimulationObserver(Protocol):
    """Anyone who wants to watch the simulation as it happens (SP10).

    The simulator notifies it after applying each turn. The observer only
    reads: it must not modify the drones.
    """

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence["Drone"]
    ) -> None:
        """`turn` is the number of the output line just completed."""
        ...


class ObserverGroup:
    """Hand each turn to several observers (recorder + capacity info)."""

    def __init__(self, *observers: SimulationObserver) -> None:
        """Group `observers`, which are called in that order."""
        self.observers = observers

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence["Drone"]
    ) -> None:
        """Pass the turn to every observer."""
        for observer in self.observers:
            observer.on_turn(turn, moves, drones)


# Phase 1 decision: the drone, the step it executes and the move it
# produces (None = wait in place: it does not appear in the output).
Decision = Tuple[Drone, Step, Optional[Move]]


class Simulator:
    """Move every drone from start_hub to end_hub, turn by turn."""

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        window: int = DEFAULT_WINDOW,
        order: Optional[PlanningOrder] = None,
    ) -> None:
        """Set up the simulation with `nb_drones` drones at start_hub.

        Raises:
            SimulationError: If the map has no start_hub/end_hub or if
                end_hub is unreachable: it is detected at turn 0, not after
                hundreds of turns going round in circles.
        """
        if graph.start_hub is None or graph.end_hub is None:
            raise SimulationError("The map needs a start_hub and an end_hub")
        self.graph = graph
        self.heuristic = AbstractDistance(graph)
        if not self.heuristic.is_reachable(graph.start_hub):
            raise SimulationError(
                f"'{graph.end_hub.name}' is unreachable from "
                f"'{graph.start_hub.name}'"
            )
        self.table = ReservationTable(graph)
        self.pathfinder = WhcaPathfinder(
            graph, self.heuristic, self.table, window, order
        )
        self.window = window
        # W // 2: there are always W/2 turns of cooperation ahead. With
        # W = 1 it would be 0, so at the very least it replans every turn.
        self.replan_every = max(1, window // 2)
        self.max_turns = max(
            1, nb_drones * len(graph.zones) * MAX_TURNS_FACTOR
        )
        self.drones: List[Drone] = [
            Drone(drone_id, graph.start_hub)
            for drone_id in range(1, nb_drones + 1)
        ]
        self._goal: Zone = graph.end_hub
        self.elapsed = 0.0   # compute seconds of the last run()
        self.replans: List[Replan] = []

    # --- API -----------------------------------------------------------

    def run(
        self, observer: Optional[SimulationObserver] = None
    ) -> List[List[Move]]:
        """Run the whole simulation.

        Args:
            observer: Called after each turn (the visualization).

        Returns:
            The trace: one list of moves per turn. Its length is the number
            of turns, the metric of the subject (Chap. VII.6).

        Raises:
            SimulationError: If it does not converge before `max_turns`, if
                the planning does not fit in the table or if some turn
                breaks a capacity (bug in SP06/SP07).
        """
        trace: List[List[Move]] = []
        turn = 0
        started = time.perf_counter()
        watching = 0.0   # time inside the observer: not compute time
        while True:
            active = [drone for drone in self.drones if drone.is_active]
            if not active:
                self.elapsed = time.perf_counter() - started - watching
                return trace
            if turn >= self.max_turns:
                raise SimulationError(self._stuck_message(turn, active))
            if self._must_replan(turn, active):
                self._replan(turn, active)
            decisions = self._decide(turn, active)
            moves = self._apply(decisions)
            self._verify(turn, moves)
            trace.append(moves)
            turn += 1
            if observer is not None:
                paused = time.perf_counter()
                observer.on_turn(turn, moves, self.drones)
                watching += time.perf_counter() - paused

    # --- replanning ----------------------------------------------------

    def _must_replan(self, turn: int, active: Sequence[Drone]) -> bool:
        """Is a replan due at the start of `turn`?

        Every half window, and also if some grounded drone has run out of
        route: waiting with no reservation would leave its zone free in the
        table for another drone to plan to enter it.
        """
        if turn % self.replan_every == 0:
            return True
        return any(not d.in_transit and not d.path for d in active)

    def _replan(self, turn: int, active: Sequence[Drone]) -> None:
        """Forget the future and plan the grounded drones again.

        Those in the air are not replanned (they can neither stop nor turn
        back) and keep their reservations with `keep`: their landing is
        already committed.
        """
        in_transit = {drone.id for drone in active if drone.in_transit}
        self.table.clear_from(turn, keep=in_transit)
        grounded = [drone for drone in active if not drone.in_transit]
        started = time.perf_counter()
        try:
            paths = self.pathfinder.plan(grounded, turn)
        except ReservationError as exc:
            raise SimulationError(
                f"Planning failed at turn {turn}: {exc}"
            ) from exc
        for drone in grounded:
            drone.path = paths[drone.id]
        self.replans.append(Replan(
            turn, len(grounded), len(in_transit),
            time.perf_counter() - started,
        ))

    # --- phase 1: decide -----------------------------------------------

    def _decide(self, turn: int, active: Sequence[Drone]) -> List[Decision]:
        """What each drone does this turn. It modifies nothing.

        Every decision is taken against the same state, so the result does
        not depend on the order of the list of drones.
        """
        decisions: List[Decision] = []
        for drone in active:
            if drone.in_transit:
                decisions.append(self._land(drone, turn))
                continue
            step = drone.next_step(turn)
            if step is None:
                raise SimulationError(
                    f"D{drone.id} has no plan at turn {turn}"
                )
            if step.connection is None:
                decisions.append((drone, step, None))
                continue
            move = Move(
                drone_id=drone.id,
                origin=drone.current_zone,
                target=step.zone,
                connection=step.connection,
                arrives=step.cost == 1,
            )
            decisions.append((drone, step, move))
        return decisions

    @staticmethod
    def _land(drone: Drone, turn: int) -> Decision:
        """Second turn of a transit: the drone lands, with no choice.

        Chap. VII.3: "the drone MUST reach its destination during the next
        turn". It is not asked anything: asking would open the door to
        waiting in the air.
        """
        step = drone.path[0]
        if drone.transit_connection is None or step.arrival_turn != turn + 1:
            raise SimulationError(
                f"D{drone.id} is in transit but cannot land at turn "
                f"{turn + 1}"
            )
        move = Move(
            drone_id=drone.id,
            origin=drone.current_zone,
            target=step.zone,
            connection=drone.transit_connection,
            arrives=True,
        )
        return drone, step, move

    # --- phase 2: apply ------------------------------------------------

    def _apply(self, decisions: Sequence[Decision]) -> List[Move]:
        """Execute every decision at once.

        Returns:
            The moves of the turn, by drone id (waits excluded).
        """
        moves: List[Move] = []
        for drone, step, move in decisions:
            if move is None:
                drone.path.pop(0)
                drone.state = DroneState.WAITING
                continue
            moves.append(move)
            if not move.arrives:
                drone.state = DroneState.IN_TRANSIT
                drone.transit_connection = move.connection
                continue
            drone.path.pop(0)
            drone.current_zone = step.zone
            drone.transit_connection = None
            drone.state = (
                DroneState.ARRIVED
                if step.zone is self._goal
                else DroneState.MOVING
            )
        moves.sort(key=lambda move: move.drone_id)
        return moves

    def _verify(self, turn: int, moves: Sequence[Move]) -> None:
        """Recount the occupancy after the turn without looking at the table.

        If the pathfinder did its job, this never fires. If it does, it is
        a bug in SP06/SP07, and it is better to know on this turn than three
        maps later.

        Raises:
            SimulationError: If a zone or connection exceeds its capacity.
        """
        in_zone: Dict[str, int] = {}
        for drone in self.drones:
            if drone.is_active and not drone.in_transit:
                name = drone.current_zone.name
                in_zone[name] = in_zone.get(name, 0) + 1
        for name, count in in_zone.items():
            zone = self.graph.get_zone(name)
            if count > zone.max_drones:
                raise SimulationError(
                    f"Turn {turn + 1}: {count} drones in '{name}' "
                    f"(max_drones={int(zone.max_drones)})"
                )

        on_link: Dict[str, int] = {}
        for move in moves:
            name = move.connection.name
            on_link[name] = on_link.get(name, 0) + 1
            if on_link[name] > move.connection.max_link_capacity:
                raise SimulationError(
                    f"Turn {turn + 1}: {on_link[name]} drones on '{name}' "
                    f"(max_link_capacity="
                    f"{move.connection.max_link_capacity})"
                )

    # --- diagnostics ---------------------------------------------------

    def _stuck_message(self, turn: int, active: Sequence[Drone]) -> str:
        """Non-convergence message that names every stuck drone."""
        where = ", ".join(
            f"D{drone.id} ("
            + (
                f"in transit on {drone.transit_connection.name}"
                if drone.transit_connection is not None
                else f"at {drone.current_zone.name}"
            )
            + ")"
            for drone in active
        )
        return (
            f"Simulation did not converge after {turn} turns. "
            f"Undelivered drones: {where}"
        )
