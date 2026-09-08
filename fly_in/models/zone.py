from typing import Optional

# Único juego de valores válido para el metadato 'zone=' (ver checklist
# de map_parser.py).
ALLOWED_ZONE_TYPES = {"normal", "restricted", "priority", "blocked"}


class Zone:
    """Un nodo del mapa: un hub normal, el start_hub o el end_hub."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: str = "normal",
        max_drones: int = 1,
        color: Optional[str] = None,
    ):
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.max_drones = max_drones
        self.color = color

    def __repr__(self) -> str:
        return (
            f"Zone(name={self.name!r}, x={self.x}, y={self.y}, "
            f"zone_type={self.zone_type!r}, max_drones={self.max_drones})"
        )
