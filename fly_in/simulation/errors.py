"""Simulation errors."""


class SimulationError(Exception):
    """The simulation could not be completed.

    The message says what happened and to which drones: "does not converge
    after 340 turns; D3 at narrow" can be debugged, a hang cannot.
    """
