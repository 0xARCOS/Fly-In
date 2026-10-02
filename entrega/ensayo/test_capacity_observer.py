import io
import re
from pathlib import Path
from typing import List, Tuple

import pytest

from fly_in.parsing.map_parser import MapParser
from fly_in.simulation.capacity_observer import CapacityObserver
from fly_in.simulation.simulator import Move, Simulator

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
OFFICIAL = sorted((MAPS_DIR / "oficial_maps").rglob("*.txt"))


def watch(path: Path) -> Tuple[List[List[Move]], List[str]]:
    nb_drones, graph = MapParser.parse(path.read_text())
    stream = io.StringIO()
    trace = Simulator(graph, nb_drones).run(CapacityObserver(graph, stream))
    return trace, stream.getvalue().splitlines()


def test_one_line_per_turn() -> None:
    trace, lines = watch(MAPS_DIR / "valid" / "bottleneck.txt")
    assert len(lines) == len(trace)


def test_bottleneck_by_hand() -> None:
    _, lines = watch(MAPS_DIR / "valid" / "bottleneck.txt")
    assert lines[0] == (
        "T1 Zone narrow: 1/1 drones, Zone start: 2/inf drones, "
        "Connection start-narrow: 1/1 capacity used"
    )
    assert lines[-1] == (
        "T4 Zone goal: 3/inf drones, "
        "Connection narrow-goal: 1/1 capacity used"
    )


@pytest.mark.parametrize("path", OFFICIAL, ids=lambda p: p.name)
def test_usage_never_exceeds_capacity(path: Path) -> None:
    _, lines = watch(path)
    for line in lines:
        for used, limit in re.findall(r": (\d+)/(\d+) ", line):
            assert int(used) <= int(limit), line
