from pathlib import Path
from typing import List, Tuple

import pytest

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.dijkstra import Dijkstra

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps" / "valid"


def load_graph(filename: str) -> Graph:
    content = (MAPS_DIR / filename).read_text()
    _, graph = MapParser.parse(content)
    return graph


def start_and_end(graph: Graph) -> Tuple[Zone, Zone]:
    """Valid maps have both; narrows Optional[Zone] (mypy)."""
    assert graph.start_hub is not None
    assert graph.end_hub is not None
    return graph.start_hub, graph.end_hub


def path_names(path: List[Zone]) -> List[str]:
    return [zone.name for zone in path]


def path_cost(path: List[Zone]) -> int:
    """Sum the movement_cost() of each zone except the origin."""
    return sum(zone.movement_cost() for zone in path[1:])


def assert_path_is_consistent(graph: Graph, path: List[Zone]) -> None:
    """Each consecutive pair of the route must be connected in the graph."""
    for current, following in zip(path, path[1:]):
        neighbor_names = {
            connection.other_end(current).name
            for connection in graph.neighbors(current)
        }
        assert following.name in neighbor_names, (
            f"'{current.name}' -> '{following.name}' "
            "not a real connection of the graph"
        )


def test_linear_path_is_optimal() -> None:
    graph = load_graph("linear.txt")
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is not None
    assert path_names(path) == ["start", "waypoint1", "waypoint2", "goal"]
    assert path_cost(path) == 3


def test_single_drone_minimal_path() -> None:
    graph = load_graph("single_drone.txt")
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is not None
    assert path_names(path) == ["start", "goal"]
    assert path_cost(path) == 1


def test_restricted_chain_adds_two_per_zone() -> None:
    graph = load_graph("restricted_chain.txt")
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is not None
    assert path_names(path) == ["start", "r1", "r2", "goal"]
    # r1 and r2 are 'restricted' (+2 each); goal is 'normal' (+1).
    assert path_cost(path) == 5


def test_blocked_zone_is_never_part_of_the_route() -> None:
    graph = load_graph("blocked_detour.txt")
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is not None
    assert "blocker" not in path_names(path)
    assert path_names(path) == ["start", "detour1", "detour2", "goal"]
    assert path_cost(path) == 3


@pytest.mark.parametrize(
    "connection_order", ["priority_first", "normal_first"]
)
def test_priority_wins_ties_regardless_of_connection_order(
    connection_order: str,
) -> None:
    zones = (
        "nb_drones: 1\n"
        "start_hub: start 0 0\n"
        "end_hub: goal 2 0\n"
        "hub: n1 1 -1\n"
        "hub: n2 2 -1\n"
        "hub: p1 1 1 [zone=priority]\n"
        "hub: p2 2 1 [zone=priority]\n"
    )
    normal_connections = (
        "connection: start-n1\n"
        "connection: n1-n2\n"
        "connection: n2-goal\n"
    )
    priority_connections = (
        "connection: start-p1\n"
        "connection: p1-p2\n"
        "connection: p2-goal\n"
    )
    if connection_order == "priority_first":
        content = zones + priority_connections + normal_connections
    else:
        content = zones + normal_connections + priority_connections

    _, graph = MapParser.parse(content)
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is not None
    # Both branches cost 3 (two zones of the branch + goal); the one with
    # more 'priority' zones wins, whatever the order they are written in.
    assert path_names(path) == ["start", "p1", "p2", "goal"]
    assert path_cost(path) == 3


def test_unreachable_target_returns_none_not_raises() -> None:
    content = (
        "nb_drones: 1\n"
        "start_hub: start 0 0\n"
        "end_hub: goal 5 0\n"
        "hub: island 1 0\n"
        "connection: start-island\n"
    )
    _, graph = MapParser.parse(content)
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is None


def test_origin_equals_target_returns_single_zone_zero_cost() -> None:
    graph = load_graph("linear.txt")
    dijkstra = Dijkstra(graph)
    start, _ = start_and_end(graph)

    path = dijkstra.find_path(start, start)

    assert path is not None
    assert path_names(path) == ["start"]
    assert path_cost(path) == 0


def test_returned_path_is_consistent_with_graph_connections() -> None:
    graph = load_graph("bottleneck.txt")
    dijkstra = Dijkstra(graph)
    start, end = start_and_end(graph)

    path = dijkstra.find_path(start, end)

    assert path is not None
    assert_path_is_consistent(graph, path)
