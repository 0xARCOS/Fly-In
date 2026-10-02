"""Tests de las métricas y los benchmarks (SP11)."""

from pathlib import Path

import pytest

from fly_in.benchmarks import (
    BENCHMARKS,
    OFFICIAL_DIR,
    Benchmark,
    BenchmarkSuite,
)
from fly_in.parsing.map_parser import MapParser
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.simulator import Simulator

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"


def metrics_of(relative: str) -> Metrics:
    """Métricas de un mapa con la configuración por defecto."""
    nb_drones, graph = MapParser.parse((MAPS_DIR / relative).read_text())
    return Metrics.from_trace(Simulator(graph, nb_drones).run(), nb_drones)


def test_bottleneck_metrics_by_hand() -> None:
    # D1 entrega en 2, D2 en 3, D3 en 4. Cada uno se mueve 2 turnos.
    m = metrics_of("valid/bottleneck.txt")
    assert m.turns == 4 and m.drones == 3
    assert m.total_moves == 6
    assert m.total_waits == (2 + 3 + 4) - 6
    assert m.avg_turns_per_drone == pytest.approx(3.0)
    assert m.avg_moves_per_turn == pytest.approx(1.5)
    assert m.peak_airborne == 0


def test_transit_counts_as_airborne_and_as_two_moves() -> None:
    m = metrics_of("valid/restricted_chain.txt")
    assert m.turns == 5 and m.total_moves == 5
    assert m.peak_airborne == 1 and m.total_waits == 0


def test_empty_trace() -> None:
    m = Metrics.from_trace([], 0)
    assert m.turns == 0 and m.avg_moves_per_turn == 0.0


def test_every_benchmark_file_exists_with_its_drone_count() -> None:
    for bench in BENCHMARKS:
        path = OFFICIAL_DIR / bench.path
        nb_drones, _ = MapParser.parse(path.read_text())
        assert nb_drones == bench.drones, bench.path


@pytest.mark.parametrize("bench", BENCHMARKS, ids=lambda b: b.path)
def test_default_configuration_meets_every_target(bench: Benchmark) -> None:
    turns = BenchmarkSuite.measure(OFFICIAL_DIR / bench.path).turns
    assert turns <= bench.max_turns


def test_target_lookup() -> None:
    target_for = BenchmarkSuite.target_for
    assert target_for(Path("x/02_circular_loop.txt")) == 15
    assert target_for(Path("01_the_impossible_dream.txt")) == 44
    assert target_for(Path("maps/valid/linear.txt")) is None
