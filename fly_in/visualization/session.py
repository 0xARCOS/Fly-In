"""Cómo se enseña una simulación ya calculada (SP10).

La simulación tarda milisegundos; lo que dura es enseñarla. Hay dos vistas:

- `window`: la partida animada en una ventana pygame y el log de eventos en
  la terminal, avanzando juntos turno a turno.
- `log`: solo el log de eventos en la terminal.

`auto` elige `window` si hay terminal y pantalla gráfica, y `log` en otro
caso: con una tubería o sin pantalla nunca se intenta abrir una ventana.
"""

import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, TextIO

from fly_in.models.graph import Graph
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.simulator import Move, Replan
from fly_in.visualization.event_log import EventLog
from fly_in.visualization.palette import UI_TEXT, UI_TITLE, UI_WARN, Painter
from fly_in.visualization.playback_controller import PlaybackController
from fly_in.visualization.recorder import ReplayRecorder
from fly_in.visualization.scene import Scene

# Segundos por turno de cada vista si no se pasa --delay.
DEFAULT_DELAYS = {"window": 0.8, "log": 0.25}
# La cuenta atrás: se ve a la vez en la ventana y en la terminal.
COUNTDOWN = (("3", 0.5), ("2", 0.5), ("1", 0.5), ("GO", 0.5))
# Cuánto espera la tarjeta final a que se pulse una tecla.
END_HOLD = 20.0


class AnimatedView(Protocol):
    """Lo que `Session` necesita de la ventana (la cumple PygameView).

    Con un Protocol, este módulo no importa pygame: solo se importa cuando
    de verdad se va a abrir una ventana.
    """

    closed: bool

    def play_turn(self, turn: int, seconds: float) -> None:
        """Anima el turno `turn` durante `seconds`."""
        ...


@dataclass(frozen=True)
class Run:
    """Una simulación terminada, lista para enseñarse."""

    graph: Graph
    nb_drones: int
    trace: Sequence[Sequence[Move]]
    recorder: ReplayRecorder
    metrics: Metrics
    replans: Sequence[Replan]
    title: str
    window: int
    target: Optional[int] = None


class Session:
    """Enseña un `Run` en la vista 'window' o 'log'."""

    def __init__(
        self, view: str, run: Run, paint: Painter, stream: TextIO,
        pace: float,
    ) -> None:
        """Prepara la sesión.

        Args:
            view: 'window' o 'log'.
            run: La simulación ya calculada.
            paint: El Painter (con o sin color).
            stream: Dónde escribir el log (stderr).
            pace: Segundos por turno (0 = todo de golpe).
        """
        self.view = view
        self.run = run
        self.paint = paint
        self.pace = pace
        self.log = EventLog(run.graph, run.nb_drones, stream, paint,
                            run.title, run.window, run.target)

    @staticmethod
    def display_available() -> bool:
        """¿Hay una pantalla gráfica donde abrir una ventana?"""
        if sys.platform in ("darwin", "win32"):
            return True
        return bool(
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        )

    @staticmethod
    def choose_view(requested: str, quiet: bool, interactive: bool) -> str:
        """La vista efectiva: 'none', 'window' o 'log'."""
        if quiet:
            return "none"
        if requested != "auto":
            return requested
        if interactive and Session.display_available():
            return "window"
        return "log"

    def play(self) -> None:
        """Enseña la simulación entera y cierra con el resumen."""
        if self.view == "none":
            return
        if self.view == "window" and self._play_window():
            return
        self.log.briefing(self.paint("terminal log", fg=UI_TEXT))
        self._play_log()
        self.log.finish(self.run.metrics, len(self.run.replans))

    # --- internos ------------------------------------------------------

    def _play_window(self) -> bool:
        """La partida en la ventana y en la terminal a la vez.

        Devuelve False si no se puede abrir la ventana: `play` sigue
        entonces con la terminal sola.
        """
        # pygame saluda por stdout al importarse, y stdout es solo para
        # las líneas del subject. La variable lo silencia.
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            from fly_in.visualization.pygame_view import PygameView
        except ImportError:
            self.log.note("pygame is not installed · terminal only",
                          UI_WARN)
            return False
        run = self.run
        scene = Scene(run.graph, run.recorder.positions,
                      run.recorder.lines, run.replans)
        controller = PlaybackController(len(run.trace))
        with PygameView(scene, run.title, run.window,
                        run.target, controller) as window:
            if not window.open():
                self.log.note("cannot open a window · terminal only",
                              UI_WARN)
                return False
            self.log.briefing(self.paint("◉ WINDOW  ", fg=UI_TITLE,
                                         bold=True)
                              + self.paint("pygame · SPACE pause · "
                                           "ESC close", fg=UI_TEXT))
            for value, seconds in COUNTDOWN:
                self.log.countdown(value)
                window.countdown(value, seconds if self.pace else 0.0)
            self._play_log(window)
            self.log.finish(run.metrics, len(run.replans))
            if not window.closed:
                window.finish(run.metrics, END_HOLD if self.pace else 0.0)
        return True

    def _play_log(self, window: Optional[AnimatedView] = None) -> None:
        """Un bloque de log por turno; con ventana, la animación del turno.

        El bloque se escribe justo antes de animar el turno, así las dos
        pantallas enseñan el mismo turno a la vez. Si el usuario cierra la
        ventana, se avisa una vez y la terminal sigue a su ritmo.
        """
        run = self.run
        replans: Dict[int, List[Replan]] = {}
        for replan in run.replans:
            replans.setdefault(replan.turn, []).append(replan)
        warned = False
        for number, moves in enumerate(run.trace, start=1):
            # La replanificación del instante T precede al turno T+1.
            self.log.turn(number, moves, run.recorder.positions[number],
                          replans.get(number - 1, []))
            if window is not None and not window.closed:
                window.play_turn(number, self.pace)
                continue
            if window is not None and not warned:
                warned = True
                self.log.note("window closed · terminal only", UI_WARN)
            if self.pace > 0:
                time.sleep(self.pace)
