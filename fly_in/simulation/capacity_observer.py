"""Observer que muestra información de capacidades durante la simulación."""

import sys
from typing import Sequence

from fly_in.models.graph import Graph
from fly_in.simulation.drone import Drone, DroneState
from fly_in.simulation.simulator import Move, SimulationObserver


class CapacityObserver(SimulationObserver):
    """Muestra capacidades de zonas y conexiones después de cada turno."""

    def __init__(self, graph: Graph) -> None:
        """Inicializa el observer con la información del grafo."""
        self.graph = graph

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Imprime información de capacidades para este turno."""
        # Contar drones en cada zona
        zone_occupancy: dict[str, int] = {}
        for drone in drones:
            # Solo contar drones activos que no están en tránsito
            if drone.is_active and not drone.in_transit:
                zone_name = drone.current_zone.name
                zone_occupancy[zone_name] = zone_occupancy.get(zone_name, 0) + 1

        # Mostrar información de zonas
        print(f"=== Turn {turn} - Zone Capacity ===", file=sys.stderr)
        for zone_name, count in sorted(zone_occupancy.items()):
            zone = self.graph.zones.get(zone_name)
            if zone:
                max_drones = zone.max_drones
                status = f"{zone_name}: {count}/{max_drones} drones"
                print(status, file=sys.stderr)

        # Mostrar información de conexiones (basado en los movimientos)
        connection_usage: dict[str, int] = {}
        for move in moves:
            conn_name = move.connection.name
            connection_usage[conn_name] = connection_usage.get(conn_name, 0) + 1

        if connection_usage:
            print(f"--- Connection Capacity ---", file=sys.stderr)
            for conn_name, count in sorted(connection_usage.items()):
                # Buscar la conexión en la lista
                for connection in self.graph.connections:
                    if connection.name == conn_name:
                        max_capacity = connection.max_link_capacity
                        status = f"{conn_name}: {count}/{max_capacity} capacity used"
                        print(status, file=sys.stderr)
                        break
        print(file=sys.stderr)
