"""Recording of a simulation, turn by turn (SP10).

`ReplayRecorder` is a simulator observer: after each turn it stores where
each drone is and the `stdout` line of that turn. The views that show the
run after simulating it (the window and the log) read from here: none of
them computes anything again.
"""

from typing import Dict, List, Sequence

from fly_in.simulation.drone import Drone
from fly_in.simulation.simulator import Move

# Position of a drone: ["z", zone] | ["a", origin, target] (in the air)
# | ["d"] (delivered).
Position = List[str]


class ReplayRecorder:
    """Store one frame per turn: positions and output line."""

    def __init__(self, drones: Sequence[Drone]) -> None:
        """Frame 0: every drone where it starts."""
        start = self._positions(drones)
        self.positions: List[Dict[str, Position]] = [start]
        self.lines: List[str] = [""]

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None:
        """Append the frame of turn `turn`."""
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
        """Where each drone is right now."""
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
