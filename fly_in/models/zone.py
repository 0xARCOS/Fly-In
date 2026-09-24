from typing import Optional, Set

# Único juego de valores válido para el metadato 'zone=' (ver checklist
# de map_parser.py).
ALLOWED_ZONE_TYPES = {"normal", "restricted", "priority", "blocked"}
MOVEMENT_COST = {"normal": 1, "priority": 1, "restricted": 2}

class Zone:
    """Un nodo del mapa: un hub normal, el start_hub o el end_hub."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: str = "normal",
        max_drones: float = 1,
        color: Optional[str] = None,
    ):
        if zone_type not in ALLOWED_ZONE_TYPES:
            raise ValueError(f"Invalid zone type: '{zone_type}'")

        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.max_drones = max_drones
        self.color = color
        self.neighbors: Set["Zone"] = set()  # Adyacentes


    def is_travelsable(self) -> bool:
        """Devuelve False únicamente para las zonas 'blocked'."""
        return self.zone_type != "blocked"
    

    def movement_cost(self) -> int:
        """Turnos que cuesta entrar a la zona"""
        if not self.is_traversable():
            raise ValueError(
                f"Cannot compute movement cost for blocked zone '{self.name}'"
            )
        return MOVEMENT_COST[self.zone_type]


    def __repr__(self) -> str:
        capacity_str = (
            "inf" if self.max_drones == float("inf") else str(int(self.max_drones))
        )
        return (
            f"Zone(name={self.name!r}, x={self.x}, y={self.y}, "
            f"zone_type={self.zone_type!r}, max_drones={capacity_str})"
        )
