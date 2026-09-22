from typing import Dict, List, Tuple

from fly_in.models.errors import MapParseError
from fly_in.models.graph import Graph
from fly_in.models.zone import ALLOWED_ZONE_TYPES, Zone

"""
Reglas de validación (checklist del parser):

- Primera línea no vacía: nb_drones: <positivo>
- Exactamente un start_hub: y un end_hub: en todo el archivo
- Nombres de zona únicos
- Coordenadas siempre enteras
- Nombres sin guiones ni espacios
- connection: solo referencia zonas ya definidas antes en el archivo
  (o define claramente si permites forward-reference — decisión de
  diseño a documentar)
- Sin conexiones duplicadas (a-b == b-a)
- zone= solo uno de: normal, restricted, priority, blocked —
  cualquier otro valor = error
- max_drones y max_link_capacity enteros positivos si están presentes
- max_drones en start_hub/end_hub se ignora silenciosamente (no es error)
- Líneas que empiezan por # se ignoran completas
- Cualquier otro fallo de formato → excepción con línea y causa
  en el mensaje
"""


def clean_lines(map_content: str) -> List[Tuple[int, str]]:
    """
    Limpia el contenido de un archivo de mapa:
    - Elimina espacios al principio y final de cada línea (strip)
    - Ignora comentarios (todo lo que esté a la derecha de #)
    - Omite líneas vacías (o que se queden vacías tras quitar comentarios)
    - Devuelve lista de tuplas (numero_de_linea_original, texto_limpio)

    El número de linea es el indice original (1-based) del archivo.
    """
    result: List[Tuple[int, str]] = []
    lines = map_content.splitlines()

    for line_index, line in enumerate(lines, start=1):
        stripped = line.strip()  # remove ' '
        if '#' in stripped:
            stripped = stripped[:stripped.index('#')].strip()
        if not stripped:
            continue
        result.append((line_index, stripped))
    return result


def parse_metadata(metadata_str: str) -> Dict[str, str]:
    """
    - Elimina los corchetes exteriores
    - Separa los elementos por tokens
    - Cada elemento debe contener obligatoriamente un signo "="
        para separar la clave del valor.
    - Limpia los espacios adicionales
    """
    metadata: Dict[str, str] = {}
    stripped = metadata_str.strip()
    if not stripped.startswith('[') or not stripped.endswith(']'):
        raise ValueError(
            f"Metadata must be wrapped in '[' and ']': '{metadata_str}'"
        )

    stripped = stripped[1:-1]
    if not stripped.strip():
        return metadata
    tokens = stripped.split()
    for token in tokens:
        if "=" not in token:
            raise ValueError(f"Invalid token without '=': '{token}'")
        parts = token.split('=', 1)
        key = parts[0].strip()
        value = parts[1].strip()
        metadata[key] = value
    return metadata


def parse_zone_line(line: str) -> Tuple[str, str, int, int, Dict[str, str]]:
    """
    Input: "hub: roof1 3 4 [zone=restricted]"
    Output: Tuple: [
        - rol
        - nombre
        - coordenada_x
        - coordenada_y
        - diccionario_metadatos
    ] Ej: ("hub", "roof1", 3, 4, {"zone": "restricted"})
    """
    # Separate rol
    if ":" not in line:
        raise ValueError("La línea debe contener ':' para separar el rol")

    rol, rest = line.split(":", 1)
    rol = rol.strip()

    # Aislar los corchetes (Metadatos)
    metadata = {}
    if "[" in rest:
        indexed = rest.index("[")
        basic_data = rest[:indexed]
        metadata_str = rest[indexed:]
        # Now we call parse_metadata function
        metadata = parse_metadata(metadata_str)
    else:
        basic_data = rest

    basic_data = basic_data.strip()
    lists = basic_data.split()
    if len(lists) != 3:
        raise ValueError(f"Waiting 3 values, got {len(lists)}")

    name = lists[0]
    if "-" in name:
        raise ValueError("zone name can't contain '-'")

    x_str = lists[1]
    y_str = lists[2]
    x = int(x_str)
    y = int(y_str)
    if x < 0 or y < 0:
        raise ValueError("Coords can't be negative")

    zone_type = metadata.get("zone", "normal")
    if zone_type not in ALLOWED_ZONE_TYPES:
        raise ValueError(
            f"Invalid zone type '{zone_type}', "
            f"must be one of {sorted(ALLOWED_ZONE_TYPES)}"
        )

    return (rol, name, x, y, metadata)


def parse_connection_line(line: str) -> Tuple[str, str, Dict[str, str]]:
    """
    Disecciona una línea de conexión.

    Input: "connection: corridorA-tunnelB [max_link_capacity=2]"
    Output: ("corridorA", "tunnelB", {"max_link_capacity":"2"})
    """
    if not line.startswith("connection:"):
        raise ValueError("La línea debe empezar con 'connection:'")

    parts = line.split(":", 1)
    body = parts[1].strip()

    metadata = {}
    if '[' in body:
        bracket_index = body.index("[")
        metadata_str = body[bracket_index:]
        metadata = parse_metadata(metadata_str)
        body = body[:bracket_index].strip()
    extremes = body.split('-')

    if len(extremes) != 2:
        raise ValueError(
            f"Invalid Format: exactly 2 zones separated by '-' "
            f"expected, {len(extremes)} obtained"
        )

    origin_zone = extremes[0].strip()
    end_zone = extremes[1].strip()

    if not origin_zone:
        raise ValueError("Origin zone name can't be empty")
    if not end_zone:
        raise ValueError("End zone name can't be empty")
    if origin_zone == end_zone:
        raise ValueError(f"A node can't connect with himself: '{origin_zone}'")

    return (origin_zone, end_zone, metadata)


class MapParser:
    @staticmethod
    def parse(map_content: str) -> Tuple[int, Graph]:
        # Clean lines and botain tuples
        cleaned = clean_lines(map_content)
        if not cleaned:
            raise ValueError("Map file is empty")

        # Validate first line start with 'nb_drones'
        first_line_num, first_line_txt = cleaned[0]
        if not first_line_txt.startswith("nb_drones:"):
            raise MapParseError(
                first_line_num,
                first_line_txt,
                "First line must define 'nb_drones'"
            )

        # Extract nums drones
        try:
            nb_drones_str = first_line_txt.split(":", 1)[1].strip()
            nb_drones = int(nb_drones_str)

            if nb_drones <= 0:
                raise ValueError("nb_drones must be a positive integer")
        except ValueError as e:
            raise MapParseError(
                first_line_num,
                first_line_txt,
                f"nb_drones must be a valid number: {e}"
            )

        graph = Graph()

        for num_line, content in cleaned[1:]:
            try:
                if content.startswith("connection:"):
                    origin, destination, meta = parse_connection_line(
                        content
                    )
                    max_link_capacity = int(meta.get("max_link_capacity", 1))
                    if max_link_capacity <= 0:
                        raise ValueError(
                            "max_link_capacity must be a positive integer"
                        )
                    graph.add_connection(
                        origin, destination, max_link_capacity
                    )
                elif (
                    content.startswith("hub:")
                    or content.startswith("start_hub:")
                    or content.startswith("end_hub:")
                ):
                    rol, name, x, y, meta = parse_zone_line(
                        content
                    )
                    max_drones = int(meta.get("max_drones", 1))
                    if max_drones <= 0:
                        raise ValueError(
                            "max_drones must be a positive integer"
                        )
                    color = meta.get("color")
                    zone_type = meta.get("zone", "normal")

                    new_zone = Zone(
                        name=name,
                        x=x,
                        y=y,
                        zone_type=zone_type,
                        max_drones=max_drones,
                        color=color
                    )
                    # rol será "hub", "start_hub" o "end_hub"
                    graph.add_zone(new_zone, rol)
                else:
                    raise ValueError(f"Unknown directive: '{content}'")

            except Exception as e:
                # If something fall, embolved with MapParseError
                raise MapParseError(num_line, content, str(e))

        if graph.start_hub is None:
            raise ValueError("Map need a 'start_hub'")

        if graph.end_hub is None:
            raise ValueError("Map need a 'end_hub'")

        return nb_drones, graph
