"""Tests de WhcaPathfinder (SP07).

Mismo orden que docs/build/SP07-whca.md: cada bloque solo tiene sentido si
el anterior pasa. Convención de tiempo de SP06: "instante t" = estado tras
t turnos; un movimiento que sale en T con coste c llega en T+c.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pytest

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.dijkstra import Dijkstra
from fly_in.pathfinding.reservation_table import (
    ReservationError,
    ReservationTable,
)
from fly_in.pathfinding.whca import (
    DroneLike,
    SearchNode,
    Step,
    PlanningOrders,
    WhcaPathfinder,
)

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
VALID_MAPS = sorted(p.name for p in (MAPS_DIR / "valid").glob("*.txt"))
OFFICIAL_MAPS = sorted(
    str(p.relative_to(MAPS_DIR))
    for p in (MAPS_DIR / "oficial_maps").glob("*/*.txt")
)


@dataclass(frozen=True)
class FakeDrone:
    """Lo mínimo que pide DroneLike; el Drone real llega en SP08."""

    id: int
    current_zone: Zone


def load_graph(relative: str) -> Graph:
    """Parsea un mapa de maps/ por ruta relativa."""
    return MapParser.parse((MAPS_DIR / relative).read_text())[1]


def make_finder(graph: Graph, window: int = 8) -> WhcaPathfinder:
    """Buscador con tabla vacía sobre `graph`."""
    return WhcaPathfinder(
        graph, AbstractDistance(graph), ReservationTable(graph), window
    )


def start_of(graph: Graph) -> Zone:
    """start_hub (estrecha Optional para mypy)."""
    assert graph.start_hub is not None
    return graph.start_hub


def drones_at_start(graph: Graph, count: int) -> List[FakeDrone]:
    """`count` drones en start_hub, con ids 1..count."""
    return [FakeDrone(i, start_of(graph)) for i in range(1, count + 1)]


def moves(path: Sequence[Step]) -> List[str]:
    """Zonas visitadas por la ruta, sin las esperas."""
    return [step.zone.name for step in path if step.connection is not None]


def positions(
    origin: Zone, start_turn: int, path: Sequence[Step]
) -> Dict[int, Optional[str]]:
    """Dónde está el dron en cada instante (None = en el aire)."""
    where: Dict[int, Optional[str]] = {start_turn: origin.name}
    for step in path:
        for in_air in range(step.arrival_turn - step.cost + 1,
                            step.arrival_turn):
            where[in_air] = None
        where[step.arrival_turn] = step.zone.name
    return where


def assert_path_is_well_formed(
    graph: Graph, origin: Zone, start_turn: int, path: Sequence[Step]
) -> None:
    """Turnos contiguos, costes coherentes y conexiones reales."""
    previous, turn = origin, start_turn
    for step in path:
        assert step.arrival_turn == turn + step.cost
        if step.connection is None:
            assert step.zone is previous and step.cost == 1
        else:
            assert step.connection is graph.connection_between(
                previous, step.zone
            )
            assert step.cost == step.zone.movement_cost()
        previous, turn = step.zone, step.arrival_turn


# --- el nodo de búsqueda -----------------------------------------------

def test_search_node_orders_by_f_first() -> None:
    cheap = SearchNode(f=3, neg_priority=0, g=9, turn=9, tie=9,
                       zone_name="z")
    deep = SearchNode(f=4, neg_priority=-5, g=0, turn=0, tie=0,
                      zone_name="a")
    assert cheap < deep


def test_search_node_breaks_f_ties_by_priority_then_discovery() -> None:
    plain = SearchNode(f=3, neg_priority=0, g=1, turn=1, tie=1,
                       zone_name="a")
    priority = SearchNode(f=3, neg_priority=-1, g=1, turn=1, tie=2,
                          zone_name="b")
    later = SearchNode(f=3, neg_priority=0, g=1, turn=1, tie=3,
                       zone_name="a")
    assert priority < plain < later


def test_window_must_be_positive() -> None:
    graph = load_graph("valid/linear.txt")
    with pytest.raises(ValueError):
        make_finder(graph, window=0)


# --- 1. un dron, tabla vacía: replica a Dijkstra -----------------------

@pytest.mark.parametrize("map_file", VALID_MAPS)
def test_single_drone_matches_dijkstra(map_file: str) -> None:
    graph = load_graph(f"valid/{map_file}")
    finder = make_finder(graph, window=50)
    start = start_of(graph)
    assert graph.end_hub is not None
    expected = Dijkstra(graph).find_path(start, graph.end_hub)
    assert expected is not None

    path = finder.find_path(FakeDrone(1, start), 0)

    assert moves(path) == [zone.name for zone in expected[1:]]
    assert all(step.connection is not None for step in path), "sin esperas"
    assert path[-1].arrival_turn == Dijkstra(graph).path_cost(expected)
    assert_path_is_well_formed(graph, start, 0, path)


@pytest.mark.parametrize("map_file", OFFICIAL_MAPS)
def test_single_drone_matches_dijkstra_cost_on_official_maps(
    map_file: str,
) -> None:
    # En los oficiales puede haber varias rutas óptimas: se compara el coste.
    graph = load_graph(map_file)
    finder = make_finder(graph, window=200)
    start = start_of(graph)
    assert graph.end_hub is not None
    expected = Dijkstra(graph).find_path(start, graph.end_hub)
    assert expected is not None

    path = finder.find_path(FakeDrone(1, start), 0)

    assert path[-1].zone is graph.end_hub
    assert path[-1].arrival_turn == Dijkstra(graph).path_cost(expected)
    assert_path_is_well_formed(graph, start, 0, path)


def test_start_turn_is_absolute() -> None:
    graph = load_graph("valid/linear.txt")
    path = make_finder(graph).find_path(FakeDrone(1, start_of(graph)), 10)
    assert [step.arrival_turn for step in path] == [11, 12, 13]


def test_drone_already_at_goal_has_nothing_to_do() -> None:
    graph = load_graph("valid/linear.txt")
    assert graph.end_hub is not None
    assert make_finder(graph).find_path(FakeDrone(1, graph.end_hub), 0) == []


# --- 2. un dron, mapa con blocked --------------------------------------

def test_single_drone_goes_around_blocked_zone() -> None:
    graph = load_graph("valid/blocked_detour.txt")
    path = make_finder(graph).find_path(FakeDrone(1, start_of(graph)), 0)
    assert moves(path) == ["detour1", "detour2", "goal"]
    assert "blocker" not in moves(path)


# --- 3-5. bottleneck.txt ----------------------------------------------

def test_second_drone_waits_one_turn_and_passes() -> None:
    graph = load_graph("valid/bottleneck.txt")
    finder = make_finder(graph)

    paths = finder.plan(drones_at_start(graph, 2), 0)

    assert moves(paths[1]) == ["narrow", "goal"]
    assert [s.arrival_turn for s in paths[1]] == [1, 2]
    first = paths[2][0]
    assert first.connection is None and first.zone.name == "start"
    assert moves(paths[2]) == ["narrow", "goal"]
    assert paths[2][-1].arrival_turn == 3


def test_two_drones_never_share_narrow() -> None:
    graph = load_graph("valid/bottleneck.txt")
    finder = make_finder(graph)
    start = start_of(graph)

    paths = finder.plan(drones_at_start(graph, 2), 0)

    timelines = [positions(start, 0, path) for path in paths.values()]
    last = max(max(t) for t in timelines)
    for turn in range(last + 1):
        in_narrow = sum(1 for t in timelines if t.get(turn) == "narrow")
        assert in_narrow <= 1, f"dos drones en narrow en el instante {turn}"


def test_three_drones_all_arrive_taking_turns() -> None:
    graph = load_graph("valid/bottleneck.txt")
    finder = make_finder(graph)

    paths = finder.plan(drones_at_start(graph, 3), 0)

    assert all(path[-1].zone is graph.end_hub for path in paths.values())
    arrivals = sorted(path[-1].arrival_turn for path in paths.values())
    assert arrivals == [2, 3, 4]
    narrow_turns = sorted(
        step.arrival_turn
        for path in paths.values()
        for step in path
        if step.zone.name == "narrow"
    )
    assert narrow_turns == [1, 2, 3], "uno por turno, sin huecos"


def test_plan_records_every_path_in_the_table() -> None:
    graph = load_graph("valid/bottleneck.txt")
    finder = make_finder(graph)

    finder.plan(drones_at_start(graph, 3), 0)

    narrow = graph.get_zone("narrow")
    for turn, drone in ((1, 1), (2, 2), (3, 3)):
        assert finder.table.zone_occupants(narrow, turn) == [drone]


def test_drones_split_between_equal_corridors() -> None:
    graph = load_graph("valid/two_corridors.txt")
    finder = make_finder(graph)

    paths = finder.plan(drones_at_start(graph, 2), 0)

    assert moves(paths[1]) == ["a1", "a2", "goal"]
    assert moves(paths[2]) == ["b1", "b2", "goal"]
    assert paths[1][-1].arrival_turn == paths[2][-1].arrival_turn == 3


# --- 6. ventana pequeña: ruta parcial ---------------------------------

def test_small_window_returns_partial_path() -> None:
    graph = load_graph("valid/linear.txt")
    finder = make_finder(graph, window=2)

    path = finder.find_path(FakeDrone(1, start_of(graph)), 0)

    assert path, "nunca vacía"
    assert moves(path) == ["waypoint1", "waypoint2"]
    assert path[-1].arrival_turn == 2
    assert path[-1].zone is not graph.end_hub


def test_goal_reached_exactly_at_window_edge_counts_as_arrival() -> None:
    graph = load_graph("valid/linear.txt")
    finder = make_finder(graph, window=3)
    path = finder.find_path(FakeDrone(1, start_of(graph)), 0)
    assert moves(path) == ["waypoint1", "waypoint2", "goal"]


def test_partial_path_can_be_recorded() -> None:
    graph = load_graph("valid/linear.txt")
    finder = make_finder(graph, window=2)
    finder.plan(drones_at_start(graph, 2), 0)
    # Ambos caben: el segundo sale un turno después.
    assert finder.table.zone_occupants(graph.get_zone("waypoint2"), 2) == [1]
    assert finder.table.zone_occupants(graph.get_zone("waypoint1"), 2) == [2]


# --- 7. dron encerrado -------------------------------------------------

ENCLOSED_MAP = """\
nb_drones: 3
start_hub: start 0 0
end_hub: goal 3 0
hub: left 1 0
hub: cell 2 0
hub: right 3 1
connection: start-left
connection: left-cell
connection: cell-right
connection: right-goal
"""


def test_enclosed_drone_waits_in_place() -> None:
    graph = MapParser.parse(ENCLOSED_MAP)[1]
    finder = make_finder(graph, window=4)
    cell = graph.get_zone("cell")
    for turn in range(0, 7):
        finder.table.reserve_wait(8, graph.get_zone("left"), turn)
        finder.table.reserve_wait(9, graph.get_zone("right"), turn)

    path = finder.find_path(FakeDrone(1, cell), 0)

    assert path, "nunca vacía"
    assert all(step.connection is None and step.zone is cell
               for step in path)
    assert path[0].arrival_turn == 1
    finder.reserve(1, cell, path)  # esperar sí cabe en la tabla


def test_fully_enclosed_drone_gets_single_wait_step() -> None:
    # Ni siquiera puede quedarse: otro dron tiene reservada su zona.
    graph = MapParser.parse(ENCLOSED_MAP)[1]
    finder = make_finder(graph)
    cell = graph.get_zone("cell")
    for turn in range(0, 3):
        finder.table.reserve_wait(8, graph.get_zone("left"), turn)
        finder.table.reserve_wait(9, graph.get_zone("right"), turn)
    finder.table.reserve_wait(7, cell, 1)

    path = finder.find_path(FakeDrone(1, cell), 0)

    assert path == [Step(cell, 1, None, 1)]


# --- 8. ruta por restricted -------------------------------------------

def test_restricted_transit_reserves_link_two_consecutive_turns() -> None:
    graph = load_graph("valid/restricted_chain.txt")
    finder = make_finder(graph)
    start = start_of(graph)

    paths = finder.plan([FakeDrone(1, start)], 0)

    first = paths[1][0]
    assert first.zone.name == "r1"
    assert first.cost == 2 and first.arrival_turn == 2
    assert first.connection is not None
    link = first.connection
    assert finder.table.link_occupants(link, 0) == [1]
    assert finder.table.link_occupants(link, 1) == [1]
    assert finder.table.link_occupants(link, 2) == []
    assert [s.arrival_turn for s in paths[1]] == [2, 4, 5]


def test_second_drone_cannot_enter_link_mid_transit() -> None:
    graph = load_graph("valid/restricted_chain.txt")
    finder = make_finder(graph)

    paths = finder.plan(drones_at_start(graph, 2), 0)

    # D1 ocupa start-r1 (capacidad 1) entre 0 y 2: D2 no puede entrar en
    # la conexión hasta el 2, aunque r1 esté libre antes.
    second = [s for s in paths[2] if s.connection is not None][0]
    assert second.zone.name == "r1"
    assert second.arrival_turn - second.cost == 2


# --- 9. swap_corridor.txt: el caso patológico --------------------------
#
# Qué pasa, documentado:
#
# a) Con un único end_hub y una h exacta, dos drones que planifican con
#    tabla vacía NUNCA quieren cruzar el mismo pasillo en sentidos
#    opuestos: si A fuera oeste→este y B este→oeste, tendría que ser a la
#    vez h(oeste) > h(este) y h(este) > h(oeste). El cruce de frente solo
#    aparece cuando un dron se ha apartado (va "hacia atrás").
# b) Si un dron cruza el pasillo hacia el otro y el que espera en la otra
#    punta tiene sitio donde quedarse, la regla anti-cruce (would_swap) lo
#    hace esperar hasta que el pasillo queda libre. Funciona.
# c) LIMITACIÓN de find_path en solitario: si quien viene de frente
#    reservó aterrizar justo en la zona (capacidad 1) donde está el otro,
#    y ese otro no está en la tabla porque planifica después, el segundo
#    queda encerrado: no puede cruzar (swap) ni quedarse (zona llena).
#    find_path devuelve la espera de último recurso, que NO cabe en la
#    tabla. plan() lo evita con la reserva provisional: ver los tests de
#    "posición actual de quien aún no ha planificado".

def test_swap_corridor_both_planned_never_meet_head_on() -> None:
    graph = load_graph("valid/swap_corridor.txt")
    finder = make_finder(graph)
    east = graph.get_zone("east")

    paths = finder.plan([FakeDrone(1, east), FakeDrone(2, start_of(graph))],
                        0)

    assert moves(paths[1]) == ["mid", "west", "goal"]
    assert moves(paths[2])[-1] == "goal"
    assert "mid" not in moves(paths[2])


SWAP_WITH_ROOM = (MAPS_DIR / "valid" / "swap_corridor.txt").read_text() \
    .replace("hub: east 3 0", "hub: east 3 0 [max_drones=2]")


def test_swap_corridor_head_on_waits_until_corridor_clears() -> None:
    graph = MapParser.parse(SWAP_WITH_ROOM)[1]
    finder = make_finder(graph)
    west, mid, east = (graph.get_zone(n) for n in ("west", "mid", "east"))
    # D9 se aparta hacia el este: west→mid (sale 0), mid→east (sale 1).
    finder.table.reserve_move(9, west, mid, 0)
    finder.table.reserve_move(9, mid, east, 1)

    path = finder.find_path(FakeDrone(1, east), 0)

    waits = [s for s in path if s.connection is None]
    first_move = [s for s in path if s.connection is not None][0]
    assert len(waits) == 2, "espera a que D9 salga del pasillo"
    assert first_move.zone is mid
    assert first_move.arrival_turn - first_move.cost == 2
    finder.reserve(1, east, path)  # y la ruta cabe: sin cruce de frente


def test_swap_corridor_known_limitation_unreservable_wait() -> None:
    graph = load_graph("valid/swap_corridor.txt")
    finder = make_finder(graph)
    west, mid, east = (graph.get_zone(n) for n in ("west", "mid", "east"))
    finder.table.reserve_move(9, west, mid, 0)
    finder.table.reserve_move(9, mid, east, 1)  # aterriza en east en 2

    path = finder.find_path(FakeDrone(1, east), 0)

    assert path == [Step(east, 1, None, 1)]
    # Esperar un turno sí cabe, pero en el 2 D9 llega a east (cap 1) y D1
    # no tiene adónde ir: ni mid (cruce) ni quedarse (lleno).
    finder.reserve(1, east, path)
    assert not finder.table.zone_has_room(east, 2)
    assert not finder.table.can_move(east, mid, 1)
    with pytest.raises(ReservationError):
        finder.table.reserve_wait(1, east, 2)


# --- posición actual de quien aún no ha planificado -------------------
#
# D2 está en `cell` y no puede salir: `right` está ocupada por un dron
# externo (p. ej. uno en tránsito conservado con `keep`) y por `left` viene
# D1. Si D1 planifica sin saber que D2 está en `cell`, reserva entrar ahí y
# D2 queda sin salida: ni cruzarse con D1 ni quedarse (zona llena).

def blocked_cell_setup(window: int = 8) -> WhcaPathfinder:
    """ENCLOSED_MAP con `right` ocupada por el dron 9 en 1..window+1."""
    graph = MapParser.parse(ENCLOSED_MAP)[1]
    finder = make_finder(graph, window)
    for turn in range(1, window + 2):
        finder.table.reserve_wait(9, graph.get_zone("right"), turn)
    return finder


def test_plan_does_not_let_earlier_drone_trap_a_later_one() -> None:
    finder = blocked_cell_setup()
    graph = finder.graph
    cell = graph.get_zone("cell")
    d1 = FakeDrone(1, graph.get_zone("left"))
    d2 = FakeDrone(2, cell)

    paths = finder.plan([d1, d2], 0)  # no lanza ReservationError

    assert all(s.connection is None and s.zone is cell for s in paths[2])
    assert "cell" not in moves(paths[1][:finder.window])
    for turn in range(1, finder.window + 1):
        assert finder.table.zone_occupants(cell, turn) == [2]


def test_plan_holds_do_not_outlive_planning() -> None:
    # Las reservas provisionales se sustituyen por la ruta real: un dron
    # que se va deja libre su zona para los que planifican antes que él.
    graph = load_graph("valid/linear.txt")
    finder = make_finder(graph)
    w1, w2 = graph.get_zone("waypoint1"), graph.get_zone("waypoint2")

    paths = finder.plan([FakeDrone(1, w2), FakeDrone(2, w1)], 0)

    assert moves(paths[1]) == ["goal"]
    assert moves(paths[2]) == ["waypoint2", "goal"]
    assert paths[2][-1].arrival_turn == 2
    assert finder.table.zone_occupants(w1, 1) == []


def test_plan_with_hold_blocking_earlier_planner_waits_not_crashes() -> None:
    # Orden inverso: el de detrás planifica primero y encuentra al de
    # delante "quieto". Espera; no choca. Es el coste de la reserva
    # provisional (ver nearest_first).
    graph = load_graph("valid/linear.txt")
    finder = WhcaPathfinder(
        graph, AbstractDistance(graph), ReservationTable(graph),
        order=lambda drones, turn: sorted(drones, key=lambda d: -d.id),
    )
    w1, w2 = graph.get_zone("waypoint1"), graph.get_zone("waypoint2")

    paths = finder.plan([FakeDrone(1, w2), FakeDrone(2, w1)], 0)

    assert paths[1][-1].zone is graph.end_hub
    assert paths[2][0].connection is None, "D2 cede: D1 seguía en w2"


# --- criterio de prioridad intercambiable -----------------------------

def test_default_order_is_by_id() -> None:
    graph = load_graph("valid/bottleneck.txt")
    finder = make_finder(graph)
    start = start_of(graph)

    paths = finder.plan([FakeDrone(3, start), FakeDrone(1, start)], 0)

    assert paths[1][-1].arrival_turn == 2
    assert paths[3][-1].arrival_turn == 3


def test_order_strategy_is_a_parameter() -> None:
    graph = load_graph("valid/bottleneck.txt")
    heuristic = AbstractDistance(graph)

    def reverse_id(drones: Sequence[DroneLike], turn: int) -> List[DroneLike]:
        return sorted(drones, key=lambda d: -d.id)

    finder = WhcaPathfinder(graph, heuristic, ReservationTable(graph),
                            order=reverse_id)
    paths = finder.plan(drones_at_start(graph, 2), 0)

    assert paths[2][-1].arrival_turn == 2
    assert paths[1][-1].arrival_turn == 3


def test_farthest_first_orders_by_distance_then_id() -> None:
    graph = load_graph("valid/linear.txt")
    heuristic = AbstractDistance(graph)
    near = FakeDrone(1, graph.get_zone("waypoint2"))
    far_a = FakeDrone(3, start_of(graph))
    far_b = FakeDrone(2, start_of(graph))

    order = PlanningOrders.farthest_first(heuristic)
    ordered = order([near, far_a, far_b], 0)

    assert [d.id for d in ordered] == [2, 3, 1]


def test_nearest_first_orders_by_distance_then_id() -> None:
    graph = load_graph("valid/linear.txt")
    heuristic = AbstractDistance(graph)
    far = FakeDrone(1, start_of(graph))
    near_a = FakeDrone(3, graph.get_zone("waypoint2"))
    near_b = FakeDrone(2, graph.get_zone("waypoint2"))

    order = PlanningOrders.nearest_first(heuristic)
    ordered = order([far, near_a, near_b], 0)

    assert [d.id for d in ordered] == [2, 3, 1]


def test_nearest_first_avoids_the_hold_cost() -> None:
    # Mismo caso que el orden inverso de arriba: con nearest_first D1
    # (delante) planifica primero y D2 le sigue sin esperar.
    graph = load_graph("valid/linear.txt")
    heuristic = AbstractDistance(graph)
    finder = WhcaPathfinder(
        graph, heuristic, ReservationTable(graph),
        order=PlanningOrders.nearest_first(heuristic),
    )
    w1, w2 = graph.get_zone("waypoint1"), graph.get_zone("waypoint2")

    paths = finder.plan([FakeDrone(2, w1), FakeDrone(1, w2)], 0)

    assert moves(paths[2]) == ["waypoint2", "goal"]
    assert paths[2][-1].arrival_turn == 2


def test_rotating_shifts_start_with_turn() -> None:
    graph = load_graph("valid/linear.txt")
    drones = drones_at_start(graph, 3)
    assert [d.id for d in PlanningOrders.rotating(drones, 0)] == [1, 2, 3]
    assert [d.id for d in PlanningOrders.rotating(drones, 4)] == [2, 3, 1]
    assert PlanningOrders.rotating([], 5) == []


def test_by_id_ignores_input_order() -> None:
    graph = load_graph("valid/linear.txt")
    start = start_of(graph)
    drones = [FakeDrone(2, start), FakeDrone(1, start)]
    assert [d.id for d in PlanningOrders.by_id(drones, 0)] == [1, 2]
