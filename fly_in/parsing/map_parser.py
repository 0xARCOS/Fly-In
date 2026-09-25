"""Parser del formato de mapa de Fly-In (Cap. VI y VII.4).

Reglas de validación:

- Primera línea no vacía: nb_drones: <entero positivo>
- Exactamente un start_hub: y un end_hub: en todo el archivo
- Nombres de zona únicos, sin guiones ni espacios
- Coordenadas siempre enteras (pueden ser negativas)
- connection: solo referencia zonas ya definidas antes en el archivo
- Sin conexiones duplicadas (a-b == b-a) ni conexiones de una zona consigo
- Metadatos: tokens clave=valor, sin claves ni valores vacíos, sin claves
  repetidas, y solo claves válidas para el tipo de línea
- zone= solo uno de: normal, restricted, priority, blocked
- max_drones y max_link_capacity enteros positivos si están presentes
- max_drones en start_hub/end_hub se ignora (no es error): su capacidad es
  ilimitada
- start_hub y end_hub no pueden ser 'blocked'
- Todo lo que hay tras '#' es comentario
- Cualquier fallo → MapParseError con línea y causa, o MapValidationError
  si el fallo es del archivo entero
"""

from typing import Dict, FrozenSet, List, Tuple

from fly_in.models.errors import MapParseError, MapValidationError
from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED, Zone, ZoneType

ZONE_KEYS: FrozenSet[str] = frozenset({"zone", "color", "max_drones"})
CONNECTION_KEYS: FrozenSet[str] = frozenset({"max_link_capacity"})
ZONE_ROLES = ("hub", "start_hub", "end_hub")


def clean_lines(map_content: str) -> List[Tuple[int, str]]:
    """Limpia el contenido de un archivo de mapa.

    - Elimina espacios al principio y al final de cada línea
    - Ignora comentarios (todo lo que esté a la derecha de #)
    - Omite líneas vacías (o que se queden vacías tras quitar comentarios)

    Returns:
        Lista de tuplas (número de línea original 1-based, texto limpio).
    """
    result: List[Tuple[int, str]] = []
    for line_index, line in enumerate(map_content.splitlines(), start=1):
        stripped = line.split("#", 1)[0].strip()
        if stripped:
            result.append((line_index, stripped))
    return result


def parse_metadata(
    metadata_str: str, allowed_keys: FrozenSet[str]
) -> Dict[str, str]:
    """Convierte un bloque '[k=v k2=v2]' en diccionario.

    Raises:
        ValueError: Si faltan los corchetes, un token no es clave=valor, la
            clave o el valor están vacíos, una clave se repite o no está en
            `allowed_keys`.
    """
    stripped = metadata_str.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        raise ValueError(
            f"Metadata must be wrapped in '[' and ']': '{metadata_str}'"
        )

    metadata: Dict[str, str] = {}
    for token in stripped[1:-1].split():
        key, sep, value = token.partition("=")
        if not sep or not key or not value:
            raise ValueError(
                f"Invalid metadata token '{token}', expected key=value"
            )
        if key not in allowed_keys:
            raise ValueError(
                f"Unknown metadata key '{key}', "
                f"allowed here: {sorted(allowed_keys)}"
            )
        if key in metadata:
            raise ValueError(f"Duplicate metadata key '{key}'")
        metadata[key] = value
    return metadata


def parse_positive_int(value: str, field: str) -> int:
    """Convierte `value` en entero positivo.

    Raises:
        ValueError: Si no es un entero o no es mayor que cero.
    """
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{field} must be an integer, got '{value}'")
    if number <= 0:
        raise ValueError(f"{field} must be a positive integer, got {number}")
    return number


def parse_zone_type(value: str) -> ZoneType:
    """Convierte el texto de 'zone=' en ZoneType.

    Raises:
        ValueError: Si no es uno de los cuatro tipos válidos.
    """
    try:
        return ZoneType(value)
    except ValueError:
        valid = [zone_type.value for zone_type in ZoneType]
        raise ValueError(
            f"Invalid zone type '{value}', must be one of {valid}"
        )


def parse_zone_line(line: str) -> Tuple[str, str, int, int, Dict[str, str]]:
    """Disecciona una línea de zona.

    Input: "hub: roof1 3 4 [zone=restricted]"
    Output: ("hub", "roof1", 3, 4, {"zone": "restricted"})

    Raises:
        ValueError: Si el formato, el nombre, las coordenadas o los
            metadatos no son válidos.
    """
    if ":" not in line:
        raise ValueError("Line must contain ':' to separate the role")
    role, rest = line.split(":", 1)
    role = role.strip()

    metadata: Dict[str, str] = {}
    if "[" in rest:
        bracket_index = rest.index("[")
        metadata = parse_metadata(rest[bracket_index:], ZONE_KEYS)
        rest = rest[:bracket_index]

    fields = rest.split()
    if len(fields) != 3:
        raise ValueError(
            f"Expected '<name> <x> <y>', got {len(fields)} value(s)"
        )
    name, x_str, y_str = fields
    if "-" in name:
        raise ValueError(f"Zone name can't contain '-': '{name}'")

    try:
        x = int(x_str)
        y = int(y_str)
    except ValueError:
        raise ValueError(
            f"Coordinates must be integers, got '{x_str}' '{y_str}'"
        )
    return (role, name, x, y, metadata)


def parse_connection_line(line: str) -> Tuple[str, str, Dict[str, str]]:
    """Disecciona una línea de conexión.

    Input: "connection: corridorA-tunnelB [max_link_capacity=2]"
    Output: ("corridorA", "tunnelB", {"max_link_capacity": "2"})

    Raises:
        ValueError: Si no hay exactamente dos zonas separadas por '-', una
            está vacía, se conecta una zona consigo misma o los metadatos no
            son válidos.
    """
    if not line.startswith("connection:"):
        raise ValueError("Line must start with 'connection:'")
    body = line.split(":", 1)[1].strip()

    metadata: Dict[str, str] = {}
    if "[" in body:
        bracket_index = body.index("[")
        metadata = parse_metadata(body[bracket_index:], CONNECTION_KEYS)
        body = body[:bracket_index].strip()

    extremes = body.split("-")
    if len(extremes) != 2:
        raise ValueError(
            f"Expected exactly 2 zones separated by '-', "
            f"got {len(extremes)}"
        )
    origin_zone = extremes[0].strip()
    end_zone = extremes[1].strip()
    if not origin_zone or not end_zone:
        raise ValueError("Connection zone names can't be empty")
    if origin_zone == end_zone:
        raise ValueError(f"A zone can't connect to itself: '{origin_zone}'")
    return (origin_zone, end_zone, metadata)


class MapParser:
    """Convierte el texto de un mapa en `(nb_drones, Graph)`."""

    @staticmethod
    def parse(map_content: str) -> Tuple[int, Graph]:
        """Parsea y valida un mapa completo.

        Returns:
            Tupla (número de drones, grafo con start_hub y end_hub).

        Raises:
            MapParseError: Si una línea concreta es inválida.
            MapValidationError: Si el archivo está vacío o le falta
                start_hub/end_hub.
        """
        cleaned = clean_lines(map_content)
        if not cleaned:
            raise MapValidationError("Map file is empty")

        first_line_num, first_line_txt = cleaned[0]
        if not first_line_txt.startswith("nb_drones:"):
            raise MapParseError(
                first_line_num,
                first_line_txt,
                "First line must define 'nb_drones: <positive_integer>'",
            )
        try:
            nb_drones = parse_positive_int(
                first_line_txt.split(":", 1)[1].strip(), "nb_drones"
            )
        except ValueError as exc:
            raise MapParseError(first_line_num, first_line_txt, str(exc))

        graph = Graph()
        for num_line, content in cleaned[1:]:
            try:
                MapParser._parse_line(content, graph)
            except ValueError as exc:
                raise MapParseError(num_line, content, str(exc))

        if graph.start_hub is None:
            raise MapValidationError("Map needs a 'start_hub'")
        if graph.end_hub is None:
            raise MapValidationError("Map needs an 'end_hub'")
        return nb_drones, graph

    @staticmethod
    def _parse_line(content: str, graph: Graph) -> None:
        """Parsea una línea de zona o de conexión y la añade al grafo.

        Raises:
            ValueError: Si la línea no es válida.
        """
        if content.startswith("connection:"):
            origin, destination, meta = parse_connection_line(content)
            capacity = parse_positive_int(
                meta.get("max_link_capacity", "1"), "max_link_capacity"
            )
            graph.add_connection(origin, destination, capacity)
            return

        if content.split(":", 1)[0] not in ZONE_ROLES or ":" not in content:
            raise ValueError(f"Unknown directive: '{content}'")

        role, name, x, y, meta = parse_zone_line(content)
        zone_type = parse_zone_type(meta.get("zone", "normal"))
        max_drones: float
        if role in ("start_hub", "end_hub"):
            # Cap. VII.4: max_drones se ignora aquí, aunque sea inválido.
            max_drones = UNLIMITED
            if zone_type is ZoneType.BLOCKED:
                raise ValueError(f"'{role}' can't be a blocked zone")
        else:
            max_drones = parse_positive_int(
                meta.get("max_drones", "1"), "max_drones"
            )
        graph.add_zone(
            Zone(name, x, y, zone_type, max_drones, meta.get("color")),
            role,
        )
