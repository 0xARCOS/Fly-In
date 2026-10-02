"""Tests de la sesión (SP10): elección de vista, log, escena y ventana.

La ventana se prueba de verdad, con el driver de vídeo `dummy` de SDL: pygame
dibuja en memoria sin necesitar pantalla.
"""

import io
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator, List, Tuple

import pytest

from fly_in.models.graph import Graph
from fly_in.parsing.map_parser import MapParser
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.simulator import Simulator
from fly_in.visualization.event_log import EventLog
from fly_in.visualization.palette import Painter, Palette
from fly_in.visualization.recorder import ReplayRecorder
from fly_in.visualization.scene import Scene
from fly_in.visualization.session import Run, Session

ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = ROOT / "maps"
ALL_MAPS = sorted(
    str(p.relative_to(MAPS_DIR))
    for p in list((MAPS_DIR / "valid").glob("*.txt"))
    + list((MAPS_DIR / "oficial_maps").glob("*/*.txt"))
)


def load(relative: str) -> Tuple[int, Graph]:
    """(nb_drones, grafo) de un mapa de maps/."""
    return MapParser.parse((MAPS_DIR / relative).read_text())


def simulate(relative: str) -> Run:
    """Una simulación completa lista para enseñarse."""
    nb_drones, graph = load(relative)
    sim = Simulator(graph, nb_drones)
    recorder = ReplayRecorder(sim.drones)
    trace = sim.run(recorder)
    metrics = Metrics.from_trace(trace, nb_drones, sim.elapsed)
    return Run(graph, nb_drones, trace, recorder, metrics, sim.replans,
               relative, 8, 10)


@pytest.fixture
def pygame_view(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """El módulo de la ventana, con vídeo en memoria (sin pantalla)."""
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from fly_in.visualization import pygame_view as module
    yield module
    import pygame
    pygame.quit()


# --- elección de vista ---------------------------------------------------

def test_quiet_wins_over_everything() -> None:
    assert Session.choose_view("window", True, True) == "none"


def test_auto_never_opens_a_window_without_a_terminal() -> None:
    assert Session.choose_view("auto", False, False) == "log"


def test_auto_opens_a_window_only_with_a_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Session, "display_available",
                        staticmethod(lambda: True))
    assert Session.choose_view("auto", False, True) == "window"
    monkeypatch.setattr(Session, "display_available",
                        staticmethod(lambda: False))
    assert Session.choose_view("auto", False, True) == "log"


# --- log de eventos ------------------------------------------------------

def test_plural() -> None:
    assert EventLog.plural(1, "drone") == "1 drone"
    assert EventLog.plural(3, "drone") == "3 drones"


def run_log(relative: str, color: bool) -> str:
    """Todo lo que escribe la vista de log, sin pausas."""
    stream = io.StringIO()
    Session("log", simulate(relative), Painter(color), stream, 0).play()
    return stream.getvalue()


def test_log_tells_the_bottleneck_story() -> None:
    out = run_log("valid/bottleneck.txt", color=False)
    assert "MISSION LOG" in out and "3 drones · 3 zones · 2 links" in out
    assert "── T02" in out and "▸ D1-goal D2-narrow" in out
    assert "D1   ★ DELIVERED to goal" in out and "3/3" in out
    assert "holding at start: D3" in out
    assert "narrow is FULL (1/1)" in out
    assert "⟳ replan" in out
    assert "MISSION COMPLETE · 4 TURNS · PAR 10 ✔" in out


def test_log_narrates_the_restricted_transit() -> None:
    out = run_log("valid/restricted_chain.txt", color=False)
    assert "◆ takes off → r1 via start-r1 (2 turns in the air)" in out
    assert "◆ lands on r1" in out


def test_log_without_color_has_no_ansi() -> None:
    out = run_log("oficial_maps/hard/01_maze_nightmare.txt", color=False)
    assert "\033" not in out


def test_each_drone_has_one_color_in_the_log() -> None:
    out = run_log("valid/bottleneck.txt", color=True)
    for drone in (1, 2, 3):
        codes = set(re.findall(rf"\033\[([0-9;]*)mD{drone}(?![-\d])", out))
        r, g, b = Palette.drone_color(drone)
        assert codes == {f"1;38;2;{r};{g};{b}"}, (drone, codes)


def test_log_holding_list_is_summarised() -> None:
    out = run_log("oficial_maps/challenger/01_the_impossible_dream.txt",
                  color=False)
    assert "… +" in out, "25 drones esperando no se listan uno a uno"


def test_capacity_alert_only_when_a_zone_fills() -> None:
    nb_drones, graph = load("valid/bottleneck.txt")
    stream = io.StringIO()
    log = EventLog(graph, nb_drones, stream, Painter(False), "m", 8)
    full = {"1": ["z", "narrow"]}
    log._capacity_alerts(full)
    log._capacity_alerts(full)
    assert stream.getvalue().count("FULL") == 1


# --- escena (sin pygame) -------------------------------------------------

def scene_of(relative: str) -> Scene:
    """La escena de un mapa ya simulado."""
    run = simulate(relative)
    return Scene(run.graph, run.recorder.positions, run.recorder.lines,
                 run.replans)


def test_scene_puts_airborne_drones_on_the_middle_of_the_link() -> None:
    scene = scene_of("valid/restricted_chain.txt")
    spot = scene.spots[1][1]
    start, r1 = scene.points["start"], scene.points["r1"]
    assert spot.airborne and spot.zone is None
    assert spot.anchor == ((start[0] + r1[0]) / 2, (start[1] + r1[1]) / 2)
    assert scene.airborne[1] == 1


def test_scene_gives_every_drone_its_own_slot_in_a_crowd() -> None:
    scene = scene_of("valid/bottleneck.txt")
    slots = [scene.spots[0][d].slot for d in scene.ids]
    assert sorted(slots) == [0, 1, 2]
    assert all(scene.spots[0][d].crowd == 3 for d in scene.ids)


def test_scene_knows_which_links_each_turn_uses() -> None:
    scene = scene_of("valid/bottleneck.txt")
    assert scene.used[0] == []
    first = scene.used[1]
    assert [(u.origin, u.target, u.drone_id) for u in first] == [
        ("start", "narrow", 1)]


def test_scene_counts_deliveries_and_replans() -> None:
    scene = scene_of("valid/bottleneck.txt")
    assert scene.delivered[0] == 0 and scene.delivered[-1] == 3
    assert scene.newly_delivered(2) == [1]
    assert 1 in scene.replan_turns, "la replanificación del instante 0"


# --- ventana pygame -------------------------------------------------------

@pytest.mark.parametrize("map_file", ALL_MAPS)
def test_window_draws_every_turn_of_every_map(
    pygame_view: ModuleType, map_file: str
) -> None:
    scene = scene_of(map_file)
    with pygame_view.PygameView(scene, map_file, 8) as view:
        assert view.open()
        for turn in range(1, scene.last + 1):
            view._paint(turn, 0.5)
            view._paint(turn, 1.0)


def test_window_session_plays_in_sync_with_the_log(
    pygame_view: ModuleType,
) -> None:
    stream = io.StringIO()
    Session("window", simulate("valid/bottleneck.txt"), Painter(False),
            stream, 0).play()
    out = stream.getvalue()
    assert "◉ WINDOW" in out and "» GO" in out
    assert out.count("── T0") == 4
    assert "MISSION COMPLETE" in out


def test_closing_the_window_keeps_the_terminal_going(
    pygame_view: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    played: List[int] = []

    def close_after_one(self: object, turn: int, seconds: float) -> None:
        played.append(turn)
        setattr(self, "closed", True)

    monkeypatch.setattr(pygame_view.PygameView, "play_turn",
                        close_after_one)
    stream = io.StringIO()
    Session("window", simulate("valid/bottleneck.txt"), Painter(False),
            stream, 0).play()
    out = stream.getvalue()
    assert played == [1]
    assert out.count("window closed · terminal only") == 1
    assert "MISSION COMPLETE" in out


def test_quit_event_closes_the_window_at_once(
    pygame_view: ModuleType,
) -> None:
    import pygame
    scene = scene_of("valid/linear.txt")
    with pygame_view.PygameView(scene, "m", 8) as view:
        assert view.open()
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        view.play_turn(1, 5.0)
        assert view.closed and not pygame.get_init()
        view.play_turn(2, 5.0)   # ya cerrada: no hace nada ni falla


def test_space_pauses_and_resumes_the_animation(
    pygame_view: ModuleType,
) -> None:
    import pygame
    scene = scene_of("valid/linear.txt")
    with pygame_view.PygameView(scene, "m", 8) as view:
        assert view.open()
        space = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        pygame.event.post(space)
        view._tick()
        assert view._paused
        pygame.event.post(space)
        view._tick()
        assert not view._paused


def test_end_card_waits_for_a_key_not_forever(
    pygame_view: ModuleType,
) -> None:
    import pygame
    run = simulate("valid/linear.txt")
    scene = Scene(run.graph, run.recorder.positions, run.recorder.lines)
    with pygame_view.PygameView(scene, "m", 8) as view:
        assert view.open()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN,
                                             key=pygame.K_RETURN))
        view.finish(run.metrics, 30.0)   # vuelve con la tecla, no a los 30 s
        view.finish(run.metrics, 0.0)


def test_window_is_a_context_manager_that_quits_pygame(
    pygame_view: ModuleType,
) -> None:
    import pygame
    with pygame_view.PygameView(scene_of("valid/linear.txt"), "m",
                                8) as view:
        assert view.open() and pygame.get_init()
    assert not pygame.get_init()


def test_no_window_means_terminal_only(
    pygame_view: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pygame_view.PygameView, "open", lambda self: False)
    stream = io.StringIO()
    Session("window", simulate("valid/linear.txt"), Painter(False), stream,
            0).play()
    out = stream.getvalue()
    assert "cannot open a window · terminal only" in out
    assert "MISSION COMPLETE" in out


def test_missing_pygame_means_terminal_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # None en sys.modules hace que el import falle con ImportError.
    monkeypatch.setitem(sys.modules, "fly_in.visualization.pygame_view",
                        None)
    stream = io.StringIO()
    Session("window", simulate("valid/linear.txt"), Painter(False), stream,
            0).play()
    out = stream.getvalue()
    assert "pygame is not installed · terminal only" in out
    assert "MISSION COMPLETE" in out


def test_pygame_never_writes_to_stdout() -> None:
    # pygame saluda por stdout al importarse: stdout es solo del subject.
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    env.pop("PYGAME_HIDE_SUPPORT_PROMPT", None)
    result = subprocess.run(
        [sys.executable, "-m", "fly_in.main", "maps/valid/linear.txt",
         "--view", "window", "--delay", "0"],
        cwd=ROOT, capture_output=True, text=True, timeout=60, env=env,
    )
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "D1-waypoint1",
        "D1-waypoint2 D2-waypoint1",
        "D1-goal D2-waypoint2",
        "D2-goal",
    ]
    assert "◉ WINDOW" in result.stderr
