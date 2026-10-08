"""Secondary metrics of a simulation (Chap. VII.6, SP11).

They are computed from the trace, not from the simulator's internal state:
they are the same figures someone reading only the output would get.
"""

from dataclasses import dataclass
from typing import Dict, Sequence

from fly_in.simulation.simulator import Move


@dataclass(frozen=True)
class Metrics:
    """Numeric summary of a finished simulation."""

    turns: int                   # the score: output lines
    drones: int
    total_moves: int             # total path cost: drone-turns in motion
    total_waits: int             # drone-turns standing still before delivery
    avg_moves_per_turn: float    # how well the work is spread
    avg_turns_per_drone: float   # average delivery turn
    peak_airborne: int           # most drones in the air at the same time
    seconds: float = 0.0         # compute time (measured by the caller)

    @classmethod
    def from_trace(
        cls,
        trace: Sequence[Sequence[Move]],
        nb_drones: int,
        seconds: float = 0.0,
    ) -> "Metrics":
        """Compute the metrics of `trace` (one list of Move per turn)."""
        turns = sum(1 for moves in trace if moves)
        total_moves = sum(len(moves) for moves in trace)
        delivered_at: Dict[int, int] = {}
        peak_airborne = 0
        for number, moves in enumerate(trace, start=1):
            airborne = sum(1 for move in moves if not move.arrives)
            peak_airborne = max(peak_airborne, airborne)
            # The last arrival of each drone is its delivery at end_hub.
            for move in moves:
                if move.arrives:
                    delivered_at[move.drone_id] = number
        arrivals = sum(delivered_at.values())
        return cls(
            turns=turns,
            drones=nb_drones,
            total_moves=total_moves,
            total_waits=arrivals - total_moves,
            avg_moves_per_turn=total_moves / turns if turns else 0.0,
            avg_turns_per_drone=arrivals / nb_drones if nb_drones else 0.0,
            peak_airborne=peak_airborne,
            seconds=seconds,
        )
