"""Errores de la simulación."""


class SimulationError(Exception):
    """La simulación no pudo completarse.

    El mensaje dice qué pasó y con qué drones: "no converge tras 340
    turnos; D3 en narrow" es depurable, un cuelgue no.
    """
