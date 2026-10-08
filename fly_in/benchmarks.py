"""Official benchmarks of the subject (Chap. VII.7) and their runner (SP11).

Usage: `python -m fly_in.benchmarks`. Prints two tables:

1. The 10 official maps with the default configuration: turns, target,
   whether it is met, time and secondary metrics.
2. The comparison of configurations (W × priority criterion), which is
   what justifies the default values.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.pathfinding.whca import (
    DEFAULT_WINDOW,
    PlanningOrder,
    PlanningOrders,
)
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.simulator import Simulator

OFFICIAL_DIR = Path(__file__).resolve().parent.parent / "maps" / "oficial_maps"


@dataclass(frozen=True)
class Benchmark:
    """A reference map and the maximum number of turns the subject asks for."""

    category: str
    path: str        # relative to maps/oficial_maps
    drones: int
    max_turns: int   # the challenger asks to "beat 45": at most 44
    label: str


BENCHMARKS: Tuple[Benchmark, ...] = (
    Benchmark("easy", "easy/01_linear_path.txt", 2, 6, "≤ 6"),
    Benchmark("easy", "easy/02_simple_fork.txt", 4, 8, "≤ 8"),
    Benchmark("easy", "easy/03_basic_capacity.txt", 4, 6, "≤ 6"),
    Benchmark("medium", "medium/01_dead_end_trap.txt", 5, 12, "≤ 12"),
    Benchmark("medium", "medium/02_circular_loop.txt", 6, 15, "≤ 15"),
    Benchmark("medium", "medium/03_priority_puzzle.txt", 5, 12, "≤ 12"),
    Benchmark("hard", "hard/01_maze_nightmare.txt", 8, 30, "≤ 30"),
    Benchmark("hard", "hard/02_capacity_hell.txt", 12, 35, "≤ 35"),
    Benchmark("hard", "hard/03_ultimate_challenge.txt", 15, 45, "≤ 45"),
    Benchmark(
        "challenger", "challenger/01_the_impossible_dream.txt", 25, 44,
        "< 45",
    ),
)

OrderFactory = Callable[[AbstractDistance], PlanningOrder]
ORDERS: Dict[str, OrderFactory] = {
    "id": lambda h: PlanningOrders.by_id,
    "nearest": PlanningOrders.nearest_first,
    "farthest": PlanningOrders.farthest_first,
    "rotating": lambda h: PlanningOrders.rotating,
}
WINDOWS = (4, 8, 16)


class BenchmarkSuite:
    """Run the official maps and compare configurations."""

    @staticmethod
    def target_for(map_path: Path) -> Optional[int]:
        """Subject's maximum turns if `map_path` is an official map."""
        for bench in BENCHMARKS:
            if map_path.name == Path(bench.path).name:
                return bench.max_turns
        return None

    @staticmethod
    def measure(
        path: Path, window: int = DEFAULT_WINDOW, order: str = "id"
    ) -> Metrics:
        """Simulate `path` with that configuration and return its metrics."""
        nb_drones, graph = MapParser.parse(path.read_text(encoding="utf-8"))
        started = time.perf_counter()
        sim = Simulator(graph, nb_drones, window,
                        ORDERS[order](AbstractDistance(graph)))
        trace = sim.run()
        return Metrics.from_trace(trace, nb_drones,
                                  time.perf_counter() - started)

    @staticmethod
    def report() -> int:
        """Print the official table and the configuration comparison."""
        print(f"Official benchmarks (W={DEFAULT_WINDOW}, order=id)\n")
        header = (
            f"{'map':36} {'drones':>6} {'turns':>5} {'target':>7} {'ok':>3}"
            f" {'time':>8} {'moves/t':>7} {'avg.dlv':>7} {'waits':>5}"
        )
        print(header)
        print("-" * len(header))
        failures = 0
        for bench in BENCHMARKS:
            m = BenchmarkSuite.measure(OFFICIAL_DIR / bench.path)
            ok = m.turns <= bench.max_turns
            failures += 0 if ok else 1
            print(
                f"{bench.path:36} {bench.drones:>6} {m.turns:>5} "
                f"{bench.label:>7} {'✅' if ok else '❌':>2} "
                f"{m.seconds * 1000:>6.0f}ms {m.avg_moves_per_turn:>7.2f} "
                f"{m.avg_turns_per_drone:>7.1f} {m.total_waits:>5}"
            )

        configs: List[Tuple[int, str]] = [
            (window, order) for window in WINDOWS for order in ORDERS
        ]
        print("\nConfiguration comparison (turns; total time)\n")
        names = [f"W{w}/{o}" for w, o in configs]
        print(f"{'map':32}" + "".join(f"{n:>13}" for n in names))
        totals: Dict[str, int] = {name: 0 for name in names}
        seconds: Dict[str, float] = {name: 0.0 for name in names}
        for bench in BENCHMARKS:
            row = f"{Path(bench.path).stem[:31]:32}"
            for (window, order), name in zip(configs, names):
                m = BenchmarkSuite.measure(
                    OFFICIAL_DIR / bench.path, window, order
                )
                totals[name] += m.turns
                seconds[name] += m.seconds
                row += f"{m.turns:>13}"
            print(row)
        print(f"{'TOTAL turns':32}"
              + "".join(f"{totals[n]:>13}" for n in names))
        print(f"{'TOTAL time (s)':32}"
              + "".join(f"{seconds[n]:>13.2f}" for n in names))
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(BenchmarkSuite.report())
