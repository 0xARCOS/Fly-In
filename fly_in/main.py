"""Punto de entrada de Fly-In: argumentos, lectura del mapa y errores.

Es la frontera centralizada de excepciones: ningún error de mapa llega al
usuario como traceback (Cap. III.1).

stdout lleva SOLO las líneas de turno del subject (Cap. VII.5); la
visualización, las métricas y los errores van a stderr. Así
`make run > salida.txt` deja un fichero limpio que se puede contar con
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
from fly_in.visualization.terminal_view import TerminalRenderer
from fly_in.simulation.capacity_observer import CapacityObserver


class FlyIn:
    """La aplicación de línea de comandos."""

    @staticmethod
    def main() -> int:
        """Ejecuta el programa y devuelve el código de salida."""
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
            # Quien leía la salida se ha ido (p. ej. `| head`). Se apuntan
            # stdout y stderr a /dev/null para que Python no falle otra vez
            # al vaciarlos al salir.
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            os.dup2(devnull, sys.stderr.fileno())
            os.close(devnull)
            return 1

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        """Define los argumentos de línea de comandos."""
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
            "--no-color", action="store_true",
            help="Disable terminal colors"
        )
        parser.add_argument(
            "-q", "--quiet", action="store_true",
            help="Disable the real-time visualization"
        )
        parser.add_argument(
            "--view",
            choices=("auto", "window", "log", "none"),
            default="auto",
            help="window: pygame window + event log here; "
                 "log: event log only; hud: full-screen terminal HUD "
                 "(default: window if there is a display, else log)"
        )
        parser.add_argument(
            "--metrics", action="store_true",
            help="Print secondary metrics on stderr"
        )
        parser.add_argument(
            "-d", "--delay", type=FlyIn.non_negative_float, default=None,
            help="Seconds per turn (default: window 0.8, log 0.25, hud 0.4)"
        )
        parser.add_argument(
            "--capacity-info", action="store_true",
            help="Display zone and connection capacity "
                 "information during simulation"
        )
        parser.add_argument(
            "--color-output", action="store_true",
            help="Print colored trace output on stderr"
        )
        return parser

    @staticmethod
    def positive_int(value: str) -> int:
        """Tipo de argparse: entero estrictamente positivo.

        Raises:
            argparse.ArgumentTypeError: Si `value` no es un entero > 0.
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
        """Tipo de argparse: número real >= 0.

        Raises:
            argparse.ArgumentTypeError: Si `value` no es un número >= 0.
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
        """Lee el archivo de mapa y devuelve su contenido.

        Raises:
            MapError: Si el archivo no existe, es un directorio, no hay
                permiso o no es texto UTF-8.
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
    def make_painter(args: argparse.Namespace) -> Painter:
        """Color solo en terminal, sin --no-color ni la variable NO_COLOR."""
        enabled = (
            sys.stderr.isatty() and not args.no_color
            and "NO_COLOR" not in os.environ
        )
        return Painter(enabled, Painter.supports_truecolor())

    @staticmethod
    def print_metrics(metrics: Metrics) -> None:
        """Métricas secundarias en stderr, una por línea (--metrics)."""
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
        """Lee el mapa, simula, enseña la simulación y escribe la salida."""
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
        paint = FlyIn.make_painter(args)
        target = BenchmarkSuite.target_for(args.map_file)

        sim = Simulator(graph, nb_drones, args.window)
        recorder = ReplayRecorder(sim.drones)

        # Build observer list based on options
        observers: list[SimulationObserver] = [recorder]
        if args.capacity_info:
            observers.insert(0, CapacityObserver(graph))

        if view == "hud":
            renderer = TerminalRenderer(
                graph, nb_drones, sys.stderr, paint, live=interactive,
                delay=delay, title=args.map_file.name, window=args.window,
                target=target,
            )
            # El renderer oculta el cursor y lo devuelve al salir, también
            # si la simulación falla o el usuario pulsa Ctrl+C.
            with renderer:
                renderer.intro()
                observers.insert(0, renderer)
                trace = sim.run(ObserverGroup(*observers))
                metrics = Metrics.from_trace(trace, nb_drones, sim.elapsed)
                renderer.finish(metrics)
        else:
            trace = sim.run(ObserverGroup(*observers))
            metrics = Metrics.from_trace(trace, nb_drones, sim.elapsed)

        if view in ("window", "log"):
            # Sin terminal no se hacen pausas: nadie las está mirando.
            pace = delay if interactive or view == "window" else 0.0
            run = Run(graph, nb_drones, trace, recorder, metrics,
                      sim.replans, args.map_file.name, args.window, target)
            Session(view, run, paint, sys.stderr, pace).play()

        for line in OutputFormatter.format_trace(trace):
            print(line)
        sys.stdout.flush()

        # Colored output if requested
        if args.color_output:
            try:
                print("\n=== Colored Trace ===", file=sys.stderr)
                for i, line in enumerate(
                    OutputFormatter.format_trace_colored(trace, paint),
                    start=1
                ):
                    print(f"Turn {i:3d}: {line}", file=sys.stderr)
            except BrokenPipeError:
                pass  # stderr closed, ignore

        if args.metrics:
            FlyIn.print_metrics(metrics)
        return 0


if __name__ == "__main__":
    sys.exit(FlyIn.main())
