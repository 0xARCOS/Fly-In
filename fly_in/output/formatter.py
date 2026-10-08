"""Output format of the subject, character by character (SP09, Chap. VII.5).

- One line per turn, with the moves separated by a single space.
- `D<id>-<zone>` when arriving at a zone; `D<id>-<connection>` on the first
  turn of a transit towards a restricted zone.
- Drones that do not move are omitted; delivered drones never reappear.
- Order within a line: ascending drone id.
"""

from typing import List, Sequence

from fly_in.simulation.simulator import Move


class OutputFormatter:
    """Turn the simulator trace into the lines of the subject."""

    @staticmethod
    def format_move(move: Move) -> str:
        """One move: 'D1-roof1', or 'D1-hub-roof1' if still in the air.

        The connection name is the one from the map file, not oriented:
        traversing it backwards prints the same name.
        """
        target = move.target.name if move.arrives else move.connection.name
        return f"D{move.drone_id}-{target}"

    @classmethod
    def format_turn(cls, moves: Sequence[Move]) -> str:
        """One turn line, sorted by id. Empty if nobody moved."""
        ordered = sorted(moves, key=lambda move: move.drone_id)
        return " ".join(cls.format_move(move) for move in ordered)

    @classmethod
    def format_trace(cls, trace: Sequence[Sequence[Move]]) -> List[str]:
        """Every line of the simulation.

        A turn with no moves produces no line: the state before and after
        is identical (a drone in the air always lands, so nobody can be in
        transit), so omitting it does not change the legality of the
        following turns. That way the number of lines is always the number
        of turns that count.
        """
        lines = (cls.format_turn(moves) for moves in trace)
        return [line for line in lines if line]
