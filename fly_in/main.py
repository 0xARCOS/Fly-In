import sys
import argparse
from pathlib import Path

from fly_in.models.errors import MapError
from fly_in.parsing.map_parser import MapParser

"""
    22/9/26
    - Definir argumentos del CLI
    - Lectura Segura del Archivo (read_map_file)
    - La Frontera Centralizada de Excepciones en main.py
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fly-In: Simulador de enrutamiento de drones"
    )
    parser.add_argument(
        "map_file", type=Path, help="Ruta al archivo del mapa (.map)"
    )
    parser.add_argument(
        "-w", "--window", type=int, default=8,
        help="Tamaño de la ventana WHCA*"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Desactiva los colores en terminal"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Desactiva la virtualización en tiempo real"
    )
    parser.add_argument(
        "--metrics", action="store_true",
        help="Muestra métricas secundarias en strerr"
    )
    return parser


def read_map_file(path: Path) -> str:
    """
        Lee el archivo de mapa y devuelve su contenido.

        Raises:
            MapError: Si el archivo no existe, es un directorio, no tiene permiso o no es UTF-8
    """
    if not path.exists():
        raise MapError(f"No existe el archivo de mapa: {path}")
    if path.is_dir():
        raise MapError(f"La ruta no es un archivo válido: {path}")

    try:
        return path.read_text(encoding="utf-8")
    except PermissionError:
        raise MapError(f"Sin permiso para leer el archivo: {path}")
    except UnicodeDecodeError:
        raise MapError(f"El archivo no es texto legible UTF-8: {path}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        content = read_map_file(args.map_file)
        nb_drones, graph = MapParser.parse(content)
        assert graph.start_hub is not None
        assert graph.end_hub is not None

        # Resumen temporal mientras no exista el simulador
        print(f"Mapa cargado con éxito: {args.map_file}")
        print(f"Drones: {nb_drones}")
        print(
            f"Zonas: {len(graph.zones)} "
            f"(start_hub={graph.start_hub.name}, end_hub={graph.end_hub.name})"
        )
        print(f"Conexiones: {len(graph.connections)}")
        return 0

    except MapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nSimulación cancelada por el usuario.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
