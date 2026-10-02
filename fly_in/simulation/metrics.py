"""Métricas secundarias de una simulación (Cap. VII.6, SP11).

Se calculan a partir de la traza, no del estado interno del simulador: son
las mismas cifras que obtendría alguien que solo leyera la salida.
"""

from dataclasses import dataclass
from typing import Dict, Sequence

from fly_in.simulation.simulator import Move


@dataclass(frozen=True)
class Metrics:
    """Resumen numérico de una simulación terminada."""

    turns: int                   # la nota: líneas de salida
    drones: int
    total_moves: int             # coste total de ruta: turnos-dron en marcha
    total_waits: int             # turnos-dron parado antes de entregar
    avg_moves_per_turn: float    # eficiencia del reparto
    avg_turns_per_drone: float   # turno medio de entrega
    peak_airborne: int           # máximo de drones en el aire a la vez
    seconds: float = 0.0         # tiempo de cálculo (lo mide quien llama)

    @classmethod
    def from_trace(
        cls,
        trace: Sequence[Sequence[Move]],
        nb_drones: int,
        seconds: float = 0.0,
    ) -> "Metrics":
        """Calcula las métricas de `trace` (una lista de Move por turno)."""
        turns = sum(1 for moves in trace if moves)
        total_moves = sum(len(moves) for moves in trace)
        delivered_at: Dict[int, int] = {}
        peak_airborne = 0
        for number, moves in enumerate(trace, start=1):
            airborne = sum(1 for move in moves if not move.arrives)
            peak_airborne = max(peak_airborne, airborne)
            # La última llegada de cada dron es su entrega en end_hub.
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
