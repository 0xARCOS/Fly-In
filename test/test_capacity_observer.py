"""Tests for --capacity-info: one line per turn, never over the limit."""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

import pytest

from fly_in.parsing.map_parser import MapParser
from fly_in.simulation.capacity_observer import CapacityObserver
from fly_in.simulation.simulator import Move, Simulator

ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "maps"
OFFICIAL = sorted((MAPS_DIR / "oficial_maps").rglob("*.txt"))


def watch(path: Path) -> Tuple[Sequence[Sequence[Move]], List[str]]:
    nb_drones, graph = MapParser.parse(path.read_text())
    observer = CapacityObserver(graph)
    trace = Simulator(graph, nb_drones).run(observer)
    return trace, observer.lines


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


def test_restricted_transit_uses_the_connection_twice() -> None:
    _, lines = watch(MAPS_DIR / "valid" / "restricted_chain.txt")
    assert lines[0] == "T1 Connection start-r1: 1/1 capacity used"
    assert lines[1].endswith("Connection start-r1: 1/1 capacity used")


@pytest.mark.parametrize("path", OFFICIAL, ids=lambda p: p.name)
def test_usage_never_exceeds_capacity(path: Path) -> None:
    _, lines = watch(path)
    for line in lines:
        for used, limit in re.findall(r": (\d+)/(\d+) ", line):
            assert int(used) <= int(limit), line


def test_flag_keeps_stdout_and_adds_stderr() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "fly_in.main", "maps/valid/bottleneck.txt",
         "--capacity-info", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "D1-narrow", "D1-goal D2-narrow", "D2-goal D3-narrow", "D3-goal",
    ]
    assert [line[:3] for line in result.stderr.splitlines()] == [
        "T1 ", "T2 ", "T3 ", "T4 ",
    ]
