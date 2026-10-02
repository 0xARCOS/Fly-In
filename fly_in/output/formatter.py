"""Formato de salida del subject, carácter a carácter (SP09, Cap. VII.5).

- Una línea por turno, con los movimientos separados por un espacio.
- `D<id>-<zona>` al llegar a una zona; `D<id>-<conexión>` en el primer
  turno de un tránsito hacia una restricted.
- Los drones que no se mueven se omiten; los entregados no reaparecen.
- Orden dentro de la línea: por id de dron ascendente.
"""

from typing import Any, List, Sequence

from fly_in.simulation.simulator import Move
from fly_in.visualization.palette import Palette


class OutputFormatter:
    """Convierte la traza del simulador en las líneas del subject."""

    @staticmethod
    def format_move(move: Move) -> str:
        """Un movimiento: 'D1-roof1', o 'D1-hub-roof1' si sigue en el aire.

        El nombre de la conexión es el del archivo de mapa, sin orientar:
        recorrerla al revés imprime el mismo nombre.
        """
        target = move.target.name if move.arrives else move.connection.name
        return f"D{move.drone_id}-{target}"

    @classmethod
    def format_turn(cls, moves: Sequence[Move]) -> str:
        """Una línea de turno, ordenada por id. Vacía si nadie se movió."""
        ordered = sorted(moves, key=lambda move: move.drone_id)
        return " ".join(cls.format_move(move) for move in ordered)

    @classmethod
    def format_trace(cls, trace: Sequence[Sequence[Move]]) -> List[str]:
        """Todas las líneas de la simulación.

        Un turno sin movimientos no produce línea: el estado antes y después
        es idéntico (un dron en el aire siempre aterriza, así que no puede
        haber nadie en tránsito), por lo que omitirlo no cambia la
        legalidad de los turnos siguientes. Así el número de líneas es
        siempre el número de turnos que cuentan.
        """
        lines = (cls.format_turn(moves) for moves in trace)
        return [line for line in lines if line]

    @staticmethod
    def format_move_colored(
        move: Move, paint: Any
    ) -> str:
        """Un movimiento coloreado por id de dron.

        Usa Palette para colorear el ID del dron según drone_color.
        """
        drone_id_str = f"D{move.drone_id}"
        target = (
            move.target.name if move.arrives else move.connection.name
        )
        colored_drone = paint(
            drone_id_str,
            fg=Palette.drone_color(move.drone_id),
        )
        return f"{colored_drone}-{target}"

    @classmethod
    def format_turn_colored(
        cls, moves: Sequence[Move], paint: Any
    ) -> str:
        """Una línea de turno coloreada, ordenada por id."""
        ordered = sorted(moves, key=lambda move: move.drone_id)
        colored_moves = [
            cls.format_move_colored(move, paint) for move in ordered
        ]
        return " ".join(colored_moves)

    @classmethod
    def format_trace_colored(
        cls, trace: Sequence[Sequence[Move]], paint: Any
    ) -> List[str]:
        """Todas las líneas coloreadas.

        Misma lógica que format_trace, pero cada dron tiene color.
        """
        lines = (
            cls.format_turn_colored(moves, paint) for moves in trace
        )
        return [line for line in lines if line]
