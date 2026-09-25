"""Tests del parser de mapas (SP02) y de las invariantes de Graph (SP01)."""

from pathlib import Path

import pytest

from fly_in.models.errors import MapError, MapParseError, MapValidationError
from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED, Zone, ZoneType
from fly_in.parsing.map_parser import MapParser, clean_lines

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
HEADER = "nb_drones: 2\nstart_hub: s 0 0\nend_hub: e 2 0\n"


def parse_file(relative: str) -> tuple[int, Graph]:
    """Parsea un mapa de la carpeta maps/."""
    return MapParser.parse((MAPS_DIR / relative).read_text())


# --- mapas de la carpeta maps/ -----------------------------------------

@pytest.mark.parametrize(
    "path",
    sorted(p.relative_to(MAPS_DIR).as_posix()
           for p in (MAPS_DIR / "valid").glob("*.txt")),
)
def test_valid_maps_parse(path: str) -> None:
    nb_drones, graph = parse_file(path)
    assert nb_drones > 0
    assert graph.start_hub is not None
    assert graph.end_hub is not None


@pytest.mark.parametrize(
    "path",
    sorted(p.relative_to(MAPS_DIR).as_posix()
           for p in (MAPS_DIR / "oficial_maps").glob("*/*.txt")),
)
def test_official_maps_parse(path: str) -> None:
    _, graph = parse_file(path)
    assert graph.start_hub is not None
    assert graph.end_hub is not None


@pytest.mark.parametrize(
    ("path", "error", "fragment"),
    [
        ("errors/connection_unknown_zone.txt", MapParseError, "undefined"),
        ("errors/dash_in_name.txt", MapParseError, "'-'"),
        ("errors/duplicate_connection.txt", MapParseError, "Duplicate"),
        ("errors/duplicate_zone_name.txt", MapParseError, "already"),
        ("errors/invalid_zone_type.txt", MapParseError, "zone type"),
        ("errors/malformed_metadata.txt", MapParseError, "etadata"),
        ("errors/missing_nb_drones.txt", MapParseError, "nb_drones"),
        ("errors/negative_capacity.txt", MapParseError, "positive"),
        ("errors/no_start.txt", MapValidationError, "start_hub"),
        ("errors/two_starts.txt", MapParseError, "start_hub"),
    ],
)
def test_error_maps_fail_with_the_right_cause(
    path: str, error: type[MapError], fragment: str
) -> None:
    with pytest.raises(error) as info:
        parse_file(path)
    assert fragment in str(info.value)


def test_parse_error_reports_line_number_and_content() -> None:
    with pytest.raises(MapParseError) as info:
        MapParser.parse(HEADER + "# comentario\nhub: a 1 1 [zone=lava]\n")
    assert info.value.line_num == 5
    assert info.value.line_content == "hub: a 1 1 [zone=lava]"
    assert str(info.value).startswith("Line 5:")


# --- archivo en conjunto ---------------------------------------------

@pytest.mark.parametrize("content", ["", "\n\n", "# solo\n  # comentarios\n"])
def test_empty_map_is_a_map_error_not_a_crash(content: str) -> None:
    with pytest.raises(MapValidationError):
        MapParser.parse(content)


def test_missing_end_hub() -> None:
    with pytest.raises(MapValidationError, match="end_hub"):
        MapParser.parse("nb_drones: 1\nstart_hub: s 0 0\n")


@pytest.mark.parametrize("value", ["0", "-3", "2.5", "abc", ""])
def test_nb_drones_must_be_a_positive_integer(value: str) -> None:
    with pytest.raises(MapParseError) as info:
        MapParser.parse(f"nb_drones: {value}\nstart_hub: s 0 0\n")
    assert info.value.line_num == 1


def test_nb_drones_can_only_appear_once() -> None:
    with pytest.raises(MapParseError, match="Unknown directive"):
        MapParser.parse(HEADER + "nb_drones: 3\n")


def test_comments_and_blank_lines_keep_original_line_numbers() -> None:
    lines = clean_lines("# c\n\nnb_drones: 1  # tail\n   \nhub: a 0 0\n")
    assert lines == [(3, "nb_drones: 1"), (5, "hub: a 0 0")]


def test_windows_line_endings_are_accepted() -> None:
    content = (HEADER + "connection: s-e\n").replace("\n", "\r\n")
    _, graph = MapParser.parse(content)
    assert len(graph.connections) == 1


# --- líneas de zona ----------------------------------------------------

def test_zone_defaults() -> None:
    _, graph = MapParser.parse(HEADER + "hub: a 1 1\n")
    zone = graph.get_zone("a")
    assert zone.zone_type is ZoneType.NORMAL
    assert zone.max_drones == 1
    assert zone.color is None


def test_zone_metadata_in_any_order() -> None:
    _, graph = MapParser.parse(
        HEADER + "hub: a 1 1 [max_drones=3 color=red zone=priority]\n"
    )
    zone = graph.get_zone("a")
    assert (zone.zone_type, zone.max_drones, zone.color) == (
        ZoneType.PRIORITY, 3, "red"
    )


def test_negative_coordinates_are_valid_integers() -> None:
    _, graph = MapParser.parse(HEADER + "hub: a -1 -2\n")
    assert (graph.get_zone("a").x, graph.get_zone("a").y) == (-1, -2)


@pytest.mark.parametrize(
    "line",
    [
        "hub: a 1.5 2",
        "hub: a x 2",
        "hub: a 1",
        "hub: a 1 1 extra",
        "hub: a-b 1 1",
        "hub : a 1 1",
        "zone: a 1 1",
        "hub: a[b 1 1",
    ],
)
def test_malformed_zone_lines(line: str) -> None:
    with pytest.raises(MapParseError):
        MapParser.parse(HEADER + line + "\n")


@pytest.mark.parametrize(
    "metadata",
    [
        "[zone=normal",
        "[zone=normal] trailing",
        "[=x]",
        "[zone=]",
        "[zone]",
        "[zone=blocked zone=normal]",
        "[foo=bar]",
        "[max_link_capacity=2]",
        "[zone=Normal]",
        "[max_drones=0]",
        "[max_drones=-1]",
        "[max_drones=2.0]",
        "[max_drones=abc]",
    ],
)
def test_invalid_zone_metadata(metadata: str) -> None:
    with pytest.raises(MapParseError):
        MapParser.parse(HEADER + f"hub: a 1 1 {metadata}\n")


def test_empty_metadata_block_is_valid() -> None:
    _, graph = MapParser.parse(HEADER + "hub: a 1 1 []\n")
    assert graph.get_zone("a").zone_type is ZoneType.NORMAL


def test_start_and_end_ignore_max_drones_even_if_invalid() -> None:
    _, graph = MapParser.parse(
        "nb_drones: 1\n"
        "start_hub: s 0 0 [max_drones=-5]\n"
        "end_hub: e 1 0 [max_drones=abc]\n"
    )
    assert graph.start_hub is not None and graph.end_hub is not None
    assert graph.start_hub.max_drones == UNLIMITED
    assert graph.end_hub.max_drones == UNLIMITED


@pytest.mark.parametrize("role", ["start_hub", "end_hub"])
def test_start_and_end_cannot_be_blocked(role: str) -> None:
    other = "end_hub" if role == "start_hub" else "start_hub"
    with pytest.raises(MapParseError, match="blocked"):
        MapParser.parse(
            f"nb_drones: 1\n{role}: a 0 0 [zone=blocked]\n{other}: b 1 0\n"
        )


# --- líneas de conexión ------------------------------------------------

def test_connection_default_and_explicit_capacity() -> None:
    _, graph = MapParser.parse(
        HEADER + "hub: a 1 1\nconnection: s-a\n"
        "connection: a-e [max_link_capacity=3]\n"
    )
    capacities = [c.max_link_capacity for c in graph.connections]
    assert capacities == [1, 3]


def test_spaces_around_the_dash_are_tolerated() -> None:
    _, graph = MapParser.parse(HEADER + "connection: s - e\n")
    assert graph.connections[0].name == "s-e"


@pytest.mark.parametrize(
    "line",
    [
        "connection: s-s",
        "connection: s-x",
        "connection: s-a-e",
        "connection: s-",
        "connection: se",
        "connection: s-e [max_link_capacity=0]",
        "connection: s-e [max_drones=2]",
        "connection: s-e [max_link_capacity=1 max_link_capacity=2]",
    ],
)
def test_invalid_connection_lines(line: str) -> None:
    with pytest.raises(MapParseError):
        MapParser.parse(HEADER + line + "\n")


def test_reversed_connection_is_a_duplicate() -> None:
    with pytest.raises(MapParseError, match="Duplicate"):
        MapParser.parse(HEADER + "connection: s-e\nconnection: e-s\n")


def test_connection_must_follow_both_zone_definitions() -> None:
    with pytest.raises(MapParseError, match="undefined"):
        MapParser.parse(
            "nb_drones: 1\nstart_hub: s 0 0\nconnection: s-e\nend_hub: e 1 0\n"
        )


# --- Graph -----------------------------------------------------------

def small_graph() -> Graph:
    """s - a - e, más una zona suelta 'lonely'."""
    graph = Graph()
    graph.add_zone(Zone("s", 0, 0), "start_hub")
    graph.add_zone(Zone("a", 1, 0), "hub")
    graph.add_zone(Zone("e", 2, 0), "end_hub")
    graph.add_zone(Zone("lonely", 3, 3), "hub")
    graph.add_connection("s", "a", 1)
    graph.add_connection("a", "e", 2)
    return graph


def test_neighbors_in_definition_order() -> None:
    graph = small_graph()
    a = graph.get_zone("a")
    names = [c.other_end(a).name for c in graph.neighbors(a)]
    assert names == ["s", "e"]
    assert graph.neighbors(graph.get_zone("lonely")) == []


def test_neighbors_returns_a_copy() -> None:
    graph = small_graph()
    a = graph.get_zone("a")
    graph.neighbors(a).clear()
    assert len(graph.neighbors(a)) == 2


def test_connection_between_works_in_both_directions() -> None:
    graph = small_graph()
    a, e = graph.get_zone("a"), graph.get_zone("e")
    assert graph.connection_between(a, e) is graph.connection_between(e, a)
    assert graph.connection_between(a, e).max_link_capacity == 2


def test_connection_between_unconnected_zones_raises() -> None:
    graph = small_graph()
    with pytest.raises(ValueError):
        graph.connection_between(graph.get_zone("s"), graph.get_zone("e"))
