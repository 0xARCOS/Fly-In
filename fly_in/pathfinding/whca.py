"""Búsqueda cooperativa en espacio-tiempo: WHCA* (SP07).

El estado de búsqueda ya no es `zona` sino `(zona, turno)`. Las reservas de
los drones que planificaron antes son obstáculos que existen solo en ciertos
turnos, y la búsqueda los esquiva sola: una colisión simplemente no está
entre los estados alcanzables.

Usa la convención de tiempo de ReservationTable (SP06): el "instante t" es
el estado tras t turnos; un movimiento que sale en T con coste c llega en
T+c.
"""

import heapq
from dataclasses import dataclass
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
)

from fly_in.models.connection import Connection
from fly_in.models.graph import Graph
from fly_in.models.zone import Zone, ZoneType
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.reservation_table import ReservationTable

DEFAULT_WINDOW = 8


class DroneLike(Protocol):
    """Lo único que la búsqueda necesita saber de un dron.

    El `Drone` de SP08 lo cumple sin heredar de nada; los tests usan un
    dataclass mínimo.
    """

    @property
    def id(self) -> int:
        """Identificador del dron (el N de `DN` en la salida)."""
        ...

    @property
    def current_zone(self) -> Zone:
        """Zona en la que está el dron al empezar a planificar."""
        ...


# Recibe los drones a planificar y el turno actual; devuelve el orden en
# que planifican. Quien va primero se lleva las mejores reservas.
PlanningOrder = Callable[[Sequence[DroneLike], int], List[DroneLike]]


@dataclass(frozen=True, order=True)
class SearchNode:
    """Un estado (zona, turno) en la cola de prioridad de A*.

    El orden de los campos ES el orden del heap: primero `f`, y ante empate
    la ruta con más zonas priority (igual que Dijkstra en SP04), luego `g`,
    `turn` y por último `tie`, un contador que desempata a favor del nodo
    descubierto antes. `zone_name` va detrás de `tie`, así que nunca llega
    a compararse.
    """

    f: int              # g + h
    neg_priority: int   # -(zonas priority en la ruta): más es mejor
    g: int              # turnos gastados desde el inicio de la ventana
    turn: int           # instante absoluto de simulación
    tie: int            # contador incremental, desempate estable
    zone_name: str


@dataclass(frozen=True)
class Step:
    """Un paso de la ruta planificada."""

    zone: Zone                        # dónde acaba este paso
    arrival_turn: int                 # instante absoluto de llegada
    connection: Optional[Connection]  # None si es una espera en el sitio
    cost: int                         # 1, o 2 si el destino es restricted


class WhcaPathfinder:
    """Windowed Hierarchical Cooperative A* (Silver, 2005).

    Busca en espacio-tiempo (zona, turno) respetando las reservas de los
    drones que ya planificaron, dentro de una ventana de `window` turnos.
    Más allá de la ventana confía en la heurística abstracta.
    """

    def __init__(
        self,
        graph: Graph,
        heuristic: AbstractDistance,
        table: ReservationTable,
        window: int = DEFAULT_WINDOW,
        order: Optional[PlanningOrder] = None,
    ) -> None:
        """Prepara el buscador.

        Args:
            graph: Grafo del mapa (con end_hub).
            heuristic: Distancias abstractas al end_hub (SP05).
            table: Tabla de reservas compartida por todos los drones.
            window: Turnos que se miran hacia delante cooperando.
            order: Criterio de prioridad entre drones; por defecto, por id.

        Raises:
            ValueError: Si la ventana no es positiva o el grafo no tiene
                end_hub.
        """
        if window < 1:
            raise ValueError(f"Window must be at least 1, got {window}")
        if graph.end_hub is None:
            raise ValueError("Graph has no end_hub")
        self.graph = graph
        self.heuristic = heuristic
        self.table = table
        self.window = window
        self.order: PlanningOrder = (
            order if order is not None else PlanningOrders.by_id
        )
        self._goal: Zone = graph.end_hub

    # --- API -----------------------------------------------------------

    def plan(
        self, drones: Sequence[DroneLike], start_turn: int
    ) -> Dict[int, List[Step]]:
        """Planifica y graba la ruta de cada dron, en orden de prioridad.

        Cada ruta se graba en la tabla ANTES de planificar la siguiente: si
        no, todos planificarían contra la misma tabla y chocarían.

        Antes de empezar, cada dron reserva quedarse en su zona toda la
        ventana (reserva provisional). Sin ella, quien planifica antes no
        ve a quien aún no lo ha hecho y puede reservar entrar en su zona
        cuando este no tiene por dónde salir. Cada dron cambia su reserva
        provisional por su ruta real justo antes de buscarla, así que
        siempre puede, como mínimo, esperar donde está.

        Returns:
            Ruta de cada dron, por id.
        """
        ordered = self.order(drones, start_turn)
        for drone in ordered:
            self._hold(drone, start_turn)

        paths: Dict[int, List[Step]] = {}
        for drone in ordered:
            self.table.release(drone.id, start_turn)
            path = self.find_path(drone, start_turn)
            self.reserve(drone.id, drone.current_zone, path)
            paths[drone.id] = path
        return paths

    def find_path(self, drone: DroneLike, start_turn: int) -> List[Step]:
        """Ruta del dron desde su posición actual, dentro de la ventana.

        Returns:
            Lista de pasos, posiblemente parcial (hasta el borde de la
            ventana). Nunca vacía salvo que el dron ya esté en end_hub: en
            el peor caso, esperar en el sitio.
        """
        start = drone.current_zone
        if start is self._goal:
            return []
        if not self.heuristic.is_reachable(start):
            return [self._wait_step(start, start_turn)]

        tie = 0
        root = SearchNode(
            f=self.heuristic.h(start),
            neg_priority=0,
            g=0,
            turn=start_turn,
            tie=tie,
            zone_name=start.name,
        )
        open_heap: List[SearchNode] = [root]
        closed: Set[Tuple[str, int]] = set()
        parents: Dict[int, SearchNode] = {}
        best: Optional[SearchNode] = None

        while open_heap:
            node = heapq.heappop(open_heap)
            zone = self.graph.get_zone(node.zone_name)

            # El objetivo se mira ANTES que la ventana: llegar justo en el
            # último turno de la ventana es llegar.
            if zone is self._goal:
                return self._reconstruct(node, parents)

            if node.turn - start_turn >= self.window:
                if best is None or node.f < best.f:
                    best = node
                continue

            state = (node.zone_name, node.turn)
            if state in closed:
                continue
            closed.add(state)

            for target, cost, bonus in self._successors(node, zone):
                tie += 1
                child = SearchNode(
                    f=node.g + cost + self.heuristic.h(target),
                    neg_priority=node.neg_priority - bonus,
                    g=node.g + cost,
                    turn=node.turn + cost,
                    tie=tie,
                    zone_name=target.name,
                )
                parents[tie] = node
                heapq.heappush(open_heap, child)

        if best is None:
            # Encerrado ahora mismo: ni siquiera se alcanza el borde de la
            # ventana. Nunca None: quedarse quieto este turno.
            return [self._wait_step(start, start_turn)]
        return self._reconstruct(best, parents)

    def reserve(
        self, drone_id: int, origin: Zone, path: Sequence[Step]
    ) -> None:
        """Graba `path` en la tabla a nombre de `drone_id`.

        `origin` es la zona en la que está el dron antes del primer paso.

        Raises:
            ReservationError: Si algún paso no cabe (bug de quien llama).
        """
        previous = origin
        for step in path:
            if step.connection is None:
                self.table.reserve_wait(drone_id, step.zone, step.arrival_turn)
            else:
                self.table.reserve_move(
                    drone_id,
                    previous,
                    step.zone,
                    step.arrival_turn - step.cost,
                )
            previous = step.zone

    # --- internos ------------------------------------------------------

    def _hold(self, drone: DroneLike, start_turn: int) -> None:
        """Reserva provisional: `drone` sigue en su zona toda la ventana.

        Se para en el primer instante sin sitio: solo pasa si un dron en
        tránsito (conservado con `keep`) aterriza ahí, y entonces este
        dron tiene que salir antes, cosa que su búsqueda ya tendrá en
        cuenta.
        """
        zone = drone.current_zone
        for turn in range(start_turn + 1, start_turn + self.window + 1):
            if not self.table.zone_has_room(zone, turn):
                return
            self.table.reserve_wait(drone.id, zone, turn)

    def _successors(
        self, node: SearchNode, zone: Zone
    ) -> List[Tuple[Zone, int, int]]:
        """Sucesores legales de `node` como (zona, coste, bonus priority)."""
        result: List[Tuple[Zone, int, int]] = []
        for connection in self.graph.neighbors(zone):
            neighbor = connection.other_end(zone)
            if not neighbor.is_traversable():
                continue
            if not self.heuristic.is_reachable(neighbor):
                continue
            # Conexión y sentido en cada turno del trayecto + zona de llegada.
            if not self.table.can_move(zone, neighbor, node.turn):
                continue
            bonus = 1 if neighbor.zone_type is ZoneType.PRIORITY else 0
            result.append((neighbor, neighbor.movement_cost(), bonus))

        # Esperar en el sitio es un vecino más (Cap. VII.3, "Stay in
        # place"): el único mecanismo para ceder el paso.
        if self.table.zone_has_room(zone, node.turn + 1):
            result.append((zone, 1, 0))
        return result

    def _reconstruct(
        self, node: SearchNode, parents: Dict[int, SearchNode]
    ) -> List[Step]:
        """Convierte la cadena de padres de `node` en pasos."""
        steps: List[Step] = []
        current = node
        while current.tie in parents:
            parent = parents[current.tie]
            zone = self.graph.get_zone(current.zone_name)
            cost = current.turn - parent.turn
            if current.zone_name == parent.zone_name:
                connection: Optional[Connection] = None
            else:
                connection = self.graph.connection_between(
                    self.graph.get_zone(parent.zone_name), zone
                )
            steps.append(Step(zone, current.turn, connection, cost))
            current = parent
        steps.reverse()
        return steps

    @staticmethod
    def _wait_step(zone: Zone, start_turn: int) -> Step:
        """Paso de "quedarse en `zone`" durante el turno `start_turn`."""
        return Step(zone, start_turn + 1, None, 1)


class PlanningOrders:
    """Criterios de prioridad intercambiables para `WhcaPathfinder.plan`.

    Cada criterio es un `PlanningOrder`: recibe los drones y el turno y
    devuelve en qué orden planifican. Los que dependen de la heurística son
    fábricas: reciben `AbstractDistance` y devuelven el criterio.
    """

    @staticmethod
    def by_id(drones: Sequence[DroneLike], turn: int) -> List[DroneLike]:
        """Por id ascendente: determinista y trivial, pero D1 acapara."""
        return sorted(drones, key=lambda drone: drone.id)

    @staticmethod
    def farthest_first(heuristic: AbstractDistance) -> PlanningOrder:
        """Los más lejanos del objetivo (mayor h) eligen primero.

        Empate por id. Suele reducir el turno del último en llegar, que es
        la métrica.
        """
        def order(
            drones: Sequence[DroneLike], turn: int
        ) -> List[DroneLike]:
            """Mayor h primero; empate por id."""
            return sorted(
                drones,
                key=lambda drone: (
                    -PlanningOrders._distance(heuristic, drone.current_zone),
                    drone.id,
                ),
            )
        return order

    @staticmethod
    def nearest_first(heuristic: AbstractDistance) -> PlanningOrder:
        """Los más cercanos al objetivo (menor h) eligen primero.

        Empate por id. Casa bien con la reserva provisional de `plan`: el de
        delante planifica antes y libera su zona, en vez de que el de
        detrás lo vea "quieto".
        """
        def order(
            drones: Sequence[DroneLike], turn: int
        ) -> List[DroneLike]:
            """Menor h primero (inalcanzables al final); empate por id."""
            return sorted(
                drones,
                key=lambda drone: (
                    PlanningOrders._distance(heuristic, drone.current_zone)
                    < 0,
                    PlanningOrders._distance(heuristic, drone.current_zone),
                    drone.id,
                ),
            )
        return order

    @staticmethod
    def rotating(drones: Sequence[DroneLike], turn: int) -> List[DroneLike]:
        """Por id, pero empezando en una posición que avanza con el turno.

        Reparte la ventaja de planificar primero entre replanificaciones.
        """
        ordered = PlanningOrders.by_id(drones, turn)
        if not ordered:
            return ordered
        shift = turn % len(ordered)
        return ordered[shift:] + ordered[:shift]

    @staticmethod
    def _distance(heuristic: AbstractDistance, zone: Zone) -> int:
        """h(zone), o -1 si es inalcanzable (esos planifican al final)."""
        return heuristic.h(zone) if heuristic.is_reachable(zone) else -1
