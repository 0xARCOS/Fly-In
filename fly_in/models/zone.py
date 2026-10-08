"""Map zone: graph node with a type, coordinates and a capacity."""

from enum import Enum
from typing import Optional


class ZoneType(Enum):
    """Zone type (Chap. VI). The value is the text of the 'zone=' tag."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


# Turns it costs to enter a zone, by type (Chap. VII.3).
# BLOCKED is missing on purpose: it cannot be entered.
MOVEMENT_COST = {
    ZoneType.NORMAL: 1,
    ZoneType.PRIORITY: 1,
    ZoneType.RESTRICTED: 2,
}

# Capacity of start_hub/end_hub (Chap. VII.2). Being infinite, any
# comparison `occupancy < max_drones` is true with no special cases.
UNLIMITED = float("inf")


class Zone:
    """A map node: a normal hub, the start_hub or the end_hub."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: ZoneType = ZoneType.NORMAL,
        max_drones: float = 1,
        color: Optional[str] = None,
    ) -> None:
        """Create the zone.

        Args:
            name: Unique name, with no dashes or spaces.
            x: Horizontal coordinate (only used for drawing).
            y: Vertical coordinate (only used for drawing).
            zone_type: Type of the zone.
            max_drones: Simultaneous drones allowed; UNLIMITED on start/end.
            color: Optional color for the visualization.
        """
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.max_drones = max_drones
        self.color = color

    def is_traversable(self) -> bool:
        """Return False only for 'blocked' zones."""
        return self.zone_type is not ZoneType.BLOCKED

    def movement_cost(self) -> int:
        """Turns it costs to enter the zone.

        Raises:
            ValueError: If the zone is 'blocked' (it cannot be entered).
        """
        if not self.is_traversable():
            raise ValueError(
                f"Cannot compute movement cost for blocked zone '{self.name}'"
            )
        return MOVEMENT_COST[self.zone_type]

    def __repr__(self) -> str:
        """Readable representation for debugging."""
        capacity_str = (
            "inf" if self.max_drones == UNLIMITED
            else str(int(self.max_drones))
        )
        return (
            f"Zone(name={self.name!r}, x={self.x}, y={self.y}, "
            f"zone_type={self.zone_type.value!r}, max_drones={capacity_str})"
        )
