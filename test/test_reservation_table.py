"""Tests de ReservationTable (SP06).

Recordatorio de la convención: "instante t" = estado tras t turnos.
Zona (z, t) = drones en z en el instante t. Conexión (c, t) = drones
cruzando c entre t y t+1.
"""

import pytest

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.reservation_table import (
    ReservationError,
    ReservationTable,
)

# start - a - b - goal, con una rama start - big - goal y un restricted.
#
#   start ── a(cap 1) ── b(cap 1) ── goal
#     │                               │
#     ├──── big(cap 3) ═══════════════┤   (big-goal: link cap 2)
#     │                               │
#     └──── r(restricted, cap 1) ─────┘
MAP = """\
nb_drones: 5
start_hub: start 0 0
end_hub: goal 4 0
hub: a 1 0
hub: b 2 0
hub: big 2 1 [max_drones=3]
hub: r 2 -1 [zone=restricted]
connection: start-a
connection: a-b
connection: b-goal
connection: start-big
connection: big-goal [max_link_capacity=2]
connection: start-r
connection: r-goal
"""


@pytest.fixture
def graph() -> Graph:
    """Grafo de prueba compartido."""
    return MapParser.parse(MAP)[1]


@pytest.fixture
def table(graph: Graph) -> ReservationTable:
    """Tabla vacía sobre el grafo de prueba."""
    return ReservationTable(graph)


def z(graph: Graph, name: str) -> Zone:
    """Atajo: zona por nombre."""
    return graph.get_zone(name)


# --- capacidad de zona -------------------------------------------------

def test_two_drones_cannot_share_a_capacity_1_zone(
    graph: Graph, table: ReservationTable
) -> None:
    table.reserve_wait(1, z(graph, "a"), 3)
    assert not table.zone_has_room(z(graph, "a"), 3)
    with pytest.raises(ReservationError):
        table.reserve_wait(2, z(graph, "a"), 3)


def test_three_drones_fit_in_a_capacity_3_zone(
    graph: Graph, table: ReservationTable
) -> None:
    for drone in (1, 2, 3):
        table.reserve_wait(drone, z(graph, "big"), 3)
    assert table.zone_occupants(z(graph, "big"), 3) == [1, 2, 3]
    assert not table.zone_has_room(z(graph, "big"), 3)


def test_same_zone_on_different_turns_does_not_interfere(
    graph: Graph, table: ReservationTable
) -> None:
    table.reserve_wait(1, z(graph, "a"), 3)
    table.reserve_wait(1, z(graph, "a"), 4)
    table.reserve_wait(2, z(graph, "a"), 5)
    assert table.zone_occupants(z(graph, "a"), 4) == [1]


@pytest.mark.parametrize("hub", ["start", "goal"])
def test_start_and_end_never_fill_up(
    graph: Graph, table: ReservationTable, hub: str
) -> None:
    for drone in range(1, 101):
        table.reserve_wait(drone, z(graph, hub), 0)
    assert table.zone_has_room(z(graph, hub), 0)


def test_same_drone_cannot_be_counted_twice(
    graph: Graph, table: ReservationTable
) -> None:
    table.reserve_wait(1, z(graph, "big"), 3)
    with pytest.raises(ReservationError):
        table.reserve_wait(1, z(graph, "big"), 3)


# --- capacidad de conexión ---------------------------------------------

def test_link_capacity_is_respected(
    graph: Graph, table: ReservationTable
) -> None:
    big, goal = z(graph, "big"), z(graph, "goal")
    table.reserve_move(1, big, goal, 5)
    table.reserve_move(2, big, goal, 5)
    assert not table.can_move(big, goal, 5)
    with pytest.raises(ReservationError):
        table.reserve_move(3, big, goal, 5)


def test_end_hub_is_unlimited_but_its_connection_is_not(
    graph: Graph, table: ReservationTable
) -> None:
    b, goal = z(graph, "b"), z(graph, "goal")
    table.reserve_move(1, b, goal, 2)
    assert table.zone_has_room(goal, 3)
    assert not table.can_move(b, goal, 2)


# --- movimientos normales ----------------------------------------------

def test_cost_1_move_occupies_link_at_t_and_zone_at_t_plus_1(
    graph: Graph, table: ReservationTable
) -> None:
    start, a = z(graph, "start"), z(graph, "a")
    conn = graph.connection_between(start, a)
    table.reserve_move(7, start, a, 4)
    assert table.link_occupants(conn, 4) == [7]
    assert table.link_occupants(conn, 5) == []
    assert table.zone_occupants(a, 4) == []
    assert table.zone_occupants(a, 5) == [7]


def test_leaving_a_zone_frees_it_for_the_same_turn(
    graph: Graph, table: ReservationTable
) -> None:
    """Cap. VII.3: 'Drones moving out of a zone free up capacity for that
    same turn'. D1 está en a (cap 1) en el instante 3 y sale hacia b; D2
    puede entrar en a en ese mismo turno (llega en el instante 4)."""
    start, a, b = z(graph, "start"), z(graph, "a"), z(graph, "b")
    table.reserve_wait(1, a, 3)
    table.reserve_move(1, a, b, 3)
    assert table.can_move(start, a, 3)


def test_cannot_enter_a_zone_where_someone_stays(
    graph: Graph, table: ReservationTable
) -> None:
    start, a = z(graph, "start"), z(graph, "a")
    table.reserve_wait(1, a, 4)
    assert not table.can_move(start, a, 3)


# --- restricted (coste 2) ----------------------------------------------

def test_cost_2_move_occupies_link_twice_and_zone_at_t_plus_2(
    graph: Graph, table: ReservationTable
) -> None:
    start, r = z(graph, "start"), z(graph, "r")
    conn = graph.connection_between(start, r)
    table.reserve_move(1, start, r, 0)
    assert table.link_occupants(conn, 0) == [1]
    assert table.link_occupants(conn, 1) == [1]
    assert table.link_occupants(conn, 2) == []
    assert table.zone_occupants(r, 2) == [1]


def test_cost_2_move_occupies_no_zone_while_in_the_air(
    graph: Graph, table: ReservationTable
) -> None:
    start, r = z(graph, "start"), z(graph, "r")
    table.reserve_move(1, start, r, 0)
    for name in ("start", "r", "a", "b", "big", "goal"):
        assert table.zone_occupants(z(graph, name), 1) == []


def test_restricted_link_is_busy_on_the_second_turn(
    graph: Graph, table: ReservationTable
) -> None:
    """Lectura estricta de 'the drone occupies the connection during
    transit': con capacidad 1, D2 no puede entrar mientras D1 sigue en el
    aire, aunque D1 saliera un turno antes."""
    start, r = z(graph, "start"), z(graph, "r")
    table.reserve_move(1, start, r, 0)
    assert not table.can_move(start, r, 1)


def test_cannot_enter_restricted_if_landing_zone_will_be_full(
    graph: Graph, table: ReservationTable
) -> None:
    start, r = z(graph, "start"), z(graph, "r")
    table.reserve_wait(9, r, 5)
    assert not table.can_move(start, r, 3)
    assert table.can_move(start, r, 4)


def test_moving_into_blocked_is_never_possible() -> None:
    blocked_map = MAP + "hub: wall 3 3 [zone=blocked]\nconnection: b-wall\n"
    g = MapParser.parse(blocked_map)[1]
    assert not ReservationTable(g).can_move(z(g, "b"), z(g, "wall"), 0)


def test_unconnected_zones_raise(
    graph: Graph, table: ReservationTable
) -> None:
    with pytest.raises(ValueError):
        table.can_move(z(graph, "a"), z(graph, "goal"), 0)


# --- anti-cruce --------------------------------------------------------

def test_would_swap_detects_opposite_moves_on_the_same_turn(
    graph: Graph, table: ReservationTable
) -> None:
    big, goal = z(graph, "big"), z(graph, "goal")
    table.reserve_move(1, big, goal, 3)
    assert table.would_swap(goal, big, 3)
    assert table.link_has_room(graph.connection_between(big, goal), 3)
    assert not table.can_move(goal, big, 3)


def test_would_swap_is_false_on_different_turns(
    graph: Graph, table: ReservationTable
) -> None:
    big, goal = z(graph, "big"), z(graph, "goal")
    table.reserve_move(1, big, goal, 3)
    assert not table.would_swap(goal, big, 4)
    assert not table.would_swap(big, goal, 3)


def test_swap_is_detected_on_the_second_turn_of_a_restricted_move() -> None:
    """D1 sale de x hacia r (restricted) en 0: está en el aire en 0 y 1.
    D2 no puede salir de r hacia x en 1: se cruzarían en pleno vuelo, aunque
    la conexión tenga capacidad 2."""
    g = MapParser.parse(
        "nb_drones: 2\nstart_hub: s 0 0\nend_hub: e 3 0\n"
        "hub: x 1 0 [max_drones=2]\nhub: r 2 0 [zone=restricted]\n"
        "connection: s-x\nconnection: x-r [max_link_capacity=2]\n"
        "connection: r-e\n"
    )[1]
    table = ReservationTable(g)
    table.reserve_move(1, z(g, "x"), z(g, "r"), 0)
    assert table.would_swap(z(g, "r"), z(g, "x"), 1)
    assert not table.can_move(z(g, "r"), z(g, "x"), 1)


# --- atomicidad --------------------------------------------------------

def test_failed_reservation_leaves_the_table_untouched(
    graph: Graph, table: ReservationTable
) -> None:
    """Si la zona de aterrizaje está llena, no debe quedar reservada la
    conexión 'a medias'."""
    start, r = z(graph, "start"), z(graph, "r")
    conn = graph.connection_between(start, r)
    table.reserve_wait(9, r, 2)
    with pytest.raises(ReservationError):
        table.reserve_move(1, start, r, 0)
    assert table.link_occupants(conn, 0) == []
    assert table.link_occupants(conn, 1) == []


# --- clear_from --------------------------------------------------------

def test_clear_from_keeps_the_past_and_drops_the_future(
    graph: Graph, table: ReservationTable
) -> None:
    big = z(graph, "big")
    for turn in range(10):
        table.reserve_wait(1, big, turn)
    table.clear_from(5)
    for turn in range(5):
        assert table.zone_occupants(big, turn) == [1]
    for turn in range(5, 10):
        assert table.zone_occupants(big, turn) == []


def test_clear_from_drops_links_and_directions_too(
    graph: Graph, table: ReservationTable
) -> None:
    big, goal = z(graph, "big"), z(graph, "goal")
    table.reserve_move(1, big, goal, 6)
    table.clear_from(5)
    assert table.link_occupants(graph.connection_between(big, goal), 6) == []
    assert not table.would_swap(goal, big, 6)


def test_clear_from_keeps_drones_in_the_air(
    graph: Graph, table: ReservationTable
) -> None:
    """D1 salió hacia r en el instante 4: está en el aire en 5 y aterriza en
    6. Al replanificar en 5, su llegada no se puede borrar o otro dron podría
    ocupar r y D1 no tendría dónde aterrizar."""
    start, r, a = z(graph, "start"), z(graph, "r"), z(graph, "a")
    conn = graph.connection_between(start, r)
    table.reserve_move(1, start, r, 4)
    table.reserve_move(2, start, a, 5)
    table.clear_from(5, keep={1})
    assert table.link_occupants(conn, 5) == [1]
    assert table.zone_occupants(r, 6) == [1]
    assert table.zone_occupants(a, 6) == []


def test_replanning_on_top_of_a_cleared_table_works(
    graph: Graph, table: ReservationTable
) -> None:
    start, a = z(graph, "start"), z(graph, "a")
    table.reserve_move(1, start, a, 5)
    table.clear_from(5)
    table.reserve_move(2, start, a, 5)
    assert table.zone_occupants(a, 6) == [2]
