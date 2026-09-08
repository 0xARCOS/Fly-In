from typing import Dict, List, Optional, Tuple

from fly_in.models.zone import Zone

ROLES = {"hub", "start_hub", "end_hub"}


class Graph:
    """
    Grafo del mapa: zonas (nodos) y conexiones (aristas) entre ellas.

    Aplica aquí, y no en el parser, las reglas que dependen del estado
    acumulado de todo el archivo:
    - Nombres de zona únicos
    - Exactamente un start_hub y un end_hub
    - connection: solo referencia zonas ya definidas antes en el archivo
    - Sin conexiones duplicadas (a-b == b-a)
    """

    def __init__(self):
        self.zones: Dict[str, Zone] = {}
        self.start_hub: Optional[Zone] = None
        self.end_hub: Optional[Zone] = None
        self.connections: List[Tuple[str, str, int]] = []

    def add_zone(self, zone: Zone, rol: str) -> None:
        if rol not in ROLES:
            raise ValueError(f"Unknown zone role: '{rol}'")

        if zone.name in self.zones:
            raise ValueError(f"Zone name '{zone.name}' is already defined")

        if rol == "start_hub":
            if self.start_hub is not None:
                raise ValueError("Only one 'start_hub' is allowed")
            self.start_hub = zone
        elif rol == "end_hub":
            if self.end_hub is not None:
                raise ValueError("Only one 'end_hub' is allowed")
            self.end_hub = zone

        self.zones[zone.name] = zone

    def add_connection(
        self, origin: str, destination: str, max_link_capacity: int
    ) -> None:
        if origin not in self.zones:
            raise ValueError(
                f"Connection references undefined zone: '{origin}'"
            )
        if destination not in self.zones:
            raise ValueError(
                f"Connection references undefined zone: '{destination}'"
            )

        for a, b, _ in self.connections:
            if {a, b} == {origin, destination}:
                raise ValueError(
                    f"Duplicate connection between "
                    f"'{origin}' and '{destination}'"
                )

        self.connections.append((origin, destination, max_link_capacity))
