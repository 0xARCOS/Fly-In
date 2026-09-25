"""Grafo del mapa: zonas, conexiones y las reglas que las relacionan."""

from typing import Dict, FrozenSet, List, Optional

from fly_in.models.connection import Connection
from fly_in.models.zone import Zone

ROLES = {"hub", "start_hub", "end_hub"}


class Graph:
    """Grafo del mapa: zonas (nodos) y conexiones (aristas) entre ellas.

    Aplica aquí, y no en el parser, las reglas que dependen del estado
    acumulado de todo el archivo:
    - Nombres de zona únicos
    - Como mucho un start_hub y un end_hub
    - connection: solo referencia zonas ya definidas antes en el archivo
    - Sin conexiones duplicadas (a-b == b-a)

    Es inmutable tras el parseo: la ocupación turno a turno vive fuera.
    """

    def __init__(self) -> None:
        """Crea un grafo vacío."""
        self.zones: Dict[str, Zone] = {}
        self.start_hub: Optional[Zone] = None
        self.end_hub: Optional[Zone] = None
        self.connections: List[Connection] = []
        # Índices para que neighbors() y connection_between() sean O(1):
        # el pathfinding los llama en cada expansión.
        self._adjacency: Dict[str, List[Connection]] = {}
        self._by_pair: Dict[FrozenSet[str], Connection] = {}

    def add_zone(self, zone: Zone, role: str) -> None:
        """Añade una zona con su rol ('hub', 'start_hub' o 'end_hub').

        Raises:
            ValueError: Si el rol es desconocido, el nombre está repetido o
                ya existe un start_hub/end_hub.
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
        """Conecta dos zonas ya definidas.

        Raises:
            ValueError: Si alguna zona no existe o la conexión está repetida
                (en cualquiera de los dos sentidos).
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
        """Busca una zona por nombre, o falla con un mensaje claro.

        Raises:
            ValueError: Si no existe ninguna zona con ese nombre.
        """
        if name not in self.zones:
            raise ValueError(f"Unknown zone: '{name}'")
        return self.zones[name]

    def neighbors(self, zone: Zone) -> List[Connection]:
        """Conexiones que tocan `zone`, en el orden en que se definieron.

        Devuelve una copia: modificarla no altera el grafo.
        """
        return list(self._adjacency.get(zone.name, []))

    def connection_between(self, zone_a: Zone, zone_b: Zone) -> Connection:
        """Conexión que une `zone_a` y `zone_b`, en cualquier sentido.

        Raises:
            ValueError: Si las dos zonas no están conectadas.
        """
        pair = frozenset((zone_a.name, zone_b.name))
        if pair not in self._by_pair:
            raise ValueError(
                f"No connection between '{zone_a.name}' and '{zone_b.name}'"
            )
        return self._by_pair[pair]
