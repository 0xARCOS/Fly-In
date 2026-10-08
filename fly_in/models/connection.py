"""Bidirectional connection between two zones."""

from fly_in.models.zone import Zone


class Connection:
    """Graph edge between two zones.

    Stores the actual `Zone` objects (not just their names) and the maximum
    number of drones that can traverse it at the same time.
    """

    def __init__(
        self, zone_a: Zone, zone_b: Zone, max_link_capacity: int = 1
    ) -> None:
        """Create the connection between `zone_a` and `zone_b`.

        Args:
            zone_a: First end, as written in the file.
            zone_b: Second end, as written in the file.
            max_link_capacity: Drones that can cross it simultaneously.
        """
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity

    def other_end(self, zone: Zone) -> Zone:
        """Return the end of this connection opposite to `zone`.

        Raises:
            ValueError: If `zone` is neither of the two ends.
        """
        if zone is self.zone_a:
            return self.zone_b
        if zone is self.zone_b:
            return self.zone_a
        raise ValueError(
            f"Zone '{zone.name}' is not part of this connection"
        )

    @property
    def name(self) -> str:
        """Name of the connection as it appears in the output (Chap. VII.5).

        It is unique in the graph: zone names contain no dashes and
        duplicate connections are rejected while parsing.
        """
        return f"{self.zone_a.name}-{self.zone_b.name}"

    def __repr__(self) -> str:
        """Readable representation for debugging."""
        return (
            f"Connection({self.zone_a.name!r}-{self.zone_b.name!r}, "
            f"max_link_capacity={self.max_link_capacity})"
        )
