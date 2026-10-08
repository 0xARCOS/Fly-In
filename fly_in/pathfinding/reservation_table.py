"""Space-time reservation table (SP06).

Time convention (shared with SP07 and SP08):

- "Instant t" is the state after executing t turns. Instant 0 is the
  initial one (every drone at start_hub). Output line k is the step from
  instant k-1 to instant k.
- Zone (z, t): drones that are in z at instant t.
- Connection (c, t): drones crossing c between instant t and t+1.
- A move that leaves `frm` at instant T towards `to` (cost c) occupies the
  connection at T … T+c-1 and zone `to` at instant T+c. It occupies no
  zone at the intermediate instants: it is in the air.
"""

from typing import AbstractSet, Callable, Dict, List, Tuple, TypeVar

from fly_in.models.connection import Connection
from fly_in.models.graph import Graph
from fly_in.models.zone import Zone

ZoneKey = Tuple[str, int]
MoveKey = Tuple[str, str, int]
Key = TypeVar("Key", ZoneKey, MoveKey)


class ReservationError(Exception):
    """Something that does not fit was about to be reserved.

    It should never happen: the planner asks before reserving. If it is
    raised, there is a bug in the caller, and it is better to find out here
    than three turns later as an unexplained collision.
    """


class ReservationTable:
    """Space-time occupancy of zones and connections.

    It stores WHO (drone id) occupies each zone and connection at each
    instant; the occupancy is the length of that list. start_hub and
    end_hub never fill up because their max_drones is UNLIMITED.
    """

    def __init__(self, graph: Graph) -> None:
        """Create an empty table for `graph`."""
        self._graph = graph
        self._zones: Dict[ZoneKey, List[int]] = {}
        self._links: Dict[ZoneKey, List[int]] = {}
        self._moves: Dict[MoveKey, List[int]] = {}

    # --- queries -------------------------------------------------------

    def zone_has_room(self, zone: Zone, turn: int) -> bool:
        """Does one more drone fit in `zone` at instant `turn`?"""
        occupants = self._zones.get((zone.name, turn), [])
        return len(occupants) < zone.max_drones

    def link_has_room(self, conn: Connection, turn: int) -> bool:
        """Does one more drone fit crossing `conn` between `turn` and +1?"""
        occupants = self._links.get((conn.name, turn), [])
        return len(occupants) < conn.max_link_capacity

    def would_swap(self, frm: Zone, to: Zone, turn: int) -> bool:
        """Is a drone crossing in direction `to → frm` between `turn`, +1?"""
        return (to.name, frm.name, turn) in self._moves

    def can_move(self, frm: Zone, to: Zone, turn: int) -> bool:
        """Can a drone leave `frm` at `turn` and arrive at `to`?

        Checks everything the move occupies: the connection and the
        direction at every instant of the trip, and the destination zone on
        arrival.

        Raises:
            ValueError: If `frm` and `to` are not connected.
        """
        conn = self._graph.connection_between(frm, to)
        if not to.is_traversable():
            return False
        cost = to.movement_cost()
        for slot in range(turn, turn + cost):
            if not self.link_has_room(conn, slot):
                return False
            if self.would_swap(frm, to, slot):
                return False
        return self.zone_has_room(to, turn + cost)

    def zone_occupants(self, zone: Zone, turn: int) -> List[int]:
        """Ids of the drones in `zone` at instant `turn` (a copy)."""
        return list(self._zones.get((zone.name, turn), []))

    def link_occupants(self, conn: Connection, turn: int) -> List[int]:
        """Ids of the drones crossing `conn` between `turn` and +1 (copy)."""
        return list(self._links.get((conn.name, turn), []))

    # --- writing -------------------------------------------------------

    def reserve_move(
        self, drone_id: int, frm: Zone, to: Zone, turn: int
    ) -> None:
        """Reserve the move of `drone_id` from `frm` to `to` leaving at
        `turn`: the connection at turn … turn+cost-1 and `to` at turn+cost.

        It is atomic: either everything is reserved or nothing is touched.

        Raises:
            ReservationError: If the move does not fit.
            ValueError: If `frm` and `to` are not connected.
        """
        if not self.can_move(frm, to, turn):
            raise ReservationError(
                f"D{drone_id}: move {frm.name}->{to.name} "
                f"leaving at turn {turn} does not fit"
            )
        conn = self._graph.connection_between(frm, to)
        cost = to.movement_cost()
        for slot in range(turn, turn + cost):
            self._add(self._links, (conn.name, slot), drone_id)
            self._add(self._moves, (frm.name, to.name, slot), drone_id)
        self._add(self._zones, (to.name, turn + cost), drone_id)

    def reserve_wait(self, drone_id: int, zone: Zone, turn: int) -> None:
        """Reserve that `drone_id` is in `zone` at instant `turn`.

        Raises:
            ReservationError: If the zone is full at that instant.
        """
        if not self.zone_has_room(zone, turn):
            raise ReservationError(
                f"D{drone_id}: zone {zone.name} is full at turn {turn}"
            )
        self._add(self._zones, (zone.name, turn), drone_id)

    def clear_from(
        self, turn: int, keep: AbstractSet[int] = frozenset()
    ) -> None:
        """Discard the reservations from `turn` onwards.

        Those before `turn` are history already executed and are kept.
        Those of the drones in `keep` are kept whole: they are drones in the
        air, whose arrival is already committed and cannot be replanned.
        """
        self._drop_from(turn, lambda drone: drone not in keep)

    def release(self, drone_id: int, turn: int) -> None:
        """Discard the reservations of `drone_id` from `turn` onwards.

        Those of the other drones are not touched. SP07 uses it to swap the
        provisional reservation of a drone for its real route.
        """
        self._drop_from(turn, lambda drone: drone == drone_id)

    # --- internals -----------------------------------------------------

    def _drop_from(self, turn: int, drop: Callable[[int], bool]) -> None:
        """Remove from the three tables, at keys >= `turn`, the drones for
        which `drop` is True."""
        self._zones = self._filtered(self._zones, turn, drop)
        self._links = self._filtered(self._links, turn, drop)
        self._moves = self._filtered(self._moves, turn, drop)

    @staticmethod
    def _add(table: Dict[Key, List[int]], key: Key, drone_id: int) -> None:
        """Record `drone_id` under `key`.

        Raises:
            ReservationError: If that drone was already recorded there:
                counting it twice would falsify the occupancy.
        """
        occupants = table.setdefault(key, [])
        if drone_id in occupants:
            raise ReservationError(f"D{drone_id} already reserved {key}")
        occupants.append(drone_id)

    @staticmethod
    def _filtered(
        table: Dict[Key, List[int]], turn: int, drop: Callable[[int], bool]
    ) -> Dict[Key, List[int]]:
        """Copy of `table` without the `drop` drones at keys >= `turn`.

        Builds a new dictionary instead of deleting while iterating:
        deleting during iteration raises RuntimeError.
        """
        result: Dict[Key, List[int]] = {}
        for key, occupants in table.items():
            if key[-1] < turn:
                result[key] = list(occupants)
                continue
            kept = [drone for drone in occupants if not drop(drone)]
            if kept:
                result[key] = kept
        return result
