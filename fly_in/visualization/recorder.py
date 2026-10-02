"""Grabación de una simulación, turno a turno (SP10).

`ReplayRecorder` es un observador del simulador: tras cada turno guarda
dónde está cada dron y la línea de `stdout` de ese turno. Las vistas que
enseñan la partida después de simularla (la ventana y el log) leen de aquí:
ninguna vuelve a calcular nada.
"""

from typing import Dict, List, Sequence

from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move

# Posición de un dron: ["z", zona] | ["a", origen, destino] (en el aire)
# | ["d"] (entregado).
Position = List[str]


class ReplayRecorder:
    """Guarda un fotograma por turno: posiciones y línea de salida."""

    def __init__(self, drones: Sequence[Drone]) -> None:
        """Fotograma 0: todos los drones donde empiezan."""
        start = self._positions(drones)
        self.positions: List[Dict[str, Position]] = [start]
        self.lines: List[str] = [""]

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Añade el fotograma del turno `turn`."""
        line = [
            f"D{m.drone_id}-"
            + (m.target.name if m.arrives else m.connection.name)
            for m in sorted(moves, key=lambda m: m.drone_id)
        ]
        positions = self._positions(drones)
        self.positions.append(positions)
        self.lines.append(" ".join(line))

    @staticmethod
    def _positions(drones: Sequence[Drone]) -> Dict[str, Position]:
        """Dónde está cada dron ahora mismo."""
        result: Dict[str, Position] = {}
        for drone in drones:
            if not drone.is_active:
                result[str(drone.id)] = ["d"]
            elif drone.in_transit and drone.path:
                result[str(drone.id)] = [
                    "a", drone.current_zone.name, drone.path[0].zone.name
                ]
            else:
                result[str(drone.id)] = ["z", drone.current_zone.name]
        return result
