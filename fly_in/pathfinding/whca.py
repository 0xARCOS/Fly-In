"""Cooperative space-time search: WHCA* (SP07).

The search state is no longer `zone` but `(zone, turn)`. The reservations
of the drones that planned earlier are obstacles that exist only on some
turns, and the search avoids them on its own: a collision is simply not
among the reachable states.

It uses the time convention of ReservationTable (SP06): "instant t" is the
state after t turns; a move that leaves at T with cost c arrives at T+c.
"""

import heapq
from dataclasses import dataclass
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)

from fly_in.models.connection import Connection
from fly_in.models.graph import Graph
from fly_in.models.zone import Zone, ZoneType
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.reservation_table import ReservationTable

DEFAULT_WINDOW = 8


class DroneLike(Protocol):
    """All the search needs to know about a drone.

    The `Drone` of SP08 satisfies it without inheriting from anything; the
    tests use a minimal dataclass.
    """

    @property
    def id(self) -> int:
        """Drone identifier (the N of `DN` in the output)."""
        ...

    @property
    def current_zone(self) -> Zone:
        """Zone the drone is in when planning starts."""
        ...


# Takes the drones to plan and the current turn; returns the order in which
# they plan. Whoever goes first gets the best reservations.
PlanningOrder = Callable[[Sequence[DroneLike], int], List[DroneLike]]


@dataclass(frozen=True, order=True)
class SearchNode:
    """A (zone, turn) state in the A* priority queue.

    The order of the fields IS the heap order: first `f`, and on a tie the
    route with more priority zones (same as Dijkstra in SP04), then `g`,
    `turn` and finally `tie`, a counter that breaks ties in favor of the
    node discovered first. `zone_name` comes after `tie`, so it is never
    compared.
    """

    f: int              # g + h
    neg_priority: int   # -(priority zones on the route): more is better
    g: int              # turns spent since the start of the window
    turn: int           # absolute simulation instant
    tie: int            # incremental counter, stable tie-break
    zone_name: str


@dataclass(frozen=True)
class Step:
    """One step of the planned route."""

    zone: Zone                        # where this step ends
    arrival_turn: int                 # absolute arrival instant
    connection: Optional[Connection]  # None for a wait in place
    cost: int                         # 1, or 2 if the target is restricted


class WhcaPathfinder:
    """Windowed Hierarchical Cooperative A* (Silver, 2005).

    Searches in space-time (zone, turn) honoring the reservations of the
    drones that already planned, within a window of `window` turns. Beyond
    the window it trusts the abstract heuristic.
    """

    def __init__(
        self,
        graph: Graph,
        heuristic: AbstractDistance,
        table: ReservationTable,
        window: int = DEFAULT_WINDOW,
        order: Optional[PlanningOrder] = None,
    ) -> None:
        """Set up the search.

        Args:
            graph: Map graph (with end_hub).
            heuristic: Abstract distances to end_hub (SP05).
            table: Reservation table shared by every drone.
            window: Turns looked ahead while cooperating.
            order: Priority criterion between drones; by id by default.

        Raises:
            ValueError: If the window is not positive or the graph has no
                end_hub.
        """
        if window < 1:
            raise ValueError(f"Window must be at least 1, got {window}")
        if graph.end_hub is None:
            raise ValueError("Graph has no end_hub")
        self.graph = graph
        self.heuristic = heuristic
        self.table = table
        self.window = window
        self.order: PlanningOrder = (
            order if order is not None else PlanningOrders.by_id
        )
        self._goal: Zone = graph.end_hub

    # --- API -----------------------------------------------------------

    def plan(
        self, drones: Sequence[DroneLike], start_turn: int
    ) -> Dict[int, List[Step]]:
        """Plan and record the route of each drone, in priority order.

        Each route is written to the table BEFORE planning the next one:
        otherwise they would all plan against the same table and collide.

        Before starting, every drone reserves staying in its zone for the
        whole window (provisional reservation). Without it, whoever plans
        first does not see those who have not planned yet and may reserve
        entering their zone when they have no way out. Each drone swaps its
        provisional reservation for its real route right before searching
        for it, so it can always, at the very least, wait where it is.

        Returns:
            Route of each drone, by id.
        """
        ordered = self.order(drones, start_turn)
        for drone in ordered:
            self._hold(drone, start_turn)

        paths: Dict[int, List[Step]] = {}
        for drone in ordered:
            self.table.release(drone.id, start_turn)
            path = self.find_path(drone, start_turn)
            self.reserve(drone.id, drone.current_zone, path)
            paths[drone.id] = path
        return paths

    def find_path(self, drone: DroneLike, start_turn: int) -> List[Step]:
        """Route of the drone from its current position, within the window.

        Returns:
            List of steps, possibly partial (up to the edge of the window).
            Never empty unless the drone is already at end_hub: in the
            worst case, waiting in place.
        """
        start = drone.current_zone
        if start is self._goal:
            return []
        if not self.heuristic.is_reachable(start):
            return [self._wait_step(start, start_turn)]

        tie = 0
        root = SearchNode(
            f=self.heuristic.h(start),
            neg_priority=0,
            g=0,
            turn=start_turn,
            tie=tie,
            zone_name=start.name,
        )
        open_heap: List[SearchNode] = [root]
        closed: Set[Tuple[str, int]] = set()
        parents: Dict[int, SearchNode] = {}
        best: Optional[SearchNode] = None

        while open_heap:
            node = heapq.heappop(open_heap)
            zone = self.graph.get_zone(node.zone_name)

            # The goal is checked BEFORE the window: arriving exactly on
            # the last turn of the window counts as arriving.
            if zone is self._goal:
                return self._reconstruct(node, parents)

            if node.turn - start_turn >= self.window:
                if best is None or node.f < best.f:
                    best = node
                continue

            state = (node.zone_name, node.turn)
            if state in closed:
                continue
            closed.add(state)

            for target, cost, bonus in self._successors(node, zone):
                tie += 1
                child = SearchNode(
                    f=node.g + cost + self.heuristic.h(target),
                    neg_priority=node.neg_priority - bonus,
                    g=node.g + cost,
                    turn=node.turn + cost,
                    tie=tie,
                    zone_name=target.name,
                )
                parents[tie] = node
                heapq.heappush(open_heap, child)

        if best is None:
            # Boxed in right now: not even the edge of the window can be
            # reached. Never None: stay still this turn.
            return [self._wait_step(start, start_turn)]
        return self._reconstruct(best, parents)

    def reserve(
        self, drone_id: int, origin: Zone, path: Sequence[Step]
    ) -> None:
        """Write `path` to the table on behalf of `drone_id`.

        `origin` is the zone the drone is in before the first step.

        Raises:
            ReservationError: If some step does not fit (caller bug).
        """
        previous = origin
        for step in path:
            if step.connection is None:
                self.table.reserve_wait(drone_id, step.zone, step.arrival_turn)
            else:
                self.table.reserve_move(
                    drone_id,
                    previous,
                    step.zone,
                    step.arrival_turn - step.cost,
                )
            previous = step.zone

    # --- internals -----------------------------------------------------

    def _hold(self, drone: DroneLike, start_turn: int) -> None:
        """Provisional reservation: `drone` stays in its zone all window.

        It stops at the first instant with no room: that only happens if a
        drone in transit (kept with `keep`) lands there, and then this
        drone has to leave earlier, which its search will already take into
        account.
        """
        zone = drone.current_zone
        for turn in range(start_turn + 1, start_turn + self.window + 1):
            if not self.table.zone_has_room(zone, turn):
                return
            self.table.reserve_wait(drone.id, zone, turn)

    def _successors(
        self, node: SearchNode, zone: Zone
    ) -> List[Tuple[Zone, int, int]]:
        """Legal successors of `node` as (zone, cost, priority bonus)."""
        result: List[Tuple[Zone, int, int]] = []
        for connection in self.graph.neighbors(zone):
            neighbor = connection.other_end(zone)
            if not neighbor.is_traversable():
                continue
            if not self.heuristic.is_reachable(neighbor):
                continue
            # Connection and direction on every turn of the trip + arrival.
            if not self.table.can_move(zone, neighbor, node.turn):
                continue
            bonus = 1 if neighbor.zone_type is ZoneType.PRIORITY else 0
            result.append((neighbor, neighbor.movement_cost(), bonus))

        # Waiting in place is one more neighbor (Chap. VII.3, "Stay in
        # place"): the only way to give way to another drone.
        if self.table.zone_has_room(zone, node.turn + 1):
            result.append((zone, 1, 0))
        return result

    def _reconstruct(
        self, node: SearchNode, parents: Dict[int, SearchNode]
    ) -> List[Step]:
        """Turn the chain of parents of `node` into steps."""
        steps: List[Step] = []
        current = node
        while current.tie in parents:
            parent = parents[current.tie]
            zone = self.graph.get_zone(current.zone_name)
            cost = current.turn - parent.turn
            if current.zone_name == parent.zone_name:
                connection: Optional[Connection] = None
            else:
                connection = self.graph.connection_between(
                    self.graph.get_zone(parent.zone_name), zone
                )
            steps.append(Step(zone, current.turn, connection, cost))
            current = parent
        steps.reverse()
        return steps

    @staticmethod
    def _wait_step(zone: Zone, start_turn: int) -> Step:
        """Step of "staying in `zone`" during turn `start_turn`."""
        return Step(zone, start_turn + 1, None, 1)


class PlanningOrders:
    """Interchangeable priority criteria for `WhcaPathfinder.plan`.

    Each criterion is a `PlanningOrder`: it takes the drones and the turn
    and returns the order in which they plan. Those that depend on the
    heuristic are factories: they take `AbstractDistance` and return the
    criterion.
    """

    @staticmethod
    def by_id(drones: Sequence[DroneLike], turn: int) -> List[DroneLike]:
        """By ascending id: deterministic and trivial, but D1 hogs."""
        return sorted(drones, key=lambda drone: drone.id)

    @staticmethod
    def farthest_first(heuristic: AbstractDistance) -> PlanningOrder:
        """The drones farthest from the goal (highest h) choose first.

        Ties by id. It tends to reduce the turn of the last arrival, which
        is the metric.
        """
        def order(
            drones: Sequence[DroneLike], turn: int
        ) -> List[DroneLike]:
            """Highest h first; ties by id."""
            return sorted(
                drones,
                key=lambda drone: (
                    -PlanningOrders._distance(heuristic, drone.current_zone),
                    drone.id,
                ),
            )
        return order

    @staticmethod
    def nearest_first(heuristic: AbstractDistance) -> PlanningOrder:
        """The drones nearest to the goal (lowest h) choose first.

        Ties by id. It fits well with the provisional reservation of
        `plan`: the drone ahead plans first and frees its zone, instead of
        the one behind seeing it "standing still".
        """
        def order(
            drones: Sequence[DroneLike], turn: int
        ) -> List[DroneLike]:
            """Lowest h first (unreachable last); ties by id."""
            return sorted(
                drones,
                key=lambda drone: (
                    PlanningOrders._distance(heuristic, drone.current_zone)
                    < 0,
                    PlanningOrders._distance(heuristic, drone.current_zone),
                    drone.id,
                ),
            )
        return order

    @staticmethod
    def rotating(drones: Sequence[DroneLike], turn: int) -> List[DroneLike]:
        """By id, but starting at a position that advances with the turn.

        Spreads the advantage of planning first across replans.
        """
        ordered = PlanningOrders.by_id(drones, turn)
        if not ordered:
            return ordered
        shift = turn % len(ordered)
        return ordered[shift:] + ordered[:shift]

    @staticmethod
    def _distance(heuristic: AbstractDistance, zone: Zone) -> int:
        """h(zone), or -1 if unreachable (those plan last)."""
        return heuristic.h(zone) if heuristic.is_reachable(zone) else -1
