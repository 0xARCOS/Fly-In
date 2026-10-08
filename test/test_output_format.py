"""Tests for OutputFormatter (SP09): the format of Chap. VII.5, verbatim."""

import re
from pathlib import Path
from typing import List, Set, Tuple

import pytest

from fly_in.models.graph import Graph
from fly_in.output.formatter import OutputFormatter
from fly_in.parsing.map_parser import MapParser
from fly_in.simulation.simulator import Move, Simulator

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
ALL_MAPS = sorted(
    str(p.relative_to(MAPS_DIR))
    for p in list((MAPS_DIR / "valid").glob("*.txt"))
    + list((MAPS_DIR / "oficial_maps").glob("*/*.txt"))
)
LINE = re.compile(r"^D\d+-\S+( D\d+-\S+)*$")

MAP = """\
nb_drones: 2
start_hub: hub 0 0
end_hub: goal 3 0
hub: roof1 1 0 [zone=restricted]
hub: a 1 1
hub: b 1 -1
connection: hub-roof1
connection: roof1-goal
connection: hub-a
connection: hub-b
connection: a-goal
connection: b-goal
"""


def graph() -> Graph:
    """Small graph with one restricted zone and two normal zones."""
    return MapParser.parse(MAP)[1]


def move(g: Graph, drone: int, frm: str, to: str, arrives: bool = True
         ) -> Move:
    """A Move between two zones of the graph."""
    origin, target = g.get_zone(frm), g.get_zone(to)
    return Move(drone, origin, target,
                g.connection_between(origin, target), arrives)


def simulate(relative: str) -> Tuple[int, List[str]]:
    """(number of turns of the trace, formatted lines)."""
    nb_drones, g = MapParser.parse((MAPS_DIR / relative).read_text())
    trace = Simulator(g, nb_drones).run()
    return len(trace), OutputFormatter.format_trace(trace)


def test_simple_move() -> None:
    g = graph()
    assert OutputFormatter.format_move(move(g, 1, "hub", "a")) == "D1-a"


def test_transit_prints_connection_then_zone() -> None:
    g = graph()
    first = move(g, 1, "hub", "roof1", arrives=False)
    second = move(g, 1, "hub", "roof1", arrives=True)
    assert OutputFormatter.format_move(first) == "D1-hub-roof1"
    assert OutputFormatter.format_move(second) == "D1-roof1"


def test_connection_name_is_not_reoriented() -> None:
    g = graph()
    backwards = move(g, 3, "roof1", "hub", arrives=True)
    in_air = Move(3, backwards.origin, backwards.target,
                  backwards.connection, arrives=False)
    assert OutputFormatter.format_move(in_air) == "D3-hub-roof1"


def test_two_drones_separated_by_one_space() -> None:
    g = graph()
    line = OutputFormatter.format_turn(
        [move(g, 1, "hub", "a"), move(g, 2, "hub", "b")]
    )
    assert line == "D1-a D2-b"


def test_moves_are_sorted_by_id() -> None:
    g = graph()
    line = OutputFormatter.format_turn(
        [move(g, 10, "hub", "a"), move(g, 2, "hub", "b"),
         move(g, 1, "a", "goal")]
    )
    assert line == "D1-goal D2-b D10-a"


def test_turn_without_moves_produces_no_line() -> None:
    g = graph()
    assert OutputFormatter.format_turn([]) == ""
    lines = OutputFormatter.format_trace([[move(g, 1, "hub", "a")], []])
    assert lines == ["D1-a"]


def test_linear_matches_hand_written_output() -> None:
    _, lines = simulate("valid/linear.txt")
    assert lines == [
        "D1-waypoint1",
        "D1-waypoint2 D2-waypoint1",
        "D1-goal D2-waypoint2",
        "D2-goal",
    ]


def test_bottleneck_matches_hand_written_output() -> None:
    _, lines = simulate("valid/bottleneck.txt")
    assert lines == [
        "D1-narrow",
        "D1-goal D2-narrow",
        "D2-goal D3-narrow",
        "D3-goal",
    ]


@pytest.mark.parametrize("map_file", ALL_MAPS)
def test_every_line_has_the_subject_format(map_file: str) -> None:
    turns, lines = simulate(map_file)
    assert len(lines) == turns, "one line per turn"
    for line in lines:
        assert LINE.match(line), line
        assert "\033" not in line


@pytest.mark.parametrize("map_file", ALL_MAPS)
def test_delivered_drones_never_reappear(map_file: str) -> None:
    nb_drones, g = MapParser.parse((MAPS_DIR / map_file).read_text())
    assert g.end_hub is not None
    goal = f"-{g.end_hub.name}"
    _, lines = simulate(map_file)
    delivered: Set[str] = set()
    for line in lines:
        tokens = line.split()
        drones = {token.split("-", 1)[0] for token in tokens}
        assert not drones & delivered
        delivered |= {t.split("-", 1)[0] for t in tokens if t.endswith(goal)
                      and t.count("-") == 1}
    assert len(delivered) == nb_drones
