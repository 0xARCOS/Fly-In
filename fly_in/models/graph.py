"""Map graph: zones, connections and the rules that relate them."""

from typing import Dict, FrozenSet, List, Optional

from fly_in.models.connection import Connection
from fly_in.models.zone import Zone

ROLES = {"hub", "start_hub", "end_hub"}


class Graph:
    """Map graph: zones (nodes) and the connections (edges) between them.

    The rules that depend on the accumulated state of the whole file are
    enforced here, not in the parser:
    - Unique zone names
    - At most one start_hub and one end_hub
    - connection: only references zones defined earlier in the file
    - No duplicate connections (a-b == b-a)

    It is immutable after parsing: turn-by-turn occupancy lives elsewhere.
    """

    def __init__(self) -> None:
        """Create an empty graph."""
        self.zones: Dict[str, Zone] = {}
        self.start_hub: Optional[Zone] = None
        self.end_hub: Optional[Zone] = None
        self.connections: List[Connection] = []
        # Indexes so that neighbors() and connection_between() are O(1):
        # pathfinding calls them on every expansion.
        self._adjacency: Dict[str, List[Connection]] = {}
        self._by_pair: Dict[FrozenSet[str], Connection] = {}

    def add_zone(self, zone: Zone, role: str) -> None:
        """Add a zone with its role ('hub', 'start_hub' or 'end_hub').

        Raises:
            ValueError: If the role is unknown, the name is repeated or
                there is already a start_hub/end_hub.
        """
        if role not in ROLES:
            raise ValueError(f"Unknown zone role: '{role}'")

        if zone.name in self.zones:
            raise ValueError(f"Zone name '{zone.name}' is already defined")

        if role == "start_hub":
            if self.start_hub is not None:
                raise ValueError("Only one 'start_hub' is allowed")
            self.start_hub = zone
        elif role == "end_hub":
            if self.end_hub is not None:
                raise ValueError("Only one 'end_hub' is allowed")
            self.end_hub = zone

        self.zones[zone.name] = zone
        self._adjacency[zone.name] = []

    def add_connection(
        self, origin: str, destination: str, max_link_capacity: int
    ) -> None:
        """Connect two already defined zones.

        Raises:
            ValueError: If either zone does not exist or the connection is
                repeated (in either direction).
        """
        if origin not in self.zones:
            raise ValueError(
                f"Connection references undefined zone: '{origin}'"
            )
        if destination not in self.zones:
            raise ValueError(
                f"Connection references undefined zone: '{destination}'"
            )

        pair = frozenset((origin, destination))
        if pair in self._by_pair:
            raise ValueError(
                f"Duplicate connection between "
                f"'{origin}' and '{destination}'"
            )

        connection = Connection(
            self.zones[origin], self.zones[destination], max_link_capacity
        )
        self.connections.append(connection)
        self._by_pair[pair] = connection
        self._adjacency[origin].append(connection)
        self._adjacency[destination].append(connection)

    def get_zone(self, name: str) -> Zone:
        """Look up a zone by name, or fail with a clear message.

        Raises:
            ValueError: If there is no zone with that name.
        """
        if name not in self.zones:
            raise ValueError(f"Unknown zone: '{name}'")
        return self.zones[name]

    def neighbors(self, zone: Zone) -> List[Connection]:
        """Connections touching `zone`, in the order they were defined.

        Returns a copy: modifying it does not alter the graph.
        """
        return list(self._adjacency.get(zone.name, []))

    def connection_between(self, zone_a: Zone, zone_b: Zone) -> Connection:
        """Connection joining `zone_a` and `zone_b`, in either direction.

        Raises:
            ValueError: If the two zones are not connected.
        """
        pair = frozenset((zone_a.name, zone_b.name))
        if pair not in self._by_pair:
            raise ValueError(
                f"No connection between '{zone_a.name}' and '{zone_b.name}'"
            )
        return self._by_pair[pair]
