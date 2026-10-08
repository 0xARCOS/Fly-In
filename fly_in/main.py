"""Fly-In entry point: arguments, map reading and errors.

It is the centralized exception boundary: no map error ever reaches the
user as a traceback (Chap. III.1).

stdout carries ONLY the turn lines of the subject (Chap. VII.5); the
visualization, the metrics and the errors go to stderr. That way
`make run > output.txt` leaves a clean file that can be counted with
`wc -l`.
"""

import argparse
import os
import sys
from pathlib import Path
from fly_in.models.errors import MapError, MapValidationError
from fly_in.parsing.map_parser import MapParser
from fly_in.benchmarks import BenchmarkSuite
from fly_in.output.formatter import OutputFormatter
from fly_in.pathfinding.abstract_distance import AbstractDistance
from fly_in.simulation.errors import SimulationError
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.capacity_observer import CapacityObserver
from fly_in.simulation.simulator import (
    ObserverGroup,
    SimulationObserver,
    Simulator,
)
from fly_in.visualization.palette import Painter
from fly_in.visualization.recorder import ReplayRecorder
from fly_in.visualization.session import (
    DEFAULT_DELAYS,
    Run,
    Session,
)


class FlyIn:
    """The command-line application."""

    @staticmethod
    def main() -> int:
        """Run the program and return the exit code."""
        args = FlyIn.build_parser().parse_args()
        try:
            return FlyIn.run(args)
        except (MapError, SimulationError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("\nInterrupted by user.", file=sys.stderr)
            return 130
        except BrokenPipeError:
            # Whoever was reading the output is gone (e.g. `| head`). Point
            # stdout and stderr to /dev/null so Python does not fail again
            # when flushing them on exit.
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            os.dup2(devnull, sys.stderr.fileno())
            os.close(devnull)
            return 1

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        """Define the command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Fly-In: drone routing simulator"
        )
        parser.add_argument(
            "map_file", type=Path, help="Path to the map file"
        )
        parser.add_argument(
            "-w", "--window", type=FlyIn.positive_int, default=8,
            help="WHCA* window size in turns (default: 8)"
        )
        parser.add_argument(
            "-q", "--quiet", action="store_true",
            help="Disable the real-time visualization"
        )
        parser.add_argument(
            "--view",
            choices=("auto", "window", "log"),
            default="auto",
            help="window: pygame window + event log here; "
                 "log: event log only "
                 "(default: window if there is a display, else log)"
        )
        parser.add_argument(
            "--metrics", action="store_true",
            help="Print secondary metrics on stderr"
        )
        parser.add_argument(
            "-d", "--delay", type=FlyIn.non_negative_float, default=None,
            help="Seconds per turn (default: window 0.8, log 0.25)"
        )
        parser.add_argument(
            "--capacity-info", action="store_true",
            help="Print zone and connection usage per turn on stderr"
        )
        return parser

    @staticmethod
    def positive_int(value: str) -> int:
        """Argparse type: strictly positive integer.

        Raises:
            argparse.ArgumentTypeError: If `value` is not an integer > 0.
        """
        try:
            number = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' is not an integer")
        if number <= 0:
            raise argparse.ArgumentTypeError(f"must be > 0, got {number}")
        return number

    @staticmethod
    def non_negative_float(value: str) -> float:
        """Argparse type: real number >= 0.

        Raises:
            argparse.ArgumentTypeError: If `value` is not a number >= 0.
        """
        try:
            number = float(value)
        except ValueError:
            raise argparse.ArgumentTypeError(f"'{value}' is not a number")
        if number < 0 or number != number:
            raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
        return number

    @staticmethod
    def read_map_file(path: Path) -> str:
        """Read the map file and return its content.

        Raises:
            MapError: If the file does not exist, is a directory, cannot be
                read due to permissions or is not UTF-8 text.
        """
        if not path.exists():
            raise MapError(f"Map file not found: {path}")
        if path.is_dir():
            raise MapError(f"Path is a directory, not a file: {path}")
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            raise MapError(f"Permission denied: {path}")
        except UnicodeDecodeError:
            raise MapError(f"File is not valid UTF-8 text: {path}")
        except OSError as exc:
            raise MapError(f"Cannot read {path}: {exc.strerror}")

    @staticmethod
    def make_painter() -> Painter:
        """Color only on a terminal and without the NO_COLOR variable."""
        enabled = sys.stderr.isatty() and "NO_COLOR" not in os.environ
        return Painter(enabled, Painter.supports_truecolor())

    @staticmethod
    def print_metrics(metrics: Metrics) -> None:
        """Secondary metrics on stderr, one per line (--metrics)."""
        for name, value in (
            ("turns", metrics.turns),
            ("drones", metrics.drones),
            ("total_moves", metrics.total_moves),
            ("total_waits", metrics.total_waits),
            ("avg_moves_per_turn", f"{metrics.avg_moves_per_turn:.2f}"),
            ("avg_turns_per_drone", f"{metrics.avg_turns_per_drone:.2f}"),
            ("peak_airborne", metrics.peak_airborne),
            ("compute_ms", f"{metrics.seconds * 1000:.1f}"),
        ):
            print(f"{name}: {value}", file=sys.stderr)

    @staticmethod
    def run(args: argparse.Namespace) -> int:
        """Read the map, simulate, show the simulation and write the output."""
        content = FlyIn.read_map_file(args.map_file)
        nb_drones, graph = MapParser.parse(content)
        assert graph.start_hub is not None and graph.end_hub is not None

        if not AbstractDistance(graph).is_reachable(graph.start_hub):
            raise MapValidationError(
                f"'{graph.end_hub.name}' is unreachable from "
                f"'{graph.start_hub.name}'"
            )

        interactive = sys.stderr.isatty()
        view = Session.choose_view(args.view, args.quiet, interactive)
        delay = args.delay if args.delay is not None else (
            DEFAULT_DELAYS.get(view, 0.0)
        )
        paint = FlyIn.make_painter()
        target = BenchmarkSuite.target_for(args.map_file)

        sim = Simulator(graph, nb_drones, args.window)
        recorder = ReplayRecorder(sim.drones)
        capacity = CapacityObserver(graph)
        observer: SimulationObserver = recorder
        if args.capacity_info:
            observer = ObserverGroup(recorder, capacity)
        trace = sim.run(observer)
        metrics = Metrics.from_trace(trace, nb_drones, sim.elapsed)

        if view in ("window", "log"):
            # No pauses without a terminal: nobody is watching them.
            pace = delay if interactive or view == "window" else 0.0
            run = Run(graph, nb_drones, trace, recorder, metrics,
                      sim.replans, args.map_file.name, args.window, target)
            Session(view, run, paint, sys.stderr, pace).play()

        for index, line in enumerate(OutputFormatter.format_trace(trace)):
            print(line)
            if args.capacity_info:
                # Flush stdout first so that, on a terminal, each capacity
                # line ends up right below the line of its turn.
                sys.stdout.flush()
                print(capacity.lines[index], file=sys.stderr)
        sys.stdout.flush()

        if args.metrics:
            FlyIn.print_metrics(metrics)
        return 0


if __name__ == "__main__":
    sys.exit(FlyIn.main())
