"""El bucle turno a turno (SP08).

Cada turno tiene tres momentos:

1. Replanificar, si toca: al inicio de cada media ventana, o antes si a
   algún dron se le ha agotado la ruta.
2. Fase 1, DECIDIR: cada dron dice qué hará este turno. Nadie se mueve.
3. Fase 2, APLICAR: todos los movimientos a la vez, y verificación de que
   el nuevo estado respeta las capacidades.

Usa la convención de tiempo de ReservationTable (SP06): el turno `t` lleva
del instante `t` al `t+1`, y es la línea `t+1` de la salida.
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

from fly_in.models.connection import Connection
from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.reservation_table import (
    ReservationError,
    ReservationTable,
)
from fly_in.pathfinding.whca import (
    DEFAULT_WINDOW,
    PlanningOrder,
    Step,
    WhcaPathfinder,
)
from fly_in.simulation.drone import Drone, DroneState
from fly_in.simulation.errors import SimulationError

# Turnos máximos = nb_drones * zonas * MAX_TURNS_FACTOR. Un dron solo tarda
# como mucho 2 por zona (restricted); en fila india, nb_drones veces eso.
# El factor 4 deja el doble de margen sobre ese peor caso razonable.
MAX_TURNS_FACTOR = 4


@dataclass(frozen=True)
class Move:
    """Lo que hizo un dron en un turno, tal como lo necesita la salida.

    `arrives` es False solo en el primer turno de un tránsito hacia una
    restricted: el dron acaba el turno en `connection` (se imprime
    `D<id>-<conexión>`). En el resto de casos acaba en `target`
    (`D<id>-<zona>`).
    """

    drone_id: int
    origin: Zone
    target: Zone
    connection: Connection
    arrives: bool


@dataclass(frozen=True)
class Replan:
    """Una replanificación: cuándo, a cuántos y cuánto costó."""

    turn: int         # instante en que se replanifica
    grounded: int     # drones replanificados
    airborne: int     # drones en el aire, conservados con keep
    seconds: float    # tiempo de cálculo de plan()


class SimulationObserver(Protocol):
    """Quien quiera ver la simulación mientras ocurre (SP10).

    El simulador le avisa tras aplicar cada turno. El observador solo lee:
    no debe modificar los drones.
    """

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence["Drone"]
    ) -> None:
        """`turn` es el número de línea de salida recién completado."""
        ...


class ObserverGroup:
    """Reparte cada turno entre varios observadores (terminal + HTML)."""

    def __init__(self, *observers: SimulationObserver) -> None:
        """Agrupa `observers`, que se llaman en ese orden."""
        self.observers = observers

    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence["Drone"]
    ) -> None:
        """Pasa el turno a cada observador."""
        for observer in self.observers:
            observer.on_turn(turn, moves, drones)


# Decisión de la fase 1: el dron, el paso que ejecuta y el movimiento que
# produce (None = espera en el sitio: no sale en la salida).
Decision = Tuple[Drone, Step, Optional[Move]]


class Simulator:
    """Mueve todos los drones de start_hub a end_hub, turno a turno."""

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        window: int = DEFAULT_WINDOW,
        order: Optional[PlanningOrder] = None,
    ) -> None:
        """Prepara la simulación con `nb_drones` drones en start_hub.

        Raises:
            SimulationError: Si el mapa no tiene start_hub/end_hub o si
                end_hub es inalcanzable: se detecta en el turno 0, no tras
                cientos de turnos dando vueltas.
        """
        if graph.start_hub is None or graph.end_hub is None:
            raise SimulationError("The map needs a start_hub and an end_hub")
        self.graph = graph
        self.heuristic = AbstractDistance(graph)
        if not self.heuristic.is_reachable(graph.start_hub):
            raise SimulationError(
                f"'{graph.end_hub.name}' is unreachable from "
                f"'{graph.start_hub.name}'"
            )
        self.table = ReservationTable(graph)
        self.pathfinder = WhcaPathfinder(
            graph, self.heuristic, self.table, window, order
        )
        self.window = window
        # W // 2: siempre quedan W/2 turnos de cooperación por delante. Con
        # W = 1 sería 0, así que como mínimo se replanifica cada turno.
        self.replan_every = max(1, window // 2)
        self.max_turns = max(
            1, nb_drones * len(graph.zones) * MAX_TURNS_FACTOR
        )
        self.drones: List[Drone] = [
            Drone(drone_id, graph.start_hub)
            for drone_id in range(1, nb_drones + 1)
        ]
        self._goal: Zone = graph.end_hub
        self.elapsed = 0.0   # segundos de cálculo del último run()
        self.replans: List[Replan] = []

    # --- API -----------------------------------------------------------

    def run(
        self, observer: Optional[SimulationObserver] = None
    ) -> List[List[Move]]:
        """Ejecuta la simulación completa.

        Args:
            observer: Se le llama tras cada turno (la visualización).

        Returns:
            La traza: una lista de movimientos por turno. Su longitud es
            el número de turnos, la métrica del subject (Cap. VII.6).

        Raises:
            SimulationError: Si no converge antes de `max_turns`, si la
                planificación no cabe en la tabla o si algún turno viola
                una capacidad (bug de SP06/SP07).
        """
        trace: List[List[Move]] = []
        turn = 0
        started = time.perf_counter()
        watching = 0.0   # tiempo dentro del observador: no es cálculo
        while True:
            active = [drone for drone in self.drones if drone.is_active]
            if not active:
                self.elapsed = time.perf_counter() - started - watching
                return trace
            if turn >= self.max_turns:
                raise SimulationError(self._stuck_message(turn, active))
            if self._must_replan(turn, active):
                self._replan(turn, active)
            decisions = self._decide(turn, active)
            moves = self._apply(decisions)
            self._verify(turn, moves)
            trace.append(moves)
            turn += 1
            if observer is not None:
                paused = time.perf_counter()
                observer.on_turn(turn, moves, self.drones)
                watching += time.perf_counter() - paused

    # --- replanificación -----------------------------------------------

    def _must_replan(self, turn: int, active: Sequence[Drone]) -> bool:
        """¿Toca replanificar al empezar `turn`?

        Cada media ventana, y también si algún dron parado se ha quedado
        sin ruta: esperar sin reserva dejaría su zona libre en la tabla
        para que otro planificara entrar en ella.
        """
        if turn % self.replan_every == 0:
            return True
        return any(not d.in_transit and not d.path for d in active)

    def _replan(self, turn: int, active: Sequence[Drone]) -> None:
        """Olvida el futuro y vuelve a planificar a los drones en tierra.

        Los que están en el aire no se replanifican (no pueden parar ni dar
        la vuelta) y conservan sus reservas con `keep`: su aterrizaje ya
        está comprometido.
        """
        in_transit = {drone.id for drone in active if drone.in_transit}
        self.table.clear_from(turn, keep=in_transit)
        grounded = [drone for drone in active if not drone.in_transit]
        started = time.perf_counter()
        try:
            paths = self.pathfinder.plan(grounded, turn)
        except ReservationError as exc:
            raise SimulationError(
                f"Planning failed at turn {turn}: {exc}"
            ) from exc
        for drone in grounded:
            drone.path = paths[drone.id]
        self.replans.append(Replan(
            turn, len(grounded), len(in_transit),
            time.perf_counter() - started,
        ))

    # --- fase 1: decidir -----------------------------------------------

    def _decide(self, turn: int, active: Sequence[Drone]) -> List[Decision]:
        """Qué hace cada dron este turno. No modifica nada.

        Todas las decisiones se toman contra el mismo estado, así que el
        resultado no depende del orden de la lista de drones.
        """
        decisions: List[Decision] = []
        for drone in active:
            if drone.in_transit:
                decisions.append(self._land(drone, turn))
                continue
            step = drone.next_step(turn)
            if step is None:
                raise SimulationError(
                    f"D{drone.id} has no plan at turn {turn}"
                )
            if step.connection is None:
                decisions.append((drone, step, None))
                continue
            move = Move(
                drone_id=drone.id,
                origin=drone.current_zone,
                target=step.zone,
                connection=step.connection,
                arrives=step.cost == 1,
            )
            decisions.append((drone, step, move))
        return decisions

    @staticmethod
    def _land(drone: Drone, turn: int) -> Decision:
        """Segundo turno de un tránsito: el dron aterriza, sin elección.

        Cap. VII.3: "the drone MUST reach its destination during the next
        turn". No se le pregunta nada: preguntarle abriría la puerta a
        esperar en el aire.
        """
        step = drone.path[0]
        if drone.transit_connection is None or step.arrival_turn != turn + 1:
            raise SimulationError(
                f"D{drone.id} is in transit but cannot land at turn "
                f"{turn + 1}"
            )
        move = Move(
            drone_id=drone.id,
            origin=drone.current_zone,
            target=step.zone,
            connection=drone.transit_connection,
            arrives=True,
        )
        return drone, step, move

    # --- fase 2: aplicar -----------------------------------------------

    def _apply(self, decisions: Sequence[Decision]) -> List[Move]:
        """Ejecuta todas las decisiones a la vez.

        Returns:
            Los movimientos del turno, por id de dron (las esperas no).
        """
        moves: List[Move] = []
        for drone, step, move in decisions:
            if move is None:
                drone.path.pop(0)
                drone.state = DroneState.WAITING
                continue
            moves.append(move)
            if not move.arrives:
                drone.state = DroneState.IN_TRANSIT
                drone.transit_connection = move.connection
                continue
            drone.path.pop(0)
            drone.current_zone = step.zone
            drone.transit_connection = None
            drone.state = (
                DroneState.ARRIVED
                if step.zone is self._goal
                else DroneState.MOVING
            )
        moves.sort(key=lambda move: move.drone_id)
        return moves

    def _verify(self, turn: int, moves: Sequence[Move]) -> None:
        """Recuenta la ocupación tras el turno sin mirar la tabla.

        Si el pathfinder hizo bien su trabajo, esto nunca salta. Si salta,
        es un bug de SP06/SP07, y es mejor saberlo en este turno que tres
        mapas después.

        Raises:
            SimulationError: Si una zona o conexión supera su capacidad.
        """
        in_zone: Dict[str, int] = {}
        for drone in self.drones:
            if drone.is_active and not drone.in_transit:
                name = drone.current_zone.name
                in_zone[name] = in_zone.get(name, 0) + 1
        for name, count in in_zone.items():
            zone = self.graph.get_zone(name)
            if count > zone.max_drones:
                raise SimulationError(
                    f"Turn {turn + 1}: {count} drones in '{name}' "
                    f"(max_drones={int(zone.max_drones)})"
                )

        on_link: Dict[str, int] = {}
        for move in moves:
            name = move.connection.name
            on_link[name] = on_link.get(name, 0) + 1
            if on_link[name] > move.connection.max_link_capacity:
                raise SimulationError(
                    f"Turn {turn + 1}: {on_link[name]} drones on '{name}' "
                    f"(max_link_capacity="
                    f"{move.connection.max_link_capacity})"
                )

    # --- diagnóstico ---------------------------------------------------

    def _stuck_message(self, turn: int, active: Sequence[Drone]) -> str:
        """Mensaje de no-convergencia que nombra a cada dron atascado."""
        where = ", ".join(
            f"D{drone.id} ("
            + (
                f"in transit on {drone.transit_connection.name}"
                if drone.transit_connection is not None
                else f"at {drone.current_zone.name}"
            )
            + ")"
            for drone in active
        )
        return (
            f"Simulation did not converge after {turn} turns. "
            f"Undelivered drones: {where}"
        )
