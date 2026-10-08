"""How an already computed simulation is shown (SP10).

The simulation takes milliseconds; what takes time is showing it. There
are two views:

- `window`: the run animated in a pygame window and the event log in the
  terminal, advancing together turn by turn.
- `log`: only the event log in the terminal.

`auto` picks `window` if there is a terminal and a graphical display, and
`log` otherwise: with a pipe or without a display it never tries to open a
window.
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
from fly_in.visualization.recorder import ReplayRecorder
from fly_in.visualization.scene import Scene

# Seconds per turn of each view when --delay is not given.
DEFAULT_DELAYS = {"window": 0.8, "log": 0.25}
# The countdown: shown at the same time in the window and the terminal.
COUNTDOWN = (("3", 0.5), ("2", 0.5), ("1", 0.5), ("GO", 0.5))
# How long the final summary waits for a key press.
END_HOLD = 20.0


class AnimatedView(Protocol):
    """What `Session` needs from the window (PygameView satisfies it).

    With a Protocol, this module does not import pygame: it is imported
    only when a window is actually going to be opened.
    """

    closed: bool

    def play_turn(self, turn: int, seconds: float) -> None:
        """Animate turn `turn` for `seconds`."""
        ...


@dataclass(frozen=True)
class Run:
    """A finished simulation, ready to be shown."""

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
    """Show a `Run` in the 'window' or 'log' view."""

    def __init__(
        self, view: str, run: Run, paint: Painter, stream: TextIO,
        pace: float,
    ) -> None:
        """Set up the session.

        Args:
            view: 'window' or 'log'.
            run: The already computed simulation.
            paint: The Painter (with or without color).
            stream: Where to write the log (stderr).
            pace: Seconds per turn (0 = everything at once).
        """
        self.view = view
        self.run = run
        self.paint = paint
        self.pace = pace
        self.log = EventLog(run.graph, run.nb_drones, stream, paint,
                            run.title, run.window, run.target)

    @staticmethod
    def display_available() -> bool:
        """Is there a graphical display to open a window on?"""
        if sys.platform in ("darwin", "win32"):
            return True
        return bool(
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        )

    @staticmethod
    def choose_view(requested: str, quiet: bool, interactive: bool) -> str:
        """The effective view: 'none', 'window' or 'log'."""
        if quiet:
            return "none"
        if requested != "auto":
            return requested
        if interactive and Session.display_available():
            return "window"
        return "log"

    def play(self) -> None:
        """Show the whole simulation and close with the summary."""
        if self.view == "none":
            return
        if self.view == "window" and self._play_window():
            return
        self.log.briefing(self.paint("terminal log", fg=UI_TEXT))
        self._play_log()
        self.log.finish(self.run.metrics, len(self.run.replans))

    # --- internals -----------------------------------------------------

    def _play_window(self) -> bool:
        """The run in the window and in the terminal at the same time.

        Returns False if the window cannot be opened: `play` then carries
        on with the terminal alone.
        """
        # pygame prints a greeting on stdout when imported, and stdout is
        # only for the lines of the subject. The variable silences it.
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
        with PygameView(scene, run.title, run.window,
                        run.target) as window:
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
        """One log block per turn; with a window, the turn's animation.

        The block is written right before animating the turn, so both
        screens show the same turn at the same time. If the user closes the
        window, it warns once and the terminal goes on at its own pace.
        """
        run = self.run
        replans: Dict[int, List[Replan]] = {}
        for replan in run.replans:
            replans.setdefault(replan.turn, []).append(replan)
        warned = False
        for number, moves in enumerate(run.trace, start=1):
            # The replan at instant T comes before turn T+1.
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
