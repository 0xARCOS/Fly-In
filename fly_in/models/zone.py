"""Zona del mapa: nodo del grafo con tipo, coordenadas y capacidad."""

from enum import Enum
from typing import Optional


class ZoneType(Enum):
    """Tipo de zona (Cap. VI). El valor es el texto del metadato 'zone='."""

    NORMAL = "normal"
    RESTRICTED = "restricted"
    PRIORITY = "priority"
    BLOCKED = "blocked"


# Turnos que cuesta entrar en una zona según su tipo (Cap. VII.3).
# BLOCKED no aparece: no se puede entrar.
MOVEMENT_COST = {
    ZoneType.NORMAL: 1,
    ZoneType.PRIORITY: 1,
    ZoneType.RESTRICTED: 2,
}

# Capacidad de start_hub/end_hub (Cap. VII.2). Al ser infinito, cualquier
# comparación `ocupación < max_drones` es cierta sin casos especiales.
UNLIMITED = float("inf")


class Zone:
    """Un nodo del mapa: un hub normal, el start_hub o el end_hub."""

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: ZoneType = ZoneType.NORMAL,
        max_drones: float = 1,
        color: Optional[str] = None,
    ) -> None:
        """Crea la zona.

        Args:
            name: Nombre único, sin guiones ni espacios.
            x: Coordenada horizontal (solo para dibujar).
            y: Coordenada vertical (solo para dibujar).
            zone_type: Tipo de la zona.
            max_drones: Drones simultáneos admitidos; UNLIMITED en start/end.
            color: Color opcional para la visualización.
        """
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.max_drones = max_drones
        self.color = color

    def is_traversable(self) -> bool:
        """Devuelve False únicamente para las zonas 'blocked'."""
        return self.zone_type is not ZoneType.BLOCKED

    def movement_cost(self) -> int:
        """Turnos que cuesta entrar en la zona.

        Raises:
            ValueError: Si la zona es 'blocked' (no se puede entrar).
        """
        if not self.is_traversable():
            raise ValueError(
                f"Cannot compute movement cost for blocked zone '{self.name}'"
            )
        return MOVEMENT_COST[self.zone_type]

    def __repr__(self) -> str:
        """Representación legible para depurar."""
        capacity_str = (
            "inf" if self.max_drones == UNLIMITED
            else str(int(self.max_drones))
        )
        return (
            f"Zone(name={self.name!r}, x={self.x}, y={self.y}, "
            f"zone_type={self.zone_type.value!r}, max_drones={capacity_str})"
        )
