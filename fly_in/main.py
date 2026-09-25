"""Punto de entrada de Fly-In: argumentos, lectura del mapa y errores.

Es la frontera centralizada de excepciones: ningún error de mapa llega al
usuario como traceback (Cap. III.1).
"""

import argparse
import sys
from pathlib import Path

from fly_in.models.errors import MapError, MapValidationError
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.abstract_distance import AbstractDistance


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


def build_parser() -> argparse.ArgumentParser:
    """Define los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Fly-In: drone routing simulator"
    )
    parser.add_argument(
        "map_file", type=Path, help="Path to the map file"
    )
    parser.add_argument(
        "-w", "--window", type=positive_int, default=8,
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
        "--metrics", action="store_true",
        help="Print secondary metrics on stderr"
    )
    return parser


def read_map_file(path: Path) -> str:
    """Lee el archivo de mapa y devuelve su contenido.

    Raises:
        MapError: Si el archivo no existe, es un directorio, no hay permiso
            o no es texto UTF-8.
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


def main() -> int:
    """Ejecuta el programa y devuelve el código de salida."""
    args = build_parser().parse_args()

    try:
        content = read_map_file(args.map_file)
        nb_drones, graph = MapParser.parse(content)
        assert graph.start_hub is not None and graph.end_hub is not None

        if not AbstractDistance(graph).is_reachable(graph.start_hub):
            raise MapValidationError(
                f"'{graph.end_hub.name}' is unreachable from "
                f"'{graph.start_hub.name}'"
            )

        # Resumen temporal mientras no exista el simulador (SP08).
        print(f"Map loaded: {args.map_file}")
        print(f"Drones: {nb_drones}")
        print(
            f"Zones: {len(graph.zones)} "
            f"(start_hub={graph.start_hub.name}, "
            f"end_hub={graph.end_hub.name})"
        )
        print(f"Connections: {len(graph.connections)}")
        return 0

    except MapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
