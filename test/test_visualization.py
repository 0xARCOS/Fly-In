"""Tests de la visualización (SP10).

La calidad visual se juzga a ojo; aquí se comprueba lo que no debe fallar
nunca: nada de ANSI sin color, ningún crash por un color raro, un color
distinto para cada dron y la grabación completa, turno a turno.
"""

import math
from pathlib import Path
from typing import Tuple

import pytest

from fly_in.models.graph import Graph
from fly_in.parsing.map_parser import MapParser
from fly_in.simulation.simulator import Simulator
from fly_in.visualization.palette import RESET, Painter, Palette
from fly_in.visualization.recorder import ReplayRecorder

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
ALL_MAPS = sorted(
    str(p.relative_to(MAPS_DIR))
    for p in list((MAPS_DIR / "valid").glob("*.txt"))
    + list((MAPS_DIR / "oficial_maps").glob("*/*.txt"))
)


def load(relative: str) -> Tuple[int, Graph]:
    """(nb_drones, grafo) de un mapa de maps/."""
    return MapParser.parse((MAPS_DIR / relative).read_text())


# --- paleta------------------------------------------------------------

@pytest.mark.parametrize(
    "name", ["red", "RED", "crimson", "turquesa", "#ff8800", "rainbow", "x"]
)
def test_any_color_name_resolves(name: str) -> None:
    rgb = Palette.resolve(name, frame=3)
    assert rgb is not None and all(0 <= c <= 255 for c in rgb)


def test_unknown_color_is_stable_and_no_color_is_none() -> None:
    assert Palette.resolve("turquesa") == Palette.resolve("turquesa")
    assert Palette.resolve(None) is None


def test_first_seven_drones_use_distinct_okabe_ito_colors() -> None:
    okabe_ito_without_black = {
        (230, 159, 0), (86, 180, 233), (0, 158, 115), (240, 228, 66),
        (0, 114, 178), (213, 94, 0), (204, 121, 167),
    }
    colors = [Palette.drone_color(drone) for drone in range(1, 8)]
    assert set(colors) == okabe_ito_without_black
    for i, a in enumerate(colors):
        for b in colors[i + 1:]:
            assert math.dist(a, b) > 60, (a, b)


def test_rainbow_changes_with_the_frame() -> None:
    assert Palette.resolve("rainbow", 0) != Palette.resolve("rainbow", 5)


def test_painter_always_resets() -> None:
    text = Painter(True)("hola", fg=(255, 0, 0), bold=True)
    assert text.endswith(RESET) and Painter.strip_ansi(text) == "hola"


def test_painter_disabled_emits_plain_text() -> None:
    assert Painter(False)("hola", fg=(255, 0, 0), bold=True) == "hola"


def test_basic_palette_fallback_uses_16_colors() -> None:
    text = Painter(True, truecolor=False)("x", fg=(250, 10, 10))
    assert "38;2" not in text and "\033[91m" in text


def test_visible_len_and_pad_ignore_ansi() -> None:
    styled = Painter(True)("abc", fg=(1, 2, 3))
    assert Painter.visible_len(styled) == 3
    assert Painter.visible_len(Painter.pad(styled, 7)) == 7


# --- grabación ----------------------------------------------------------

def test_recorder_keeps_one_frame_per_turn_plus_the_start() -> None:
    nb_drones, graph = load("valid/restricted_chain.txt")
    sim = Simulator(graph, nb_drones)
    recorder = ReplayRecorder(sim.drones)
    trace = sim.run(recorder)
    assert len(recorder.positions) == len(trace) + 1
    assert recorder.positions[0] == {"1": ["z", "start"]}
    assert recorder.positions[1] == {"1": ["a", "start", "r1"]}
    assert recorder.positions[-1] == {"1": ["d"]}
    assert recorder.lines[0] == "" and recorder.lines[2] == "D1-r1"
