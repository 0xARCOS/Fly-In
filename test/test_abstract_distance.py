from pathlib import Path
from typing import List

import pytest

from fly_in.models.graph import Graph
from fly_in.models.zone import Zone, ZoneType
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.dijkstra import Dijkstra

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps" / "valid"


def load_graph(filename: str) -> Graph:
    _, graph = MapParser.parse((MAPS_DIR / filename).read_text())
    return graph


def path_cost(path: List[Zone]) -> int:
    return sum(zone.movement_cost() for zone in path[1:])


def linear_graph(b_type: ZoneType = ZoneType.NORMAL) -> Graph:
    """start -> a -> b -> goal; `b_type` cambia el tipo de la zona b."""
    graph = Graph()
    graph.add_zone(Zone("start", 0, 0), "start_hub")
    graph.add_zone(Zone("a", 1, 0), "hub")
    graph.add_zone(Zone("b", 2, 0, zone_type=b_type), "hub")
    graph.add_zone(Zone("goal", 3, 0), "end_hub")
    graph.add_connection("start", "a", 1)
    graph.add_connection("a", "b", 1)
    graph.add_connection("b", "goal", 1)
    return graph


# --- 1. h(end_hub) == 0 -------------------------------------------------

def test_h_of_end_hub_is_zero() -> None:
    graph = linear_graph()
    assert graph.end_hub is not None
    assert AbstractDistance(graph).h(graph.end_hub) == 0


# --- 2. Lineal todo normal: h(start) == 3 -------------------------------

def test_linear_all_normal() -> None:
    graph = linear_graph()
    dist = AbstractDistance(graph)
    assert dist.h(graph.get_zone("start")) == 3
    assert dist.h(graph.get_zone("a")) == 2
    assert dist.h(graph.get_zone("b")) == 1


# --- 3. b restricted: h(start) == 4 y h(b) == 1  (el test clave) --------

def test_restricted_middle_zone_cost_is_paid_by_the_one_entering() -> None:
    graph = linear_graph(b_type=ZoneType.RESTRICTED)
    dist = AbstractDistance(graph)
    assert dist.h(graph.get_zone("b")) == 1      # NO 2: b la paga quien entra
    assert dist.h(graph.get_zone("a")) == 3
    assert dist.h(graph.get_zone("start")) == 4


# --- 4 y 6. blocked: fuera del dict e is_reachable False ----------------

def test_blocked_zone_is_absent_and_unreachable() -> None:
    graph = linear_graph(b_type=ZoneType.BLOCKED)
    dist = AbstractDistance(graph)
    blocked = graph.get_zone("b")
    assert "b" not in dist._dist
    assert not dist.is_reachable(blocked)
    with pytest.raises(KeyError):
        dist.h(blocked)
    # y corta el camino: start y a quedan aisladas del objetivo
    assert not dist.is_reachable(graph.get_zone("a"))
    assert not dist.is_reachable(graph.get_zone("start"))


# --- 5 y 6. zona aislada: fuera del dict e is_reachable False -----------

def test_isolated_zone_is_absent_and_unreachable() -> None:
    graph = linear_graph()
    graph.add_zone(Zone("island", 9, 9), "hub")     # sin conexiones
    dist = AbstractDistance(graph)
    island = graph.get_zone("island")
    assert "island" not in dist._dist
    assert not dist.is_reachable(island)
    with pytest.raises(KeyError):
        dist.h(island)


# --- 7. Coherencia con SP04, zona por zona, en todos los mapas ----------

@pytest.mark.parametrize(
    "map_file", sorted(p.name for p in MAPS_DIR.glob("*.txt"))
)
def test_consistency_with_dijkstra(map_file: str) -> None:
    graph = load_graph(map_file)
    assert graph.end_hub is not None
    dijkstra = Dijkstra(graph)
    dist = AbstractDistance(graph)

    for zone in graph.zones.values():
        path = dijkstra.find_path(zone, graph.end_hub)
        assert dist.is_reachable(zone) == (path is not None), zone.name
        if path is not None:
            assert dist.h(zone) == path_cost(path), zone.name
